## ADDED Requirements

### Requirement: Explicitly empty part values
A `Part` given `value=""` SHALL keep an empty value through a KiCad build. A `Part` given no value
(`value=None`) SHALL take the Value of its symbol, as before. `Part.value_empty` SHALL say which; the DSL
SHALL pass the component ids of such parts to the build (`empty_values`) without changing the model, its
schemas or canonical JSON. An Altium build SHALL keep writing the symbol's name as the comment of a
component without a value.

#### Scenario: An empty value under a symbol with a Value
- **WHEN** `Part("F1", "Lib:Fuse", footprint="Lib:Fuse", value="")` is built and the symbol's Value is `Fuse`
- **THEN** the built footprint's Value is empty

#### Scenario: No value given
- **WHEN** the same part is built without `value=`
- **THEN** the built footprint's Value is `Fuse`

#### Scenario: Existing designs keep their digests
- **WHEN** a design has no part with `value=""`
- **THEN** its canonical JSON is byte-identical to the one before this change
