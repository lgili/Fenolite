## ADDED Requirements

### Requirement: Full-stack pad records
A pad whose per-layer stack gives every copper layer a circle, an oval, a rectangle or a rounded rectangle with its corner ratio SHALL be written with stack mode 1 when the inner layers share one shape and size, and with stack mode 2 otherwise, by the write rows of `docs/formats/altium/pcb-library.md` that restate the read rows of `import.md`, "Pads and padstacks". A stack with a custom shape on any layer MUST stay a lost `pad` with its reason.

#### Scenario: Per-layer stack read back
- **GIVEN** a footprint with one pad of 1.6 mm round on top and bottom and 1.2 mm round on the inner layers of a 4-layer board
- **WHEN** `uv run pytest tests/unit/backends/altium/test_pcblib_stacks.py` writes it and reads the document back
- **THEN** the pad has stack mode 1, and its shape and size per copper layer equal the model's

### Requirement: Slotted pad holes
A through-hole pad whose padstack holds no copper layer of its own and an oval hole (`hole_shape` `slot` with a length) SHALL be written with stack mode 0 and the sixth subrecord holding hole shape 2, the slot length and the slot rotation relative to the pad (`docs/formats/altium/pcb-records.md`, "Pad"). The hole size is the slot's width.

#### Scenario: Slot read back
- **GIVEN** a footprint with one plated pad of 1.2 by 2.4 mm with an oval drill of 0.6 by 1.8 mm
- **WHEN** `uv run pytest tests/unit/backends/altium/test_pcblib_stacks.py -k slot` writes it and reads the document back
- **THEN** the pad has hole shape `slot`, a drill of 0.6 mm and a hole length of 1.8 mm

### Requirement: Connector and free pads
A pad of kind `connect` SHALL be written as a surface pad whose manual paste expansion removes its paste opening, and whose manual solder-mask expansion removes its mask opening when the pad lists no solder-mask layer. Such a pad MUST be counted `changed` under `pad`, not lost.

#### Scenario: Connector pad
- **GIVEN** a footprint with one `connect` pad on `F.Cu` alone
- **WHEN** the board is written and read back
- **THEN** the pad is a surface pad on its copper layer with no paste and no mask opening, and the report has no lost `pad`

### Requirement: Free pads for pads without a number
A pad without a number inside a footprint SHALL be written as a pad of that footprint with an empty designator when `pcb-library.md` holds a row with a public source that allows it, and otherwise as a free pad at its board position, counted `changed` under `pad` with that reason.

#### Scenario: Unnamed pad
- **GIVEN** a footprint whose pad has no number, and the corpus row of `pcb-library.md` that shows Altium-saved documents holding component pads with an empty designator
- **WHEN** the board is written and read back
- **THEN** the pad is a pad of its component with an empty designator, and the report has no lost or changed `pad` for it

### Requirement: Mechanical layers of KiCad drawings
`lower.KICAD_MECHANICAL` SHALL map `User.1` to `User.8` to Mechanical 1 to 8, `Dwgs.User` to Mechanical 9, `Cmts.User` to Mechanical 10, and `Eco1.User` and `Eco2.User` to Mechanical 11 and 12; the fabrication and courtyard layers keep Mechanical 13 to 16. A graphic or text on a mapped layer MUST be written there and the document MUST name the layer after its KiCad name.

#### Scenario: Drawing on Dwgs.User
- **GIVEN** a board with one line on `Dwgs.User` and one text on `F.Cu`
- **WHEN** it is written and read back
- **THEN** the line is on Mechanical 9, the text on the top copper layer, and the report loses neither

### Requirement: Copper texts and unmapped layers
A free text on a copper layer of the written stack MUST be written as a text record on that copper layer. A graphic or text on a layer outside `lower.KICAD_MECHANICAL`, the overlays and the copper layers (`User.9` and above, `Margin`) MUST stay a reported loss with its reason.

#### Scenario: Layer outside the map
- **GIVEN** a board with one line on `User.9`
- **WHEN** it is written
- **THEN** the line is not written and the report counts it lost under `graphic` with the reason that names the layer

### Requirement: Derived PCB library
A conversion to Altium SHALL write `<name>.PcbLib` with one footprint per distinct footprint name of the board (the part of `lib_ref` after its last `:`), built from the first instance in reference order in the footprint's frame, and every component of the document MUST link that library. An instance whose pads or graphics differ from its library footprint MUST be counted `changed` under `footprint` with the reason "differs from the library footprint"; the document keeps the instance as it is.

#### Scenario: Two instances, one edited
- **GIVEN** a board with `R1` and `R2` of footprint `R_0603`, and `R2` with one pad moved by 0.1 mm
- **WHEN** it is converted to Altium
- **THEN** the library holds one footprint `R_0603` with the pads of `R1`, both components link it, and the report counts one `changed` footprint

## MODIFIED Requirements

### Requirement: Footprint content checks
`pcblib.check_footprint(defn, extras)` SHALL return a `FootprintCheck` that refuses the footprint, or lists what is dropped. `extras` maps each pad id to a `pcblib.PadExtras(corner_ratio, refusal, dropped)` that `lens.altium.pad_extras` builds from the KiCad children the model keeps opaque.
- The footprint MUST be refused, with the reason, when: a pad has shape `trapezoid` or `custom`, or a padstack that `pcblib.stack_problem` refuses (a layer that no Altium stack holds, a copper offset, a layer shape other than a circle, an oval, a rectangle or a rounded rectangle, a slot without a length, or a surface pad whose stack differs from its own copper); a through-hole pad has no drill, a drill offset, or copper on only one side; a pad has chamfered corners; a `roundrect` pad has no corner ratio; a pad number that is not empty, or the footprint name, fails `ascii.text_problem` or exceeds 255 bytes (an empty pad number is written as an empty designator, change c0160); or a graphic lies on a copper layer.
- The check MUST list as dropped: `polygon` graphics, filled `rect` and `circle` graphics, graphics on layers outside `LAYER_MAP`, and the pad settings in `PadExtras.dropped` (solder mask and paste margins, zone connection, thermal settings, a missing paste or mask layer).
- Texts, properties and 3D model links of the footprint MUST be listed as extras, not as dropped primitives.
- A refused footprint MUST NOT be written; a dropped item MUST NOT be written.

#### Scenario: Written connector pad and stack
- **GIVEN** a footprint with one `connect` pad and one through-hole pad whose padstack gives its outer and inner layers circles
- **WHEN** it is checked
- **THEN** it is not refused (change c0160: "Full-stack pad records", "Connector and free pads")

#### Scenario: Refused pad shapes
- **GIVEN** footprints with one `trapezoid` pad, one `custom` pad, one oval-drilled through-hole pad, and one `roundrect` pad without ratio
- **WHEN** each is checked
- **THEN** each is refused with a reason that names the pad

#### Scenario: Dropped polygon
- **GIVEN** a footprint with a `polygon` on `F.SilkS` and a line on `Dwgs.User`
- **WHEN** it is checked and written
- **THEN** both are listed as dropped, and the written footprint holds only its pads and other graphics
