## ADDED Requirements

### Requirement: Repeated sheets as channels
The import SHALL instantiate the child sheet of a sheet symbol once per channel. `adapter.netlist.parse_repeat(text)` SHALL return `Repeat(name, first, last)` for a sheet symbol designator of the form `Repeat(NAME, a, b)` (case-insensitive keyword, unsigned integer bounds, a name that is not empty) and `None` for any other text.
- A repeat MUST give `last - first + 1` instances, in index order. A sheet symbol without a repeat gives one instance, and two sheet symbols that name one file give one instance each.
- Each instance of a repeat MUST be a `Module` whose name is the channel identifier followed by `[<index>]`, and whose extension bag holds the sheet symbol's unique id (`sheet_symbol`) and the index (`channel_index`).
- The components, pins and local nets of the child sheet MUST exist once per instance, with ids derived from the instance path, so that two imports of one project give equal ids. A repeat has one unique id for all its channels: the native id of a component of channel `i` MUST name the sheet symbol as `<unique id>[<i>]`, a form of this import that is recorded in `docs/formats/altium/connectivity.md` as not Altium's.
- A repeat that does not parse, whose first index is above its last, or that would bring the instances of the project above `MAX_CHANNELS` (256) MUST give one instance and `altium.import.repeated-sheet` (warning) naming the sheet symbol. An instantiated repeat MUST give `altium.import.channels` (info) with the sheet symbol and its count.
- A project without a repeat and without a file named twice MUST import to the canonical model it imported to before this change, except for the `pin_pad_map` and the `pin_pads` bag pairs that "Pin-to-pad map of a footprint model" gives its components.
- No public file of the corpus holds a `Repeat` statement: the facts of this requirement MUST be labelled `INFERRED` on the facts page, with `H-A-IMP-RPT-COUNT`, until an author report or a public file settles them.

#### Scenario: Two channels
- **GIVEN** the authored project `tests/data/altium/channels/two/` whose top sheet holds a sheet symbol `Repeat(CH,1,2)` on a child sheet with `R1` and `C12`
- **WHEN** the folder is read and the import runs
- **THEN** the circuit holds four channel components in the modules `CH[1]` and `CH[2]`, `altium.import.channels` names `CH` with the count 2, and no `altium.import.repeated-sheet` is reported

#### Scenario: Unparsable repeat
- **GIVEN** the same sheets with the designator `Repeat(CH,2,1)`
- **WHEN** the import runs
- **THEN** one instance is read and `altium.import.repeated-sheet` names `CH`

#### Scenario: Single-channel projects unchanged
- **WHEN** `uv run pytest tests/corpus/test_altium_channels.py -k unchanged` imports the corpus sets without a repeat
- **THEN** none has a channel, a channel source or a channel issue

