## ADDED Requirements

### Requirement: Interface ports of a device
A c0248 device record SHALL define its reserved key `interfaces` as `[[interfaces]]` tables. Each holds `name`, `kind`, `direction`, `members` (member name to a list of the device's functions), the parameters allowed for its kind and direction in c0248's `{ min, max }` spelling, `reference` (another `power` interface of the device) and `evidence`.

#### Scenario: Valid ports load
- **GIVEN** an illustrative device record authored for Fenolite with the ports `vdd` (`power`, `in`) and `i2c1` (`i2c`, `inout`, `reference = "vdd"`)
- **WHEN** `uv run pytest tests/unit/catalog/test_device_ports.py -k valid` loads it
- **THEN** both interfaces load with their members, parameters and evidence, and the record no longer gives `FEN-3002`

### Requirement: Refused device interfaces
The device loader SHALL give `FEN-3004`, naming the file, the interface and the rule, for an interface whose kind or member is unknown, that names a function the device lacks or a function in two members, whose `reference` is not another `power` interface of the device, that sets a parameter its kind and direction do not allow, or whose name equals a function of the device or an attribute of `Part`.

#### Scenario: Bad ports refused
- **WHEN** the loader reads, in turn, an interface naming a function the device lacks, an interface named like one of the device's functions, a `reference` to a non-`power` interface, and a `current` on a `logic` interface
- **THEN** each gives `FEN-3004` naming the file, the interface and the rule
