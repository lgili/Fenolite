## Context

- **Scope.** Plan, schematic: "v0.2b: 'readable' autolayout (snap of 2-pin parts on IC pins, orthogonal wires) and a hierarchical sheet per `Module`". Plan v0.2a deferred both ("Postponed: readable autolayout, hierarchy per `Module` … (v0.2b)").
- **What v0.2a proposes (not archived).**
  - c0060: `SchematicSheet(name, paper, title_block, lib_symbols, symbols, labels, no_connects, sheets, pages)`, `SymbolInstance`, `NetLabel`, `NoConnectFlag`, `SheetRef(name, file, position, size, uses)`, `SheetPage`; wires and junctions of a read file stay opaque slots; `sch.sheet_files` walks a hierarchy relative to the folder of each referencing file.
  - c0061: `schgen.generate_schematic` builds one flat sheet: one instance per unit, one global label per connected pin, no-connect flags from marks, power flags, `pad_nets` for unconnected pins; `schlayout.layout_units` flows cells in rows by module, picks A4 to A0, honours `schematic-placements.toml`; `sch.write_schematic` per target; `lower_for_schematic` writes `Component.path = /<symbol uuid>` and the `unconnected-(…)` pad nets; the stand-in `update_from_schematic`. Its documented limits: "one sheet up to A0, no wires, no hierarchy, no buses".
  - c0063: `sch_netlist.own_netlist(sheet, *, project)` reads one generated sheet inside a grammar that refuses wires, hierarchy and labels off pins; the build's netlist guard compares it with the circuit; the oracle compares it with `kicad-cli`'s export on examples and 25 generated designs.
  - c0069 (v0.2b, proposed): `sync --to-source` writes `schematic-placements.toml` from the schematic, keyed by component path.
- **Measured on 2026-10-05** (scratch probes, hand-written sheets, `kicad-cli` 9.0.9 in the pinned image and 10.0.6 locally; recorded by tasks 1.1 and 1.2):
  - A sheet symbol without pins loads, ERC reports nothing, and global labels of one text join pins of the root and of the child into one net with that text as its name.
  - A net named only by a hierarchical label in sheet `modA` is `/modA/SIG`; a sheet pin without its hierarchical label gives `hier_label_mismatch`.
  - The child file may live in a sub-folder (`Sheetfile "sheets/modA.kicad_sch"`). A grandchild's `Sheetfile` is resolved from the folder of the file that names it: `b.kicad_sch` named from `sheets/a.kicad_sch` loads, `sheets/b.kicad_sch` named from there is dropped, with no ERC finding and exit 0.
  - Child files carry no `sheet_instances`. A symbol in sheet `a/b` has the instance path `/<root uuid>/<a uuid>/<b uuid>`; the netlist gives it `sheetpath (names "/a/b/") (tstamps "/<a uuid>/<b uuid>/")` and its own `tstamps`, and the properties `Sheetname` = `b` and `Sheetfile` = the text that names its file. The root's `Sheetname` is `Root` on 10.0.6 and empty on 9.0.9.
  - A wire joins the pins at its two ends. A pin end in the middle of a wire is not connected, on both majors. A junction on an unsplit wire connects on 10.0.6, while 9.0.9 reports `unconnected_wire_endpoint` and leaves the pin unconnected; wires split at the junction point connect on both.
  - Two pins joined by a wire, with one global label at one end, form one net named by the label, with no ERC finding. One pin with a lone global label gives `isolated_pin_label` (10.0.6) or `global_label_dangling` (9.0.9). A wired group without a label is named `Net-(<ref>-Pad<n>)`. Unconnected pins in a child sheet are named `unconnected-(<ref>-Pad<n>)`, as in a flat sheet.
- **Constraints.** Stdlib only, integers only. Net names in the schematic must stay equal to the board's (c0061's parity and lens rest on it). c0061's output must stay available (`--schematic-layout grid`).

## Goals / Non-Goals

**Goals:**
- A reader sees modules as sheets and the parts around an IC next to its pins.
- Every net name, pad net and position on the board stays as v0.2a writes it.
- Fenolite still proves its own schematic without a tool, and KiCad still accepts it on both majors.

**Non-Goals:**
- Everything under "Non-goals" in the proposal.
- Beauty. The layout is deterministic and never worse than c0061's grid; it is not a schematic router.

## Decisions

