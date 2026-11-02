## ADDED Requirements

### Requirement: Context assets bind reviewed conversion
Context indexes and full symbol assets SHALL have deterministic relative paths and content digests. Import/build/sync plans MUST bind every source, index and asset; stale inputs MUST refuse confirmation under the existing FEN-4002 contract. Missing, unknown or unresolved context data MUST fail closed. Ordinary projects without contextual variants SHALL keep their existing bytes and receipts.

#### Scenario: A local property asset changes after review
- **WHEN** any contextual asset or index changes between planning and confirmation
- **THEN** confirmation writes nothing and requires a fresh reviewed plan

#### Scenario: An ordinary project has no contextual metadata
- **WHEN** its existing build and byte guards run
- **THEN** the output bytes and approval/receipt behavior remain unchanged

### Requirement: Context index has a closed schema
`symbol-contexts.toml` MUST use the closed `fenolite.symbol-contexts.v0` schema in the design, sorted unique sheet/native-ID rows, exact source/AST/asset/binding SHA-256 digests and canonical relative paths. The DSL SHALL explicitly require the index. Missing, unknown, duplicate, stale, symlinked or escaping data MUST refuse before staging. No model/S field or CLI envelope is added.

#### Scenario: A required context index is removed
- **WHEN** the script names the context index and that file or any required row is absent
- **THEN** build refuses before staging instead of falling back to another definition

### Requirement: Native namespace spelling remains intact
Imported symbol library namespaces with safe interior spaces MUST retain their original native IDs. Generated paths SHALL reject traversal, separators, controls, reserved names and ambiguous trailing spelling. Context assets MUST use digest filenames rather than native IDs.

#### Scenario: A metadata variant uses a spaced namespace
- **WHEN** an authored source uses a safe native namespace with interior spaces
- **THEN** import preserves its namespace and full definitions without a path escape
