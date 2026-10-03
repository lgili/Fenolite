## Why

The roadmap's v0.3 names an analyses track: current capacity, clearance and creepage distances. Fenolite can judge shorts and rule clearances (c0029), but it cannot answer "how much current does this track carry?" or "how far apart are these two nets through air and along the surface?". These are questions on the neutral model.

## What Changes

- New package `fenolite.analysis` (already in the layering table: `model`, `geometry`, `backends.base`).
- **Current capacity** of tracks, arcs and vias from one published power-law fit, `I = K · ΔT^0.44 · A^0.725`. Each coefficient is recorded with its public source (S-0269, S-0270) in `docs/analyses.md`. The result is an integer in milliamperes, computed with `decimal`, the same on every platform. No table or figure of any standard is read or reproduced.
- **Clearance** between two nets or net classes: the exact gap on each copper layer (c0029's thick shapes), and across the board edge between the two outer faces, as an interval.
- **Creepage**: the shortest path along the board surface on the outer faces, around cut-outs and around the board edge. Lengths are integers with a stated band.
- Every value carries its location: layer, items and the path points.
- **Requirements come from the user**, in a TOML file: currents per net or class, distances per pair, and an optional voltage step table that the user fills. Fenolite ships no requirement value.
- Command `fenolite analyze PATH`, read-only, on any board a registered backend reads. Results enter the envelope's `issues` as `analysis.*` findings; error findings exit 5.
- A recorded KiCad probe: KiCad 9 and 10 have a `creepage` rule constraint (S-0272), so `kicad-cli pcb drc` can bracket a creepage value on authored benches. It is supporting data, never a gate.

Size: 11.5 design-days, with a cut order (design, "Budget").

## Capabilities

### New Capabilities
- `board-analyses`: the capacity formula and its recorded coefficients, board boundary, clearance, creepage, user requirement tables, findings, the `analyze` command, evidence.

### Modified Capabilities
- None. `check`, `STAGE_ORDER`, the model, the schemas and `package-layering` are unchanged.

## Non-goals

- Conformance to any safety or design standard. Fenolite measures; the user decides.
- Shipping any voltage-to-distance table, pollution degree, material group, altitude factor or default temperature rise.
- Interpolation between the user's table rows.
- Current flow: parallel paths, pours, planes, thermal reliefs, neighbouring tracks, ambient.
- Resistance, voltage drop, fusing current, impedance.
- Distances through solid insulation; coatings and solder mask; components' own bodies and leads.
- The effect of floating copper between two nets on creepage.
- A `check` stage, a build guard, or lowering a creepage rule to a backend's rules file.
- Anything specific to one backend.

## Evidence level required

- Arithmetic of the fit: mechanical (unit tests against an independent `Fraction` and `math` computation). The fit itself is `INFERRED` (`H-G-AN-FIT`, `H-G-AN-VIA`): no command-line oracle exists; KiCad's calculator is GUI-only.
- Same-layer clearance: the level of c0029's thick gaps; `INFERRED` in the report (`H-G-AN-GAP`).
- Creepage and edge paths: `INFERRED` (`H-G-AN-PATH`, `H-G-AN-EDGE`), checked by hand-computed authored cases and a brute-force grid search.
- The KiCad creepage bracket (`H-K-AN-CREEP`): recorded on 10.0.6; it raises no label.
- Every reply of `analyze` carries `INFERRED` or lower. `UNVERIFIED` when an item or an input was left out.

## Impact

- New `src/fenolite/analysis/` (seven modules), `src/fenolite/cli/cmd_analyze.py`, `docs/analyses.md`, `docs/evidence/board-analyses.md`, tests under `tests/unit/analysis/`.
- Depends on c0029 (`geometry.thick`) and c0028 (`BoardFrame`, `BoardPad`), archived first. Independent of c0039–c0046; an Altium board is analysable once c0043 reads it.
- Sources S-0269 to S-0273; S-0274 to S-0276 stay unused.
