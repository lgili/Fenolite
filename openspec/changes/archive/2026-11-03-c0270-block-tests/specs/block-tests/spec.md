## ADDED Requirements

### Requirement: Block test convention
Each block SHALL have its usage example at `usage/<name>.py`, its tests at `tests/test_<name>.py` and its golden file at `golden/<name>.json`, relative to the folder of the module that defines it, `<name>` being the name part of its id. A shipped `Fenolite:` block MUST have all three; `fenolite blocks show` MUST give each path, or `null` when the file is missing.

#### Scenario: Paths in the record
- **GIVEN** the authored block `Test:divider` in `tests/data/blocks/lib/divider.py` with its three files
- **WHEN** `uv run pytest tests/unit/blocks/test_runner.py -k paths` runs `fenolite blocks show Test:divider --json`
- **THEN** `tests`, `usage` and `golden` are `tests/test_divider.py`, `usage/divider.py` and `golden/divider.json`

#### Scenario: Every shipped block follows the convention
- **WHEN** `uv run pytest tests/unit/blocks/test_convention.py` runs
- **THEN** every shipped block has its usage example, a tests module with at least one `test_*` function, and a golden file

### Requirement: Usage examples build
A usage example SHALL count as built when `fenolite build` of it, with seed 0 and timestamp `2026-01-01T00:00:00Z`, exits 0 and neither the build nor the tool-free check stages report a finding above `info`. Otherwise `fenolite blocks test` MUST report `blocks.usage-failed` (error) naming the block and the first such finding.

#### Scenario: A usage example with an unwired port
- **GIVEN** a copy of the authored usage example whose `OUT` port is left unconnected
- **WHEN** `uv run pytest tests/unit/blocks/test_runner.py -k usage_failed` runs the runner on it
- **THEN** the result holds `blocks.usage-failed` naming `Test:divider` and `build.port-unused`, and the exit code is 5

### Requirement: Golden block files
A golden file SHALL be the canonical JSON of an object with `schema` `fenolite.block-golden.v0`, `block`, `version`, `usage`, `seed`, `timestamp`, and the usage build's `circuit` and `rules` objects. `fenolite blocks test` MUST compare its bytes with the file and report `blocks.golden-differs` (error) with at most twenty differing JSON paths, sorted, and the command that regenerates it.

#### Scenario: A changed value is caught
- **GIVEN** the authored block whose golden file was written, and a copy whose bottom resistor default changed
- **WHEN** `uv run pytest tests/unit/blocks/test_runner.py -k golden_differs` runs the runner
- **THEN** the result holds one `blocks.golden-differs` whose paths include the bottom resistor's value, and the golden file is unchanged

#### Scenario: Same bytes on every run
- **WHEN** the golden comparison runs twice on the unchanged authored block
- **THEN** both runs report `equal` and give the same reply bytes

### Requirement: Golden files written under the protocol
`fenolite blocks test ID --golden` SHALL write golden files only through `--dry-run` and `--confirm --plan <plan id>`, the plan listing each file with its old and new SHA-256. A block whose usage example does not build MUST be refused with `blocks.usage-failed` and nothing written.

#### Scenario: Regenerate after review
- **WHEN** `uv run pytest tests/unit/blocks/test_runner.py -k golden_write` runs `--golden --dry-run`, then `--confirm --plan` with the plan id
- **THEN** the dry run writes nothing and names the golden file, and the confirmed run writes exactly those bytes with a receipt holding its SHA-256

### Requirement: Block test functions
The runner SHALL load a block's tests module from its path and call, in name order, every module-level function whose name starts with `test_` and that has no required parameter. A raised exception MUST give `blocks.test-failed` (error) with the test name and the first 500 characters of the message; a function with required parameters MUST be skipped with `blocks.test-unsupported` (warning).

#### Scenario: Pass, fail and skip
- **GIVEN** an authored tests module with one passing function, one raising `AssertionError("ratio")` and one taking a parameter `tmp_path`
- **WHEN** `uv run pytest tests/unit/blocks/test_runner.py -k functions` runs the runner
- **THEN** the result lists them in name order as `passed`, `failed` with the message `ratio`, and `skipped`, with one `blocks.test-failed` and one `blocks.test-unsupported`

### Requirement: Block test codes
`blocks.convention-missing` (error for a shipped block, warning otherwise), `blocks.usage-failed`, `blocks.golden-differs`, `blocks.golden-missing`, `blocks.test-failed` (error) and `blocks.test-unsupported` (warning) SHALL be the block test codes, each explained by `fenolite explain` and listed in `docs/cli-contract.md`, "Block tests".

#### Scenario: Every block test code is explained
- **WHEN** `uv run pytest tests/unit/cli/test_explain_cmd.py` runs
- **THEN** each of the six codes has an entry whose `see` is the heading `blocks`

### Requirement: Shipped blocks tested in CI
The repository's fast suite SHALL run, for every shipped block, its usage build, its golden comparison and its test functions through the runner, with no `kicad-cli`, corpus, KiCad library or network. The KiCad jobs MUST build every shipped usage example for targets 9 and 10 and read the board back with the connectivity of the script.

#### Scenario: Shipped blocks in the fast suite
- **WHEN** `uv run pytest tests/unit/blocks/test_shipped_blocks.py` runs with `subprocess.run` patched to raise
- **THEN** every shipped block passes and no subprocess ran

#### Scenario: Usage boards read back
- **WHEN** `uv run pytest tests/kicad/blocks/test_usage_boards.py` runs in a KiCad job
- **THEN** each usage board of targets 9 and 10 loads in `kicad-cli` and its netlist has the nets of the script
