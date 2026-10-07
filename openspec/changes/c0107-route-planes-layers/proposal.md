## Why

This is a proposal of milestone v0.4 (`docs/roadmap.md`, "v0.4: proposals on other branches", row c0107), written against `origin/dev` at `9aba2dff`. A review of 2026-10-05, made with generated boards of 100 to 600 parts, found three routing gaps on boards with inner planes, and none of them is closed on that commit:

- `route` skips a net that has a zone, or traces it with `--include-zone-nets`. No SMD pad gets a via to its plane: a 600-part probe needed 549 hand-computed vias.
- Every copper layer is a signal layer in the Specctra file, so Freerouting routes across the planes, and no class can be kept to some layers.
- Class-to-class and edge clearance never reach the router.

Measured on 2026-10-05 with Freerouting 2.4.1: a layer written `(type power)` gets no wire; Freerouting never brings an SMD pad to a plane on such a layer, but one protected via per pad completes the plane net; `use_layer`, `class_class` and `layer_rule` are honoured. A 100-part board so prepared routed with no unconnected item under KiCad 10.0.6.

## What Changes

- **Plane layers.** A copper layer of KiCad type `power` is a plane layer. `board(planes=…)` now sets that type on KiCad boards, also on a rebuild; it never removes one. A plane without a zone of its net on its layer gives a warning.
- **Plane fan-out.** Before the router runs, `route` joins each SMD pad of a plane net to its plane with a short track and a through via, found by a deterministic search; a pad without room is reported. Plane nets are never traced. `--no-plane-fanout` skips it.
- **Design file.** Plane layers `(type power)` with one `plane` per zone; `use_layer` per class; `class_class` clearances; per-layer widths; edge clearance as keep-out bands; rules it cannot carry are reported.
- **Track layer rules.** A thirteenth rule kind `no_tracks`, lowered to KiCad's `disallow track` per layer, read back, declared with `design.rules.rule()`. In an Altium build it gets its row in the rule table (`no-counterpart`) and one `altium.not-lowered` warning per rule: it is never dropped in silence.
- **Routing job.** `RoutingJob.plane_layers`, `JobNet.layers`; `route` reads rules.

Size: 10 design-days; cut order in the design.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `specctra-dsn`: MODIFIED "Design files are written from the model", "Specctra issue codes and facts"; ADDED "Plane layers in design files", "Routing layers in design files", "Routing rules in design files".
- `routing`: ADDED "Plane and routing layers in a routing job", "Plane fan-out", "Freerouting plugin sends planes, layers and rules".
- `cli-contract`: ADDED "Plane nets in the route command".
- `rules-model`: MODIFIED "Rule kinds and limits" (thirteen kinds, one without a limit); ADDED "Track layer rules".
- `kicad-file-backend`: ADDED "Plane layers of a board", "Track layer rules in rules files".
- `design-dsl`: MODIFIED "Planes in a build", "Rule constructor in the DSL" (no limit for `no_tracks`).
- `altium-pcb-writer`: ADDED "Track layer rules in the Altium rule table".
- `kicad-oracle`: ADDED "Plane routing passes the oracle".

## Non-goals

- Fan-out as a script intent: c0111 can call the engine.
- Escape of QFN and BGA signal pads, differential pairs: c0110.
- Via-in-pad fan-out: c0111 and c0112. Blind fan-out vias: nowhere, as no yardstick item needs HDI.
- Nets Freerouting leaves alone, time budgets, its optimizer: c0109. Open-connection selection, locks: c0108.
- Other rules in the Specctra file (area, net, part selectors; other kinds): nowhere, as the subset has no construct for them; reported as not sent.
- Split planes in the script, planes of zones without an outline, other `disallow` rules: nowhere, as no yardstick item needs them.
- An Altium rule record for `no_tracks`: nowhere until a public file holds the record of Altium's routing-layers rule; the row says so.
- Plane fan-out for the Altium target: `route` works on a KiCad board; an Altium build takes the routed board with `--copper-from`, fan-out vias included.
- KiCadRoutingTools options for planes: nowhere, as none is documented.

## Evidence level required

- `ORACLE-VERIFIED(freerouting 2.4.1)` for `H-G-DSN-LAYERS`, `H-G-DSN-PLANE`, `H-G-DSN-CLEARANCE`; `KICAD-VERIFIED (10.0.x)` for `H-G-DSN-EDGE`.
- `KICAD-VERIFIED (9.0.x, 10.0.x)` for `H-K-LAYER-POWER`, `H-K-DRU-NOTRACKS` and `H-K-FANOUT`.
- `H-K-KRT-PLANES` when a checkout exists. Routes stay `UNVERIFIED`.

## Impact

- New `backends/kicad/fanout.py`, `routing/layers.py`; changed DSN writer, routing, `route`, KiCad layers and rules, the Altium rule table, DSL, build, `explain.toml`.
- `planes=` changes the KiCad board; `route` adds fan-out copper on boards with plane layers.
- `rules.json` gains a kind: releases 0.2.x and 0.3.x cannot read a model document that holds a `no_tracks` rule; documents without one keep their bytes.
- `build.plane-not-lowered` leaves the code table; nine codes are new.

## Prerequisites

On `dev` before the first task:

- Release `0.3.0` (the Altium write side: c0084, whose "Rule lowering table" this change extends, c0085 and c0088, all archived).
- c0100 (`board-layer-count`): it modifies "Planes in a build" and owns the layer table; this delta is regenerated from its archived text (task 0.1).
- c0108 (`route-open-nets`): it modifies "Net selection" and "Route command"; the fan-out step is written against its selection and its write rule.
- Met on `9aba2dff`: c0068 (pad copper at KiCad's offset) and c0071 (the rule kind table), both archived on 2026-10-05.
- Not needed first: c0096, c0097, c0099. c0096's `no_tracks` is the keep-out flag, another object; c0097 keeps `ClearanceResolver.resolve`, which the fan-out calls.
- After this change: c0109, c0110, c0111, c0104 and c0103 (each regenerates what it shares, design Decision 14).
