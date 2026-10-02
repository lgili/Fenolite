## Context

- **Gap A1 of the dogfood buck board.** Built through the public API only, its 29 parts gave 25 silkscreen warnings (`silk_overlap`, `silk_over_copper`, `silk_edge_clearance`); the references of the connectors, a transistor and the mounting holes crossed the board edge. Nothing in the model, the DSL or the build can move, turn, hide or re-layer a footprint's Reference or Value.
- **Today's reader (c0009, living).** Every `property` of a board footprint is a projected `Opaque` slot: its name and value go to `Component.ref`, `value` and `properties` ("Unmodelled board content is kept as slots"). `fp_text` items are opaque.
- **Today's writer (c0017, living; c0012 MODIFIES "Projected fields on write").** A read property is re-emitted verbatim, with only the value atom of Reference and Value rewritten; any other changed property value gives `kicad.board.projection-read-only`. A created footprint writes Reference on `F.SilkS` and the other properties on `F.Fab` at the footprint origin, with the skeleton's font (`board.md`, "Created items"). `embed.place_footprint` copies the library's properties, makes their angles absolute, and on the bottom side flips their layers, negates their Y and toggles `mirror`.
- **Neighbours.** c0011 places every built part with `place_footprint(with_property(…))`; c0027 appends user properties the same way, hidden on the fabrication layer; c0019 keeps or re-places matched footprints (precedence locked `place()` > board > `place()` > staging, two-way merge, no base); c0028 adds `fenolite.backends.kicad.frame.placed_extent(footprint) -> PlacedExtent`, whose `own` rings are the courtyard of the footprint's side in the board frame, with a pad-hull fallback.
- **Probes run for this proposal (2026-10-02).** Boards written as text in a scratch folder, `kicad-cli` 10.0.6 (local, S-0020) and 9.0.9 (pinned image `kicad/kicad`, local run, S-0029). Silkscreen extents came from `pcb export gerbers` and verdicts from `pcb drc --format json`. Both majors gave the same results:

  | fact | observation |
  |---|---|
  | position frame | a property's `at` X Y is footprint-local: the DRC anchor of a field is `at + R(θ)·local` (footprint (10, 30) with local (−8, 0) → (2, 30); (30, 10) at 90° with (8, 0) → (30, 2); bottom (6, 30) at 30° with (−5, 0) → (1.669873, 32.5)); no further mirror on the bottom |
  | angle frame | the stored angle is the board angle: on a footprint at 90°, stored 0 draws the text horizontal and stored 90 vertical; an edge canary confirms it |
  | justification | from the anchor, `left` runs to +X, `right` to −X, `bottom` lies above, `top` below; `mirror` reverses the horizontal sense, on either side |
  | keep-upright | without `(unlocked yes)`, a text stored at 180° or 270° is drawn as at 0° or 90°; with it, at the true angle |
  | DRC items | a crossing Reference gives `silk_edge_clearance` with an item "Reference field of <ref>" whose uuid is the property's and whose position is the anchor; a Value gives "Value field of  (<value>)"; a user field's violation lists only the edge item; a hidden field is not checked |
  | 9.0 silence | with the board's `min_silk_clearance` at 0, 9.0.9 reports no `silk_edge_clearance` (10.0.6 does); at 0.1 mm both do |
  | cut-out canary | an `Edge.Cuts` cut-out equal to the courtyard box: a field `0.25 mm + thickness/2` outside it, justified away, gives no violation; an anchor inside gives one, and so does a mirrored field justified the wrong way |

- **Census of the 21 readable corpus boards (S-0058).** 15 759 properties: 14 953 placed (`at`, `layer`, `uuid`, `effects`; the angle always written; hiding only as `(hide yes)`, 12 451; `(unlocked yes)` 10 458) and 806 bare (`ki_fp_filters`). 114 placed properties have no font thickness (`Datasheet`, `Description`). No footprint of the 1 674 repeats a property name. Property `justify` holds only `mirror` (8 369). No knockout. All 1 281 `fp_text` items are `user` texts; `fp_text reference` and `value` occur only in the third-party boards of format 7.0 and older.
- **Re-save, checked exactly.** `H-K-UUID-KEEP-2` says a 10.0.6 re-save "replaces `fp_text` items by properties". A new `pcb upgrade --force` of the 16 demos shows it is only in `RoyalBlue54L-Feather`, and only its 4 hidden `fp_text user "${REFERENCE}"` items (on `F.Fab`, in mounting holes): each became `(property "Field4" "${REFERENCE}" … (hide yes) …)` with a new uuid, after the other properties. The 67 visible `fp_text` items of that board stayed.
- **Older forms.** A third-party 7.0 board (S-0027) writes `(fp_text reference "FID3" (at 0 3 270) (layer "F.SilkS") hide (effects …) (tstamp U))`; `pcb upgrade` on 10.0.6 turns it into `(property "Reference" "FID3" (at 0 3 270) (layer "F.SilkS") (hide yes) (uuid U) (effects …))`. No 8.0 board or binary is at hand, so the 8.0 form is not observed (`H-K-FIELD-V8`).

