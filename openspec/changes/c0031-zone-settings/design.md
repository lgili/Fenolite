## Context

- **The gap (dogfood buck board, A4).** The board was built through Fenolite's public API only. It poured `GND` on both copper layers, but could not ask for a 0.3 mm pour clearance, a solid connection on the exposed pad or thermal reliefs elsewhere. `model.board.Zone` holds `outline`, `name`, `layers`, `net_id`, `priority` and `fills` only.
- **What exists.**
  - c0009's reader keeps every zone setting as an opaque child (`docs/formats/kicad/board.md`, section "What the reader models": `hatch`, `connect_pads`, `min_thickness`, `filled_areas_thickness`, `fill`, `placement`, `attr`, `locked`). Pad `zone_connect` is opaque too.
  - c0017's writer writes a created zone with `net`, `net_name`, `layer`, `uuid`, `name`, `priority`, `polygon` and `filled_polygon` only (`pcb._emit_zone`, `CANONICAL_ORDER["zone"]`). KiCad then applies its own loader defaults.
  - The writer already has the two hooks this change needs. `_Writer.absent(entity, created)` leaves out fields whose value is what the reader gives a missing child. `_Writer.reconcile` handles projected opaque slots ("Projected fields on write").
  - c0011's DSL has no zones: `Design.board(width, height, copper)` and `Part.place` only. `lens.build.build_design` keeps `Board.zones` of the model it is given.
  - c0019 keeps every board zone with its slots ("Copper items follow their nets"). Its `zone_digest` covers "the texts of the zone's other opaque slots (its fill settings)". c0015, on the roadmap, refills through `kicad-cli` 10 and lifts `filled_polygon` geometry into `Zone.fills`.
- **KiCad facts observed at proposal time (2026-10-02).** Scratch scripts were run on authored canaries; nothing was committed. Each fact becomes a hypothesis row and is settled again by the tasks.
  - **Loader defaults.** `kicad-cli` 10.0.6 `pcb upgrade --force` was run on a zone without `connect_pads`, `min_thickness` and `fill`. The re-save writes `(hatch none 0.5) (connect_pads (clearance 0.5)) (min_thickness 0.25) (fill (thermal_gap 0.5) (thermal_bridge_width 0.5) (island_removal_mode 0))`. A refill gives the same fills as the explicit values 0.5/0.25/thermal/0.5/0.5 (`H-K-ZONE-DEFAULTS`).
  - **GUI defaults.** The 10.0.6 GUI save of a new project (`tests/data/kicad/project/empty_10.kicad_pro`, S-0020) stores the same values in `board.design_settings.defaults.zones`: `min_clearance` 0.5, `min_thickness` 0.25, `pad_connection` 1, `thermal_relief_gap` 0.5, `thermal_relief_spoke_width` 0.5, `fill_mode` 0, `remove_islands` 0, `min_island_area` 10, `hatch_thickness` 1.0, `hatch_gap` 1.5, `hatch_orientation` 0, `hatch_smoothing_level` 0, `hatch_smoothing_value` 0.1, `corner_smoothing` 0, `corner_radius` 0, `border_display_style` 2 and `border_hatch_pitch` 0.5. The demo census agrees: of the 67 zones at tag 10.0.6, 47 have a minimum thickness of 0.25, 48 a gap of 0.5, 46 a spoke of 0.5 and 56 `(hatch edge 0.5)` (S-0058, counts only).
  - **Refill measurements (10.0.6, `pcb drc --refill-zones --save-board`, exact kernel).** These are `H-K-ZONE-CONNECT` and `H-K-ZONE-GEOM`.
    - Thermal reliefs give four spokes per pad: on the axes for a rectangular SMD pad, at 45° for a round THT pad.
    - `connect_pads yes` covers the relief ring. `no` isolates the pad (`isolated_copper`). `thru_hole_only` is solid on SMD pads and thermal on THT pads.
    - A pad `zone_connect` 0/1/2/3 means none/thermal/solid/thru-hole-thermal. It overrides a footprint `zone_connect`, which overrides the zone.
    - The fill keeps the larger of the zone clearance, the `Default` class clearance and a custom rule, plus about 0.5 µm. The measured gaps were 0.300499, 0.200499 and 0.600499 mm for a zone clearance of 0.3, 0.1 and 0.3 mm with a 0.6 mm rule.
    - The spoke width equals `thermal_bridge_width` (0.35, 0.25, 0.5 mm), and the relief gap equals `thermal_gap` within 1 nm.
    - `island_removal_mode` 0/1/2 removes, keeps, or keeps above `island_area_min` an enclosed island; a kept island is written `(island yes)`.
    - A minimum thickness of 0.25 mm removes a 0.2 mm channel, and 0.15 mm keeps it.
    - A hatched fill of 1/1.5 mm gives bars of 0.998 mm and holes of 1.502 mm.
  - **DRC without refill (10.0.6)** reports "zone clearance 0.5000 mm; actual 0.3000 mm" for an authored fill 0.3 mm from a pad of another net. With a zone clearance of 0.1 mm it reports nothing.
  - **Target-9 fills are inflated.** A `20241229` zone written by today's writer, without `(filled_areas_thickness no)`, is plotted by 9.0.9 (pinned image, B.Cu Gerber) and re-saved by 10.0.6 with its fill grown by `min_thickness / 2` = 0.125 mm per side, with rounded corners (26–34 mm becomes 25.875–34.125 mm). With the flag, the fill is kept as written (`H-K-ZONE-FAT9`).
  - **9.0.9 loads every form** this change writes for target 9: `pcb drc` exits 0 and writes a report for thermal, solid, none, `thru_hole_only`, a full hatch, island modes 0 and 2, smoothing, `(locked yes)`, pad `zone_connect` 0–3 and a footprint `zone_connect` (`H-K-ZONE-LOAD9`). 9.0 has no `--refill-zones` and no `pcb upgrade` (S-0037; `H-K-01`), so the meaning cannot be observed there.
  - **Forms per major (census, S-0058).** 9.0-written zones (`20241229`) write `island_removal_mode` only when it is not 0, and then also `island_area_min` (2 zones, mode 1). 10.0-written zones (`20250513`, `20260206`) always write `island_removal_mode`, and `island_area_min` only for mode 2.
  - **10.0.6 re-saves** write the `fill` children in this order: `yes`, `mode`, `thermal_gap`, `thermal_bridge_width`, `smoothing`, `radius`, `island_removal_mode`, `island_area_min`, `hatch_thickness`, `hatch_gap`, `hatch_orientation`, `hatch_smoothing_level`, `hatch_smoothing_value`, `hatch_border_algorithm`, `hatch_min_hole_area`.
    - `smoothing none` drops `radius`. A hatch smoothing level of 0 drops both smoothing children.
    - The hatch loader defaults are 1 mm, 1.5 mm, 0°, `hatch_thickness` and 0.15.
    - `hatch_border_algorithm` accepts only `hatch_thickness` and `min_thickness`.
    - `(locked yes)` sits between `net` and `layer`.
  - **Simulation.** These forms reproduce all 71 native demo zones (67 at tag 10.0.6, 4 at 9.0.9.1). They also reproduce all 355 zones of the three third-party boards upgraded by 10.0.6. 18 of those carry `(fill yes)` with no fill polygon.
  - **Usage of `zone_connect` (counts only).** The local 10.0.6 footprint libraries hold 2485 pads with `(zone_connect 2)`, 225 with 0 and 11 with 1, and 29 footprint-level `(zone_connect 1)`. 616 of the 776 footprints of `Package_DFN_QFN` have a pad with `(zone_connect 2)` (S-0018). The 21 readable demos hold 196 pads with 2 and 5 with 0, and 8 footprint-level values.
