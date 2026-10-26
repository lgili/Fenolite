# altium-schematic-layout Specification

## Purpose
Preserve schematic presentation edits made in Altium Designer across Fenolite builds, while refusing
electrical changes or source conflicts that cannot be safely replayed.

## Requirements
### Requirement: Native layout capture
The system SHALL support `fenolite sync DESIGN.py --out DIR --to-source --target altium` and SHALL capture edited schematic bytes beside the script only when the complete set of baseline sheets has unchanged component identities, symbol assignments, parameters and electrical connectivity.

#### Scenario: Presentation edits
- **WHEN** generated sheets are moved, rotated, annotated or styled without changing the circuit
- **THEN** sync stores their exact bytes, with their generated baseline hashes

#### Scenario: Electrical change or unverifiable input
- **WHEN** a net, component identity or symbol changes, a baseline is missing, or a reader cannot verify the project
- **THEN** sync refuses capture and writes no file

### Requirement: Layout replay and conflicts
The system SHALL replay saved native sheets byte for byte when their fresh generated baseline matches, and SHALL refuse all writes when any saved sheet changes or disappears from the generated project.

#### Scenario: Rebuild after sync
- **WHEN** the source generates the same baseline as the saved snapshot
- **THEN** build outputs the saved native sheet bytes and retains the fresh baseline independently

#### Scenario: Changed source sheet
- **WHEN** the source changes a saved sheet, including adding a component
- **THEN** build reports a layout conflict without replacing existing files

#### Scenario: New unsaved sheet
- **WHEN** a generated sheet has no saved layout and the saved sheets remain unchanged
- **THEN** build generates the new sheet normally

### Requirement: Reviewed mutations
The system SHALL use the existing dry-run, confirm, plan and receipt protocol for captures and replayed builds, binding their baseline and layout inputs to the reviewed plan.

#### Scenario: Edited file changes after review
- **WHEN** an edited sheet or layout snapshot changes after a dry-run
- **THEN** confirmation of that plan is refused as stale