## Goals / Non-Goals

**Goals:**
- Typed fields on placed footprints, read from 8.0, 9.0 and 10.0 boards and written for targets 9 and 10, with RT1 intact.
- Board-frame helpers, and a helper that puts a field beside the courtyard on a chosen side.
- DSL requests and their application in the build; precedence across rebuilds with GUI edits winning.
- Frames and helper behaviour settled on both majors with DRC canaries.

**Non-Goals:**
- Silkscreen legality beyond the canaries (c0022 placement legality, c0029 copper); an automatic side choice; text extents from font metrics.
- Symbol fields (c0012); `gr_text`, `fp_text` and text boxes.
- Writing property values other than Reference and Value through the writer; adding fields without slots to, or removing them from, a read footprint; user properties (c0027; their values stay the script's on kept footprints, Decision 17).
- Font face, bold, italic, keep-upright (`unlocked`) and knockout in the model.
- New issue codes, FEN codes, layering edges or runtime dependencies.

## Decisions

1. **Fields are modelled children with their own slots.** A placed `property` becomes a `FootprintField` entity in `FootprintInstance.fields`, with its own slot list, as pads are; the footprint's slot for it is `Modeled("fields")`.
   - The brief asks for "property nodes as modelled children", and an entity reuses the pad machinery: slot lists in `ext["kicad"]`, rebuild order by provenance index, `_write_order` for created items.
   - Rejected: a typed edit over the opaque property fragment (rewriting children of an opaque slot is a new exception to `kicad-slots` "Slot source for model entities", which c0012 also MODIFIES). Rejected: value objects whose slots sit in the footprint's bag under an index (fragile when fields are reordered, and no home for the uuid).

2. **The text stays in the component; the value atom stays projected.** A field holds placement and appearance only. Its value atom is an `Opaque` slot of the field, projected into `Component.ref`, `value` or `properties`.
   - So "Projected fields on write" (c0012's text) needs no change: the writer rewrites Reference and Value atoms, and other values stay read-only in the writer. On a kept footprint the values of c0027's user properties still come from the script, as c0019 Decision 22 decides: the lens sets their value slots, never the writer (Decision 17).
   - Rejected: `FootprintField.value` (two sources of truth, and other property values would become writable, a delta to a requirement that c0012 modifies).

3. **The model uses the pad frame.** `position` is the stored footprint-local point; `rotation` is relative to the footprint, so the board angle is `(rotation + footprint rotation) mod 360°`; on the bottom side the stored coordinates are already mirrored. The probes confirm this frame on both majors (Context).
   - Rejected: the board angle in the model (rotating a footprint would have to rewrite every field; c0019 Decision 7 meets the same problem with absolute child angles). Rejected: board-frame positions (they change with every move).

4. **Which properties are fields, and how much of them.** A property is a field when it holds `at`, `layer` and a font `size`; only the first property of a name is one. `effects` is one modelled child carrying size, thickness, justification and mirror. An `effects` with anything else (`bold`, a `face`) stays projected, so its size cannot be edited; `unlocked`, knockout and unknown children stay opaque in place.
   - The census covers every Reference and Value of the corpus; `bold` occurs on 6 properties.
   - Rejected: nested slot lists for `effects` and `font` (more writer code and RT1 risk for 6 properties). Rejected: modelling keep-upright or knockout (not needed by A1; kept verbatim).

5. **Ids by name.** `derived_id("fld", "kicad", "<key>:field:<name>")`, `<key>` the native id behind the footprint's pad ids; `native_ids["kicad"]` is the property's uuid; prefix `fld` joins the closed table (an ADDED `design-model` requirement, as c0008 added `fpd`).
   - A placed copy and its read-back board give equal ids, and a field keeps its id when KiCad gives the property a new uuid.
   - Rejected: the property uuid inside the id (10.0.6 creates new uuids when it converts hidden texts).

6. **Tolerant reading of older forms.** A bare `hide` atom, in the property or in its `effects`, reads as hidden. Such an atom stays an `Opaque` slot. 8.0 boards stay read-only (`FEN-7003`), so the writer never emits these forms. A repeated name stays opaque with `kicad.board.kept-opaque` (c0027 records that a re-save merges duplicate field names, `H-K-VENDOR-DUPNAME`). A field with an inexact `at` or font stays a projected property, as "Exact numbers on boards" keeps an inexact pad.
   - Rejected: refusing older spellings (8.0 boards are readable today, and RT1 must keep holding for them). Rejected: a new reader code for repeated names (`pcb.ISSUE_CODES` is a closed table in a living requirement).

7. **Writing.** A field is emitted as name, value, `(at X Y A)` with the board angle, always written, `layer`, `(hide yes)` when hidden, `uuid`, and `effects` with font size, optional thickness and optional `justify` (h, v, `mirror`). Read fields are rebuilt from their slots, so unchanged nodes stay tree-equal and `unlocked` keeps its place. `CANONICAL_ORDER["property"]` gains `hide` between `layer` and `uuid` (the observed order), and `FLOOR_HEADS` gains `hide` (an 8.0 name, S-0033 at tag 8.0.0; the created test board writes it). A created footprint places each property it writes from the field of that name.
   - Rejected: creating property nodes for fields without a slot list added to a read footprint (a property value would become writable, a delta to "Projected fields on write"). Adding such a field there raises `ValueError`; a field that brings its slot list, such as a user property that the lens takes from the built copy (Decision 17), is written from its slots. Removing one leaves the component's property unmatched, which gives `projection-read-only`.

8. **Helpers live in the KiCad backend.** `backends/kicad/fields.py` may import `geometry` and c0028's `frame`; `lens` calls it without importing `geometry`, and `dsl` keeps importing only `model`.
   - Rejected: `placement` (the lens may not import it). Rejected: `lens` (no geometry).

9. **`place_outside` uses justification instead of text extents.** Board angle 0; the anchor sits `gap + thickness/2` outside the box of `placed_extent(fp).own`, centred on the other axis; the justification points away from the box (top → `bottom`, bottom → `top`, left → `right`, right → `left`, the horizontal sense reversed for a mirrored field). `DEFAULT_GAP` is 0.25 mm, a Fenolite choice.
   - The probes show the ink stays on the far side of the anchor, apart from a stroke half-width: for "I" at 1 mm the stroke centre lies 0.34 mm beyond the anchor sideways, 0.13 mm for `bottom` and 0.04 mm for `top`; `gap + thickness/2` absorbs the half-width. Other glyphs are not measured, so the module's label stays `INFERRED`.
   - Rejected: font metrics (KiCad's stroke font is not modelled, and reading its tables is out of clean-room scope). Rejected: an automatic side (needs text extents). Rejected: angle 90° placements (later).

10. **DSL surface.** `Part.field(name, …)` for `Reference` and `Value`, board-frame offsets from the part's placement point, the board angle, a side-relative layer (`silk`, `fab`), visibility, size, thickness, justification, `outside` and `gap`, and `locked`.
    - Board-frame offsets match how the script places parts and what DRC reports; "2.5 mm above U1, horizontal" stays true after `rot=90`.
    - `justify` takes KiCad's words in the text's reading frame, so a mirrored field on the bottom side runs the other way on the board (`H-K-FIELD-JUSTIFY`); `docs/dsl.md` says so, and `place_outside` handles it itself.
    - Rejected: footprint-frame offsets (they turn with the part). Rejected: any property name (an unknown name needs a new code in closed build tables). Rejected: a separate `reference_outside()` call (one surface).

11. **Build.** `build_design(…, fields=…)` applies the requests right after `place_footprint` or staging, through `lens.fields.apply_requests`. A field missing from the footprint raises `FormatError` (`FEN-3004`), as a malformed library input.
    - c0011's "Built project files" spells `build_design`'s signature, and c0019 and c0027 MODIFY it. This change adds a keyword with a default through an ADDED requirement and modifies none of them (Open Questions).
    - Rejected: requests carried on `Placement` (staged parts have none, and c0019's `KeptPlacement` replaces them). Rejected: a `build.*` code (`BUILD_ISSUE_CODES` is a closed table that c0019 and c0027 modify).

12. **Precedence across rebuilds.** A locked request wins, then the board's field, then an unlocked request, then the library: the rule of c0019 Decision 5, applied per field, as a two-way merge without a base (c0019 Decision 3).
    - An agent cannot drag a label in KiCad, so `locked=True` is its way to force a field on an existing board; `--discard-layout` stays the way to start again.
    - This refines c0019's "Kept and re-placed footprints" without modifying it: a kept footprint keeps every slot of its node, and only the values of fields named by a locked request change, besides the user-property values that c0019 gives to the script (Decision 17).
    - It is the edited-in-place model of c0028 Decision 20, shared with c0019's footprints and c0031's zones; script copper follows that decision's other, derived model.
    - Rejected: a three-way merge with `.fenolite/` as base (cache authority). Rejected: the script always wins (GUI edits lost on every build).

13. **Board fields follow a re-placed footprint.** When c0019 re-places a matched footprint with the same lib id on the same side (a locked move, an alias, an off-board part placed again), each field the board footprint has takes the board's values, unless a locked request names it.
    - A locked move would otherwise reset every hand-placed field. Fields are footprint-relative (Decision 3), so the copy is exact.
    - The footprint is still c0019's built copy (its node, ids and uuids); only its field values come from the board.
    - Rejected: carrying across a side change (it needs `embed`'s flip rules for fields; later). Rejected: always the built copy.

14. **No issue codes; outcomes in the result.** `merge_fields` returns `kept`, `forced` and `carried`, reported as `result.preserved.fields`. A key under c0019's `preserved` is additive.
    - Rejected: `layout.field-*` codes (they would MODIFY c0019's closed `PRESERVE_ISSUE_CODES` and c0011's "Build issue codes", which c0019 and c0027 modify).

15. **The oracle uses DRC canaries only.** Anchors come from DRC item positions matched by uuid; angle, justification, mirror and keep-upright from edge canaries; `place_outside` from a courtyard cut-out. Bench projects set `min_silk_clearance` to 0.1 mm, and each "no violation" verdict sits in a report whose crossing control fires (the rule of `kicad-oracle` "DRC verdicts come from the JSON report"). Probes on boards written as text run first, before the model exists, with a stop rule.
    - Rejected: Gerber or SVG parsing (a new format reader for tests; used only in the proposal's scratch probes). Rejected: the default clearance of 0 (9.0.9 is silent).

16. **One living requirement is MODIFIED.** `kicad-file-backend` "Unmodelled board content is kept as slots" lists "properties" among projected children and has the scenario "Footprint property is projected", which a modelled field breaks. Its full text is copied from the living spec (c0009) and edited: fields join the modelled items; the projected list names non-field properties, the field's value atom and a field `effects` that the emitter does not reproduce, and becomes non-exhaustive ("among others"), so that projected children that later requirements add, such as c0031's zone settings, do not contradict it; and the scenario becomes "Footprint property is a field", with a new one for bare properties. No active change modifies it (checked on 2026-10-02).
    - Not modified: `design-model` "Board entities read from file backends", `kicad-slots` "Slot source for model entities" and `kicad-file-backend` "Projected fields on write"; this change only adds requirements beside them.
    - Rejected: keeping every property projected at the footprint level and adding fields as a second projection (Decision 1); the scenario would stay true, but the writer would rewrite opaque fragments.

17. **User properties stay the script's on kept footprints (c0019 Decision 22, carried to fields).** c0019 gives the values of a kept footprint's user properties to the script and keeps their placement and appearance from the board. After this change those `property` nodes are fields, so `merge_layout` applies the rule to fields:
    - a field of the kept footprint with the same name (after `str.casefold()`) keeps its position, rotation, layer, size, thickness, visibility, justification, mirror, uuid and other slots; only its `Opaque` value-atom slot takes the script's value, and its name the script's spelling;
    - a missing user property is added as the built copy's field, with its slot list, the uuid of c0019's rule and an id derived for the kept footprint; the writer emits it after the last field node (`kicad-slots`, "Order-preserving rebuild"), so no writer rule changes;
    - the component takes the script's values, so "Projected fields on write" passes; `merge_fields` never changes a value slot, and requests name only `Reference` and `Value`.
    - The rule is stated in the ADDED "Footprint fields across rebuilds", which names "Kept and re-placed footprints"; c0019's text lets later requirements change named slots of a kept node.
    - Rejected: the board wins for the values (c0019 Decision 22 rejects it: a part number changed in the script would never reach a kept footprint). Rejected: `FootprintField.value` (Decision 2). Rejected: a MODIFIED copy of c0019's "Kept and re-placed footprints" (a long text copied again for one bullet, where c0019's exception path allows the ADDED form).

## Files and public API

| file | public API |
|---|---|
| `src/fenolite/model/board.py` | `FieldJustifyH = Literal["left", "center", "right"]`; `FieldJustifyV = Literal["top", "center", "bottom"]`; `@dataclass(frozen=True, slots=True) class FootprintField(Entity)` with `name: str`, `position: Point`, `layer: str`, `size: Size`, `rotation: Udeg = 0`, `thickness: Nm \| None = None`, `visible: bool = True`, `h_justify: FieldJustifyH = "center"`, `v_justify: FieldJustifyV = "center"`, `mirrored: bool = False`; `FootprintInstance.fields: tuple[FootprintField, ...] = field(default=(), metadata=ORDERED)` |
| `src/fenolite/model/__init__.py` | re-exports `FootprintField`, `FieldJustifyH`, `FieldJustifyV` |
| `src/fenolite/core/ids.py` | prefix `fld` in `PREFIXES` |
| `schemas/fenolite.model.v0/board.json` | regenerated by `tools/gen_schemas.py` |
| `src/fenolite/backends/kicad/pcb.py` | `FOOTPRINT_FIELDS["property"] = "fields"`; `FIELD_FIELDS` (`at` → `position`, `layer` → `layer`, `hide` → `visible`, `uuid` → `native_ids`, `effects` → `effects`); `FIELD_POSITIONAL = ("name",)`, so the value atom splits as an opaque slot (`POSITIONAL["property"]` keeps `("name", "value")` for created nodes); the field reader and emitter; `model_source` and the writer for `FootprintField`; `CANONICAL_ORDER["property"]` with `hide`; `FLOOR_HEADS` with `hide` |
| `src/fenolite/backends/kicad/fields.py` (new) | `OutsideSide = Literal["top", "bottom", "left", "right"]`; `DEFAULT_GAP = 250_000`; `field_anchor(fp, field) -> Point`; `field_angle(fp, field) -> Udeg`; `set_field(fp, name, *, anchor=None, angle=None, layer=None, visible=None, size=None, thickness=None, justify=None, mirrored=None) -> FootprintInstance`; `place_outside(fp, name, *, side, gap=DEFAULT_GAP) -> FootprintInstance`; `EVIDENCE` |
| `src/fenolite/backends/kicad/__init__.py` | re-exports `field_anchor`, `field_angle`, `set_field`, `place_outside` |
| `src/fenolite/dsl/part.py`, `convert.py`, `__init__.py` (c0011; extended) | `Part.field(name, *, dx=None, dy=None, rot=None, layer=None, visible=None, size=None, thickness=None, justify=None, outside=None, gap=None, locked=False) -> None`; `@dataclass(frozen=True, slots=True) class FieldRequest`; `fields(design) -> Mapping[str, tuple[FieldRequest, ...]]` |
| `src/fenolite/lens/fields.py` (new) | `class FieldRequestLike(Protocol)`; `apply_requests(instance, requests) -> FootprintInstance`; `@dataclass(frozen=True) class FieldMerge(design: Design, kept: tuple[str, ...], forced: tuple[str, ...], carried: tuple[str, ...])`; `merge_fields(merged: Merged, board: Design, match: LayoutMatch, requests: Mapping[str, Sequence[FieldRequestLike]]) -> FieldMerge` |
| `src/fenolite/lens/preserve.py` (c0019; extended) | `merge_layout` applies c0019's user-property rule to fields (Decision 17); public names and `PRESERVE_ISSUE_CODES` unchanged |
| `src/fenolite/lens/build.py` (c0011, c0019; extended) | `build_design(…, fields: Mapping[str, Sequence[FieldRequestLike]] = MappingProxyType({}))`; `summary["preserved"]["fields"]` |
| `src/fenolite/cli/cmd_build.py` (c0011, c0019; extended) | passes `dsl.fields(design)`; `result.preserved.fields` |
| `docs/formats/kicad/board.md` | fact rows of Context, the reader table row for `property`, writer bullets for fields, `hide` in the floor names |
| `docs/dsl.md`, `docs/lens.md`, `docs/cli-contract.md` | `Part.field` and its frame; field precedence and `carried`; `result.preserved.fields` |
| `docs/hypotheses.md`, `docs/evidence/sources.md`, `LEGAL-ANNEX.md`, `src/fenolite/backends/kicad/PROVENANCE.md` | rows of this change; session row; an `oracle` row for `pcb drc` and `pcb upgrade` on field benches |
| `docs/evidence/kicad/probes/9.0.9.json`, `10.0.6.json` | `field-*` outcomes |
| `tests/unit/model/test_fields_model.py`, `tests/unit/backends/kicad/test_pcb_fields.py`, `test_pcb_fields_write.py`, `test_fields_helper.py`, `tests/unit/dsl/test_fields.py`, `tests/unit/lens/test_build_fields.py`, `test_fields_merge.py`, `tests/unit/cli/test_build_fields_command.py`, `tests/corpus/test_board_fields.py` (new); c0019's `tests/unit/lens/test_preserve_footprints.py` and `tests/unit/cli/test_build_preserve_command.py` (extended) | hermetic and corpus tests |
| `tests/kicad/board/_fieldprobe.py`, `test_field_probes.py`, `_fieldbench.py`, `test_field_oracle.py` (new); `tests/kicad/_probes.py` (c0017; extended) | probes and oracle, `needs_kicad`, major-aware |

Layering: `dsl` imports `core` and `model`; `lens.fields` imports `core`, `model`, `backends.kicad.fields` and c0019's `lens.preserve`; `backends.kicad.fields` imports `core`, `model`, `geometry` and `backends.kicad.{pcb,frame}`. Every edge is in `package-layering`; `ALLOWED` is unchanged.

## Sources registered by this change

| id | URL | licence of source | used for |
|---|---|---|---|
| S-0120 | https://docs.kicad.org/8.0/en/pcbnew/pcbnew.html | GPL-3.0-or-later or CC-BY-3.0-or-later, as the 9.0 page S-0010 (to check on the page) | footprint fields and text properties in 8.0, background for `H-K-FIELD-V8` (to verify on the page; if it says nothing, the row rests on S-0021 and S-0030) |

S-0121 to S-0124 stay free. Extended "used for" cells, with no new id (task 1.1):
- **S-0020** and **S-0029**: field probes and oracle on 10.0.6 and on the pinned 9.0.9 image.
- **S-0021** and **S-0040**: the syntax of footprint `property` and `fp_text` (keywords only, in Fenolite's words).
- **S-0030** (tag 8.0.0) and **S-0033** (tag 8.0.0): dated notes on footprint properties; `hide` exists in the 8.0 format (`FLOOR_HEADS`).
- **S-0058**: the property census; **S-0027**: the 7.0 `fp_text` form of a third-party copy.
- **S-0022** and **S-0037**: `pcb drc` and `pcb upgrade --force`; **S-0010** and **S-0038**: keep-upright and text properties in the manuals (to verify on the pages).

No KiCad source file is read. If a URL above is already registered when the change is implemented, its id is cited and no row is added.

## Hypotheses registered by this change

| id | statement | settling test | criterion | proposal probe (2026-10-02) |
|---|---|---|---|---|
| H-K-FIELD-FRAME | The `at` X Y of a board footprint's `property` is footprint-local, its anchor being `at + R(θ)·local` with no further mirror on the bottom side, and its angle is the board angle (S-0020, S-0029) | `tests/kicad/board/test_field_oracle.py -k "anchors or inside or angle"` | on both majors: anchors within 10 nm for top 0°, 30°, 90° and bottom 0°, 30°, 90°; moved fields silent with a live control; the angle canary as specified | observed on both majors |
| H-K-FIELD-JUSTIFY | From its anchor a `left` text runs to +X and a `right` one to −X, `bottom` lies above and `top` below; `mirror` reverses the horizontal sense; without `(unlocked yes)` a text at 180° or 270° is drawn as at 0° or 90° (S-0020, S-0029) | `test_field_oracle.py -k "justify or upright"` | every justification, mirror and keep-upright canary as specified, on both majors | observed on both majors |
| H-K-FIELD-DRC | `pcb drc` reports a Reference or Value field crossing the edge as `silk_edge_clearance` with an item whose uuid is the property's, whose position is the anchor and whose description names the field; hidden fields are not checked; 9.0.9 reports the check only when `min_silk_clearance` is above 0, and 10.0.6 also at 0 (S-0020, S-0029, S-0055, S-0056) | `test_field_oracle.py -k "anchors or hidden"`; probes `field-hidden` and `field-edge-zero` | as stated on both majors | observed on both majors |
| H-K-FIELD-RESAVE | A 10.0.6 re-save keeps a property node written by Fenolite (position, angle, layer, hiding, size, thickness, justification) and its uuid; it turns hidden `fp_text user` items into hidden properties named `Field<N>` with new uuids and keeps visible ones (S-0020, S-0022) | `test_field_oracle.py -k resave`; supporting data from `tests/corpus/test_board_fields.py` on upgraded copies | on 10.0.6 the re-read fields equal the written ones | conversion observed on the 16 demos; the written half is pending |
| H-K-FIELD-V8 | 8.0 boards hold Reference and Value as `property` nodes with `at`, `layer` and `effects`, as 9.0 does; how 8.0 writes hiding is to be read from the sources (S-0021, S-0030, S-0120) | doc check in task 1.1; optional probe with a `kicad/kicad` 8.0 image (`fp upgrade` of a footprint) | a source states it, or the probe shows it; the reader accepts both spellings either way | not observable locally |
| H-K-FIELD-OUTSIDE | A field set by `place_outside` (angle 0, anchor `gap + thickness/2` outside the courtyard box, justification pointing away) keeps its ink outside the box by more than `min_silk_clearance` for the bench references (S-0020, S-0029) | `test_field_oracle.py -k outside` | on both majors, no violation on the cut-out benches and one for every control | observed on both majors for four sides and a mirrored left side |

Cited, not settled here: `H-G-ROT-DIR`, `H-G-BOTTOM-PLACE`, `H-G-BOTTOM-STORE`, `H-G-FLIP`, `H-G-PAD-ANGLE-ABS`, `H-K-UUID-KEEP-2` (refined by `H-K-FIELD-RESAVE`), `H-K-PCB-READ`, `H-K-PCB-WRITE`, `H-K-LENS-KEEP` (c0019), `H-G-FRAME-CRTYD` (c0028), `H-K-VENDOR-DUPNAME` (c0027).

## Evidence level per behaviour (before merge)

| behaviour | level required | proof |
|---|---|---|
| Model, schema, ids, prefix | mechanical | `tests/unit/model/test_fields_model.py`, `tools/gen_schemas.py --check` |
| Reader mapping and slots | mechanical; lossless reading `CORPUS-VERIFIED` (RT1 on 21 boards and the upgraded copies) | `test_pcb_fields.py`, `tests/corpus/test_board_rt1.py`, `test_board_fields.py` |
| Writer: emitted nodes, unchanged nodes, created fields | mechanical; loads on both majors | `test_pcb_fields_write.py`, `test_pcb_write.py`, `tests/kicad/board/test_triad.py` |
| Position and angle frames, bottom side | `KICAD-VERIFIED (9.0.x, 10.0.x)` | `test_field_oracle.py` |
| Justification, mirror, keep-upright | `KICAD-VERIFIED (9.0.x, 10.0.x)` | `test_field_oracle.py` |
| DRC items of fields; the 9.0 silence | `KICAD-VERIFIED (9.0.x, 10.0.x)` | `test_field_oracle.py`, probe files |
| `place_outside` | `KICAD-VERIFIED` on the bench; `fields.EVIDENCE` stays `INFERRED` | `test_field_oracle.py -k outside` |
| Edited fields survive a re-save | `KICAD-VERIFIED (10.0.x)` | `test_field_oracle.py -k resave` |
| 8.0 forms | `INFERRED` | `board.md` row |
| DSL, build application, lens precedence and reports; user properties on kept footprints (Decision 17) | mechanical | unit and command tests |
| `build` envelope | unchanged (`INFERRED`); `fields.EVIDENCE` is not added (Open Questions) | — |

## Budget (working days)

| work | days |
|---|---|
| 1. registers, probes first, format page | 1.25 |
| 2. model, schema, prefix | 0.5 |
| 3. reader | 1.25 |
| 4. corpus RT1 and census | 0.5 |
| 5. writer | 1.25 |
| 6. backend helpers | 1.0 |
| 7. DSL | 0.5 |
| 8. build application | 0.75 |
| 9. lens precedence; user properties as fields (Decision 17) | 1.25 |
| 10. oracle on both majors | 1.25 |
| 11. closing | 0.75 |
| **total** | **10.25** |

The roadmap has no line for this change. c0008 took about three times its plan line, so the estimate counts the reader and writer work of c0009 and c0017 at their real pace. Cut order, to 8.5 days. A cut first edits or removes the requirements and scenarios named with it, so no requirement is archived without its code:
1. **Carrying** (Decision 13; −0.25). layout-lens "Footprint fields across rebuilds": the re-placed rule and `carried` are removed, and so are the scenarios "Fields follow a forced move" and "A side change takes the library fields"; re-placed footprints keep the built copy's fields.
2. **`place_outside`** (Decision 9; −1.25). kicad-file-backend "Footprint field helpers" keeps the conversions only; design-dsl drops `outside` and `gap` and the scenario "Reference above a part"; kicad-oracle drops "Outside" and its scenario; `H-K-FIELD-OUTSIDE` is not registered. A1 is then met with explicit offsets only.
3. **Re-save** (−0.25). kicad-oracle drops "Re-save"; `H-K-FIELD-RESAVE` stays `INFERRED` from the demo half.

Not optional: the model, reading, writing, both-major frames, DSL offsets, the build application, the lens precedence and the user-property rule (Decision 17).

## Risks / Trade-offs

- [c0028's `placed_extent` changes name, module or result] → Task 1.1 re-checks it; `place_outside` needs only the points of the courtyard on the footprint's side.
- [c0011, c0019 or c0027 change `build_design`, `Merged` or `result.preserved`] → Task 1.1 re-checks the names; the ADDED requirements follow them.
- [Modelling 14 953 properties breaks RT1] → The corpus gate (task 4.1) runs before writer work; the reproducibility check keeps odd spellings as projected slots.
- [Glyph ink of other references crosses the anchor] → `gap + thickness/2`, a 0.25 mm default and the `INFERRED` label beyond the bench.
- [Keep-upright surprises for angles above 90° and up to 270°] → `docs/dsl.md` says KiCad draws such fields turned, unless the library field is unlocked.
- [9.0.9's silent edge check hides real problems] → A `board.md` fact row; c0026 lowers board minimums and may lower `min_silk_clearance` later.
- [Duplicate property names, or 8.0 spellings] → Opaque slots with `kicad.board.kept-opaque`; 8.0 boards stay read-only.
- [`.fenolite/board.json` of every build gains `fields`, so tests of c0011 and c0019 that pin those bytes change] → Task 8.1 updates them in the same commit; the board, project and rules files of a build without requests keep their bytes.
- [Overrun] → The cut order of "Budget".

## Migration Plan

- Additive: a model field with a default, a regenerated schema, a new id prefix, two new modules, a DSL call, a build keyword and a result key. Behaviour change: a placed property is a modelled field, and `.fenolite/board.json` lists fields. Unchanged boards are written tree-equal as before, and RT1 holds.
- Archive order: after c0011 (`design-dsl`), c0019 (`layout-lens`, `merge_layout`, `Merged`, `result.preserved`) and c0028 (`frame.placed_extent`), as the canonical order has it (… c0012, c0028, c0029, c0030, c0031 …). The ADDED requirements need those capabilities and names; c0012 archives earlier and shares no requirement with this change.
- The MODIFIED `kicad-file-backend` "Unmodelled board content is kept as slots" copies the living text. If c0031 or another change modifies it before this change is archived, this copy takes that text as its base (task 1.1).
- Rollback: remove `fields.py` of both packages, the field mapping and emitter, the DSL call and the build keyword; restore the living text of the MODIFIED requirement; boards written meanwhile stay valid KiCad boards.
- Hand-overs: c0022's placer and legality check may call `place_outside` and judge field boxes; c0026 may lower `min_silk_clearance`; c0027's user properties are hidden fields here, and on kept footprints their values stay the script's (Decision 17).

## Open Questions

- **DSL offset frame.** The default measures `dx` and `dy` in the board frame from the part's placement point, with the board angle. The alternative, the footprint frame, turns with the part.
- **Default gap.** 0.25 mm (Fenolite choice). To confirm.
- **Codes or result keys.** The default reports precedence outcomes in `result.preserved.fields` only, so the closed code tables of c0011 and c0019 stay untouched; `layout.field-*` codes can follow once those tables are archived.
- **The `build_design` keyword.** The default adds `fields` through the ADDED "Field placements in a build". c0011's "Built project files", which c0019 and c0027 MODIFY, still spells the signature without it; the coordinator may fold the keyword into the last MODIFIED text when archiving.
- **`fields.EVIDENCE` in the build envelope.** The default does not add it, because that would modify "Build evidence" (c0011, MODIFIED by c0019 and c0027); both are `INFERRED`.
- **8.0 probe.** An optional run of a `kicad/kicad` 8.0 image (S-0029, at implementation time only) would settle `H-K-FIELD-V8`. The default keeps it optional; the reader accepts both spellings.
- **Names beyond Reference and Value in the DSL.** The default allows only these two in v0.1; the model and the writer already handle every field.
- **`fp_text user` as fields.** The default leaves them opaque; 10.0.6 converts only hidden ones into properties.
- **Budget.** 10.25 working days, 8.5 after cuts. To accept.
- **Divergence check against the working tree (2026-10-02).** c0011's code is uncommitted (`dsl/part.py` has `Part.place` and `Request`; `lens/build.py` has `build_design(design, placements, *, name, copper, resolver, target, allow_lossy)`); c0019, c0027 and c0028 are proposals. Task 1.1 re-checks every consumed name.
