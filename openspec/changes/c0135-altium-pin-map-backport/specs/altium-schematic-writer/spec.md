## ADDED Requirements

### Requirement: Pin map records of a footprint model
The schematic document writer, in both forms, and the schematic library writer SHALL write the pin map of a component whose `pin_pad_map` renames a pad as `MapDefiner` records (record 47) of its footprint model, directly after the `MapDefinerList` (record 46) of that model (`H-A-SCHX-PINMAP`; `docs/formats/altium/schematic-records.md`, records 46 and 47). In a schematic document each record names record 46 as its owner (`OWNERINDEX`); in a library no record carries an owner key, and the record belongs to the component it follows.
- One record MUST be written for each pin of the component whose pad differs from what a reader assumes without a record, the pad of the pin's own designator: `DESINTF` the pin's designator, `DESIMPCOUNT` `1`, and `DESIMP0` the pad that `pin_pad_map` gives the pin. A pin outside the map, and a pin that the map leaves on the pad of its own designator, gets no record. This is the form that Altium saves (`H-A-SCHX-PINMAP-FORM`: of 295 footprint models of four public project sets, 293 hold no record, one holds a record for each of its 6 pins and one holds 1 record for 8 pins, and no record names the pin's own pad alone); the count says what Altium writes, not that Altium applies a record Fenolite writes.
- The records MUST be in the order of the pins of the symbol, whatever the order of the pairs of the map.
- A component without such a pin MUST get record 46 without a record 47, as before this requirement, so the files of a design without a renaming map have the bytes they had.
- A component without a footprint model has no record 46 and writes no map.
- The schematic library MUST write the map of a library component only when every component of the design that uses its symbol links the footprint that the library's footprint model names (record 45) and has the same pad for every pin; otherwise the library component holds no record 47. A map is a map onto one footprint: a part that links another footprint than its symbol's own gets its map on the sheet alone. The schematic document carries the map of each component in every case.
- A pad name of a map that `text_problem` refuses MUST give `altium.text-unwritable` (error, nothing written), as any written text does.
- `docs/formats/altium/connectivity.md` ("Component link") MUST state the numbering of `DESIMP<i>` and which pins of a footprint model hold a record, with the counts of the public sets, under `H-A-SCHX-PINMAP-FORM`, and what Fenolite writes under `H-A-SCHX-PINMAP`.

#### Scenario: Map written and read back
- **GIVEN** the blink with `pad_map={"1": "2", "2": "1"}` on its `D1`, which links the footprint its symbol names
- **WHEN** `uv run pytest tests/unit/lens/test_altium_pad_map.py -k hold_the_map` builds it for the Altium target in the ASCII and in the binary form and reads the written sheet and library with Fenolite's readers
- **THEN** the footprint model of `D1` on the sheet, and the library component `Mini_LED`, each hold two records 47, of the pins `1` and `2` with the pads `2` and `1`

#### Scenario: Records of one map
- **GIVEN** the blink with its `R1` on a 32-pad footprint, which is not the footprint its symbol names, and `pad_map={"1": "1", "2": "3"}`
- **WHEN** `uv run pytest tests/unit/lens/test_altium_pad_map.py -k renamed_pin` builds it
- **THEN** the sheet holds one record 47, of pin `2` with `DESIMP0` `3`, and none for pin `1`; and the library component `Mini_R`, whose footprint model names the symbol's own footprint, holds none

#### Scenario: Order of the records
- **GIVEN** the blink whose `D1` has `pad_map={"2": "1", "1": "2"}`
- **WHEN** `uv run pytest tests/unit/lens/test_altium_pad_map.py -k follow_the_pins` builds it and reads the sheet and the library
- **THEN** the records of `D1` name the pins `1` and `2` in that order in both files

#### Scenario: Users of one symbol that differ
- **GIVEN** the blink with a second LED `D2` of the same symbol and footprint without a map, and `pad_map={"1": "2", "2": "1"}` on `D1`
- **WHEN** `uv run pytest tests/unit/lens/test_altium_pad_map.py -k users_of_a_symbol_differ` builds it
- **THEN** the library component `Mini_LED` holds no record 47, and the sheet holds the two records of `D1`

#### Scenario: No map, same bytes
- **WHEN** `uv run pytest tests/unit/lens/test_altium_golden.py tests/unit/lens/test_altium_binary_golden.py tests/unit/lens/test_altium_schlib_golden.py tests/unit/lens/test_altium_hier_golden.py tests/unit/lens/test_altium_no_connect_golden.py tests/unit/lens/test_altium_pad_map.py -k "golden or no_record"` runs after this change
- **THEN** every golden file under `tests/data/altium` is compared unchanged, and the blink without a `pad_map` holds no record 47 in either form

#### Scenario: A design without a board
- **GIVEN** the blink without its board and with `pad_map={"1": "2", "2": "1"}` on its `D1`
- **WHEN** `uv run pytest tests/unit/lens/test_altium_pad_map.py -k without_a_board` builds it in both forms
- **THEN** no PCB document is written, and the sheet and the library hold the two records

#### Scenario: Pad name that no record holds
- **GIVEN** the blink whose `D1` has `pad_map={"1": "A|B"}`
- **WHEN** `uv run pytest tests/unit/lens/test_altium_issues.py -k "pad-name or closed_set"` builds it for the Altium target
- **THEN** the build reports `altium.text-unwritable` as an error and writes nothing

#### Scenario: The form the public sets hold
- **WHEN** `FENOLITE_REQUIRE=corpus uv run pytest tests/corpus/test_altium_map_records.py` counts the map records of the footprint models of `altium-set:02` to `altium-set:05`
- **THEN** 295 models hold 7 records: 293 hold none, one holds 6 for its 6 pins and one holds 1 for its 8 pins; no record names the pin's own pad alone, and every record numbers its pads from 0 without a gap
