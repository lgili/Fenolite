## Why

No router of Fenolite routes a differential pair or escapes a fine-pitch part: the routing protocol and the Specctra file hold no pair, and c0016 and c0023 made both non-goals. c0104 declares pairs; nothing makes their copper. This is a proposal of milestone v0.4 (`docs/roadmap.md`, "v0.4: proposals on other branches", row c0110), written against `origin/dev` at `9aba2dff`, where `routing/protocol.py` holds no pair, no escape and no feature, as when a review of 2026-10-05 found the gap.

Measured on 2026-10-05:

- Freerouting 2.4.1 routes the same with or without `(pair (nets P N))` lists: pairs as two single nets, which KiCad 9.0.9 and 10.0.6 report as out of gap and uncoupled.
- KiCadRoutingTools v0.22.1 (`route_diff.py`) routes them coupled at exactly the class gap over 93–97 % of their length, with no gap or uncoupled finding on either major. Its matching left 0.62 mm of skew on one pair; it skips `DP1`/`DN1`, which KiCad pairs.
- QFN-48 (0.5 mm): Freerouting connects all 40 nets, but with inner signal layers its fanout stage narrows tracks, which KiCad reports; KiCadRoutingTools leaves 2 open with its escape script, 5 without. BGA-121 (0.8 mm, 96 nets, two signal layers): Freerouting writes no session in 900 s, nor in 1800 s without its fanout stage; KiCadRoutingTools leaves 7 open with dog-bone escape, and routes nothing without it.

## What Changes

- **A feasibility gate first**, as in c0016: four authored benches, both tools, both majors; its verdict decides what is built.
- **Pairs in the routing job**: `JobPair`, `RoutingJob.pairs`: two selected nets that KiCad pairs by name (c0104), with their class pair values and skew limit. Routers declare `features`; one without `pairs` gets no pair net (`route.pair-skipped`), unless `--pairs-as-nets`.
- **KiCadRoutingTools routes pairs** (`route_diff.py`) at the job's sizes, without ground vias or polarity swaps.
- **Escape**: `fenolite route --escape REF[=grid|perimeter]`; KiCadRoutingTools runs `qfn_fanout.py` or `bga_fanout.py` (dog-bones) first. Freerouting runs without automatic neck-down and gains `fanout=off`.
- **Specctra**: no pair list is written.
- **Width guard**: copper narrower than its job gives `route.width-below-job`.

Size: 8 design-days.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `routing`: ADDED "Pairs and escape in a routing job", "Pair selection for routing", "Escape requests for routing", "KiCadRoutingTools routes pairs", "KiCadRoutingTools escapes parts", "Freerouting declares no router feature"; MODIFIED "Freerouting plugin" (neck-down always off, the option `fanout`).
- `specctra-dsn`: ADDED "Differential pairs in design files".
- `cli-contract`: ADDED "Pairs and escape in the route command", "Router pair and escape features in capabilities".
- `kicad-oracle`: ADDED "Pair and escape routes pass the oracle", "Pair coupling in KiCad's DRC is probed".

## Non-goals

- Pairs through Freerouting: nowhere, because 2.4.1 ignores them and Fenolite writes no router (plan D11).
- Ground vias beside pair vias: nowhere in v0.4, because a run lifts only selected nets.
- Per-layer pair widths: c0105.
- Matching across pairs: nowhere in v0.4, because the yardstick matches within pairs.
- Meanders on router copper: nowhere in v0.4, because the router's matching serves routed pairs and c0106 script copper.
- Vias in pads: c0111, c0112. Blind escape vias: nowhere in v0.4, because no yardstick item needs them.
- Neck-down areas (c0103) and hole clearance in a router: nowhere in v0.4, because c0107 sends neither.
- Polarity swaps: nowhere, because they change the netlist.
- Pairs in an Altium build: c0104's ground (the build reports a pair interface with `altium.not-lowered` today). This change adds no rule kind, no model field and no document content; a routed pair reaches an Altium build as tracks, through `--copper-from`.

Limits: a pair needs two selected nets of one class with pair values, whose names KiCad and the tool pair; a leg may be 0.4 µm narrower than asked; the tool may leave skew; per-part escape needs KiCadRoutingTools.

## Evidence level required

- `H-K-KRT-PAIR`, `H-K-KRT-ESCAPE`, `H-G-DSN-FANOUT`, `H-K-DRU-PAIRCOUPLE`: `KICAD-VERIFIED (9.0.x, 10.0.x)`.
- `H-K-KRT-PAIRNAMES`, `H-G-DSN-PAIR`, `H-G-DSN-NARROW`: `ORACLE-VERIFIED(<tool>)`.
- Protocol, selection, command: mechanical. Routes stay `UNVERIFIED`.

## Impact

- New: `routing/pairs.py`, `routing/escape.py`, benches and gate tests.
- Changed: `routing/protocol.py`, `codes.py`, both plugins, `cmd_route.py`, `cmd_capabilities.py`, docs.
- No model field and no schema change: a model document written after this change is read by 0.2.x and 0.3.x as before.
- Four sources are registered as S-0662 to S-0665 (they were drafted as S-0410 to S-0413, which catalog datasheets hold on `dev`).

## Prerequisites

On `dev` before the first task:

- Release `0.3.0`.
- c0104 (`diff-pair-constraints`), hard: `model.pairs`, the class pair values, `diff_pair_skew`. Task 0.1 stops without it.
- c0107 (`route-planes-layers`), hard: plane layers, `JobNet.layers`, the project's rules in `route`, the plane fan-out on the gate benches.
- c0108 (`route-open-nets`) and c0109 (`routing-scale-control`): the candidates come from c0108's selection; the pair and escape steps are runs inside c0109's budget and tiers; the MODIFIED "Freerouting plugin" is regenerated from the text c0109 leaves.
- c0078 (`router-fetch`) before c0109, by the fixed order of "Freerouting plugin": c0078, c0109, c0110.
- Not needed first: c0096, c0097, c0099; c0105 (per-layer pair widths stay there).
- After this change: c0119 (the yardstick's routing), c0111 and c0112 (vias in pads).
