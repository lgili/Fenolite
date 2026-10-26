## Why

The review of 2026-10-05 of the gaps to a complex board (milestone v0.4; `docs/roadmap.md`, "The complex board, c0100–c0120") found two gaps in `fenolite analyze` (c0047) with no owner, and both are open at `origin/dev` `9aba2dff`:

- A `[[current]]` row applies a net's whole current to each of its items, a capacitor branch included. Pours, planes and via arrays, which carry a power stage's current, are not analysed, and nothing gives a resistance or a voltage drop.
- No distance is measured between copper on two layers. Every cut-out lengthens creepage whatever its width, and copper of another net or of none on the path is ignored, so creepage can be overstated.

Measured on 2026-10-05 (design, Context): KiCad 10.0.6's `min_groove_width` never bridges a cut-out; a track of another net across the path splits KiCad's creepage into two halves; neither major judges a distance between layers; a stored fill is one ring joined to its holes by zero-width slits.

## What Changes

- **Power paths.** `[[path]]` rows (`from`, `to`, `milliamps`, `temp_rise_mk`, `drop_mv`) and `--path`. The net's copper network (tracks, arcs, pads, via groups, fill regions) keeps the copper on some path between the two pad sets; the rest carries no direct current and is not judged.
- **Narrowest section** of a fill between two ports, exact on the integer geometry; its capacity by c0047's fit is an estimate.
- **Judging.** Copper carrying the whole current fails below it (`analysis.path-exceeded`); copper in parallel is undecided.
- **Drop.** Resistance as an interval: tracks and barrels as uniform conductors, a fill between two ports bounded by `ρ/t · ℓ²/A` and `ρ/t · A/w²`. The user gives the resistivity. The maintainer decided on 2026-10-07 that this fits the plan: it is a measure against a limit of the user, with no field solver, and non-goal N9 stands.
- **Insulation between layers** from c0101's stack-up, with the dielectric sheet count; `insulation_nm`.
- **Grooves** narrower than the user's width are bridged on the creepage path (`groove_nm`, `--groove-width`).
- **Conductors** of other nets, or of none, are crossed at no length by creepage and clearance, and named.
- Opt-in kinds `power` and `insulation`, nine codes with their entries in `cli/data/explain.toml`, recorded KiCad probes.
- **Any backend.** `analyze` reads a board through the backend that detects it, so the new kinds run on a KiCad board and on an imported Altium `.PcbDoc`; the limits of an import are stated (design, Decision 16).

Size: 9.75 design-days; 8 after the cut order.

## Prerequisites

Read at `origin/dev` `9aba2dff` on 2026-10-07.

- `0.3.0` released from `dev`: the proposals of v0.4 come to `dev` after it.
- c0047 and c0071: archived on `dev`. `src/fenolite/analysis/`, `cli/cmd_analyze.py` and the three requirements this change modifies have not changed since the proposal was written.
- c0101 (stack-up; a proposal of v0.4) first for two parts: insulation between layers and the barrel resistance of a via group read its `Stackup.depth`, and `Stackup` on `dev` has no such method. Fill regions, sections, the network, capacities, grooves and conductors need nothing of it and may be built before it.
- c0102 (outline shapes) and c0111 (thermal arrays in a pad): soft. Their boards are read as any other; neither must land first.
- c0096, c0097 and c0099 (board authoring): nothing in common. c0099 adds `analysis/body_volumes.py`, another module of the package, and touches no file or name of this change.
- c0114 (waivers) does not reach `analysis.*` findings, and this change adds no waiver (Non-goals).
- Waiting for this change: c0119 (the copper analyses of the yardstick board).

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `board-analyses`: MODIFIED "Clearance on a layer", "Creepage on the board surface", "Requirement tables supplied by the user"; ADDED "Copper fill regions", "Narrowest copper section", "Power path network", "Power path current", "Power path voltage drop", "Insulation between layers", "Creepage grooves", "Creepage over conductors", "Power and insulation kinds", "Power and insulation codes", "Power and insulation evidence", "Power and insulation KiCad probes".

## Non-goals

- Field solutions inside pours (crowding, temperature), shares of parallel copper, AC impedance, fusing: nowhere, because the project plan excludes simulation and power and thermal integrity (N9). Line impedance: c0105.
- Judging a sheet count: nowhere, because which overlaps it covers is the user's standard.
- Writing `rules.min_groove_width`: nowhere, because 10.0.6 ignores it on cut-outs.
- Mask, coatings, component bodies: nowhere, as in c0047.
- A `check` stage: nowhere in v0.4, for c0047's reason.
- Waiving an `analysis.*` finding: nowhere. c0114's waivers cover `copper.*` and `kicad.drc.*` findings stored with a design; `analyze` judges only against the requirements file the user passes and stores nothing, so the user changes the row.
- Copper graphics as conductors of a path (the copper graphics of a footprint instance, c0126): nowhere for now; they are counted and reported, never dropped silently.

Limits: ports are ideal contacts; via groups share current equally; a section whose port hull holds a hole is a bound; cut-outs are bridged whole; V-grooves are not cut at the groove width; insulation ignores copper on layers between; wide sections lie outside the fit's range.

## Evidence level required

- Geometry (regions, sections, insulation, grooves, crossings): hand-computed cases and a grid cut; `INFERRED`.
- Section capacity, network, region bounds: `INFERRED`, checked against a finite-difference solution in tests.
- KiCad behaviours: recorded probes that never gate; fill slits `CORPUS-VERIFIED`.

## Impact

- New: `analysis/fills.py`, `section.py`, `network.py`, `power.py`, `insulation.py`, `grooves.py`.
- Changed: `analysis/surface.py`, `distance.py`, `report.py`, `requirements.py`, `codes.py`, `copper.py`; `cli/cmd_analyze.py`; three docs pages.
- New data file `tests/data/analysis/strip_10.kicad_pcb` with its row in `tests/data/MANIFEST.toml`; nine entries in `src/fenolite/cli/data/explain.toml`; sources S-0681 and S-0682.
- Creepage and clearance shorten where other copper lies on the path. Depends on c0047 (archived) and, for insulation and barrels, on c0101.
- No model key and no schema change. The requirements file gains optional keys under the same schema name; a requirements file that uses them is refused by 0.2.x and 0.3.0, whose key sets are closed (design, Migration Plan).
