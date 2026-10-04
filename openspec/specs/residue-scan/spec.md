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

### Requirement: Public format inventories are not token lists
The name check behind "No token list in the repository" (`tests/residue/test_no_token_list.py`) SHALL allow exactly one path whose name looks like a token list: `src/fenolite/backends/kicad/data/tokens.toml`, the public KiCad format inventory. Every other path matching the name check MUST still fail. The same test module SHALL check that the allowed file parses with `tomllib` and holds only the top-level keys `format` (equal to `1`), `collected_at`, `token`, `form` and `note`, and that every `token` and `form` row cites at least one id registered in `docs/evidence/sources.md`. A file at that path that fails the content check MUST fail the test.

#### Scenario: Allowed inventory passes
- **GIVEN** `src/fenolite/backends/kicad/data/tokens.toml` with `format = 1` and rows citing registered sources
- **WHEN** `uv run pytest tests/residue/test_no_token_list.py` runs
- **THEN** the test passes and the file is not reported

#### Scenario: Private list still rejected
- **GIVEN** a pull request adds `tools/residue/tokens.sha256`, or `src/fenolite/backends/kicad/data/tokens.txt`
- **WHEN** `uv run pytest tests/residue/test_no_token_list.py` runs
- **THEN** the test fails naming the file

#### Scenario: Inventory with foreign content rejected
- **GIVEN** `tokens.toml` gains a top-level `[[denylist]]` table
- **WHEN** `uv run pytest tests/residue/test_no_token_list.py` runs
- **THEN** the test fails naming the file and the key `denylist`

### Requirement: Private gate is documented
`docs/provenance.md` SHALL hold a section "Private residue gate" that states, from the code of `tools/residue/scan.py` and the `Makefile`:
- what `FENOLITE_RESIDUE_TOKENS`, `FENOLITE_RESIDUE_TOKENS_FILE` and `FENOLITE_RESIDUE_BLOBS_FILE` do, their order of precedence and the two home-folder files read when they are unset;
- that the scan's last line reports the gate as `on` or `skipped`, and that a skipped gate is not an error;
- that the `Makefile` turns the gate on when the private list files exist, so `make residue`, `make check` and `make check-fast` run it, and a bare `scan.py` call does not;
- that CI and the release workflow run with the gate off, because the lists are never published;
- that the maintainer runs the gate locally, over the tree and over the history, before a release, and records the history run in `docs/evidence/residue-history.md`.

The section MUST NOT quote a private token, a private hash or the content of any private file.

#### Scenario: Section present
- **WHEN** `uv run pytest tests/residue/test_scan.py -k gate_documented` reads `docs/provenance.md`
- **THEN** the page holds the heading "Private residue gate" and names the three variables, each of which occurs in `tools/residue/scan.py`

#### Scenario: Gate off without a list
- **GIVEN** none of the three variables is set and neither home-folder file exists
- **WHEN** `uv run python tools/residue/scan.py` runs on a clean tree
- **THEN** the exit code is 0 and the last line ends with `private gate: skipped (no private list configured)`

