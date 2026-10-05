# fenolite-component-catalog Specification

## Purpose
Specify the offline, Fenolite-authored catalog of reusable generic schematic symbols and PCB footprints.

## Requirements
### Requirement: Offline Fenolite-authored standard catalog
Fenolite SHALL ship a deterministic, offline catalog of generic schematic symbol and footprint definitions under the reserved `Fenolite:` library namespace. Catalog definitions MUST be Fenolite-authored model data; they MUST NOT be copied or vendored from another CAD library. Every entry MUST have a stable lib id, kind, category, summary, evidence level and a list of public source ids for factual electrical or physical claims. The catalog MUST permit incremental additions and MUST NOT claim complete coverage of commercial parts.

#### Scenario: Common catalog entries are available offline
- **WHEN** `list_entries()` is called without a configured CAD installation or network
- **THEN** it returns the same sorted built-in entries and their source/evidence metadata

#### Scenario: Unknown catalog ID
- **WHEN** a caller requests an unknown catalog symbol or footprint id
- **THEN** the API raises `KeyError` without attempting network access

### Requirement: Discoverable catalog API and CLI
The public `fenolite.catalog` API SHALL list and retrieve symbol/footprint definitions by stable lib id, with optional case-insensitive search over id, category and summary. `fenolite catalog list` and `fenolite catalog show <lib-id>` SHALL expose the same entries through the CLI JSON envelope, including evidence and source ids, without running an external tool.

#### Scenario: Search by category
- **WHEN** the API or CLI searches for a category in the shipped catalog
- **THEN** matching entries are returned in stable lib-id order with their kind and evidence

#### Scenario: Show a definition
- **WHEN** `fenolite catalog show Fenolite:Resistor` names a known entry
- **THEN** it returns its kind, metadata, source ids and package/symbol definition summary

### Requirement: Build resolves built-in definitions
The KiCad `fenolite build` SHALL resolve catalog symbol and footprint lib ids without consulting global/project CAD library tables for those ids. It SHALL write the definitions used by the design into the generated project's local libraries. A project-authored definition whose lib id exactly matches a catalog entry MUST take precedence for that build only; other catalog entries remain available. The build MUST report the origin as `builtin` for an unmodified catalog entry and `authored` for a project override.

#### Scenario: Offline built-in build
- **GIVEN** a design that names a shipped symbol and footprint
- **WHEN** it is built with empty library tables and offline resolver configuration
- **THEN** its definitions resolve, the generated local tables point to the local output libraries, and the result labels their origin `builtin`

#### Scenario: User customizes a standard definition
- **GIVEN** a project-authored symbol or footprint with the same lib id as a catalog entry
- **WHEN** the project is built
- **THEN** the authored definition is used and labelled `authored`, with no mutation of the shipped catalog

### Requirement: Source and evidence labels
Each factual symbol pin map or physical package dimension in the catalog SHALL cite one or more public sources registered in `docs/evidence/sources.md`. A land pattern not explicitly specified by those sources MUST be labelled `INFERRED` in catalog metadata and the definition description. Writer/readback success MUST NOT upgrade an inferred dimension's evidence level.

#### Scenario: Inferred land pattern stays inferred
- **GIVEN** a catalog footprint whose source specifies body dimensions but not copper lands
- **WHEN** its definition is listed and written/read back
- **THEN** it remains labelled `INFERRED` and its description says the land dimensions are not manufacturer-recommended

#### Scenario: Provenance validation
- **WHEN** the catalog source check runs
- **THEN** it fails for an entry with an unregistered source id, no evidence label, or an `INFERRED` footprint without an inferred-land description

### Requirement: Reusable symbol body graphics
`SymbolDef` SHALL carry optional ordered symbol-local graphic primitives in integer nanometres. The DSL symbol authoring API SHALL create line, rectangle, circle and polygon primitives, and the KiCad symbol reader/writer SHALL preserve those primitives through a read/write round-trip. Symbols with declared graphics MUST use those graphics for their body and MUST NOT get an additional synthetic pin-bounds rectangle; symbols with no declared graphics retain the existing fallback.

#### Scenario: Resistor body is drawn from catalog graphics
- **GIVEN** the built-in resistor symbol with two pins and a declared rectangular body
- **WHEN** its symbol library is written and read back
- **THEN** the symbol has the same pins and ordered geometry and no extra generated body rectangle

#### Scenario: Existing symbol without graphics stays compatible
- **GIVEN** an authored symbol with pins and no graphic primitives
- **WHEN** its symbol library is written
- **THEN** the current generated pin-bounds rectangle remains present
