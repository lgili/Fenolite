## Context

c0175's design, decision 10 ("Library fidelity"), holds the three tools of this change; its fourth item
(body copy by pad fit and the coverage report, task 10.4) stays there. What exists:

- The Altium reader keeps a pad's paste and solder-mask modes and expansions in the pad's `altium` bag
  (`paste` and `mask`, `<mode>,<expansion>`, only when the mode is not "from the rules";
  `docs/formats/altium/import.md`). The modes are 0 none, 1 from the rules, 2 manual
  (`pcb-records.md`, "Pad"). Which bytes hold the paste `Enabled` switch and the solder `Tented` option is
  not known (`pcb-library.md`, U1 and U2).
- The document's rules are kept as `RuleRecord` values (`read/pcb.py`); a `SolderMaskExpansion` or
  `PasteMaskExpansion` record holds `EXPANSION` as mil text, `PRIORITY` and `SCOPE1EXPRESSION`
  (`pcb-records.md`, CORPUS-VERIFIED).
- `models3d.body_models` (c0193) gives each embedded model with its data and its placement in the board
  frame (`BodyModel`; `H-A-BODY-MODEL-PLACE`).
- The conversion derives the project's footprint library from the written board text
  (`altium_to_kicad.footprint_files`): each footprint brought back to its origin and the top side.

## Decisions

1. **Layers by kind.** In `prepare`, an imported pad keeps its copper layers and gains: a surface pad on
   `F.Cu` the layers `F.Paste` and `F.Mask`, on `B.Cu` `B.Paste` and `B.Mask`; a plated or unplated
   through-hole pad `F.Mask` and `B.Mask`. A surface pad on an inner layer gains nothing. The pads of a
   generated hole footprint (c0170) are not imported pads and are left alone.
2. **Margins.** Mode 2 (manual): the pad's own expansion. Mode 1 (from the rules): the expansion of the
   enabled rule of its kind whose scope is `All` and whose priority comes first; no such rule gives no
   margin (the board's default stands, as it does in the source). When an enabled rule of the kind with
   another scope comes before it, the scope is not evaluated: the pad gets the `All` rule's expansion and
   is listed as `pad-margin` with the reason. A rule whose scope, read with the closed scope grammar
   (`read/scope.py`), selects no pad (`IsVia`, `IsTrack`, a conjunction with one, a disjunction of them
   only) cannot govern a pad and is left out: the public documents `-01`, `-04` and `-05` put an `IsVia`
   mask rule before the `All` one, and counting it gave every pad of the three a `pad-margin` loss (745,
   53 and 96) although the margin taken is the governing one. Mode 0 (none): no margin. Every committed Altium library and
   Fenolite's own writer hold paste mode 0 on every pad (U2), so mode 0 cannot mean "no opening" here.
   An expansion of 0 is no margin (`None`): KiCad reads a margin of 0 as "follow the board".
3. **Margins in the model.** `Pad.mask_margin` and `Pad.paste_margin` (`Nm | None`, default `None`). The
   KiCad readers project the first `solder_mask_margin` and `solder_paste_margin` child of a pad into the
   fields and keep the child as an opaque slot, as `zone_connect` was projected before it was modelled; no
   committed board or footprint holds such a child, so no read design of the test data changes. The writers
   emit the field for a pad without such a child, after `layers` (after `net` on a board) and before
   `zone_connect` (S-0001's order of a pad), and refuse a field that disagrees with a kept child
   (`kicad.board.projection-read-only`, `kicad.lib.projection-read-only`); `None` keeps the child.
4. **Placements in the model.** `ModelPlacement(path, offset=(x, y, z), rotation=(x, y, z),
   scale=(x, y, z))`: lengths in nm in the footprint frame with Y down as every model point, angles in µdeg
   counter-clockwise seen from +axis, scale in ppm. `FootprintDef.placements` holds them for a footprint
   read from another format; a footprint read from KiCad keeps its `model` children as read in `models`
   and holds no placement. The footprint writer appends one `(model "path" (offset (xyz …)) (scale (xyz
   …)) (rotate (xyz …)))` per placement after the footprint's other children, and refuses placements on a
   definition whose slots hold a `model` child.
5. **KiCad's frame of a model.** Measured with `kicad-cli pcb export vrml` 10.0.7 on a probe board: a
   footprint at (10, 20) on a 30 × 30 board with `(offset (xyz 1 2 3))` and `(rotate (xyz 0 0 90))` puts
   the model at (−4, −3, 3.8) around the board centre in VRML's Y-up frame and turns it by −90° about Z.
   So the offset's Y points up (the model's −Y) and Z from the top face, and a positive `rotate` Z turns
   clockwise seen from above: the writer writes `−y` and `−angle`. Only the Z turn is measured.
6. **Placing an Altium model.** For a body of a top-side footprint whose embedded model `body_models`
   gives: the offset is the model's board position brought into the footprint frame (minus the footprint
   position, turned back by its rotation) and the body's `MODEL.3D.DZ`; the Z turn is `ROTZ` minus the
   footprint's rotation. A model of a bottom-side footprint, or turned about X or Y, is a `model` loss with
   its reason. The model's file is written beside the derived library as
   `<name>.3dshapes/<footprint>_<sha12>.step`, `sha12` the first 12 hex digits of the SHA-256 of its data,
   and named in the footprint as `${KIPRJMOD}/<name>.3dshapes/<file>`. The body itself stays a `body`
   loss as before; a placed model is listed as a `model` change.
7. **Library from a board.** `fenolite.library.derive_library(text)` reads a KiCad board's text and, for
   each footprint in reference order, takes its node, removes the placement children (`at`, `uuid`,
   `locked`, `path`, `sheetname`, `sheetfile`, the pads' nets), turns its pads and texts back by the
   footprint's angle and flips a bottom footprint (`embed.flip_footprint_tree`): the same transform the
   conversion uses (moved there from `altium_to_kicad.footprint_files`). Two instances of one name whose
   written footprints differ, the uuids aside, give a second footprint `<name>_2` (then `_3`) and
   `library.instances-differ` (warning). Reference and Value become `REF**` and the name.
8. **Drift report.** `--diff LIBRARY` reads `<LIBRARY>/<name>.kicad_mod` for each derived footprint and
   compares the definitions: `pads` (number, kind, shape, size, position, rotation, layers, drill),
   `silkscreen` and `courtyard` (the graphics on `F.SilkS`/`B.SilkS` and on `F.CrtYd`/`B.CrtYd`),
   `models` (the paths) and `fields` (the properties other than Reference and Value). A footprint missing
   from the library is `missing`. The command writes nothing with `--diff`. Each differing footprint is
   one `library.drift` finding (error), so the command exits 5 when the library has drifted and 0 when
   it has not, as `diff --allow` answers its question by the exit code.

## Risks / Trade-offs

- A margin taken from an `All` rule while a scoped rule may govern the pad: reported, never silent.
- Rotations about X and Y are common in Altium models; they stay losses until KiCad's order of turns is
  measured on a probe.
- `--diff` compares the model, not the bytes: a respelling of a number is no difference.

## Open questions

None.
