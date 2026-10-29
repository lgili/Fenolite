## ADDED Requirements

### Requirement: Library propose command
`fenolite library propose` SHALL be a command of the registry, read-only without `--proposal` and mutating with it, described in `docs/cli-contract.md` ("library propose") with its options (`--datasheet`, `--proposal` once or twice, `--out`, `--licence`), its result schema `fenolite.library-propose.v0` and its codes. Its example arguments MUST name authored files under `tests/data/proposals/`.

#### Scenario: Consistency suite covers propose
- **WHEN** `uv run pytest tests/consistency -q` runs
- **THEN** `library propose` runs with its example arguments, its skeleton form exits 0 and its proposal form's dry run exits 4

### Requirement: Library propose result
The result of `library propose` with proposals SHALL hold `device`, `folder`, `datasheet` (`file`, `sha256`), `proposals` (`file`, `sha256`, `proposer`), `package` (family and pins), `doubts`, `uncited` and `plan`. The envelope evidence MUST be `INFERRED` with `H-L-PROPOSAL`; the device's own label is a field.

#### Scenario: Result fields
- **WHEN** the authored proposal is proposed with `--dry-run --json`
- **THEN** the result holds every field above and `evidence.level` is `INFERRED`
