## Context

- **Need.** The maintainer routes a 4-layer board through Fenolite and opens it in Altium Designer 26.5.
  Power and critical copper is described by script; a router plugin routes the rest.
- **Today.** c0035's `pcbdoc.write_pcbdoc` writes the outline, a 2-layer stack, components, pads, nets
  and designators. Altium Designer 26.5 opens that document (author report of 2026-10-03). `Vias6`,
  `Polygons6`, `Classes6` and `Rules6` are written empty, and `Tracks6`/`Arcs6` hold footprint graphics
  only. `lens.altium` reports net classes as "kept in the model only".
- **Base.** This change builds on c0035's second revision (`docboard.py`, the 42 storages), which is on
  the c0035 branch and reaches `main` when that branch merges.
- **Model.** `model.board` already has `Track`, `Arc`, `Via` (`layers`, `via_type`), `Zone` (`outline`,
  `layers`, `net_id`, `priority`, `fills`), `Layer` and `Stackup`; `model.circuit` has `NetClass`
  (clearance, track width, via diameter and drill) and `Net.netclass_id`.
- **DSL.** `design.board(width, height, copper=2)` accepts 2 or 4 (`dsl/design.py`). `to_model` does
  not carry the count; `cli/cmd_build.py` passes it to the KiCad build only.
- **Research of 2026-10-03** (public sources only; notes outside the repository, to be recorded in
  `docs/formats/altium/pcb-copper.md` by task 1.2):
  - Four Altium-saved documents (S-0172, S-0174, S-0175, S-0176) hold 2 439 tracks of 49 bytes, 162
    arcs of 60 bytes and 390 vias of 321 or 351 bytes. AltiumSharp version 1 writes a via of 209 bytes
    (S-0150); KiCad reads from 31 bytes (S-0160).
  - A polygon pour is a property record with the keys of the board outline that c0035 already writes,
    plus a net, a name and a pour index. Its poured copper is stored apart, in `Regions6` and
    `ShapeBasedRegions6`.
  - **The outline alone is a state Altium saves.** One polygon of S-0176 has no poured primitive. Altium
    documents the unpoured state and the repour commands (S-0195, S-0196).
  - S-0176 is a 4-layer board with two internal planes: its stack lists grow from 9 to 13 entries, and
    the numbered layers are linked through `PREV` and `NEXT`. No board with signal mid layers was read.
  - Net classes are `KIND=0` records with members `M0`, `M1`, …. A rule is a 16-bit kind number and a
    property record. Altium saves 15 to 20 classes and about 40 rules; c0035 writes none of either,
    and the document opens.
  - Blind, buried and micro vias need via types and drill pairs in the stack (S-0197).
- **Oracle probe of 2026-10-03.** A document authored for the probe, with tracks on four layers, an
  arc, vias and two polygons, was imported by `kicad-cli` 10.0.6 and read with
  `fenolite.backends.kicad.pcb.read_board`: layers, nets, widths and coordinates matched to the
  nanometre; the polygons came back as unfilled zones; vias of 31, 74, 209 and 321 bytes were all
  read. Net classes and rules gave no error, but `pcb import` writes no project file, so they cannot
  be compared.

## Goals / Non-Goals

**Goals**
- Write what the model holds: tracks, arcs, through vias, zones as unpoured polygons, a 2- or 4-layer
  signal stack, net classes, and three kinds of rules.
- Refuse, with a named issue, everything that cannot be written exactly.
- Check the copper with the `kicad-cli` oracle, and give the maintainer a routed sample early.

**Non-Goals**
- A source of copper (c0028, c0016, c0023), a reader of `.kicad_pcb` copper for the Altium build.
- Poured copper, hatched pours, zone settings (c0031), zone fill (c0015).
- Internal planes, split planes, blind, buried and micro vias, drill pairs past the first.
- Differential pairs, tear-drops, keep-outs, board texts, graphics and holes, other rule kinds.
- Stacks other than 2 or 4 copper layers; an Altium reader; any change to the KiCad target.

