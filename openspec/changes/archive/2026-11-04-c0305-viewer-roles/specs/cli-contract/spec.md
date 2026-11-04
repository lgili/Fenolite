## ADDED Requirements

### Requirement: View command shows roles
`fenolite view --roles run` SHALL run `fenolite roles BOARD --check` read-only for each board shown and add its role data to the scene; `--roles FILE` SHALL read a saved reply. `result.roles` MUST count roles by state and findings by severity, and the reply's evidence MUST be the lower of the scene's and the roles'. A file that is not a `roles` reply MUST be `FEN-3004`.

#### Scenario: Roles of a built reference board
- **WHEN** `uv run pytest tests/unit/cli/test_view_cmd.py -k roles` runs `fenolite view <bad buck> --roles run --export page.html --confirm --json`, then with a `check` reply as `--roles`
- **THEN** the first exits 0 with `result.roles` counts equal to the reply's and evidence `INFERRED`, and the second exits 3 with `FEN-3004`
