#!/usr/bin/env python
# -*- coding: utf-8 -*-
import httpx
import asyncio
from typing import Optional
from clients.common import base_url, headers
import itertools
import logging

log = logging.getLogger(__name__)


class MEFClient:
    """MEFClient."""

    async def _create_evc(
        self,
        flows: dict,
        client: httpx.AsyncClient,
    ) -> dict:
        """Create EVC."""
        url = f"{base_url()}/kytos/mef_eline/v2/evc/"
        r = await client.post(url, json=flows, headers=headers(), timeout=60)
        r.raise_for_status()
        res = r.json()
        return res

    async def _del_evc(
        self,
        evc_id: str,
        client: httpx.AsyncClient,
    ) -> dict:
        """Create EVC."""
        url = f"{base_url()}/kytos/mef_eline/v2/evc/{evc_id}"
        r = await client.delete(url, headers=headers(), timeout=60)
        r.raise_for_status()
        res = r.json()
        return res

    async def list_evcs(
        self,
    ) -> dict:
        """List EVCs."""
        url = f"{base_url()}/kytos/mef_eline/v2/evc/"
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.get(url, headers=headers(), timeout=60)
            r.raise_for_status()
            res = r.json()
            return res

    async def del_evcs(
        self,
        max_concurrency: Optional[int] = None,
        wait=0,
    ) -> list[str]:
        """Delete EVCs."""
        log.info("Deleting EVCs... ")
        async with httpx.AsyncClient(timeout=60) as client:
            evcs = await self.list_evcs()
            if not evcs:
                return []
            res = []
            max_concurrency = (
                max_concurrency
                if max_concurrency and max_concurrency > 0
                else len(evcs)
            )
            log.info(
                f"Deleting {len(evcs)} EVCs, max_concurrency {max_concurrency} ..."
            )
            for batch in itertools.batched(
                zip((self._del_evc(evc_id, client) for evc_id in evcs), evcs),
                max_concurrency,
            ):
                try:
                    tasks = []
                    for task, evc_id in batch:
                        res.append(evc_id)
                        tasks.append(task)
                    log.info(f"Deleting {len(tasks)} EVCs ...")
                    await asyncio.gather(*tasks)
                    if wait:
                        log.info(f"del_evcs will wait for {wait}s ...")
                except httpx.HTTPError as exc:
                    log.error(exc.response.text)
                    raise
            return res

    async def _create_evpls(
        self,
        vlan_i=1,
        n=100,
        uni_a="00:00:00:00:00:00:00:01:1",
        uni_z="00:00:00:00:00:00:00:03:1",
        primary_path=None,
        backup_path=None,
        queue_id=None,
        metadata=None,
        name_prefix="evpl",
        max_concurrency=50,
        wait=1,
    ):
        max_concurrency = max_concurrency if max_concurrency > 0 else 50
        log.info(f"Creating {n} EVPLs, max_concurrency {max_concurrency} ...")
        async with httpx.AsyncClient(timeout=60) as client:
            res = []
            for batch in itertools.batched(range(vlan_i, vlan_i + n), max_concurrency):
                tasks = []
                for vlan in batch:
                    payload = {
                        "name": f"{name_prefix}-{vlan}",
                        "dynamic_backup_path": True,
                        "uni_a": {
                            "interface_id": uni_a,
                            "tag": {"tag_type": "vlan", "value": vlan},
                        },
                        "uni_z": {
                            "interface_id": uni_z,
                            "tag": {"tag_type": "vlan", "value": vlan},
                        },
                    }
                    if primary_path or backup_path:
                        payload.pop("dynamic_backup_path")
                        payload["primary_path"] = primary_path
                        payload["backup_path"] = backup_path
                    if metadata:
                        payload["metadata"] = metadata
                    if queue_id:
                        payload["queue_id"] = queue_id
                    tasks.append(self._create_evc(payload, client))
                try:
                    res.extend(await asyncio.gather(*tasks))
                    if wait:
                        log.info(
                            f"Created {len(tasks)} EVCs, will wait for {wait}s ..."
                        )
                except httpx.HTTPError as exc:
                    log.error(exc.response.text)
                    raise
            return res

    async def create_dyn_evpls(
        self,
        vlan_i=1,
        n=100,
        uni_a="00:00:00:00:00:00:00:01:1",
        uni_z="00:00:00:00:00:00:00:03:1",
        queue_id=None,
        metadata=None,
        name_prefix="evpl-dynamic",
        max_concurrency=50,
        wait=1,
    ):
        """Create dynamic EVPLs."""
        return await self._create_evpls(
            vlan_i=vlan_i,
            n=n,
            uni_a=uni_a,
            uni_z=uni_z,
            queue_id=queue_id,
            metadata=metadata,
            name_prefix=name_prefix,
            max_concurrency=max_concurrency,
            wait=wait,
        )

    async def create_static_evpls(
        self,
        vlan_i=1,
        n=100,
        uni_a="00:00:00:00:00:00:00:01:1",
        uni_z="00:00:00:00:00:00:00:03:1",
        primary_path=None,
        backup_path=None,
        queue_id=None,
        metadata=None,
        name_prefix="evpl-static",
        max_concurrency=50,
        wait=1,
    ):
        """Create static EVPLs."""
        if not primary_path:
            primary_path = [
                {
                    "endpoint_a": {"id": "00:00:00:00:00:00:00:01:3"},
                    "endpoint_b": {"id": "00:00:00:00:00:00:00:02:2"},
                },
                {
                    "endpoint_a": {"id": "00:00:00:00:00:00:00:02:3"},
                    "endpoint_b": {"id": "00:00:00:00:00:00:00:03:2"},
                },
            ]
        if not backup_path:
            backup_path = [
                {
                    "endpoint_a": {"id": "00:00:00:00:00:00:00:03:3"},
                    "endpoint_b": {"id": "00:00:00:00:00:00:00:01:4"},
                }
            ]
        return await self._create_evpls(
            vlan_i=vlan_i,
            n=n,
            uni_a=uni_a,
            uni_z=uni_z,
            primary_path=primary_path,
            backup_path=backup_path,
            queue_id=queue_id,
            metadata=metadata,
            name_prefix=name_prefix,
            max_concurrency=max_concurrency,
            wait=wait,
        )
