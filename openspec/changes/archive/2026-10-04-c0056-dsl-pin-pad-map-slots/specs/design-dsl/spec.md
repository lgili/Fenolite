## ADDED Requirements

### Requirement: Per-component pin-to-pad mapping
The DSL build SHALL assign each symbol pin's net to the physical footprint pad named by `Component.pin_pad_map`, using identity mapping for pins not listed. Circuit net members and no-connects SHALL remain keyed by symbol pin number. A mapping with a missing source pin, missing pad target, or duplicate physical target MUST report `build.pin-pad-map-invalid` as an error and write no output. This issue SHALL join the closed build issue set of `design-dsl`, "Build issue codes".

#### Scenario: Remap a connected symbol pin
- **GIVEN** component `U1` maps symbol pin `1` to physical pad `2` and pin `1` is connected to net `N`
- **WHEN** the build resolves its footprint pads
- **THEN** pad `2` carries net `N`, while `Net.members` keeps pin number `1`

#### Scenario: Refuse an invalid pin-to-pad map
- **GIVEN** a map names a missing source pin or target pad
- **WHEN** the component is built
- **THEN** `build.pin-pad-map-invalid` is an error and the build writes no files
