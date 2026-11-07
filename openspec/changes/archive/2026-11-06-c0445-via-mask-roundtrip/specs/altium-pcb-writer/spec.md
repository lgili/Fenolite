## MODIFIED Requirements

### Requirement: Via records
`pcbrecords.via_record(x, y, diameter, hole, *, net=NO_INDEX, start=1, end=32, locked=False, tented_top=False, tented_bottom=False, mask=None)` SHALL write one via as record type 3 with one subrecord of 321 bytes, the form Altium saves (S-0150, S-0160, S-0173, S-0172, S-0174, S-0175, S-0176; `H-A-PCB-CU-VIA`).
- The subrecord MUST start with the common prefix on layer 74 with flags `0C 00`, or `08 00` for a locked via when `via` is in `LOCK_WRITTEN` ("PCB units and record framing", "Locked copper records"), polygon and component `0xFFFF`; then x at 13, y at 17, the diameter at 21, the hole at 25, the start layer at 29 and the end layer at 30: 1 and 32 for a through via, the ids of the two copper layers of its span for a blind or buried via (change c0085, "Blind and buried via records").
- The later fields MUST follow the rows of `pcb-copper.md`, "Via": thermal-relief air gap 10 mil at 32, 4 conductors at 36, conductor width 10 mil at 38, 20 mil at 42 and at 46, solder-mask expansion 4 mil at 54 and at 242 (`mask` in binary units when it is not `None`, change c0445), stack mode 0 at 74, thirty-two diameters at 75, the 16-bit 15 and the 32-bit 259 at 203, `2A` at 254, `0x7FFFFFFF` at 291 and at 295, the entry size 30 at 304, 9 at 308 and 1 at 320; every other byte 0.
- `pcbdoc.write_pcbdoc` MUST write each `model.board.Via` of `PcbDocSpec.vias` in `Vias6`, sorted by net name, position, diameter and then entity id, at its converted position, with its net's index and its `locked`. It MUST raise `ValueError` for a via whose `via_type` is `micro`, whose `layers` are not two different copper layers of the board, or whose drill is not below its diameter. With `PcbDocSpec.allow_full_drill` (change c0128; `False` by default, and no build sets it) a via whose drill equals its diameter MUST be written instead: the hole at 25 holds the value of the diameter at 21, and every other byte is that of any via. A drill above the diameter and a drill of 0 or less MUST be refused in both cases.
- Vias MUST NOT be listed in `UniqueIDPrimitiveInformation`.
- With `mask` not `None` (change c0445), the subrecord MUST hold `mask` at 54 and at 242 and the manual solder-mask cache state 2 at 66, as a tented side does (c0112). `pcbdoc.write_pcbdoc` MUST pass `PcbDocSpec.via_mask` (nanometres, `None` by default) converted to binary units to every via. `lower.from_design` MUST set it to `Board.mask_margin` for a write of a model (no build options) and to `None` for a build (S-2042, S-2043; the opening Altium gives is `INFERRED`).

#### Scenario: Via bytes
- **WHEN** `via_record(393701, 393701, 236220, 118110, net=2)` runs
- **THEN** the record is `03`, the length 321 and a subrecord whose bytes 0 to 4 are `4A 0C 00 02 00`, whose bytes 29 and 30 are `01 20`, and whose 32-bit values at 21, 25, 75 and 199 are 236220, 118110, 236220 and 236220

#### Scenario: Micro via refused
- **WHEN** a spec holds a via with `via_type="micro"` between `F.Cu` and `In1.Cu`
- **THEN** `write_pcbdoc` raises `ValueError` naming the via's id

#### Scenario: Blind via refused
- **WHEN** a spec holds a via with `via_type="blind"` whose two layers are both `F.Cu`, a span that is not two different copper layers of the board (a blind via with a span of two copper layers is written since change c0085, "Blind and buried via records")
- **THEN** `write_pcbdoc` raises `ValueError` naming the via's id

#### Scenario: Via with a full drill
- **GIVEN** a spec with a through via of diameter 600 000 nm and drill 600 000 nm
- **WHEN** `write_pcbdoc` runs, and again with `allow_full_drill=True`
- **THEN** the first raises `ValueError` naming the via's id, as before change c0128; the second writes one via record whose 32-bit values at 21 and 25 are both 236220, and with a drill of 600 001 nm it raises `ValueError` too

#### Scenario: Locked via bytes
- **WHEN** `via_record(393701, 393701, 236220, 118110, net=2, locked=True)` runs with `via` in `LOCK_WRITTEN`
- **THEN** bytes 0 to 4 of the subrecord are `4A 08 00 02 00`, and every other byte equals that of the unlocked record

#### Scenario: A via with its own mask expansion
- **WHEN** `via_record(0, 0, 200000, 100000, mask=-40000)` runs
- **THEN** its subrecord holds the 32-bit value -40000 at 54 and at 242 and the byte 2 at 66, while the record written without `mask` holds 40000 at 54 and 0 at 66
