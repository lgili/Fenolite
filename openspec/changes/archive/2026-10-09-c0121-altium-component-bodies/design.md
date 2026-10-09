## Context

- **What the model holds.** `fenolite.model.board.ComponentBody` (change c0043; `docs/design-model.md`, "Padstack holes, offsets and component bodies"): `kind` (`extruded` or `model`), `height` (board surface to the top), `standoff` (board surface to the underside, 0 by default), `outline` (a polygon in the footprint frame, empty when the source gives none), `layer`, `model` (a name; no data) and `name`. It lives in `FootprintInstance.bodies` and `FootprintDef.bodies`. `Design.validate()` reports `model.body-height` for a height below the standoff or a negative standoff. `FootprintDef.models` is another thing: the 3D model references of a KiCad footprint, a tuple of strings that the KiCad backend reads from `(model …)` and writes back as read (`backends/kicad/mod.py`).
- **Where a body comes from today.** Only from the Altium import (`adapter/board.py` and `adapter/library.py` call `adapter/bodies.component_body`) or from a model authored as a model. The DSL and the catalog make none: no call of `ComponentBody` is under `src/fenolite/dsl` or `src/fenolite/catalog`, no component or part has a height attribute, and a definition read from a KiCad library holds no body. The KiCad backend reads and writes no body; a KiCad build keeps the bodies of a design in `.fenolite/`.
- **What the reader knows.** `read/bodies.py` frames every body record of `ComponentBodies6`, of `ShapeBasedComponentBodies6` and of a library footprint, keeps every byte, and types seven keys (`docs/formats/altium/pcb-bodies.md`, rows under `H-A-IMP-BODY`, all `INFERRED`). The import maps a body with a component index to a `ComponentBody`: the kind from `MODEL.NAME`, the heights, the outline in the footprint frame, the layer of the layer byte, the identifier. It reads `ComponentBodies6` only. Model data of the `Models` storage is not imported.
- **What the writer does.** `pcbdoc.EMPTY_STORAGES` writes `ComponentBodies6`, `ShapeBasedComponentBodies6`, `Models`, `ModelsNoEmbed` and `Textures` with `Header` 0 and an empty `Data`. `lens.altium_copper.lower_items` and `lower._footprints` report each body with `altium.not-lowered` and `body/<id>` (c0085, "Component bodies are reported"); `KINDS` holds `body`, so `result.pcb` already counts it. `pcbrecords.region_record` writes a region whose first eight keys are the first eight keys of a body.
- **What c0085 said was missing** (its task 3.4): a fact row for each of the 28 untyped keys of a saved extruded body, the body layer of the layer map, and a path from a library footprint to its bodies.
- **Constraints.** Stdlib only; integer nanometres in, the PCB unit out; no key is written whose row is missing; no KiCad output changes; committed Altium samples keep their bytes; nothing of `adapter/bodies.py`, `model/board.py` or the analyses is touched (c0099).

## Goals / Non-Goals

**Goals:**
- The facts of the body record are rows with sources before any writer code, and the writer writes exactly the rows.
- An extruded body of the model is in the written document and reads back, or is counted with a reason.
- One Altium session settles what the corpus cannot: whether Altium takes a body whose identity keys are stand-ins.

**Non-Goals:**
- Everything under "Non-goals" in the proposal.

## Measured (2026-10-06, the corpus cache, Fenolite's own readers)

Read: the eight PCB documents with the use `rta` (`altium-third-party-pcbdoc-01` to `-08`; S-0172, S-0174, S-0175, S-0176, S-0187, S-0188, S-0199, S-0200) and the four PCB libraries (`altium-third-party-pcblib-01` to `-04`; S-0170, S-0171), with `read_pcbdoc`, `read_pcblib` and `read_bodies`, by throwaway scripts outside the repository. Only counts and value forms are recorded. Task 1.2 turns the measurement into `tests/corpus/test_altium_bodies.py`.

**Streams.** Every document holds `ComponentBodies6` and `ShapeBasedComponentBodies6` with the same number of records (23 to 1302; 1748 in all), each `Header` the 32-bit record count. `Models` holds one property record and one numbered stream per embedded model (3 to 68 per document, 213 in all); `ModelsNoEmbed` and `Textures` are empty in all eight. `UniqueIDPrimitiveInformation` lists pads only (3784 records, no body). Every record frames with an empty tail and no hole.

**Two kinds.** `MODEL.MODELTYPE=0` in 1272 records (five documents of three repositories: 2, 5, 30, 18 and 1217, so 1265 come from one repository) and `MODEL.MODELTYPE=1` in 476 (all eight documents). They differ as follows:

| | extruded (`MODEL.MODELTYPE=0`, 1272) | model (`MODEL.MODELTYPE=1`, 476; where a cell says 391, the count is of the seven documents that are not heavy) |
|---|---|---|
| `MODEL.NAME` | empty (1272) | a file name (476; corrected on 2026-10-07) |
| `MODEL.EMBED` | `FALSE` (1272) | `TRUE` (476) |
| `MODELID` in the `Models` storage | never (0 of 1272) | always (476 of 476) |
| last keys | `MODEL.EXTRUDED.MINZ`, `MODEL.EXTRUDED.MAXZ` | `MODEL.MODELSOURCE` (`Undefined`) |
| `STANDOFFHEIGHT` | 0 (1268) or positive (4) | 0 (301), positive (82), negative (93) |
| `MODEL.3D.ROTX/Y/Z`, `MODEL.3D.DZ` | `0.000`, `0mil` (1272) | any |
| outline | 4 vertices (1263), 5 (3), 6 (5), 21 (1) | 4 vertices (391) |

