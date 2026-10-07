## MODIFIED Requirements

### Requirement: PCB units and record framing
`backends.altium.pcbrecords` SHALL hold the units and the framing shared by the PCB library and the PCB document (S-0002, S-0150, S-0160, S-0162).
- `to_units(nm)` MUST return `nm · 50 / 127` (1/10 000 mil, 2.54 nm) rounded half away from zero, as an int32; a value outside the int32 range MUST raise `ValueError`. Every length, position and size written in a binary record MUST pass through it.
- `mil_text(units)` MUST return the length in mils as a decimal with at most four decimals, trailing zeros and a trailing point removed, followed by `mil` (`10000000` gives `1000mil`, `3937008` gives `393.7008mil`). Every length written in property text MUST use it.
- `string_block(text)` MUST return a 32-bit little-endian length, then one length byte and the 7-bit ASCII text; texts that `ascii.text_problem` refuses or that exceed 255 bytes MUST raise `ValueError`.
- `property_block(fields)` MUST return c0033's `binary.frame_record(fields)`.
- Angles MUST be written as IEEE-754 doubles in degrees, counter-clockwise, computed from microdegrees or from exact coordinates with `decimal` and converted to a double once with `float(Decimal)`. No `math` trigonometric function may produce a written value.
- The common prefix of a track, arc and pad geometry MUST be: layer byte, two flag bytes, net index, polygon index `0xFFFF`, component index (all uint16, `NO_INDEX = 0xFFFF` for none), then `FF FF FF FF`. The flag bytes MUST be `0x0C 0x00` (unlocked) for every item but a locked free track, arc or via of a record kind in `pcbrecords.LOCK_WRITTEN`, whose flag bytes MUST be `0x08 0x00`: bit 2 of the first byte clear, every other bit as in the unlocked form ("Locked copper records").
- `pcbrecords.EVIDENCE` MUST be `INFERRED` and name every `H-A-PCB-*` row this change registers.

#### Scenario: Units
- **WHEN** `to_units` is called with `0`, `254`, `1000000`, `-1000000` and `127`
- **THEN** it returns `0`, `100`, `393701`, `-393701` and `50`

#### Scenario: Mil text
- **WHEN** `mil_text` is called with `10000000`, `3937008` and `-5`
- **THEN** it returns `1000mil`, `393.7008mil` and `-0.0005mil`

#### Scenario: Angles do not depend on the platform
- **WHEN** `uv run pytest tests/unit/backends/altium/test_pcbrecords.py -k angle` runs the arc of start (−0.29, −1.08) mm, mid (1.27, −1.65) mm and end (2.83, −1.08) mm
- **THEN** the start and end angles equal the doubles pinned in the test, computed once with `decimal` at 40 digits, and no module of `backends/altium` imports a trigonometric function of `math`

#### Scenario: Flag bytes of a locked track
- **WHEN** `uv run pytest tests/unit/backends/altium/test_pcbrecords.py -k locked` builds the same track record with `locked=False` and with `locked=True`, `track` being in `LOCK_WRITTEN`
- **THEN** the two records differ in one byte, the first flag byte, `0C` against `08`

### Requirement: Via records
`pcbrecords.via_record(x, y, diameter, hole, *, net=NO_INDEX, locked=False)` SHALL write one through via as record type 3 with one subrecord of 321 bytes, the form Altium saves (S-0150, S-0160, S-0173, S-0172, S-0174, S-0175, S-0176; `H-A-PCB-CU-VIA`).
- The subrecord MUST start with the common prefix on layer 74 with flags `0C 00`, or `08 00` for a locked via when `via` is in `LOCK_WRITTEN` ("PCB units and record framing", "Locked copper records"), polygon and component `0xFFFF`; then x at 13, y at 17, the diameter at 21, the hole at 25, the start layer 1 at 29 and the end layer 32 at 30.
- The later fields MUST follow the rows of `pcb-copper.md`, "Via": thermal-relief air gap 10 mil at 32, 4 conductors at 36, conductor width 10 mil at 38, 20 mil at 42 and at 46, solder-mask expansion 4 mil at 54 and at 242, stack mode 0 at 74, thirty-two diameters at 75, the 16-bit 15 and the 32-bit 259 at 203, `2A` at 254, `0x7FFFFFFF` at 291 and at 295, the entry size 30 at 304, 9 at 308 and 1 at 320; every other byte 0.
- `pcbdoc.write_pcbdoc` MUST write each `model.board.Via` of `PcbDocSpec.vias` in `Vias6`, sorted by net name, position, diameter and then entity id, at its converted position, with its net's index and its `locked`. It MUST raise `ValueError` for a via whose `via_type` is not `through`, whose `layers` are not the top and the bottom copper layer, or whose drill is not below its diameter.
- Vias MUST NOT be listed in `UniqueIDPrimitiveInformation`.

