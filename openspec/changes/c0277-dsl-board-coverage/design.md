## Context

- **Source.** `docs/research/board-library.md`, sections 1 ("What the DSL cannot express yet") and 4.3
  (DSL coverage); table of section 5: c0277 has no dependency and is used by c0275 and c0278.
- **What exists on `dev` (0.6.0).**
  - `COPPER_COUNTS = (2, 4, 6, 8)` in `dsl/design.py`, equal to `layers.CREATED_COPPER_COUNTS`; inner rows
    `(2k + 2, "In<k>.Cu", signal)`. `H-K-PCB-LAYERS` records the probes for 2, 4, 6, 8 and the refused 3;
    its first, hand-made record also loaded every even table from 2 to 34 on 10.0.6 and 32 and 34 on
    9.0.9, and refused 3 and 5. The Altium writer already writes any even stack up to 32 with at most 16
    signal and 16 plane layers (`altium-pcb-writer`, "Layer stacks of any even count").
  - The drawing calls refuse copper layers (`dsl.items.DRAWING_LAYER_KINDS`). `Dimension.kind` is
    `aligned` or `orthogonal`; other dimension types, `group`, `image`, teardrop zones, pad `chamfer*`,
    `primitives`, footprint clearances and `model` stay opaque slots of the reader
    (`docs/formats/kicad/board.md`, "What the reader models").
  - Authored pads take `circle`, `rect`, `oval`, `roundrect` (`dsl/footprint.py`); the model `PadShape`
    already names `trapezoid` and `custom`, and `Pad.corner_ratio` is in parts per million.
  - `Zone.outline` holds points only; `Outline` already holds `arcs` (`OutlineArc`), and `board(outline=…)`
    takes `arc_to` steps through `shape.closed_ring`.
  - Opaque content keeps its place and is rewritten for nets per target (c0163), and `check_emittable`
    gates too-new tokens (`kicad-version-gating`, "Emit check").
- **Constraint.** "Byte-identical existing builds": every new model field defaults to empty and is left
  out of canonical JSON when empty; every new writer branch runs only for the new DSL calls.

## Goals / Non-Goals

**Goals**

- Each hole of research 4.3 has a DSL call, or the verbatim item covers it with a finding.
- Each written item is proved by KiCad on both majors (load, DRC, re-save) before merge.
- Every existing example and test board builds the same bytes.

**Non-Goals**

- See the proposal. In addition: the KiCad reader keeps modelling exactly what it models today. Promoting
  the new kinds from opaque slots to modelled content on read is a follow-up (open question 2); c0275's
  emitter reads those slots with its own small interpreters.

## Decisions

### 1. Copper counts

- `COPPER_COUNTS = CREATED_COPPER_COUNTS = (2, 4, …, 32)`, every even count. Inner rows keep the rule
  `(2k + 2, "In<k>.Cu", signal)`: `In30.Cu` is 62. The numbers of the 9.0 scheme give copper the even
  numbers and technical layers odd ones, so no row collides.
- `copper=1` is decided by a probe, `pcb-layers-1-t<M>` (a table holding `F.Cu` as its only copper row):
  - `load` on both majors (and on 10.0.6 a re-save that keeps it): `1` joins both tuples, its table is
    the two-copper table without `B.Cu`, and a copper item on `B.Cu` is `kicad.copper.bad-layer`;
  - otherwise `copper=1` raises `DslError` with the hint "a single-sided board is copper=2 with nothing
    on B.Cu", and the hypothesis records the refusal.
- Odd counts above 1 stay refused (KiCad refuses 3 and 5).
- **Consequences**, each with a task:
  - `stackup()`: one `stack.copper()` per layer, unchanged rule; no preset above six layers (no
    fabricator data is authored). KiCad's default stack-up for a board without one is probed for 10, 16
    and 32 (`pcb-stackup-default-<n>`).
  - `planes=`: any inner layer of the count.
  - Lens, copper guard, exports (one Gerber per copper layer, job file `LayerNumber`), blind and buried
    via spans and the Specctra hand-off take the table as they take eight layers today; the viewer gives
    every inner layer a colour (it cycles its inner palette).
  - Altium: the writer's limits stay; a script whose signal layers (copper minus declared planes) exceed
    16, or whose planes exceed 16, gives `altium.stack-signal-limit` (error, exit 5) with the hint to
    declare planes or build for KiCad, instead of the silent default stack of `altium.not-lowered`.
