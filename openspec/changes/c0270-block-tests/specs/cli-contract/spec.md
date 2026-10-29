## ADDED Requirements

### Requirement: Block test command
`fenolite blocks test [ID...] [--golden] [--only usage|golden|tests]` SHALL run, for each selected block in id order, the convention check, the usage build, the golden comparison and the test functions, and return `result.blocks` with per block `id`, `version`, `usage`, `golden` and `tests`. It MUST exit 0 when no finding is above `info` and 5 otherwise, and MUST write only with `--golden` under the protocol.

#### Scenario: One block tested
- **WHEN** `uv run pytest tests/unit/cli/test_blocks_test.py -k one` runs `fenolite blocks test Test:divider --json` on the authored library
- **THEN** the exit code is 0, `result.blocks[0].usage` is `passed`, `golden` is `equal`, every test is `passed`, and no file was written

#### Scenario: Unknown block
- **WHEN** `fenolite blocks test Test:dividr --json` runs
- **THEN** the exit code is 2 with `FEN-2001`, and the hint names `Test:divider`
