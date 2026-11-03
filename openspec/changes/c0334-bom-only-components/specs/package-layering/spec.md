## ADDED Requirements

### Requirement: Lazy source BOM preservation at the API boundary
The API MAY import exactly `fenolite.importer.bom_only` inside function bodies of
`api/_drawn.py` and `api/sides.py` to preserve source purchasing instances using
the importer's shared hierarchy and identity traversal. This grants no other
API-to-importer edge. Top-level imports, imports guarded only by ImportError,
and other importer modules MUST remain forbidden. Fresh `import fenolite.api`
MUST load no importer module. 

#### Scenario: Exact lazy boundary only
- **WHEN** the import-graph controls exercise permitted imports, top-level imports,
  guarded imports, other API modules and other importer targets
- **THEN** only the exact function-body edges pass and a fresh API import loads no importer

#### Scenario: Repeated source identity survives
- **WHEN** the API reads purchasing instances in repeated sheet modules
- **THEN** the shared complete traversal retains source identities and electrical partitions
