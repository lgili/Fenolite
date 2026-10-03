## Context

- **Need.** The maintainer routes a 4-layer board through Fenolite and opens it in Altium Designer 26.5.
  Power and critical copper is described by script; a router plugin routes the rest.
- **Today.** c0035's `pcbdoc.write_pcbdoc` writes the outline, a 2-layer stack, components, pads, nets
  and designators. Altium Designer 26.5 opens that document (author report of 2026-10-03). `Vias6`,
  `Polygons6`, `Classes6` and `Rules6` are written empty, and `Tracks6`/`Arcs6` hold footprint graphics
  only. `lens.altium` reports net classes as "kept in the model only".
- **Model.** `model.board` already has `Track`, `Arc`, `Via` (`layers`, `via_type`), `Zone` (`outline`,
  `layers`, `net_id`, `priority`, `fills`), `Layer` (`kind` is `copper` for every copper layer) and
  `Stackup`; `model.circuit` has `NetClass` and `Net.netclass_id`.
- **DSL.** `design.board(width, height, copper=2)` accepts 2 or 4 (`dsl/design.py`). `to_model` does
  not carry the count: `cli/cmd_build.py` passes `design.copper` to the build.
- **KiCad reader.** `fenolite.backends.kicad.pcb.read_board` reads a `.kicad_pcb` into the model, with
  the `fenolite.path` property of each footprint. `lens` may import `backends`.
- **Maintainer's decisions of 2026-10-03** (this amendment):
  1. Public Altium-saved boards with signal mid layers may be downloaded to scratch.
  2. An inner layer can be a signal layer or an internal plane with a net. Split planes are out.
  3. Copper comes from the script (c0028, later) and from a routed KiCad board (`--copper-from`, now).
- **Research of 2026-10-03** (public sources only; notes outside the repository, to be recorded in
  `docs/formats/altium/pcb-copper.md` by task 1.2):
  - Six Altium-saved documents were read: S-0172, S-0174, S-0175 (two layers), S-0176 (signal, plane,
    plane, signal) and, after the approval, S-0199 and S-0200 (four **signal** layers; MIT).
  - Tracks have 49 bytes, arcs 60, vias 321 or 351 in all of them. AltiumSharp version 1 writes a via
    of 209 bytes (S-0150); KiCad reads from 31 bytes (S-0160).
  - A polygon pour is a property record with the keys of the board outline that c0035 writes, plus a
    net, a name and a pour index. Its poured copper is stored apart (`Regions6`). **The outline alone
    is a state Altium saves** (S-0176) and documents (S-0195, S-0196).
  - **Signal mid layers, observed.** S-0199 links 1 → 2 → 3 → 32. A mid layer's stack entry holds
    `NAME`, `LAYERID`, `USEDBYPRIMS`, `COPTHICK` and `COMPONENTPLACEMENT=1`. S-0200 links
    1 → 3 → 5 → 32 (Mid-Layer 2 and 4) and holds tracks with the layer bytes 3 and 5: the mid-layer
    number is free, and the position comes from the chain.
  - **Planes, observed.** S-0176 links 1 → 39 → 40 → 32. A plane's entry holds `COPTHICK` and
    `PULLBACKDISTANCE`; `PLANE<n>NETNAME` names its net. The saved plane also has one `Split Plane`
    polygon record and pull-back tracks on its layer, all derived from the outline.
  - Net classes are `KIND=0` records with members. A rule is a 16-bit kind number and a property
    record. c0035 writes none of either, and the document opens.
- **Oracle probes of 2026-10-03** (`kicad-cli` 10.0.6, documents authored for the probes):
  - Tracks on four layers, an arc, vias and two polygons came back to the nanometre.
  - KiCad maps the stack **by chain position**: a plane in the chain becomes a copper layer of type
    `power`, a mid layer one of type `signal`. This holds for the chains 1 → 39 → 40 → 32,
    1 → 39 → 3 → 32 and 1 → 2 → 39 → 32, without any split-plane record. It corrects the first
    research, which said KiCad maps no plane.
  - Net classes, rules and a plane's net are not in the imported board.

## Goals / Non-Goals

**Goals**
- Write tracks, arcs, through vias, zones as unpoured polygons, a 2- or 4-layer stack whose inner
  layers are signal layers or planes, net classes, and three kinds of rules.
- Take the copper from one of three sources through one interface: the model, the script's resolved
  copper, or a routed KiCad board.
- Refuse, with a located issue, everything that cannot be written exactly or does not match.
- Check with `kicad-cli`, and give the maintainer a routed sample early.

