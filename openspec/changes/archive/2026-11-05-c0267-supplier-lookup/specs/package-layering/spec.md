## ADDED Requirements

### Requirement: Supplier package boundary
`suppliers` SHALL import only its own package, `core`, `pick`, `catalog` and `model`, with third-party keyring imported lazily. No other source package SHALL import `suppliers` directly; callers MUST use the `fenolite.suppliers` entry points. Static discovery and code metadata MUST stay outside the provider runtime. All existing package import edges MUST remain unchanged.

#### Scenario: Suppliers stay behind the entry points
- **GIVEN** a supplier imports pick and catalog, and CLI discovers it through metadata
- **WHEN** the import-graph proof runs
- **THEN** it passes; a direct CLI, DSL or pick import of suppliers fails, as does a supplier import of DSL
