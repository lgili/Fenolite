# Preserve custom properties of drawn sheet references

The signed L12 source refuses the declared public VME owner during extraction at
`slow_gpio.fields.Field2`. c0326 correctly refuses to discard that field: its
`DrawnSheetRef.fields` contract carries only code-owned Sheetname/Sheetfile poses.
This change represents additional sheet properties explicitly, including their
text and supported pose/font, without changing electrical connectivity or granting
an exception to fidelity checks.

Add `DrawnSheetProperty` and an optional ordered `DrawnSheetRef.properties` tuple.
Preserve them in the closed TOML/schema, KiCad extraction/lowering, level S and
scene generation. Keep Sheetname/Sheetfile text authority, unknown-style refusals,
exact units, ordinary defaults and existing byte pins unchanged. Model 1.0 remains
held until the final combined model-0 inventory includes this addition.
