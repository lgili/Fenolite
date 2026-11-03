## ADDED Requirements

### Requirement: Effective authored stroke styles
Schematic scenes SHALL implement preserved explicit thickness, bold and italic in Fenolite’s authored stroke font and style-sensitive glyph-box masks. Default scene bytes and comparison thresholds MUST remain unchanged. Glyph-box equality MUST NOT be described as native glyph-raster equality.

#### Scenario: Styled text differs
- **WHEN** one supported effective font style changes on visible authored text
- **THEN** the scene and comparison mask reflect that change and the comparison locates it

#### Scenario: Unsupported face
- **WHEN** a visible named face, mirrored text or unrepresentable dimension is requested
- **THEN** rendering refuses with the source locator rather than substituting defaults

#### Scenario: Defaults retained
- **WHEN** font effects are omitted or effective false/zero
- **THEN** existing scene bytes and comparison behavior remain unchanged

### Requirement: Opaque free-text colour preservation
The view SHALL display validated effective RGB from opaque free-text fonts without changing the original node or extending typed DrawnFont. It SHALL refuse malformed, duplicate and out-of-range colour channels. Level8 BW geometry MUST NOT imply RGB equality.

#### Scenario: Effective free-text red
- **WHEN** an opaque free-text font requests validated red
- **THEN** the view displays red and strict replay preserves its original node

#### Scenario: Unsupported typed colour
- **WHEN** a typed drawn field or label requests font colour
- **THEN** existing closed-font validation refuses it with a locator

### Requirement: Opaque nonvisual hyperlink metadata
The view adapter MAY omit measured nonvisual href metadata from its local clone only when exactly one href contains exactly one string. It MUST preserve the complete original opaque node, refuse malformed or repeated href, keep typed effects closed, and open no URL.

#### Scenario: Original link metadata preserved
- **WHEN** opaque free text has one valid href
- **THEN** the glyph scene remains unchanged while strict replay retains the complete source node
