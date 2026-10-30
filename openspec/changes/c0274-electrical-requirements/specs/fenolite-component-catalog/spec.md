## ADDED Requirements

### Requirement: Absolute and operating limits of a device
In a device record, a pin's `voltage` and `current`, each key of `[ratings]` and each `[[limits]]` `voltage` SHALL be a table of `abs_max` and/or `operating`, each a `{ min, max }` table or a string read as the maximum. The single `{ min, max }` form of c0248 MUST raise `FormatError` (`FEN-3004`) naming the file and the key, with a hint to say `abs_max` or `operating`. An `operating` range outside its `abs_max` range MUST raise `FEN-3004`.

#### Scenario: Both kinds on one pin
- **GIVEN** `VIN = { pins = ["5"], voltage = { operating = { min = "2.7V", max = "6V" }, abs_max = "6.5V" } }`
- **WHEN** `uv run pytest tests/unit/catalog/test_devices.py -k limits` parses the record
- **THEN** `VIN` holds the rating (`voltage`, `abs_max`, max 6 500 000 µV) and the rating (`voltage`, `operating`, 2 700 000 to 6 000 000 µV)

#### Scenario: The ambiguous form is refused
- **WHEN** records with `VIN = { pins = ["5"], voltage = { min = "2.7V", max = "6V" } }` and with `voltage = { operating = "7V", abs_max = "6.5V" }` are parsed
- **THEN** each raises `FormatError` with code `FEN-3004` naming `VIN`, the first with the hint naming `abs_max` and `operating`

### Requirement: Limits between two pins
A device record SHALL accept `[[limits]]` tables, each with `between` (two distinct functions of the device) and `voltage` (as "Absolute and operating limits of a device"), meaning the voltage of the first function minus that of the second. An unknown function, a repeated pair or another key MUST raise `FEN-3004`. The canonical text MUST order the rows by `between`.

#### Scenario: Bootstrap to switch node
- **GIVEN** `[[limits]]` with `between = ["BST", "SW"]` and `voltage = { abs_max = "6V" }` in a record whose functions include `BST` and `SW`
- **WHEN** the record is parsed and written with `device_text`
- **THEN** `DeviceDef.limits` holds one `PinPairLimit` for `("BST", "SW")` with `abs_max` 6 000 000 µV, the text round-trips, and `between = ["BST", "XX"]` raises `FEN-3004` naming `XX`

### Requirement: Logic thresholds of device pins
A pin of a device record MAY state `input_high_min`, `input_low_max`, `output_high_min`, `output_low_max` (voltages from `ground`) and `output_current_max` (a current), each one quantity text from the datasheet. A c0252 `logic` or bus port of the device SHALL take a threshold its own table omits from its member pins, the strictest of them (highest `input_high_min`, lowest `input_low_max`, lowest `output_high_min`, highest `output_low_max`, lowest `output_current_max`).

#### Scenario: A port takes its pins' thresholds
- **GIVEN** a record whose pins `PB6` and `PB7` state `input_high_min` 1.3 V and 1.4 V and whose `i2c1` port (`sda` on `PB7`, `scl` on `PB6`) states no `input_high_min`
- **WHEN** `uv run pytest tests/unit/catalog/test_device_ports.py -k thresholds` loads it and builds a part
- **THEN** the model `Port` `i2c1` has the param `input_high_min` of 1.4 V, and with `input_high_min = "1.2V"` in the port's table it has 1.2 V

### Requirement: Device class key
A device record MAY hold `class`, one name of the roles' class vocabulary (`net-roles`, "Part classes"). Another name MUST raise `FEN-3004` listing the vocabulary. The key is evidence for `fenolite.roles.classify`, never a second classifier.

#### Scenario: A ferrite says what it is
- **GIVEN** a record with `ref_prefix = "L"` and `class = "ferrite"`
- **WHEN** a part placed from it is classified by `roles.classify`
- **THEN** its class is `ferrite` with confidence `high` and source `device`, and `class = "bead"` raises `FEN-3004`

### Requirement: Device temperatures in kelvin
Device temperature limits SHALL be stored in integer millikelvin (unit `mK`), read from texts in `degC` or `K` by `fenolite.core.quantities`. A text that is not a whole number of millikelvin MUST raise `FEN-3004`.

#### Scenario: Celsius and kelvin agree
- **WHEN** records with `temperature = { operating = { min = "-40degC", max = "125degC" } }` and `temperature = { operating = { min = "233.15K", max = "398.15K" } }` are parsed
- **THEN** both give the operating range 233 150 to 398 150 mK, and `"-40.0001degC"` raises `FEN-3004`
