## ADDED Requirements

### Requirement: Explicit digest-bound native project input
A KiCad build MAY declare a portable native project input through design.kicad_project(path, sha256=...). The file SHALL be a checked declared input resolved within the script folder, parsed with the existing exact native JSON/version policy. Failed path/hash/format checks SHALL change nothing. No undeclared ambient project or output seed SHALL substitute for that input.

#### Scenario: Portable generated import
- **GIVEN** checked original project bytes
- **WHEN** import emits Python and that complete folder is moved and built
- **THEN** its explicit native sidecar/digest carries unmanaged project data and the plan names that input

#### Scenario: A reviewed input changes
- **WHEN** the template changes after plan review
- **THEN** confirmation refuses with existing stale-plan behavior and no output changes

### Requirement: Typed settings govern the explicit baseline
The declared template SHALL initialize unmanaged project data while typed/code-owned settings and generated root/file/cache identities SHALL win afterward. The approved rebuild precedence SHALL be documented and tested. No-request builds SHALL retain existing bytes and preservation behavior.

#### Scenario: Template conflicts with code-owned settings
- **WHEN** typed design minima/stack/frame/root data conflict with the declared native baseline
- **THEN** the final project reflects typed ownership and fresh generated identities, while unmanaged settings survive

#### Scenario: Unsupported backend
- **WHEN** an explicitly declared KiCad project template is requested for Altium
- **THEN** the build refuses before staging even with allow-lossy

### Requirement: Preservation evidence does not invent semantic coverage
A retained native project key SHALL NOT be reported as globally modeled level6 semantics merely because it survives. Scoped native electrical/render/physical proofs SHALL remain explicit, complete and source-bound.

#### Scenario: Inter-sheet display settings survive a fresh build
- **GIVEN** non-default checked show/own-page/short/prefix/suffix settings
- **WHEN** original project becomes generated Python and a fresh native project
- **THEN** all5 controls and independently measured native effective text survive without an equivalence waiver

### Requirement: Explicit imported floor ownership
The existing declaration SHALL accept optional exact-bool preserve_minimums=False. False SHALL retain the original typed-minimum planning/output behavior. Explicit True SHALL retain the five supported native hard floors from the declared digest-bound baseline in every planner and final output while actual DRU override rules remain independent. The importer SHALL emit True. No canonical model field SHALL be introduced.

#### Scenario: Source floor and actual override coexist
- **GIVEN** a declared source hard floor0.01 and an actual custom rule0.7
- **WHEN** preserve_minimums=True builds the project
- **THEN** native Pro retains0.01, actual DRU retains0.7, and native DRC observes the override
