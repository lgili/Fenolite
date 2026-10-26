# dsl-footprint-authoring Specification

## Purpose
Define and register project-authored footprints using the Fenolite DSL and supported file backends.
## Requirements
### Requirement: Define and register footprints
The DSL SHALL let a design declare a footprint using safe library and footprint identifiers, supported pads and graphics, and integer-nanometre geometry. Registration SHALL reject duplicate library IDs and invalid geometry before writing output. Authored definitions SHALL remain outside the canonical model and `.fenolite` persistence.

#### Scenario: Register a valid footprint
- GIVEN a design and a footprint with a safe ID, one valid pad, and supported graphics
- WHEN the footprint is registered
- THEN the design exposes its `FootprintDef` by library ID for building
- AND the canonical model contains no library definition

#### Scenario: Reject invalid or duplicate definition
- GIVEN a design with an authored footprint
- WHEN another definition has the same library ID, an unsafe name, non-positive pad size, or invalid drill
- THEN registration or construction raises `DslError` before any files are written

### Requirement: Assign authored footprints to parts
The DSL SHALL allow a part's existing `footprint` field to name an authored footprint's library ID. Build resolution SHALL prefer a registered authored definition with the exact ID and otherwise preserve current library resolution behavior. Pin-to-pad assignment SHALL use a part's explicit per-instance map, with identity mapping for unmapped pins. Mappings SHALL be one-to-one and SHALL be validated against resolved symbol pins and footprint pads before any output is written. Nets and no-connects SHALL continue to refer to symbol pin designators.

#### Scenario: Build with an authored footprint
- GIVEN a part assigned to a registered footprint and symbol pins whose numbers exist on that footprint
- WHEN a supported backend build resolves the part
- THEN that exact authored definition is used for placement and library output
- AND no external footprint library lookup is required for that part

#### Scenario: Reject a missing assigned pad
- GIVEN a registered footprint assigned to a part
- WHEN a connected symbol pin number has no matching pad number
- THEN build reports the existing located pin/pad mismatch and writes no partial output

#### Scenario: Build with a remapped pin
- GIVEN a part maps symbol pin `2` to physical pad `3`, and pin `2` is connected to a net
- WHEN the design is built
- THEN pad `3` carries that net while the circuit member remains pin `2`

#### Scenario: Reject invalid mappings
- GIVEN a mapping with duplicate target pads or a source/target absent from the resolved part
- WHEN the design is built
- THEN the build reports a located mapping issue and writes no partial output

### Requirement: Serialize deterministic backend footprints
KiCad build SHALL serialize authored definitions into a project `.pretty` library and use the same geometry on the board. The experimental Altium build SHALL lower the documented supported subset into its PCB library. Unsupported geometry SHALL be refused with a located issue rather than silently omitted. Repeated builds from equal inputs SHALL produce byte-identical authored footprint files.

#### Scenario: Write a supported footprint
- GIVEN an authored footprint composed only of supported pads and graphics
- WHEN a dry-run build is planned and then confirmed
- THEN the output plan includes the corresponding generated library files and board placement
- AND the generated footprint bytes are deterministic

#### Scenario: Refuse unsupported geometry
- GIVEN an authored footprint containing a feature outside the supported subset
- WHEN a backend build is requested
- THEN it reports an actionable unsupported-feature issue
- AND it does not write an incomplete footprint

### Requirement: Author slotted through-hole pads
The footprint DSL SHALL support a slot whose drill width is `drill`, whose overall length is `drill_length`, and whose axis is `drill_rotation` relative to the footprint. Slot length SHALL be at least its width. Round drills SHALL remain the default. Writers without evidenced slot serialization SHALL refuse the footprint with a located unsupported-feature issue. The KiCad writer SHALL refuse an axis that its oval drill form cannot encode.

#### Scenario: Serialize a slot to KiCad
- GIVEN an authored through-hole pad with slot width 0.8 mm, length 1.6 mm and `drill_rotation=90`
- WHEN its KiCad footprint is written
- THEN the drill node represents an oval of that width and length

#### Scenario: Refuse slot lowering without evidence
- GIVEN an authored slot footprint built for a target whose writer does not support slots
- WHEN the build is planned
- THEN it reports the target-specific unsupported geometry and writes no incomplete footprint

### Requirement: Author repeated physical pads for one terminal

`Footprint.pad(number, ..., shared=False)` SHALL keep pad numbers unique by default. A caller MAY declare a subsequent physical pad with a number already present only by passing `shared=True`. Passing `shared=True` without an earlier pad of that number MUST raise `DslError`. All physical pads with the same number SHALL remain separate pads and receive the electrical net of that footprint pad number during build resolution. Their generated entity IDs MUST be unique and deterministic; existing IDs of footprints with unique pad numbers MUST remain unchanged.

#### Scenario: Two physical lands share a symbol terminal

- **GIVEN** a footprint with pad `2` and a second pad `2` declared with `shared=True`
- **WHEN** the footprint is built for a part whose symbol pin `2` is on net `GND`
- **THEN** both physical pads numbered `2` carry net `GND` and have distinct stable IDs

