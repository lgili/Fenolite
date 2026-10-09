## Why

This is a proposal of milestone v0.4 (`docs/roadmap.md`, "v0.4: proposals on other branches", row c0109), written against `origin/dev` at `9aba2dff`, where both plugins are as they were when a review of 2026-10-05 found that neither can be steered on a board of hundreds of nets:

- KiCadRoutingTools runs one process per net, 600 s each, in name order, with no bound on the job; the living spec says one run.
- Freerouting gets every net, routes those `route` did not select, zone nets included, and Fenolite throws that copper away.
- A Freerouting run that reaches its time limit returns nothing.

Measured on 2026-10-05 on a generated 4-layer board of 100 parts (101 signal nets, GND and +3V3 on inner zones): `fenolite route --router freerouting --timeout 900` exited 5 after 912 s with no copper. Freerouting had closed every connection at 256 s, GND and +3V3 included (191 items, not 103), then ran its optimizer until killed. Without both, the board routed in 112 CPU seconds with no open signal connection. KiCadRoutingTools, one process per net, left two nets crossing; one process for the same 28 nets left none, in a quarter of the time.

## What Changes

- **One budget per route.** `--timeout` bounds the whole `route` step for every router (default 900 s); the per-net limit and the 600 s sentinel go.
- **Finished runs are kept.** When the budget ends, the copper of finished router runs is written and the run under way is stopped. `route.budget-exhausted` (warning), `result.budget`, `result.runs`, `result.not_attempted`.
- **KiCadRoutingTools in groups.** One process per group of nets with equal track width and via sizes; clearances from the project file; sizes kept exact. `group-nets=N` splits a group.
- **Tiers.** `--order GLOB` (repeatable) routes the matching nets first; later tiers see earlier copper as fixed.
- **Freerouting sees only its nets.** Nets outside the job leave the network section of the design file; their pins and copper stay as obstacles.
- **Freerouting's optimizer off by default.** `optimize=on` runs it afterwards on the time left and keeps the first session if it is cut.
- **The plugins' spec text** matches the code.

Size: 7 design-days; cut order in the design.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `routing`: MODIFIED "KiCadRoutingTools plugin", "Freerouting plugin"; ADDED "Routing time budget", "Routing tiers".
- `specctra-dsn`: ADDED "Nets outside the routing job in design files".
- `cli-contract`: ADDED "Route command budget and tiers".
- `kicad-oracle`: ADDED "Grouped and budgeted routes pass the oracle".

## Non-goals

- Progress lines and resumable job files: c0120; a cut job resumes with `route` again, which selects the open nets (c0108).
- Open-net selection, locks, failing on open nets: c0108. Planes, layers and rules for routers: c0107. Pairs and escape: c0110.
- The scheduled routing run on a large board and its budgets: c0119.
- Rip-up across KiCadRoutingTools processes: nowhere in v0.4, because the plugin never removes copper it did not add (c0016).
- A net order inside one Freerouting run: nowhere, because Freerouting 2.4.1 documents none.
- **Limits.** A run stopped by the budget gives no copper: Freerouting writes only at the end, and a killed KiCadRoutingTools output is not trusted. A job of one run keeps nothing when cut. `optimize=on` repeats the autorouter first.

## Evidence level required

- `H-G-DSN-NOOPT`, `H-G-DSN-NETLESS`: `ORACLE-VERIFIED(freerouting 2.4.1)`. `H-K-KRT-GROUP`: `KICAD-VERIFIED (9.0.x, 10.0.x)` for the pinned tag.
- Budget, runs, tiers and groups: mechanical, with the fake tools. `route` results stay `UNVERIFIED`.

## Impact

- Changed: the `routing` package (new `budget.py`), `backends/specctra/dsn.py`, `cli/cmd_route.py`, the routing pages of `docs/`.
- `--timeout` bounds the job for KiCadRoutingTools. Freerouting runs without its optimizer unless asked. Reaching the budget is a warning, not exit 5.
- No model field and no schema change: a model document written after this change is read by 0.2.x and 0.3.x as before. New result keys `budget`, `runs`, `not_attempted`; new flag `--order`; two new codes with their `explain` entries.

## Prerequisites

On `dev` before the first task:

- Release `0.3.0`. Nothing of the Altium write side is touched: `route` works on a KiCad board, and no rule kind, model field or Altium requirement changes here.
- c0108 (`route-open-nets`), hard: an error plans no write, and a cut job resumes through its selection.
- c0107 (`route-planes-layers`): the netless mode keeps a plane's net declared and builds on its text of "Design files are written from the model"; `budget` and `tier` come after its job fields.
- c0078 (`router-fetch`, agent track): it modifies "Freerouting plugin" (the jar's third location). The fixed order for that requirement is c0078, then c0109, then c0110; each delta is regenerated from the living text the one before left (task 0.1).
- Not needed first: c0096, c0097, c0099.
- After this change: c0110 (its pair and escape steps are runs inside this budget; it regenerates "Freerouting plugin" and "KiCadRoutingTools plugin" readings from this text), c0119.