- **Environment.** `kicad-cli` 10.0.6 is installed locally. The pinned 9.0.9 image (`kicad/kicad:9.0.9@sha256:e638b79b…`, S-0029) runs locally and in the `kicad-9` job. The demo corpus is cached.
- **Working tree on 2026-10-02.** c0010 was archived while this change was written. c0011 is being implemented (`src/fenolite/dsl/`, `src/fenolite/lens/build.py`). c0019–c0021 are proposed. c0026–c0030 are proposed beside this change. c0028 MODIFIES "Identifier derivation" with a fifth case and ADDS script copper to `layout-lens`, whose merge codes are `kicad.copper.*`; this change follows both patterns (Decision 12, Migration Plan). Task 1.1 re-checks every consumed name.
- **Constraints.**
  - Stdlib only; `dsl` imports `model` only; `lens` imports `model` and `backends`, never `geometry` (`package-layering`).
  - No FEN code, no `rules-model` change, no change to the copper check.
  - Default values come from observation and public files only. KiCad's C++ source is read for keyword or version facts only.

## Goals / Non-Goals

**Goals:**
- A typed, closed description of a zone's settings, with KiCad's new-zone values as defaults, read from 9.0 and 10.0 boards and written for both targets without loss.
- A pad-level zone connection that board and library pads carry.
- `d.zone(gnd, layers=…, clearance=mm(0.3), connection="thermal")` in a design script, kept across rebuilds with the board winning, as c0019 decides for footprints.
- Proof by refill on 10.0.6 that each setting means what the model says, and proof that 9.0.9 loads every form.
- Target-9 fills plotted as written.

