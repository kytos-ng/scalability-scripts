#!/usr/bin/env python
# -*- coding: utf-8 -*-
import asyncio
import sys
import logging

from clients.flow_manager import FlowManagerClient
from clients.mef_eline import MEFClient
from clients.sdntrace_cp import SDNTraceClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(threadName)s] %(name)s.%(module)s:%(lineno)d - %(message)s",
)
log = logging.getLogger(__name__)

httpx_log = logging.getLogger("httpx")
httpx_log.setLevel(logging.WARNING)

mef_eline = MEFClient()
sdntrace_cp = SDNTraceClient(mef_eline)
flow_manager = FlowManagerClient()

sw1 = "00:00:00:00:00:00:00:01"
sw2 = "00:00:00:00:00:00:00:02"
sw3 = "00:00:00:00:00:00:00:03"


async def main() -> None:
    try:
        res = await mef_eline.del_evcs()
        print(res)
        n_evcs = 500
        max_concurrency = 100
        res = await mef_eline.create_dyn_evpls(
            vlan_i=100, n=n_evcs, max_concurrency=max_concurrency
        )
        print(res)
        wait_for = 10
        log.info(f"Waiting for {wait_for}s before running SDN traces ...")
        await asyncio.sleep(wait_for)
        checks = await sdntrace_cp.trace_evcs(max_concurrency=max_concurrency)
        if checks:
            log.error(f"Traces failed: {checks}")
            sys.exit(1)
        res = await mef_eline.del_evcs()
        print(res)
    except Exception as exc:
        log.error(str(exc))
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