#### Scenario: Accidental duplicate remains an error

- **GIVEN** a footprint that declares pad `2` twice without `shared=True`
- **WHEN** the second pad is declared
- **THEN** `DslError` reports the duplicate pad number

#### Scenario: Shared flag requires a prior pad

- **GIVEN** a footprint with no pad `2`
- **WHEN** pad `2` is declared with `shared=True`
- **THEN** `DslError` reports that there is no earlier pad to share

### Requirement: Unnumbered hole pads in authored footprints
`Footprint.pad(number, …)` SHALL accept the empty number `""` for a pad of kind `np_thru_hole`, the form of a mounting hole in KiCad's own library (`H-K-HOLE-FOOTPRINT`), and SHALL refuse it, with `DslError`, for every other kind.
- One footprint MAY hold several unnumbered pads without `shared=True`. The k-th, counted from 1 in declaration order, MUST have the id `derived_id("pad", "fenolite.dsl", "<lib id>:pad::<k>")`, so the ids of numbered pads do not change.
- An unnumbered pad maps to no pin: the build MUST NOT give `build.pad-without-pin` for it, and a `pad_map` that names `""` MUST raise `DslError`.
- The written footprint MUST hold `(pad "" np_thru_hole …)`; the pad's default layers stay `*.Cu` and `*.Mask`, and the drill rules of the other through-hole pads apply.

#### Scenario: Two unnumbered holes
- **GIVEN** `fp = Footprint("Proj", "Two_Holes")` and two calls `fp.pad("", at=(mm(0), mm(0)), size=(mm(3.2), mm(3.2)), shape="circle", kind="np_thru_hole", drill=mm(3.2))` and `fp.pad("", at=(mm(10), mm(0)), size=(mm(2), mm(2)), shape="circle", kind="np_thru_hole", drill=mm(2))`
- **WHEN** `fp.definition` is read and its `.kicad_mod` is written
- **THEN** its two pads have the ids `derived_id("pad", "fenolite.dsl", "Proj:Two_Holes:pad::1")` and `…:pad::2`, and the text holds `(pad "" np_thru_hole circle` twice

#### Scenario: Empty number refused for other kinds
- **WHEN** `fp.pad("", at=(mm(0), mm(0)), size=(mm(2), mm(2)), shape="circle", kind="thru_hole", drill=mm(1))` and `fp.pad("", at=(mm(0), mm(0)), size=(mm(1), mm(1)))` are called
- **THEN** each raises `DslError` naming the pad number

#### Scenario: No pin for an unnumbered hole
- **GIVEN** a part whose authored footprint holds two numbered pads, both connected, and one unnumbered hole
- **WHEN** it is built with `--dry-run --json`
- **THEN** the exit code is 0 and `issues` holds no `build.pad-without-pin`

### Requirement: Assembly and test properties on authored pads
`Footprint.pad(…, fab_property=None)` SHALL set the mark of an authored pad: `None`, or a value of `fenolite.model.board.PadFabProperty`, stored as `Pad.fab_property` of the definition and written by the footprint writer ("Assembly and test pad properties on boards and footprints").
- Any other value MUST raise `DslError` naming `fab_property`.
- `castellated` and `mechanical` MUST be refused with `DslError` on a pad whose kind is not `thru_hole`: KiCad's DRC reports such a pad as `padstack` (`H-K-PAD-FABPROP`).
- A pad declared without the keyword MUST be unchanged, and the bytes of its footprint file MUST NOT change.

#### Scenario: A marked BGA ball
- **GIVEN** `fp = Footprint("Local", "Ball", kind="smd")`
- **WHEN** `fp.pad("A1", at=(mm(0), mm(0)), size=(mm(0.3), mm(0.3)), shape="circle", fab_property="bga")` is called and the footprint is written for target 10
- **THEN** the definition's pad has `fab_property == "bga"` and the written pad holds `(property pad_prop_bga)`

#### Scenario: Refused marks
- **GIVEN** an SMD footprint
- **WHEN** a pad is declared with `fab_property="castellated"`, and another with `fab_property="fiducial"`
- **THEN** both raise `DslError`, the first naming `castellated` and `thru_hole`, the second naming `fab_property`

### Requirement: Authored footprints carry Reference and Value
`fenolite.backends.kicad.mod.prepare_authored_definition` SHALL give a definition without a KiCad slot list, whether authored with `fenolite.dsl.Footprint` or taken from the built-in catalog, the two properties `Reference` and `Value`, so that the footprint written to the project library and the footprint placed on the board are conventional KiCad footprints.
- The two `property` children MUST come after the `kind` slot and before the pads, `Reference` first, with the texts, layers, positions, size and stroke of `embed.default_fields(defn)` (`kicad-file-backend`, "Mandatory fields of a placed footprint").
- `FootprintDef.properties` of the prepared definition MUST hold `Reference` with the text `REF**` and `Value` with the footprint's name; a `properties` entry the definition already has under either name MUST win over the default text. A footprint definition of the built-in catalog holds no such entry, so the library text of a catalog footprint's `Reference` is `REF**`.
- A definition that already has a slot list MUST be returned unchanged.
- `mod.write_footprint` of a prepared definition MUST write both properties, with uuids that derive from the lib id and the property name. Two builds from equal inputs MUST still give byte-identical footprint files ("Serialize deterministic backend footprints").
- `Part.field("Reference", …)` and `Part.field("Value", …)` MUST apply to a part whose footprint is authored or from the catalog, as they do for a library footprint.
- A definition that is not prepared MUST NOT gain the properties: the Altium build, which reads definitions as the script or the catalog gives them, sees none (`fenolite-component-catalog`, "Catalog-only design passes check").
- `docs/dsl.md` MUST say, under "Authored footprints", that the two fields are generated and where they are placed.

