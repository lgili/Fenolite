## Why

The dogfood buck board (public API only) got 25 silkscreen warnings; several references crossed the board edge. The model has no field type: c0009 projects each `property` into the component's text, and c0017's writer rewrites only the Reference and Value atoms, so a field cannot be moved, rotated, hidden or put on another layer.

Probes (`kicad-cli` 10.0.6 and the pinned 9.0.9 image; S-0020, S-0029) fixed the frames on both majors: a property's `at` is footprint-local (absolute = `at + R(θ)·local`, no further mirror on the bottom), its angle is the board angle, and `pcb drc` reports a field's anchor and uuid. 9.0.9 reports `silk_edge_clearance` only when the board's minimum silk clearance is above zero.

## What Changes

- **Model.** `FootprintField` (prefix `fld`): name, position and rotation in the pad frame, layer, size, thickness, visibility, justification and mirror, in `FootprintInstance.fields` (default `()`). The text stays in the component. Schema regenerated.
- **Reading.** Placed `property` nodes of 8.0 to 10.0 boards become modelled children with their own slots; their value atom stays projected. Bare properties, repeated names and `fp_text` are read as before.
- **Writing.** `write_board` writes fields from the model and keeps unchanged nodes tree-equal; created footprints take their properties' placement from their fields.
- **Helpers.** `backends/kicad/fields.py`: `field_anchor`, `field_angle`, `set_field` (board frame in, model frame stored) and `place_outside`, which puts a field beside the box of c0028's `placed_extent` on a chosen side, with its justification pointing away.
- **DSL and build.** `Part.field("Reference" | "Value", dx=, dy=, rot=, layer="silk" | "fab", visible=, size=, thickness=, justify=, outside=, gap=, locked=)` and `dsl.fields(design)`; `build_design(…, fields=…)` applies them after placement.
- **Lens.** `lens/fields.py` `merge_fields`: a locked request wins, then the board's field, then an unlocked request, then the library. Board fields follow a footprint that is re-placed with the same lib id and side. Outcomes go to `result.preserved.fields`. User properties keep c0019's rule: value from the script, placement from the board.
- **Oracle.** DRC canaries on both majors (anchors, edge crossings, angle, justification, mirror, keep-upright, hidden fields, a courtyard cut-out for `place_outside`); a 10.0.6 re-save keeps an edited field. Probes run first.
- **Registers.** S-0120; `H-K-FIELD-*` hypotheses; `board.md`, `dsl.md` and `lens.md` sections.

Budget: 10.25 working days; cut order in the design.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `design-model`: ADDED "Footprint fields".
- `kicad-file-backend`: ADDED "Footprint fields on boards", "Footprint fields are written" and "Footprint field helpers"; MODIFIED "Unmodelled board content is kept as slots".
- `design-dsl` (c0011): ADDED "Field placements in the DSL" and "Field placements in a build".
- `layout-lens` (c0019): ADDED "Footprint fields across rebuilds".
- `kicad-oracle`: ADDED "Footprint fields pass the field oracle".

## Non-goals

- Silkscreen legality beyond the canaries (c0022, c0029); automatic side choice; font metrics.
- Symbol fields (c0012); `gr_text`, `fp_text` and text boxes.
- Writing property values other than Reference and Value; adding slotless fields to, or removing fields from, a read footprint; user properties (c0027).
- Font face, bold, italic, keep-upright and knockout in the model (kept opaque).
- New issue codes, FEN codes or import edges.

## Evidence level required

- Frames, justification, keep-upright, DRC items and the 9.0.9 silence (`H-K-FIELD-FRAME`, `-JUSTIFY`, `-DRC`): `KICAD-VERIFIED (9.0.x, 10.0.x)` on the bench.
- `place_outside` (`H-K-FIELD-OUTSIDE`): `KICAD-VERIFIED` on the bench, `INFERRED` for other strings.
- Re-save (`H-K-FIELD-RESAVE`): `KICAD-VERIFIED (10.0.x)`. The 8.0 forms (`H-K-FIELD-V8`): `INFERRED`.
- Model, reader, writer, DSL, build and lens rules: mechanical; RT1 over the corpus.

## Impact

- `model/board.py`, `core/ids.py`, `backends/kicad/pcb.py` and new `fields.py`, `dsl`, `lens/build.py`, `lens/preserve.py` and new `fields.py`, `cli/cmd_build.py`, `schemas/`.
- Archive after c0011, c0019 and c0028, whose names it uses; c0012 archives earlier.