#### Scenario: Via bytes
- **WHEN** `via_record(393701, 393701, 236220, 118110, net=2)` runs
- **THEN** the record is `03`, the length 321 and a subrecord whose bytes 0 to 4 are `4A 0C 00 02 00`, whose bytes 29 and 30 are `01 20`, and whose 32-bit values at 21, 25, 75 and 199 are 236220, 118110, 236220 and 236220

#### Scenario: Blind via refused
- **WHEN** a spec holds a via with `via_type="blind"` between `F.Cu` and `In1.Cu`
- **THEN** `write_pcbdoc` raises `ValueError` naming the via's id

#### Scenario: Locked via bytes
- **WHEN** `via_record(393701, 393701, 236220, 118110, net=2, locked=True)` runs with `via` in `LOCK_WRITTEN`
- **THEN** bytes 0 to 4 of the subrecord are `4A 08 00 02 00`, and every other byte equals that of the unlocked record

## ADDED Requirements

### Requirement: Locked copper records
`pcbrecords.track_record`, `arc_record` and `via_record` SHALL take `locked: bool = False`, and `pcbdoc.write_pcbdoc` SHALL pass the `locked` of each free `Track`, `Arc` and `Via` of the spec (`design-model`, "Copper locks in the board model"), so a locked item of the model is a locked primitive of the document (`H-A-PCB-CU-LOCK`).
- **Fact first.** `pcbrecords.LOCK_WRITTEN` MUST be the closed set of the record kinds, among `track`, `arc` and `via`, for which `docs/formats/altium/pcb-copper.md` holds a row saying that bit 2 of the first flag byte, clear, locks a free primitive of that kind, with a public source of `docs/evidence/sources.md` and a label. A kind MUST NOT enter the set before its row is on the page; a test MUST compare the set with the page.
- A record of a kind in `LOCK_WRITTEN` built with `locked=True` MUST differ from the unlocked record in that one bit. A record of a kind outside it MUST be the unlocked record whatever `locked` is; the build reports those items (`altium-build`, "Copper locks in an Altium build"), so a lock is never dropped without an issue.
- With `locked=False` every record MUST have the bytes it had before this change, and a document of a design without locked copper MUST keep its bytes.
- Component primitives, pads, fills, regions and texts are not changed: their flag bytes stay `0x0C 0x00`.
- The order of the records in `Tracks6`, `Arcs6` and `Vias6` MUST NOT depend on `locked`.

#### Scenario: Three locked items in a document
- **GIVEN** the routed sample's model with one track, one arc and one via set `locked=True`, and `LOCK_WRITTEN` holding the three kinds
- **WHEN** `uv run pytest tests/unit/backends/altium/test_pcbdoc_copper.py -k locked` writes the document and reads it with `backends.altium.read`
- **THEN** exactly those three primitives have `Prefix.locked` true, and the document differs from that of the unlocked model in three bytes

#### Scenario: The set follows the page
- **WHEN** `uv run pytest tests/unit/backends/altium/test_pcbrecords.py -k lock_written` compares `LOCK_WRITTEN` with the rows of the locked flag in `pcb-copper.md`
- **THEN** each kind of the set has its row with a source id and a label, and a kind without a row is not in the set

#### Scenario: A design without locks keeps its bytes
- **WHEN** `uv run pytest tests/unit/lens/test_altium_copper.py -k bytes` builds the routed sample
- **THEN** `<name>.PcbDoc` has the SHA-256 it had before this change
