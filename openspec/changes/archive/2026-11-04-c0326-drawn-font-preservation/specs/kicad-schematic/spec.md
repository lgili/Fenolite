## ADDED Requirements

### Requirement: Drawn native font preservation
KiCad extraction and writing SHALL preserve target-probed effective fonts and justification on typed drawn text. Native `(size HEIGHT WIDTH)` MUST map to `Size(w=WIDTH,h=HEIGHT)`. Canonical false/zero presence MUST NOT imply invented native tokens. Unknown effects MUST refuse; existing native text slots MUST remain preserved.

#### Scenario: Small field survives
- **GIVEN** an authored visible field with unchanged text and size 0.25 mm
- **WHEN** it is extracted, lowered, written and read back
- **THEN** its font remains 0.25 mm and the strict authored full proof is equal at all nine levels

#### Scenario: Unsupported source effect
- **WHEN** extraction encounters an unsupported effect on a typed drawn item
- **THEN** it reports its source locator and strict conversion stages no output

#### Scenario: Native effective style
- **GIVEN** authored omitted, false/true style and zero/omitted thickness controls
- **WHEN** the actual target loads and exports the schematic
- **THEN** writing and level-S readback follow the measured effective style or refuse unsupported forms

#### Scenario: Missing native justification
- **WHEN** missing, empty and explicit native label/pin justification controls are extracted
- **THEN** their measured native anchor is preserved rather than automatically selecting the legacy role anchor

### Requirement: Legacy drawn pose bag compatibility
The private drawn adapter SHALL retain every six-part legacy field payload byte-for-byte and append separately versioned font data only for explicit fonts. It MUST read old bags and reject malformed, duplicate, unknown or orphan style records. Default generated names and bytes MUST remain unchanged.

#### Scenario: No explicit font
- **WHEN** legacy field poses with absent fonts are lowered
- **THEN** the complete private bag equals its old byte representation

#### Scenario: Orphan font record
- **WHEN** a versioned font record names no field pose
- **THEN** decoding refuses rather than silently dropping it
