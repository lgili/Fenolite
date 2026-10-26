## ADDED Requirements

### Requirement: Assembly and test pad properties on boards and footprints
The shared footprint mapping (`_fpmap`) SHALL model a pad's `(property <token>)` child as `Pad.fab_property`, for board pads and `.kicad_mod` pads alike, through the table `_fpmap.FAB_PROPERTY_TOKENS`:

| `fab_property` | KiCad token |
|---|---|
| `bga` | `pad_prop_bga` |
| `fiducial_global` | `pad_prop_fiducial_glob` |
| `fiducial_local` | `pad_prop_fiducial_loc` |
| `test_point` | `pad_prop_testpoint` |
| `heatsink` | `pad_prop_heatsink` |
| `castellated` | `pad_prop_castellated` |
| `mechanical` | `pad_prop_mechanical` |
| `press_fit` | `pad_prop_pressfit` |

- A pad without the child MUST have `fab_property is None` and no slot for it.
- A token outside the table MUST keep the child as an `Opaque` slot, with `fab_property is None` and the info `kicad.board.kept-opaque` on a board or `kicad.lib.kept-opaque` in a footprint file. A pad with several such children MUST keep each of them as an `Opaque` slot with the same info, and `fab_property` is projected from the first one; a model value that differs from what they hold MUST give `kicad.board.projection-read-only` on a board and the read-only error of `mod.write_footprint` in a footprint file.
- The emitters MUST write the child from the model. A created pad writes it after `drill`, or after `size` when it has no drill, and before `layers` (`CANONICAL_ORDER["pad"]` and `PAD_CANONICAL`); a read pad without the child gets it only when the value is not `None`. `mod.prepare_authored_definition` MUST give an authored pad whose value is set a `Modeled` slot for it in that place, and none otherwise.
- `embed.place_footprint` MUST keep the value of the definition's pads, and `mod.write_footprint` MUST write it.
- `pad_prop_pressfit` is a token of KiCad 10 (inventory row `pad-property-pressfit`). A pad that holds `press_fit` in the model, written for target 9, MUST raise `LossyWriteError` with `droppable = False` and the issue `kicad.token.too-new`, as "Lossy writes are refused unless allowed" rules for modelled content.
- `docs/formats/kicad/board.md` MUST hold the table, the place of the child, and the facts of `H-K-PAD-FABPROP` and `H-K-PAD-FABPROP-LIB`.

#### Scenario: A fiducial pad on a board
- **GIVEN** a `20260206` board whose footprint pad holds `(property pad_prop_fiducial_glob)` between its `size` and `layers` children
- **WHEN** it is read and written for target 10
- **THEN** the pad has `fab_property == "fiducial_global"` and a `Modeled` slot for the child, and the written pad node is tree-equal to the source

#### Scenario: A created test-point pad
- **GIVEN** a created through-hole pad with a 0.8 mm drill and `fab_property == "test_point"`
- **WHEN** its footprint is written for target 9
- **THEN** the pad holds `(property pad_prop_testpoint)` after its `drill` child and before its `layers` child

#### Scenario: An unknown mark
- **GIVEN** a board pad that holds `(property pad_prop_unknown)`
- **WHEN** it is read with an `issues` list
- **THEN** `fab_property is None`, the child is an `Opaque` slot, and `issues` holds one info `kicad.board.kept-opaque`

#### Scenario: Press-fit for KiCad 9
- **GIVEN** a created board whose through-hole pad has `fab_property == "press_fit"`
- **WHEN** it is written for target 9, with and without `allow_lossy`
- **THEN** both calls raise `LossyWriteError` with `droppable == False`, and its issues name the inventory row `pad-property-pressfit`

#### Scenario: Library footprints round trip
- **GIVEN** the fetched footprint corpus
- **WHEN** `uv run pytest tests/corpus/test_footprint_rt.py` runs
- **THEN** it passes, and every pad that holds one of the eight tokens has a `Modeled` slot for it

## MODIFIED Requirements

### Requirement: IPC-D-356 parsing
`fenolite.backends.kicad.ipcd356.read_ipcd356(text)` SHALL parse the netlist that `kicad-cli pcb export ipcd356` writes into `Ipcd356(unit_nm, records)`.
- Each `317` or `327` record MUST give `code`, `net`, `ref`, `pin`, `x`, `y` (export units, Y up), `rotation` from the `R` field when present, `side`, and `covered` from the `S` field that follows the rotation: `S0` gives `none`, `S1` `top`, `S2` `bottom` and `S3` `both`, the sides whose solder mask covers the pad (observed on 9.0.9 and 10.0.6, `H-K-TESTPOINT-D356`), and `None` when the record has no `S` field.
- `ref` and `pin` MUST be the export's fixed-width fields as written, stripped of padding: the export truncates the reference to 6 characters and the pin to 4 (observed on 10.0.6, S-0019). A via record has `ref == "VIA"` and an empty `pin`.
- `UNITS CUST 0` MUST give `unit_nm == 2540`.
- Text without a `UNITS` line MUST raise `FormatError`.
- `tests/kicad/test_geometry_frame.py` MUST parse its export with this function.

#### Scenario: Through-hole record
- **GIVEN** an authored export text with the line `P  UNITS CUST 0` and one `317` record for net `GND`, reference `D1`, pin `1`, at `X+0001000Y-0002000` with `R030`
- **WHEN** `read_ipcd356` is called
- **THEN** `unit_nm == 2540` and the record has `net == "GND"`, `ref == "D1"`, `pin == "1"`, `x == 1000`, `y == -2000` and `rotation == 30`

#### Scenario: Via and truncated records
- **GIVEN** an authored export text with a `317` via record, whose reference field is `VIA` and whose pin field is blank, and a `327` record whose reference field holds the six characters `ABCDEF` of the reference `ABCDEFG1`
- **WHEN** `read_ipcd356` is called
- **THEN** the via record has `ref == "VIA"` and `pin == ""`, and the other record has `ref == "ABCDEF"`

#### Scenario: Missing units
- **WHEN** `read_ipcd356` is called on text without a `UNITS` line
- **THEN** `FormatError` is raised

#### Scenario: Mask codes
- **GIVEN** an authored export text with two `327` records ending `R000S2` and `R000S1`, a `317` record ending `R000S0`, and a `327` record ending `R000S3`
- **WHEN** `read_ipcd356` is called
- **THEN** their `covered` values are `bottom`, `top`, `none` and `both`, in that order
