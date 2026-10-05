## Context

- c0039 to c0042 give records: `read.sch.SchDocument`, `read.schlib.SchLibrary`,
  `read.pcb.PcbDocument`, `read.pcblib.PcbLibrary` and `read.project.AltiumProject`. None of them
  computes a net or builds a model entity, by their own requirements.
- The neutral model (`fenolite.model`) is what checks, the lens, analyses (c0047), equivalence
  (c0045) and conversion read. The only backend that fills it from files is KiCad
  (`backends/kicad/pcb.py`, `mod.py`, `sym.py`).
- `fenolite.backends.altium` is a writer package and is not a registered backend. The registry holds
  one built-in.
- A schematic stores drawing objects. Its nets follow from geometry and from names, with a scope
  that depends on the project (S-0185). No KiCad schematic reader exists yet, so this is the first
  code in Fenolite that derives a netlist from a drawing.
- The model lacks three things an Altium design states: buses, pad holes that are not round with
  copper offsets, and component bodies. The roadmap names them as the additive deltas of v0.3.
- Sibling state after integration (2026-10-03): c0039 to c0042 have specs, and the names below are
  theirs. The points that were open between the changes are settled in Decisions 3, 11 and 17.

## Goals / Non-Goals

**Goals**

- One adapter package from records to `Design` and `Library`, pure and deterministic.
- Schematic connectivity defined rule by rule, each rule with a source or a hypothesis and a test.
- An `AltiumBackend` registered for `detect` and `read`.
- Three additive model deltas in their smallest useful form.
- Evidence from three directions: Fenolite's own files, public project sets (schematic against
  PCB), and `kicad-cli pcb import`.

**Non-Goals**

- Parsing bytes, CLI commands on Altium files, round-trip levels, equivalence, sheet templates.
- Writing from an imported model; a lossless container in the model.
- Schematic presentation, repeated sheets with annotation, nested harnesses, variants,
  differential pairs, zone settings, split planes, per-layer via stacks, footprint fields.

## Decisions

1. **The adapter is a package of pure functions over records; the backend does the file work.**
   - `adapter.*` takes records and returns model objects. `backend.py` reads bytes, calls the
     readers and passes file names and hashes in.
   - So tests build records in memory or read authored files, and c0044 and c0045 can call the
     adapter on documents they already hold.
   - Rejected: one `read_altium(path)` function. It mixes file access with mapping and cannot be
     tested without files.
   - Rejected: adapters inside each reader module. The readers must not import `fenolite.model`
     (c0041, "PCB reader package").

2. **The model is a projection, not a container.**
   - An entity holds what the model has fields for, plus small text pairs in `ext["altium"]`: the
     original integers of inexact conversions and a closed list of keys (`EXT_KEYS`).
   - Records and keys that map to nothing stay in the readers' documents, which are lossless by
     their own requirements, and are counted by `altium.import.unmapped`.
   - Rejected: storing every unmapped record in `Board.ext` as encoded bytes. It doubles the file in
     `board.json`, and the lossless round trip of c0044 works on records, not on the model.
   - Rejected: slots (`Modeled`/`Opaque`) per entity, as the KiCad board reader has. They serve a
     writer that re-emits a file from the model; that writer is v0.4 and will state its own slot
     rules. The provenance locator already names the source record of every entity.

3. **Units: `core.units.u_to_nm`, half to even, with the original integer kept.**
   - `docs/formats/units.md` defines the conversion and says importers keep the original integers.
     The adapter keeps them only when the conversion is inexact (`u` not a multiple of 50), so most
     bags stay empty on metric and on 5-mil grids.
   - c0041's `pcbprims.to_nm` is the same function (settled at integration: its first draft rounded
     half away from zero, which differs by 1 nm at `u ≡ 25 mod 50`; c0041 was edited to the
     project rule). The adapter may call either.
   - Angles: a stored double becomes microdegrees through `Fraction`, never through float
     arithmetic. "Exact" means that the double nearest to the result is the stored one.
   - Rejected: keeping every original integer. It triples the size of `board.json` for no reader.

4. **Frame: negate Y, shift nothing.**
   - The model's frame is KiCad's: Y down. Altium's Y is up. X is kept.
   - The board origin (`ORIGINX`, `ORIGINY`) goes to the board's bag. The writer of c0035 shifts
     boards so that the outline's corner is at (1000 mil, 1000 mil); an import of a written file
     therefore differs from its source model by one translation, which tests allow for.
   - Footprint rotation and the bottom side are the inverse of the writer's placement, which
     `kicad-cli` already confirmed for written files (`H-A-PCB-KICAD-DOC`). For files that Altium
     saved, the oracle test of this change settles it (`H-A-IMP-FRAME`).
   - Rejected: subtracting the origin. Two imports of one board whose origin moved would differ in
     every coordinate.

5. **Copper layers are named by position in the chain; other layers by a closed table.**
   - `F.Cu`, `In<j>.Cu`, `B.Cu` are the names the writers, the KiCad backend, the checks and the
     lens already use. Naming by position is what KiCad's importer does, so the oracle can compare
     layer by layer, and it matches the writer of c0038 for the stacks it writes.
   - A plane stays a `Layer` of kind `copper` with its net in the bag (c0038, Decision 5).
   - Mechanical layers become `Mech.<n>`. Altium has no fixed fabrication or courtyard layer
     (`pcb-records.md`), so none is guessed. Open Question 4.
   - Rejected: Altium's own names as layer names. No consumer could select copper by name, and a
     user may rename layers.

