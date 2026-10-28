# documentation-consistency Specification

## Purpose
Keep operational, release and contributor instructions aligned with implemented capabilities and validation requirements while preserving dated decisions as history.
## Requirements
### Requirement: Current instructions identify available capabilities

The operational placement and schematic guides SHALL describe the implemented placement strategies and KiCad ERC stage. Release-facing documentation SHALL distinguish functionality in the released package from work on another branch. Installing an optional dependency SHALL NOT be described as providing a command absent from that release.

#### Scenario: The engineer chooses a placement strategy
- **WHEN** the engineer reads the placement strategy table
- **THEN** grid, manual and constrained are listed and constrained's finite translation search and rule limitations remain explicit

#### Scenario: The engineer checks a schematic
- **WHEN** the engineer follows the KiCad schematic check guidance
- **THEN** it identifies fenolite check as running ERC when kicad-cli is available and distinguishes missing tools from verification success

### Requirement: Current status and historical decisions are distinguishable

The roadmap SHALL begin with the current release status and link its release record. Dated earlier holds MAY remain as historical decisions but SHALL NOT appear as the current milestone status. Contributor instructions SHALL put complete validation in CI and quick checks locally.

#### Scenario: A contributor reads validation instructions
- **WHEN** the contributor opens CONTRIBUTING.md
- **THEN** local instructions use make check-fast and focused proofs, with complete validation on the exact CI commit before merge or archive
