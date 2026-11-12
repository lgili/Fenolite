# c0497: board edits of an Altium PCB document, public and checked

Found on: editing a private two-layer power board with `fenolite.backends.altium.edit` on 2026-11-11 (codes
only; nothing from the board is in this change).

## Why

Six board jobs had no operation in the edit session (`edit.session.Session`). The scripts that did them
used private names (`s._queue`, `ops._twins`, `records.transform`, `records.patch`,
`records.region_outline`) or left the job to Altium. Each gap, by its failure id:

- **F27, designator and comment texts.** `Session.move` moves a free text only (`ops.View._distance` drops
  every text with a component index). A component's designator or comment cannot be moved or turned. The
  free-text lookup also failed in the field: `Text` names a text by its shown string alone, so it cannot
  tell apart two texts with one string and cannot reach a text whose string is held in another form. The
  workaround queued `records.transform(raw, records.shift(dx, dy), turn=-r)` on the raw record. Three facts
  make this unsafe by hand: the record's X,Y is the text's bottom-left anchor, the anchor is mirrored on the
  bottom side (`pcbrecords.text_record`, `x1, x2 = (x - width, x)` when mirrored), and the component holds an
  autoposition setting that may move the text again.
- **F28, board cut-out.** No operation adds one. The workaround cloned the first `Regions6` record with
  `ISBOARDCUTOUT=TRUE` (layer byte 56, `V7_LAYER=MULTILAYER`) and its `ShapeBasedRegions6` twin
  (`ops._twins`), and wrote the ring with `records.region_outline`. Nothing updated the board shape or the
  fabrication drawing.
- **F29, polygon cut-out.** No operation adds a region of `KIND=1`. The user drew it in Altium.
- **F30, via tenting.** No operation sets a via's tenting or its solder-mask expansion. The workaround patched
  about 1,300 via records byte by byte, copying the flag bytes of vias that Altium had already saved as
  tented.
- **F31, fabrication drawing.** The outline and cut-outs drawn as tracks on a mechanical layer cannot be
  redrawn from the board shape, and nothing checks that such a drawing matches the board shape. The
  workaround patched track records with `records.patch`.
- **F32, region outline.** `Session.set_outline` takes a `Polygon` only. A free region's outline (a keep-out,
  a cut-out, a drawing) cannot be changed.

## What Changes

- **Texts of a component (F27).** New items `Designator(ref)` and `Comment(ref)`. `Session.move` and
  `Session.rotate` take them. A move shifts the anchor. A turn turns the text about its own box centre, and
  keeps the anchor rule of its side. Both set the component's autoposition key of that text to manual. `Text`
  gains optional `layer` and `at` to narrow a free text (design D2).
- **Board cut-out (F28).** `Session.add_board_cutout(ring, *, drawing=None)`. It writes a free region of
  `KIND=0` with `ISBOARDCUTOUT=TRUE` on the Keep-Out layer, and its shape-based twin. The template is a cut-out
  the document holds, else the writer's form (`pcbrecords.cutout_region`). A ring that crosses the board outline
  is refused unless `notch=True`. Then the `Board6` outline and the `BoardRegions` record become the outline less
  the ring. `drawing=LAYER` also redraws the fabrication drawing (F31) in the same commit (design D3).
- **Polygon cut-out (F29).** `Session.add_polygon_cutout(ring, *, layer)` writes a free region of `KIND=1` on a
  copper layer. The pour of each polygon on that layer whose outline meets the ring is removed, as
  `set_outline` removes it, and is listed in the receipt (design D4).
- **Via tenting (F30).** `Session.set_via_mask(selector, *, tented_top, tented_bottom, expansion=None,
  count)`. The selector is one `Via` or `Vias(net=None, hole=None)`, and `count` states how many vias it
  takes. The operation writes bits 5 and 6 of the first flags byte and the manual cache state 2 at byte 66,
  as the writer has written them since c0112 and c0166. With `expansion`, it also writes bytes 54 and 242
  (design D5).
- **Fabrication drawing (F31).** `Session.draw_board_shape(layer, *, width, old_count)`. It removes the free
  tracks and arcs on `layer` (`old_count` states how many) and draws the `Board6` outline and every board
  cut-out ring as tracks and arcs of `width`. A new stage of `fenolite check`, `altium.board-drawing`, compares
  the drawing on a mechanical layer with the board shape. It gives `altium.board-drawing.mismatch` (warning)
  for each outline edge or cut-out ring that has no drawn edge within 0.01 mm, and for each drawn edge that is
  not on one (design D6).
- **Region outline (F32).** `Session.set_outline` also takes a `Region`. It writes the new ring into the
  `Regions6` record and its twin with `records.region_outline`, and keeps every key, the layer, the net and the
  flags (design D7).
- **Gates and evidence.** New gates `text`, `cutout`, `tenting` and `board_drawing`, all off. Each rests on a new
  hypothesis: `H-A-EDIT-TEXT`, `H-A-EDIT-CUTOUT`, `H-A-EDIT-TENT` and `H-A-EDIT-DRAWING`. The region outline
  takes the `set_outline` gate (`H-A-EDIT-SHAPE`). The new kit cases of Part J decide each gate.
- **CLI (design D1).** `fenolite edit PATH.PcbDoc --ops-file FILE` runs a JSON list of session operations
  under the write protocol: dry run, plan, confirm. A closed gate gives `altium.edit.gate`, as the session
  does. `--gate NAME` opens one gate for one run, with the warning `altium.edit.gate-opened` and the evidence
  `UNVERIFIED`.

## Impact

- `src/fenolite/backends/altium/edit/ops.py`: the new items and operations, plus `View._distance` for texts.
  `edit/session.py`: `OPERATIONS`, `ROWS`, `GATES` and the new methods. `edit/records.py`: the text anchor
  helpers. `edit/__init__.py`: exports.
- `src/fenolite/backends/altium/edit/drawing.py` (new): the board-shape drawing and its comparison.
  `checks` registers the stage `altium.board-drawing`.
- `src/fenolite/cli/cmd_edit.py`: the `.PcbDoc` mode.
- `docs/formats/altium/pcb-records.md` and `pcb-copper.md`: the rows behind each written field, with labels.
  `docs/hypotheses.md`: four new rows. `docs/evidence/altium-edit.md`: new Part J cases.
- Agent guide page `altium.md`, `docs/cli-contract.md` ("edit"), `CHANGELOG.md`.
- Builds on c0452 (shapes and creation). It does not overlap c0499, which adds parts, links and schematic
  edits. If c0502 gives `fenolite edit` a `.PcbDoc` mode first, D1 adds these operations to that mode.
  Removing a stale pour by name is c0504 (F33). This change removes the pour only where its own cut-out makes
  the pour stale.