6. **The outline becomes `Edge.Cuts` graphics; `Board.outline` stays `None`.**
   - "Board entities read from file backends" says an imported board has no `Outline` and that its
     edge graphics are authoritative. Every consumer of a board frame (c0028) reads those graphics.
   - Rejected: filling `Board.outline`. It needs a MODIFIED requirement and gives two forms of one
     fact.

7. **A PCB document has no footprint definitions; an instance is its component's pads.**
   - Pads go to the footprint frame by the inverse of `Transform.placement(position, rotation)`
     without a mirror, the model's rule for every imported board. A model built from a script may
     hold a bottom footprint's pads unmirrored, so tests compare an import with a KiCad board read
     by `KicadBackend`, not with the built model.
   - Graphics, texts and regions of a component are counted, not modelled: `FootprintInstance` has
     no field for them (c0030 adds `fields`; this change does not depend on it).
   - Rejected: synthesising a `FootprintDef` per pattern from the first instance. Two instances of
     one pattern may differ, and `ReadResult` holds a `Design` or a `Library`, not both.

8. **Padstack delta: hole shape, slot length, hole rotation, per-layer offset.**
   - `Padstack` and `PadstackLayer` exist. The delta adds four fields with defaults.
   - The corner radius of a rounded rectangle stays in the bag (`corner_percent`), as the KiCad
     reader keeps its ratio opaque. One rule for both backends is a later change.
   - Rejected: `Pad.drill_shape` and `Pad.slot_length` on the pad. A pad without a padstack must
     keep meaning "simple", and the hole is part of the stack.
   - Rejected: a `mode` field. Explicit layers say the same; a definition uses the wildcard
     `In*.Cu`.
   - Rejected: mask and paste layers in `Pad.layers`. In Altium they follow from rules or from a
     manual expansion; listing them would assert openings the file does not state.

9. **Bus delta: `Bus(name, members)` with `BusMember(index, net_id)`.**
   - A bus is an indexed vector. `Interface.members` is a mapping sorted by key, which loses the
     order (`D10` sorts before `D2`) and has no index.
   - A harness stays an `Interface` of kind `harness` (c0037).
   - Rejected: `Interface(kind="bus")` with the range in a bag. Every consumer would parse names.
   - Rejected: members as net names. Every other reference in the model is an id.

10. **Body delta: `ComponentBody` with a height, a standoff and an optional outline.**
    - Uses: the height of a part for clearance to an enclosure and for the analyses track; the body
      outline for placement checks. Both need lengths, not a 3D model.
    - Two kinds: `extruded` and `model`. Altium's cylinder and sphere bodies import as `extruded`
      with their height and no outline until a consumer needs them.
    - It is an entity (prefix `bdy`) so that it carries provenance and a bag.
    - Rejected: `Component.height` alone. A part may have several bodies, and the outline is lost.
    - Rejected: embedding model data. Files stay outside the model.

11. **Body records are decoded in `read/bodies.py`, owned by this change.**
    - Hand-over, stated in both changes: c0041 keeps `ComponentBodies6` and
      `ShapeBasedComponentBodies6` as bytes in `PcbDocument.storages`, and a library footprint's
      body primitives as `RawPrimitive` ("No typed component bodies"). This change decodes those
      bytes and parses no other record. The delta of Decision 10 needs them.
    - The module lives under `read/`, follows c0041's import rules, keeps every byte and types a
      key only with a source. The adapter reads its records like any other.
    - Rejected: decoding inside the adapter. It would put byte parsing in the mapping layer.

12. **Connectivity is computed per sheet in exact integers, then joined across sheets.**
    - Coordinates are `SchLength.value` (1/100 000 of 10 mil). "On a segment" is a zero cross
      product and a box test. No tolerance: Altium snaps to a grid, and a tolerance would join
      objects that Altium does not.
    - Step 1, local nets: union-find over wire ends, wire segments, junctions and electrical
      points. Step 2: names within the sheet. Step 3: the scope joins across sheets. Step 4: buses
      and harnesses add joins by position and by entry name. Step 5: naming.
    - The steps are separate functions with plain data between them, so a rule has one place and
      one test.
    - Rejected: a tolerance of half a grid step. No source states one.
    - Rejected: following KiCad's importer. It converts drawings and lets KiCad's own netlister
      decide; its rules are KiCad's, not Altium's.