## Decisions

1. **This change only writes.** `build_altium` writes the copper found in `design.board`. It adds no
   copper source.
   - Route of script copper: c0028's intents resolve to model tracks and vias against KiCad
     footprints, in the frame of the placements. The Altium build resolves the same footprints and
     uses the same frame, so the resolved items can be handed to it unchanged.
   - Route of router results: c0016 and c0023 return model tracks and vias.
   - Order: c0038 does not depend on c0028. Its tests and its sample put copper into the model with
     `dataclasses.replace`. Until c0028 lands, a CLI build has no copper to write; the handing-over of
     intents to the Altium build is a small delta of c0028's implementation or of a follow-up (Open
     Question 1).
   - Rejected: an option that reads copper from a `.kicad_pcb`. It is useful, but it is a copper
     source with its own questions (which nets match, which frame), and it is not needed to prove the
     writer.
2. **No new DSL surface.** `design.board(w, h, copper=4)` exists. `build_altium` gains `copper=2`, and
   `cmd_build._run_altium` passes `run.design.copper`.
   - Rejected: carrying the count in `to_model` as `Board.layers`. The layer entities are created by
     the KiCad backend (`backends.kicad.layers.created_layers`) with KiCad extension data; `fenolite.dsl`
     may import only `model`.
   - When `design.board.layers` holds copper layers (a model built or read elsewhere), they win, and a
     count that differs from `copper` is `altium.copper-stack`.
3. **Inner layers are signal layers.** `In1.Cu` and `In2.Cu` map to Mid-Layer 1 and 2 (ids 2 and 3).
   - A power plane is a zone on an inner layer, written as a polygon pour.
   - Rejected: internal planes (ids 39 to 54). They are negative layers with their own connect and
     clearance rules and split-plane records; the model has no such notion, and KiCad's importer maps
     no plane, so no oracle could check them.
4. **Stack values.** `docboard.StackSpec` carries copper thicknesses and one dielectric between
   neighbours. The lens fills it from `Board.stackup` when the stack-up fits, else from
   `StackSpec.default`. For four layers the middle dielectric is the core and the outer two are
   prepregs (`DIELTYPE` 0 and 2).
   - Default values (0.2 mm prepreg, 1.0 mm core, `FR-4`, `4.800`, 1.4 mil copper) are Fenolite's
     choices, not values of any board.
   - The 2-layer default MUST give c0035's bytes, so no existing golden changes because of the stack.
   - The entries of a **signal** mid layer in the `V9` and `_V8` lists are inferred from the plane
     entries of S-0176 and from the top-layer entries (`H-A-PCB-CU-STACK`). Variant `c2` isolates the
     stack for the maintainer.
5. **Tracks and arcs keep the short forms** (36 and 47 bytes) through the existing
   `pcbrecords.track_record` and `arc_record`. Altium Designer 26.5 accepts them in c0035's document.
   - Rejected: the 49- and 60-byte forms. Their tails (mask expansions, a long layer id, a keep-out
     byte) come from one GPL page and add nothing the model holds.
6. **Vias use the 321-byte form Altium saves.** `pcbrecords.via_record` writes the fields of the fact
   page and zero elsewhere.
   - Why not the short form here: a via has no accepted short form yet, S-0173 reports that Altium
     misreads a via written in another layout, and all 390 vias read have 321 or 351 bytes.
   - Rejected: 209 bytes (version 1). It is a library writer's form that no report confirms in Altium.
   - The two 16-byte ids at 259 and 275 are zero; S-0173 reports zero ids in Altium-authored library
     vias. Vias are not listed in `UniqueIDPrimitiveInformation`: the saved documents list pads only.
7. **Through vias only.** A via must be `through` from the top to the bottom copper layer.
   - Rejected: writing a blind via with start and end layers. KiCad reads it, but Altium needs a via
     type and a second drill pair in the stack (S-0197), which no document read here holds.
