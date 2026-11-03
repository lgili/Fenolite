## ADDED Requirements

### Requirement: Block test command
`fenolite blocks test [ID...] [--golden] [--only usage|golden|tests]` SHALL run, for each selected block in id order, the convention check, the usage build, the golden comparison and the test functions, and return `result.blocks` with per block `id`, `version`, `usage`, `golden` and `tests`. It MUST exit 0 when no finding is above `info` and 5 otherwise, and MUST write only with `--golden` under the protocol.

#### Scenario: One block tested
- **WHEN** `uv run pytest tests/unit/cli/test_blocks_test.py -k one` runs `fenolite blocks test Test:divider --json` on the authored library
- **THEN** the exit code is 0, `result.blocks[0].usage` is `passed`, `golden` is `equal`, every test is `passed`, and no file was written

#### Scenario: Unknown block
- **WHEN** `fenolite blocks test Test:dividr --json` runs
- **THEN** the exit code is 2 with `FEN-2001`, and the hint names `Test:divider`

### Requirement: Project block convention discovery
Without `--from`, `blocks test` SHALL also discover local Python modules with a matching `usage/<module>.py` or `tests/test_<module>.py`. It MUST apply explicit id and category filters to the combined catalog.

#### Scenario: Project example from its folder
- **WHEN** `uv run fenolite blocks test --json` runs in `examples/blocks/`
- **THEN** `Example:divider` passes its usage, golden comparison and test functions

## MODIFIED Requirements

### Requirement: Exit-code vocabulary
Commands MUST use only these exit codes: `0` success; `1` internal failure; `2` usage error; `3` unreadable or future input; `4` confirmation required; `5` verification findings of severity error, or incomplete `blocks test` warnings; `6` external tool missing or incompatible; `7` refused lossy operation.

#### Scenario: Findings map to 5
- **GIVEN** `_echo --issue error` produces an error finding
- **WHEN** it runs with `--json`
- **THEN** the exit code is 5 and `ok` is false

#### Scenario: Warnings do not fail
- **GIVEN** `_echo --issue warning` produces only warnings
- **WHEN** it runs with `--json`
- **THEN** the exit code is 0 and `ok` is true

#### Scenario: Incomplete block tests fail
- **WHEN** `uv run pytest tests/unit/cli/test_blocks_test.py -k warning -q` runs a test needing a fixture
- **THEN** `blocks test` exits 5 with `blocks.test-unsupported` at severity warning
