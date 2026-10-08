## ADDED Requirements

### Requirement: Bus label beside the connection point
The net label of every bus block that the schematic writer draws SHALL lie on the first run of the bus line at `BusBlock.label_point`, `LABEL_OFFSET` (100 mil) right of the block's start, and SHALL NOT lie on the start, which is the connection point of the block's port or sheet entry. `LABEL_OFFSET` MUST stay below `BUS_RUN`. This supersedes, for the label's position only, "the label lies at its start" of "Bus records".

#### Scenario: The label of a bus block
- **WHEN** `uv run pytest tests/unit/backends/altium/test_bus_records.py -k beside_the_connection_point` draws the block of `D[0..3]` from (1000, 2000) and builds the design `tree` in the binary and the ASCII form
- **THEN** the label point is (1100, 2000), and on no written sheet does a net label lie on the first point of a bus line

#### Scenario: Four-bit bus
- **WHEN** `uv run pytest tests/unit/backends/altium/test_bus_records.py -k four_bit_bus` builds the design `tree` as one sheet
- **THEN** the one net label `D[0..3]` lies on the first run of the bus line, past its start and before its corner, and the read netlist holds the nets `D0` to `D3` with their pins

#### Scenario: The repeated entry of the two-channel sample
- **WHEN** `uv run pytest tests/unit/backends/altium/adapter/test_channel_files.py -k repeat_bus_and_project_forms` reads `tests/data/altium/channels/two/two.SchDoc`
- **THEN** the bus line starts on the connection point of the sheet entry `Repeat(OUT)`, no net label lies on the connection point of either sheet entry, and the label `OUT[1..2]` lies 100 mil along the bus

### Requirement: The rest of a bus block in place
Moving the bus label SHALL move nothing else of the block: the bus line, the bus entries, the member wires and their labels MUST keep their positions relative to the block's start. The cell of the block MUST reach the end of the label's text, so what the layout places to its right moves by `LABEL_OFFSET` at most. A document without a drawn bus MUST keep its bytes, in both forms.

#### Scenario: Geometry of the block
- **WHEN** `uv run pytest tests/unit/backends/altium/test_bus_records.py -k bus_block_geometry` draws the block of `D[0..3]`
- **THEN** its line, its bus entries and its member wires are those of change c0086

#### Scenario: A build without a bus
- **WHEN** `uv run pytest tests/unit/lens/test_build_bytes_pinned.py` builds the pinned examples, none of which draws a bus
- **THEN** every pinned digest is unchanged

### Requirement: Project keys of the two-channel sample
The project file of the authored two-channel sample (`tests/_altium_channels.project_text`) SHALL hold in `[Design]`, after `Version`, `HierarchyMode` and the channel keys in the corpus order, the seven net and compile keys that all six corpus project files hold, with their majority value, in the corpus order. The project file writer of a build is not changed.

#### Scenario: Project keys of the two-channel sample
- **WHEN** `uv run pytest tests/unit/backends/altium/adapter/test_channel_files.py -k repeat_bus_and_project_forms` reads `two.PrjPcb`
- **THEN** `[Design]` holds `Version`, `HierarchyMode`, `ChannelRoomNamingStyle`, `ChannelDesignatorFormatString`, `ChannelRoomLevelSeperator`, `AllowPortNetNames`, `AllowSheetEntryNetNames`, `AppendSheetNumberToLocalNets`, `NetlistSinglePinNets`, `ReorderDocumentsOnCompile`, `NameNetsHierarchically` and `PowerPortNamesTakePriority`, in this order, with `AllowSheetEntryNetNames=1` and `ReorderDocumentsOnCompile=1`