13. **Each rule is a row of `connectivity.md` with a source or a hypothesis.**

    | rule | source | hypothesis |
    |---|---|---|
    | a wire end on another wire connects (T joint) | S-0185 | `H-A-IMP-WIRE` |
    | crossing wires connect only at a junction | S-0185, S-0130 (record 29) | `H-A-IMP-WIRE` |
    | a pin connects at its end away from the body | S-0140 | `H-A-SCH-NETS` (c0032) |
    | a point inside a segment connects | none | `H-A-IMP-PIN-MID` |
    | a net label connects at its location, lower left | S-0140, S-0185 | `H-A-SCH-NETS` |
    | labels of one name join within a sheet, without letter case | S-0185 | `H-A-IMP-WIRE` |
    | a port connects at both ends | S-0130; `hier_facts` F13 from S-0187, S-0188 | `H-A-IMP-PORT-ENDS` |
    | power ports join by name over the design | S-0140, S-0185 | `H-A-SCH-NETS` |
    | a power port wired to a port stays local | S-0185 | `H-A-IMP-POWER-LOCAL` |
    | the automatic scope | S-0185 | `H-A-IMP-SCOPE` |
    | a port joins the sheet entry of its name | S-0185 | `H-A-SCH-HIER-COMPILE` (c0037) |
    | off-sheet connectors join under one parent | S-0185 | `H-A-IMP-OFFSHEET` |
    | kinds never join by name | S-0185 | `H-A-IMP-DUP-NAME` |
    | name priority by kind and by option | S-0185 | `H-A-IMP-NAME-TIE` |
    | system names `Net<ref>_<pin>` | S-0185 | `H-A-IMP-NAME-AUTO` |
    | bus members `<name><i>` and joins by position | S-0301, S-0185 | `H-A-IMP-BUS` |
    | harness entries of one name are one net | S-0186; G14 to G16 | `H-A-SCH-HARN-NETS` (c0037), `H-A-IMP-HARN-NAME` |
    | a hidden pin with a net name joins that power net | S-0185 (legacy projects still netlist) | `H-A-IMP-HIDDEN-PIN` |

    - The umbrella test is `H-A-IMP-NETLIST`: on public project sets the schematic netlist equals
      the pad netlist of the PCB document. A set that exercises a rule and agrees supports that
      rule; a rule that no set exercises stays `INFERRED`.

14. **Two nets never merge because they share a name across kinds; the second is renamed.**
    - S-0185 says identifiers of different kinds do not connect by name. The model needs unique
      net names (`nets_by_name`, the net id).
    - `<name>#<k>` keeps both nets and makes the clash visible as a warning. The corpus test shows
      whether Altium merges them (`H-A-IMP-DUP-NAME`).
    - Rejected: merging by name. If Altium does not merge, the import would hide a real open.

15. **Components: one per designator per sheet instance; the native id is the unique-id path.**
    - Altium places one component record per part. Parts share the designator text.
    - The path `\<sheet symbol id>\<component id>` is what a PCB component stores as
      `SOURCEUNIQUEID` (`hier_facts` U2), so the same string links both sides and gives the same
      component id from a project and from its PCB document alone.
    - Which part's id the PCB stores for a multi-part component is not stated: the link accepts any
      part (`H-A-IMP-LINK`).

16. **Project merge: the circuit comes from the sheets, the board from the PCB document, and
    neither is corrected by the other.**
    - Footprints link to schematic components; PCB nets to schematic nets by name. What does not
      link is added and reported.
    - A pad keeps the net the PCB document gives it. Comparing the two netlists is the check
      `netlist.assignment_compare` of c0044.
    - Rejected: overwriting pad nets from the schematic. The import would report a board that does
      not exist.

17. **Rules go through c0042's `map_rules`.**
    - c0042 owns the kind table, the key meanings and the scope grammar. `Rules6` records hold the
      same keys as a rule file's records. Settled interface: the adapter calls
      `map_rules([r.fields for r in doc.rules], origin=<file name>)`; `RuleRecord.fields` (c0041) is
      the whole pair list, so no conversion is needed. The mapper returns rules with ids, native ids
      and a bag of its own; the adapter replaces those three by the ones of its tables, adds the
      provenance, and keeps everything else.
    - A disabled rule is not mapped (c0042's rule won over this change's first text, which gave it
      the severity `ignore`): it is counted with the reason `disabled`.
    - The mapper's per-rule infos are summarised per kind as `altium.import.rule-unmapped`, so an
      import of a saved board, which holds 39 to 50 rules, reports a handful of lines.
    - Rejected: a second mapper in the adapter. Two tables for one format would drift.

18. **`AltiumBackend` reads; it does not write.**
    - `write_kinds == ()`. The neutral `write(design)` returns one text for a board; the Altium
      writers write several binary files from a build and stay experimental features of `build`.
    - `read` of a project file reads the listed sheets and the first PCB document from disk, inside
      the project folder only, as `ProjectSet` skips files outside its root.
    - `inspect` and `check` gate on KiCad kinds before they ask the registry, so they keep refusing
      Altium files until c0044. The spec states this as "registering changes neither command",
      without a scenario that c0044 would make false.
    - Rejected: registering three backends (`altium-sch`, `altium-pcb`, `altium-prj`). One format
      family, one name, as KiCad.

19. **Issue codes use the prefix `altium.import.`.**
    - `altium.*` is taken by the build (`ALTIUM_ISSUE_CODES`), `altium.sch.*`, `altium.schlib.*`
      and `altium.pcb-read.*` by the readers. A third level keeps the tables disjoint.

## Files and public API