8. **Zones are unpoured polygons.** One `Polygons6` record per zone layer, solid, with the outline, the
   net, a name and a pour index; no region.
   - Altium saves this state and documents it (S-0176, S-0195). The maintainer repours once.
   - Rejected: writing `Zone.fills` as regions. Regions need the `ShapeBasedRegions6` twin and a
     per-vertex double form; the fills are derived data that Altium recomputes with its own rules.
   - Pour settings are fixed (solid, remove dead copper, pour over same-net objects). c0031's
     `ZoneSettings` do not exist yet; mapping them is left to a later change.
   - Pour order: `POURINDEX` rises as `Zone.priority` falls. KiCad's importer inverts it the same way.
   - `Zone.priority` ties and names are resolved deterministically (zone id, stack position).
9. **Net classes.** One `KIND=0` class per `NetClass`, with its nets as members. Altium's super classes
   are not written: c0035 writes none and the document opens.
   - When the PCB document is planned, `altium.not-lowered` no longer reports net classes.
10. **Rules are the last group and the cut.** Clearance, Width and Routing Via Style, one rule per
    class value and one `All` rule per kind.
    - Writing them is cheap: a kind number and a property record. The unknown is Altium's reaction to
      three kinds without the other 36 (`H-A-PCB-CU-RULES`); variant `c5` isolates it.
    - Width and via limits span the written copper, so the document's own copper never breaks them.
    - `All` rules use Fenolite's defaults (0.2 mm, 0.25 mm, 0.6/0.3 mm), since the DSL has no default
      class.
    - Rules are written only when the document holds copper or a net class, so a design without
      either keeps c0035's bytes.
    - If the group is cut, or if Part C refutes it, `Rules6` stays empty and Altium applies its own
      defaults; the classes still carry the grouping.
11. **Errors, not drops.** Copper that cannot be written exactly gives an error and no file
    (`altium.copper-stack`, `-copper-layer`, `-via-unsupported`, `-zone-unsupported`, `-copper-invalid`).
    - Rejected: dropping the item with a warning. A missing via is an open circuit that the user would
      find only in Altium.
    - The lens checks before the writer; the writer's `ValueError`s are a second line.
12. **Oracle.** A new test imports the routed sample with `kicad-cli pcb import` and compares tracks,
    arcs, vias, zone outlines and the four copper layers with the model, through Fenolite's reader.
    It settles `H-A-PCB-CU-KICAD` only.
13. **Sample and variants.** The routed sample is the blink design with `copper=4` and authored copper
    (`tests/_altium_copper.py`). Six variants `c0` to `c5` add one feature each; they are written to a
    folder outside the repository for the maintainer, as c0035's variants were.
    - The blink golden document changes once: its class `PWR` and five rules are now written.
14. **MODIFIED deltas.** Two requirements of c0035 state the opposite of this change and are MODIFIED:
    `altium-pcb-writer` "PCB document file" (four storages are no longer always empty; routed records
    follow the component primitives; the 2-layer links are one case) and `altium-build` "PCB document
    output" (net classes are lowered). Everything else is ADDED. See "Spec deltas and archive order".
15. **Cut order** (sizes in design-days, total 7.75):
    1. Rules (group 7, −0.75).
    2. Stack values from `Board.stackup` (task 3.2, −0.25): defaults only.
    3. Net classes (group 5, −0.5); "PCB document output" then keeps c0035's text.
    - Not optional: tracks, arcs, vias, the four-layer stack, polygons and the oracle (minimum 6.25).

## Files and public API

