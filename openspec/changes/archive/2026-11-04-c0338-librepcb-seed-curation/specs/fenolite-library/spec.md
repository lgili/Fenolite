## ADDED Requirements
### Requirement: Curated artwork is explicit and reproducible
The review draft SHALL retain its immutable raw seed separately and record its
exact source-bound change in existing provenance notice and NOTICE. Only two
resistor graphical pin lengths SHALL change from2,000,000nm to2,032,000nm; pin
anchors/names/numbers, device mappings and physical footprint geometry SHALL
remain unchanged. No checker waiver or source-parser rounding is permitted.

#### Scenario: Reproducible four-item review candidate
- **WHEN** the external recipe runs twice on the same byte-attested raw seed
- **THEN** all candidate file hashes match, complete library check returns exit0 with zero ERROR and all four preferred100mil WARN visible,
  and native before/after partitions match the same expected three nets
- **AND** the generated preview identifies the two changed lengths explicitly
- **AND** human acceptance, integration and release gates remain pending