| file | public API | state |
|---|---|---|
| `src/fenolite/backends/altium/adapter/__init__.py` | `import_board`, `import_circuit`, `import_project`, `import_footprints`, `import_symbols`, `netlist`, `SheetInput`, `BoardInput`, `ProjectInput`, `NetOptions`, `Netlist`, `NetGroup`, `PinKey`, `LAYERS`, `PIN_TYPES`, `EXT_KEYS`, `IMPORT_ISSUE_CODES`, `EVIDENCE` | new |
| `…/adapter/units.py` | `pcb_length(u) -> Nm`, `pcb_point(x, y) -> Point`, `text_length(text) -> tuple[Nm, bool] \| None`, `angle(d) -> tuple[Udeg, bool]`, `arc_points(cx, cy, r, start, end) -> tuple[Point, Point, Point]` | new |
| `…/adapter/ids.py` | `Ids` (native ids, content ids with occurrence counters), `provenance(file, sha256, locator)`, `bag(pairs)` | new |
| `…/adapter/codes.py` | `IMPORT_ISSUE_CODES`, `issue(code, message, where="", hint="")`, `Census` | new |
| `…/adapter/layers.py` | `LAYERS`, `LayerMap.from_board(record)`, `LayerMap.name(layer_id)`, `stackup(record, ids)` | new |
| `…/adapter/board.py` | `import_board`; nets, classes, footprints, synthesised circuit | new |
| `…/adapter/pads.py` | `pad(record, frame, layers, ids)`, `padstack(record, …)` | new |
| `…/adapter/copper.py` | tracks, arcs, vias, zones, graphics, texts, outline | new |
| `…/adapter/bodies.py` | `component_body(record, frame, …)` | new |
| `…/adapter/library.py` | `import_footprints`, `import_symbols` | new |
| `…/adapter/connectivity.py` | `local_nets(document) -> tuple[LocalNet, ...]`, `on_segment(p, a, b) -> bool` | new |
| `…/adapter/netlist.py` | `netlist`, `NetOptions`, `NetOptions.from_project`, `choose_scope`, `Netlist`, `NetGroup`, `PinKey`, `BusGroup`, `HarnessGroup` | new |
| `…/adapter/circuit.py` | `import_circuit`; components, pins, modules, buses, interfaces, no-connect marks | new |
| `…/adapter/rules.py` | `import_rules(records, layers, ids) -> RuleSet` (calls `read.rules.map_rules`) | new |
| `…/adapter/project.py` | `import_project`, the component and net links | new |
| `src/fenolite/backends/altium/read/bodies.py` | `read_bodies`, `encode`, `BodyRecord` | new |
| `src/fenolite/backends/altium/backend.py` | `AltiumBackend`, `CAPABILITIES`, `READ_KINDS` | new |
| `src/fenolite/backends/altium/__init__.py` | docstring: the package now also reads | changed |
| `src/fenolite/backends/registry.py` | registers both built-ins | changed |
| `src/fenolite/model/circuit.py` | `Bus`, `BusMember`, `Circuit.buses` | changed |
| `src/fenolite/model/board.py` | `HoleShape`, `Padstack.hole_shape`, `.hole_length`, `.hole_rotation`, `PadstackLayer.offset`, `BodyKind`, `ComponentBody`, `FootprintInstance.bodies` | changed |
| `src/fenolite/model/library.py` | `FootprintDef.bodies` | changed |
| `src/fenolite/model/design.py` | `validate()`: `model.unknown-net` for bus members, `model.duplicate-bus-index`, `model.body-height` | changed |
| `src/fenolite/model/__init__.py` | exports `Bus`, `BusMember`, `ComponentBody` | changed |
| `src/fenolite/core/ids.py` | prefixes `bus`, `bdy` | changed |
| `schemas/fenolite.model.v0/{circuit,board,library}.json` | regenerated | changed |
| `docs/formats/altium/connectivity.md`, `import.md`, `pcb-bodies.md` | fact pages | new |
| `docs/altium.md`, `docs/design-model.md`, `docs/formats/units.md`, `docs/cli-contract.md`, `docs/formats/README.md` | sections | changed |
| `tests/unit/backends/altium/adapter/` | unit tests, one file per module | new |
| `tests/_altium_records.py` | builders of in-memory records for tests | new |
| `tests/corpus/test_altium_import.py`, `tests/kicad/altium/test_import_oracle.py` | corpus and oracle tests | new |
| `tests/corpus/manifest.toml`, `tests/corpus/test_manifest.py` | project sets | changed |
| `tests/unit/backends/test_registry.py`, `tests/unit/cli/test_capabilities_backends.py`, `tests/unit/cli/test_capabilities_experimental.py` | pinned values | changed |

Consumed, with the change that creates each:

| name | from |
|---|---|
| `read.sch.read_schematic`, `detect`, `SchDocument` (`components()`, `wires()`, `buses()`, `net_labels()`, `power_ports()`, `ports()`, `junctions()`, `no_ercs()`, `sheet_symbols()`, `harnesses()`, `shown_children`, `children_of`), the typed records and their attributes, `SchLength`, `EVIDENCE` | c0040 |
| `read.schlib.read_schlib`, `SchLibrary`, `SchLibComponent` | c0040 |
| `read.pcb.read_pcbdoc`, `PcbDocument` (`nets`, `components`, `classes`, `rules`, `polygons`, `pads`, `vias`, `tracks`, `arcs`, `texts`, `fills`, `regions`, `shape_regions`, `wide_strings`, `pad_unique_ids`, `storages`, `net_name`, `primitives_of`, `regions_of`), `BoardRecord`, the record classes | c0041 |
| `read.pcblib.read_pcblib`, `PcbLibrary`, `LibFootprint` | c0041 |
| `read.project.load_project`, `AltiumProject`; `read.rules.map_rules` | c0042 |
| `read.cfb` | c0039 (through the readers only) |
| `Circuit.no_connects` | c0036 |
| `Interface(kind="harness")`, `tests/data/altium/hier/` | c0037 |
| `tests/data/altium/routed/`, `docs/formats/altium/pcb-copper.md` | c0038 |

Layering: `backends.altium` imports `model`, `geometry` and `backends.base` only, as its row of
`package-layering` allows. No new sub-package of `fenolite` is created, so the table is unchanged.

## Sources registered by this change

