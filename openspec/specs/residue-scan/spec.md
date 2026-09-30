# residue-scan Specification

## Purpose
Mechanically detect material that must not be published (absolute paths, internal identifier shapes, known non-public files, private tokens) in the tree, in staged changes, in built artefacts and in the git history, without ever printing what it found.
## Requirements
### Requirement: Scan engine and pattern sources
`tools/residue/scan.py` SHALL scan the working tree (excluding `.git`, `.venv`, `tests/corpus/cache`, `private/`), the built wheel when present, and all staged files when invoked with `--staged`, using these pattern sources: public structural regexes from `tools/residue/patterns.regex`; public whole-file hashes from `tools/residue/blobs.sha256`; and, when configured, a private token list (`FENOLITE_RESIDUE_TOKENS` with inline tokens, or the file named by `FENOLITE_RESIDUE_TOKENS_FILE`, or `~/.fenolite-residue-tokens`) and a private whole-file hash list (the file named by `FENOLITE_RESIDUE_BLOBS_FILE`, or `~/.fenolite-residue-blobs`). Private lists live outside the tracked tree.

#### Scenario: Structural hit
- **GIVEN** a file `examples/x/notes.md` containing an absolute path of the form `/Users/<name>/…`
- **WHEN** `uv run python tools/residue/scan.py` runs
- **THEN** the exit code is 5 and the output lists `examples/x/notes.md:<offset>:abs-user-path`

#### Scenario: Blob hit
- **GIVEN** a committed file whose SHA-256 appears in `tools/residue/blobs.sha256`
- **WHEN** the scan runs
- **THEN** the exit code is 5 and the output names the file and the pattern id `known-blob`

#### Scenario: Private token hit without disclosure
- **GIVEN** `FENOLITE_RESIDUE_TOKENS` contains a token that occurs in `docs/x.md`
- **WHEN** the scan runs
- **THEN** the exit code is 5, the output contains `docs/x.md:<offset>:private-token`, and the output does not contain the token text

#### Scenario: Absent private list is not an error
- **GIVEN** no private token list is configured
- **WHEN** the scan runs on a clean tree
- **THEN** the exit code is 0 and the output states that the private gate was skipped

### Requirement: Multi-encoding and container awareness
The scan MUST match patterns against each file decoded as UTF-8, UTF-16LE and cp1252, MUST scan raw bytes of compound files (signature `D0 CF 11 E0 A1 B1 1A E1`), and MUST scan entries of zip-based artefacts (wheels, `.zip`).

#### Scenario: UTF-16 content
- **GIVEN** a token stored as UTF-16LE inside a binary fixture
- **WHEN** the scan runs with that token in the private list
- **THEN** the file is reported

#### Scenario: Wheel content
- **GIVEN** `dist/fenolite-*.whl` contains a data file with a structural hit
- **WHEN** the scan runs
- **THEN** the wheel entry is reported with its inner path

### Requirement: Failure semantics
On any hit the scan MUST exit with code 5, MUST print `path:offset:pattern-id` per hit, and MUST NOT print the matched text. On a clean tree it MUST exit 0.

#### Scenario: Output never leaks
- **GIVEN** any hit
- **WHEN** the scan output is inspected
- **THEN** no line contains the matched substring

### Requirement: No token list in the repository
The repository MUST NOT contain a list of private identifiers in any form, including hashed or salted forms.

#### Scenario: Hashed list rejected in review
- **GIVEN** a pull request adds `tools/residue/tokens.sha256`
- **WHEN** `pytest tests/residue/test_no_token_list.py` runs
- **THEN** the test fails naming the file

### Requirement: Integration points
The residue scan SHALL run as a step of the CI `unit` job, SHALL be runnable as `pytest tests/residue`, and SHALL be installable as a git pre-commit hook via `make hooks`.

#### Scenario: Hook blocks a commit
- **GIVEN** the hook is installed and a staged file contains a structural hit
- **WHEN** `git commit` runs
- **THEN** the commit is refused and the hook output names the file

### Requirement: Scope waivers are explicit
Waivers MUST be declared per file and per pattern in `tools/residue/scope.toml` with a justification, and the scan MUST print the count of active waivers.

#### Scenario: Waived numeric code
- **GIVEN** `scope.toml` waives `numeric-code` for `examples/blink_2layer/bom.csv` with a justification
- **WHEN** the scan runs
- **THEN** the file is not reported and the summary shows `waivers: 1`