1. **One sheet per module, global labels only.** A design with at least one module that holds a part, directly or below, gets a root sheet and one child sheet per such module. The root holds the parts outside every module, one sheet symbol per top-level module and the power flags; a child holds its module's own parts and one sheet symbol per sub-module.
   - Labels stay global: a hierarchical label would rename a module-local net `power/FB` to `/power/FB` in KiCad and break the equality with the board. Sheet symbols therefore have no pins.
   - A design without modules gets one sheet, with the satellites of Decision 5. `--schematic-layout grid` asks for c0061's sheet, without satellites and without hierarchy, whatever the modules.
   - Rejected: one sheet per top-level module only (the plan says "per `Module`"; nested modules would collapse into one page). Rejected: sheet pins with hierarchical labels (net names change, and pins have to be routed to the sheet symbol).

2. **File names.** A child sheet is written to `sheets/<module path with "/" replaced by ".">.kicad_sch`. The root names it `sheets/<file>`; a child names its sub-modules' files as `<file>`, from its own folder (`H-K-SCH-HIER-FILE`). Two modules whose files would collide give `build.sheet-file-collision` (error) and nothing is written.
   - All child files share one folder, so the relative names stay one level deep.
   - Because KiCad drops a sheet whose file it cannot find without a finding, the build's netlist guard (Decision 8) is the check that every sheet is reached.

3. **Sheet symbols and pages.** Each sheet symbol is a box of height 12.7 mm and width `max(25.4 mm, CHAR_ROOM × (len(name) + 2))` rounded up to `ORIGIN_STEP`, named by the module's last path segment, placed in one row after the units of its parent sheet and before the power flags. Pages: the root is `1`, the children are numbered from `2` in depth-first order of their module paths (natural order). The root's `sheet_instances` lists only `/`; each sheet symbol's `instances` gives the path of the sheet that holds it and the child's page.

4. **Paths.** A symbol in a child sheet uses `/<root uuid>/<sheet uuids from the top down>`. Its footprint's `path` is `/<sheet uuids>/<symbol uuid>` (`H-K-SCH-HIER-PATH`): the netlist's `sheetpath` `tstamps` followed by the symbol's own. Root symbols keep `/<symbol uuid>`. The layout lens matches by uuid and `fenolite.path`, never by `path`, so the change of form keeps every layout; c0069's identity rewrite takes the new `path` from the built copy.

5. **Satellites.** In one sheet, an *anchor* is a unit with three pins or more, and a *satellite* is a component with exactly two pins in one unit whose two connection points lie on one axis with opposite pin angles. A satellite is snapped to the first free anchor pin, in anchor order then natural pin order, that is on the net of one of its pins (its *near pin*), when every condition holds:
   - the rotation that turns the near pin to face the anchor pin, with the body extending away from the anchor, is in `schlayout.PROVED_FRAMES` with no mirror;
   - the satellite's origin is `pin_point` offset so that its near pin lands at `SNAP_REACH` (5 080 000 nm) from the anchor pin, along the pin's outward direction; origins are multiples of `GRID` (1 270 000 nm);
   - its box (body, pins, Reference and Value room, and the room of its two labels) overlaps neither the anchor's body, nor another anchor's cell, nor a satellite or wire already snapped.
   - The anchor pin then has one wire, from its connection point to the near pin. The wired pair gets one global label at the near pin, turned perpendicular to the wire, towards the side of the anchor pin away from the anchor body's centre line. The far pin gets its global label as c0061 places it. Each anchor pin takes at most one satellite.
   - A satellite that `schematic-placements.toml` places is not snapped, unless its entry equals the snapped origin, rotation and mirror, so `sync` followed by a build keeps the wire.
   - Rejected: several satellites per pin with junctions (needs split wires and junctions, which 9.0.9 judges differently from 10.0.6 when not split); bent wires (more rules for one gain); a label in the middle of a wire (not measured).

6. **Clusters in the flow.** An anchor and its satellites form one cell, the union of their boxes, wires and label rooms grown by `CELL_MARGIN` and `TEXT_ROOM`, rounded up to `ORIGIN_STEP`. The cell takes the anchor's place in c0061's order; snapped satellites leave the order. Each sheet picks its own paper from A4 to A0. A sheet that does not fit A0 gives `build.schematic-too-large` naming the sheet.

