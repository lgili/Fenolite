## ADDED Requirements

### Requirement: View command draws check findings
`fenolite view` SHALL accept `--check FILE` (a `check` reply) or `--check run`, reply with `result.check` counting findings by severity, and refuse a file that is not a `check` reply with `FEN-3004`.

#### Scenario: Not a check reply
- **WHEN** `uv run pytest tests/unit/cli/test_view_cmd.py -k check_reply` passes an `analyze` reply to `--check`
- **THEN** the exit code is 3 and the error code is `FEN-3004`