**The record, both kinds.** Type 12, one subrecord. Offsets in the subrecord: 0 the layer byte; 1 and 2 the bytes 12 and 0 (1748); 3 to 6 `FF` (no net, no polygon); 7 the component index as 16 bits (never `0xFFFF` in an extruded body of a document; `0xFFFF` in 4 bodies of the heavy document that name a model, and in the library record; corrected on 2026-10-07); 9 to 12 `FF`; 13 to 17 zero; 18 the length of the property text with its NUL; then the text, a 32-bit vertex count and the vertices. In `ComponentBodies6` a vertex is two doubles, and every coordinate of every vertex is a whole number of units (1748 of 1748 records); the first vertex is not repeated (1747 of 1748). The twin in `ShapeBasedComponentBodies6` at the same stream index has the same 18 bytes, the same property text byte for byte and the same component (1748 of 1748); its vertices are 37 bytes each, none round, with the same integer coordinates and one more vertex that repeats the first (1747); the one body with `ISSHAPEBASED=TRUE` holds 4 round vertices there and 21 plain ones in the other storage. Both windings occur (633 and 639 of the extruded).

**Field table of an extruded body** (1272 records; "known" means that the writer can state the value from the model or from a constant that every record holds):

| # | key or field | values over the corpus | written as | known |
|---|---|---|---|---|
| — | layer byte | 69 (764), 72 (488), 70 (15), 57 (5): `56 + n` for Mechanical `n` up to 16, and 72 for every layer above 16 | the mechanical layer of decision 5 | yes |
| — | flag bytes, net, polygon, the five bytes | constant (1272) | the constants | yes |
| — | component index | the component of the body; every index names a component | the index of the placed component | yes |
| 1 | `V7_LAYER` | `MECHANICAL13` (764), `MECHANICAL23` (488), `MECHANICAL14` (15), `MECHANICAL1` (5); agrees with the byte up to 16 | the text of the layer byte | yes |
| 2 | `NAME` | one space (1272) | one space | yes |
| 3 | `KIND` | `0` (1272) | `0` | yes |
| 4 | `SUBPOLYINDEX` | `-1` (1272) | `-1` | yes |
| 5 | `UNIONINDEX` | `0` (1272) | `0` | yes |
| 6 | `ARCRESOLUTION` | `0.5mil` (1272) | `0.5mil` | yes |
| 7 | `ISSHAPEBASED` | `FALSE` (1271), `TRUE` (1, the body with arcs) | `FALSE` | yes |
| 8 | `CAVITYHEIGHT` | `0mil` (1272) | `0mil` | yes |
| 9 | `STANDOFFHEIGHT` | mil text, at most four decimals; 0 (1268), positive (4) | the body's standoff | yes |
| 10 | `OVERALLHEIGHT` | mil text; 20 values, each above the standoff (1272) | the body's height | yes |
| 11 | `BODYPROJECTION` | `0` on a component whose layer is `TOP` (767 of 767), `1` on `BOTTOM` (505 of 505); the same on the model bodies with a component (291 and 181) | 0 or 1 by the side of the footprint | yes |
| 12 | `ARCRESOLUTION` (a second time) | `0.5mil` (1272) | `0.5mil` | yes |
| 13 | `BODYCOLOR3D` | an integer; seven values, `12632256` in 836 | `12632256`, Fenolite's choice | choice |
| 14 | `BODYOPACITY3D` | `1.000` (1272) | `1.000` | yes |
| 15 | `IDENTIFIER` | empty (1270) or decimal character codes joined by commas (2; 373 of the model bodies) | the codes of `ComponentBody.name`, empty without a name | yes |
| 16 | `TEXTURE` | empty (1272) | empty | yes |
| 17–20 | `TEXTURECENTERX`, `TEXTURECENTERY`, `TEXTURESIZEX`, `TEXTURESIZEY` | `0mil` (1225 to 1265); else within 0.0004 mil of 0 | `0mil` | yes |
| 21 | `TEXTUREROTATION` | a real in the form ` 0.00000000000000E+0000` (a leading space, 14 decimals, a four-digit exponent); 0, 45, 90, 180, 270 and 360; equal to the component's rotation in 796 of 1272, so no rule is known | the form with the value 0 (115 records hold it), Fenolite's choice | choice |
| 22 | `MODELID` | a GUID in braces; 77 values for 1272 bodies; none is an entry of `Models` | **a stand-in**: a GUID derived from the body's id | **no** |
| 23 | `MODEL.CHECKSUM` | an unsigned 32-bit decimal; one value per `MODELID` (77); not a function of the body: 24 of the 53 distinct (box, heights) shapes hold more than one checksum, and 17 checksums more than one shape; 0 never occurs | **a stand-in**: `0` | **no** |
| 24 | `MODEL.EMBED` | `FALSE` (1272) | `FALSE` | yes |
| 25 | `MODEL.NAME` | empty (1272) | empty | yes |
| 26, 27 | `MODEL.2D.X`, `MODEL.2D.Y` | mil text; with `MODEL.2D.ROTATION=0.000` (1266) exactly the centre of the outline's bounding box, a half unit rounded towards zero (675 bodies hold a half; 698 of 698 half values round down); the 6 others hold `360.000` and differ | the centre of the bounding box, rounded towards zero | yes |
| 28 | `MODEL.2D.ROTATION` | `0.000` (1266), `360.000` (6) | `0.000` | yes |
| 29–31 | `MODEL.3D.ROTX`, `ROTY`, `ROTZ` | `0.000` (1272) | `0.000` | yes |
| 32 | `MODEL.3D.DZ` | `0mil` (1272) | `0mil` | yes |
| 33 | `MODEL.MODELTYPE` | `0` (1272) | `0` | yes |
| 34 | `MODEL.EXTRUDED.MINZ` | equal to `STANDOFFHEIGHT` (1272 of 1272) | the standoff | yes |
| 35 | `MODEL.EXTRUDED.MAXZ` | equal to `OVERALLHEIGHT` (1272 of 1272) | the height | yes |
| — | `MODEL.SNAPCOUNT` (2 records, `0`), `BODYOVERRIDECOLOR` (3 records, `TRUE`) | optional | not written | — |
| — | outline | whole units, absolute in the document; the first vertex not repeated | the model's outline, placed, in whole units | yes |

