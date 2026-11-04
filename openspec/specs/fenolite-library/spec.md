# fenolite-library Specification

## Purpose
TBD - created by archiving change c0281-import-copy-fidelity. Update Purpose after archive.
## Requirements
### Requirement: Skipped levels in the proof gate
The proof gate SHALL accept a level `skipped` only when `fidelity.proof.skipped` gives its reason and the reason is not `build-failed`; the derived result is unchanged by a skipped level and MUST list the skipped levels with their reasons. Until c0278's level S runs on drawn imports, `S` skipped with `drawn-unavailable` passes.

#### Scenario: Level S skipped with a reason
- **GIVEN** a fixture proof whose levels are `equal` and whose `S` is `skipped` with `fidelity.proof.skipped.S` `drawn-unavailable`
- **WHEN** `uv run pytest tests/unit/library/test_proof_gate.py -k skipped` runs
- **THEN** the gate result is `pass` and lists `S: drawn-unavailable`; without the reason, or with `build-failed`, it is `fail`

### Requirement: Replayable conversion steps
A step of `conversion.steps` SHALL NOT hold `--plan`: a plan id hashes its working folder and cannot replay elsewhere. A writing step MUST be recorded with `--confirm` alone. `library audit` MUST give `library.provenance-invalid` for a step with `--plan`; `replay` runs each step as recorded.

#### Scenario: Step with a plan id
- **GIVEN** a fixture board item whose second step ends with `--confirm --plan 0123456789abcdef`
- **WHEN** `uv run pytest tests/unit/library/test_audit.py -k plan_step` runs
- **THEN** the audit reports `library.provenance-invalid` naming the step; with `--confirm` alone it passes, and its replay in a fresh folder gives the recorded `outputs_tree`

### Requirement: Preserve approved licence registry entries across repositories
The shipped registry SHALL retain all previously approved text digests and
match the library registry after incorporating documented maintainer approvals.

#### Scenario: Synchronize the reviewed registry union
- **WHEN** both old registries and new text approvals are reconciled
- **THEN** every old approved digest remains allowed
- **AND** the shipped registry equals the library registry without relaxing any other licence rule

### Requirement: Conservative LibrePCB legacy metadata and pads
The bounded 0.1 seed SHALL select a unique unlocalized name alongside well-formed unique locale alternatives. It SHALL accept a scalar drill only when zero and unaccompanied by a hole. An absent package_pad MAY use the pad UUID only when declared by the package. Ambiguous names, unknown references and nonzero or malformed legacy drills SHALL remain explicit refusals.

#### Scenario: Localized metadata preserves the default
- **GIVEN** an authored element with one default name and distinct valid localized names
- **WHEN** it is read
- **THEN** its default name is kept and no translated text replaces it

#### Scenario: Ambiguous defaults refuse
- **WHEN** two unlocalized names or duplicate locale identities are present
- **THEN** the element is explicitly refused

#### Scenario: Legacy surface pad binds safely
- **GIVEN** a zero scalar drill and pad UUID declared in its package
- **WHEN** the footprint is seeded
- **THEN** its exact surface pad geometry and package mapping are retained

#### Scenario: Drill information cannot disappear
- **WHEN** a scalar drill is nonzero, malformed or coexists with a hole
- **THEN** the footprint is refused without a fabricated surface pad

#### Scenario: Declared reference prefix remains visible
- **GIVEN** an authored component declaring a valid prefix
- **WHEN** symbol and device records are seeded
- **THEN** both keep that prefix; a missing field alone uses U and an invalid field is refused

### Requirement: Numeric internal function normalization is reversible
The seed converter SHALL normalize an ASCII numeric internal function name to
Pin_<original>, without changing the symbol's visible pin name, pin number,
UUID relationship or electrical mapping. It SHALL refuse identifier collisions
and other invalid names. It SHALL emit library.seed-function-normalized and
record the ordered UUID/original/normalized map in the existing dated provenance
modification_notice and NOTICE. Geometry and evidence SHALL remain unchanged.

#### Scenario: Numeric resistor functions
- **WHEN** authored signals named 1 and 2 map to two symbol pins and package pads
- **THEN** device functions are Pin_1 and Pin_2, symbol names/numbers remain 1/2,
  and replay preserves the same partition and source-bound normalization map

#### Scenario: Legal identifier collision
- **WHEN** signals 1 and Pin_1 would share a normalized identifier
- **THEN** the device is refused explicitly and no device is planned

### Requirement: Signed cardinal pin angles retain exact orientation
The seed converter SHALL canonicalize only exact cardinal pin rotations modulo
360 degrees, preserve a source-bound map in warning and existing provenance
notice, and refuse noncardinal input without rounding.

#### Scenario: Signed cardinal and near-cardinal
- **WHEN** a source pin has rotation -90deg
- **THEN** it emits270deg with the same native orientation and partition
- **WHEN** it has45deg or -90.0001deg
- **THEN** its component and dependent devices are explicitly refused

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