| file | public API |
|---|---|
| `src/fenolite/backends/altium/pcbrecords.py` (extended) | `LAYER_MAP` with `In1.Cu`, `In2.Cu`; `COPPER_LAYER_TEXT`; `copper_stack(names) -> tuple[int, ...]`; `VIA = 3`, `VIA_SIZE = 321`; `via_record(x, y, diameter, hole, *, net=NO_INDEX) -> bytes` |
| `src/fenolite/backends/altium/libboard.py` (extended) | `stack_fields(used_layers, substack, stack=None)`, `legacy_lines(stack=None)`, `layer_sets(stack=None)`; dielectric and mid-layer entries |
| `src/fenolite/backends/altium/docboard.py` (extended) | `Dielectric(kind, thickness, epsilon_r, material)`; `StackSpec(copper, thicknesses, dielectrics)`, `StackSpec.default(copper)`; `board_records`, `board_fields`, `board_text(..., stack=None)`; `polygon_fields(layer_text, vertices, *, name, pour_index, net, auto_name)` shared with the outline |
| `src/fenolite/backends/altium/pcbdoc.py` (extended) | `COPPER_STORAGES`; `EMPTY_STORAGES` (21); `NetClassSpec(name, nets, clearance, track_width, via_diameter, via_drill)`; `PcbDocSpec.copper_layers`, `.stack`, `.tracks`, `.arcs`, `.vias`, `.zones`, `.net_classes` (defaults: two layers, no copper); `DEFAULT_CLEARANCE`, `DEFAULT_TRACK_WIDTH`, `DEFAULT_VIA_DIAMETER`, `DEFAULT_VIA_DRILL`; `polygon_name(text) -> str`; eight more ids in `EVIDENCE` |
| `src/fenolite/lens/altium.py` (extended) | `build_altium(..., copper=2)`; `pcb_document(..., copper=2)`; six codes in `ALTIUM_ISSUE_CODES`; summary `copper` |
| `src/fenolite/cli/cmd_build.py` (extended) | passes `run.design.copper`; `result.copper` |
| `tests/_altium_pcb_read.py` (extended, test code) | `ViaRecord`, `PolygonRecord`, `ClassRecord`, `RuleRecord`; `PcbDoc.vias`, `.polygons`, `.classes`, `.rules`, `.copper_chain` |
| `tests/_altium_copper.py` (new, test code) | `routed_model() -> Design`; `variants() -> dict[str, Design]` |
| `tests/unit/backends/altium/test_pcbrecords.py`, `test_docboard.py`, `test_libboard.py`, `test_pcbdoc.py`, `test_altium_pcb_read.py`; `tests/unit/lens/test_altium_pcb.py`, `test_altium_issues.py`, `test_altium_pcb_golden.py` (extended) | copper cases |
| `tests/unit/lens/test_altium_copper_golden.py` (new) | golden files, variants, protocol check |
| `tests/kicad/altium/test_pcbdoc_copper_oracle.py` (new) | the copper oracle |
| `tests/data/altium/routed/` (new, authored) | five files, in `MANIFEST.toml`; `tests/data/altium/blink/blink.PcbDoc` rebuilt |
| `docs/formats/altium/pcb-copper.md` (new), `pcb-document.md`, `docs/altium.md`, `docs/cli-contract.md`, `docs/evidence/altium-pcb.md` (Part C), `docs/hypotheses.md`, `docs/evidence/sources.md`, `src/fenolite/backends/altium/PROVENANCE.md`, `LEGAL-ANNEX.md` | facts, steps, rows |

`backends.altium` still imports only `core`, `model` and `geometry`; `lens` imports `model` and
`backends`. `tests/unit/test_import_graph.py` needs no `ALLOWED` change. `pyproject.toml` `dependencies`
stays empty.

## Sources registered by this change

