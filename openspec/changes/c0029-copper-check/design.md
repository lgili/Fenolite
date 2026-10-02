## Context

- **The gap (A3 of the dogfood buck board).** A board built through Fenolite's public API only carried a `GND` via whose copper touched a `VIN` track. KiCad loaded the via on `VIN` without a message, its DRC reported no short, only `via_dangling`, and a board saved by KiCad afterwards held the via on `VIN`. The report has no committed artefact, so this change treats it as reported, not verified (`H-K-VIA-RENET`, UNVERIFIED). Whatever KiCad does, a short that Fenolite writes must be caught by Fenolite before KiCad sees it.
- **`check` today.** c0013 defines `fenolite check` as a fixed pipeline (`checks.stages.STAGE_ORDER`, `run_checks`), with KiCad injected through `Validator` and `Oracle` (`backends.base`). Its requirement "Check stages and statuses" lets a later change insert a stage through an ADDED requirement. c0020 does so and then pins the whole tuple: its ADDED requirement "Stages added for findings and round trips" says `STAGE_ORDER` SHALL be an exact six-stage tuple. Inserting a stage after c0020 is therefore a MODIFIED delta of that ADDED requirement (Decision 9).
- **The data.** The model has `Track(start, end, width, layer, net_id)`, `Arc(start, mid, end, width, layer, net_id)`, `Via(position, diameter, drill, layers, net_id, via_type)` with `layers` the two outermost copper layers, `Zone(outline, layers, net_id, priority, fills)` and `ZoneFill(layer, polygon, island)`. Pads sit in the footprint frame (`Pad.position`, `Pad.rotation`). Roundrect ratios, chamfers, trapezoid deltas and custom primitives stay opaque slots. Net classes are `Circuit.netclasses` (`NetClass.clearance`) with `Net.netclass_id`; rules are `Design.rules` (`Rule(kind, selector_a, selector_b, layers, min, severity, priority)`).
- **Board-frame pads (c0028).** c0028 owns pad positions, angles, layers and shapes in the board frame. It adds to `backends.base` the records `PadCopper(layer, core, width, filled=False, exact=True)` and `BoardPad(…, ref, pad_id, number, kind, layers, net_id, net, copper, …)` and the protocol `BoardFrame` (`board_pads(design, *, issues=None)`), which `KicadBackend` satisfies (`_FRAME`), with the work in `backends/kicad/frame.py`. A `PadCopper` follows the conventions of `Thick` exactly; supersets (trapezoids, chamfers, curved custom primitives, unknown corner ratios) are flagged `exact=False`. This change consumes that interface and computes no pad frame itself; task 1.3 re-checks the names against c0028's archived text.
- **Board minimums (c0026).** c0026 keeps board-wide rules as custom rules and also writes the board-setup minimums they imply. It measures per major whether a custom clearance rule governs the items of a class with a larger clearance (`H-K-PRO-MIN-CLASS`, table `lowering.RULES_OVER_CLASSES`) and whether a minimum governs a lower custom rule (`H-K-PRO-MIN-RULE`, table `lowering.FLOOR_OVER_RULES`). Its open question 6 leaves to this change how the clearance in force uses them.
- **Rules facts.**
  - When several custom rules match a pair, the later rule in the file governs (`H-K-DRU-ORDER`, KICAD-VERIFIED). c0018's `rulemap.rule_order` orders model rules so that priority 1 is written last.
  - A condition on side `A` alone matches a pair in either order, and names compare without regard to letter case (`H-K-DRU-COND`, KICAD-VERIFIED).
  - Board-setup minimums are floors (`H-K-DRU-KIND`, INFERRED for rules; `H-K-PRO-FLOOR`, KICAD-VERIFIED for class values). The template floor `min_clearance` is 0.
  - A `.kicad_dru` next to the board is read with or without a project file (`docs/formats/kicad/rules.md`, `H-K-TOK-RULES-SILENT`).
  - c0018's canary rule (`tests/data/kicad/tokens/canary/canary.kicad_dru`) has no condition: 3 mm on every pair. c0010's net-class bench therefore scopes its canary to `net CANARY_A`, because the unconditional canary would govern every class row.
- **The project files.** c0010's `pro.read_project` gives `ProjectInfo.floors["clearance"]`, and `pro.apply_project(design, info)` sets the classes and each net's class (`netclass_id = None` means `Default`). c0018's `dru.read_rules` lifts rules of the closed grammar and keeps the others opaque. A DSL design has no rule other than net classes and no `Default` class; KiCad's `Default` class comes from the project template that c0010 writes. The files written next to the board are therefore the only complete source of what KiCad enforces.
- **The geometry kernel (c0005).** Exact predicates on integer points (`segments_closer_than`, `dist2_segment_segment`, `dist2_point_segment`, `point_in_ring`), `Polygon` and `polygons_intersect`, `Arc.polygonize(tol)` with every point of the true curve within `tol + 1` nm of the polyline, `BBox` and the immutable STR `SpatialIndex`.
- **The build.** c0011's `lens.build.build_design` returns every file as bytes and refuses (no files) on any error issue. c0019's "Build command" adds that a build with an error issue returns no planned write and exits 5. c0019 merges the existing board's copper and the user's rules into what the build writes, and states that `lens` never imports `geometry`. "Build issue codes" is a closed table of the build's own findings.
- **Layering.** `checks` may import `core`, `model`, `geometry` and `backends.base`; `lens` may import `model` and `backends`; `cli` may import anything. Only this change of the batch may propose a MODIFIED `package-layering`; it does not (Decision 11).
- **Zone fills on 9.0.** c0031 observed that 10.0.6 inflates the fill of a target-9 zone written without `(filled_areas_thickness no)`. Fill parity is therefore proved on 10.0.6 with target-10 boards only.
- **Environment.** KiCad 10.0.6 is installed locally; 9.0.9 runs in the pinned image (S-0029). Order: after c0028 and c0020.

