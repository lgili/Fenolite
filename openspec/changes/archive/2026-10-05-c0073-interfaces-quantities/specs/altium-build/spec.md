## ADDED Requirements

### Requirement: Typed interfaces in an Altium build
An Altium build SHALL keep interfaces of the kinds `i2c`, `spi`, `uart` and `usb2` (`design-dsl`, "Typed interfaces in the DSL") in the model only, and SHALL report them with the `altium.not-lowered` info that names the design's diff pairs.
- The info for the kind `interfaces` MUST name every `diff_pair`, `i2c`, `spi`, `uart` and `usb2` interface, sorted by name; with none of them, no such info is given.
- Their nets MUST be written as plain nets; harness lowering MUST NOT take them, and every planned file outside `.fenolite/` MUST equal, byte for byte, the file of the same design without them; `.fenolite/circuit.json` holds the interfaces.

#### Scenario: I2C in an Altium build
- **GIVEN** `examples/altium_sample/design.py` and a variant that adds `I2C(sda, scl)` on two of its signal nets
- **WHEN** both are built with `--target altium --dry-run --json`
- **THEN** the variant's planned files outside `.fenolite/` equal the example's byte for byte, and its `issues` hold one `altium.not-lowered` info for `interfaces` naming the I2C interface