| id | URL | licence | used for |
|---|---|---|---|
| S-0195 | https://www.altium.com/documentation/cstu/unpoured-polygon and https://techdocs.altium.com/display/ADRR1/PCB_Dlg-PolygonManagerForm((Polygon+Pour+Manager))_AD | Altium documentation, all rights reserved (read for facts) | an unpoured polygon is drawn by its outline only; the Unpoured Polygon rule; the repour commands |
| S-0196 | https://altium.com/documentation/node/312655/printable/print and https://altium.com/documentation/altium-designer/pcb-dlg-polygonmanagerformpolygon-pour-manager-ad?version=19 | Altium documentation, all rights reserved (read for facts) | fill modes and their primitives, pour-over choices, pour order, shelving, the connect-style rule |
| S-0197 | https://www.altium.com/documentation/altium-designer/pcb/blind-buried-micro-vias and https://altium.com/documentation/altium-designer/pcb-dlg-drillpairformdrill-pair-properties-ad | Altium documentation, all rights reserved (read for facts) | blind, buried and micro vias need via types and drill pairs |
| S-0198 | https://www.altium.com/documentation/cstu/layer-stack-manager | Altium documentation, all rights reserved (read for facts) | signal and plane layers of the layer stack |

Existing ids, whose "used for" cells task 1.1 widens:
- S-0160, S-0161 (KiCad's importer, GPL, facts only): via fields and length thresholds; polygon, class
  and rule keys; zones from polygons; layers Mid-Layer n to `In<n>.Cu`; planes not mapped.
- S-0150 (AltiumSharp **version 1 only**, commit `afe796434b6d2110c745c90abe44a6ddf64f5bca`,
  `PcbLibWriter.cs` and `PcbLibReader.cs`): the via field order to byte 208. Version 2 is not a source.
- S-0173 (GPL-3.0 format page, facts only, no source code): the 321- and 351-byte via and its field
  table; the 49- and 60-byte tails.
- S-0172, S-0174, S-0175, S-0176 (Altium-saved documents under Apache-2.0, BSD-2-Clause, MIT and
  Apache-2.0; scratch only, never committed): record lengths, polygon, class and rule keys, the
  unpoured polygon and the 4-layer stack of S-0176.
- S-0020, S-0166 (`kicad-cli`, a subprocess): the oracle.

S-0199 to S-0204 stay free. One of them is kept for a public Altium-saved board with **signal** mid
layers, if the maintainer approves the download (Open Question 2).

## Hypotheses registered by this change

| id | statement | test | criterion |
|---|---|---|---|
| `H-A-PCB-CU-KICAD` | `kicad-cli pcb import` reads the tracks, arcs, vias and zone outlines of the document on two and on four copper layers, with the model's nets and geometry | `tests/kicad/altium/test_pcbdoc_copper_oracle.py` in `kicad-10` | exit 0, no error; every item within 10 nm; four copper layers |
| `H-A-PCB-CU-TRACK` | Altium Designer shows free 36-byte tracks and 47-byte arcs with their nets, on outer and mid layers, and treats the routed nets as connected | Part C, step C1 | no prompt; no connection line on a routed net |
| `H-A-PCB-CU-VIA` | Altium Designer shows the 321-byte through vias with their diameter, hole and net | Part C, step C1 | three vias with the listed sizes and nets |
| `H-A-PCB-CU-STACK` | Altium Designer shows a stack of four signal layers, with Mid-Layer 1 and 2 written by analogy with the top layer, and three dielectrics | Part C, step C2 | four signal layers in the Layer Stack Manager; no repair |
| `H-A-PCB-CU-REPOUR` | Polygons written without regions open as unpoured outlines, and "Repour All" fills them on their net | Part C, step C3 | two outlines; after the repour, copper on `In1.Cu` and `B.Cu` connected to `GND` |
| `H-A-PCB-CU-CLASS` | Altium Designer lists a `KIND=0` class with its member nets when no super class is written | Part C, step C4 | `PWR` with `GND` and `VIN` |
| `H-A-PCB-CU-RULES` | Altium Designer accepts a `Rules6` of Clearance, Width and Routing Via Style rules only, and shows them | Part C, step C4 | five rules in the rules editor; the design rule check runs |
| `H-A-PCB-CU-VIEWER` | The Altium 365 Viewer renders the copper on four layers | Part C, step C5 | tracks, vias and four layers visible |

`H-A-PCB-CU-KICAD` starts at `INFERRED` and becomes `ORACLE-VERIFIED(kicad-cli)` when task 6.1 passes
on 10.0.6. The other seven start at `INFERRED` with the result `pending (author report)`. No id
collides with `docs/hypotheses.md` or an active change (checked 2026-10-03).

## Evidence level per behaviour (before merge)

| behaviour | level | basis |
|---|---|---|
| Layer map, record bytes, polygon keys, class and rule keys, determinism | Fenolite's own rules | unit tests; the independent reader `tests/_altium_pcb_read.py` |
| Tracks, arcs, vias, zone outlines and four copper layers as KiCad reads them | `ORACLE-VERIFIED(kicad-cli)` (10.0.x), `H-A-PCB-CU-KICAD` | the copper oracle; says nothing about Altium |
| Tracks, arcs and vias in Altium | `INFERRED`, then author report | Part C, C1 |
| Four-layer stack in Altium | `INFERRED`, then author report | Part C, C2 |
| Unpoured polygons and the repour | `INFERRED` (S-0176, S-0195), then author report | Part C, C3 |
| Net classes and rules | `INFERRED`; no oracle | Part C, C4 |
| Viewer | `INFERRED`, then `A365 Viewer` author report | Part C, C5 |
| Altium build envelope | `INFERRED`, experimental | an author report never promotes an operation |

## Size (design-days)

| group | tasks | dd |
|---|---|---|
| 1. sources, hypotheses, fact page | 1.1 0.25, 1.2 0.5 | 0.75 |
| 2. tracks, arcs, vias, lens, first sample | 2.1 0.25, 2.2 0.5, 2.3 0.5, 2.4 0.25, 2.5 0.25 | 1.75 |
| 3. four-layer stack | 3.1 0.75, 3.2 0.25, 3.3 0.25 | 1.25 |
| 4. polygons | 4.1 0.5, 4.2 0.25 | 0.75 |
| 5. net classes | 5.1 0.5 | 0.5 |
| 6. oracle, golden files, Part C | 6.1 0.5, 6.2 0.5 | 1.0 |
| 7. rules (cut first) | 7.1 0.5, 7.2 0.25 | 0.75 |
| 8. documentation and the maintainer's report | 8.1 0.25, 8.2 0.25 | 0.5 |
| 9. closing | 9.1 0.25, 9.2 0.15, 9.3 0.1 | 0.5 |
| **total** | | **7.75** |

This is a size, not a calendar estimate. c0035's PCB document was 3.5 design-days for the whole file;
this change adds five record kinds and a stack to it. A refuted hypothesis in Part C adds a fix of
about 0.5 each (c0035 needed two such rounds).

## Spec deltas and archive order

**Archive order: c0032 → c0033 → c0034 → c0035 → c0036 → c0037 → c0038.** No Altium capability is in
`openspec/specs/` yet. `openspec archive` applies a MODIFIED delta only to a requirement that exists,
so c0035 must be archived before this change.

| capability | requirement | delta | base text |
|---|---|---|---|
| `altium-pcb-writer` | Copper layer map; Four-layer stack; Routed track and arc records; Via records; Polygon pour records; Net class records; Design rule records; Copper records read back; Copper oracle | ADDED (9) | — |
| `altium-pcb-writer` | PCB document file | MODIFIED | c0035's ADDED text in its second revision of 2026-10-03 ("the document in the form Altium saves", on the c0035 branch), copied in full |
| `altium-build` | Copper in an Altium build; Copper issue codes; Copper evidence; Routed sample and author report; Copper is documented | ADDED (5) | — |
| `altium-build` | PCB document output | MODIFIED | c0035's ADDED text, copied in full |

- Edits to "PCB document file": the four copper storages leave `EMPTY_STORAGES` (25 → 21) and hold
  records; `board_text` takes `stack`; the 2-layer links and the count of 2231 fields are stated for two
  copper layers; `Tracks6` and `Arcs6` also hold routed records; the sample scenario names the class.
- Edits to "PCB document output": net classes are no longer reported by `altium.not-lowered` when the
  document is planned; keep-outs, board texts, graphics and holes are; the blink scenario expects no
  `altium.not-lowered`.
- **c0036** modifies `altium-build` "Altium symbol sources" and two `altium-schematic-writer`
  requirements; it does not touch the two requirements above.
- **c0037** (schematic hierarchy and harness, written in parallel) is expected to touch the schematic
  writer and, at most, `SOURCEHIERARCHICALPATH` in "PCB document links and nets". If it modifies "PCB
  document file" or "PCB document output", this change rebases its two texts onto c0037's.
- c0035's "PCB layer map", "PCB issue codes", "PCB evidence and capabilities", "PCB files read back",
  "PCB document oracle" and "PCB author reports" are extended by ADDED requirements, as c0035 extended
  c0032's; their texts stay true as written.
- No requirement name of this change exists in `openspec/specs/` or in an active change (c0020, c0021,
  c0028 to c0036; checked 2026-10-03).

## Risks / Trade-offs

- [Altium refuses the mid-layer stack entries, which are inferred] → variant `c2` isolates the stack;
  a public board with signal mid layers settles the rows (Open Question 2). The fix changes
  `libboard` only.
- [Altium wants regions for a polygon, or marks the polygon in a way not seen] → `H-A-PCB-CU-REPOUR`
  and variant `c3`. Fallback: write the zones as outlines on a mechanical layer and report them, or
  write regions in a follow-up.
- [Three rule kinds without the rest upset Altium] → rules are last, isolated in `c5`, and cut first.
- [The 321-byte via holds bytes whose meaning is unknown] → each fixed byte is a row of the fact page
  that states the rule seen in the saved documents; variant `c1` isolates vias.
- [KiCad accepts what Altium refuses] → KiCad levels never promote an Altium row (as in c0035).
- [The blink golden document changes] → the earlier author reports name the old SHA-256 and stay
  valid for the facts they settled; Part C names the new one.
- [Until c0028, no CLI build has copper] → stated in `docs/altium.md`; the sample is built by a test
  helper.
- [`COPPERORIENTATION` and the hole-shape pairs are not written] → c0035 writes neither and its
  document opens; they are listed under "Not written" in the fact page.

## Migration Plan

- A design without copper and without net classes gives the same `.PcbDoc` bytes as before.
- A design with a net class gets a new `<name>.PcbDoc` on its next build (the class and the rules).
  c0032's edited-output rule applies: a document edited in Altium is refused with `FEN-7001` unless
  `--discard-layout` is given.
- Rollback: revert the change; no stored file needs repair.

## Open Questions

1. Who hands c0028's resolved copper to the Altium build? Default: c0028's implementation adds one
   task and one requirement ("Copper intents in an Altium build") when it lands after this change;
   if c0028 lands first, a follow-up change does. This change needs neither.
2. May one public Altium-saved board with four **signal** layers be downloaded to scratch (licence,
   URL, commit and SHA-256 recorded as S-0199)? Default: yes, in task 1.2, if the maintainer approves;
   without it the stack rows stay inferred by analogy and rest on Part C alone.
3. Should the Altium build read copper from a routed `.kicad_pcb` of the same script
   (`--copper-from`)? Default: no, not in this change. It would give the maintainer a route before
   c0028, so it is the first candidate for a follow-up.
4. Should vias be tented (flag bits 5 and 6)? Default: no (`0C`), with a 4 mil solder-mask expansion
   as the saved documents show.
5. Which `All` rule defaults? Default: clearance 0.2 mm, width 0.25 mm, via 0.6/0.3 mm.
6. Should a zone with a net that has no pad be written? Default: yes; Altium removes dead copper.
7. Does the maintainer want `fills` written as regions later, so the board opens poured? Default: a
   follow-up after c0015, when fills exist in the model.
