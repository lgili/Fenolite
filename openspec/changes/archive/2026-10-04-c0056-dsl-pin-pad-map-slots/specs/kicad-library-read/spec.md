## MODIFIED Requirements

### Requirement: Unmodelled footprint content is kept as slots
The reader MUST record the slot list of the footprint in `ext["kicad"]`, and the slot list of every pad and graphic in its own `ext["kicad"]`, using the encoding of `kicad-slots`.
- A child the model represents completely MUST be a `Modeled` slot.
- A child the model represents only partly MUST be an `Opaque` slot, with the representable part projected into the model field. This covers `tags`, a property, a model, every `stroke`, a padstack and a drill with an offset.
- An oval drill with unequal X and Y sizes MUST project its narrower dimension to `Pad.drill`, its longer dimension to `Padstack.hole_length`, and its axis to `Padstack.hole_rotation`; the drill node MUST be `Modeled`. A round drill MUST remain `Pad.drill` with no slot geometry. Offset and unusual drill forms stay opaque.
- A graphic whose geometry or fill cannot be represented MUST NOT appear in `graphics`. It MUST be an `Opaque` slot of the footprint. This covers an `arc` inside `pts`, a hatch or unknown fill, and an `fp_rect` with a corner radius.
- Every opaque slot that loses modelled meaning MUST add the info `kicad.lib.kept-opaque`. This covers offset drills, a padstack, a stroke type other than `solid` or `default`, and every unrepresentable graphic.

An opaque fragment MUST carry as minimum version the greatest minimum that the `kicad-token-inventory` gives for the token paths inside it, and the file version when the inventory has no row for the fragment's own head.

#### Scenario: Oval drill is modeled as a slot
- **GIVEN** a pad with `(drill oval 1.2 2.0)`
- **WHEN** it is read
- **THEN** `pad.drill == 1_200_000`, its padstack has `hole_shape == "slot"`, `hole_length == 2_000_000`, and `hole_rotation == 90_000_000`, the drill child is `Modeled`, and no kept-opaque issue is reported for it