## Goals / Non-Goals

**Goals:**
- An exact, hermetic short and clearance check of copper, usable as a library function, a `check` stage and a build guard, with one semantics.
- A clearance in force that is defined from the model (rules, classes, board minimum) and proved equal to KiCad's on canaries.
- Every finding located: layer, point and both items.
- The reported re-net recorded per major.
- A measured cost on real boards.

**Non-Goals:**
- Everything under "Non-goals" in the proposal.
- Exact algebraic distances between arcs (Decision 2).
- Netlist or connectivity checks (c0020's assignment compare), unconnected items, dangling vias.
- A zone fill, or a stale-fill verdict (c0019's digest, c0015).
- Changing `Selector.matches`, `rule_order`, `read_board`, `build_design` or `BUILD_ISSUE_CODES`.

## Decisions

1. **Thick shapes, exact, in the geometry kernel.** Every copper piece is a core swept by a disc: a point (via, round pad), a segment (track, oval pad), an open polyline (arc) or a filled ring (fill, rectangular and polygonal pad cores) with a width. The gap of two pieces is `dist(core_a, core_b) − (w_a + w_b) / 2`. Doubling coordinates makes every half-width an integer, so `thick_touch` (gap ≤ 0) and `thick_closer_than` (gap < limit) are decided with `segments_closer_than`, exact squared distances and `point_in_ring`, never a float. `geometry/thick.py` holds the type and five functions (`thick_bbox`, `thick_touch`, `thick_closer_than`, `thick_gap_floor`, `thick_witness`); c0022's edge clearance can reuse them.
   - Rejected: polygonising every item and using polygon booleans (inexact for discs, slow, and the boolean backends are extras).
   - Rejected: float distances with a tolerance (the kernel's rule: nothing returns a float).
   - Rejected: a private module in `checks`. `placement` (c0022) cannot import `checks`.

2. **Arcs within a stated band.** An arc becomes the polyline of `Arc.polygonize(ARC_TOL_NM)`, 1 µm, with band `e = arc_tol + 1` nm, the kernel's bound. A short is reported only when the arc's shape narrowed by `2e` touches (the true copper touches); a clearance finding is reported when the shape widened by `2e` is too close (no violation is missed). A pair whose true gap lies within `2e` of the clearance may be reported; the reported gap is a lower bound.
   - Rejected: exact arc-to-segment and arc-to-arc distances (sums of square roots, many cases, slow in Python).
   - Rejected: arcs as unsupported items. Curved tracks are common.

3. **What is copper.** Tracks; arcs; vias as discs on every copper layer of their span (`Board.layers` table order between `layers[0]` and `layers[1]`; a `through` via spans all); pads as c0028's per-layer cores; zone fills as filled rings on their layer. Not copper: zone outlines, rule areas, graphics, texts, holes, `np_thru_hole` pads.
   - Vias and through-hole pads carry their full shape on every spanned layer: KiCad's unused-layer removal is an opaque slot, so Fenolite may report more on inner layers (documented difference).
   - An item that cannot be shaped is counted and reported as `copper.item-unsupported`, never skipped in silence.
   - Rejected: graphics and texts on copper layers now (no typed net on them in the model).

4. **Pairs and findings.** Two items are judged when they share a copper layer and their nets differ; two items of one net, and two items without a net, are not; an item without a net is judged against every netted item. Candidates come from one STR index per layer over boxes grown by `⌈max_value / 2⌉` on each item, so no pair within its clearance is missed. Each item pair gives at most one finding: a short on any shared layer wins over clearance, and the first layer in table order is named.
   - Rejected: one finding per layer for vias and through-hole pads (the same defect repeated per layer).
   - Rejected: skipping netless copper. A netless track touching a net is exactly the kind of copper KiCad may re-assign on load.

5. **Clearance in force, defined from the model, combined as KiCad is measured to combine it.** For a pair on a layer: the governing rule is the last matching `clearance` rule in `rule_order` (either item order, `Rule.layers` honoured, names compared without regard to case), and an `ignore` rule silences the pair. Without a rule, the larger clearance of the two nets' classes applies (a net without a class takes the class named `Default`), raised to a positive board minimum, which also applies alone (`H-K-PRO-FLOOR`, `H-K-PRO-MIN-KEYS`). With a rule, its `min` applies; two switches carry c0026's measured tables for the major judged: `rules_over_classes` false takes the larger of the rule and the classes, and `floor_over_rules` true raises the rule to the board minimum. Both default to true, the claims c0026's tables ship with. When nothing gives a value, the pair is unset: it is judged for shorts only, counted, and one info reports the count.
   - `rule_precedence` re-implements `rulemap.rule_order` in `checks` (which cannot import `backends.kicad`); a unit test asserts that the two orders are equal on generated rule sets.
   - Case: `Selector.matches` is case-sensitive; the resolver compares case-folded copies of selectors and subjects, so the model's own semantics stay unchanged.
   - Arcs take `item_kind track`; fills take `zone`.
   - The switches live in `DesignRules`, filled by the KiCad adapter from `lowering.RULES_OVER_CLASSES` and `lowering.FLOOR_OVER_RULES["min_clearance"]`, so `checks` never imports `backends.kicad` and never restates c0026's measurement.
   - Fallback: if `H-K-COPPER-RESOLVE` is refuted on a major, the resolver follows the measurement, the row gets a `-2` successor, and `docs/formats/kicad/copper.md` records it; a refutation of c0026's rows changes c0026's tables, which the switches follow with no change here.
   - Rejected: the maximum of every matching rule and class value. Among rules it contradicts `H-K-DRU-ORDER`; between a rule and the classes, c0026's measurement decides.
   - Rejected: a second measurement of rule over class and floor over rule here. c0026 owns it; this change's parity rows re-check it through the switches.
   - Rejected: a default clearance when nothing is set. Fenolite ships no requirement values (`rules-model`, "Fenolite lowers only the design's rules").

6. **Rules come from the project's own files, through an injected source.** The clearance KiCad enforces lives in `<stem>.kicad_pro` (classes, assignments, floor) and `<stem>.kicad_dru` (custom rules), for native and built input alike: a built project's `Default` class and floor come from c0010's template, and c0019 merges user rules. `backends.base` gains `DesignRules` and the `@runtime_checkable` protocol `DesignRulesSource`; `KicadBackend.design_rules(design, project)` reads the two files of the copy set and calls `copperrules.design_rules_from_texts`, which applies `read_project`, `apply_project` and `read_rules` and counts opaque clearance rules. `run_checks` passes the validator as the rules source when it satisfies the protocol, so `run_checks` keeps c0013's signature. `design_rules` is not a backend operation, so `CapabilityReport.operations` and "Write capability fields" are untouched.
   - Unread files and opaque clearance rules give `copper.rules-incomplete` and an `UNVERIFIED` stage, never a crash.
   - Rejected: the `.fenolite/` model only (misses the template's `Default` class and floor and the user's merged rules).
   - Rejected: a new `run_checks` parameter (a MODIFIED delta of c0013's "Check stages and statuses").
   - Rejected: enriching `Validation.read.design` inside `validate` (changes c0013's "Validation operation" and every stage that reads it).

7. **Pads through c0028's frame.** The stage takes pads from the validator when it satisfies c0028's `BoardFrame` (`KicadBackend` does), the guard from `KicadBackend` directly; `run_checks` keeps its signature. Each `PadCopper` entry becomes `Thick(entry.core, entry.width, entry.filled)` on `entry.layer`, with no conversion. An entry with `exact=False` is a superset of the pad: judged as given, it never hides a clearance violation, and a short it gives says "approximated pad shape" in its message; such entries are counted, and the false shorts they may cause near chamfers are a documented difference. Without a frame, pads are unsupported items (`UNVERIFIED`), so the check never claims more than it saw.
   - `np_thru_hole` pads, whose records c0028 leaves without copper entries, and pads without a copper layer are not copper and are never counted as unsupported; a pad of another kind with a copper layer but no entry is.
   - An entry that `Thick` refuses (`GeometryError`) makes its pad an unsupported item, never a crash: c0028's `PadCopper` refuses the degenerate cores it can see, but `backends.base` cannot import `Polygon`, so a filled ring that `Polygon` refuses can still reach this change.
   - Interface used from c0028: `BoardFrame.board_pads(design, *, issues=None) -> tuple[BoardPad, ...]`; `BoardPad.ref`, `number`, `pad_id`, `net_id`, `kind`, `copper`; `PadCopper.layer`, `core`, `width`, `filled`, `exact`. This answers c0028's open question 1: yes, and c0028 may call `thick_closer_than` in its own tests.
   - Rejected: computing board-frame pads here (the duplication the dogfood script got wrong at 270°).

8. **Zones.** Fills are copper exactly as stored; outlines are not, because a pour is designed to flow around other nets. Outlines feed one Fenolite rule: zones of different nets, equal priority and a shared layer whose outlines intersect give `copper.zone-overlap` (warning), since the fill of the overlap depends on the filler's order. KiCad's outcome on such zones is recorded (`copper-zone-overlap`) but not required.
   - The zone's own clearance is not applied. KiCad's DRC applies it to fills (0.5 mm when the zone sets none; c0031's probe `zone-clearance-drc`). The zone's own clearance in the copper check: a v0.2a follow-up to c0029, once c0031 has typed it (Open Questions). Until then it is a documented difference in `docs/formats/kicad/copper.md`, and the fill parity bench sets it to 0 (Decision 13).
   - Rejected: outlines as copper (would flag every pour against every other net inside it).
   - Rejected: computing fills (c0015).

9. **One stage, `copper.clearance`, between `erc.lite` and `drc.kicad`.** It runs on the board model that `run_checks` read once, for native and built input (the board is the layout authority). It is in `DEFAULT_STAGES` and not in `ORACLE_STAGES`, so `--stages copper.clearance` needs no `kicad-cli`, and it runs before KiCad's DRC.
   - **MODIFIED delta, archive-order dependency.** `specs/verification-loop/spec.md` MODIFIES c0020's ADDED requirement "Stages added for findings and round trips", with c0020's full text copied and edited: the tuple gains `copper.clearance`, and the first sentence and the stage bullets say which change adds which stage; `copper.clearance` stays out of `ORACLE_STAGES`; `run_checks` passes the copper inputs; the stage function is `checks.copper.copper_stage`; the default-stage scenario and the read-only scenario list the new stage; new scenario "Copper stage needs no kicad-cli". `openspec validate --strict` accepts it; `openspec archive` succeeds only after c0020 is archived, which the order guarantees. Task 11.2 re-checks the text against c0020's archived version.
   - Rejected: an ADDED requirement restating `STAGE_ORDER` (two contradicting requirements in the living spec).
   - Rejected: an opt-in stage (the guard against shorts should run by default) and an oracle stage (it needs no tool).

10. **Codes and severities.** Six codes: `copper.short` (error), `copper.clearance` (the governing rule's severity, `error` for class and floor values), `copper.zone-overlap` (warning), `copper.rules-incomplete` (warning), `copper.item-unsupported` (warning), `copper.clearance-unset` (info). Shorts are always errors: they are physical defects. Of the last three codes, `copper.rules-incomplete` and `copper.item-unsupported` lower the stage to `UNVERIFIED`, because part of the copper or of the rules went unjudged; `copper.clearance-unset` does not, because the pairs it counts were judged for shorts as the model asks.
    - Rejected: honouring KiCad's project `rule_severities` and exclusions. A project could then silence the guard, and Fenolite's verdict would depend on a GUI preference (documented difference).

11. **The guard lives in `cli/cmd_build.py`, on the triad it is about to write.** After `build_design` returns its files, `cmd_build` reads the planned board back with `read_board`, applies the planned project and rules texts with `design_rules_from_texts`, takes pads from `KicadBackend`'s frame and calls `check_copper`. `--copper-check refuse` (default) adds the copper issues with their severities, so c0019's "Build command" rule returns no planned write and exits 5; `--copper-check warn` reports copper errors as warnings and writes. `result.copper_check` reports mode, counts, rules and evidence. The guard judges the bytes that will be written, preserved copper included, with the same code as the stage. Build orchestration already lives in `cmd_build` plus `lens/build.py`, as the project plan's layering resolution puts it.
    - Rejected: MODIFIED `package-layering` with `lens → checks`. `lens` would reach `geometry` through `checks`, against c0019's text ("`lens` never imports `geometry`"), and the authoring lens would depend on the verifier.
    - Rejected: an injected callable in `build_design`. The verifier's codes would join `BuildOutput.issues`, the build's own findings, and a Python caller who injects nothing would still be unguarded; the step in `cmd_build` keeps the authoring lens free of the verifier.
    - Rejected: a guard in `write_board` or `write_triad`. `backends.kicad` cannot import `checks`, and the writer stays a serializer.
    - Rejected: judging `BuildOutput.design` instead of the read-back text. It would not be the bytes KiCad reads.
    - Rejected: an `off` mode. `warn` is the escape hatch; a check that can be switched off silently is not a guard.
    - Python callers of `build_design` are not guarded; `docs/dsl.md` shows the `check_copper` call that gives the same verdict.

12. **The re-net is probed first, and nothing depends on it.** Task group 2 builds two `_rulebench` benches (dangling and anchored via) on both majors and records five probes: the IPC-D-356 via record's net (`read_ipcd356`), `shorting_items` in the DRC report, and on 10.0 the via's net after `pcb upgrade`. The probes settle or refute `H-K-VIA-RENET` per major; the DRC types naming the via are recorded as supporting data.
    - Rejected: GUI-only verification (not repeatable, no artefact).
    - Rejected: making the guard depend on the outcome. The guard catches shorts before any tool sees them.

13. **Parity on canaries, not full parity.** Benches per pair kind and per clearance source, at overlap, touch, `c − 10 µm`, `c` and `c + 10 µm`, on both majors (fills on 10.0.6). Benches without a project setting use c0018's `_rulebench`, a `{}` project and rules that select the probe nets only, as "Rules proofs carry a canary" asks. Benches that need net classes or a board minimum are written through c0010's triad path with c0010's canary scoped to `net CANARY_A`, and any custom rule after it: this is the departure c0010's net-class oracle already made, because the unconditional canary (3 mm on every pair) would govern every pair over the classes, and a `{}` project holds no class or floor. Verdicts map from the report by type and item uuids (`H-K-DRC-TYPES`, `H-K-DRC-UUID`). The touch type and the `c − 1 µm`, `c − 1 nm` rows are recorded only: KiCad may apply a tolerance at the boundary, and Fenolite stays strict.
    - The fill bench writes its zone with `(connect_pads (clearance 0))`, inserted by token edit because c0031's writer comes later. Without it KiCad applies its default zone clearance of 0.5 mm to the fill, above every `c` of the rows, and the row would measure the zone's own clearance, which this check does not apply (Decision 8).
    - Fallback: a refuted pair kind either gets a shape rule that explains the measurement (recorded with a `-2` successor) or becomes a documented difference in `docs/formats/kicad/copper.md`, and `copper.EVIDENCE` stays `INFERRED`.
    - Rejected: comparing whole demo boards with KiCad's DRC as a gate (full parity, out of scope); the measurement records counts only.

14. **Cost.** One index per layer; each arc polygonised once; each filled ring gets a lazily built edge index, queried with the other shape's box grown by the clearance; the resolver memoises by `(kinds, nets, refs, layer)`. `tests/corpus/test_copper_perf.py` records counts and times on the 21 readable demo boards with a 0.2 mm test rule, never asserted.
    - Cut if a demo board takes more than 60 s locally: fills are judged edge-indexed only against items whose box meets the fill's box, and the measurement drops to 5 boards.

15. **Locations and determinism.** `where` names both items (`REF-PIN` for pads, `provenance.locator` otherwise, a fill by its zone), the message gives the layer and the point in exact millimetres, and findings sort by code, `where`, message, as c0013 requires of every stage.

16. **No model, schema or FEN-code change; one MODIFIED delta.** The only MODIFIED requirement is c0020's "Stages added for findings and round trips" (Decision 9). c0019's MODIFIED design-dsl requirements ("Build command", "Build issue codes", "Build evidence") are not modified: the ADDED "Copper guard before writing" adds an option, a step of `cmd_build` and a result key, as "Build command" allows, and its codes are not build findings; they pass through the `build` envelope under the sentence of "Build issue codes" that lets later requirements add codes (c0019 Decision 23), and the requirement names it.

## Files and public API

| file | public API |
|---|---|
| `src/fenolite/geometry/thick.py` (new) | `@dataclass(frozen=True, slots=True) class Thick(core: tuple[Point, ...], width: int, filled: bool = False)`; `thick_bbox(t: Thick) -> BBox`; `thick_touch(a: Thick, b: Thick) -> bool`; `thick_closer_than(a: Thick, b: Thick, limit: int) -> bool`; `thick_gap_floor(a: Thick, b: Thick) -> int`; `thick_witness(a: Thick, b: Thick) -> Point` |
| `src/fenolite/geometry/__init__.py` (extended) | re-exports `Thick`, `thick_bbox`, `thick_touch`, `thick_closer_than`, `thick_gap_floor`, `thick_witness` |
| `src/fenolite/checks/clearance.py` (new) | `@dataclass(frozen=True, slots=True) class Clearance(value: Nm \| None, severity: Literal["error", "warning"] \| None, source: str = "")`; `rule_precedence(rules: Sequence[Rule]) -> tuple[Rule, ...]`; `class ClearanceResolver`: `__init__(self, design: Design, *, min_clearance: Nm \| None = None, rules_over_classes: bool = True, floor_over_rules: bool = True)`, `subject(self, kind: CopperKind, net_id: str \| None, *, ref: str \| None, layer: str) -> RuleSubject`, `resolve(self, a: RuleSubject, b: RuleSubject) -> Clearance`, `max_value: Nm` |
| `src/fenolite/checks/copper.py` (new) | `ARC_TOL_NM = 1_000`; `CopperKind = Literal["track", "arc", "via", "pad", "fill", "zone"]`; `@dataclass(frozen=True, slots=True) class CopperRef(kind: CopperKind, where: str, entity_id: str, net: str)`; `class CopperFinding(code: str, severity: Severity, layer: str, at: Point, items: tuple[CopperRef, CopperRef], gap: Nm, clearance: Nm \| None, source: str, message: str)`; `class CopperReport(findings: tuple[CopperFinding, ...], issues: tuple[Issue, ...], summary: Mapping[str, object], evidence: Evidence)`; `check_copper(design: Design, *, pads: Sequence[BoardPad] \| None, min_clearance: Nm \| None = None, rules_over_classes: bool = True, floor_over_rules: bool = True, arc_tol: int = ARC_TOL_NM, inputs: Sequence[Evidence] = ()) -> CopperReport`; `copper_stage(design: Design \| None, *, project: ProjectSet, rules_source: DesignRulesSource \| None, frame: BoardFrame \| None, evidence: Evidence) -> StageResult`; `EVIDENCE: Evidence` (`INFERRED`; `H-K-COPPER-SHAPES`, `H-K-COPPER-RESOLVE`, `H-K-COPPER-ZONES`) |
| `src/fenolite/checks/stages.py` (c0013, c0020; extended) | `STAGE_ORDER` with `copper.clearance`; `run_checks` passes the board model, `Validation.read.evidence`, the project set and the narrowed validator to `copper_stage` |
| `src/fenolite/checks/codes.py` (c0013; extended) | six `copper.*` rows |
| `src/fenolite/checks/__init__.py` (c0013; extended) | re-exports `check_copper`, `CopperReport` |
| `src/fenolite/backends/base.py` (extended) | `@dataclass(frozen=True, slots=True) class DesignRules(design: Design, min_clearance: Nm \| None = None, rules_over_classes: bool = True, floor_over_rules: bool = True, opaque_clearance_rules: int = 0, unread: tuple[tuple[str, str], ...] = (), evidence: Evidence = Evidence())`; `@runtime_checkable class DesignRulesSource(Protocol)`: `design_rules(design: Design, project: ProjectSet, *, issues: list[Issue] \| None = None) -> DesignRules` |
| `src/fenolite/backends/kicad/copperrules.py` (new) | `design_rules_from_texts(design: Design, *, project_text: str \| None, rules_text: str \| None, major: int = versions.DEFAULT_TARGET, file_stem: str = "", issues: list[Issue] \| None = None) -> DesignRules` (switches from c0026's `lowering.RULES_OVER_CLASSES` and `lowering.FLOOR_OVER_RULES`) |
| `src/fenolite/backends/kicad/backend.py` (extended) | `KicadBackend.design_rules(design, project, *, issues=None) -> DesignRules`; `_RULES_SOURCE: DesignRulesSource = KicadBackend()` (checked by pyright) |
| `src/fenolite/cli/cmd_build.py` (c0011, c0019; extended) | `--copper-check refuse\|warn` (default `refuse`); `COPPER_CHECK_MODES = ("refuse", "warn")`; `copper_guard(files: Mapping[str, bytes], *, name: str, mode: str) -> tuple[tuple[Issue, ...], dict[str, object]]`; `result.copper_check` |
| `src/fenolite/backends/kicad/PROVENANCE.md` | row for `copperrules.py` (facts only; S-0010, S-0038) |
| `tests/_copper.py` (new) | `bridged_project(tmp_path: Path, *, major: int) -> Path`; `bridge_pads(text: str, ref: str, from_pad: str, across_pad: str) -> str`; `thick_cases()` (generated shapes for the brute-force tests) |
| `tests/unit/geometry/test_thick.py`, `tests/unit/checks/test_clearance.py`, `test_copper.py`, `test_copper_stage.py`, `tests/unit/backends/kicad/test_copperrules.py`, `tests/unit/cli/test_build_copper_guard.py` (new); `tests/unit/backends/test_base_types.py`, `tests/unit/cli/test_check_cmd.py`, `test_check_readonly.py` (extended) | hermetic tests |
| `tests/kicad/copper/_benches.py`, `test_via_renet.py`, `test_copper_parity.py`, `test_parity_bench.py` (new); `tests/kicad/rules/_rulebench.py` (rows `arc_pair`, `via_pair`, `pad_track`, `tht_track`, `fill_track` added); `tests/kicad/_probes.py` (rows added) | `needs_kicad`, major-aware; `test_parity_bench.py` hermetic |
| `tests/corpus/test_copper_perf.py` (new) | `needs_corpus`, `slow` |
| `docs/formats/kicad/copper.md` (new) | fact table (re-net, DRC types, resolution, fills) and the supported-cases table against KiCad's DRC |
| `docs/evidence/copper-check.md` (new) | counts and timings per demo board |
| `docs/geometry.md`, `docs/cli-contract.md`, `docs/dsl.md` | thick shapes; the stage, the codes and `--copper-check`; the `check_copper` recipe for Python callers |
| `docs/evidence/kicad/probes/9.0.9.json`, `10.0.6.json` (regenerated) | `copper-renet-*`, `copper-parity-*`, `copper-resolve-*`, `copper-touch-type`, `copper-boundary-*`, `copper-zone-overlap` |

Layering: `geometry/thick.py` imports `core` and `geometry`; `checks/clearance.py` and `checks/copper.py` import `core`, `model`, `geometry` and `backends.base`; `backends/kicad/copperrules.py` imports `core`, `model`, `backends.base` and `pro`, `dru`, `lowering`, `versions` of its own package; `backends.base` still imports only `core` and `model`; `cmd_build` imports `checks` and `backends`. Every edge is in "Allowed import edges", unchanged.

## Sources registered by this change

None. S-0115 to S-0119 stay unused. Cited: S-0010 and S-0038 (KiCad 9.0 and 10.0 board-editor manuals: net classes, custom rules and their precedence, board-setup minimums, DRC), S-0019 and S-0020 (IPC-D-356 observations; `kicad-cli` 10.0.6 as oracle), S-0029 (the pinned 9.0.9 image), S-0022 and S-0037 (CLI manuals: `pcb drc`, `pcb export ipcd356`, and `pcb upgrade` on 10.0 only, which `KicadCli.upgrade_board` enforces), S-0055 and S-0056 (DRC report keys). Task 1.1 widens the "used for" cell of S-0010 and S-0038 (the clearance of two classes, rule over class, minimums as floors), S-0020 and S-0029 (the re-net and parity observations).

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-K-VIA-RENET | `kicad-cli` 9.0.9 and 10.0.6 load a via of net `GND` whose copper touches only a track of net `VIN` on `VIN`: the IPC-D-356 export lists it under `VIN`, `pcb drc` reports no `shorting_items` for it, and a 10.0 re-save (`pcb upgrade`) writes it on `VIN`. Reported by a Fenolite dogfood build on 2026-10-02, without a committed artefact; the probe's runs are recorded under S-0020 (10.0.6) and S-0029 (9.0.9) | `tests/kicad/copper/test_via_renet.py` | per major: `copper-renet-export` = `present`, `copper-renet-drc` = `absent`, and on 10.0 `copper-renet-resave` = `present`; the anchored probes are supporting data |
| H-K-COPPER-SHAPES | KiCad's DRC judges copper as Fenolite's thick shapes do (a track is its centre segment swept by its width, an arc likewise within 2 µm, a via a disc of its diameter on each spanned layer, a pad the core and width of c0028's record), so the `shorting_items`, `clearance` or clean verdict of each pair agrees at an overlap, at `c − 10 µm`, at `c` and at `c + 10 µm` (S-0010, S-0038) | `tests/kicad/copper/test_copper_parity.py -k parity` | on 9.0.9 and 10.0.6, every `copper-parity-<kind>` probe = `equal`; touch type and boundary rows recorded |
| H-K-COPPER-RESOLVE | Beyond what c0026 measures (rule over class, floor over rule), KiCad's clearance in force for a pair follows Fenolite's resolver: without a custom rule the larger clearance of the two nets' classes applies; a rule with a condition stands to the classes as an unconditional one does (`H-K-PRO-MIN-CLASS`); an `ignore` rule silences the pair; and a rule on `A.Type == 'Track'` governs arc tracks (S-0010, S-0038) | `tests/kicad/copper/test_copper_parity.py -k resolve` | on 9.0.9 and 10.0.6, every `copper-resolve-<case>` probe = `equal`, with the switches taken from c0026's tables for the running major |
| H-K-COPPER-ZONES | KiCad 10.0.6 judges the stored `filled_polygon` of a target-10 board as copper exactly, with no added stroke, when the zone's own clearance is 0 (S-0038) | `tests/kicad/copper/test_copper_parity.py -k fill` | on 10.0.6, `copper-parity-fill-track` = `equal` |

The rows get backend `kicad`, result `pending`, level `UNVERIFIED` for `H-K-VIA-RENET` (reported, unverified) and `INFERRED` for the three `H-K-COPPER-*` rows, in task 1.1. Ids used without changing their level: `H-K-DRU-ORDER`, `H-K-DRU-COND`, `H-K-DRU-KIND`, `H-K-PRO-FLOOR`, `H-K-PRO-PATTERNS`, `H-K-TOK-RULES-SILENT`, `H-K-PCB-READ`, `H-K-PCB-POS` (IPC-D-356 via records: reference `VIA`, net name field), `H-K-DRC-TYPES` and `H-K-DRC-UUID` (c0020), and `H-K-PRO-MIN-CLASS`, `H-K-PRO-MIN-RULE` and `H-K-PRO-MIN-KEYS` (c0026). No id owned by c0015, c0028, c0030 or c0031 is cited.

## Evidence level per behaviour (before merge)

| behaviour | level required | proof |
|---|---|---|
| Thick-shape gaps | mechanical (exact; brute force over `Fraction`) | `tests/unit/geometry/test_thick.py` |
| Clearance resolution logic | mechanical (unit tests; `rule_precedence` equals `rule_order`) | `tests/unit/checks/test_clearance.py` |
| Clearance in force equals KiCad's | KICAD-VERIFIED (9.0.x, 10.0.x), `H-K-COPPER-RESOLVE` | `test_copper_parity.py -k resolve` |
| Verdict parity per pair kind | KICAD-VERIFIED (9.0.x, 10.0.x), `H-K-COPPER-SHAPES` | `test_copper_parity.py -k parity` |
| Fill parity | KICAD-VERIFIED (10.0.x), `H-K-COPPER-ZONES` | `test_copper_parity.py -k fill` |
| Zone overlap warning | INFERRED (Fenolite rule); KiCad's outcome recorded | `test_copper.py -k zone_overlap`; probe `copper-zone-overlap` |
| Re-net on load | recorded per major (`H-K-VIA-RENET`, UNVERIFIED until run; settled or refuted) | `test_via_renet.py` |
| Design rules adapter | `Evidence.combine(pro.EVIDENCE, dru.EVIDENCE)` of what was read | `test_copperrules.py` |
| `copper.clearance` stage and the guard | `Evidence.combine` of `copper.EVIDENCE`, `pcb.EVIDENCE` (`INFERRED`, `H-K-PCB-READ`), the rules adapter and c0028's frame; `UNVERIFIED` with `copper.rules-incomplete` or `copper.item-unsupported` | `test_copper_stage.py`, `test_build_copper_guard.py` |
| Stage is hermetic and read-only | mechanical | `test_check_cmd.py`, `test_check_readonly.py -k new_stages` |
| Cost | measured and recorded, never gated | `test_copper_perf.py` |

`copper.EVIDENCE` is `INFERRED` and stays `INFERRED` after task 11.2 settles the three `H-K-COPPER-*` rows: the canaries cover pair kinds and clearance sources on benches, and fills on 10.0 only, not every board. c0027, c0028 and c0030 keep their module constants at `INFERRED` for the same reason, so `check_copper(…, inputs=())` never reports `KICAD-VERIFIED` for an arbitrary board. The stage's envelope stays `INFERRED` while the board reader is. This change does not merge while `H-K-COPPER-SHAPES` or `H-K-COPPER-RESOLVE` is below `KICAD-VERIFIED` on 9.0.9 or 10.0.6, unless the fallback of Decision 5 or 13 is applied and recorded for that major.

## Budget (about 2.4 weeks; no roadmap line, new change)

| work | days |
|---|---|
| registers, provenance, `copper.md` skeleton, c0028 alignment | 0.5 |
| re-net probe on both majors | 1.0 |
| `geometry/thick.py` and its exact tests | 1.5 |
| clearance resolver | 0.75 |
| copper items, `check_copper`, zone overlaps | 1.75 |
| design rules source and the KiCad adapter | 0.5 |
| `copper.clearance` stage and `check` wiring | 0.75 |
| build guard | 0.75 |
| parity canaries on both majors (tasks 9.1 rule benches, 9.2 class, floor and resolution benches, 9.3 fill and zone benches with the 9.0.9 run) | 3.0 |
| measurement on demo boards | 0.5 |
| docs | 0.25 |
| closing | 0.75 |
| **total** | **12.0** |

c0008 took about three times its plan line, so this estimate is itemised per task. Cut order: (1) the zone-overlap rule, its requirement and its probe (−0.25); (2) the `via_pair` and pad–pad parity rows (−0.25); (3) the measurement on 5 boards instead of 21 (−0.25); (4) the 9.0.9 run of the class and floor benches becomes supporting data, rule benches stay on both majors (−0.5). Not optional: the exact kernel, shorts, the clearance resolution, the stage, the guard in `refuse` mode, the re-net probe on both majors, and parity for tracks, vias and SMD pads on both majors.

## Risks / Trade-offs

- [c0028's review renames its records] → task 1.3 re-checks the names against c0028's archived text before code starts; the stage works without a frame (pads unsupported, `UNVERIFIED`).
- [c0026's tables differ between majors] → the switches follow them per major; the parity rows run with the switches of the running major.
- [KiCad applies a tolerance at the clearance boundary] → `copper-boundary-*` rows record it; Fenolite stays strict; the difference is documented.
- [False positives: net ties, removed unused layers, roundrect corners if c0028 cannot read the ratio] → documented differences; `--copper-check warn`; `copper.item-unsupported` where a shape is missing.
- [Large pours make fills slow] → edge index per fill, memoised resolution, measurement and the cut of Decision 14.
- [`H-K-VIA-RENET` refuted] → the row records the observed behaviour; the guard and the stage are unchanged.
- [`H-K-COPPER-RESOLVE` refuted on a case] → the resolver follows the measurement (Decision 5); the row gets a `-2` successor.
- [c0020's text changes in review] → the MODIFIED copy is re-based at archive (task 11.2); if c0020 relaxes `STAGE_ORDER` to a relative order, the delta becomes an ADDED requirement.
- [Opaque custom rules on native projects] → `copper.rules-incomplete`, stage `UNVERIFIED`; KiCad's DRC (c0020) still judges them.
- [Overrun] → 12 days stated, with the cut order above.

## Migration Plan

- Additive: a geometry module, two `checks` modules, an adapter module, a protocol, a stage, six codes, a build option, tests and docs. No model, schema or FEN-code change. The new default stage adds findings to `check` runs; boards with real shorts now exit 5 under `check` and refuse under `build` until fixed or built with `--copper-check warn`.
- Rollback: remove the modules, the stage from `STAGE_ORDER` (restoring c0020's text), the six codes, the build option and the probe rows.

## Open Questions

- **Guard default.** Default `refuse`; `warn` on request. To confirm.
- **Stage name.** Default `copper.clearance`, with codes `copper.*`.
- **Netless copper.** Default: judged against netted copper, not against other netless copper.
- **A project without classes.** Default: no clearance in force (`copper.clearance-unset`); KiCad's built-in `Default` values are not assumed, since Fenolite ships no rule values. Native boards with a real project get the project's `Default` class.
- **c0028 interface.** Resolved with c0028's text: `BoardFrame.board_pads` in `backends.base`, satisfied by `KicadBackend`, records as in Decision 7. If c0028's review renames them, c0028's names win and task 1.3 renames them here.
- **c0026's open question 6 (how c0029 uses the minimums).** Default: the minimum comes from `ProjectInfo.floors["clearance"]` of the project file written next to the board, and the combination follows c0026's tables through `DesignRules` (Decision 5); `project_minimums` and `lower_minimums` are not called.
- **The zone's own clearance in the copper check.** Default: a v0.2a follow-up to c0029 (`docs/roadmap.md`, v0.2a follow-ups) adds it to the clearance in force of fill pairs, as the floor that KiCad's DRC applies (c0031's probe `zone-clearance-drc`), through an ADDED `copper-check` requirement, after c0031 has typed `ZoneSettings.clearance`. Until then it is a documented difference (Decision 8).
- **Zone overlap severity.** Default `warning`, because KiCad's own verdict is only recorded.
- **Arc tolerance.** Default 1 µm (band 1.001 µm per arc).
- **Fills on 9.0.** Default: judged as stored; 9.0 fill parity waits for c0031's `filled_areas_thickness` fix.
- **Project severities and exclusions.** Default: not applied; Fenolite's verdict is the model's.
- **Net ties.** Default: reported as shorts until a footprint's net-tie groups are typed (a later change).
- **Built input source.** Default: the project files next to the board, not `.fenolite/`, for native and built input alike.
- **Python API.** Default: `build_design` stays unguarded; `docs/dsl.md` documents the `check_copper` call.
- **c0020's exact `STAGE_ORDER`.** Default: this change MODIFIES c0020's ADDED requirement (archive-order dependency, Decision 9). If c0020's review relaxes it to a relative order that later changes extend by ADDED requirements, this delta becomes an ADDED requirement and no MODIFIED delta remains.
- **Batch questions for the user.** None of the open questions of the batch concerns this change.
- **Register guard (c0014).** This design cites `H-K-VIA-RENET` and the three `H-K-COPPER-*` ids before task 1.1 registers them, as "Ids proposed by active changes" allows. Task 1.1 is the first implementation commit.