### Requirement: Channel designators
Each component of a channel SHALL get the designator its project gives it, from the first of these sources that knows it: (1) the component of the project's PCB document whose unique-id path names the channel's sheet symbol and the sheet component, whose own designator is taken (its source designator is the sheet's); (2) the entry of the project's annotation file for that unique-id path; (3) `adapter.channels.channel_designator(format, designator, names, style=…, separator=…, indexes=…)` with the designator format, the room naming style and the level separator of the project file, the designators of the sheet symbols from the top (for a repeat its channel identifier) and the channel index of each (`None` for a plain sheet symbol).
- The keywords `KEYWORDS` and the styles `FLAT_STYLES`, `PATH_STYLES`, `NUMERIC_STYLES` and `ALPHA_STYLES` MUST be those recorded in `docs/formats/altium/connectivity.md`, each fact labelled. For a channel of a repeat, `$ChannelIndex` MUST be its index, `$ChannelAlpha` the letter of an index from 1 to 26, `$ChannelPrefix` the channel identifier, and the room name the identifier followed by the index or by its letter, as the style says.
- A format with `$ChannelIndex` or `$ChannelAlpha` on a plain channel, a `$` that starts no keyword, a room name under a style outside the recorded ones, a letter for an index outside 1 to 26, the mixed style on a channel of a repeat, a flat style under a repeat higher up, and a format that would give the channels of one repeat one designator MUST NOT be guessed: the components get `<designator>@<channel path>`, where a channel of a repeat is written as its identifier followed by its index, and one `altium.import.channel-naming` (warning) gives their count. Sheets read without a project file MUST keep the designators of the sheet.
- The import result MUST report, per source, how many components took their designator from it.
- No two components of the imported circuit MAY share a reference because of a repeat; when sources 1 and 3 disagree for components, source 1 wins and one `altium.import.channel-naming` gives their count and both values of the first.
- The unique-id path of a board component of a channel of a repeat has no recorded form (`UNKNOWN` on the facts page): the import MUST NOT try a path for it. A board component MAY link to such a channel component only when its own designator is the channel designator of source 3 and its source designator the designator of the sheet (`altium.import.linked-by-designator`); the channel components that no board component links to MUST be counted by one `altium.import.channel-naming`.
- Source 2 is not implemented while "Annotation file read" is open: an absent or empty annotation file changes nothing.

#### Scenario: Designators from the board
- **GIVEN** the corpus project `altium-set:02`
- **WHEN** it is imported and `fenolite check` runs on it
- **THEN** no non-empty reference is held twice in the circuit, and every component of a repeated sheet has the designator of its board component

#### Scenario: Designators from the naming format
- **GIVEN** `tests/data/altium/channels/two/` without a PCB document and without an annotation file
- **WHEN** the import runs
- **THEN** the four references are those of `channel_designator` for the project's format (`R1_CH1`, `R1_CH2`, `C12_CH1`, `C12_CH2`), and the result counts four components for the source `format`

#### Scenario: Unknown format
- **GIVEN** the same sheets with a designator format that holds a `$` word outside `KEYWORDS`
- **WHEN** the import runs
- **THEN** `altium.import.channel-naming` is reported once, and the references are `R1@CH1`, `R1@CH2`, `C12@CH1` and `C12@CH2`

### Requirement: Channel nets
The nets of a repeated sheet SHALL be resolved per channel.
- A net that the child sheet does not export MUST be one net per channel. When a net label names it, its name MUST be the label as `channel_designator` renames a designator, with the label as an alias, and the label itself when the format cannot be applied; when no identifier names it, its system name MUST be built on the channel designator of its component (`Net<channel designator>_<pin>`).
- A sheet entry `Repeat(NAME)` MUST connect the port `NAME` of channel `i` to member `i` of the parent's bus `NAME`, counted from the first channel in the order of the bus identifier; a parent that holds no such bus, or one with fewer members than channels, MUST give `altium.import.channel-naming` (warning) naming the entry and the count of channels left without a member. The statement MUST NOT name a net.
- Any other sheet entry MUST connect every channel to the one parent net.
- A global net label or power port MUST be one net for all channels, under the net identifier scope that "Net identifier scope" resolves.

#### Scenario: Shared and per-channel nets
- **GIVEN** `tests/data/altium/channels/two/`, whose child sheet has a port `VCC` under the entry `VCC`, a port `OUT` under the entry `Repeat(OUT)` and an internal net `MID`
- **WHEN** the import runs
- **THEN** `VCC` holds pins of both channels, `OUT1` and `OUT2` hold one channel each, and the circuit holds the two nets `MID_CH1` and `MID_CH2`

#### Scenario: Corpus project agrees with its board
- **WHEN** `uv run pytest tests/corpus/test_altium_channels.py -k nets` compares the imported schematic of `altium-set:02` with its PCB document
- **THEN** no pin of a repeated sheet is on one side only, and none is on another net than its pad

### Requirement: Pin-to-pad map of a footprint model
When the current footprint model of a schematic component carries a pin map, the imported component SHALL carry it in `Component.pin_pad_map`, so that the element of each mapped pin in the assignment comparison and in level 2 of `equivalent` is `REF-<pad>` with the pad the map gives; without a map the pin number is the pad name. The members of the circuit's nets stay keyed by pin number.
- `pin_pad_map` gives a pin one pad and a pad one pin ("Persist per-component pin-to-pad maps" of `design-model`). A map record that lists several pads MUST give the pin its own designator when the record lists it, else the first pad listed; a record that lists no pad, and one whose pad another pin already stands for, MUST leave the pin its own designator. Each such record MUST be kept whole in the component's extension bag (`pin_pads`, `<pin>=<pad>,<pad>…`), and one `altium.import.pin-map` (info) per import MUST give their count.
- A record that names no pin of the component MUST be left out.
- A net of the PCB document that the sheets lack MUST list the pin of each pad, through the map.

#### Scenario: Mapped pins
- **GIVEN** an authored sheet whose component `Q1` maps the pins `1, 2, 3` to the pads `G, D, S`
- **WHEN** the schematic netlist of the import is built
- **THEN** its elements for `Q1` are `Q1-G`, `Q1-D` and `Q1-S`

#### Scenario: Records the map cannot hold
- **GIVEN** an authored sheet whose component maps pin `1` to the pads `1, 4`, pin `2` to `5, 6` and pin `3` to no pad
- **WHEN** the import runs
- **THEN** `pin_pad_map` is `(("2", "5"),)`, the bag holds the three records, and `altium.import.pin-map` counts three

## MODIFIED Requirements

### Requirement: Net identifier scope
`adapter.netlist` SHALL join local nets across sheets by the scope of `NetOptions.scope`, one of `automatic`, `flat`, `hierarchical`, `strict_hierarchical` and `global` (S-0185).
- `automatic` MUST choose `hierarchical` when the top sheet holds a sheet entry, else `flat` when any sheet holds a port, else `global`. The top sheets are the sheets that no sheet symbol names. The chosen scope MUST be reported by `altium.import.scope` (info).
- **Power ports** join by text across every sheet, except in `strict_hierarchical`, where they join within a sheet only. In `hierarchical` and `strict_hierarchical`, a power port whose local net also holds a port stays local to its sheet (`H-A-IMP-POWER-LOCAL`).
- **Net labels** join across sheets only in `global`.
- **Ports.** In `flat` and `global`, ports with one name join across every sheet. In the hierarchical scopes a port joins only the sheet entry of the same name on each sheet symbol whose file name names the port's sheet.
- **Off-sheet connectors** (a power port record flagged as a cross-sheet connector) with one text join across the sheets that share a parent, in every scope (`H-A-IMP-OFFSHEET`).
- Identifiers of different kinds never join by name. Names are compared without letter case.
- A sheet symbol's file name MUST be matched to a sheet by file name without folder and without letter case; a name with `;` lists several sheets. A sheet that is not among the inputs MUST give `altium.import.sheet-missing` (warning), and its entries stay named points.
- A sheet named by more than one sheet symbol MUST be instantiated once per symbol, each instance with its own unique-id path, and MUST give `altium.import.channels` (info); a sheet symbol whose designator is a `Repeat` statement is instantiated as "Repeated sheets as channels" says. The components of such instances are named as "Channel designators" says.
- A sheet symbol that names one of its own ancestors MUST give `altium.import.sheet-loop` (error) and no descent.
- `NetOptions` MUST be built from the project's `[Design]` options by `NetOptions.from_project(project)`; a hierarchy mode whose meaning c0042 marks unknown MUST give `altium.import.scope-unknown` (warning) and `automatic`.

#### Scenario: Hierarchical sample
- **GIVEN** the project of `tests/data/altium/hier/` of c0037 (a top sheet, two module sheets, one harness)
- **WHEN** it is imported with `NetOptions()`
- **THEN** `altium.import.scope` names `hierarchical`, and the nets, as sets of `(ref, pin)` pairs by name, equal those of the model the build wrote the project from

#### Scenario: Ports do not join sideways
- **GIVEN** two module sheets that each hold a port `EN` wired to one pin, and a top sheet whose two sheet symbols have an entry `EN` each, not wired together
- **WHEN** the netlist is built in the hierarchical scope
- **THEN** the two pins are on different nets; in the flat scope they are on one net

#### Scenario: Automatic scope without sheet entries
- **GIVEN** two sheets without sheet symbols, each with a port `CLK`
- **WHEN** the netlist is built with `scope="automatic"`
- **THEN** the scope is `flat` and the two ports join

#### Scenario: Missing sheet
- **GIVEN** a top sheet whose sheet symbol names `Power.SchDoc`, which is not among the inputs
- **WHEN** the netlist is built
- **THEN** `altium.import.sheet-missing` names `Power.SchDoc`, and the wires on the symbol's entries form nets of their own

### Requirement: Import issue codes
Every issue of the adapter SHALL carry a code of the closed table `adapter.IMPORT_ISSUE_CODES`, which maps each code to its one severity, and `docs/cli-contract.md` SHALL list the table.
- Errors: `altium.import.bad-stack`, `altium.import.sheet-loop`.
- Warnings: `altium.import.bad-length`, `altium.import.bad-geometry`, `altium.import.layer-outside-stack`, `altium.import.duplicate-net`, `altium.import.unknown-member`, `altium.import.padstack-unknown`, `altium.import.via-span`, `altium.import.no-designator`, `altium.import.sheet-missing`, `altium.import.repeated-sheet`, `altium.import.channel-naming`, `altium.import.scope-unknown`, `altium.import.duplicate-net-name`, `altium.import.duplicate-sheet-name`, `altium.import.bus-width`, `altium.import.harness-nested`, `altium.import.pcb-only-component`, `altium.import.document-skipped`, `altium.import.zone-hole-outside`.
- Infos: `altium.import.inexact`, `altium.import.multi-class`, `altium.import.zone-arc`, `altium.import.copper-shape`, `altium.import.scope`, `altium.import.option-ignored`, `altium.import.pin-map`, `altium.import.channels`, `altium.import.bus-member`, `altium.import.harness-entry`, `altium.import.extra-board`, `altium.import.linked-by-designator`, `altium.import.pcb-only-net`, `altium.import.rule-unmapped`, `altium.import.unmapped`.
- An issue's `where` MUST be a locator of "Identifiers and provenance", a reference, a `REF-PIN` or a net name; a counting issue's message MUST hold its counts.
- An error issue never stops the import: the adapter raises only for a programming error and for a project with nothing to read.
- No code of this table MUST equal a code of `fenolite.lens.altium.ALTIUM_ISSUE_CODES` or of the readers' tables.

#### Scenario: Closed table
- **WHEN** `uv run pytest tests/unit/backends/altium/adapter/test_codes.py` collects the codes that the adapter's source can give and those the tests have seen
- **THEN** both sets are within `IMPORT_ISSUE_CODES`, every code of the table has one severity, every code is a row of `docs/cli-contract.md`, and none is a code of the build or of a reader
