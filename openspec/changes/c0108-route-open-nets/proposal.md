## Why

This is a proposal of milestone v0.4 (`docs/roadmap.md`, "v0.4: proposals on other branches", row c0108), written against `origin/dev` at `9aba2dff`. `fenolite route` takes a net only when it has no track, arc or via. A review of 2026-10-05 found, this change measured, and that commit still shows:

- A 3 mm script stub keeps its net out of every later run, although the net is open. Only `--rip` brings it back, and it deletes the stub.
- A track written `(locked yes)` is read without its lock and removed by `--rip`.
- When a router returns copper but reports every net open, `route` writes nothing and exits 0.
- `route` exits 0 however many nets stay open.
- Only KiCad's DRC says which connections are open, and its report stops at 499 items. `checks.equivalence.routing.pieces` (c0089, on `dev`) gives the connected pieces of a net for the comparison of two designs; it gives no open connection, no count per net against KiCad's, and shapes pads from the model alone.

## What Changes

- **Open connections from the board.** `analysis.connectivity` finds the copper islands of each net and joins them by a minimum spanning tree of nearest anchors (pads, track and arc ends, vias). Islands of zone fills alone do not count. The union of touching copper becomes one function, `geometry.touch_groups`, shared with `pieces`. Measured on 2026-10-05: the count per net equals KiCad's `unconnected_items` on 19 bench cases (9.0.9, 10.0.6), on 20 of the 21 corpus boards readable that day (task 1.4 counts again on the manifest of `dev`) and on generated 4-layer boards of 100 to 400 parts.
- **Selection by open connections.** `route` takes the nets with two or more pads and an open connection. Script copper and earlier routes stay; the router connects to them (Freerouting 2.4.1: 8 of 8 nets closed).
- **The verdict after the merge.** `routed`, `unrouted` and the new `result.open` come from the open connections after the merge, not from the router.
- **Partial copper is kept** and written, with `route.partial` (info).
- **`--require-complete`.** A selected net still open gives `route.incomplete` (error): exit 5, nothing written.
- **Locks.** `Track`, `Arc` and `Via` gain `locked`, read and written as `(locked yes)`. `--rip` keeps locked and script copper. `Design.track`, `via` and `stitch` take `locked=`.
- **Locks in the second backend** (decision of the maintainer, 2026-10-07). An Altium build writes the lock bit of a locked track, arc or via, and the Altium import reads it. The format fact is recorded first, from a public source; a record kind without its fact row is written unlocked with one `altium.not-lowered` warning, never in silence.
- **`fenolite net`** gives `islands` and `open` per net.

Size: 6.5 design-days; cut order in the design.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `board-analyses`: ADDED "Open connections of a net".
- `routing`: MODIFIED "Net selection"; ADDED "Router copper on open nets".
- `cli-contract`: MODIFIED "Route command"; ADDED "Open connections in the net command".
- `geometry-kernel`: ADDED "Groups of touching thick shapes".
- `design-model`: ADDED "Copper locks in the board model".
- `altium-pcb-writer`: MODIFIED "PCB units and record framing", "Via records"; ADDED "Locked copper records".
- `altium-build`: ADDED "Copper locks in an Altium build".
- `altium-import`: ADDED "Copper locks from an Altium board".
- `kicad-file-backend`: ADDED "Copper locks on boards".
- `design-dsl`: ADDED "Copper locks in the DSL".
- `manual-copper`: ADDED "Locked script copper".
- `kicad-oracle`: ADDED "Open connections agree with unconnected items", "Copper locks pass the oracle", "Routing of open nets passes the oracle".

## Non-goals

- Net order, time budgets, partial sessions: c0109. Plane nets and fan-out: c0107. Pairs and escape: c0110.
- A connectivity stage in `check`, and counts above KiCad's 499: c0120.
- Copper drawings with a net (a `gr_rect` on copper holding `net`): a change of its own, not among the proposals of v0.4; until then such a net reads open and the census names the board.
- Locks of other Altium objects (pads, fills, regions, texts, polygons): nowhere here; a component's lock is already read and written.
- Altium Designer's own view of the lock bit: an author report on the verification kit (`H-A-PCB-CU-LOCK`), not a gate of this change.
- Script copper locked by default: nowhere, because it would rewrite every board with script copper (Decision 6).
- A retry loop inside one run: nowhere, because the agent runs `route` again.

## Evidence level required

- `H-K-CONN-PARITY`: `KICAD-VERIFIED (9.0.x, 10.0.x)` on the bench, `CORPUS-VERIFIED` on the census.
- `H-K-LOCK-FORM`: `KICAD-VERIFIED (9.0.x, 10.0.x)`.
- `H-G-DSN-PARTIAL`: `ORACLE-VERIFIED(freerouting 2.4.1)`; `H-K-KRT-PARTIAL` when a checkout runs.
- `H-A-PCB-CU-LOCK`: `INFERRED` (a public source and Fenolite's own reader); `ALTIUM-VERIFIED(author-report)` only after a kit run.
- Limits: anchors may differ from the items KiCad names; a net joined only by a copper drawing reads open; arcs are judged within 1 µm; fills as stored.
- Routes stay `UNVERIFIED`.

## Impact

- New `analysis/connectivity.py` and `geometry.touch_groups` (moved out of `checks/equivalence/routing.py`); changed `backends/altium/pcbrecords.py`, `pcbdoc.py`, the Altium adapter and `lens/altium_copper.py`; changed `routing/select.py`, `cli/cmd_route.py`, `cli/cmd_net.py`, `model/board.py`, `backends/kicad/pcb.py` and `copper.py`, `dsl/intents.py` and `design.py`, the board schema.
- `route` selects nets it skipped before; `routing.select.unrouted` takes `open_nets`.
- `board.json` gains the key `locked` on tracks, arcs and vias: releases 0.2.x and 0.3.x cannot read a model document that carries it; a design without locked copper keeps its bytes.

## Prerequisites

On `dev` before the first task:

- Release `0.3.0`: c0085 and c0128 archived (both modify "Via records"; this delta is regenerated from their text, task 0.1), c0124 and c0132 archived (both modify the import's "Tracks, arcs and vias", which this change extends with an ADDED requirement), c0126 archived (its 0.2.0 fixture serves the compatibility scenario).
- Met on `9aba2dff`: c0066 (the `net` view and paging), c0068 (copper intents) and c0089 (`pieces`), all archived.
- Not needed first: c0096 (its `locked` is the placement lock of a part, another field), c0097, c0099.
- No proposal of v0.4 must land before this one. After it: c0107 (the fan-out step uses this selection and write rule), c0109, c0110, c0111, c0112 (`Via` field order; it regenerates "Via records"), and the DRC and connectivity parts split out of c0120.