- *Alternative:* accept 34 because KiCad loads it. Rejected: 32 is the count KiCad's documentation and
  board setup offer; 34 loading is an implementation accident.

### 2. Copper text and graphics

```python
d.text("logo/txt", "REV B", (mm(5), mm(5)), layer="F.Cu", knockout=True)
d.polygon("logo/shape", LOGO_POINTS, layer="B.Cu", width=mm(0), fill=True)
d.polygon("heatspreader", SPREADER, layer="F.Cu", width=mm("0.2"), fill=True, net=gnd)
```

- `text`, `line`, `rect`, `circle`, `arc` and `polygon` accept copper layers of the board; `dimension`
  does not. Graphics take `net=None` (a `Net`, which joins the design); texts take `knockout=False`
  (copper and silkscreen layers only). `Graphic.net_id` and `Text.knockout` are new model fields,
  omitted when unset.
- The copper guard judges copper graphics with their geometry and net (a graphic without a net is
  copper of no net). Copper text has no outline in Fenolite (no font renderer): it is judged by KiCad's
  DRC only, and `copper.text-unchecked` (info) says so once per board.

### 3. Pads of authored footprints

```python
fp.pad("1", at=(mm(0), mm(0)), size=(mm(1), mm(2)), shape="trapezoid", delta=(mm("0.2"), mm(0)))
fp.pad("2", at=(mm(2), mm(0)), size=(mm(1), mm(1)), shape="rect", chamfer=250_000, corners=("top_left",))
fp.pad("3", at=(mm(4), mm(0)), size=(mm(1), mm(1)), shape="roundrect", radius_ratio=200_000)
fp.pad("4", at=(mm(6), mm(0)), size=(mm("0.5"), mm("0.5")), shape="custom", anchor="circle", primitives=TAB)
```

- `delta` (trapezoid), `chamfer` (ratio in parts per million, 0 to 500 000) with `corners` (a non-empty
  subset of `top_left`, `top_right`, `bottom_left`, `bottom_right`), `radius_ratio` (as `corner_ratio`),
  and `custom` with `anchor` (`circle` or `rect`) and `primitives`: a tuple of `footprint.poly(points,
  width=, fill=)`, `footprint.segment(a, b, width=)`, `footprint.circle(center, radius, width=, fill=)`
  and `footprint.arc(start, mid, end, width=)` in pad coordinates.
- Model: `Pad.trapezoid_delta`, `Pad.chamfer_ratio`, `Pad.chamfer_corners`, `Pad.anchor_shape` and
  `Pad.primitives` (a tuple of `PadPrimitive(kind, points, width, filled)`), all omitted when unset.
- Ratios are integers (no floats in the model). The writer prints the decimal the file format takes.

### 4. Teardrops

```python
d.teardrops(
    where=select.netclass("Signal"),
    max_length=mm(1),
    max_width=mm(2),
    length_ratio=500_000,
    width_ratio=1_000_000,
    curved=True,
    vias=True,
    pads=True,
)
```

- One call per selection; a pad or via matched by two calls takes the later call (reported
  `dsl.teardrops-overlap`, info). Every parameter left at `None` omits its token, so KiCad's own default
  applies; Fenolite authors no default value.
- Written as the teardrop settings node of each matching pad (inside the vendored footprint instance)
  and via, with the tokens of the KiCad file-format documentation (S-0001), recorded in
  `docs/formats/kicad/board.md` before the writer, `INFERRED` until `H-K-TEARDROP` settles them.
- Teardrop zones are not written: KiCad 10.0.6 removes them on re-save (`H-K-UUID-KEEP-2`) and regenerates
  them on fill, so `fenolite fill` makes them. The copper guard ignores teardrops; KiCad's DRC judges them.
- Model: `Pad.teardrop` and `Via.teardrop` (`Teardrop`, frozen), omitted when unset.

### 5. Groups

- `d.group(name, *members, locked=False)`: members are `Part` objects, and keys of copper intents, table
  rows' tables, zones, rule areas, drawings, images and other groups. A member in two groups, an unknown
  key or a cycle raises `DslError`. Model `Group(name, member_ids, locked)` in `Board.groups`, id
  `derived_id("grp", "dsl", "group:<name>")`; the KiCad uuid comes from the id.
- Altium has no group record in the writer: `altium.group-skipped` (warning) per group.

### 6. Images

