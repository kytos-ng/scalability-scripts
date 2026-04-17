# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Scalability scripts for locally exploring Kytos-ng NApps during development. Scripts create, manage, and verify EVCs (Ethernet Virtual Connections) at scale against a local Kytos-ng instance at `http://localhost:8181/api`. 

Each topology will have basic scripts to test network services scalability such as EVCs, and then in interactive mode with `ipython` you can explore it as you wish, which is the mode you should be using when freely exploring including also performing mininet network convergence operation like interface shutdown.

## Commands

```bash
# Install dependencies (uses uv)
uv sync

# Start the ring3 Mininet topology (requires Mininet installed) in another terminal
sudo mn --custom mn-topos/topos.py --topo ring3

# Interactive usage with IPython (examples in the sections below)
uv run ipython
# >>> from ring3_evcs import *

# Or run the main ring3 EVC scalability script
uv run python ring3_evcs.py

```

## Architecture

All clients are async (httpx + asyncio) and live in `clients/`. They share base URL and headers from `clients/common.py`.

- **`clients/mef_eline.py`** (`MEFClient`) - CRUD operations for EVCs via the `mef_eline/v2` API. Bulk operations use `itertools.batched()` with a configurable `max_concurrency`.
- **`clients/sdntrace_cp.py`** (`SDNTraceClient`) - Runs control plane traces via `amlight/sdntrace_cp/v1`. Reuses `MEFClient.list_evcs()` to fetch EVCs, builds trace payloads for both directions (forward/reverse), submits them via `PUT /traces`, and verifies each trace reached the expected destination switch.
- **`clients/flow_manager.py`** (`FlowManagerClient`) - Install, list, and delete flows via `kytos/flow_manager/v2`. Flows use a `0xBB` cookie prefix. `install_port_flows` creates bidirectional flows between two ports with incrementing priorities. `list_flows` queries `stored_flows` with optional `cookie_range` filtering. `delete_flows` removes flows matching the cookie prefix.

Entry point scripts (e.g., `ring3_evcs.py`) compose these clients into workflows and export client instances and switch aliases (`sw1`, `sw2`, `sw3`) for interactive IPython use.

Note: query params with colons (e.g., dpid) must be built as raw strings to avoid URL-encoding — do not use httpx `params=` for these.

`mn-topos/topos.py` defines Mininet topologies (ring3: 3 switches in a ring, 4 hosts).

## Topologies

The following minimal topologies are used in the scripts:

1) ring3

## IPython examples

Start IPython from the project root. The `ring3_evcs` module sets up clients and switch aliases for the ring3 topology.

```python
from ring3_evcs import *
```

This gives you: `mef_eline`, `sdntrace_cp`, `flow_manager`, `sw1`, `sw2`, `sw3`.

### mef_eline and sdntrace_cp

```python
# Create 1000 dynamic EVPLs starting at VLAN 1000
await mef_eline.create_dyn_evpls(vlan_i=1000, n=1000, max_concurrency=100)

# List all EVCs
evcs = await mef_eline.list_evcs()
len(evcs)

# Trace all EVCs (both directions) and verify
checks = await sdntrace_cp.trace_evcs(max_concurrency=100)
# returns only failed traces by default (return_failed_only=True)
print(checks)

# Trace and return all results
checks = await sdntrace_cp.trace_evcs(return_failed_only=False)
[c for c in checks if c["success"]]

# Create more 500 static EVPLs with default primary/backup paths
evcs = await mef_eline.create_static_evpls(vlan_i=3000, n=500, max_concurrency=100)

# Delete all EVCs
evcs = await mef_eline.del_evcs()
```

### flow_manager

```python
# Install 500 bidirectional flows on sw1 between ports 1 and 2
await flow_manager.install_port_flows(sw1, n=500, port_a=1, port_z=2)

# List installed flows on sw1
flows = await flow_manager.list_flows(sw1)
len(flows[sw1])

# List flows filtered by cookie range
await flow_manager.list_flows(sw1, cookie_range=(0xBB00000000000001, 0xBB000000000001F4))

# Install flows on sw2 with custom priority start
await flow_manager.install_port_flows(sw2, n=100, port_a=2, port_z=3, priority_start=500)

# Delete flows matching the default cookie prefix (0xBB) on sw1
await flow_manager.delete_flows(sw1)

# Delete flows on all switches with cookie 0xBB prefix
await flow_manager.delete_flows(sw1)
await flow_manager.delete_flows(sw2)
await flow_manager.delete_flows(sw3)
```