The key order is the same in 1267 records; the five others hold one of the two optional keys. So 33 of the 35 keys have a value rule (two of them a stated choice of Fenolite among values that occur), and two have none.

**Libraries.** One body in the four libraries, in one footprint beside 2 pads and 21 tracks: a model body (`MODEL.MODELTYPE=1`, embedded), one primitive of type 12 with one subrecord, the same 18 bytes with the component index `0xFFFF`, 34 keys in the document's order, plain vertices in whole units. No extruded body of a library was read.

**KiCad's importer on the seven documents that are not heavy** (`kicad-cli` 10.0.6, macOS, `pcb import --format altium`, counts of the written board): the footprints that hold a `(model …)` are exactly the components with a model body (245, 40, 45, 3, 23, 27 and 6), and no component whose bodies are all extruded has one (1, 5, 10 and 6 such components). KiCad shows nothing for an extruded body.

**Read today in public pages** (facts in Fenolite's words): a body has an identifier, a board side and a mechanical layer; an extruded body has an overall height and a standoff height, both from the board surface, and a negative standoff is for a body that passes through the board; when a component is flipped its body moves to the paired mechanical layer and its board side follows; bodies are what the component clearance check measures (S-0303, read again; the page on extruded, spherical and cylindrical bodies, S-0570). The format page of a third-party writer of PCB libraries (the page of S-0173, read again as S-0571; GPL, facts only, no code read) reports three things about its own writer: its extruded bodies hold no model key at all and end at `TEXTUREROTATION`; a checksum of 0 is accepted in a record of the `Models` storage; and a body whose outline has fractional units is dropped silently. The page does not say that its bodies were opened in Altium Designer, so the three are reports, not verified facts.

## What follows from the measurement

- **An extruded body can be written from the model.** Outline, heights, side, layer, identifier and component link are all there, and 31 keys are constants or copies of them.
- **Two keys cannot.** `MODELID` and `MODEL.CHECKSUM` are an identity that the body carries from where it was made; the corpus shows that the checksum does not follow from the outline and the heights. Whatever Fenolite writes there is a stand-in, and only Altium can say whether it matters. This is the one real unknown of the change, and it is why the option is off by default. For a body that was read, change c0129 replaces the stand-ins by the values of the document.
- **A model body cannot be written.** Its `MODELID` must name a record and a stream of `Models` with the model's data, and its checksum is that data's; the design model carries a model name and no data ("No model data is carried"), and embedding third-party STEP files is a licence question of its own. 391 of the 446 bodies of the seven documents are of this kind, so a rewrite of those documents stays without most of its bodies; the heavy document is the other way round (1217 of 1298 are extruded).
- **KiCad is no oracle for the body.** It can only show that the document with bodies is still read and that nothing else moved.
- **The library side is thin**: one record, of the kind that is not written.

## Decisions

1. **Scope: extruded bodies with an outline and a height.** Written: a `ComponentBody` with `kind == "extruded"`, an outline of at least three points and `height > standoff`. Not written, each with its reason in `altium.not-lowered` (`body/<id>`): kind `model` ("a body that names a 3D model needs the model's data, which the model does not hold"); an empty or shorter outline ("the body has no outline"); a height not above the standoff; a body whose projection is unknown (decision 9); every body when the option is `off` ("component bodies are not written without --altium-bodies extruded").
2. **No invented body.** A footprint without a body gets none, and nothing is reported for it: there is no item. No body is derived from a courtyard, a fabrication outline or a pad box, and no height is assumed, because the model states neither a height nor that the courtyard is the body. A script cannot state a height today; that is the DSL's gap, written under "Out of scope".
3. **The model gains nothing.** `ComponentBody` holds every value the record needs. c0126, the last model change of v0.3, covers footprint graphics and is not touched.
4. **Fact rows first, and the rule.** Tasks 1.1 to 1.3 write the rows, the sources and the corpus test before `pcbrecords.body_record` exists. `pcbrecords.BODY_KEYS` (the keys in order) is compared with the rows of the page by a unit test: a key without a row fails the test, and so does a row marked "stand-in" without a hypothesis of the register. A stand-in row is allowed only while the option is off by default.
5. **Layer.** The layer byte is the Altium id of `ComponentBody.layer` when the layer map of the document gives it a mechanical layer 1 to 16 (ids 57 to 72: `F.Fab` and `B.Fab` are 69 and 70 in `pcbrecords.BOARD_LAYER_MAP`, and an imported body names its layer by the byte, so a body on a layer above 16 comes back on 72). Any other layer, and an empty one, gives Mechanical 13 for a body of a top footprint and Mechanical 14 for a bottom one: Fenolite's choice, the pair of `FLIP_PAIRS`, which 777 of the 1272 extruded bodies follow. `V7_LAYER` is the text of the byte. A layer above 16 is not written by name: the reader's own row says that the byte cannot hold it.
6. **Frame and units.** The outline is the body's outline placed by the footprint's position, rotation and side, in the frame of the document (`pcbdoc.Frame`), converted with `pcbrecords.to_units`, so every vertex is a whole unit; equal neighbours and a repeated last point are dropped, and a body that keeps fewer than three vertices is reported as without outline. Heights are `mil_text(to_units(nm))`. `MODEL.2D.X/Y` is the centre of the bounding box of the written vertices in mil text, a half unit rounded towards zero.
7. **Both storages.** Each written body is one record of `ComponentBodies6` (plain vertices) and one of `ShapeBasedComponentBodies6` (37-byte vertices, none round, the first repeated) at the same index, with the same text; each `Header` is the count. Bodies are written in the order of the components and, within a component, of `bodies`. No entry of `UniqueIDPrimitiveInformation`, `Models` or `Textures` is written for a body.
8. **The record form and its stand-ins.** The writer has two forms. `saved` (the default of the option): the 35 keys of the table in their order, with `MODELID` a GUID in braces derived from the body's id by a hash, so that a build is repeatable (`pcbrecords.body_model_id`) and `MODEL.CHECKSUM=0`. `short`: the first 21 keys, ending at `TEXTUREROTATION`, the form that S-0571 reports of its writer. `short` is reachable from `pcbrecords.body_record(form="short")` and from the test that builds the files of step X8; no command line option selects it. Reason for `saved` as the default: it is the shape that every one of the 1748 saved records has, Fenolite's reader and the import read it without a special case, and the two stand-ins are the smallest departure from it; `short` departs in fourteen keys and rests on one report.
9. **Beside c0099, and independent of it** (edited on 2026-10-07). This change writes a body from `standoff` and `height` as `dev` holds them, and names no field of c0099 (`codex/c0099-body-volumes`; "What c0099 specifies" below). The proposal of 2026-10-06 held a second case here, for a branch that already had c0099: a body with `projection_unknown` not written, and `z_min` and `z_max` written as the standoff and the overall height. That case is removed: c0099 belongs to the milestone after this one and lands after the `0.3.0` release, so code of this change that read its fields would read fields that `dev` does not have. Teaching the body writer about `z_min`, `z_max` and `projection_unknown` is a follow-up by the owner of the writer after c0099 is on `dev` (change c0129 if it fits there), with its own requirement and test; c0099 itself keeps `height` and `standoff` filled from the source, so that the writer's output for a body that was read does not change when it lands.
   This change edits none of c0099's files (`adapter/bodies.py`, `adapter/board.py`, `adapter/codes.py`, `model/board.py`, `model/design.py`, `analysis/body_volumes.py`, the schemas). Both append to `docs/formats/altium/pcb-bodies.md`, `docs/hypotheses.md`, `docs/evidence/sources.md`, `docs/altium.md` and `CHANGELOG.md`.
10. **Opt-in.** `--altium-bodies off|extruded` on `fenolite build --target altium`, `bodies="off"` on `lens.altium.build`, `lens.altium.write_model`, `lower.from_design`/`write_design` and `AltiumBackend.model_roundtrip`. With `off` nothing of this change runs and every output is the bytes of today. The value is recorded in the build summary (`result.pcb.bodies`), so RT-A2 knows whether to compare bodies.
11. **Accounting.** `result.pcb.written.body` counts the bodies written and `not_lowered.body` the others, as "Written items are accounted" of c0085 defines the two; the sum is the number of bodies of the board's footprints. No new issue code: `altium.not-lowered` (info) with `where` `body/<id>`. The key order of `result.pcb` gains `bodies` last (asserted in `tests/unit/cli/test_build_altium.py`).
12. **Library footprints.** `pcblib` writes each written-kind body of `FootprintDef.bodies` as a primitive of type 12 in the footprint's stream, in the library frame, with the component index `0xFFFF`, the plain vertices and `BODYPROJECTION=0`, counted in the stream's header; under the same option. `lower.from_design` gives the definition it synthesises from a footprint instance no body: its footprints are per instance and the document carries the bodies.
13. **Read-back and round trips.** `BODY_SCOPE` is `kind`, `height`, `standoff`, `outline`, `layer` and `name` of a body, within 2 nm; the outline is compared as a ring from its smallest point (the adapter keeps the order). With bodies written, RT-A2 and RT-A3 compare the kind `body` for the bodies that were written; `rta3.without_unwritten` takes out the others by the ids that `not_lowered` names, as for every kind. With bodies off, both levels are what they are today and the page keeps its numbers. The corpus test adds one run with bodies on and prints, per document: bodies written, bodies not written by reason, and whether the document is still equal inside the scope. Expected from the measurement, to be confirmed by the run: 55 of 446 written on the seven documents (2, 0, 5, 30, 0, 0, 18) and 1217 of 1298 on the heavy one.
14. **KiCad.** One probe, `altium-pcbx-bodies`: `kicad-cli pcb import` reads `body2.PcbDoc`; levels 1 to 4 of `equivalent` hold against the same design built with bodies off (the sample holds no copper, so there is no level 5; "Found on 2026-10-07", 11); no footprint of KiCad's board holds a model. Outcome `equal` (the two imports are equal). It is recorded for 10.0.6; the importer of 9.0.9 has no `pcb import`.
15. **The sample.** `tests/data/altium/body2/`: the design of `tests/_altium_body2.py`, authored as a model as `board6` is, two copper layers, at least three footprints, one of them on the bottom side, with four bodies: a rectangle of 2.5 mm on a top footprint, a rectangle of 1 mm on the bottom footprint, a six-point outline of 4 mm with a standoff of 0.5 mm and the name `STANDOFF`, and one body of kind `model`, which is reported. Built with `--altium-bodies extruded`. `board6` and the four older samples are not rebuilt: **no committed file changes its bytes**. Reason for a sample of its own: Part X of `board6` is not reported yet, and a body that Altium refused would make its step X1 fail and hide ten other answers.
16. **Cut order.** First the library bodies (decision 12), then the `short` form and its second file set, then the corpus run with bodies on. Never the fact rows, the corpus test of the rows, the record in the document, the accounting and step X8's first file set.

## What c0099 specifies (read on 2026-10-06 from `codex/c0099-body-volumes`, commit `4f72c5a6`)

Information only: nothing in this change depends on c0099 (decision 9, as edited on 2026-10-07).

The hand-over `docs/board-authoring-gaps.md` of `codex/board-authoring-gaps` names c0099 and its branch; the change folder `openspec/changes/c0099-component-body-volumes/` is on that branch, based on `dev`. Nothing of it is reused here; it is summarised so that the two changes do not overlap.

- **It does not add `adapter/bodies.py`.** The file exists since c0043 and is in this change's base; c0099 edits it (every body is kept; `component_body` gains `mounted_side` and no longer returns `None`).
- **Model** (`design-model`, MODIFIED "Component bodies"): `ComponentBody.z_min`, `z_max` (optional, signed, from the mounted face outwards) and `projection_unknown`; the new error `model.body-volume`; `model.body-height` kept for a body without bounds.
- **Import** (`altium-import`, MODIFIED "Component body records"): no body is dropped; the new warning `altium.import.body-unknown`; a body whose `BODYPROJECTION` is not the side of its component, whose model type is neither 0 nor 1, or whose height is below its standoff is kept with `projection_unknown`. Nothing new goes into `ext`.
- **Analysis** (new capability `component-body-volumes`): "Signed body volume contract", "Native body projection and unknown geometry", "Board and opposite-face volume analysis", "Body projection diagnostics and evidence"; `analysis/body_volumes.py`.
- **Registers:** two hypothesis rows of its own, one of the import family about signed body heights and one general row about body volumes (their ids are not cited here, because they are not in this branch's register); sources numbered S-0452 and S-0453 on its branch. **S-0452 is taken on this branch** by another page (the multi-channel pages of c0083), so c0099 needs new numbers when it is integrated; its S-0452 is the page this change registers as S-0570; whichever of the two changes lands second uses the other's id for the page (task 1.1).
- **Non-goal of c0099:** "Native writer changes"; its page says "the existing native writer does not write bodies". That is the ground of this change.
- **One sentence of c0099 this change must not break:** "Native records MUST remain available to the native writer". The reader's `BodyRecord.raw` stays as it is; this change writes from the model and does not read a record back into a writer; keeping a read body's identity is change c0129 ("Decisions (2026-10-06)", 7).

## Found on 2026-10-07 (implementation)

What the code, the data and the tests showed against the text of 2026-10-06. Each item is corrected in the spec deltas, in this file or in the tasks, in the same commit.

1. **The measurement was repeated and holds.** Every number of "Measured" was measured again on 2026-10-07 with Fenolite's own readers, over the eight PCB documents and the four libraries, the heavy document included (one run with `FENOLITE_HEAVY=1`), and is pinned in `tests/corpus/test_altium_bodies.py` (13 tests). No number of the field table differs. Two statements of "Measured" are corrected:
   - "the component index … never `0xFFFF` in a document" holds for the 1272 extruded bodies only: 4 of the 85 bodies of the heavy document that name a model hold `0xFFFF` (they are the 4 that the import does not map: 1298 of its 1302 bodies are in the model).
   - `MODEL.NAME` is a file name and `MODEL.EMBED` is `TRUE` in all 476 bodies that name a model, not only in the 391 of the seven smaller documents.
   Measured in addition, and now a fact row: the text of a body has no leading bar, no line end and one closing NUL (1748 of 1748); in the one saved library with a body the body is the last primitive, the stream's header counts it, and the footprint's list of unique ids names its two pads and not the body.
2. **The base texts of the three MODIFIED requirements** (task 0.1; `openspec list` on 2026-10-07: c0085, c0090, c0127 and c0128 are on `dev` and not archived; c0043 is archived).
   - "Imported boards are written from the model": the text is no longer c0090's. c0127 and then c0128 modified it; the delta here now starts from **c0128's** text, the last of them (it holds c0127's arc clause and scenarios and c0128's `rewrite` clause and scenario), with this change's three edits: the signature gains `bodies="off"`, the footprint clause says that the definition holds no body, and the list of what is left out names the bodies that are not written. One sentence was added to the `rewrite` clause: bodies are written by `bodies` alone, in a rewrite as in any other write. c0126 (proposed, not implemented) modifies the same requirement from c0090's text: whichever of the two is archived second copies the other's text.
   - "Component bodies are reported": c0085's delta (the requirement is not in the living spec).
   - "RT-A2 on a written model": c0090's delta; no later change touches it.
3. **The clauses of c0099 were still in the delta.** Decision 9 was edited on 2026-10-07, but "Component bodies are reported" still named `projection_unknown`, `z_min` and `z_max`. They are removed: `body_problem` reads `kind`, `outline`, `height` and `standoff` and no other field, and a written body holds `standoff` and `height`.
4. **`result.pcb` was not in the result of the command.** Change c0085 specified it and `docs/cli-contract.md` describes it, but `cmd_build` never copied it from the library's build summary: `fenolite build --target altium --json` had no key `pcb`. The requirement of this change (`result.pcb.bodies`) needs it, so the result now holds `pcb` after `copper` (`null` without a PCB document). **This is a change of the result of every Altium build**, with or without the option; no file of a build changes. The pinned key order of `tests/unit/cli/test_build_altium.py` gains `pcb`. Accepted by the coordinator on 2026-10-07: it repairs c0085 to its own spec; the changelog says it in bold and `docs/cli-contract.md` says since when the command returns the key.
5. **A body is placed with its component, without a mirror.** The text said "placed by the footprint's position, rotation and side". A footprint instance of the model holds its pads as seen from the top, also on the bottom side (the import frames them with `Transform.placement(position, rotation)`, no mirror; `lower._library_pad` undoes that for the pad writer), and it holds its bodies the same way. So the outline is placed by the position and the rotation that the document gives the footprint's component, without a mirror, and the side only chooses `BODYPROJECTION` and the default layer. In a build the placement is that of the placed component, which is the instance's unless a copper source moved it: the body stays with its component.
6. **Reasons added.** A standoff below the board surface has no record (no saved extruded body holds one; `body_record` refuses it). A height is compared with the standoff in the units of the record, so two heights within one unit are "not above". A body whose placed outline keeps fewer than three vertices in whole units has no outline. A body whose footprint is no component of the written document ("its footprint is not written": a footprint that was refused, or a free pad) is reported; `pcbdoc.place_body` and the lowering decide the last two, not `body_problem`.
7. **Names.** The build's function is `lens.altium.build_altium`, not `lens.altium.build`. `body_problem` and its two reason texts live in `pcblib` (the library writer needs them, and `pcbdoc` imports `pcblib`); `pcbdoc` gives them out again. New beside the planned API: `pcbrecords.body_layer` (the layer rule), `pcbdoc.place_body`, `pcbdoc.body_vertices`, `pcbdoc.body_records`, `pcbdoc.BODY_MODES` and `body_mode`, `PcbDocSpec.body_form`, `pcblib.library_body_vertices`, `lens.altium_copper.lower_bodies`, `AltiumInputs.bodies` and `AltiumInputs.body_reasons` (reason → count, for the corpus table).
8. **Where the comparison of bodies lives.** `roundtrip.py` may import readers and neutral types only (`tests/unit/backends/altium/test_roundtrip.py` guards it), so it holds `BODY_SCOPE` and `EVIDENCE_BODIES`, and the comparison is the new module `backends/altium/bodydiff.py` (`body_changes`, `body_view`, `body_count`; evidence declared by "see roundtrip"). The model difference of `checks.diff` knows no kind `body` and is not changed.
9. **How RT-A2 knows that bodies were written.** The text said "its summary holds `pcb.bodies == "extruded"`", but the check reads the stored model of a build and no summary. `lower.stored_board` now gives each stored footprint exactly the bodies that were written for its component (none without the option, as before: the stored model of a build without the option is byte for byte what it was), and the stage compares bodies when the stored board holds one. The pipeline asks the backend through a new protocol of `backends/base.py`, `BodyComparer` (`body_differences(model, reading)` gives the changes and their evidence); `checks.rta2.rta2_stage` takes them as `bodies=`. No stage name, no issue code and no key of `stage_evidence()` is added.
10. **The library.** The body is the last primitive of the footprint's stream and is counted in its header, as measured; it gets **no** entry in the footprint's list of unique ids (Fenolite lists every other primitive there). `check_footprint(..., bodies=…)` counts the bodies that are not written in its notes, so a definition with a body that is built without the option gains the words "1 component body" in its `altium.footprint-extras-dropped` info; no definition read from a KiCad library holds a body.
11. **The KiCad probe.** `body2` holds no copper, so `equivalent` has no level 5 to run: the probe compares the two imports at levels 1 to 4. It also compares the two KiCad boards as text. KiCad draws the ids of the imported items at random and orders the footprints by them, so the order of the blocks changes from run to run: the lines are compared as a multiset, without the ids. The probe is `equal` on `kicad-cli` 10.0.6 (macOS, 2026-10-07; the one oracle file was run three times). The test of c0085 that lists the `altium-pcbx-*` probes now names this one too.
12. **The explain entry.** `altium.not-lowered` did not say that no body is written, so nothing was to reword; one clause about `body/<id>` and the option was added, inside the 400 characters the table allows.
13. **A waiver of the residue scan.** `body2.PcbLib` holds the view window that `libboard.py` writes into every PCB library (two nine-digit numbers), as `blink.PcbLib`, `routed.PcbLib` and `board6.PcbLib` do; it has the same waiver in `tools/residue/scope.toml`, per file, whose text names the numbers (approved by the coordinator on 2026-10-07).
14. **The corpus run with bodies.** On the seven documents that are not heavy the trip with `bodies="extruded"` is equal and writes 2, 0, 5, 30, 0, 0 and 18 bodies (55 of 446), as decision 13 expected; the 391 others name a model. The heavy document was run in the slot for the long runs on the same day: equal, 1217 bodies written and 81 not (each names a model), as pinned; over the eight documents 1272 of 1744 bodies are written.

## Files and public API

- `src/fenolite/backends/altium/pcbrecords.py`: `BODY = 12`, `BODY_KEYS`, `BODY_COLOR`, `body_record(layer, vertices, *, component, standoff, overall, bottom, identifier="", model_id="", shape_based=False, form="saved") -> bytes`, `body_model_id(body_id) -> str`.
- `src/fenolite/backends/altium/pcbdoc.py`: `PlacedBody` (the body with its component index and placed vertices), `PcbDocSpec.bodies`, `body_problem(body) -> str | None`, the two storages leave `EMPTY_STORAGES` when the spec holds a body.
- `src/fenolite/backends/altium/pcblib.py`: `LibFootprint.bodies`; the type 12 primitive.
- `src/fenolite/backends/altium/lower.py`, `src/fenolite/lens/altium_copper.py`, `src/fenolite/lens/altium.py`, `src/fenolite/cli/cmd_build.py`: the option and the accounting.
- `src/fenolite/backends/altium/roundtrip.py`, `rta3.py`: `BODY_SCOPE`; the kind `body` when bodies were written. `src/fenolite/backends/altium/bodydiff.py` (new): the comparison ("Found on 2026-10-07", 8). `src/fenolite/backends/base.py`: `BodyComparer`; `src/fenolite/checks/rta2.py` and `documents.py`: the bodies in RT-A2.
- Tests: `tests/corpus/test_altium_bodies.py`; `tests/unit/backends/altium/test_pcb_bodies.py`, `test_pcblib_bodies.py`; `tests/unit/lens/test_altium_bodies.py`; `tests/kicad/altium/test_pcb_bodies_oracle.py` with `tests/_bodycases.py`; `tests/_altium_body2.py`; `tests/data/altium/body2/`.
- Pages: `docs/formats/altium/pcb-bodies.md`, `docs/altium.md`, `docs/cli-contract.md`, `docs/evidence/altium-pcb.md`, `docs/evidence/altium-roundtrip.md`.

## Sources registered by this change

Block reserved for this change: S-0570 to S-0579.

- S-0570 (new): Altium's documentation page "Working with Extruded, Spherical & Cylindrical 3D Bodies" (all rights reserved, read for facts on 2026-10-06): the properties of an extruded body, the negative standoff, the paired mechanical layer on a flip. c0099 registers the same page under a number of its own; c0121 keeps S-0570 for it, unless c0099 is on `dev` first: then the implementer cites c0099's id for the page and S-0570 stays unused.
- S-0571 (new): the format page of S-0173 at the same commit, read again on 2026-10-06 for its section on component bodies (GPL-3.0, facts only, no source code read): the three reports named under "Measured".
- Registered and used: S-0303 (the 3D body object), S-0160 and S-0161 (the framing rows of c0043, as they stand; not read again), S-0020 (`kicad-cli` as an oracle), the corpus rows S-0170 to S-0176, S-0187, S-0188, S-0199 and S-0200.
- KiCad's Altium importer is not read for this change.

Sources under a copyleft or an all-rights-reserved licence are read for facts only; nothing is transcribed.

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-A-PCBX-BODY-FORM | A saved extruded body has the binary fields, the key order, the constants and the links between keys that "Written form of an extruded body" states, and a twin record with the same text | `tests/corpus/test_altium_bodies.py -k form` | every extruded body of every cached row holds every row marked "every record"; the rows come from at least three repositories; each row with exceptions holds within its stated count |
| H-A-PCBX-BODY-2D | `MODEL.2D.X/Y` of an extruded body with `MODEL.2D.ROTATION=0.000` is the centre of its outline's bounding box, a half unit rounded towards zero | `tests/corpus/test_altium_bodies.py -k centre` | exact on every such body |
| H-A-PCBX-BODY-READBACK | A body written by `body_record` reads back through the import to the model's body inside `BODY_SCOPE` within 2 nm | `tests/unit/lens/test_altium_bodies.py -k readback` | equal for `body2`, top and bottom, at 0, 90 and 30 degrees |
| H-A-PCBX-BODY-OPEN | Altium opens a document whose extruded bodies are in the saved form with a derived `MODELID` and `MODEL.CHECKSUM=0`, without a message, and shows each body with its heights, side and layer | author report, step X8, file set `saved` | the three bodies read as the table |
| H-A-PCBX-BODY-SHORT | The same for the short form, which holds no model key | author report, step X8, file set `short` | the three bodies read as the table |
| H-A-PCBX-BODY-ID | After Altium saves the document, the bodies keep their `MODELID`, and the report of the saved file says what `MODEL.CHECKSUM` holds | author report, step X8.6 (counts printed by Fenolite from the saved file; the file is not committed) | the counts are recorded; the row is a measurement, not a pass or fail |
| H-A-PCBX-BODY-LIB | Altium opens a PCB library whose footprint holds an extruded body written in the document's form with the component index `0xFFFF` | author report, step X8.7 | the body is listed in the footprint with its heights |
| H-A-PCBX-BODY-KICAD | `kicad-cli pcb import` reads a document with written bodies as it reads the same document without them, and shows no model for an extruded body | `tests/kicad/altium/test_pcb_bodies_oracle.py` | probe `altium-pcbx-bodies` `equal` |

All start `INFERRED`. The id of the body row that the design of c0085 reserved (the stem `H-A-PCBX-` with `BODY`, archived with c0085 on 2026-10-09) was never registered and stays unused: its statement is split over `-OPEN` and `-SHORT`. No id above is in `docs/hypotheses.md` or in another active change (checked 2026-10-06). The pattern `ALTIUM_HYPOTHESES` of `tests/unit/test_format_facts.py` accepts the stem `H-A-PCBX-`.

## Author report: Part X, step X8 (component bodies)

Step X8 of Part X of `docs/evidence/altium-pcb.md` was reserved for bodies and says "Not run". This change replaces that line by the steps below and keeps the number. The step, with both forms, belongs to **session 2** of the maintainer's Altium work: session 1 is the folder he already has (`~/fenolite-altium-checks/session-1/`), and nothing is added to it. Files: built by `FENOLITE_ALTIUM_BODY2=<folder> uv run pytest tests/unit/lens/test_altium_bodies.py -k golden` into `~/fenolite-altium-checks/session-2/X8-bodies/saved/` and `…/short/` (never into the repository), with their SHA-256 beside the steps and this table:

| body | footprint | side | layer | overall height | standoff | outline |
|---|---|---|---|---|---|---|
| 1 | a top footprint | Top | Mechanical 13 | 2.5 mm | 0 mm | a rectangle |
| 2 | the bottom footprint | Bottom | Mechanical 14 | 1 mm | 0 mm | a rectangle |
| 3 `STANDOFF` | a top footprint | Top | Mechanical 13 | 4 mm | 0.5 mm | six points |

1. **X8.1** Open `saved/body2.PrjPcb` and `body2.PcbDoc`. Expected: no repair prompt and no message in the Messages panel (`H-A-PCBX-BODY-OPEN`).
2. **X8.2** Open the PCB panel in the mode "3D Models" (or select each body in 2D). Expected: three bodies, each owned by the footprint of the table.
3. **X8.3** Read in the properties of each body: identifier, board side, layer, overall height, standoff height. Expected: the table.
4. **X8.4** Switch to the 3D view. Expected: three solids at the heights of the table, body 2 below the board.
5. **X8.5** Repeat X8.1 to X8.4 with the folder `short/` (`H-A-PCBX-BODY-SHORT`).
6. **X8.6** Save `saved/body2.PcbDoc` under another name outside the repository and run `FENOLITE_ALTIUM_BODY2_SAVED=<that file> uv run pytest tests/unit/lens/test_altium_bodies.py -k saved_report -s`. It prints counts only: the bodies per storage, how many keep the `MODELID` that was written, how many hold a `MODEL.CHECKSUM` other than 0, and the number of keys per body (`H-A-PCBX-BODY-ID`).
7. **X8.7** Open `saved/body2.PcbLib`, select the footprint with body 1 and read the body's heights (`H-A-PCBX-BODY-LIB`). Left out when the library bodies were cut.

The maintainer reports one generic outcome per step (`as expected`, or what differed in one sentence), the tool as `AD <major>.<minor>` and the date. No file that Altium wrote is committed. A step that fails refutes the row it names: the row keeps its id and gets a registered successor. An author report never moves an operation out of `experimental`. What the report decides: with X8.1 to X8.4 as expected, `saved` stays the form and the default of the option may become `extruded` (a one-line change with its changelog line, outside this change); with only X8.5 as expected, the form becomes `short` ("Decisions (2026-10-06)", 3, "to switch"); with neither, the option stays off and the report's sentence is the next fact row.

## Size (design-days)

| group | dd |
|---|---|
| entry, fact rows, sources, registers, the corpus test of the rows | 1 |
| the record and the two storages of the document | 0.75 |
| option, accounting, the build and the model writer | 0.75 |
| library bodies | 0.5 |
| sample, read-back, RT-A2 and RT-A3 with bodies | 0.75 |
| KiCad probe | 0.25 |
| step X8: files, protocol, pages | 0.5 |
| closing | 0.25 |

Total: 4.75. This is a size, not a calendar estimate.

## Spec deltas and archive order

- `altium-pcb-writer`: "Component bodies are reported" is not in the living spec; it is ADDED by c0085, which is not archived. Its MODIFIED text here is the whole text of c0085's delta with this change's edit. "Imported boards are written from the model" is ADDED by c0090, not archived, and MODIFIED since by c0127 and c0128: its MODIFIED text here is the whole text of **c0128's** delta, the last of them, with this change's edits ("Found on 2026-10-07", 2). The proposal of 2026-10-06 started from c0090's text with one clause changed ("a component body" becomes "a component body that "Component bodies are reported" does not write"). The sibling c0128 (vias with a drill equal to the diameter in a rewrite) may edit the via clause of the same requirement: the two edits touch different clauses, and the one archived second copies the other's text.
- `altium-verification`: "RT-A2 on a written model" is MODIFIED by c0090 (not archived); the text here is c0090's with one bullet added.
- `altium-build`: one ADDED requirement. "Complete board in an Altium build" of c0085 already names bodies and is not changed.
- No delta for `design-model`, `altium-import` or `altium-pcb-reader`.
- Archive order: after c0085 and c0090. Independent of c0099.

## Out of scope, with the reason

- **A height in a script.** `part.body(height=…)` or catalog heights would give DSL designs a body, with the courtyard box or a stated outline. It needs no model change (the entity exists), but it is a DSL decision with its own questions (which outline, which side of a flipped part, catalog data with sources), not a correction. After v0.3.
- **Model bodies with embedded STEP data.** Needs model data in the design model or beside it, the `Models` record and stream form (213 records read: nine keys; the stream's encoding was not looked at), the checksum of the data, and a licence rule for third-party models.
- **Replaying the identity of a body that was read:** change c0129, right after c0099 is on `dev` ("Decisions (2026-10-06)", 7).
- **Cylinders, spheres, arcs in outlines, textures, snap points.**
- **Reading `ShapeBasedComponentBodies6` in the import.** The twin holds the arcs of the one shape-based body; the import reads the plain storage.

## Risks / Trade-offs

- [Altium refuses a body with stand-in identity keys, or the whole document] → the option is off by default; step X8 runs on a sample of its own with a second form; a rollback is the option's default.
- [The constants come mostly from one repository (1265 of 1272 records)] → the seven records of the two other repositories hold the same constants; the page states the split; the label is the lowest of its rows.
- [`BODYCOLOR3D` and `TEXTUREROTATION` are choices] → both are values that saved records hold; the rows say "choice".
- [A body on a layer above Mechanical 16 comes back on Mechanical 16] → it does so in the import already; the write keeps the byte, so the round trip is equal.
- [The rewrite of the public documents still lacks 391 of 446 bodies] → stated in the proposal and counted by reason; it is the model-body limit, not a defect.

## Migration Plan

- None for callers: without the option every output is unchanged, byte for byte (a regression test over the committed samples and over `board6`).
- Rollback: the option's value `off`.

## Decisions (2026-10-06)

The coordinator accepted the defaults below on the maintainer's behalf on 2026-10-06, as the conservative reading of his order "a follow-up change with fact rows before the write"; they are to be shown to him, and each keeps what switching it would cost.

1. **Inside v0.3.** c0121 is implemented inside v0.3, opt-in and `experimental`, before c0092. The corpus gives enough for the record's shape and too little for two keys, and that gap is closed by Altium, not by more corpus. Not taken: the writer after v0.3 with only groups 0 and 1 (rows, sources, corpus test) inside it. To switch: tasks 2.1 to 5.2 move to a later change unchanged, and the requirements other than "Body facts before body code" move with them.
2. **The option is off until step X8 is reported.** Not taken: `extruded` at once, as every item of c0085 was written before Part X. To switch: the default in `cmd_build.py` and in the model writer, the scenario "Without the option", the RT-A3 numbers of the evidence page, and `body2` only.
3. **The saved form of 35 keys with the two stand-ins is what is written; the short form is built for step X8 only.** To switch to `short`: the default of `form` in `body_record`, the row labels of keys 22 to 35 ("not written"), the committed `body2.PcbDoc`.
4. **A body that names a 3D model is never written by this change.** No alternative that the facts support.
5. **No body is invented where the model has none.** A way to state a height in a script is a later change of the DSL (see "Out of scope").
6. **Library bodies are written, and are the first item of the cut order.** Not taken: a library without bodies until an extruded library body was read from a public file.
7. **Keeping `MODELID` and `MODEL.CHECKSUM` of a body that was read is change c0129**, a small change of its own, scheduled right after c0099 is on `dev`. It keeps the two values as bag keys of the import and writes them back in a rewrite, so that the 1272 extruded bodies of the corpus are rewritten with the values Altium wrote and not with stand-ins: it is what makes a rewrite carry real values. It is not part of c0121 because it edits `adapter/bodies.py`, which c0099 edits. Until c0129, every written body holds the stand-ins.
8. **The sample is the new `body2`;** `board6` and the four older samples keep every byte. Not taken: two bodies in `board6`, as c0085 first planned, which would change `board6.PcbDoc`, `board6.PcbLib` and the digests of Part X.

## Open decisions for the maintainer

None is open: the eight questions of this change are answered under "Decisions (2026-10-06)", by the coordinator on the maintainer's behalf, and wait for his review. A decision he reverses is switched as its entry says.
