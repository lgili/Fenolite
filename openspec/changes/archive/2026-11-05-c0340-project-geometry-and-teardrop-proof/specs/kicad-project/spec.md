## ADDED Requirements

### Requirement: Proved effective project curve error
KiCad project extraction/writing SHALL preserve explicit supported curve approximation settings. Effective default normalization SHALL require real native missing/default controls on the supported versions. Unsupported target lowering SHALL retain the existing explicit loss policy.

#### Scenario: Nondefault source approximation
- **WHEN** a source project configures0.01mm curve approximation
- **THEN** import and a fresh standalone build retain10000nm, and level6 detects any changed setting
