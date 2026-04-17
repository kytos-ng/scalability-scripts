#!/usr/bin/env python
# -*- coding: utf-8 -*-
import httpx
import logging

from clients.common import base_url, headers

log = logging.getLogger(__name__)


class FlowManagerClient:
    """Async client for kytos/flow_manager."""

    def _base_url(self, dpid: str) -> str:
        return f"{base_url()}/kytos/flow_manager/v2/flows/{dpid}"

    async def list_flows(
        self,
        dpid: str,
        cookie_range: tuple[int, int] | None = None,
    ) -> dict:
        """List flows installed on a switch.

        cookie_range: (min, max) passed as two cookie_range query args (gte, lte).
        """
        qs = f"state=installed&dpid={dpid}"
        if cookie_range is not None:
            qs += f"&cookie_range={cookie_range[0]}&cookie_range={cookie_range[1]}"
        url = f"{base_url()}/kytos/flow_manager/v2/stored_flows?{qs}"
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.get(url, timeout=60)
            try:
                r.raise_for_status()
            except httpx.HTTPError as exc:
                log.error(exc.response.text)
            return r.json()

    async def install_port_flows(
        self,
        dpid: str,
        n: int = 1000,
        port_a: int = 1,
        port_z: int = 2,
        priority_start: int = 1,
        cookie: int = 0xBB00000000000000,
    ) -> dict:
        """Install n flows between two ports with incrementing priority.

        For each flow i (0..n-1):
          - match in_port=port_a, priority=priority_start+i -> output port_z
          - match in_port=port_z, priority=priority_start+i -> output port_a
        """
        flows = []
        for i in range(n):
            priority = priority_start + i
            flows.append(
                {
                    "priority": priority,
                    "cookie": cookie + priority,
                    "match": {"in_port": port_a},
                    "actions": [{"action_type": "output", "port": port_z}],
                }
            )
            flows.append(
                {
                    "priority": priority,
                    "cookie": cookie + priority,
                    "match": {"in_port": port_z},
                    "actions": [{"action_type": "output", "port": port_a}],
                }
            )

        log.info(
            f"Installing {len(flows)} flows on {dpid} "
            f"(ports {port_a}<->{port_z}, priorities {priority_start}-{priority_start + n - 1}) ..."
        )
        async with httpx.AsyncClient(timeout=60) as client:
            try:
                r = await client.post(
                    self._base_url(dpid),
                    json={"flows": flows},
                    headers=headers(),
                    timeout=60,
                )
                r.raise_for_status()
                res = r.json()
                log.info(f"Installed {len(flows)} flows on {dpid}")
                return res
            except httpx.HTTPError as exc:
                log.error(exc.response.text)
                raise

    async def delete_flows(
        self,
        dpid: str,
        cookie: int = 0xBB00000000000000,
        cookie_mask: int = 0xFF00000000000000,
    ) -> dict:
        """Delete flows matching cookie from a switch."""
        log.info(f"Deleting flows on {dpid} (cookie={cookie:#x}) ...")
        async with httpx.AsyncClient(timeout=60) as client:
            try:
                r = await client.request(
                    "DELETE",
                    self._base_url(dpid),
                    json={"flows": [{"cookie": cookie, "cookie_mask": cookie_mask}]},
                    headers=headers(),
                    timeout=60,
                )
                r.raise_for_status()
                res = r.json()
                log.info(f"Deleted flows on {dpid}")
                return res
            except httpx.HTTPError as exc:
                log.error(exc.response.text)
                raise