| id | URL | licence | used for |
|---|---|---|---|
| S-0301 | https://www.altium.com/documentation/altium-designer/sch-obj-busbus-ad | Altium documentation, all rights reserved (read for facts) | bus net labels `<name>[<a>..<b>]`, rising or falling; member nets `<name><i>`; a bus needs a label; bus entries; a bus port leaves a sheet |
| S-0302 | https://www.altium.com/documentation/altium-designer/pcb-obj-padpad-ad | Altium documentation, all rights reserved (read for facts) | pad stack modes Simple, Top-Middle-Bottom and Full Stack; pad shapes; hole shapes round, rectangular and slot with a length; plated; mask and paste expansion from a rule or manual; offset of the pad from its hole |
| S-0303 | https://www.altium.com/documentation/altium-designer/pcb-obj-3dbody3d-body-ad | Altium documentation, all rights reserved (read for facts) | 3D body kinds (generic model, extruded, cylinder, sphere); overall height and standoff height; board side and layer; identifier; embedded or linked models |
| S-0305 | reserved: the repository of a third project set, if task 1.4 needs one that is not registered | a licence file that permits the use | sheets, project file and PCB document of one public project |

S-0304 and S-0306 to S-0308 stay unused. The range of this change was moved from S-0237–S-0244 to
S-0301–S-0308 at integration, because S-0235 to S-0239 belong to the range of the active change
c0025. The page on design rules is not registered here: c0041 registers the same URL as S-0286,
and task 1.1 widens that row (a lower priority number is a higher priority; rule scopes as
queries). All pages were consulted on 2026-10-03; no file was downloaded.

