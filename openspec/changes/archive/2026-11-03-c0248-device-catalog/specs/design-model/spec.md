## ADDED Requirements

### Requirement: Device definitions in the library layer
`fenolite.model.library` SHALL provide the frozen value objects `DeviceDef`, `DevicePin`, `Rating` and `DeviceProvenance`, and `Library` SHALL gain `devices`, sorted by id. Devices MUST NOT be part of `Design` or of the `.fenolite/` layer files ("Library definitions"). A built component names its device only through the reserved properties `fenolite.device` and `fenolite.device.sha256`. The schemas MUST be regenerated with `tools/gen_schemas.py`.

#### Scenario: Device round trip
- **GIVEN** the `DeviceDef` of `Example:BUCK_6V_2A`
- **WHEN** it is dumped and loaded with `canonical.dumps` and `canonical.loads`
- **THEN** the loaded record equals the original, and its pins keep code-point order

#### Scenario: Devices stay out of the layer files
- **WHEN** `examples/devices/design.py` is built with `--confirm`
- **THEN** no file under `.fenolite/` holds a `DeviceDef`, and the component `U1` in `.fenolite/circuit.json` holds the property `fenolite.device`

### Requirement: Device definition fields
`DeviceDef` SHALL hold `id`, `summary`, `symbol`, `footprint`, `manufacturer`, `mpn`, `datasheet`, `ref_prefix`, `value`, `evidence`, `sources`, `ground`, `unused_pads`, `properties`, `pins` (ordered by function code point), `ratings` (ordered by key) and `provenance`. Every field but `id` has a default. `DevicePin` SHALL hold `function`, `pin_pads` (ordered pairs in the form of `Component.pin_pad_map`), `voltage`, `current` and `must_connect`.

#### Scenario: Pins in code-point order
- **GIVEN** a record whose pins are written in the order `VIN`, `BST`, `GND`
- **WHEN** it is parsed
- **THEN** `DeviceDef.pins` holds `BST`, `GND`, `VIN` in that order

### Requirement: Integer ratings in the model
`Rating` SHALL hold `key`, `unit` (`uV`, `uA`, `uW` or `mdegC`), `min` and `max`, each an `int` or `None`. No field of a device definition MUST hold a float.

#### Scenario: No float in a device
- **WHEN** the canonical JSON of every shipped and test device is scanned
- **THEN** it holds no number with a fraction or an exponent