**Non-Goals:**
- Everything under Non-goals in the proposal.
- Judging whether fills are current (c0015 and c0019's digests).
- Encoding KiCad's range limits for settings (for example a smallest minimum thickness).

## Decisions

1. **Three modelled children, emitted whole, in each major's form.** `connect_pads`, `min_thickness` and `fill` are modelled the way c0009 models `keepout`: each is projected into the model and must be reproduced tree-equal by the emitter for the file's major ("Modelled children are reproducible").
   - The version-aware forms (Context) reproduce every corpus zone. A child that does not reproduce stays opaque and projected, with `kicad.board.kept-opaque`, so a read is never lossy. An unknown child, such as a future `fill` child, takes the same path.
   - `locked` is modelled as `(locked yes)`.
   - Rejected: a slot group per `fill` child, with the key `fill[0]`. c0009 already uses `fill[k]` for the k-th `filled_polygon`, and the groups would need more code for no corpus gain. Rejected: `Optional` fields that record which children were written (API noise).
2. **`ZoneSettings` is always present.** `Zone.settings` defaults to `ZoneSettings()`. An absent child reads as the default, which is also what KiCad assumes (`H-K-ZONE-DEFAULTS`).
   - For a read zone, the writer inserts a missing child only when its part of the model differs from the default, through c0017's `absent()` hook. An untouched board keeps its text, and RT1 holds.
   - A created zone always writes all three children, in KiCad's new-zone form, so the file does not depend on loader defaults.
   - Rejected: `settings: ZoneSettings | None`. `None` would mean "absent" on a read zone and "KiCad's defaults" on a created one, and the DSL, c0015 and c0019's digest all need a value.
3. **Defaults are KiCad's new-zone values, from observation.**

   | value | default | source |
   |---|---|---|
   | clearance, minimum thickness | 0.5 mm, 0.25 mm | GUI save `defaults.zones` (S-0020); 10.0.6 re-save of absent children; demo census |
   | connection | `thermal` | `pad_connection` 1 (S-0020); re-save writes no atom; refill shows spokes |
   | thermal gap, spoke width | 0.5 mm, 0.5 mm | S-0020; re-save; census |
   | island removal, minimum island area | `always`, 10 mm² | `remove_islands` 0, `min_island_area` 10 (S-0020); re-save writes mode 0 |
   | smoothing, radius | `none`, 0 | `corner_smoothing` 0, `corner_radius` 0 (S-0020) |
   | fill mode; hatch thickness, gap, orientation, smoothing level and value | `solid`; 1 mm, 1.5 mm, 0°, 0, 0.1 | S-0020; re-save of a bare `(mode hatch)` |
   | hatch border, minimum hole area | `hatch_thickness`, 0.15 | re-save of a bare `(mode hatch)` (not in the GUI save) |
   | outline display | `(hatch edge 0.5)` | `border_display_style` 2 and `border_hatch_pitch` 0.5 (S-0020); 56 of 67 demo zones |

   - The loader half is `KICAD-VERIFIED (10.0.x)`. That the GUI's new-zone dialog uses `defaults.zones` is `INFERRED` from the key path.
   - Rejected: values taken from KiCad's C++ headers. The source is read for keyword and version facts only.
4. **`Zone.filled` is explicit.** It is the `yes` atom of `fill`: a fill flag that KiCad keeps apart from the polygons (a zone written with polygons and no `yes` is re-saved without `yes`).
   - c0015 sets it with the fills it lifts, and c0019's `drop_stale_fills` clears it (MODIFIED "Zone fills and the staleness digest").
   - Rejected: deriving `yes` from `fills`. 18 zones of the upgraded third-party copies are filled with an empty result and would lose their modelling. Rejected: a field of `ZoneSettings` (it is state, not a setting).
5. **`Zone.locked` is modelled.** The DSL's `locked=True` writes KiCad's lock, as c0011's `place(locked=True)` does for footprints, and a lock set in KiCad is visible to the lens.
   - Rejected: leaving `locked` opaque (the script's lock could not be written).
6. **Target 9 gets `(filled_areas_thickness no)` on created zones.** Without it, 9.0.9 and 10.0.6 treat a `20241229` fill as a thin outline and grow it by half the minimum thickness (`H-K-ZONE-FAT9`). Created zones, and fills that c0015 lifts into them, would otherwise be 0.125 mm larger per side than the model.
   - A read zone is written as it was read: KiCad 9 always writes the flag (4 of 4 9.0-written zones, 53 of 53 in 9.0-format files at tag 10.0.6). A zone without it was made by another tool, and its fills mean what that tool meant. `board.md` records the pitfall.
   - For target 10 the row `zone-filled-areas-thickness` (`until_major = 9`) keeps applying.
   - Rejected: no flag (the defect stays). Rejected: inserting the flag into read zones (this changes the meaning of third-party files).
7. **Created zones are written in KiCad's new-zone form.** The form includes `(hatch edge 0.5)`, the GUI's outline display, which is cosmetic and not modelled.
   - Rejected: no `hatch` child. KiCad then shows `hatch none`, unlike a zone drawn in the GUI.
8. **Per-pad override: `Pad.zone_connection`.** `None` means that the pad follows its footprint and the zone. The shared footprint mapping (`_fpmap`) reads and writes `(zone_connect N)`, so board pads, `.kicad_mod` pads, `place_footprint` copies and `write_footprint` agree.
   - Precedence observed on 10.0.6: pad > footprint > zone.
   - The footprint-level `zone_connect`, and per-pad `thermal_gap`, `thermal_bridge_width` and `thermal_bridge_angle`, stay opaque.
   - This answers the dogfood case without new DSL surface: an exposed pad whose library footprint says `(zone_connect 2)` is solid in a thermal pour. Official QFN footprints do (616 of 776), and c0027 vendors project footprints that a user may edit.
   - Rejected: a footprint-level field, which cannot make one pad solid. Rejected: deferring; 2485 solid pads of the official libraries are opaque data today.
9. **One zone module in the backend.** `backends/kicad/zones.py` holds `project_settings`, `emit_settings`, the atom and code tables, the pad codec and the rebuild merge `merge_zones` (Decision 12). `pcb.py` (1993 lines), `_fpmap.py` and `lens.preserve` call it.
   - Rejected: more code inside `pcb.py`.
10. **The DSL declares zones; ids come from the zone name.**
    - The call is `Design.zone(net, *, layers, name=None, outline=None, priority=0, clearance=None, min_thickness=None, connection=None, thermal_gap=None, thermal_spoke_width=None, islands=None, min_island_area=None, locked=False)`.
    - The name defaults to the net's name. One zone may span several layers, as KiCad zones do. The outline defaults to the board rectangle.
    - Layers are checked against `board(copper=…)` at the call, so the build needs no new code. Area is a `"…mm2"` string.
    - Hatching and smoothing stay with the model API.
    - The model id is `derived_id("zon", "dsl", "zone:<name>")`. This needs a row in c0011's closed `KEYS` table (MODIFIED "Identifier derivation", Migration Plan).
    - Per-pad requests in the DSL are deferred (Open Questions).
    - Rejected: zone objects joined with `add()` (a second kind of member for one list).
    - Rejected: carrying per-pad requests on `Component`. That would edit c0011's "DSL to model" and "Placement of built parts", which c0027 modifies.
    - Rejected: a new `build_design` keyword. That would edit "Built project files", which c0019 and c0027 modify.
11. **The build needs no code path.** `to_model` puts the zones into `Board.zones`; `build_design` keeps them; the writer writes created zones (Decision 7).
    - Rejected: a build step that turns zone requests into model zones. The DSL already gives model zones, and a step would edit c0011's "Built project files", which c0019 and c0027 modify.
12. **Lens: match by uuid; the board wins unless the script locks the zone.**
    - Script zones are matched to board zones by KiCad uuid, which a re-save keeps (`H-K-UUID-KEEP-2`) and which the zone name fixes.
    - For a matched pair, the compared values are outline, layers, net name, priority, lock and `settings.effective()`.
    - The board wins (`kicad.zone.overridden`, info) unless the script's zone is locked. A locked zone replaces the board zone (`kicad.zone.forced`, warning) and inherits its fills for the digest to judge. This is c0019's precedence for footprints, as the brief asks ("settings edited in the GUI must win as the lens defines").
    - It is the edited-in-place model of c0028 Decision 20, which c0019 (footprints) and c0030 (fields) share; script copper follows the other, derived model of that decision. The marker is the uuid derived from the zone's own name; no marker is shared with script copper's version-8 uuids (c0028 Decision 20).
    - A zone new in the script is added.
    - A board zone whose uuid equals the uuid derived from its own name is the script's, and is an orphan when the script no longer declares it: it is removed with `kicad.zone.orphan` (warning). A zone drawn in KiCad has a random uuid, and one renamed in KiCad no longer matches its uuid, so both are kept.
    - The merge is `backends/kicad/zones.merge_zones`, called by `merge_layout`, as c0028 hands script copper to `copper.merge_copper`. Its codes form the closed table `zones.MERGE_ISSUE_CODES` of `kicad.zone.*` codes, which pass through `PRESERVE_ISSUE_CODES` and `BUILD_ISSUE_CODES` unchanged, as c0028's `kicad.copper.*` codes do: c0019's "Layout issue codes" and "Build issue codes" let every `kicad.*` code through, and "Zones declared in the script" names both. So neither text is modified.
    - The new requirement states that it replaces the zone rule of c0019's "Copper items follow their nets" for these zones, as c0028 does for script copper. That requirement's text is not modified either.
    - Rejected: the script always wins (GUI edits lost). Rejected: the board always wins with no lock (an agent could change a zone only with `--discard-layout`, which loses the routing). Rejected: matching by name (a name is not unique in KiCad). Rejected: `layout.zone-*` codes in c0019's closed table (a third MODIFIED delta of c0019, which c0028 avoids in the same way).
13. **The digest uses effective settings.** `zone_digest` adds the canonical JSON of `settings.effective()`. Values that cannot change a fill, such as hatch values of a solid fill, never drop fills. `filled` and `locked` stay out. `drop_stale_fills` clears `filled` with the fills.
    - Rejected: digesting the written children. Their form depends on the target, so c0019's "Digests ignore ids and formats" would fail.
14. **Zone clearance and rules.** KiCad keeps the larger of the zone clearance and the class or custom-rule clearance (observed), so Fenolite writes the zone clearance as given and lowers no rule for it. Board-setup minimums (c0026) are a floor for clearances; that they also floor zone fills is `INFERRED` and not relied on.
    - Without a refill, DRC applies the zone clearance to fills (observed). c0029's resolver does not, and the brief keeps the copper check out of scope. The probe `zone-clearance-drc` records the fact. The zone's own clearance in the copper check: a v0.2a follow-up to c0029 (Open Questions).
    - Custom-rule constraints `zone_connection`, `thermal_relief_gap` and `thermal_spoke_width` stay user rules in `.kicad_dru`, which c0019 merges. New rule kinds go to a v0.2a rule-kinds change (c0026 Open Question 3); "Rule kinds and limits" is a living `rules-model` requirement of c0018, which c0026 does not change.
    - Rejected: lowering the zone clearance into a custom rule (KiCad already keeps the larger value, and a rule would duplicate it). Rejected: modelling those three constraints as rule kinds (the v0.2a rule-kinds change of c0026 Open Question 3).
15. **Probes first, exact measurement.** The zone bench is built through the model API like c0018's rules bench. The probes `zone-defaults-t10` and `zone-fat9` run before the model code, with a stop rule. Refilled fills are judged with c0005's exact predicates, never by counting DRC messages.
    - 9.0.9 proves loading only, and its labels say so.
    - `zone-fat9` reads the `B.Cu` plot with a small Gerber helper (`tests/kicad/zones/_gerber.py`), because `H-K-ZONE-FAT9` is a claim about the plot, the file a fab receives, and 9.0.9 has neither `pcb upgrade` nor `--refill-zones` (S-0037). c0028 and c0030 rejected Gerber parsing because DRC canaries answered their questions. The helper reads only the subset that `docs/formats/kicad/gerber.md` records from S-0125, and it lives in `tests/`, never in `src`.
    - Rejected: GUI automation (no headless GUI). Rejected: the `pcbnew` Python module inside the image (an oracle surface beyond `kicad-cli`).

## Files and public API

| file | public API |
|---|---|
| `src/fenolite/model/board.py` (extended) | `ZoneConnection = Literal["solid", "thermal", "none", "thru_hole_only"]`; `ZoneFillMode = Literal["solid", "hatched"]`; `IslandRemoval = Literal["always", "never", "below_area"]`; `ZoneSmoothing = Literal["none", "chamfer", "fillet"]`; `HatchBorder = Literal["hatch_thickness", "min_thickness"]`; `@dataclass(frozen=True, slots=True) class ZoneHatch(thickness: Nm = 1_000_000, gap: Nm = 1_500_000, orientation: Udeg = 0, smoothing_level: int = 0, smoothing_value: str = "0.1", border: HatchBorder = "hatch_thickness", min_hole_area: str = "0.15")`; `@dataclass(frozen=True, slots=True) class ZoneSettings(clearance: Nm = 500_000, min_thickness: Nm = 250_000, connection: ZoneConnection = "thermal", thermal_gap: Nm = 500_000, thermal_spoke_width: Nm = 500_000, island_removal: IslandRemoval = "always", min_island_area: int = 10_000_000_000_000, smoothing: ZoneSmoothing = "none", smoothing_radius: Nm = 0, fill_mode: ZoneFillMode = "solid", hatch: ZoneHatch = ZoneHatch())` with `effective() -> ZoneSettings`; `Zone.settings: ZoneSettings`, `Zone.filled: bool`, `Zone.locked: bool`; `Pad.zone_connection: ZoneConnection \| None` |
| `schemas/fenolite.model.v0/board.json`, `library.json` | regenerated by `tools/gen_schemas.py` |
| `src/fenolite/backends/kicad/zones.py` (new) | `CONNECT_ATOMS: Mapping[ZoneConnection, str \| None]`; `PAD_CONNECT_CODES: Mapping[int, ZoneConnection]`; `ISLAND_CODES: Mapping[int, IslandRemoval]`; `HATCH_EDGE: Node` (`(hatch edge 0.5)`); `@dataclass(frozen=True) class SettingsRead(settings: ZoneSettings, filled: bool, locked: bool, reasons: Mapping[str, str], inexact: frozenset[str])`; `setting_parts`, `DEFAULT_PARTS`, `projection_differences` and `with_fill_flag` (what each child stands for, for the writer); `project_settings(children: Sequence[Node], *, major: int) -> SettingsRead`; `emit_settings(settings: ZoneSettings, *, filled: bool, locked: bool, major: int) -> dict[str, Node]` (keys `locked`, `connect_pads`, `min_thickness`, `fill`); `read_pad_connect(node: Node) -> ZoneConnection \| None`; `pad_connect_node(connection: ZoneConnection) -> Node`; `script_zone_uuid(name: str) -> str`; `@dataclass(frozen=True) class ZoneMerge(zones: tuple[Zone, ...], issues: tuple[Issue, ...], kept: tuple[str, ...], forced: tuple[str, ...], added: tuple[str, ...], removed: tuple[str, ...], decided: frozenset[str])`; `merge_zones(built: Design, board: Design) -> ZoneMerge`; `MERGE_ISSUE_CODES: Mapping[str, Severity]` |
| `src/fenolite/backends/kicad/pcb.py` (extended) | `ZONE_FIELDS` gains `locked`, `connect_pads` → `connection`, `min_thickness`, `fill` → `fill_settings`; `KEEPOUT_FIELDS` excludes them; `CANONICAL_ORDER["zone"]` = `net`, `net_name`, `locked`, `layer`, `layers`, `uuid`, `name`, `hatch`, `priority`, `connect_pads`, `min_thickness`, `filled_areas_thickness`, `keepout`, `fill`, `polygon`, `filled_polygon`; `CANONICAL_ORDER["connect_pads"]`, `["fill"]`, `POSITIONAL["connect_pads"]`, `["fill"]`; `CANONICAL_ORDER["pad"]` gains `zone_connect` between `net` and `uuid`; `FLOOR_HEADS` gains 13 names; the reader projects settings; the writer's `items`, `absent` and `reconcile` cover them |
| `src/fenolite/backends/kicad/_fpmap.py` (extended) | `PAD_FIELDS` gains `zone_connect` → `zone_connection`; `emit_pad` writes it |
| `src/fenolite/dsl/design.py` (c0011; extended) | `Design.zone(net: Net \| None, *, layers: Sequence[str], name: str \| None = None, outline: Sequence[tuple[object, object]] \| None = None, priority: int = 0, clearance: object = None, min_thickness: object = None, connection: str \| None = None, thermal_gap: object = None, thermal_spoke_width: object = None, islands: str \| None = None, min_island_area: str \| None = None, locked: bool = False) -> None`; `@dataclass(frozen=True) class ZoneSpec`; `Design.zones: dict[str, ZoneSpec]` |
| `src/fenolite/dsl/units.py` (c0011; extended) | `as_nm2(value: object, *, name: str) -> int` (a string with the unit `mm2`, exact) |
| `src/fenolite/dsl/convert.py` (c0011; extended) | `KEYS["zone"] = ("zon", "zone:<name>")`; `to_model` fills `Board.zones` in name order |
| `src/fenolite/lens/preserve.py` (c0019; extended) | `merge_layout` passes the zones to `zones.merge_zones`; `zone_digest` covers `settings.effective()`; `drop_stale_fills` clears `filled`; public names and `PRESERVE_ISSUE_CODES` unchanged |
| `tests/_boards.py` (extended) | `created_board()` gains zone `GND_HATCH` and pad `"1"` of `U1` with `zone_connection="solid"`; `zone()` gains a `settings` text argument |
| `tests/unit/model/test_zone_settings.py`, `tests/unit/backends/kicad/test_zone_codec.py`, `test_zone_settings_read.py`, `test_zone_settings_write.py`, `test_pad_zone_connect.py`, `test_zone_merge.py`, `tests/unit/dsl/test_zones.py`, `tests/unit/lens/test_build_zones.py`, `tests/unit/lens/test_preserve_zones.py`, `tests/unit/cli/test_build_zones_command.py` | hermetic (new) |
| `tests/kicad/zones/_zonebench.py`, `_gerber.py`, `test_zonebench.py` (hermetic), `test_zone_probes.py`, `test_zone_oracle.py` | oracle (new); `tests/kicad/conftest.py` adds the folder to `sys.path`; probes join `PROBES` |
| `tests/corpus/test_board_census.py` | `test_zone_settings` (counts per origin to `FENOLITE_CENSUS_OUT`) |
| `docs/formats/kicad/board.md`, `docs/design-model.md`, `docs/dsl.md`, `docs/lens.md` | fact rows and sections (task 1.2 and the group tasks) |
| `docs/formats/kicad/gerber.md` (new) | fact rows of the Gerber subset that `_gerber.py` reads, with S-0125, S-0020 and S-0029 (task 1.2) |

## Sources registered by this change

| id | URL | licence of source | used for |
|---|---|---|---|
| S-0125 | https://www.ucamco.com/en/gerber/downloads (the Gerber Layer Format Specification; task 1.1 records the revision read) | to check on the page and in the document (task 1.1; "not stated" otherwise) | the subset of the Gerber format that `tests/kicad/zones/_gerber.py` reads in the `zone-fat9` plots: the coordinate format statement `%FS…*%` (zero omission, absolute notation, integer and decimal digits), the unit statement `%MO…*%`, regions between `G36*` and `G37*`, and the `D02` (move) and `D01` (draw) coordinate words |

S-0126 … S-0129 stay unused.

Extended "used for" cells, with no new id (task 1.1):
- **S-0001** and **S-0021**, the format pages: the `zone` and `pad` syntax for `connect_pads`, `fill`, `island_removal_mode`, hatching and `zone_connect`. To verify on the pages; where they say nothing, the fact rests on the census and the oracle.
- **S-0010** and **S-0038**, the board editor manuals: zone properties and pad connections, as background, verified on the pages in the same way.
- **S-0020** (`kicad-cli` 10.0.6 and the GUI save): `defaults.zones` of the new-project save; re-saves and refills of the zone canaries.
- **S-0022**: `--refill-zones` and `--save-board`. **S-0037**: neither exists in 9.0.
- **S-0029**: the 9.0.9 image runs the zone loads and the target-9 plot.
- **S-0033**: each new `FLOOR_HEADS` name exists at tag 8.0.0.
- **S-0058**: the census of zone forms per format version.
- **S-0018**: counts of `zone_connect` in the official footprints, counts only.

No KiCad source file is read for values. If a URL is registered by the time this change is implemented, the existing id is cited. The Gerber facts are recorded in `docs/formats/kicad/gerber.md` (new) with S-0125, and with S-0020 and S-0029 for what `pcb export gerbers` writes on each major.

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-K-ZONE-DEFAULTS | A zone written without `connect_pads`, `min_thickness` and `fill` loads in 10.0.6 as clearance 0.5 mm, minimum thickness 0.25 mm, thermal reliefs, gap 0.5 mm, spoke 0.5 mm and island mode 0; the GUI's new-project save stores the same zone defaults (S-0020) | `tests/kicad/zones/test_zone_probes.py::test_defaults` (probe `zone-defaults-t10`) | on 10.0.6 the re-saved children equal `emit_settings(ZoneSettings(), filled=False, locked=False, major=10)`, and `ZoneSettings()` equals `defaults.zones` of `empty_10.kicad_pro` field by field |
| H-K-ZONE-CONNECT | Refilled on 10.0.6: thermal reliefs give four spokes (axes for a rectangular SMD pad, 45° for a round THT pad); solid covers the relief ring; none isolates the pad; `thru_hole_only` is solid on SMD and thermal on THT; pad `zone_connect` 0–3 overrides the footprint's, which overrides the zone's (S-0022) | `tests/kicad/zones/test_zone_oracle.py -k connection` | every case gives its probe pattern on 10.0.6 |
| H-K-ZONE-GEOM | Refilled on 10.0.6: the fill keeps the larger of the zone and class or rule clearance within +5 µm; spoke width and relief gap equal the settings within 1 µm; island modes and areas, the minimum thickness and the hatch widths act as set; DRC without refill applies the zone clearance to fills | `test_zone_oracle.py -k "clearance or geometry"`; probe `zone-clearance-drc` | every measurement within its bound on 10.0.6 |
| H-K-ZONE-FORM | 9.0-written zones write `island_removal_mode` and `island_area_min` only for a mode other than 0, and 10.0-written zones write the mode always and the area only for mode 2. `smoothing` and `radius` appear only with smoothing, and the hatch smoothing children only for a level above 0. These forms reproduce every native demo zone and every zone of the upgraded third-party copies (S-0058) | `tests/corpus/test_board_census.py -k zone_settings`, `tests/corpus/test_board_rt1.py` | 0 zones with an opaque setting child in both origins, and RT1 on all readable boards |
| H-K-ZONE-FAT9 | A `20241229` zone without `(filled_areas_thickness no)` is plotted by 9.0.9 and 10.0.6 with its fill grown by `min_thickness / 2`; with the flag it is plotted as written (S-0020, S-0029; plots read as S-0125 describes) | `test_zone_probes.py::test_fat9` (probe `zone-fat9`, both majors) | the Gerber region of the written zone has the extreme coordinates of its fill, and the copy without the flag extends 125 000 nm further on each side |
| H-K-ZONE-LOAD9 | `kicad-cli` 9.0.9 loads every settings form that Fenolite writes for target 9; the meaning cannot be observed without `--refill-zones` (S-0037) | `test_zone_oracle.py -k load` in the pinned 9.0.9 image | `pcb drc` exits 0 and writes a report for every case board and the target-9 blink pour |

Cited, not settled here: `H-K-UUID-KEEP-2`, `H-K-01`, `H-K-PCB-READ`, `H-K-PCB-WRITE`, `H-K-TOK-OBSOLETE`, `H-K-LENS-FILL` (c0019), `H-K-DRU-ORDER` (c0018).

## Evidence level per behaviour (before merge)

| behaviour | level required | proof |
|---|---|---|
| Model, `effective()`, schemas | mechanical | `tests/unit/model/test_zone_settings.py`, `tests/unit/test_schema_drift.py` |
| Reading the forms of both majors | `CORPUS-VERIFIED` (native demos and upgraded third-party copies; `H-K-ZONE-FORM`) | `test_zone_settings_read.py`; `tests/corpus/test_board_census.py -k zone_settings`; `test_board_rt1.py` |
| Writing per target | mechanical; target 10 `KICAD-VERIFIED (10.0.x)` through `zone-defaults-t10` and the refills; target 9 `KICAD-VERIFIED (9.0.x)` for loading, and `INFERRED` for the hatched and smoothed forms (no 9.0 save) | `test_zone_settings_write.py`; `test_zone_oracle.py` |
| Meaning of each setting and of pad overrides | `KICAD-VERIFIED (10.0.x)`; on 9.0 `INFERRED` | `test_zone_oracle.py -k "connection or clearance or geometry"` |
| Defaults equal KiCad's new zone | `KICAD-VERIFIED (10.0.x)` for absent children; the GUI half `INFERRED` (S-0020) | `test_zone_probes.py::test_defaults` |
| Target-9 fills plotted as written | `KICAD-VERIFIED (9.0.x, 10.0.x)` | `test_zone_probes.py::test_fat9` |
| Pad `zone_connect` read and written | `CORPUS-VERIFIED` (demo boards and the footprint corpus) | `test_pad_zone_connect.py`; `tests/corpus/test_footprint_rt.py` |
| DSL zones and the build | mechanical; the built pour loads on `9.0.x` and `10.0.x` | `tests/unit/dsl/test_zones.py`, `tests/unit/lens/test_build_zones.py`; `test_zone_oracle.py -k build` |
| Zone merge (`zones.merge_zones`), its codes, and the digest | mechanical | `tests/unit/backends/kicad/test_zone_merge.py`, `tests/unit/lens/test_preserve_zones.py`, `tests/unit/cli/test_build_zones_command.py` |

`pcb.EVIDENCE` stays `INFERRED` (`H-K-PCB-READ`), and the build envelope is unchanged.

## Budget (8.0 working days; no plan line)

| work | days |
|---|---|
| 1. registers, docs skeletons, fact rows | 0.5 |
| 2. zone bench, measurement helpers and probes first (10.0.6, 9.0.9) | 1.0 |
| 3. model, `effective()`, schemas | 0.75 |
| 4. reader: projection, per-major forms, opaque fallback | 1.0 |
| 5. writer: created and read zones, canonical order, floor names, created board | 1.0 |
| 6. pad zone connection on boards and libraries | 0.5 |
| 7. corpus census and RT1 | 0.25 |
| 8. DSL `zone()`, ids, build | 0.75 |
| 9. lens: zone merge, digest, codes | 1.0 |
| 10. refill and load oracle, build oracle, probe files | 0.75 |
| 11. closing | 0.5 |
| **total** | **8.0** |

The gap came from the dogfood board, so no plan line exists. c0008 took about three times its line, so the estimate is a design-style count with a cut order to 6.5. A cut first edits or removes the requirements and scenarios named with it.
1. **Hatching and smoothing leave the model (−0.5).**
   - `design-model` "Zone settings in the board model" loses `ZoneHatch`, `fill_mode`, `smoothing` and `smoothing_radius`, and the scenario "Values without effect are dropped" keeps only the island area.
   - In `kicad-file-backend`, a `fill` holding `mode`, `smoothing`, `radius` or `hatch_*` stays opaque and projected. The scenario "Hatched fill" becomes a kept-opaque scenario. `FLOOR_HEADS` loses those names, and `GND_HATCH` becomes a solid, locked zone with `below_area` islands.
   - `kicad-oracle` loses the hatch bullet.
2. **The lock and the orphan rule leave the lens (−0.75).** `Zone.locked` and the DSL's `locked` go; the board always wins; script zones are only added, never removed.
   - `layout-lens` "Zones declared in the script" loses the locked and orphan bullets and the scenarios "A locked zone wins" and "Zone removed from the script".
   - `MERGE_ISSUE_CODES` keeps only `kicad.zone.overridden`.
   - "Zone fills and the staleness digest" replaces its new scenario with an unlocked one that expects no `zone.fill-stale`.
   - The `locked` scenarios of `kicad-file-backend` go.
3. **The 9.0.9 half of `zone-fat9` and the build refill go (−0.25).** `H-K-ZONE-FAT9` is restated for 10.0.6 (`KICAD-VERIFIED (10.0.x)`); `kicad-oracle` keeps the 9.0.9 loads only.

Not optional:
- the settings model and the pad field;
- reading and writing for both targets, with the target-9 flag;
- `Design.zone`;
- uuid matching, added zones and the digest;
- refill proofs of the connection modes and of the clearance in force.

**Moving the whole change to v0.2a.** The order puts it before c0015, and it is cuttable.
- The cost: c0015 must take the target-9 `(filled_areas_thickness no)` write (one task, about +0.25 day), or its target-9 fills are plotted 0.125 mm larger per side by 9.0.9 (`H-K-ZONE-FAT9`). c0015 must also decide the `(fill yes)` flag without `Zone.filled`.
- DSL boards in v0.1 cannot ask for a clearance, thermal reliefs or islands. The workaround is to edit zones in KiCad after the first build, which c0019 keeps.
- c0019 and c0029 need no change, because settings then stay opaque text.

## Reconciliation with the working tree (2026-10-04, task 1.1)

This change was written before c0011, c0019, c0028 and c0038 were implemented. Every consumed name was checked against the tree at commit 7a50ed4; the texts above are edited in place where they differed, and the differences are listed here.

- **MODIFIED deltas.** `design-model` "Identifier derivation", `kicad-file-backend` "Zones, fills and rule areas" and `layout-lens` "Zone fills and the staleness digest" were diffed against the living specs. Each differs only by the edits of "Migration Plan"; no text was re-copied.
- **`pcb.py`.** The file has 2211 lines. `_emit_zone(zone, nets)` gains the keyword `major`; `_Writer.absent`, `_Writer.reconcile`, `_Writer.projection`, `CANONICAL_ORDER`, `POSITIONAL`, `FLOOR_HEADS`, `ZONE_FIELDS`, `KEEPOUT_FIELDS` and `kicad_uuid` exist as the design names them. `locked` is already in `FLOOR_HEADS` (footprints).
- **Field names.** The four new zone children map to the fields `locked`, `connection`, `min_thickness` and `fill_settings`, as "Files and public API" says. A field name is a slot label, not a model attribute.
- **`zones.py` and `pcb.py`.** `pcb` imports `zones`, so `zones` cannot import `pcb`. `script_zone_uuid` spells the uuid rule of `pcb.kicad_uuid` itself, and a test pins the two together.
- **DSL.** `Design.board` has the keyword `planes` (c0038). `Design.zone` accepts an inner layer of a four-layer board whether or not a plane names it; a plane stays a build parameter that the KiCad target does not write. The id comes from `convert.key_id("zone", name)`; the `KEYS` row is `("zon", "zone:<name>")`.
- **Lens.** `merge_layout` already hands script copper to `copper.merge_copper(board, built)`. `merge_zones(built, board)` keeps the argument order of this change's spec. `build_design` calls `merge_layout` a second time, on the board it has just written, to compute the cached layout; the zone merge is therefore idempotent on a board that the same script wrote.
- **The fill flag on an opaque `fill` child (found in task 9.1).** c0019's fill tests add a zone whose `fill` is in the 9.0 form to a 10.0-format board. Its `fill` child is therefore opaque, and `drop_stale_fills`, which now clears `Zone.filled`, made the writer refuse the build with `kicad.board.projection-read-only`. "Zone settings are written" is edited: when only `filled` differs and the child's atoms are the plain form, the writer sets the `yes` atom in place and keeps the lists as read, the way it already rewrites the value of an opaque `Reference` property. This also removes the risk listed below for c0015's fill lift on such zones; a change of `settings` or `locked` through an opaque child is still refused.
- **`SettingsRead.inexact` and `ZoneMerge.decided`.** `SettingsRead` gains `inexact`, the heads whose reason is an inexact length or angle, so the reader can report `kicad.board.inexact-length` or `kicad.board.inexact-angle` as "Exact numbers on boards" requires. `ZoneMerge` gains `decided`, the ids of the zones whose net `merge_zones` already set; `merge_layout` applies the net rule of "Copper items follow their nets" to the others.
- **`c0011`'s closed `KEYS` test.** `tests/unit/dsl/test_ids.py` pins the key set, so it gains `zone`; no other c0011 test changes.
- **The Altium target (c0038, found in task 10.1).** `lens.altium.build_altium` takes one copper source and raises `ValueError` when `copper_source` is given together with copper in `design.board`. Script zones are copper in the model, so `--copper-from` on a script with `zone()` raised. `design-dsl` "Zones in a build" gains a rule and a scenario: without `--copper-from` the script's zones are the model source (written as unpoured polygon pours, with `altium.zones-unpoured`, as c0038 writes model zones); with `--copper-from`, `cmd_build` leaves the script's zones out of the model, because the routed board already holds them. `altium-build` is not modified.
- **Probes.** Probe functions join `PROBES` through a module function, as every other family does: `_zonebench.zone_probes()`.
- **S-0125.** Registered with revision 2026.05 of the specification. Its section 1.4 reserves all rights, so the row says "read for facts only, nothing copied".
- **Sources opened.** S-0001 describes the zone children and `zone_connect` 0 to 2; the value 3 is not stated there. S-0021 shows only an old zone example. S-0010 and S-0038 describe the zone properties and state that the larger of the zone and net-class clearance is used. S-0037 has `pcb export gerbers` and neither `--refill-zones` nor `--save-board`. All 13 new `FLOOR_HEADS` names are in `pcb.keywords` at tag 8.0.0 (S-0033).
- **c0030 (footprint fields), which archives first.** Its MODIFIED "Unmodelled board content is kept as slots" makes the list of projected children non-exhaustive ("among others"), so the projected zone setting children of "Zone settings are read" do not contradict it. Its ADDED requirements concern footprints, fields and pads' owners only. Both changes edit `CANONICAL_ORDER`, `FLOOR_HEADS`, `_fpmap.py`, `model/board.py` and the schemas; the edits are in different entries, and the schemas are regenerated after the rebase.

## Risks / Trade-offs

- [c0011's, c0019's or c0028's texts change before they are archived] → Each MODIFIED delta edits one row or one rule; tasks 8.1 and 9.1 re-copy the texts and the coordinator rebases.
- [9.0 writes hatched or smoothed zones differently, which cannot be observed without a 9.0 save] → The reproducibility check keeps such children opaque on read. The written 10.0 form loads on 9.0.9 (`H-K-ZONE-LOAD9`). The label stays `INFERRED`.
- [The orphan rule removes a zone the user wanted] → It removes only zones whose uuid is derived from their own name; `kicad.zone.orphan` names it, and the `.bak` of the mutation protocol keeps the board.
- [A later KiCad changes its loader or GUI defaults] → Created zones write explicit values; the defaults probe runs per version.
- [c0015 lifts fills without setting `Zone.filled`] → The zone is then written as "not filled", as KiCad writes such a zone. c0015's design consumes the field (Open Questions).
- [A zone with an opaque projected setting child refuses edits (`projection-read-only`), c0015's fill lift included] → 0 of 426 corpus zones fall back today; the refusal is located.
- [c0017's tests pin the created zone's children] → Tasks 5.1 and 6.1 update them; the order rules of "Slot source for model entities" still hold.
- [Overrun; c0008 took about three times its line] → The cut order of "Budget".

## Migration Plan

- **Additive model.** The new fields have defaults, so old JSON documents load (scenario "Old documents still load"). `board.json` and `library.json` are regenerated. `.fenolite/` caches regenerate on the next build.
- **Written text.**
  - Created zones gain their setting children, and target-9 created zones gain `(filled_areas_thickness no)`, so their fills are plotted as written.
  - Read zones change only where the model changed.
  - Library pads holding `zone_connect` are written tree-equal.
- **Archive-order dependencies.** `openspec validate --strict` accepts these deltas now. `openspec archive` of this change needs c0011 and c0019 archived first. The canonical order (c0011 → c0019 → c0028 → c0031) gives that; the `design-model` delta also needs c0028 archived first.
  - `design-model` "Identifier derivation" is copied from c0028's MODIFIED text, which copies c0011's and adds a fifth case. This change adds one `KEYS` row (`zone`) and one scenario. c0028 archives first; if its text changes before then, task 8.1 re-copies it and keeps only these two edits.
  - `layout-lens` "Zone fills and the staleness digest" is copied from c0019's ADDED text. Its edits: the first sentence clears `filled`; `zone_digest` gains `settings.effective()`, its opaque slots are only the fill settings that the reader kept opaque, and it leaves out `filled` and `locked`; the scenario "A removed part drops fills" expects `filled == False`; a scenario "A zone setting change drops fills" is new.
  - c0019 is proposed and may change, so task 9.1 re-copies that text before the change is archived.
  - `kicad-file-backend` "Zones, fills and rule areas" is the living text, with one sentence in the `Zone` bullet and one scenario; no other open change modifies it.
- **What this change does not modify.** It modifies none of the c0011 `design-dsl` requirements that c0019 and c0027 modify. It does not modify c0019's "Copper items follow their nets" or "Layout issue codes": the new "Zones declared in the script" states its own precedence for script zones, and its codes are `kicad.*` codes.
- **Rollback.** Revert the change and regenerate the schemas; no stored data needs a migration.

## Open Questions

- **Per-pad zone connection in the DSL.** Default: deferred to v0.2a, together with the per-footprint request mechanism (c0030 faces the same transport). Library footprints carry `zone_connect`, and the model API can set `Pad.zone_connection` today.
- **The zone's own clearance in the copper check.** Default: a v0.2a follow-up to c0029 (`docs/roadmap.md`, v0.2a follow-ups) adds it as a floor for fill pairs, matching KiCad's DRC (probe `zone-clearance-drc`). This change does not modify `copper-check`.
- **Zone defaults in `.kicad_pro`.** Default: not written; `defaults.zones` only steers zones drawn later in the GUI.
- **If this change moves to v0.2a.** Default: c0015 takes the target-9 flag task and decides `(fill yes)` (Budget).
- **Hatching and smoothing in the DSL.** Default: model API only.
- **Default zone name.** Default: the net's name, with `name=` required for a second zone on the same net or for a zone without a net. To confirm.
- **Marker of script zones.** Resolved: the uuid derived from the zone's own name. No marker is shared with script copper: c0028 Decision 20 keeps two precedence models, and its version-8 uuids belong to the derived one.
- **Meaning of `locked`.** Default: as c0019 reads `place(locked=True)`, the script's precedence plus KiCad's lock.
- **c0015's question for the maintainer (target-9 fills, `docs/roadmap.md`, "Later questions").** `H-K-ZONE-FAT9` bears on it: fills re-emitted for target 9 without `(filled_areas_thickness no)` are plotted 0.125 mm larger per side by 9.0.9, which can produce clearance violations. Default: c0015 relies on this change's flag; the question stays as worded.
- **Hand-over to c0015.** Default: c0015 lifts `fills` and `filled` together from the 10.0-written copy and keeps `settings` from the original model, because settings are inputs of the fill.
- **9.0 forms of hatched and smoothed zones.** Default: the 10.0 form for both targets, guarded by the reproducibility check; `INFERRED`.
- **Budget.** 8.0 working days, with the cut order to 6.5. To accept.