Cited, already registered or registered by an earlier active change (task 1.1 widens their "used
for" cells): S-0002, S-0020, S-0130 (records 17, 18, 25, 26, 27, 29, 37 and the cross-sheet flag),
S-0131 (KiCad's schematic importer, facts only), S-0139, S-0140, S-0150 (AltiumSharp version 1
only), S-0160, S-0161 (KiCad's PCB importer, facts only: body records, pad modes, polygons),
S-0164, S-0166, S-0172, S-0174 to S-0176, S-0185 to S-0188 (c0037), S-0195 to S-0200 (c0038).

## Hypotheses registered by this change

All rows: backend `altium`, level `INFERRED` at registration. "Sets" means the test
`tests/corpus/test_altium_import.py -k project_sets`; "oracle" means
`tests/kicad/altium/test_import_oracle.py`.

| id | statement | test | criterion |
|---|---|---|---|
| `H-A-IMP-NETLIST` | The adapter's rules give, for a public project, the netlist of its PCB document | sets | equal partitions for every linked component on three sets from three repositories |
| `H-A-IMP-WIRE` | Wire ends on wires connect; crossings connect only at a junction; labels of one name join within a sheet without letter case | sets, on sets that hold T joints, crossings and repeated labels | no differing net traced to these rules |
| `H-A-IMP-PIN-MID` | An electrical point inside a wire segment connects | sets; the census counts such points | no differing net at such a point, or the count is 0 and the row stays `INFERRED` |
| `H-A-IMP-PORT-ENDS` | A port connects at its location and at its far end, along X or along Y by its style | sets with ports wired at the far end | no differing net at a port |
| `H-A-IMP-SCOPE` | The automatic scope is hierarchical with sheet entries on the top sheet, else flat with ports, else global | sets of both kinds | the chosen scope gives equal partitions |
| `H-A-IMP-POWER-LOCAL` | A power port on a net with a port is local to its sheet in the hierarchical scopes | sets; census of such nets | equal partitions, or count 0 |
| `H-A-IMP-OFFSHEET` | Off-sheet connectors of one name join across the sheets of one parent | sets; census | equal partitions, or count 0 |
| `H-A-IMP-DUP-NAME` | A net label and a power port of one name on unconnected nets are two nets | sets; census of such pairs | the PCB document holds them apart, or count 0 |
| `H-A-IMP-NAME-TIE` | A net with several candidates takes the name by kind priority, then by level, then the smallest text | sets, names compared | at least 95 % of named nets have the PCB net's name; the rest listed by rule |
| `H-A-IMP-NAME-AUTO` | An unnamed net is `Net<ref>_<pin>` of its first pin in natural order | sets, names compared | reported as a count; no criterion blocks |
| `H-A-IMP-HIDDEN-PIN` | A hidden pin whose record names a net joins the power net of that name; the key is recorded by task 1.2 from S-0130 or S-0131 | unit fixture; sets census | the key has a source row, else hidden pins join by position only and the row says so |
| `H-A-IMP-BUS` | Bus members are `<name><i>` in range order, and a bus port joins its sheet entry by position | unit fixture; sets with buses | equal partitions, or count 0 |
| `H-A-IMP-HARN-NAME` | A harness member without a label is named `<harness>.<entry>` | sets with harnesses, names compared | reported as a count |
| `H-A-IMP-LINK` | A PCB component's `SOURCEUNIQUEID` is the unique-id path of one part of its schematic component | sets | at least 95 % of PCB components link by path; the rest by designator |
| `H-A-IMP-FRAME` | Negating Y and inverting the writer's placement gives KiCad's side, rotation and pad positions | oracle | lengths within 10 nm, angles within 1 000 microdegrees, on every corpus document |
| `H-A-IMP-LAYERS` | Naming copper by chain position gives KiCad's copper layers | oracle | equal layer count and equal layer per track and via |
| `H-A-IMP-PADSTACK` | Pad stack modes 0, 1 and 2 and hole shapes 0, 1 and 2 mean what `import.md` states; offsets are per layer | oracle (pad sizes per layer, drill forms) | KiCad's pads agree on size per copper layer, drill size and slot length |
| `H-A-IMP-ZONE` | A polygon's regions are its poured copper, and its vertices its outline | oracle (zone outlines) | outlines within 10 nm |
| `H-A-IMP-BODY` | The body record's keys for heights, projection, identifier and model mean what `pcb-bodies.md` states | `-k bodies_identity`, and an internal check: the overall height is at least the standoff in every body read | byte identity; the check holds for every body |
| `H-A-IMP-SYMFRAME` | A schematic library's pins import, without a flip, to the KiCad symbol they were written from | `test_library.py -k kicad_example`; `kicad-cli sym upgrade` on the same library | equal pins by `(unit, number)` |

No id collides with `docs/hypotheses.md` or with an active change (checked 2026-10-03 with `grep`
over `docs/` and `openspec/`).

## Evidence level per behaviour (before merge)

| behaviour | level at merge | becomes |
|---|---|---|
| model deltas, canonical form, schemas | not format evidence; unit tests | — |
| units and ties | `INFERRED` (`H-A-UNIT`, settled by c0041's oracle) | `ORACLE-VERIFIED(kicad-cli)` with c0041 |
| layers, footprints, pads, tracks, vias, zone outlines of a PCB document | `ORACLE-VERIFIED(kicad-cli)` on 10.0.x when the oracle test passes on the corpus documents; else `INFERRED` | — |
| padstack details KiCad reads | `ORACLE-VERIFIED(kicad-cli)`; offsets and modes it does not read: `INFERRED` | — |
| bodies | `CORPUS-VERIFIED` for byte identity and the height check; key meanings `INFERRED` | — |
| net classes, rules | the level of c0042's mapper (`INFERRED`) | — |
| connectivity, scope | `CORPUS-VERIFIED` per rule that a passing set exercises, with three repositories; else `INFERRED` | — |
| net names | `INFERRED` (supporting counts only) | — |
| own files | `INFERRED` (Fenolite reads what Fenolite wrote) | — |
| libraries | `ORACLE-VERIFIED(kicad-cli)` where c0040's and c0041's library oracles read the same field; else `INFERRED` | — |
| `adapter.EVIDENCE`, the backend's report | `INFERRED`: the lowest wins while any `H-A-IMP-*` row is `INFERRED` | — |

No author report is needed, and none may promote a row.

## Budget

| part | design-days |
|---|---|
| registers, three fact pages, corpus rows | 1.5 |
| model deltas, schemas, validation | 1.0 |
| units, ids, bags, codes, census | 1.0 |
| layers and stack-up | 0.75 |
| nets, classes, footprints, pads, padstacks, synthesised circuit | 1.75 |
| tracks, arcs, vias, zones, outline, graphics, texts | 1.25 |
| body records and bodies | 1.0 |
| footprint and symbol libraries | 1.0 |
| schematic components and pins | 0.75 |
| connectivity within a sheet | 1.5 |
| scope and names | 1.5 |
| buses | 0.75 |
| harnesses and modules | 1.0 |
| rules and project merge | 1.0 |
| backend, registry, capabilities | 0.5 |
| own-file tests | 0.5 |
| corpus sets test | 1.0 |
| oracle test | 0.75 |
| docs and closing | 0.5 |
| **total** | **19.0** |

A size, not calendar time.

## Risks / Trade-offs

- [The connectivity rules are wrong on a real project] → the sets test fails loudly. The differing
  rule is fixed, or the set is marked `known-diff` with its cause, and the rule stays `INFERRED`.
- [Fewer than three repositories give a full set] → connectivity stays `INFERRED`; the change still
  merges, and the report says so. Open Question 5.
- [A sibling reader changes a name] → the adapter touches reader names in few places: the functions
  that take records. The consumed-names table above is the checklist at implementation.
- [The oracle disagrees because KiCad's importer differs] → differences are listed by kind in
  `import.md` with their cause; never excluded by file.
- [Repeated sheets give duplicate references] → a warning explains it, and with a PCB document the
  references come from the link. Annotation files are v0.5b.
- [Inexact conversions accumulate] → at most 0.5 nm per value, and the original integer is kept.
- [Body keys are guessed] → a key is typed only with a source row; the rest stays in `properties`.
- [The registry now imports a second module on first use] → `backend.py` imports no reader until
  `read`; a test checks `sys.modules`.
- [Three more model fields before the model freeze] → all additive, all with defaults; old files
  load unchanged; the schemas are regenerated.
- [Large boards are slow] → connectivity is `O(n log n)` with a sweep over segment boxes
  (`geometry.index`); the board import is linear.

## Migration Plan

- No data migration: the model deltas have defaults, and `SCHEMA_VERSION` stays `"0"`.
- `result.backends` of `fenolite capabilities` gains the entry `altium` before `kicad`. A consumer
  that read `backends[0]` as KiCad must select by name; `docs/cli-contract.md` says so, and
  `CHANGELOG.md` lists it under "Changed".
- **Archive order.** c0032 and c0035 (the text of "Experimental features in capabilities" that this
  change modifies), c0036 (`Circuit.no_connects`), c0037 and c0038 (samples and sources), c0039 to
  c0042, then c0043; c0044 and c0045 after it.
- **design-model.** This change only ADDS three requirements. Among the active changes, c0028 and
  c0031 MODIFY "Identifier derivation", c0030 ADDS "Footprint fields", c0031 ADDS "Zone settings in
  the board model" and c0036 ADDS "No-connect marks in the circuit model". None touches a
  requirement of this change, and no name collides, so c0043 may archive before or after c0028,
  c0030 and c0031. The prefix table gains `bus` and `bdy` here and `fld` in c0030: both edits are
  to `core/ids.py`, merged by hand.
- **backend-protocol.** "Backend registry" is copied from the living spec; no active change
  modifies it (c0015, c0020, c0028, c0029 and c0044 only ADD requirements).
- **cli-contract.** "Backends in capabilities" is copied from the living spec. "Experimental
  features in capabilities" is copied from c0035's MODIFIED text, which must be archived first.
- Rollback: remove the registration; nothing else depends on the backend until c0044.

## Open Questions

1. **Settled (integration, 2026-10-03): `map_rules` of c0042 accepts the rule records of a PCB
   document** as field lists, `RuleRecord.fields` (Decision 17). The adapter never holds a rule
   table.
2. **Settled (integration, 2026-10-03): half to even everywhere**, the rule of
   `docs/formats/units.md`. c0041's `pcbprims.to_nm` now returns `core.units.u_to_nm`.
3. **Should a copper fill or region with a net be more than a `Graphic`?** Default: a `Graphic`
   with the net in its bag, and a count. An additive `Graphic.net_id` would let checks and analyses
   use it; that is a later model change.
4. **Should mechanical layers map to `F.Fab`, `F.CrtYd` and their bottom partners?** Default: no;
   `Mech.<n>` always. The layer-kind keys of newer files are not in a fact page yet.
5. **Which third repository gives a project set?** S-0187 and S-0188 give two. Default: task 1.4
   takes the first of S-0174, S-0175 and S-0176 whose repository holds the project file and the
   sheets at the registered commit under the registered licence; else a new repository as S-0305;
   else connectivity stays `INFERRED`.
6. **Should a schematic read alone report missing sheets as errors?** Default: warnings; one sheet
   is a valid input.
7. **Should `Bus` hold members without a net?** Default: no; a gap in the indexes says it.
8. **For the maintainer:** is a board-only read (`.PcbDoc`) expected to carry pin types? Default:
   `unspecified`, since the file states none.

## Implementation notes

Recorded while implementing (2026-10-05), on `origin/dev` with c0040, c0041 and c0042 landed. Where a note
says "spec amended", the delta in this folder was changed to what the scenarios and the files show.

**Names taken from the sibling changes, re-checked before use.**

1. `read.sch` is a package (`read/sch/`), not a module; `SchDocument` and the record classes are imported
   from it. A binary record's locator in c0040 is `<stream>/record <frame>`; the adapter writes its own
   locators `FileHeader#<index>` and `Additional#<index>` from `RecordRef`, as this change's spec states.
2. `PcbDocument` has no body records: the adapter reads `storages["ComponentBodies6"]["Data"]` through
   `read.bodies`. Polygon and outline vertices are exact fractions of units (`OutlineVertex`), component
   positions too; region vertices are doubles in the plain storage.
3. `ProjectOptions` (c0042) has no key for "Higher Level Names Take Priority": `NetOptions.from_project`
   leaves `higher_level_names_first` at its default (`False`). `net_scope` spells `strict-hierarchical`;
   the adapter's scope is `strict_hierarchical`.
4. `fenolite.backends.base.Backend` is not runtime-checkable: the backend's conformance is a typed
   assignment that pyright checks (`backend._BACKEND`), as the KiCad backend does.

**Deviations from the text of the design, each with its reason.**

5. **`import_project` takes records.** `import_project(project: ProjectInput)`; the backend builds the
   `ProjectInput` from `load_project`. The adapter opens no file, so it cannot take an `AltiumProject`,
   which holds paths. `BoardInput` and `RulesInput` are exported too. Spec amended.
6. **`import_rules(records, ids, *, file, sha256, issues)`** takes no layer map: the mapper of c0042 gives
   no rule a layer.
7. **Evidence outside the adapter.** `EVIDENCE` lives in `backends/altium/import_evidence.py` and is
   re-exported by `adapter`: the registry scenario forbids loading the adapter at registration, and the
   capability report needs the evidence. Extra modules that the file table did not name: `adapter/context.py`
   (the state of one board import), `adapter/parts.py` (the components of a sheet), `adapter/pins.py`
   (`PIN_TYPES`), `adapter/evidence.py`.
8. **Stack-up.** Saved documents list overlay, paste and solder-mask entries in the physical list, and
   the blink scenario counts copper, dielectric, copper. Only copper and dielectric entries enter the
   stack-up. Spec amended.
9. **Slot scenario.** 1 mm and 2.5 mm are no whole numbers of units (1 mm reads back as 1 000 001 nm), so
   the scenario now uses 40 mil and 100 mil. The slot rotation is read as relative to the pad. Spec amended.
10. **Padstack fields.** `Padstack.hole_shape`, `hole_length` and `hole_rotation` were already in the model
    (c0056, which also made the KiCad reader type a slotted hole); this change adds
    `PadstackLayer.offset`. `Circuit.buses` sits before `no_connects`, which an existing test keeps last.
    Spec amended (`design-model`).
11. **Paste and mask pairs** are given only when the mode is not 1 (from a rule), so that a plain pad has
    an empty bag. The key `shape` (the shape number of a `custom` pad) was added to `EXT_KEYS`. Spec amended.
12. **Hidden pins.** No fact page holds a key for a hidden pin's net, and S-0185 says that Altium no
    longer supports one; no key is read (`H-A-IMP-HIDDEN-PIN` settled as written). Spec amended.
13. **An unconnected pin is in no net.** A net without an identifier that holds fewer than two pins is
    dropped: the models that Fenolite builds, and the PCB documents of the sets, give such a pin no net.
    The first text kept every net with a pin and named it `Net<ref>_<pin>`. Spec amended.
14. **Ports and sheet entries that carry a bus or a harness are no net identifiers.** Otherwise each gave
    an empty net named after the harness.
15. **The ASCII form of the hierarchical sample holds no harness** (the writer reports
    `altium.not-lowered`), so its import has no interface; the binary form has one.
16. **One issue per skipped document.** The project reader's `document-outside` and `document-missing`
    issues about a sheet or a PCB document are replaced by `altium.import.document-skipped`. Spec amended.
17. **The pinned test `tests/unit/cli/test_capabilities.py`** needed no change; `test_registry.py`,
    `test_capabilities_backends.py` and `test_capabilities_experimental.py` were updated as task 7.2 says.
    The living text of "Experimental features in capabilities" lists `altium_harness` among the schematic
    writer's kinds (c0037); this delta's copy of that list is older and was left for the archive step.
18. **A component with a value or a footprint that the script leaves empty** is written with its symbol's
    value and footprint; the own-file tests compare what the script states.

**What the public project sets changed (task 8.3).**

19. **Five sets, not three.** S-0174, S-0175 and S-0176 each hold their project file and sheets at the
    registered commit, so all three became sets (03, 05, 04) beside S-0187 (01) and S-0188 (02); S-0305 is
    unused. 29 rows were added (25 sheets, 3 project files, 1 PCB document, the last one `heavy`), and 18
    tagged. The new use `altium-import` is in `ALTIUM_READER_USES` and in the fetch step of the `kicad-10`
    job; that job excludes heavy rows, so set 01 is skipped there and runs with `FENOLITE_HEAVY=1`.
20. **Harness members by dotted labels.** One saved sheet (S-0188) names the members of a harness with net
    labels `<harness>.<entry>` on wires, the harness going by the net label on its line; without that rule
    13 nets stayed apart. Fact row added to `connectivity.md`, then the code and a regression in the corpus
    test. Spec amended.
21. **Harness ports and sheet entries by touching.** 11 sheet entries of one set (S-0187) lie on harness
    line ends without `HARNESSTYPE`; a port or entry now belongs to a harness by touching it. Spec amended.
22. **The pin-to-pad map.** 111 map records of two sets name other pads than the pin's designator. The
    comparison applies the map (`parts.PartGroup.pin_pads`); the model's components do not carry it, which
    `docs/altium.md` lists under what is not imported. A pair is compared when the sheets hold the pin and
    the PCB document the pad. Spec amended.
23. **Set 02 is a known difference.** Two pins of two four-pin components are unwired on their sheet (no
    wire within 15 units) and carry a net in the PCB document: 6 differing groups, 156 of 158 nets equal.
    The count is pinned in the test (`KNOWN_DIFFS`), and the row's note states the cause; the note form of
    `corpus-policy` gained the sentence `Known difference: …`. `altium_set_problems` is called beside
    `manifest_problems`, not inside it, because a test of c0042 checks a subset of the rows.

**Hypotheses after tasks 8.1 and 8.2 (task 10.2).**

- `CORPUS-VERIFIED`: `H-A-IMP-NETLIST`, `-WIRE`, `-SCOPE`, `-LINK` (four sets of four repositories agree:
  509 nets, 0 differing groups; 879 components of five sets link by path).
- `ORACLE-VERIFIED(kicad-cli)` on 10.0.6: `H-A-IMP-FRAME`, `-LAYERS`, `-ZONE` (outlines): 424 footprints,
  1 526 pads, 3 069 tracks, 1 166 vias and 44 zone outlines agree on the two authored documents and the
  seven corpus rows.
- `INFERRED`, with the reason in each row: `-PIN-MID`, `-OFFSHEET`, `-DUP-NAME`, `-BUS` (no set exercises
  them), `-PORT-ENDS`, `-POWER-LOCAL`, `-HARN-NAME` (fewer than three repositories), `-NAME-TIE`,
  `-NAME-AUTO` (names are supporting data), `-HIDDEN-PIN`, `-PADSTACK` (the oracle compares simple pads
  only), `-BODY` (identity and the height check hold; key meanings have one source), `-SYMFRAME`.
- No row was refuted. `adapter.EVIDENCE` and the backend's report stay `INFERRED`: the lowest wins.

**Left open.**

- Task 10.1 (the full `make check` and the full `uv run pytest -q`) is left for the coordinator's single
  run at landing, by the load rule of this session; `make check-fast` and the tests of every touched file
  ran here.
- Region holes of zone fills, the fills themselves against KiCad, per-layer pad sizes, slots and offsets
  against KiCad, and `Component.pin_pad_map` from the map records are not done by this change.

**Added at landing (coordinator, 2026-10-05).** The change lands on top of a batch that brings `fenolite explain` (c0066), whose test asks for an entry per issue code. `IMPORT_ISSUE_CODES` is therefore listed in `explain.TABLES`, and `src/fenolite/cli/data/explain.toml` holds one entry for each of the 32 `altium.import.*` codes, with the meaning of the table in `docs/cli-contract.md` ("Altium import") and a fix written for it. Tasks 10.1 and 10.3 are ticked on the full suite run at landing (7622 passed) before this rebase; after it, `make check-fast` ran on the stacked commits.
