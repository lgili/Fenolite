## MODIFIED Requirements

### Requirement: Build resolves built-in definitions
The KiCad `fenolite build` SHALL resolve catalog symbol and footprint lib ids without consulting global/project CAD library tables for those ids. It SHALL write the definitions used by the design into the generated project's local libraries. A project-authored definition whose lib id exactly matches a catalog entry MUST take precedence for that build only; other catalog entries remain available. The same SHALL hold for the lib ids of a device pack (c0266), below project definitions and above the catalog. The build MUST report the origin as `builtin` for an unmodified catalog entry, `pack` for a pack definition and `authored` for a project override.

#### Scenario: Offline built-in build
- **GIVEN** a design that names a shipped symbol and footprint
- **WHEN** it is built with empty library tables and offline resolver configuration
- **THEN** its definitions resolve, the generated local tables point to the local output libraries, and the result labels their origin `builtin`

#### Scenario: User customizes a standard definition
- **GIVEN** a project-authored symbol or footprint with the same lib id as a catalog entry
- **WHEN** the project is built
- **THEN** the authored definition is used and labelled `authored`, with no mutation of the shipped catalog

#### Scenario: Pack definition resolved offline
- **GIVEN** a design that names a footprint of the cached demo pack, with empty library tables
- **WHEN** it is built
- **THEN** the footprint is written into the local output library and the result labels its origin `pack`, with the pack name and version