7. **Model and writer.** `SchematicSheet` gains `wires`, a tuple of `Wire(start, end)` entities (prefix `wir`), horizontal or vertical and of non-zero length. The reader of c0060 leaves `wires` empty: a read sheet keeps its wires as opaque slots. The writer emits, in order: no-connect flags, wires, labels, symbol instances, sheet references, then `sheet_instances` only when the sheet has pages, so a child file has none. A sheet reference is written as the probes wrote it on both majors: `at`, `size`, the four flags, `stroke`, `fill`, `uuid`, the `Sheetname` and `Sheetfile` properties, and `instances`.

8. **Own netlist over the tree.** `own_netlist(sheet, *, project, children={})` takes the child sheets keyed by their path from the root file's folder. Points are joined across one sheet by pins, wire ends and labels; a connected group with one label text is a net of that text across all sheets; a node alone is an unconnected net as before. The grammar refuses what the generator never writes: a bent or zero wire, a wire end on no pin, a wire that meets anything but at its ends, a group with two texts or a wired group with none, a sheet reference with pins or naming a missing child, a child named twice. The build guard therefore still proves the whole tree, and catches a missing sheet before KiCad would drop it.

9. **Build files.** `build` writes every child sheet beside the root, records their SHA-256 in `.fenolite/build.json`, and replaces an edited child sheet with `build.schematic-replaced` as c0061 does for the root. A child file of an earlier build that the design no longer has is left alone, with `build.sheet-stale` (warning) naming it: Fenolite deletes nothing.

10. **Cut order.** First Decision 6's per-sheet paper (keep one paper for all sheets), then the satellites (task 4.x: hierarchy alone still meets half of the plan line), never the hierarchy and its oracle.

## Files and public API

- `src/fenolite/model/schematic.py`: `Wire`, `SchematicSheet.wires`; prefix `wir`.
- `src/fenolite/backends/kicad/schlayout.py`: `SNAP_REACH`, `Cluster(anchor, satellites, wires, labels)`, `snap_satellites(units, nets, *, placements=None) -> tuple[tuple[Cluster, ...], tuple[Issue, ...]]`, `layout_units(…, clusters=(), refs=())`, `sheet_ref_size(name)`.
- `src/fenolite/backends/kicad/schgen.py`: `GeneratedSchematic.children` (path → sheet, in page order), `generate_schematic(…, layout="readable")`, `sheet_file(module_path)`.
- `src/fenolite/backends/kicad/sch.py`: wires and sheet references in `write_schematic`.
- `src/fenolite/backends/kicad/sch_netlist.py`: `own_netlist(…, children={})`, new reasons.
- `src/fenolite/lens/build.py`, `src/fenolite/cli/cmd_build.py`: `--schematic-layout readable|grid`, child files, `build.sheet-stale`, `build.sheet-file-collision`.
- Tests: `tests/unit/backends/kicad/test_schlayout_snap.py`, `test_schgen_hierarchy.py`, `test_sch_netlist.py` (extended), `tests/unit/lens/test_build_hierarchy.py`; `tests/kicad/schematic/test_hierarchy_probes.py`, `test_hierarchy_oracle.py`; `tests/_gendesigns.py` gains nested modules and satellites.

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-K-SCH-HIER-FILE | A sheet reference's `Sheetfile` is resolved from the folder of the file that holds the reference; a name that resolves to no file drops that sheet with no ERC finding and exit 0; a sheet symbol without pins loads, and global labels of one text join pins of all sheets into one net of that text (S-0020, S-0029) | `tests/kicad/schematic/test_hierarchy_probes.py::test_sheet_files` | probes `sch-hier-file-parent` `present`, `sch-hier-file-project` `absent`, `sch-hier-global` `equal` on 9.0.9 and 10.0.6 |
| H-K-SCH-HIER-PATH | For a symbol in a child sheet, the netlist gives `sheetpath` `tstamps` `/<sheet uuids>/` and the symbol's `tstamps`, whose join is the footprint `path` that Fenolite writes; KiCad's "Update PCB from Schematic" writes the same `path` (S-0020, S-0029) | `tests/kicad/schematic/test_hierarchy_oracle.py::test_paths` | for every component of every hierarchical build in the oracle set, the joined netlist value equals the written footprint `path` on both majors; the update half stays `INFERRED` (no headless update) |
| H-K-SCH-WIRE-END | A wire joins the pins at its two ends and nothing in its middle; two pins joined by one wire with one global label form one net named by the label, with no ERC finding (S-0020, S-0029) | `tests/kicad/schematic/test_hierarchy_probes.py::test_wire_ends` | probes `sch-wire-ends` `equal` and `sch-wire-middle` `absent` on both majors |