- `d.image(key, file, at, *, layer="F.SilkS", scale="1")`: `file` is a PNG path relative to the script
  folder, read by the build (as `placements.toml` is), never by the DSL. A missing or non-PNG file is
  `build.image-missing` / `build.image-format` (error). `scale` is a decimal string (no floats).
- Model `Image(position, layer, scale, data)`, `data` the base64 text of the PNG bytes, in
  `Board.images`; `result.board_items.images` counts them, and the build's declared inputs gain the file.
- Altium: `altium.image-skipped` (warning).

### 7. Dimensions

| call | KiCad type | model fields |
|---|---|---|
| `radial_dimension(key, center, edge, *, leader_length, layer=…)` | `radial` | `start` = centre, `end` = edge point, `leader_length` |
| `leader(key, start, knee, *, text, frame="none", layer=…)` | `leader` | `start`, `end` = knee, `text`, `frame` (`none`, `rect`, `circle`) |
| `center_mark(key, center, edge, *, layer=…)` | `center` | `start`, `end` |

`DimensionKind` gains `radial`, `leader` and `center`; `Dimension.text`, `leader_length` and `frame` are
new fields, omitted when unset. Units, precision and text sizes follow the linear call.

### 8. Zone arcs

`zone(outline=…)` accepts `arc_to` steps as `board(outline=…)` does, through `closed_ring`; `Zone.arcs`
(`OutlineArc`) is new and omitted when empty. The KiCad writer emits the arc inside the polygon's
`pts`; the fill engine and the copper guard flatten arcs with the tolerance the board outline uses.
Altium: an arc edge is written as a region arc when the writer has one, else flattened with
`altium.zone-arc-flattened` (info).

### 9. Footprint-instance overrides

```python
u1.override(clearance=mm("0.15"), mask_margin=mm("0.05"), zone_connection="solid")
u1.edit_pad("EP", size=(mm("3.2"), mm("3.2")), paste_margin=mm("-0.1"))
u1.field("Reference", dx=mm(0), dy=mm(-3), size=mm(1), bold=True, face="KiCad Font")
```

- `override` takes `clearance`, `mask_margin`, `paste_margin`, `paste_ratio` (ppm), `zone_connection`,
  `thermal_gap` and `thermal_spoke_width`; model `FootprintInstance.overrides` (`FootprintOverrides`),
  omitted when unset; the writer emits the footprint-level tokens.
- `edit_pad(number, ...)` replaces fields of every pad of that number of this instance only: `at`,
  `size`, `shape`, `rotation`, `drill`, the pad shapes of decision 3, `mask_margin`, `paste_margin`.
  An unknown pad is `build.pad-unknown` (error). The library footprint is unchanged; the copper guard
  and the assignment check judge the edited pads.
- `Part.field` gains `bold`, `italic` and `face`; `FootprintField` gains the three, omitted when unset.

### 10. 3D model references

`part.model(name, *, offset=(0, 0, 0), rotation=(0, 0, 0), scale=("1", "1", "1"), hidden=False)`, called
once per model, replaces the footprint's model list for this instance. `name` is a reference only
(`${KICAD10_3DMODEL_DIR}/…`, `3dmodels/x.step`): nothing is read. Offsets are lengths, rotations
angles, scales decimal strings. Model `FootprintInstance.models` (`ModelRef`), omitted when empty.
`fenolite models --vendor` and STEP export resolve the names as today.

### 11. Verbatim items

```python
d.verbatim("art/barcode", '(barcode (at 120 80) (layer "F.SilkS") (text "SN-0001") (type qr))')
u1.verbatim("keepout", '(zone (net "") (layers "F.Cu") (keepout (tracks not_allowed)) ...)')
d.verbatim(
    "rule/hv",
    '(rule "hv" (constraint clearance (min 2mm)) (condition "A.NetClass == \'HV\'"))',
    target="kicad_dru",
)
```

- `target` is `kicad_pcb` (a board root child, default), `kicad_dru` (a rule of the rules file) or, for
  `part.verbatim`, the footprint node. The DSL checks only that `text` is a non-empty string and the key.
- The build parses it with the s-expression reader; a parse failure, a head that the DSL expresses or the
  header owns (`version`, `generator`, `generator_version`, `general`, `paper`, `layers`, `setup`,
  `net`, `footprint`; and `pad`, `property`, `at`, `layer` in a footprint), a layer not on the board, or a
  net name not in the design is an error (`build.verbatim-invalid`, `-head`, `-layer`, `-net`).
