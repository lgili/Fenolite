## ADDED Requirements

### Requirement: Repeated sheets as channels
The import SHALL instantiate the child sheet of a sheet symbol once per channel. `adapter.netlist.parse_repeat(text)` SHALL return `Repeat(name, first, last)` for a sheet symbol designator of the form `Repeat(NAME, a, b)` (case-insensitive keyword, integer bounds) and `None` for any other text.
- A repeat MUST give `last - first + 1` instances, in index order. A sheet symbol without a repeat gives one instance, and two sheet symbols that name one file give one instance each.
- Each instance MUST be a `Module` whose name is the sheet symbol's name followed by `[<index>]` for a repeat, and whose extension bag holds the sheet symbol's unique id and the index.
- The components, pins and local nets of the child sheet MUST exist once per instance, with ids derived from the instance path, so that two imports of one project give equal ids.
- A repeat that does not parse, whose bounds are reversed, or that would bring the instances of the project above `MAX_CHANNELS` (256) MUST give one instance and `altium.import.repeated-sheet` (warning) naming the sheet symbol. An instantiated repeat MUST give `altium.import.channels` (info) with the sheet symbol and its count.
- A project without a repeat and without a file named twice MUST import to the canonical model it imported to before this change.

#### Scenario: Two channels
- **GIVEN** the authored project `tests/data/altium/channels/two/` whose top sheet holds a sheet symbol `Repeat(CH, 1, 2)` on a child sheet with `R1` and `C1`
- **WHEN** `load_project` and the import run
- **THEN** the circuit holds four components in the modules `CH[1]` and `CH[2]`, `altium.import.channels` names `CH` with the count 2, and no `altium.import.repeated-sheet` is reported

#### Scenario: Unparsable repeat
- **GIVEN** the same project with the designator `Repeat(CH, 2, 1)`
- **WHEN** the import runs
- **THEN** one instance is read and `altium.import.repeated-sheet` names `CH`

#### Scenario: Single-channel projects unchanged
- **WHEN** `uv run pytest tests/corpus/test_altium_channels.py -k unchanged` imports the corpus sets without a repeat
- **THEN** the canonical model of each equals the one recorded before this change

### Requirement: Channel designators
Each component of a channel SHALL get the designator its project gives it, from the first of these sources that knows it: (1) the component of the project's PCB document whose unique-id path names the channel's sheet symbol and the sheet component, whose own designator is taken (its source designator is the sheet's); (2) the entry of the project's annotation file for that unique-id path; (3) `adapter.channels.channel_designator(format, designator, names, style=…, separator=…)` with the designator format, the room naming style and the level separator of the project file.
- The keywords `KEYWORDS` and the styles `FLAT_STYLES` and `PATH_STYLES` MUST be those recorded in `docs/formats/altium/connectivity.md`, each fact labelled. A format with a keyword that needs the index of a `Repeat` statement on a plain channel, a `$` that starts no keyword, or a room name under a style outside the recorded ones MUST NOT be guessed: the components get `<designator>@<channel path>` and one `altium.import.channel-naming` (warning) gives their count. Sheets read without a project file MUST keep the designators of the sheet.
- The import result MUST report, per source, how many components took their designator from it.
- No two components of the imported circuit MAY share a reference because of a repeat; when two sources disagree for one component, source 1 wins and `altium.import.channel-naming` names both values.

#### Scenario: Designators from the board
- **GIVEN** the corpus project `altium-set:02`
- **WHEN** it is imported and `fenolite check` runs on it
- **THEN** no non-empty reference is held twice in the circuit, and every component of a repeated sheet has the designator of its board component

#### Scenario: Designators from the naming format
- **GIVEN** `tests/data/altium/channels/two/` without a PCB document and without an annotation file
- **WHEN** the import runs
- **THEN** the four references are those of `channel_designator` for the project's format, and the result counts four components for the source `format`

#### Scenario: Unknown format
- **GIVEN** the same project with a naming format that `NAMING_FORMATS` lacks
- **WHEN** the import runs
- **THEN** `altium.import.channel-naming` is reported once, and the references are `R1@CH1`, `R1@CH2`, `C12@CH1` and `C12@CH2`

### Requirement: Channel nets
The nets of a repeated sheet SHALL be resolved per channel.
- A net that the child sheet does not export MUST be one net per channel, named with the channel suffix that the naming format gives a net.
- A sheet entry `Repeat(NAME)` MUST connect channel `i` to member `i` of the parent's bus `NAME`, counted from the first channel; a parent that offers fewer members than channels MUST give `altium.import.channel-naming` (warning) naming the entry.
- Any other sheet entry MUST connect every channel to the one parent net.
- A global net label or power port MUST be one net for all channels, under the net identifier scope that "Net identifier scope" resolves.

#### Scenario: Shared and per-channel nets
- **GIVEN** `tests/data/altium/channels/two/`, whose child sheet has an entry `VCC`, an entry `Repeat(OUT)` and an internal net `MID`
- **WHEN** the import runs
- **THEN** `VCC` holds pins of both channels, `OUT1` and `OUT2` hold one channel each, and the circuit holds two nets for `MID`

#### Scenario: Corpus project agrees with its board
- **WHEN** `uv run pytest tests/corpus/test_altium_channels.py -k nets` compares the imported schematic of `altium-set:02` with its PCB document
- **THEN** no pin of a repeated sheet is on one side only

### Requirement: Pin-to-pad map of a footprint model
When the footprint model of a schematic component carries a pin map, the element of each pin in the assignment comparison and in level 2 of `equivalent` SHALL be `REF-<pad>` with the pad the map gives; without a map the pin number is the pad name.
- A pin that the map sends to no pad MUST be left out of the comparison and counted as uncovered with the reason `unmapped-pin`.

#### Scenario: Mapped pins
- **GIVEN** an authored sheet whose component `Q1` maps the pins `1, 2, 3` to the pads `G, D, S`
- **WHEN** the schematic netlist of the import is built
- **THEN** its elements for `Q1` are `Q1-G`, `Q1-D` and `Q1-S`
