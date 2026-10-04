# Design

## Public API
- `Part(..., pad_map={"symbol_pin": "physical_pad"})` defines a per-component bijection for mapped pins. Omitted pins keep identity mapping. Validate non-empty string designators, one-to-one physical pads, and conflicts before build output.
- `Footprint.pad(..., drill_shape="round"|"slot", drill_length=..., drill_rotation=...)` adds oblong holes. `drill` remains width/diameter; slot length includes the ends and must be at least drill width. Existing round drills remain source-compatible.
- Extend canonical `Component` with sorted pin-to-pad pairs and `Padstack` with `hole_shape`, `hole_length`, and `hole_rotation`, reusing the model extension planned in c0043.

## Implementation
Files: `dsl/part.py`, `dsl/footprint.py`, `dsl/convert.py`, `lens/build.py`, `model/circuit.py`, `model/board.py`, generated board/circuit schemas, KiCad `_fpmap.py` and `mod.py`, tests, docs and CHANGELOG. Build checks connections and no-connects using symbol pins, then applies nets to physical pads using the map. Mapping is per component and defaults to identity. KiCad footprint output writes modeled slot width, length and rotation. Altium keeps its existing explicit refusal until its public record representation is evidenced.

## Evidence
Model/API behavior: `INFERRED`, validated by unit tests. KiCad output: `INFERRED` until the existing subprocess oracle confirms it. Altium slot lowering: explicitly unsupported and refused; this change does not claim support.

## Budget
Estimate: 2 design-days.