**Non-Goals**
- A router or a copper DSL (c0028, c0016, c0023); an Altium reader.
- Poured copper, hatched pours, zone settings (c0031), zone fill (c0015).
- Split planes, plane primitives, plane rules; blind, buried and micro vias; a second drill pair.
- Differential pairs, tear-drops, keep-outs, board texts, graphics and holes, other rule kinds.
- Stacks other than 2 or 4 copper layers; planes in the KiCad target.

## Decisions

1. **One interface, three sources.** `build_altium` writes copper from exactly one source.
   - **model**: `design.board` already holds copper (tests, and routers of c0016 and c0023).
   - **script** and **board**: `lens.altium.CopperSource(design, origin, where)`, a model with placed
     footprints and copper in the frame of the placements.
   - Both `CopperSource` origins run the same match checks and the same lowering. So the script
     route is tested now, with a KiCad-built model that stands for c0028's output.
   - Rejected: merging two sources. A board written by `fenolite build` already holds the script's
     copper, so a merge would write it twice.
   - Routed records are sorted by geometry and net, not by entity id. The three sources then give the
     same bytes for the same copper, which one test checks.
2. **Script copper: c0038 now, c0028 later.** c0038 does not depend on c0028 and does not change its
   text. See "Interface for c0028".
3. **`--copper-from` reads the board in-process** with `fenolite.backends.kicad.pcb.read_board`.
   - Rejected: `kicad-cli` to convert. The reader exists, and the build stays free of external tools.
   - The board must be of the same design. Checked: components (by `fenolite.path`, else by
     reference), footprint links and pad positions, pad nets, the outline's box, and the net names of
     the copper.
   - **The board's placements win.** Copper is only right relative to the footprints as the board
     places them. Parts are moved while routing, and the exported tool project is the source of truth
     for layout (`design-model`, "Layout authority"). A difference is reported once
     (`altium.placement-from-board`).
   - Rejected: requiring equal placements. It would refuse every board in which a part was nudged.
   - Rejected: keeping the script's placements and copying the copper anyway. Tracks would miss pads.
   - A mismatch is an error with a location, never a drop. A footprint that the design does not hold
     is a mismatch too (Open Question 2).
4. **Planes in the DSL: `design.board(w, h, copper=4, planes={"In1.Cu": gnd})`.**
   - A plane is a property of the stack, so it sits beside `copper`. The value is a `Net` or a name.
   - `dsl.planes(design)` returns the mapping; `cmd_build` passes it to the build, as it passes
     `design.copper`.
   - Rejected: a call `design.plane(layer, net)`. It splits one stack description over two calls.
   - Rejected: deriving a plane from a zone that covers the board on an inner layer. It guesses.
5. **The model does not change.** A plane layer stays a `Layer` of kind `copper`.
   - Rejected: a `LayerKind` `plane`. Every consumer that selects `kind == "copper"` (the KiCad
     writer, wildcard pads, the copper check of c0029) would have to learn it, the canonical schema
     would change, and KiCad has no such layer, so it would not round-trip.
   - Rejected: a net id on `Layer`. Layer entities are created by the KiCad backend; `to_model`
     creates none, and `fenolite.dsl` may import only `model`.
   - Consequence: a board read from a file has no plane. With `--copper-from`, planes come from the
     script, and the board's zone on that layer and net is left to the plane
     (`altium.plane-zone-merged`).
   - The KiCad target writes no plane: it reports `build.plane-not-lowered` (Open Question 1).
6. **Inner layers in Altium.** `In<n>.Cu` as a signal layer is Mid-Layer n (ids 2 and 3). Planes are
   numbered from the top: Internal Plane 1 (id 39), then 2 (id 40).
   - All four stacks are written: signal-signal (as S-0199), plane-plane (as S-0176), and the two
     mixed ones, composed from the two observed entry forms. S-0200 shows that Mid-Layer 2 without
     Mid-Layer 1 is a saved state.
   - A plane is its chain links, its stack entry and `PLANE<n>NETNAME`. The `Split Plane` record and
     the pull-back tracks that S-0176 also holds are derived data and are not written
     (`H-A-PCB-CU-PLANE`; variant `p0` isolates it).
   - Tracks, arcs and foreign-net zones on a plane are refused (`altium.plane-copper`): they would
     need split planes.
   - No Plane Connect or Plane Clearance rule is written; Altium's defaults apply.
