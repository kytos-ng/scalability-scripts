#!/usr/bin/env python
# -*- coding: utf-8 -*-
import httpx
import itertools
import logging

from clients.common import base_url, headers
from clients.mef_eline import MEFClient

log = logging.getLogger(__name__)


def _parse_interface_id(interface_id: str) -> tuple[str, int]:
    """Parse an interface_id into (dpid, port_number).

    e.g. '00:00:00:00:00:00:00:01:1' -> ('00:00:00:00:00:00:00:01', '1')
    """
    parts = interface_id.rsplit(":", 1)
    return parts[0], int(parts[1])


def _build_trace_entries(evcs: dict) -> list[dict]:
    """Build trace entries for both directions of each EVC.

    Returns a list of dicts with 'trace' payload and 'evc_id' / 'direction'
    metadata for result verification.
    """
    entries = []
    for evc_id, evc in evcs.items():
        uni_a = evc.get("uni_a", {})
        uni_z = evc.get("uni_z", {})
        tag_a = uni_a.get("tag", {}).get("value")
        tag_z = uni_z.get("tag", {}).get("value")

        if uni_a.get("interface_id") and tag_a is not None:
            dpid, port = _parse_interface_id(uni_a["interface_id"])
            entries.append({
                "evc_id": evc_id,
                "direction": "forward",
                "trace": {
                    "switch": {"dpid": dpid, "in_port": port},
                    "eth": {"dl_vlan": tag_a},
                },
            })

        if uni_z.get("interface_id") and tag_z is not None:
            dpid, port = _parse_interface_id(uni_z["interface_id"])
            entries.append({
                "evc_id": evc_id,
                "direction": "reverse",
                "trace": {
                    "switch": {"dpid": dpid, "in_port": port},
                    "eth": {"dl_vlan": tag_z},
                },
            })

    return entries


def _check_trace_result(
    entry: dict,
    result: list[dict],
    evcs: dict,
) -> dict:
    """Check whether a single trace result reached the expected endpoint.

    Returns a dict with evc_id, direction, success, and detail.
    """
    evc_id = entry["evc_id"]
    direction = entry["direction"]
    evc = evcs[evc_id]

    if direction == "forward":
        expected_intf = evc["uni_z"]["interface_id"]
    else:
        expected_intf = evc["uni_a"]["interface_id"]

    expected_dpid, expected_port = _parse_interface_id(expected_intf)

    if not result:
        return {
            "evc_id": evc_id,
            "direction": direction,
            "success": False,
            "detail": "empty trace result",
        }

    last_step = result[-1]
    last_dpid = last_step.get("dpid", "")

    success = last_dpid == expected_dpid
    return {
        "evc_id": evc_id,
        "direction": direction,
        "success": success,
        "detail": (
            "ok"
            if success
            else f"expected dpid {expected_dpid}, got {last_dpid}"
        ),
    }


class SDNTraceClient:
    """Async client for kytos-ng/sdntrace_cp."""

    def __init__(self, mef_client: MEFClient | None = None) -> None:
        self._mef = mef_client or MEFClient()

    async def run_traces(
        self,
        trace_entries: list[dict],
        max_concurrency: int = 50,
    ) -> list[list[dict]]:
        """Submit traces in batches and return results in order."""
        payloads = [{"trace": e["trace"]} for e in trace_entries]
        url = f"{base_url()}/amlight/sdntrace_cp/v1/traces"
        all_results: list[list[dict]] = []
        print(url)

        async with httpx.AsyncClient(timeout=60) as client:
            for batch in itertools.batched(
                enumerate(payloads), max_concurrency
            ):
                batch_indices, batch_payloads = zip(*batch)
                try:
                    r = await client.put(
                        url,
                        json=list(batch_payloads),
                        headers=headers(),
                        timeout=60,
                    )
                    r.raise_for_status()
                    data = r.json()
                    all_results.extend(data["result"])
                except httpx.HTTPError as exc:
                    raise ValueError(
                        f"sdntrace_cp traces failed: {exc.response.text}"
                    ) from exc

        return all_results

    async def trace_evcs(
        self,
        max_concurrency: int = 50,
        return_failed_only=True,
    ) -> list[dict]:
        """List all EVCs, trace each one in both directions, and verify.

        Returns a list of check results with evc_id, direction, success,
        and detail.
        """
        evcs = await self._mef.list_evcs()
        if not evcs:
            log.info("No EVCs found, nothing to trace")
            return []

        entries = _build_trace_entries(evcs)
        log.info(
            f"Tracing {len(evcs)} EVCs ({len(entries)} trace entries), "
            f"max_concurrency {max_concurrency} ..."
        )

        results = await self.run_traces(entries, max_concurrency=max_concurrency)

        checks = []
        for entry, result in zip(entries, results):
            check = _check_trace_result(entry, result, evcs)
            checks.append(check)
            if not check["success"]:
                log.warning(
                    f"Trace FAILED evc={check['evc_id']} "
                    f"direction={check['direction']}: {check['detail']}"
                )

        passed = sum(1 for c in checks if c["success"])
        failed = len(checks) - passed
        log.info(f"Trace results: {passed} passed, {failed} failed out of {len(checks)}")

        if return_failed_only:
            checks = [c for c in checks if not c["success"]]

        return checks