- Every `uuid` atom inside is replaced by `embed.placement_uuid(<key>, "/verbatim/<n>")`, so two builds
  agree and two items never share a uuid. Net nodes follow the opaque-content rewrite for the target.
  `check_emittable` gates the tokens (target 9 refuses a 10-only token with `FEN-7001` unless
  `--allow-lossy`).
- One `build.verbatim-item` (info) per item names the key and the head; `result.board_items.verbatim`
  counts them. Over an existing board, a node with a verbatim uuid is replaced by the script's, and one
  whose key left the script is removed, as script drawings are ("Board items declared in the script").
- Altium: `altium.verbatim-skipped` (warning) per item.
- *Alternative:* a generic `design.raw(sexpr_tree)`. Rejected: text is what the importer has, and it is
  diffable in review.

### 12. Codes

| code | severity | when |
|---|---|---|
| `copper.text-unchecked` | info | copper text exists; only KiCad's DRC judges it |
| `dsl.teardrops-overlap` | info | a pad or via matched by two `teardrops` calls |
| `build.image-missing`, `build.image-format` | error | image file absent or not PNG |
| `build.pad-unknown` | error | `edit_pad` names no pad of the footprint |
| `build.verbatim-item` | info | one per verbatim item |
| `build.verbatim-invalid`, `-head`, `-layer`, `-net` | error | refused verbatim text |
| `altium.stack-signal-limit` | error | more than 16 signal or 16 plane layers |
| `altium.group-skipped`, `altium.image-skipped`, `altium.verbatim-skipped` | warning | no Altium record |
| `altium.zone-arc-flattened` | info | an arc edge written as segments |

## Risks / Trade-offs

- **Many small model additions.** Each is optional and omitted when empty; a test builds every example
  and compares bytes with the commit before the change.
- **32-layer probes take CI time** (16 counts, 2 targets). The probes run in the KiCad job only, with
  one board each.
- **Verbatim items bypass the model.** They are reported, gated by version and layer and net checks, and
  c0278 compares them as text. They are the last resort, not a design tool.
- **Teardrop tokens differ between majors.** Recorded per major before the writer; the gate refuses a
  token a target does not know.

## Open questions

1. *Accept `copper=1` when KiCad loads a one-copper table?* Recommended: yes, decided by the probe.
2. *Promote radial/leader/centre dimensions, groups, images and pad shapes to modelled content on read?*
   Recommended: yes, in a follow-up after c0278 exists to prove the read-write round trip.
3. *Allow verbatim items in the rules file?* Recommended: yes (`target="kicad_dru"`), because custom
   rules are common on real boards and the DSL rule constructor covers a subset.

## Relation to the batch

- **c0275** uses every call here; its coverage table lists what is still unexpressed and writes verbatim
  items with `--allow-lossy`. c0275 also modifies "Zones in the DSL" (`key=`): whichever change archives
  second rebases its MODIFIED copy on the other's text.
- **c0278** compares groups, images, dimensions, zones with arcs and verbatim items in its levels 6 and 7.
- **c0276** (drawn schematic) is unrelated: this change touches the board only.

## Evidence

| behaviour | level before merge | hypothesis |
|---|---|---|
| tables of 2 to 32 layers load, Gerbers, re-save | `KICAD-VERIFIED` (9.0.x, 10.0.x) | `H-K-PCB-LAYERS` (extended) |
| builds of 10, 16 and 32 layers | `KICAD-VERIFIED` | `H-K-BUILD-LAYERS-32` |
| one-copper table | recorded either way | `H-K-PCB-ONE-COPPER` |
| copper text and graphics | `KICAD-VERIFIED` | `H-K-COPPER-ART` |
| pad shapes | `KICAD-VERIFIED` | `H-K-PAD-SHAPES` |
| teardrops | `KICAD-VERIFIED` | `H-K-TEARDROP` |
| groups, images, dimensions, zone arcs | `KICAD-VERIFIED` | `H-K-GROUP`, `H-K-IMAGE`, `H-K-DIM-KINDS`, `H-K-ZONE-ARC` |
| instance overrides, model references | `KICAD-VERIFIED` | `H-K-FP-OVERRIDE`, `H-K-MODEL-REF` |
| verbatim items | `KICAD-VERIFIED` | `H-K-VERBATIM` |
| Altium stacks above 8 layers | `ALTIUM-VERIFIED(kit)` | `H-A-STACK-32` |