7. **Stack values.** `docboard.StackSpec` carries copper thicknesses, one dielectric between
   neighbours and the plane nets. The lens fills it from `Board.stackup` when the stack-up fits, else
   from `StackSpec.default`.
   - Default values (0.2 mm prepreg, 1.0 mm core, `FR-4`, `4.800`, 1.4 mil copper) are Fenolite's
     choices, not values of any board.
   - Dielectrics are named and numbered from the top (`Dielectric 1` to `3`, as S-0199). `DIELTYPE`
     is 1 for a core and 2 for a prepreg (S-0199, S-0200). The 2-layer default keeps c0035's
     `DIELTYPE=0` and bytes, so no golden changes because of the stack.
   - A signal mid layer is written with `COMPONENTPLACEMENT=1`, as both boards save it.
   - The lists keep the overlay entries (13 entries, as S-0176), since c0035's 9-entry list has them
     and opens in Altium.
8. **Tracks and arcs keep the short forms** (36 and 47 bytes) through the existing
   `pcbrecords.track_record` and `arc_record`. Altium Designer 26.5 accepts them in c0035's document.
   - Rejected: the 49- and 60-byte forms. Their tails add nothing the model holds.
9. **Vias use the 321-byte form Altium saves.** `pcbrecords.via_record` writes the fields of the fact
   page and zero elsewhere.
   - Why not a short form: a via has no accepted short form yet, S-0173 reports that Altium misreads
     a via written in another layout, and every via read has 321 or 351 bytes.
   - Rejected: 209 bytes (version 1). No report confirms it in Altium.
   - The two 16-byte ids are zero. Vias are not listed in `UniqueIDPrimitiveInformation`.
10. **Through vias only.** A via must be `through` from the top to the bottom copper layer.
    - Rejected: a blind via with start and end layers. Altium needs a via type and a second drill
      pair in the stack (S-0197), which no document read here holds.
11. **Zones are unpoured polygons.** One `Polygons6` record per zone layer, solid, with the outline,
    the net, a name and a pour index; no region.
    - Altium saves this state and documents it (S-0176, S-0195). The maintainer repours once.
    - Rejected: writing `Zone.fills` as regions. They are derived data that Altium recomputes.
    - Pour settings are fixed. c0031's `ZoneSettings` do not exist yet.
    - `POURINDEX` rises as `Zone.priority` falls. Ties are resolved by net name and geometry.
12. **Net classes.** One `KIND=0` class per `NetClass`, with its nets as members. Altium's super
    classes are not written. Net classes always come from the script, never from a copper source.
13. **Rules are the last group and the cut.** Clearance, Width and Routing Via Style, one rule per
    class value and one `All` rule per kind.
    - The unknown is Altium's reaction to three kinds without the other 36 (`H-A-PCB-CU-RULES`);
      variant `c5` isolates it.
    - Width and via limits span the written copper, so the document's own copper never breaks them.
    - `All` rules use Fenolite's defaults (0.2 mm, 0.25 mm, 0.6/0.3 mm).
    - Rules are written only when the document holds copper or a net class.
14. **Errors, not drops.** Copper that cannot be written exactly gives an error and no file.
    - Rejected: dropping the item with a warning. A missing via is an open circuit.
    - The lens checks before the writer; the writer's `ValueError`s are a second line.
15. **Oracles.** Two tests in the `kicad-10` job.
    - The copper oracle imports the routed sample and the plane variant and compares copper and
      layer types with the model (`H-A-PCB-CU-KICAD`).
    - The round-trip oracle goes from a KiCad board through `--copper-from` and `kicad-cli pcb import`
      back to a KiCad board, and compares the two boards (`H-A-PCB-CU-ROUNDTRIP`).
    - Neither settles an Altium row.
16. **Sample and variants.** The routed sample is the blink design with `copper=4` and authored copper
    (`tests/_altium_copper.py`), available as a model, as a KiCad-built model and as a `.kicad_pcb`.
    Variants `c0` to `c5` add one feature each; `p0` has a ground plane. They are written to a folder
    outside the repository for the maintainer.
17. **MODIFIED deltas.** Three requirements are MODIFIED; everything else is ADDED. See "Spec deltas
    and archive order".
18. **Cut order** (sizes in design-days, total 11.0):
    1. Rules (group 9, −0.75).
    2. Stack values from `Board.stackup` (task 3.2, −0.25): defaults only.
    3. Net classes (group 7, −0.5); "PCB document output" then keeps c0035's text.
    - Not optional: tracks, arcs, vias, the stack with planes, polygons, both copper sources and the
      oracles (minimum 9.5).

## Interface for c0028

c0038 is implemented now. c0028 (`openspec/changes/c0028-board-frame-copper/`) lands later and hands
its copper over. This change does not edit c0028's files; it states what c0028's implementation adds.

- **What c0038 provides.** `build_altium(…, copper_source=CopperSource(design, "script"))`, under the
  requirement "Script copper in an Altium build", with its checks and tests.