Ids used without changing their level: `H-K-SCH-MINIMAL`, `H-K-SCH-PINFRAME`, `H-K-SCH-UNCONNECTED`, `H-K-SCH-SLASH`, `H-K-SCH-PARITY`, `H-K-SCH-UPDATE` (c0061), `H-K-NETLIST-OWN` (c0063).

## Risks / Trade-offs

- [A snapped satellite overlaps a field KiCad auto-places differently] → fields are written at fixed offsets with `do_not_autoplace` (target 10) as c0061 does; the overlap check uses the same text room.
- [Global labels everywhere look busy in a hierarchy] → accepted; they keep names equal to the board's. Hierarchical labels can come with sheet pins in a later change.
- [KiCad silently drops a sheet it cannot find] → the netlist guard counts every child; the oracle compares components with `kicad-cli`'s.
- [A project built in v0.2a changes on the first v0.2b build] → new files and paths only; the lens keeps the layout (Decision 4); `--schematic-layout grid` keeps the old form.
- [The plan's "orthogonal wires" read as routed wires] → one straight wire per satellite is orthogonal and measured; bends wait for a router.

## Migration Plan

- Designs without modules: the satellites change the sheet once; `--schematic-layout grid` gives v0.2a's bytes.
- Designs with modules: the first build writes `sheets/` and changes symbol and footprint paths; later builds are byte-identical. `build.sheet-stale` lists child files that a later design no longer has.
- c0060, c0061 and c0063 not archived when this change starts: the entry task stops it, because every MODIFIED requirement here is theirs.
- Rollback: `--schematic-layout grid` gives c0061's output.

## Open Questions

- **Should `--schematic-layout` default to `grid` for one release, so v0.2a projects do not change?** Default: `readable`, as the plan's v0.2b line asks; the flag keeps the old form.
- **Should a module with one part get its own sheet?** Default: yes, for a predictable mapping from modules to sheets.
- **Sheet names repeated at one level** cannot happen (module names are unique per parent); none is reserved.

## Corrections on 2026-10-06

The proposal was written on 2026-10-05, before c0060 to c0065, c0069, c0074 and c0044 landed. Every MODIFIED delta was regenerated from the living text, and these points of the proposal were wrong about the tree or left a gap. The text above stays as proposed; where it differs, this section and the spec deltas win.

1. **c0063 is implemented and not archived.** Its four requirements are modified from the text of its own delta (`cli-contract` "Netlist command" is new in this change's deltas). This change archives after c0063.
2. **"Generated sheet content" (living).** The blink of `examples/` marks its unused pins, so the scenario keeps "29 no-connect flags"; the proposal's renamed scenario "Marks become flags" is dropped and the living "A pin without a mark" is kept. `GeneratedSchematic` keeps `unvendored` and `power_flags` and gains `satellites`. Each sheet embeds only the definitions its own instances name.
3. **"Schematic writing per target" (living).** The lossy rule is the living one (the token's own node is removed), not the older text the proposal copied.
4. **"Deterministic sheet layout" (living).** The living text has a **Units** bullet (`UnitBox`, `UnitPin`, `shelf_pack`), which the proposal's copy had lost. `UnitBox` gains `text` (the length of the longer of Reference and Value), because Decision 5 needs the room of those texts; sheet references are given as `RefBox(path, name, file)`; `layout_units` gains `sheet`, the name that `build.schematic-too-large` reports.
5. **"Generated schematic issue codes" and "Modelled schematic content" (living) are modified too.** The first says `schgen.ISSUE_CODES` "SHALL be exactly this table", so two new codes need its table changed, not a bullet elsewhere. The second has a scenario that says "the sheet has no field that lists wires", which `SchematicSheet.wires` would break: it now says the field is empty for a read sheet.
6. **"Netlist grammar check" (c0063).** The reason `undefined-symbol` stays. `sch_netlist.ISSUE_CODES` stays its own closed set. `shared-point` keeps c0063's second half (several pins of one instance at a point without a label).
7. **A built project must be read back from its files (Decision 7 and 8 revised).** c0063's `fenolite netlist --source fenolite` reads the written `.kicad_sch` with `read_schematic`, where a wire is an opaque slot. With the proposal's rule (an opaque `wire` is the reason `wire`) the command would refuse every project built with the default layout, against c0063's scenario "Own reading without a tool". So the wires of a sheet are its `wires` and the opaque root `wire` slots of a read sheet (`sch.opaque_wires`), read alike and under the same refusals; the reason `wire` is left for junctions and buses. The command reads the child sheets the root names. The reader still models no wire (c0060's rebuild is untouched).
8. **Use paths are checked.** The reason `sheet` also covers a symbol whose use is not at the instance path of its sheet, and a child that no reference names: the build guard then proves the paths KiCad resolves references by, not only the nets.
9. **Placed satellites (Decision 5 revised).** "Its entry equals the snapped origin" has no meaning before the anchor has an origin, and the anchor's origin in the flow depends on what is snapped. A satellite named by the placements file is therefore snapped only when its anchor is named too; `sync` writes every unit, so `sync` followed by a build keeps every wire. The scenario "Placed satellite keeps its wire" places `U1` as well.
10. **Overlap rule (Decision 5 made exact).** "Never worse than c0061's grid" needs more than the anchor's body: the rooms of the labels of the anchor's other connected pins and of its Reference and Value are obstacles too, and a pin point may not lie on a snap wire (the grammar's `wire-touch`). The cells of other units matter only around a placed anchor, because in the flow a cluster is one cell. `snap_satellites` returns the clusters only: it has nothing to report.
11. **File collisions fold letter case**, as vendored library paths do: `sheets/A.kicad_sch` and `sheets/a.kicad_sch` are one file on Windows and macOS.
12. **`build.sheet-stale` comes from `build_design`**, from the last build record, so no file is read; `result.schematic` also lists the child `files`, and its counts cover every sheet.
13. **`update_from_schematic`** keeps accepting one text (c0061's and c0069's tests and the living `layout-lens` text call it so) and also takes the mapping of this change.
17. **Parity (c0072) reads the tree (added on the rebase onto 949d1f0c).** c0072 landed with an own-netlist path that refused more than one sheet, because the tree grammar of this change did not exist yet. `parity_inputs.grammar_issues` and `own_netlist` now pass the root and its children to `sch_netlist`, and `KicadBackend.schematic_side` and `cmd_parity` lost their single-sheet test, so `fenolite parity` and the `parity` stage of `check` need no tool for a project with module sheets. c0072's requirements already say "when the sheet tree is inside Fenolite's grammar", so none of its deltas changes; this change still archives after c0063 and after c0072, whose code it edits. `tests/data/kicad/parity/agree/blink.kicad_sch` was regenerated: the blink now has its resistor beside the controller pin (the board file is unchanged).
14. **The oracle judges ERC by comparison (found while running it).** The acceptance design of c0069 and the generated designs leave pins open and labels alone: ERC reports that for the flat form too (29 `pin_not_connected` for the acceptance design). "No violation" therefore holds only for a design that marks its open pins (the nested design of the scenarios); for the others no violation type may be counted more often than for the same design built with `--schematic-layout grid` (9.0.9 counts one `pin_not_connected` fewer on the readable sheets of one generated design, for a pin that is open in both forms and alone on its net in both exports. A bounded look on 2026-10-06 found that 9.0.9 reports 24 of that project's 25 open pins whatever is done, and that the pin it leaves out, pin 27 or pin 16 of `U4`, changes when unrelated lone labels are added; it is neither the wires nor the sheet symbol. The loss is in 9.0.9's ERC report; `docs/evidence/kicad-schematic.md` has the measurements. The netlist comparison is the exact check of connectivity). A dropped sheet is not silent in every design either: a label that loses its net's other pin gives `isolated_pin_label`; ERC still says nothing about the sheet. And the netlist lists one `tstamps` per unit of a part, in KiCad's order: the footprint path must be one of them.
16. **Known limit of the overlap rule.** KiCad draws the Reference and the Value of a turned symbol turned with it. The room that the snap keeps for those texts is the one of an unturned symbol, where the writer puts them; beside a pin on the left or right side of an IC the satellite is turned by 90 or 270 degrees, and its Reference can then touch its own far label (seen on the rendered blink). The connections are not affected. A follow-up can write the fields of a turned satellite unturned, or keep the turned room.
15. **Not changed, and worth a follow-up.** Once every unit is named by the placements file (after `sync`), `layout_units` flows only the power flags, from the top-left corner, and chooses the paper from that flow alone: flags can land on placed symbols, and a sheet larger than A4 comes back as A4. This is how c0061 and c0069 left placements; this change keeps the wires through `sync` and does not touch that rule.