#### Scenario: Authored two-pad footprint
- **GIVEN** the footprint `Local:TwoPad` of `docs/dsl.md`, "Authored footprints", registered in a design whose part `R1` uses it
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_embed_fields.py -k authored` builds the design for targets 9 and 10
- **THEN** `lib/Local.pretty/TwoPad.kicad_mod` holds `(property "Reference" "REF**"` and `(property "Value" "TwoPad"`, the board footprint holds `Reference` `R1`, and a second build writes the same bytes

#### Scenario: Field request on a catalog part
- **GIVEN** a design whose part `R1` uses `Fenolite:Chip_0603` and calls `r1.field("Reference", outside="top")` and `r1.field("Value", visible=False)`
- **WHEN** the design is built
- **THEN** the exit code is 0, the `Reference` field of `R1` lies beside the top of its courtyard box, and its `Value` field is hidden

#### Scenario: Every catalog footprint
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_embed_fields.py -k every_catalog` prepares and places each footprint that `catalog.list_entries(kind="footprint")` names
- **THEN** each instance holds both fields, and neither field's position lies inside the footprint's extent box

### Requirement: Net-tie groups in authored footprints
`Footprint.net_tie(*numbers)` SHALL declare one net-tie group of an authored footprint: pads of different nets that the footprint joins on purpose, through overlapping pads or a copper graphic (`line`, `rect`, `circle` or `polygon` on a copper layer). A group MUST hold at least two distinct non-empty pad numbers, else the call raises `DslError`.
- `definition` MUST raise `DslError` when a number of a group names no pad of the footprint, or when a number is in two groups; it MUST carry the groups in `FootprintDef.net_ties`, in call order, each in the order of its numbers.
- The KiCad footprint writer MUST emit one `(net_tie_pad_groups "<group>" …)` child right after `attr`, one string per group, its numbers joined with `", "`, as KiCad's own library writes it (S-0018, S-0042). A definition without groups MUST emit no such child, so an authored footprint written before this change keeps its bytes.
- The board that `build` writes MUST carry the child in the placed footprint, and KiCad 9.0.9 and 10.0.6 MUST load it and honour the group (`kicad-oracle`, "Net-tie facts are probed").
- The Altium build MUST NOT drop a group silently: it writes the pads and their copper as for any footprint, writes no net-tie mark, and reports the footprints that have groups in one `altium.not-lowered` info whose `where` is the kind `net-tie` (`backends.altium.lower`). The kind MUST NOT be in `LOSS_KINDS`: the pads are written, so the issue is an `info` and a write without `allow_lossy` is not refused. Its copper guard judges the tied pads; a `copper.short` waiver accepts them (`design-dsl`, "Waivers in the copper guard").

#### Scenario: Emitted form
- **GIVEN** a footprint with pads `1` and `2`, a copper line between them on `F.Cu`, and `fp.net_tie("1", "2")`
- **WHEN** `uv run pytest tests/unit/dsl/test_net_tie.py -k emit` writes its definition for targets 9 and 10
- **THEN** the text holds `(net_tie_pad_groups "1, 2")` as the child that follows `attr`, and the definition has `net_ties == (("1", "2"),)`

#### Scenario: Refused groups
- **WHEN** `net_tie("1")` is called, then `net_tie("1", "9")` on a footprint without pad `9`, then `net_tie("1", "2")` and `net_tie("2", "3")` on one footprint, and `definition` is read
- **THEN** the first call raises `DslError`, and `definition` raises `DslError` naming pad `9`, then pad `2`

#### Scenario: No group, same bytes
- **GIVEN** an authored footprint without `net_tie`
- **WHEN** it is written for targets 9 and 10
- **THEN** the bytes equal those written before this change, and no `net_tie_pad_groups` child appears

#### Scenario: A net tie in an Altium build
- **GIVEN** a design that places as `NT1` an authored footprint with two pads `1` and `2` 0.5 mm apart and `fp.net_tie("1", "2")`, its pads on nets `A` and `B`
- **WHEN** `uv run pytest tests/unit/cli -k "altium and net_tie"` builds it with `--target altium --dry-run --json`
- **THEN** the exit code is 0, the planned `.PcbLib` and `.PcbDoc` hold both pads, and `issues` holds one `altium.not-lowered` info whose `where` is `net-tie` and whose message counts one footprint