- **What c0028 provides.** `lens.build.build_design(…, copper_intents=dsl.copper(design))`, whose
  `BuildOutput.design` holds the resolved tracks and vias ("Copper intents in a build").
- **The hand-over** (one task in c0028's implementation, about 0.25 design-day):
  - In `cmd_build._run_altium`, when the script has copper intents and `--copper-from` is absent,
    run `build_design` in memory for the KiCad target with the intents. Write none of its files.
  - If it reports an error (`kicad.copper.*`, `kicad.frame.*`), stop: the Altium build writes nothing.
  - Otherwise pass `CopperSource(built.design, "script")`.
  - With `--copper-from`, do not resolve the intents: the board wins, and c0028 reports that once.
- **Conditions the source model meets**, all true of c0028's output as specified:
  - copper layers named `F.Cu`, `In1.Cu`, `In2.Cu`, `B.Cu`;
  - points in the frame of `place()` (`BOARD_ORIGIN`);
  - through vias between the first and the last copper layer;
  - net ids that resolve to the script's net names;
  - footprints that carry the `fenolite.path` property.
- **`result.copper`.** For the Altium target it has this change's keys. c0028 uses the same key for
  the KiCad target with other fields (`intents`, `regenerated`, …); it may add `intents` here.
- **Order.** c0038 → c0028. If c0028 were implemented first, the hand-over task would move into this
  change with no other edit.

## Files and public API

| file | public API |
|---|---|
| `src/fenolite/backends/altium/pcbrecords.py` (extended) | `LAYER_MAP` with `In1.Cu`, `In2.Cu`; `COPPER_LAYER_TEXT`; `copper_stack(names, planes=()) -> tuple[int, ...]`; `VIA = 3`, `VIA_SIZE = 321`; `via_record(x, y, diameter, hole, *, net=NO_INDEX) -> bytes` |
| `src/fenolite/backends/altium/libboard.py` (extended) | `stack_fields(used_layers, substack, stack=None)`, `legacy_lines(stack=None)`, `layer_sets(stack=None)`; dielectric, mid-layer and plane entries |
| `src/fenolite/backends/altium/docboard.py` (extended) | `Dielectric(kind, thickness, epsilon_r, material)`; `StackSpec(copper, thicknesses, dielectrics, plane_nets=())`, `StackSpec.default(copper, plane_nets=())`; `board_records`, `board_fields`, `board_text(..., stack=None)`; `polygon_fields(layer_text, vertices, *, name, pour_index, net, auto_name)` shared with the outline |
| `src/fenolite/backends/altium/pcbdoc.py` (extended) | `COPPER_STORAGES`; `EMPTY_STORAGES` (21); `NetClassSpec(name, nets, clearance, track_width, via_diameter, via_drill)`; `PcbDocSpec.copper_layers`, `.stack`, `.tracks`, `.arcs`, `.vias`, `.zones`, `.net_classes` (defaults: two layers, no copper); `DEFAULT_CLEARANCE`, `DEFAULT_TRACK_WIDTH`, `DEFAULT_VIA_DIAMETER`, `DEFAULT_VIA_DRILL`; `polygon_name(text) -> str`; ten more ids in `EVIDENCE` |
| `src/fenolite/lens/altium.py` (extended) | `CopperSource(design, origin, where="")`; `build_altium(..., copper=2, planes=None, copper_source=None)`; `pcb_document(..., copper=2, planes=None, copper_source=None)`; `match_source(design, source, footprints) -> tuple[Mapping[str, PlacementRequest], list[Issue]]`; twelve codes in `ALTIUM_ISSUE_CODES`; summary `copper` |
| `src/fenolite/lens/build.py` (extended) | `plane_issues(planes) -> list[Issue]`; `build.plane-not-lowered` in `BUILD_ISSUE_CODES` |
| `src/fenolite/dsl/design.py`, `convert.py`, `__init__.py` (extended) | `Design.board(width, height, copper=2, planes=None)`; `Design.planes`; `planes(design) -> Mapping[str, str]` |
| `src/fenolite/cli/cmd_build.py` (extended) | `--copper-from FILE`; passes `design.copper`, `planes(design)` and the board source; `result.copper`; the board in `input` |
| `tests/_altium_pcb_read.py` (extended, test code) | `ViaRecord`, `PolygonRecord`, `ClassRecord`, `RuleRecord`; `PcbDoc.vias`, `.polygons`, `.classes`, `.rules`, `.copper_chain`, `.plane_nets` |
| `tests/_altium_copper.py` (new, test code) | `routed_model() -> Design`; `routed_kicad_design() -> Design`; `routed_board_text() -> str`; `routed_script() -> str`; `variants() -> dict[str, Design]` |
| `tests/unit/backends/altium/test_pcbrecords.py`, `test_docboard.py`, `test_libboard.py`, `test_pcbdoc.py`, `test_altium_pcb_read.py`; `tests/unit/lens/test_altium_pcb.py`, `test_altium_issues.py`, `test_altium_pcb_golden.py`; `tests/unit/dsl/test_structure.py`; `tests/unit/lens/test_build_issues.py` (extended) | copper, plane and source cases |
| `tests/unit/lens/test_altium_copper_golden.py`, `test_altium_copper_source.py`; `tests/unit/cli/test_build_copper_from.py` (new) | golden files, variants, protocol check; source matching; the CLI option |
| `tests/kicad/altium/test_pcbdoc_copper_oracle.py`, `test_copper_from_oracle.py` (new) | the two oracles |
| `tests/data/altium/routed/` (new, authored) | five files, in `MANIFEST.toml`; `tests/data/altium/blink/blink.PcbDoc` rebuilt |
| `docs/formats/altium/pcb-copper.md` (new), `pcb-document.md`, `docs/altium.md`, `docs/dsl.md`, `docs/cli-contract.md`, `docs/evidence/altium-pcb.md` (Part C), `docs/hypotheses.md`, `docs/evidence/sources.md`, `src/fenolite/backends/altium/PROVENANCE.md`, `LEGAL-ANNEX.md` | facts, steps, rows |

`backends.altium` still imports only `core`, `model` and `geometry`. `lens.altium` receives models and
never imports `fenolite.dsl`; `cli` reads the board with `backends.kicad`. `tests/unit/test_import_graph.py`
needs no `ALLOWED` change. `pyproject.toml` `dependencies` stays empty.

## Sources registered by this change

| id | URL | licence | used for |
|---|---|---|---|
| S-0195 | https://www.altium.com/documentation/cstu/unpoured-polygon and https://techdocs.altium.com/display/ADRR1/PCB_Dlg-PolygonManagerForm((Polygon+Pour+Manager))_AD | Altium documentation, all rights reserved (read for facts) | an unpoured polygon is drawn by its outline only; the Unpoured Polygon rule; the repour commands |
| S-0196 | https://altium.com/documentation/node/312655/printable/print and https://altium.com/documentation/altium-designer/pcb-dlg-polygonmanagerformpolygon-pour-manager-ad?version=19 | Altium documentation, all rights reserved (read for facts) | fill modes and their primitives, pour-over choices, pour order, shelving, the connect-style rule |
| S-0197 | https://www.altium.com/documentation/altium-designer/pcb/blind-buried-micro-vias and https://altium.com/documentation/altium-designer/pcb-dlg-drillpairformdrill-pair-properties-ad | Altium documentation, all rights reserved (read for facts) | blind, buried and micro vias need via types and drill pairs |
| S-0198 | https://www.altium.com/documentation/cstu/layer-stack-manager | Altium documentation, all rights reserved (read for facts) | signal and plane layers of the layer stack |
| S-0199 | https://github.com/luxonis/oak-hardware at commit `7d569e3ccdff30014a498dc6c64a2e0dcad6964c`, `NG6011_Dot_projector/PCB/NG6011.PcbDoc`; SHA-256 `bf32fd189e9850f2e9de397a567ba78934ad62e7b092184a3ad71227d5b8cf39`; downloaded 2026-10-03 | MIT (`LICENSE`, (c) 2020 luxonis); saved by Altium Designer; scratch only, never committed | a stack of four signal layers (Top, Mid-Layer 1, Mid-Layer 2, Bottom): the entries of a signal mid layer, dielectric names, ids and types, layer sets, polygons on `MID1` and `MID2` |
| S-0200 | same repository and commit, `DM6010_Y-adapter/PCB/DM6010_R2M2E2.PcbDoc`; SHA-256 `62e53020ef96657bc013334446579ed6db6e8d225c50026579af533a0b281f2d`; downloaded 2026-10-03 | MIT; saved by Altium Designer; scratch only, never committed | a stack with Mid-Layer 2 and 4: tracks on mid layers (layer byte, long layer id), free mid-layer numbers |

Existing ids, whose "used for" cells task 1.1 widens:
- S-0160, S-0161 (KiCad's importer, GPL, facts only): via fields and length thresholds; polygon, class
  and rule keys; zones from polygons; the stack read by chain position; planes as `power` layers.
- S-0150 (AltiumSharp **version 1 only**, commit `afe796434b6d2110c745c90abe44a6ddf64f5bca`,
  `PcbLibWriter.cs` and `PcbLibReader.cs`): the via field order to byte 208. Version 2 is not a source.
- S-0173 (GPL-3.0 format page, facts only, no source code): the 321- and 351-byte via and its field
  table; the 49- and 60-byte tails.
- S-0172, S-0174, S-0175, S-0176 (Altium-saved documents under Apache-2.0, BSD-2-Clause, MIT and
  Apache-2.0; scratch only, never committed): record lengths, polygon, class and rule keys, the
  unpoured polygon, and the two internal planes of S-0176 with `PLANE<n>NETNAME`.
- S-0020, S-0166 (`kicad-cli`, a subprocess): the oracles.

Download rules that were kept: a public repository of the GitHub organisation `luxonis` with an MIT
`LICENSE`; URL, commit, licence, date and SHA-256 recorded; files in scratch only; nothing decompiled,
no code read or transcribed. S-0201 to S-0204 stay free.

## Hypotheses registered by this change

| id | statement | test | criterion |
|---|---|---|---|
| `H-A-PCB-CU-KICAD` | `kicad-cli pcb import` reads the tracks, arcs, vias and zone outlines of the document on two and on four copper layers, with the model's nets and geometry, and reads a plane of the stack as a `power` layer at its position | `tests/kicad/altium/test_pcbdoc_copper_oracle.py` in `kicad-10` | exit 0, no error; every item within 10 nm; four copper layers with the expected types |
| `H-A-PCB-CU-ROUNDTRIP` | Copper copied from a KiCad board with `--copper-from` and imported back by `kicad-cli` equals the copper of the source board | `tests/kicad/altium/test_copper_from_oracle.py` in `kicad-10` | every track, arc, via and zone outline within 10 nm, none added, footprints at the source's placements |
| `H-A-PCB-CU-TRACK` | Altium Designer shows free 36-byte tracks and 47-byte arcs with their nets, on outer and mid layers, and treats the routed nets as connected | Part C, step C1 | no prompt; no connection line on a routed net |
| `H-A-PCB-CU-VIA` | Altium Designer shows the 321-byte through vias with their diameter, hole and net | Part C, step C1 | three vias with the listed sizes and nets |
| `H-A-PCB-CU-STACK` | Altium Designer shows a stack of four signal layers written in the form S-0199 saves (13 list entries, `COMPONENTPLACEMENT=1` on mid layers, three dielectrics) | Part C, step C2 | four signal layers in the Layer Stack Manager; no repair |
| `H-A-PCB-CU-PLANE` | Altium Designer shows an internal plane written as its stack entry and `PLANE<n>NETNAME` only, on its net, beside a signal mid layer, and connects the pads and vias of that net to it | Part C, step C6 | Internal Plane 1 on `GND` in the Layer Stack Manager; no connection line on `GND` |
| `H-A-PCB-CU-REPOUR` | Polygons written without regions open as unpoured outlines, and "Repour All" fills them on their net | Part C, step C3 | two outlines; after the repour, copper on `In1.Cu` and `B.Cu` connected to `GND` |
| `H-A-PCB-CU-CLASS` | Altium Designer lists a `KIND=0` class with its member nets when no super class is written | Part C, step C4 | `PWR` with `GND` and `VIN` |
| `H-A-PCB-CU-RULES` | Altium Designer accepts a `Rules6` of Clearance, Width and Routing Via Style rules only, and shows them | Part C, step C4 | five rules in the rules editor; the design rule check runs |
| `H-A-PCB-CU-VIEWER` | The Altium 365 Viewer renders the copper on four layers | Part C, step C5 | tracks, vias and four layers visible |

`H-A-PCB-CU-KICAD` and `H-A-PCB-CU-ROUNDTRIP` start at `INFERRED` and become
`ORACLE-VERIFIED(kicad-cli)` when tasks 8.1 and 8.2 pass on 10.0.6. The other eight start at `INFERRED`
with the result `pending (author report)`. No id collides with `docs/hypotheses.md` or an active change
(checked 2026-10-03).

## Evidence level per behaviour (before merge)

| behaviour | level | basis |
|---|---|---|
| Layer map, record bytes, polygon keys, class and rule keys, determinism, source matching | Fenolite's own rules | unit tests; the independent reader `tests/_altium_pcb_read.py` |
| Tracks, arcs, vias, zone outlines, four copper layers and their types as KiCad reads them | `ORACLE-VERIFIED(kicad-cli)` (10.0.x), `H-A-PCB-CU-KICAD` | the copper oracle; says nothing about Altium |
| Copper copied with `--copper-from` | `ORACLE-VERIFIED(kicad-cli)` (10.0.x), `H-A-PCB-CU-ROUNDTRIP` | the round-trip oracle |
| Tracks, arcs and vias in Altium | `INFERRED`, then author report | Part C, C1 |
| Stack of four signal layers in Altium | `INFERRED` (S-0199, S-0200), then author report | Part C, C2 |
| Internal plane and its net in Altium | `INFERRED` (S-0176); no oracle for the net | Part C, C6 |
| Unpoured polygons and the repour | `INFERRED` (S-0176, S-0195), then author report | Part C, C3 |
| Net classes and rules | `INFERRED`; no oracle | Part C, C4 |
| Viewer | `INFERRED`, then `A365 Viewer` author report | Part C, C5 |
| Altium build envelope | `INFERRED`, experimental | an author report never promotes an operation |

## Size (design-days)

| group | tasks | dd |
|---|---|---|
| 1. sources, hypotheses, fact page | 1.1 0.25, 1.2 0.5 | 0.75 |
| 2. tracks, arcs, vias, lens, first sample | 2.1 0.25, 2.2 0.5, 2.3 0.5, 2.4 0.25, 2.5 0.25 | 1.75 |
| 3. four-layer signal stack | 3.1 0.75, 3.2 0.25, 3.3 0.25 | 1.25 |
| 4. polygons | 4.1 0.5, 4.2 0.25 | 0.75 |
| 5. internal planes | 5.1 0.5, 5.2 0.5, 5.3 0.25 | 1.25 |
| 6. copper sources | 6.1 0.75, 6.2 0.5, 6.3 0.25 | 1.5 |
| 7. net classes | 7.1 0.5 | 0.5 |
| 8. oracles, golden files, Part C | 8.1 0.5, 8.2 0.25, 8.3 0.5 | 1.25 |
| 9. rules (cut first) | 9.1 0.5, 9.2 0.25 | 0.75 |
| 10. documentation and the maintainer's report | 10.1 0.5, 10.2 0.25 | 0.75 |
| 11. closing | 11.1 0.25, 11.2 0.15, 11.3 0.1 | 0.5 |
| **total** | | **11.0** |

This is a size, not a calendar estimate. The first proposal was 7.75. The amendment adds planes (1.25),
the two copper sources (1.5), the round-trip oracle (0.25) and documentation (0.25); the fact page
costs the same, since the mid-layer rows are now read from files instead of inferred. A refuted
hypothesis in Part C adds a fix of about 0.5 each (c0035 needed two such rounds).

## Spec deltas and archive order

**Archive order: c0032 → c0033 → c0034 → c0035 → c0036 → c0037 → c0038.** No Altium capability is in
`openspec/specs/` yet. `openspec archive` applies a MODIFIED delta only to a requirement that exists,
so c0035 must be archived before this change. c0028 is archived after it or before it: the two
changes modify no common requirement.

| capability | requirement | delta | base text |
|---|---|---|---|
| `altium-pcb-writer` | Copper layer map; Four-layer stack; Routed track and arc records; Via records; Polygon pour records; Net class records; Design rule records; Copper records read back; Copper oracle | ADDED (9) | — |
| `altium-pcb-writer` | PCB document file | MODIFIED | c0035's ADDED text in its second revision of 2026-10-03 ("the document in the form Altium saves"), copied in full |
| `altium-build` | Copper in an Altium build; Internal planes in an Altium build; Script copper in an Altium build; Copper from a routed KiCad board; Copper round trip oracle; Copper issue codes; Copper evidence; Routed sample and author report; Copper is documented | ADDED (9) | — |
| `altium-build` | PCB document output | MODIFIED | c0035's ADDED text, copied in full |
| `design-dsl` | Planes in a build | ADDED | — |
| `design-dsl` | Board and placements in the DSL | MODIFIED | the living text of `openspec/specs/design-dsl/spec.md`, copied in full |

- Edits to "PCB document file": the four copper storages leave `EMPTY_STORAGES` (25 → 21) and hold
  records; `board_text` takes `stack`; the 2-layer links and the count of 2231 fields are stated for two
  copper layers; `PLANE<n>NETNAME` may name a plane's net; `Tracks6` and `Arcs6` also hold routed
  records; the sample scenario names the class.
- Edits to "PCB document output": net classes are no longer reported by `altium.not-lowered` when the
  document is planned; keep-outs, board texts, graphics and holes are; with a copper source a
  component takes the source's placement; the blink scenario expects no `altium.not-lowered`.
- Edits to "Board and placements in the DSL": the `planes` argument, `Design.planes`, `planes(design)`
  and three scenarios. Its other bullets and scenarios are unchanged.
- **Who else touches these requirements** (checked 2026-10-03 against c0020, c0021, c0028 to c0037):
  - "Board and placements in the DSL": no active change modifies it. c0021 modifies `design-dsl`
    "Library resolution during build" and "Build command"; c0028, c0029, c0030, c0031, c0036 and
    c0037 only add `design-dsl` requirements. So this delta needs no order.
  - "Build command" and "Build issue codes" are extended by ADDED requirements ("Planes in a build",
    "Copper from a routed KiCad board"), as those requirements allow, so c0021's MODIFIED "Build
    command" does not collide.
  - "PCB document file" and "PCB document output": c0036 and c0037 do not modify them. c0037 modifies
    `altium-pcb-writer` "PCB document links and nets" and `altium-build` "Altium build outputs", and
    adds "Altium sheets option"; `--copper-from` and `--altium-sheets` are independent options.
- c0035's "PCB layer map", "PCB issue codes", "PCB evidence and capabilities", "PCB files read back",
  "PCB document oracle" and "PCB author reports", and c0032's "Altium build target", are extended by
  ADDED requirements; their texts stay true as written.
- No requirement name of this change exists in the same capability in `openspec/specs/` or in an
  active change. c0028 has "Copper issue codes" and "Copper evidence" in another capability
  (`manual-copper`), which does not collide.

## Risks / Trade-offs

- [Altium wants the `Split Plane` record or the pull-back tracks of a plane] → `H-A-PCB-CU-PLANE` and
  variant `p0`. Fallback: write the one record and the pull-back tracks as S-0176 holds them, from
  the outline (about 0.5), or tell the user to declare a zone on a signal layer instead.
- [A stack with one plane and one signal mid layer was not seen in a saved file] → both entry forms
  are observed, KiCad reads the composition, and `p0` is exactly this stack.
- [`COMPONENTPLACEMENT=1` on mid layers comes from two boards of one publisher] → it is what both
  hold; variant `c2` isolates the stack. The fix changes `libboard` only.
- [Altium wants regions for a polygon] → `H-A-PCB-CU-REPOUR` and variant `c3`. Fallback: regions in a
  follow-up.
- [Three rule kinds without the rest upset Altium] → rules are last, isolated in `c5`, and cut first.
- [The 321-byte via holds bytes whose meaning is unknown] → each fixed byte is a row of the fact page;
  variant `c1` isolates vias.
- [A board is refused because its footprints come from another library version] → the issue names
  the component and the pad; the user rebuilds the KiCad project from the script first.
- [The board's placements differ from the script's without the user noticing] → one
  `altium.placement-from-board` info names the refs, and `result.copper.placements_from_board` counts.
- [KiCad accepts what Altium refuses] → KiCad levels never promote an Altium row (as in c0035).
- [The blink golden document changes] → the earlier author reports name the old SHA-256 and stay
  valid for the facts they settled; Part C names the new one.
- [Until c0028, a script cannot describe copper] → `--copper-from` is the route; `docs/altium.md` says so.
- [`COPPERORIENTATION`, `DIELLOSSTANGENT` and the hole-shape pairs are not written] → c0035 writes none
  and its document opens; they are listed under "Not written" in the fact page.

## Migration Plan

- A design without copper, planes and net classes gives the same `.PcbDoc` bytes as before.
- A script without `planes` builds the same files for both targets.
- A design with a net class gets a new `<name>.PcbDoc` on its next build (the class and the rules).
  c0032's edited-output rule applies: a document edited in Altium is refused with `FEN-7001` unless
  `--discard-layout` is given.
- Rollback: revert the change; no stored file needs repair.

## Open Questions

1. Should the KiCad target write a plane as a zone over the outline on that layer? Default: no, it
   reports `build.plane-not-lowered`; a follow-up can lower it once c0031's zones exist.
2. Should `--copper-from` accept board footprints that the script does not hold (mounting holes,
   logos)? Default: no, a mismatch; the user adds the part to the script.
3. Should vias be tented (flag bits 5 and 6)? Default: no (`0C`), with a 4 mil solder-mask expansion
   as the saved documents show.
4. Which `All` rule defaults? Default: clearance 0.2 mm, width 0.25 mm, via 0.6/0.3 mm.
5. Should a zone with a net that has no pad be written? Default: yes; Altium removes dead copper.
6. Does the maintainer want `fills` written as regions later, so the board opens poured? Default: a
   follow-up after c0015, when fills exist in the model.
7. Should Plane Connect and Plane Clearance rules be written with the rules group? Default: no;
   Altium's defaults apply until Part C says otherwise.
