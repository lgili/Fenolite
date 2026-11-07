## ADDED Requirements

### Requirement: Configurable layer order
The board or footprint viewer SHALL let the user reorder all available layers through accessible controls and Alt+Up/Down, apply or cancel the draft, and restore Default viewer order. Applied order SHALL govern both the visible layer list and layer stepping. It SHALL preserve native names, stable layer IDs, source and scene data, geometry, draw order, current layer, visibility, opacity and other selections. The preference SHALL be scoped to document identity and source hash in this browser; unavailable storage SHALL fall back to this page session. Invalid preferences SHALL not remove, duplicate or introduce layers. The feature SHALL NOT infer a universal Altium order or invent unavailable native layers.

#### Scenario: Apply and cancel an accessible order
- **GIVEN** a board with available layers, a selected current layer and some hidden layers
- **WHEN** the user opens Order layers, selects a layer and uses Move up/down or Alt+Up/Down
- **THEN** the draft changes without changing the applied list, visibility or selection; Apply updates the list and layer stepping, while Cancel or Escape discards the draft and returns focus

#### Scenario: Restore the viewer order
- **GIVEN** an applied custom order
- **WHEN** the user chooses Reset to default and Apply
- **THEN** the viewer restores its original deterministic layer ordering and clears the saved preference, preserving current layer, visibility, opacity and selections

#### Scenario: A preference belongs to its document
- **GIVEN** a custom order applied to a document with a source hash
- **WHEN** the page reloads, opens a different document/hash, or cannot access localStorage
- **THEN** reload of the same document/hash restores the saved order; another identity uses its own default; unavailable storage keeps a choice for this page session without failing

#### Scenario: An invalid saved order
- **GIVEN** stored IDs containing unknown values or duplicates, a malformed value, or a changed set of available layer IDs
- **WHEN** the viewer reads its preference
- **THEN** it preserves every available layer exactly once, ignores unknown IDs and duplicates, and appends new IDs in default order; malformed preferences use the default
