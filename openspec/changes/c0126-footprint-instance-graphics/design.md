## Context

Decision of the maintainer, 2026-10-06 (design of c0090, "Decisions of the maintainer", 1): the model holds the graphics of each footprint instance before v0.3 closes, so that an Altium document that is read and written back keeps the silkscreen of its footprints, and so that the Altium build goes through the one lowering `backends/altium/lower.py::from_design` (the open task 2.2 of c0090). This change is implemented on top of c0123 (several pads per pin in `Component.pin_pad_map`), which changes the model first, and it is the last change of the model in v0.3.

Everything below was read in the code on `ba21a109` and measured on 2026-10-06 with Fenolite's own readers on the public corpus (rows with the use `rta`, heavy row included).

- **The model today.** `model/board.py::FootprintInstance` holds `component_id`, `lib_ref`, `position`, `rotation`, `side`, `locked`, `attributes`, `pads`, `fields` (`FootprintField`: where the Reference, the Value and the user properties are drawn) and `bodies`. It holds no graphic and no free text. `Pad` holds `shape` (`roundrect` is one value) and no corner value. `Board.graphics` (`Graphic`: `kind`, `layer`, `points`, `width`, `filled`) and `Board.texts` (`Text`) are the board's own drawings, in board coordinates. `model/library.py::FootprintDef` already holds `graphics: tuple[Graphic, ...]`, ordered, in the definition's frame.
- **Canonical JSON.** `model/canonical.py::to_data` leaves out every field at its default, and `_decode_dataclass` gives a missing key its default and refuses an unknown key (`unexpected property`). `SCHEMA_VERSION` is `"0"` (`model/design.py`), and two earlier additive changes kept it (`docs/design-model.md`, "No-connect marks" and "Buses"). `FootprintInstance.pads` is not marked `ordered`, so the JSON sorts pads by number and id.
- **KiCad today.** `backends/kicad/pcb.py::_Reader.footprint` maps the children of a board footprint with `FOOTPRINT_FIELDS` (`layer`, `at`, `uuid`, `attr`, `pad`, `path`, `property`). `fp_line`, `fp_arc`, `fp_circle`, `fp_rect`, `fp_poly` and `fp_text` are in no entry of that table: they are `Opaque` slots of `FootprintInstance.ext["kicad"]` (`slots.split`), and `write_board` emits each one verbatim at its place (`slots.rebuild`). `roundrect_rratio` is an opaque child of the pad in the same way (`_fpmap.PAD_FIELDS` does not name it). Three places read those fragments back: `backends/kicad/frame.py` (`footprint_edges` for the outline, `_ratio` for the copper of a pad), and `lens/altium.py` (`pad_extras`, `footprint_texts`, `corner_ratios`). A built footprint goes the same way: `embed.place_footprint` emits the library definition as a board footprint and maps it with `pcb.read_board`. The model cache of a KiCad build, `.fenolite/board.json`, is `canonical.dump_texts` of the board that was read back (`lens/build.py`), bags included.
- **Altium import today.** `adapter/board.py::read_board` makes one footprint per record of `Components6` with its pads. `adapter/copper.py` skips every track, arc, fill, region and text that carries a component index and counts it as `footprint-graphics` (`tracks`, `arcs`, `shapes`, `texts`). The designator and the comment are read as strings only (`adapter/board.py::_texts_of`). The same module already maps the same records of a library footprint to graphics (`definition_graphics`, used by `adapter/library.py`). A rounded pad keeps its percentage in the pair `corner_percent` of its bag (`adapter/pads.py::pad`).
- **Altium write today.** Two paths. The build (`lens/altium.py::build_altium` → `pcb_document`) hands the writers library definitions: `pcblib.LibFootprint(defn, extras, texts)`, where `extras` come from KiCad fragments (`pad_extras`). The write of a model (`lower.from_design` → `_footprints`) makes a definition per instance from its pads alone: `FootprintDef(id=fp.id, name=pattern, pads=…)`. Both end in `pcbdoc.place_component`, which takes a definition in the top-side form and mirrors it for the bottom side; that is why `lower._library_pad` takes a bottom pad back to the top side first.
- **What the writer carries of a footprint's graphics.** `pcblib._graphic_drop` keeps a line, an unfilled rectangle (four tracks), an unfilled circle and an arc on a layer of `pcbrecords.FLIP_PAIRS` (`F.SilkS`, `B.SilkS`, `F.Fab`, `B.Fab`, `F.CrtYd`, `B.CrtYd`), drops polygons, filled shapes and other layers, and `check_footprint` refuses a footprint with a graphic on a copper layer. No text of a footprint is written; the component's designator and comment are written at a place the writer chooses.
- **Layer names are not symmetric.** The writer puts `F.Fab` on Mechanical 13 and `F.CrtYd` on Mechanical 15 (`pcbrecords.LAYER_MAP`, Fenolite's choice). The import names every mechanical layer `Mech.<n>` (`adapter/layers.py::_table`). A document that Fenolite wrote therefore reads back with `Mech.13`, and the rewrite of that reading cannot place it: measured on `tests/data/altium/board6/board6.PcbDoc`, "the layer Mech.13 has no layer in the document" for 2 texts and 5 of its 6 graphics that are not written.

## Measured on 2026-10-06

Records with a component index that are not pads, per kind and layer class, on the eight public PCB documents of the RT-A3 table (the per-document totals equal the column `footprint-graphics` of `docs/evidence/altium-roundtrip.md`: 3469, 602, 846, 315, 271, 1074, 307, 9763; 16 647 in all):

| records | overlay | mechanical | paste and mask | copper | other | all |
|---|---|---|---|---|---|---|
| tracks | 2 199 | 11 086 | 0 | 14 | 0 | 13 299 |
| arcs | 164 | 287 | 12 | 34 | 0 | 497 |
| fills | 0 | 6 | 38 | 19 | 0 | 63 |
| regions | 1 | 12 | 171 | 35 | 3 | 222 |
| designator texts | 946 | 15 | 0 | 0 | 0 | 961 |
| comment texts | 961 | 0 | 0 | 0 | 0 | 961 |
| other texts | 55 | 589 | 0 | 0 | 0 | 644 |

- 68 % of the records are lines and arcs on mechanical layers; the silkscreen lines and arcs are 14 %; the designator and the comment are 12 %.
- Each of Fenolite's own samples (`blink`, `board6`, `routed`) holds 33 such records: 4 tracks and 2 arcs on the overlay, 20 tracks and 1 arc on Mechanical 13 to 16, and 3 designator and 3 comment texts.
- Size: a line or arc of the board that the import maps today takes 1 213 to 1 428 bytes of `board.json` (id, provenance with the file's hash and locator, bag, points). The eight imported boards are 52.5 MB of `board.json` today; 16 647 more entities add about 22 MB (43 %). The largest goes from 36.2 MB to about 50 MB. A graphic of a built board has no provenance and no bag and is expected at about a fifth of that; task 7.1 measures both.
- Corner values: 401 of the 3 784 pads of the eight documents carry a table of corner percentages.

## Found on 2026-10-08

Implemented on the base `f17b03e9` (`origin/dev`), which holds c0123 and, since this proposal was written, c0121, c0124, c0127, c0128, c0132, c0134 and c0138.

1. **"Equal field by field, with no listed exception" cannot hold for the two Python objects.** The specification of the build holds library definitions; the one of the lowering holds definitions made from instances, whose pads and graphics have ids of their own (two instances of one footprint cannot share ids in a model). No record is written from an id, a bag or a provenance. The comparison is made on the written view (table A and C above) and on the bytes of `pcbdoc.write_pcbdoc`; the scenario "The two paths give one specification" of `altium-build` is restated. This is no weakening of the acceptance test, which is the bytes of the committed samples.
2. **The MODIFIED deltas were regenerated from newer texts** (task 0.1): "Imported boards are written from the model" from the delta of c0121 (the last of c0127, c0128 and c0121 to modify it), "Altium write of a model" and "Round-trip level RT-A3" from the deltas of c0128 (the last to modify each; c0128's RT-A3 holds c0127's sentences). "Stored board of an Altium build" has no newer delta than c0090's, and "Footprint instances and pads" none but the living text (c0124 and c0132 modify other requirements of `altium-import`). The sentences of "Spec deltas" in the tasks were applied again.
3. **No fixture of an old model document existed on dev**: `tests/data/` holds no `board.json` and no folder `tests/data/model/` on `f17b03e9` (`grep` over `tests/data/MANIFEST.toml` for `board.json` and `0.2.0`: nothing). The convention of this change, `tests/data/model/v<version>/<design>.board.json`, is the first.

4. **A primitive of a component on an internal plane is no item of its footprint.** Change c0124 (on the base since this proposal) makes no entity of a line on an internal plane: it is a cut in the plane, not a drawing and not copper. The import keeps that rule for the primitives of a component: such a primitive stays counted as `footprint-graphics`, the second case of that category beside the component without a readable position. The requirement "Footprint instances and pads" and "Graphics, fields and texts of a component" say so. Measured on the eight public documents: no such primitive (the category is 0 on every one).
5. **`PlacedComponent.comment` exists**: it is the comment's string. The two new fields are `designator_place` and `comment_place` (`pcbdoc.TextPlace | None`), not `designator` and `comment`. The requirement "Footprint items of a written component" names them so.
6. **Not every graphic of an instance can go through the definition.** `pcblib.check_footprint`, which must not change, keeps a definition's graphic only on the six layers of `pcbrecords.FLIP_PAIRS` and only when it is a drawn line, rectangle, circle or arc. A graphic on a mechanical layer of a board that was read, on a paste or solder-mask layer, a filled shape and a polygon are therefore written as the instance holds them: `PlacedComponent.items` (`pcbdoc.ComponentGraphic`: the graphic in the pad frame, the Altium id of its layer, no mirror and no layer flip), after the definition's graphics. `Mech.<n>` is the layer `56 + n` for n from 1 to 16, so `Mech.13` to `Mech.16` are the layers 69 to 72 of the decision. The drawn lines, rectangles, circles and arcs on the overlays (and on the four mechanical layers of Fenolite's layer map, for a model that was not read from Altium) go into the definition in the top-side form, as the requirement says. The requirement is restated in that sense.
7. **An arc of a footprint that was read is written from its record** (c0127, on the base since this proposal): the import keeps the pair `arc` on an `arc` graphic of a component as on a free one, and `lower` hands the kept record to the writer (`PlacedComponent.arc_records`, `ComponentGraphic.arc`) while `lower.kept_arc` finds that it still says the graphic's three points, placed on the board, within 2 nm. Otherwise the arc is derived from its points, as before.
8. **A fill reads back as a filled rectangle.** The writer has one record for a filled shape, the region (c0085). A fill of a component, which the import maps to a filled `rect`, would read back from its rewrite as a filled `polygon` of four points, a difference inside the widened scope. In the items of a footprint, a region of four vertices that is a rectangle square to the footprint is therefore the filled `rect` that a fill of the same corners gives: the two are one shape in the model. A free region of the board stays a `polygon` (the scope does not compare board graphics).
9. **`fenolite explain` needs a table for a code.** `tests/unit/cli/test_explain_cmd.py` refuses an entry of `explain.toml` whose code is in no table of `cli.explain.TABLES`, and no `model.*` code had a table or an entry. `model.design.MODEL_ISSUE_CODES` holds `model.corner-ratio` alone; the older `model.*` codes are out of scope here.
10. **The fixture needs a waiver of the residue scan.** `tools/residue/scan.py` flags numbers of nine or ten digits under `tests/data/`: the board coordinates of the fixture in nanometres (100 000 000 to 150 000 000). One waiver for that one file is added to `tools/residue/scope.toml`, with its reason; it waits for the approval of the maintainer.
11. **The mechanical-layer enable key has a public source**, so task 5.2 does not stop: over the eight public PCB documents, every one of the 43 (document, mechanical layer 1 to 16) pairs that a track, arc, fill, region or text lies on holds `LAYER<56+n>MECHENABLED=TRUE`, and the layer set `&Mechanical Layers` lists exactly the enabled layers in 8 of 8 records (source S-0580, a census with Fenolite's own reader; fact row in `pcb-document.md`). The writer enables each of Mechanical 1 to 12 that a primitive of the document lies on, in the numbered layers, in the two layer sets and, in step with them, in the stack lists.
12. **The schematic form, the directions, the drawing sheets and the output job are no options of the lowering.** The table of Decision 8 put them "in `options`". The output job is made from the stack of the lowered document (`pcbdoc.document_stack(spec)`), so it cannot be known before `from_design` runs, and none of the four is read by the lowering: they stay arguments of `project.write_project`, as before. `LowerOptions` holds `name`, `library`, `sheets`, `copper`, `planes` and `body_form`; the library file and the symbol library of a component are `project.pcblib_name(link, design=name)` and `project.schlib_name(link, design=name)`, computed in `lower` from `name` (the table's `library_file` and `symbol_file`). The requirement "Altium build through the lowering" is restated.
13. **A projection must not empty a footprint that was not read from KiCad.** `lens.altium.write_model` projects every design it writes; the stored board of an Altium build is such a design, and its footprints hold their graphics and no `kicad` bag. `fpitems.with_footprint_items` now returns a footprint without a `kicad` bag as it is, unmarked (requirement "Footprint items projected on request" restated; `tests/unit/backends/kicad/test_fpitems.py::test_footprint_without_a_kicad_bag_is_kept`). Without it the scenario "Build and write agree" would write the stored model without silkscreen.
14. **The comparison of the two paths cannot outlive the former path.** Task 6.2 removes `pcb_document`, so `test_lower_build_spec.py` keeps what task 6.1 measured: the SHA-256 of the PCB document of every example build in both sheet modes as the former path wrote it, taken with `pcb_document` in place, and the build through the lowering must write those bytes. `blink_official` needs KiCad's official libraries and was not built on the machine of this change: 8 of the 9 builds with a PCB document were compared in each mode.
15. **The probe `altium-fpitems-kicad` is not registered in `tests/kicad/_probes.py`.** A registered probe whose result is not in `docs/evidence/kicad/probes/10.0.6.json` fails `tests/kicad/test_probe_results.py`, and the result needs kicad-cli 10.0.6, which the machine of this change did not hold. `tests/kicad/altium/test_fpitems_oracle.py` holds the probe's outcome function and runs it; registering and recording it is task 7.3, owed.
16. **RT-A3 did not take the footprint items that a write leaves out out of the first model.** The first CI run of this change (kicad-10 job, 2026-10-08) failed `tests/corpus/test_altium_rta3.py` on `-01` (75 differences), `-03` (16), `-04` (9), `-06` (2), the same four with bodies, and `altium-set:05`, each first at `/footprint_graphic/0`, removed. The write counted those graphics, as Decision 7 says, under `footprint-copper` (a graphic on a copper layer: filled rectangles and polygons, lines and circles; 22 on the seven documents) and `footprint-graphic` (77 lines and arcs of zero width on Mechanical 1, which the rule of change c0085 for a drawn line refuses as for a free graphic of the board, and 3 filled shapes on the keep-out layer, which has no layer in the document). `rta3.without_unwritten` took out what `AltiumInputs.not_lowered` names for every other kind, but not the graphics and texts of a footprint, although the requirement "Footprint graphics in the Altium round trips" says it does. It does now (`tests/unit/backends/altium/test_lower_items.py::test_rta3_takes_out_the_footprint_items_that_are_not_written`), and the seven documents that are not heavy are equal. The own samples hold no such item, so no unit test had shown it. Writing a zero-width line or a primitive on the keep-out layer is no part of this change: the first needs the rule of c0085 changed for a rewrite, the second a fact row for the layer's record; both stay declared losses, counted per kind.

## Goals / Non-Goals

**Goals:**
- A footprint instance holds its graphics and its free texts, and a rounded pad its corner ratio, in the neutral model.
- An Altium document that is imported and written back holds the lines, arcs, designator and comment of its footprints on the layers the writer has.
- One lowering: the Altium build gives `lower.from_design` a model and its options, and no committed sample changes a byte.
- No output of a KiCad command changes.

**Non-Goals:**
- Component bodies (3D). c0085 cut the body record ("Found" 8 of its design: the saved bodies hold 35 keys, seven typed). The sibling proposal c0121 owns bodies. Nothing here reads, writes or compares a body.
- Graphics of a library definition read from an Altium library beyond what `definition_graphics` maps today; its texts stay counted.
- An edit of a footprint's graphics written to a KiCad board. The KiCad writer keeps writing the file's own children.
- A PCB library derived from the instances of a model that was read.
- Per-layer corner ratios of a pad stack.
- Everything under "Non-goals" of the proposal.

## Decisions

### 1. The new fields

```
FootprintInstance.graphics: tuple[Graphic, ...] = ()   # ordered
FootprintInstance.texts:    tuple[Text, ...]    = ()   # ordered
Pad.corner_ratio:           int | None          = None
```

Three fields, each with a default. Nothing else of the model changes: no new class, no new id prefix (`gfx` and `txt` exist in `core/ids.py::PREFIXES`), no new literal.

- **Reuse `Graphic` and `Text`.** They are the entities of `Board.graphics`, `Board.texts` and `FootprintDef.graphics`, so every consumer of a graphic (the diff, the frame code, the writers' `graphic_records`) takes a footprint's graphic as it is. Rejected: a new `FootprintGraphic` class (a second class with the same five fields, and a second schema definition); a list of opaque strings (it is what KiCad's bag is today, and no other backend can read it).
- **Frame: the pad frame.** A point `p` of a footprint's graphic or text lies on the board at `position + R(rotation)·p`, with no further mirror, as `Pad.position` and `FootprintField.position` do (`docs/design-model.md`, "Pad frame"). A bottom footprint holds mirrored coordinates. `Text.rotation` is relative to the footprint, as `FootprintField.rotation`. Reasons: KiCad stores a footprint's children so (`frame.footprint_edges` places them with `_Placement(position, rotation)` and no flip); the import already takes pads back through `Transform.placement(position, rotation).inverse()`; moving a footprint changes only its position lines of the JSON ("Readable diffs"). Rejected: board coordinates (every graphic changes when its footprint moves, and the id of a graphic without a native id, which is derived from content, would change with it); the definition's frame (top side, not mirrored: a second convention beside the pads of the same instance).
- **Layers after the flip.** `layer` is the board layer the item lies on: a silkscreen line of a bottom footprint is on `B.SilkS`. It is what both files store, and what `Pad.layers` does.
- **Order.** Both fields are `ordered`: file order for KiCad, primitive order for Altium (tracks, arcs, fills, regions by record index), definition order for a build. The writers write in that order, so the bytes of a build do not depend on a sort.
- **Reference and Value stay fields.** The model already says where they are drawn: `FootprintInstance.fields`, with `visible`. The text itself stays in the component (`Component.ref`, `value`). A designator and a comment text of an Altium component become the fields `Reference` and `Value`; `visible` comes from the component record's `name_on` and `comment_on`. A footprint text that is neither goes to `texts` with its string as stored (`.Designator`, `${REFERENCE}`: no token is translated). `Text` has no `visible`, no mirror and no justification: a text of a footprint carries what a free text of the board carries today (`adapter/copper.py::texts`), and on a write its mirror follows the side of its layer as for a board text (`pcbrecords.BOTTOM_SIDE`).
- **What a footprint's graphic may be.** Any `GraphicKind` on any layer, copper included: KiCad and Altium both put copper lines inside footprints (102 records of the corpus). A consumer that cannot use one says so and counts it.

### 2. Corner ratio

`Pad.corner_ratio: int | None`: the corner radius of a `roundrect` pad as **parts per million of the shorter side** of `Pad.size`; `None` when unknown or when the shape is not `roundrect`. 250 000 is a quarter of the shorter side (KiCad `0.25`, Altium 50 %). The pad has no other shape parameter: `PadShape` is a name, and `Padstack` holds holes and per-layer shapes.

- KiCad writes the ratio as a decimal of the shorter side from 0 to 0.5 (`frame._basic` computes `r = ratio · min(w, h)`). Altium stores a whole percentage from 0 to 100 of half the shorter side (`pcbrecords.corner_percent` writes `round(200 · ratio)`; `lower._extras` reads `percent / 200`). One percent is exactly 5 000 ppm; a KiCad decimal of up to six places is exact.
- `Design.validate()` reports `model.corner-ratio` (error) for a value outside 0 … 500 000 and for a value on a pad that is not `roundrect`.
- Rejected: a float (the model has none); a decimal string, as `ZoneHatch.smoothing_value` (exact for any text, but every consumer parses it and the scope of a round trip cannot compare it as a number); a radius in nanometres (both files store a ratio, and the radius changes with the size); per mille (KiCad's library values such as `0.208333` are not exact).
- A KiCad ratio with more than six decimals is rounded half to even to one ppm. No KiCad file is written from this field (Decision 5), so no byte depends on the rounding.
- The per-layer percentages of an Altium pad stack are not in the model: the import takes the one of the pad's own shape (`adapter/pads.py::pad`, `corner_percentages[slot]`) and the writer refuses a per-layer stack already.

### 3. The library of a footprint

No new field. `FootprintInstance.lib_ref` already names the library and the footprint as `<library>:<name>` in both imports: the header atom of a KiCad board footprint (`_Reader.footprint`) and `<stem of source_footprint_library>:<pattern>` (`adapter/board.py::_lib_ref`); `lower._link` and `project.split_link` split it. A second pair of fields would say the same twice.

What c0090's table called "the PCB library file" is not a fact of an instance. It is two things:
- the **definitions** that `<name>.PcbLib` holds (pads and graphics in the top-side form, the description, the pad count). A `Design` holds instances. The build has the definitions, because it resolved them, and hands them to the lowering as an option (Decision 8);
- the **name of the library file** in each component record: `<design>.PcbLib` in a build (`project.pcblib_name`), the library part of `lib_ref` in a write of a model. That is a naming rule of the caller, an option too.

Rejected: `FootprintInstance.description` and a library written from instances (see "Decisions of the maintainer", 7).

### 4. Ids of the new items

- Altium import: a graphic or a text of a footprint has no native id. Its id is a content id in the section `fp:<footprint native id>` over its fields in the footprint frame, with the occurrence counter of `adapter/ids.py::Ids.content`. Two equal lines in one footprint get two ids; moving the footprint changes none; another footprint changing changes none.
- KiCad projection: `_fpmap.Ids` scoped to the footprint's native id, as pads of a board footprint (`pcb._PadIds`): `derived_id("gfx", "kicad", "<fp uuid>:<uuid>")` with a uuid, a content id without one.
- Build: `derived_id("gfx" | "txt", "altium", "stored:<component id>:gfx:<index>")`, as `lower.stored_board` derives pad ids today.
- `Design.entities()` and `validate()` find the new entities without a change (`model/design.py::iter_entities` walks every dataclass field). `Design.by_layer` gains the footprint's graphics and texts.

### 5. KiCad: nothing moves

The hard condition is that no KiCad output of 0.2.0 changes. `.fenolite/board.json` is one of the outputs of `fenolite build`, and c0123's pinned digests include it (`tests/_pinned.py::files_digest` leaves out only `meta.json` and `build.json`). If `read_board` filled the new fields, every `.fenolite/board.json` of every KiCad build would change, and so would `fenolite inspect` and `fenolite diff` on any board. So:

- **`read_board`, `read_footprint`, `place_footprint` and `write_board` do not change.** A design read from a KiCad file has empty `graphics` and `texts` and `corner_ratio` `None`, exactly as an old model document reads.
- **A projection on request.** `backends.kicad.fpitems.with_footprint_items(design) -> Projection` returns the design with, for every footprint: one `Graphic` per opaque `fp_line`, `fp_arc`, `fp_circle`, `fp_rect`, `fp_poly` child (the mapping of `_fpmap.read_graphic`, which `mod.py` uses for a library footprint), one `Text` per opaque `fp_text`, and `corner_ratio` from the pad's opaque `roundrect_rratio`. The slots stay as they are. A child that `Graphic` or `Text` cannot hold (a dashed stroke, a polygon with arcs, `fp_text_box`, `dimension`, a curve) is left out and counted in `Projection.skipped` by head. Each projected footprint gets the pair `("fenolite.projected", "footprint-items")` in its `kicad` bag.
- **The writer treats them as read-only projections.** "Projected fields on write" of `kicad-file-backend` already says what a writer does with a field that is a copy of an opaque child: project again and compare. With the pair present, `write_board` compares the footprint's `graphics`, `texts` and its pads' `corner_ratio` with a fresh projection; a difference is `kicad.board.projection-read-only` (an existing code). Without the pair the fields are not looked at. No byte of a written board comes from the new fields.
- **Who asks.** `lens.altium.write_model` (the write of a KiCad design as Altium documents), which today reads `roundrect_rratio` itself (`corner_ratios`). `backends/kicad/frame.py` keeps reading the bag.

**Proof that nothing moves** (task group 3a, run before any reader of the fields exists and again at the end):
- RT1, same-version rebuild byte for byte: `tests/unit/backends/kicad/test_pcb_rebuild.py`, `tests/corpus/test_board_rt1.py`, `tests/unit/backends/kicad/test_roundtrip.py`; format identity: `tests/kicad/test_fmt_identity_10.py`, `tests/corpus/test_fmt_identity_9.py`.
- RT2: `tests/unit/checks/test_rt2_stage.py`, `tests/kicad/check/test_rt2_stage.py`, `tests/kicad/check/test_corpus_rt.py`, `tests/kicad/schematic/test_corpus_rt2.py`.
- Builds: `tests/unit/lens/test_build_bytes_pinned.py` (c0123): every pin of its `KICAD` table unchanged, which covers `.kicad_pcb`, `.kicad_sch`, `.kicad_pro`, `.kicad_dru`, the vendored libraries, the tables and the five layer files under `.fenolite/` for 35 designs on targets 9 and 10; `tests/unit/lens/test_build_determinism.py`, `test_build_readback.py`, `test_lens_acceptance.py`; the committed acceptance projects `tests/data/acceptance/*` (`tests/kicad/acceptance/test_finished.py`).
- A new test, `tests/unit/backends/kicad/test_fpitems.py::test_projection_changes_no_byte`: for every board of `tests/data/kicad/board/`, `write_board(read_board(text))` and `write_board(with_footprint_items(read_board(text)).design)` are the same text, and `canonical.dumps` of the unprojected design is the text it was before this change (a digest pinned in the test on the commit before any code).
- **No KiCad file is named as changing.** The claim is "none".

Rejected: fill on every read (see "Decisions of the maintainer", 3); `Modeled` slots with an emitter (the writer would write footprint children from the model; `_Reader.check` keeps byte equality on a read and write, but every `.fenolite/board.json` changes, a text needs an entity with KiCad's whole `effects`, and the flip code of `embed.py` would have two sources).

### 6. Altium import

`adapter/copper.py` gains `footprint_items(doc, ctx, index, frame, rotation)`: the primitives with component index `index`, mapped as `definition_graphics` maps a library footprint and taken into the footprint frame with the inverse placement that the pads use.

| record with a component index | becomes | not mapped, and counted as |
|---|---|---|
| track | `line` graphic on its layer | — |
| arc | `arc` graphic; a full circle is a `circle` | radius 0: `bad-geometry` |
| fill | filled `rect`, or `polygon` when turned | — |
| region | filled `polygon` | fewer than three vertices: `bad-geometry`; its holes: `region-holes`, as for a free region |
| text, designator | field `Reference`: position, layer, size, rotation, thickness, `visible` | a second one of the same component: a text of the footprint |
| text, comment | field `Value`, likewise | likewise |
| other text | `Text` in `texts` | — |

- A graphic on a copper layer keeps its net name in the pair `net`, as a free shape on copper does today.
- `footprint-graphics` stays a category of the census for the one case that still gives no entity: the primitives of a component whose record has no readable position (`adapter/board.py`, the `continue` after `altium.import.bad-length`). On the corpus documents and the own samples it is expected to be 0.
- The census gets no new category: a mapped record counts under `mapped` of its kind (`tracks`, `arcs`, `fills`, `regions`, `texts`), so "the mapped and the unmapped counts of a kind add up to the reader's record count" holds.
- `Pad.corner_ratio` is `5000 · corner_percent`. The pair `corner_percent` stays in the bag, so a model stored before this change still writes (Decision 9).
- No new format fact: every field used is typed by the reader today (`read/pcbprims.py`: `TrackRecord`, `ArcRecord`, `FillRecord`, `RegionRecord`, `TextRecord.is_designator`, `is_comment`; `read/pcb.py::ComponentRecord.name_on`, `comment_on`). The rows of `docs/formats/altium/import.md` that say what a component index means are amended with their registered sources.

### 7. Altium write of a footprint's items

`lower._footprints` builds each component's definition from the instance: pads as today, and now graphics, in the top-side form (`_library_graphic` mirrors a bottom footprint's points about the local X axis and swaps the layer, the inverse of what `place_component` applies, as `_library_pad` does for pads).

- **Layers.** For a board that was read from Altium (`"altium" in board.native_ids`) the layer table of footprint and board items gains `Mech.13` … `Mech.16` → 69 … 72. Those four layers are enabled in every document that Fenolite writes (`libboard.ENABLED_MECHANICAL`), so no record of the board changes. With that, Fenolite's own samples keep all 27 lines and arcs of their footprints on a rewrite, and `board6` writes the 2 texts and 5 graphics it leaves out today.
- **Mechanical 1 … 12** (part of group 5, not to be cut: decision of the maintainer): for a board read from Altium `Mech.<n>` → `56 + n`, for footprint and board items, and the board record enables each mechanical layer that a primitive lies on (`MECHENABLED`, a key the writer writes today for 13 to 16); a document that uses none of them keeps its bytes. Without these layers a rewrite of a public document would keep the overlay lines and arcs (2 363 of 16 647 records) and what lies on Mechanical 13 to 16; with them, 11 373 more.
- **What `from_design` leaves out and counts.** New kinds of `lower.MORE_KINDS`, so `lower.KINDS` and `result.pcb` of a build do not change: `footprint-graphic` (a polygon or a filled shape until group 5b; a layer without a layer in the document; a degenerate arc) as an info; `footprint-copper` (a graphic on a copper layer: 102 records of the corpus) as a warning that needs `allow_lossy`, in `LOSS_KINDS`, like `copper-shape`; `footprint-text` (a free text until group 5a; a text the record cannot hold) as an info.
- `pcblib.check_footprint` is not changed: the lowering filters what it hands over, so the refusal of a copper graphic and the drops of the build stay as they are for a library footprint.
- **Fields.** `pcbdoc.PlacedComponent` gains `designator: TextPlace | None = None` and `comment: TextPlace | None = None` (position in the footprint frame, layer, height, stroke, rotation, shown). `None` keeps the place and the `NAMEON` / `COMMENTON` values the writer chooses today, so a build's bytes do not move. `from_design` fills them from the fields `Reference` and `Value` of an instance that has them.
- **Free texts** (group 5a) are text records with the component's index; **fills and regions** (group 5b) are the region records of c0085 with the component's index.
- **Corner ratio.** `_extras` reads `pad.corner_ratio` (`Fraction(ratio, 10**6)`), else the pair `corner_percent` (a model stored before this change), else the caller's `corner_ratios`. The parameter `corner_ratios` of `from_design` and `write_design` is kept for one release and `lens.altium.write_model` stops passing it once group 3b lands.

### 8. The build goes through `from_design`

`from_design(design, *, issues, options: LowerOptions | None = None)`. `options` holds what a build knows and a model does not; `None` is the write of a model as c0090 defined it.

| what the build decides | today in `lens.altium` | after |
|---|---|---|
| placements, staged parts | `pcb_document` | the lens places: `lens.altium.place_footprints` gives the model a `FootprintInstance` per component (position, rotation, side, locked; the pads and graphics that `pcblib.check_footprint` keeps, in the pad frame; `corner_ratio = 5000 · pcbrecords.corner_percent(ratio)`) before the lowering |
| the footprints of `<name>.PcbLib` | `resolve_footprints` | unchanged, handed over as `options.library` |
| the library file name of a component | `project.pcblib_name(link, design=name)` | `options.library_file` |
| symbol link and symbol library name | `project.schlib_name` | `options` |
| the sheet link of a component on a module sheet | `hierarchy.sheet_of`, `symbol_key` | `options.sheets`, computed in `lower` (`hierarchy` is a module of the backend) |
| comment fallback for text outside 7-bit ASCII | `pcb_document` | `lower`, same rule and same issue |
| pad nets | by pin number (`pad_nets`) | by pad (`nets_by_pad`), from `Pad.net_id` of the placed instances, which c0123 sets through the pin-to-pad map |
| copper: layer count, planes, script copper, a copper source | `altium_copper.lower_copper`, `with_copper` | the lens puts the plan's tracks, arcs, vias and zones and the layers into the model's board; `lower._copper` writes them |
| rules | `altium_copper.lowered_rules` | `lower`, with the same `rulemap` |
| form, directions, drawing sheet, output job | options of `write_project` | unchanged, in `options` |

- **Byte equality is the acceptance test.** c0090 wrote that the bytes of the samples would change if the build went through the model, because the model had no graphics. With `graphics` and `corner_ratio` in the instance they need not. The claim is: **no file under `tests/data/altium/` changes** (65 files; the six that hold a board are `blink`, `board6` and `routed`, each `.PcbDoc` and `.PcbLib`).
- **How "none" is proved.** The first implementation task (1.1), before any change of the model, writes `tests/unit/backends/altium/test_lower_build_spec.py` as a report: for every example script, in both sheet modes, the `PcbDocSpec` of `pcb_document` and the one of `from_design` are compared field by field, and every differing field is a row of the table "The two build paths, field by field" below. Task 6.1 turns the report into an assertion of equality, and the switch (6.2) is made when it passes with no listed exception. Then, without an edit of any of them: `tests/unit/lens/test_altium_pcb_golden.py` (`test_golden_pcb_files`, `test_sample_files_keep_their_bytes`), `test_altium_copper_golden.py` (`test_golden_routed_files`, `test_golden_sample_files_keep_their_bytes`), `test_altium_pcb_complete.py` (`test_board6_golden_files`, `test_altium_samples_of_earlier_changes_keep_their_bytes`), the other `test_altium_*_golden.py`, `tests/unit/cli/test_build_altium.py` (the keys of `result`, `result.pcb` and the issue list) and `tests/unit/lens/test_altium_issues.py`.
- **What does change in a build:** `.fenolite/board.json` of an Altium build that writes a PCB document. Its footprints gain `graphics` and its rounded pads `corner_ratio`. It is not a committed file. c0123's `ALTIUM` pins digest it with the other files, so the ten pins move; task 6.3 changes them with this reason beside them, after showing that the digest of the files outside `.fenolite/` is unchanged.
- **`pcb_document` and `corner_ratios` are removed** when the switch is made; `lower.stored_board` stays (the stored model is the board that was written, Decision 10).
- **Stop rule.** If the comparison of task 1.1 shows a field of the specification that cannot come from the model plus the options, the switch of the build stops there and the implementer reports to the coordinator before going on. The model is not bent to hide it: no field is added, renamed or given a second meaning, and no value is approximated, to make the two specifications meet. This change is meant to be the last of the model in v0.3; that holds only if the table is complete.

### The two build paths, field by field

Filled by task 1.1, the first implementation task, before any change of the model; updated by task 6.1 with the commit that closes each row.

Measured on 2026-10-08 on the base `f17b03e9`, before any change under `src/`, by `tests/unit/backends/altium/test_lower_build_spec.py` in its first form (a report). 15 scripts under `examples/`, each in the sheet modes `flat` and `modules`: 9 builds write a PCB document and are compared in each mode (`altium_hier_board`, `blink_2layer`, `blink_official`, `blink_routed`, `board_40parts`, `kit/board6`, `kit/flat`, `kit/libs`, `kit/routed`); 6 plan no PCB document (`altium_hier/design.py`, `altium_hier/partial.py`, `altium_kicad/design.py`, `altium_kicad/no_connect.py`, `altium_sample/design.py`, `kit/tree/design.py`: Altium footprint links or no footprint) and have nothing to compare. The lowering is given the model the build stores, as the build holds it in memory. 71 placed components in all per mode.

The report compares two views. The **written view** holds what `pcbdoc` writes records from: every field of `PcbDocSpec` but the placed footprints, every field of `PlacedComponent` but `footprint`, `pad_nets` and `nets_by_pad`, and of each placed footprint its pattern, the pads and graphics that `pcblib.check_footprint` keeps (every field but `id`, `native_ids`, `provenance`, `ext`, `net_id`), the corner percentage and the net of each pad. The **raw view** is every field of the two objects.

**A. Fields of the written view that differ on the examples.**

| field | `pcb_document` | `from_design` on the stored model | the equal value comes from |
|---|---|---|---|
| `components[].footprint`: the pads (30 components of 5 builds hold rounded pads; every pad field after the first rounded pad shifts) | the pads of the library definition, rounded rectangles included | the rounded pads are left out: "a rounded rectangle without a corner ratio" | (a) `Pad.corner_ratio`. Measured: with the build's ratios handed over through c0090's `corner_ratios`, every pad field of the written view is equal on all 9 builds (number, kind, shape, position, size, rotation, layers, drill, pad stack, zone connection, corner percentage, net) |
| the corner percentage of a rounded pad | `corner_percent(ratio)` of KiCad's decimal (`Decimal('0.25')` → 50) | none | (a) `Pad.corner_ratio = 5000 · corner_percent(ratio)`, read back as `Fraction(ratio, 10**6)`: the same whole percent. KiCad's own decimal stays in the library definition, from which `<name>.PcbLib` is written (`options.library`) |
| `components[].footprint`: the graphics (71 components, 304 kept graphics per mode) | the graphics that `check_footprint` keeps of the library definition | none | (a) `FootprintInstance.graphics`, placed in the pad frame by `place_footprints` and taken back to the top-side form by `lower._library_graphic` |
| `components[].footprint_library` (71) | `<design>.PcbLib` (`project.pcblib_name`) | `<library of lib_ref>.PcbLib` | (b) `LowerOptions.library_file` |
| `components[].component_library` (71) | `<design>.SchLib` (`project.schlib_name`) | `<library of the symbol link>.SchLib` | (b) `LowerOptions.symbol_file` |
| `components[].sheet` (`modules` mode: 43 components of 2 builds) | `(sheet symbol ids, module names)` | `None` | (b) `LowerOptions.sheets`; computed in `lower` with `hierarchy.sheet_of` and `symbol_key` |
| `components[].pad_nets` / `nets_by_pad` | by pad number / `None` | empty / by pad id | (c) the same net per pad (the written view's `net` is equal): `Pad.net_id` of the placed instances, which `place_footprints` sets through the pin-to-pad map (`altium_copper.pad_net_names`, c0123) |
| `frame` (9) | `None` | `Frame.of(outline)` | (c) the same frame: `None` means `Frame.of(outline)`. `lower` gives `None` for a board that was not read from an Altium document; no byte of a write changes |
| `zones` (1 build, `board_40parts`) | one zone on two layers | two zones of one layer (`stored_board` splits a zone per written polygon and derives ids) | (c) the lens puts the plan's zones into the model's board before the lowering; the stored board is made after it, as today |

**B. Fields of the raw view that no record is written from** (they differ, and stay different).

| field | `pcb_document` | `from_design` | why it is no row of kind (d) |
|---|---|---|---|
| `footprint.defn.id`, `.description`, `.keywords`, `.kind`, `.library`, `.models`, `.properties`, `.native_ids`, `.provenance`, `.ext`; `footprint.texts` | those of the library definition | those of a definition made from the instance | The PCB document reads `defn.name` (`PATTERN`) and the kept pads and graphics, and nothing else of a placed footprint (`pcbdoc._component_record`, `place_component`). The other fields are written into `<name>.PcbLib` and read by the lens's checks, from the library definitions that the lens hands over as `options.library` |
| `footprint.extras[].dropped`, `.refusal` | the notes of `lens.altium.pad_extras` | empty | They feed `altium.primitive-dropped` and `altium.footprint-unsupported`, which `resolve_footprints` reports in the lens before the lowering, unchanged |
| `id`, `native_ids`, `provenance`, `ext` of a pad and of a graphic; the key of `extras` | those of the library entity | those of the instance's entity | An id is a key inside the specification. Two components of one footprint share the library's pad ids; the pads of two instances of a model cannot (`Design.validate`, duplicate ids). `place_footprints` derives them as `stored_board` does |

**C. Fields that are equal on every example, where the two paths follow different rules** (found by reading both, 2026-10-08).

| field | `pcb_document` | `from_design` | the equal value comes from |
|---|---|---|---|
| `nets` | every net name, in circuit order (a script's circuit is sorted by name) | the names a record holds, once, sorted | (c) with options: the circuit's order; the build's checks refuse a name that no record holds before the lowering |
| `outline` | `Board.outline.points` as given; cut-outs plan no document | `_open` of the points; cut-outs counted | (c) the lens decides whether a document is planned; with options the points are taken as given |
| `components[]` order, staged parts | by component path; an unplaced part staged right of the outline | the order of `Board.footprints` | (c) `place_footprints` places and stages in the build's order |
| `components[].comment` | `_comment`, and the symbol name for a text outside 7-bit ASCII | `Component.value` | (c) the rule and its issue move into `lower` (with options) |
| `components[].unique_id` | `project.unique_id(component.id)` | the native unique id, else the same | equal for a model that was not read from Altium |
| `copper_layers`, `stack` | the script's layer count and planes (`board_layers`, `plane_nets`, `stack_values`) | the board's copper layers and their pair `plane_net` | (b) `LowerOptions.copper` and `.planes` |
| `tracks`, `arcs`, `vias`, `zones` of a copper source | the source's copper, checked (`lower_copper`); an item that cannot be written is an error | the board's copper; an item that cannot be written is counted | (c) the lens checks as today and puts the plan's copper into the model's board, with the design's net ids |
| `net_classes`, `texts`, `graphics`, `keepouts`, `holes`, `design_rules` | `altium_copper.net_classes`, `lower_items`, `rulemap.lower` | the same rules for what both write; a shape on a copper layer is counted under `copper-shape` by the one and under `graphic` by the other, and written by neither | (c) the lens reports as today; the lowering writes the same items |
| `bodies`, `body_form` | `altium_copper.lower_bodies`, from the bodies of the model's footprints | `pcbdoc.place_body` per instance | (c) `place_footprints` keeps the bodies of the model's footprint of a component; (b) the form |
| `origin`, `free_pads`, `arc_records`, `allow_full_drill`, `rules` | defaults | defaults for a board that was not read | equal |

**Verdict (2026-10-08): no row of kind (d).** Every field that a record of the PCB document is written from comes from (a) one of the three new fields, (b) an entry of `LowerOptions`, or (c) lens code that moves or stays. The rows of table B are no fields of the document: they are keys and library data that the PCB library and the lens's own checks read from `options.library`. The switch of the build (group 6) can go on.

**Closed on 2026-10-08 (task 6.1), by the commit of this change.** With `lens.altium.lowered_pcb` (the reason checks, the copper source, `place_footprints`, `altium_copper.lower_copper`, the plan's copper put into the model's board, then `lower.from_design` with `lower.LowerOptions`), every example build that writes a PCB document gave, in both sheet modes, a specification equal to that of `pcb_document` in the written view with no listed exception, the same issues and the same bytes of `pcbdoc.write_pcbdoc` (8 builds per mode; `blink_official` not built, "Found" 14). Rows of kind (a) are closed by `place_footprints` (the pads and graphics in the pad frame, `corner_ratio` of the written percent); rows of kind (b) by `LowerOptions` (`library`, `name`, `sheets`, `copper`, `planes`, `body_form`; "Found" 12); rows of kind (c) by `lowered_pcb` and by `from_design` with options (the circuit's net order, the outline as given, the build's comment rule `lower.written_comment`, `PcbDocSpec.frame` `None`). The pad field `corner_ratio` is no field a record is written from: the written view compares the corner percentage instead. The switch was then made (task 6.2).

**What cannot hold as written, and is restated** ("Found on 2026-10-08", 1): the two `PcbDocSpec` objects cannot be equal in every field of the raw view, because the entities of an instance have ids of their own. The assertion of task 6.1 is therefore: the two specifications are equal in the written view, field by field, with no listed exception, **and** `pcbdoc.write_pcbdoc` gives the same bytes for both. The scenario "The two paths give one specification" says so.

### 9. Old model documents

A `board.json` written by 0.2.0, or by any commit before this change, has none of the three keys. It loads with `graphics == ()`, `texts == ()` and `corner_ratio is None`, and every consumer then does what it does today:

- the Altium write of such a model writes no footprint graphic; for a rounded pad it reads the pair `corner_percent` (an Altium import) or the caller's ratios, and counts a pad without either as it does today;
- RT-A2 on a built project whose stored board holds footprints without graphics, while the reading holds some, is skipped with the reason `model-predates-graphics` (the form of c0090's `model-predates-board`);
- a rebuild writes a new `.fenolite/`; nothing needs a migration.

`SCHEMA_VERSION` stays `"0"`, as for `no_connects`, `buses`, the pad stack fields and the bodies. One direction does not work and is said in the changelog line and in `docs/design-model.md` (tasks 8.5 and 2.6): **0.2.0 cannot read a model document that carries the new keys** (`unexpected property 'graphics'`), because the reader of the canonical form is strict. That was already so for every additive change of the model.

The first direction is proved on a file that 0.2.0 itself wrote (task 2.2): `tests/data/model/v0.2.0/blink_2layer.board.json`, built by the code of the tag `v0.2.0` from `examples/blink_2layer/design.py` at that tag in a scratch worktree outside the repository, with a fixed seed and timestamp, copied byte for byte and declared in `tests/data/MANIFEST.toml`. It is authored data of Fenolite. The test loads it and serialises it again to the same bytes.

The committed schemas `schemas/fenolite.model.v0/board.json` and `library.json` are regenerated (`Pad` is shared with library definitions).

### 10. What the comparisons read

- **`diff`** (`checks/diff.py`). Today `keyed["footprint"][owner]` holds every field of the instance but `pads`, as nested values. The two new fields are skipped there and compared as two content kinds, `footprint_graphic` and `footprint_text`: each entity with the reference of its footprint, matched by content like `graphic` and `text`, so order does not count and a scope's tolerance applies to the points. `corner_ratio` is a field of the kind `pad`. Without a scope every comparison is exact, as today. Two designs without the new fields give the report they gave before.
- **`equivalent`** (`checks/equivalence/levels.py`). No level changes. Levels 1 to 5 compare components, nets, pads, placement and routing; a footprint's drawing is none of these, and the corner ratio is not part of level 3 (the profile of KiCad's importer has no claim about it). Graphics count in the model difference and in the two Altium round-trip levels below, and nowhere in `equivalent` in v0.3.
- **RT-A2 and RT-A3** (`roundtrip.RT_A2_SCOPE`, which is `RT_A3_SCOPE`). The scope gains the kind `footprint_graphic` with `kind`, `layer`, `points`, `width` and `filled`, and the field `corner_ratio` of `pad`. Lengths within 2 nm, as the rest of the scope; the points of an `arc` graphic follow whatever rule holds for the points of a copper arc when this change is implemented (c0090, "Found" 10a; c0127), and task 0.1 writes which. `fields` and `texts` of a footprint are written and not compared: the stored board of a build holds no field for the designator that the writer places itself, and a row of "Round trips" in `docs/altium.md` says so.
- **The stored board holds what was written.** `lower.stored_board` gives each footprint the graphics that the document holds, in the written form: a rectangle is its four lines in the writer's order, because the reading holds four tracks. `ModelWriter.in_model_frame` names `Mech.13` … `Mech.16` of the reading `F.Fab`, `B.Fab`, `F.CrtYd`, `B.CrtYd` when the model was not read from Altium.
- **Pad order.** `FootprintInstance.pads` is not ordered in the JSON. The build lowers the model it holds in memory, in library order, so its bytes are those of today. A write of the model loaded from `.fenolite/` may order the pad records of a component otherwise: it reads to an equal model and is not promised byte-equal to the build. The scenario "Build and write agree" says both.

### 11. RT-A3 expectations

- `record:footprint-graphics` leaves `unwritten` on every document of the table and on the own samples (16 647 and 33 records).
- What appears instead, as model items not written, by key: `footprint-copper` (102 on the corpus); `footprint-graphic` for a layer without a layer in the document (the 3 regions on other layers), for fills and regions if group 5b is cut (285), for a region with holes; `footprint-text` if group 5a is cut (644). The 11 373 mechanical lines and arcs are written. Task 7.2 measures them and replaces these predictions on the evidence page.
- What stays as it is, because this change does not touch it: `shape-based-regions`, `pour-primitives`, `polygons`, `classes`, `region-holes`, the storages kept as bytes, and `body`.
- The verdicts must not move: seven documents equal, the heavy one as c0127 leaves it. A new difference inside the widened scope is a defect of the import or of the writer and is fixed there.
- KiCad's importer (`H-A-PCBX-FPGFX-KICAD`): on the rewrite of each own sample and of each public document that is not heavy, `kicad-cli pcb import` gives a board whose footprints, projected by Decision 5, hold as many lines and arcs per footprint and layer class as Fenolite's reading of the same rewrite. It needs group 3b.

## Files and public API

- `src/fenolite/model/board.py`: the three fields; `model/design.py`: `by_layer`, `validate` (`model.corner-ratio`); `schemas/fenolite.model.v0/board.json`, `library.json` (generated).
- `src/fenolite/checks/diff.py`: the kinds `footprint_graphic`, `footprint_text`.
- `src/fenolite/backends/kicad/fpitems.py` (new): `Projection`, `with_footprint_items`, `PROJECTED_PAIR`; `pcb.py`: the comparison in the projection check of `write_board`.
- `src/fenolite/backends/altium/adapter/copper.py`: `footprint_items`; `adapter/board.py`, `adapter/pads.py`.
- `src/fenolite/backends/altium/lower.py`: `LowerOptions`, `_library_graphic`, the new kinds, `stored_board`; `pcbdoc.py`: `TextPlace`, `PlacedComponent.designator`, `.comment`; `libboard.py`: mechanical layers enabled by use; `roundtrip.py`: the scope; `backend.py`: `in_model_frame`.
- `src/fenolite/lens/altium.py`: `place_footprints`; `pcb_document` and `corner_ratios` removed; `write_model` projects.
- `src/fenolite/checks/rta2.py`: `predates_graphics`; `src/fenolite/cli/data/explain.toml`: `model.corner-ratio`.
- Tests: `tests/unit/model/test_footprint_items.py`, `tests/unit/backends/kicad/test_fpitems.py`, `tests/unit/backends/altium/adapter/test_footprint_items.py`, `tests/unit/backends/altium/test_lower_items.py`, `test_lower_build_spec.py`, `tests/unit/checks/test_diff.py` (extended), `tests/kicad/altium/test_fpitems_oracle.py`, `tests/corpus/test_altium_import.py` and `test_altium_rta3.py` (extended). One file is added under `tests/data/`: `tests/data/model/v0.2.0/blink_2layer.board.json` (Decision 9), with its entry in `tests/data/MANIFEST.toml`.

## Sources registered by this change

- No new source is expected: every record field used is typed by the readers and has a row in `docs/formats/altium/pcb-records.md`, `pcb-read.md` or `pcb-document.md`.
- If the mechanical layers or the text placement need a field without a row, the row is written first with a registered public source, or the item is reported as not lowered. A new source takes an id of the block **S-0580 … S-0589**, reserved for this change by the coordinator (S-0570 … S-0579 is c0121's).

## Hypotheses registered by this change

| id | statement | settling test | criterion | level sought |
|---|---|---|---|---|
| H-G-FPGFX-ADD | The three fields are additive: a design without them gives the canonical texts it gave before, and a document without the keys loads | `tests/unit/model/test_footprint_items.py`, `tests/unit/test_schema_drift.py` | equal texts for the fixture designs; a 0.2.0 `board.json` loads | `INFERRED` |
| H-G-CORNER-PPM | One ppm of the shorter side holds Altium's whole percentages and KiCad decimals of six places exactly | `tests/unit/model/test_footprint_items.py -k corner` | `5000 · p` and back for p in 0 … 100; the ratios of the vendored library footprints | `INFERRED` |
| H-K-PCB-FPGFX | The projection of a board footprint equals the graphics that `mod.read_footprint` gives for the same definition, placed in the pad frame | `tests/unit/backends/kicad/test_fpitems.py` | equal for every footprint of the mini library on both sides and at four angles | `INFERRED` |
| H-K-PCB-FPGFX-BYTES | No output of a KiCad read, write or build changes | the gate of Decision 5 | every listed test passes without an edit; no pin of `KICAD` moves | `INFERRED` |
| H-A-IMP-FPGFX | A track, arc, fill, region or text with a component index belongs to that component's footprint and maps to its graphics, fields and texts | `tests/corpus/test_altium_import.py` | on every listed document the census conserves each kind's record count and `footprint-graphics` is 0 | `CORPUS-VERIFIED` |
| H-A-PCBX-FPGFX | The written graphics and corner ratios of a component read back as the model's | `tests/unit/backends/altium/test_lower_items.py` | equal within 2 nm for the own samples, both sides | `INFERRED` |
| H-A-PCBX-FPGFX-KICAD | KiCad's importer reads the written lines and arcs as parts of the footprint | `tests/kicad/altium/test_fpitems_oracle.py` | equal counts per footprint and layer class on the listed rewrites; probe `altium-fpitems-kicad` | `ORACLE-VERIFIED(kicad-cli 10.0.x)` |
| H-A-PCBX-FPTEXT | A designator and a comment written from a field lie where the field says, shown or hidden | `test_lower_items.py -k field` | position, height and `visible` read back equal | `INFERRED` |
| H-A-PCBX-MECH | A primitive on Mechanical 1 … 12 is read on that layer when the board record enables it | `test_lower_items.py -k mechanical` | read back on `Mech.<n>` | `INFERRED` |
| H-A-PCBX-BUILD-LOWER | The build through `from_design` writes the bytes it wrote before | the golden tests of Decision 8 | no file under `tests/data/altium/` changes; the pins move by `.fenolite/board.json` alone | `INFERRED` |
| H-A-VER-RTA2-GFX | For a built project the stored footprint graphics and corner ratios equal the reading | `tests/unit/lens/test_altium_rta2.py` | every example build compares `footprint_graphic` with 0 differences | `INFERRED` |
| H-A-VER-RTA3-GFX | A document that Altium saved keeps the footprint graphics that the write reports as written | `tests/corpus/test_altium_rta3.py` | equal on every listed document that is equal today | `INFERRED` |
| H-A-PCBX-FPGFX-AD | Altium shows the rewritten lines, arcs, designator and comment as parts of their component | author report, Part G | steps G1 to G6 | `ALTIUM-VERIFIED(author-report)` |

All start `INFERRED`. None of these ids is in `docs/hypotheses.md` or in another active change (checked on `ba21a109` and on the branch of c0123, 2026-10-06). The families `IMP` and `PCBX` are accepted by `ALTIUM_HYPOTHESES` of `tests/unit/test_format_facts.py`.

## Author report, Part G (only the maintainer can do this)

Files, built by task 8.2 into `~/fenolite-altium-checks/c0126-part-g/` (outside the repository): `original/` (the committed `board6` project), `rewrite/` (its import written by `AltiumBackend().write`), `rewrite-mech/` (an authored document with lines on Mechanical 1 and 5, imported and written), and `expected.md` (the counts per component and layer, the corner percentages of four pads, the places of the three designators).

1. G1: open `rewrite/board6.PcbDoc` beside `original/board6.PcbDoc`. Expected: each component shows the same silkscreen outline in both.
2. G2: in the PCB List panel, filter the tracks and arcs of `U1`. Expected: the counts of `expected.md`, each on the layer named there.
3. G3: drag `R1` by 5 mm. Expected: its lines move with it; undo.
4. G4: press `L` while dragging `R1`. Expected: its overlay lines go to the bottom overlay; undo.
5. G5: open the properties of the four pads named in `expected.md`. Expected: the corner radius percentages of the table.
6. G6: compare the place and the visibility of the designator and the comment of each component with the original. Expected: equal.
7. G7: `rewrite-mech/` holds a document with lines on Mechanical 1 and 5. Expected: both layers are listed and shown, and the lines lie on them.

The build needs no step: its files are byte-equal to the committed samples, which the earlier parts cover. Nothing is marked `ALTIUM-VERIFIED` before the report is recorded.

## Size (design-days)

| group | dd |
|---|---|
| 0 entry check | 0.25 |
| 1 the two build paths compared, field by field | 0.5 |
| 2 model: registers, the 0.2.0 fixture, fields, schema, validation, diff, page | 1.75 |
| 3a KiCad gate | 0.5 |
| 3b KiCad projection on request | 1.5 |
| 4 Altium import | 1.5 |
| 5 lowering: lines and arcs, fields, corner ratio, Mechanical 1 to 16 | 1.75 |
| 5a free texts | 0.5 |
| 5b fills and regions | 0.25 |
| 6 build through the lowering | 3 |
| 7 round trips, corpus, oracle, pages | 1.75 |
| 8 Part G files, closing | 0.5 |

Total: 13.75. This is a size, not a calendar estimate.

**Cut order.** First 3b (with it the KiCad oracle and the removal of `corner_ratios`), then 5a, then 5b. Never: the comparison of the two build paths, the model fields, the KiCad gate, the import, group 5 (Mechanical 1 to 12 included, by the maintainer's decision), and the build through the lowering with byte-equal samples. Without the three groups that can be cut the size is 11.5.

## Spec deltas and archive order

- `design-model`: three ADDED requirements. "Model layers for v0.1" and "Footprint fields" are not modified: the first lists layers, not fields, and the second stays true.
- `kicad-file-backend`: one ADDED requirement. "Projected fields on write" is not modified: its last bullet already covers "any other projection".
- `altium-import`: MODIFIED "Footprint instances and pads", copied from the living text (no active change holds a delta of it: checked with `grep` over `openspec/changes/*/specs` on `ba21a109` and on the branch of c0123); two sentences are replaced, two scenarios added. One ADDED requirement.
- `altium-pcb-writer`: MODIFIED "Imported boards are written from the model", copied from the delta of c0090 (ADDED there, not archived); one ADDED requirement.
- `backend-protocol`: MODIFIED "Altium write of a model", copied from the delta of c0090.
- `altium-build`: MODIFIED "Stored board of an Altium build", copied from the delta of c0090; one ADDED requirement. "Altium build outputs" is not modified: its steps and its file list stay true.
- `altium-verification`: MODIFIED "Round-trip level RT-A3", copied from the delta of c0090 (the scenario "Own sample" and one bullet); one ADDED requirement. "Round-trip level RT-A2" is not modified: it says "at least" for the scope.
- `verification-loop`: one ADDED requirement.
- If c0127 or c0128 modify "Round-trip level RT-A3" or "Imported boards are written from the model" before this change is implemented, task 0.1 copies their text and applies the same replacements again; the replaced sentences are quoted under "Spec deltas" of the tasks.
- Archive order: after c0090, c0123, c0127 and c0128; before c0092.

## Risks / Trade-offs

- [The build's specification has a field that the model and the options cannot give] → the stop rule of Decision 8; task 1.1 finds it before the model or any byte moves, and the implementer reports to the coordinator.
- [A KiCad byte moves by accident] → the gate runs first, on the commit before any code, and after every group; the projection is a new module that nothing on the read or write path imports.
- [`board.json` of an imported board grows by about 43 %] → said in the changelog, measured in task 7.1 and shown to the maintainer with the result ("Decisions of the maintainer", 5).
- [RT-A3 finds differences in graphic arcs] → the rule for arcs is c0127's; the scope names it, and a listed row may differ in `footprint_graphic` arcs only with its cause on the evidence page.
- [No public source gives the meaning of the key that enables a mechanical layer] → task 5.2 stops and reports; the lines on Mechanical 1 to 12 are then counted under `footprint-graphic`, not written on a guess.

## Migration Plan

- Model documents: none (Decision 9).
- Altium builds: same project files; a larger `.fenolite/board.json`.
- Callers of `from_design(…, corner_ratios=…)`: the parameter stays for one release.
- `altium.import.unmapped` of an import no longer lists `footprint-graphics` on a normal document: a change of a command's output, said in the changelog.

## Measured on 2026-10-08 (task 7.1)

Size of `.fenolite/board.json` and of the canonical `board.json` of an import, before (the base `7f25ca8a`) and after this change, measured with Fenolite's own code on the machine of this change:

| what | before | after |
|---|---|---|
| Altium build of `blink` (each of the four `blink` pins) | 52 402 | 63 644 |
| Altium build of `board_40parts` | 218 117 | 351 501 |
| Altium build of `nested` | 55 305 | 71 247 |
| Altium build of `units` | 52 356 | 63 598 |
| import of `tests/data/altium/blink/blink.PcbDoc` (27 footprint graphics, 6 field places) | 107 937 | 189 878 |
| import of `tests/data/altium/routed/routed.PcbDoc` | 138 637 | 221 118 |
| import of `tests/data/altium/board6/board6.PcbDoc` | 187 686 | 264 096 |

An imported graphic or field costs about 2.3 to 2.5 kB of `board.json` with its provenance and bag (the estimate above was 1.3 kB per line). A graphic of a built board has no provenance and no bag: the blink build adds 11 242 bytes for 27 graphics and 34 corner ratios. The sizes of the imports of the eight public documents were measured with the corpus run of task 7.2 on 2026-10-09: `docs/evidence/altium-roundtrip.md`, section "RT-A3" (for example `altium-third-party-pcbdoc-01` from 7 168 701 to 14 623 055 bytes, measured on the base `7f25ca8a` and on the tree of release 0.4.0).

## Decisions of the maintainer (2026-10-06)

The seven open decisions of the first form of this proposal, as answered through the coordinator on 2026-10-06. No decision is open.

1. **The change goes ahead in v0.3**, implemented on top of c0123.
2. **Mechanical 1 to 12 are in, and are not to be cut.** A rewrite keeps the assembly and courtyard drawings of its footprints, not only the silkscreen. The group left the cut order; it is part of group 5 (task 5.2).

The other six are **decided by default, to be shown to the maintainer with the result** (task 8.5 shows each with what was measured):

3. **KiCad reads fill the fields on request only** (Decision 5). No KiCad output changes; the fields are empty on a design read from KiCad until a caller asks for the projection. Not taken: filling on every read, which would change `.fenolite/board.json` of every KiCad build and all 70 `KICAD` pins of c0123.
4. **The corner ratio is in ppm of the pad's shorter side** (Decision 2). Not taken: a decimal string, a radius in nanometres.
5. **Provenance is kept on every imported footprint graphic**, as on every imported entity. The cost is about 1.3 kB per graphic and about 43 % more `board.json` on the public corpus; task 7.1 measures it, and the number is shown with the result.
6. **Copper lines inside a footprint are not written.** They are counted as `footprint-copper`, a loss that needs `allow_lossy` (Decision 7). Not taken: writing them as tracks of the component with their net.
7. **No PCB library is derived from an imported model in v0.3.** The component records name the library of `lib_ref`. A derived library belongs to v0.5a, with `convert`.
8. **Fields and free texts are written and not compared in RT-A2 and RT-A3** (Decision 10). Their read-back is covered by unit tests.

Two conditions of the coordinator, both in the tasks:

- The field-by-field comparison of the two build paths is the first implementation task (1.1), before any change of the model, with its result as a table in this design and the stop rule spelled out in the task.
- "0.2.0 cannot read a model document that carries the new keys" is said in the changelog line and in `docs/design-model.md` (tasks 8.5 and 2.6), and a `board.json` that 0.2.0 wrote is a committed fixture that must load unchanged and serialise to its own bytes (tasks 2.2 and 2.3).
