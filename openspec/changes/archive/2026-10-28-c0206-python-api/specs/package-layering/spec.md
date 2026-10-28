## ADDED Requirements

### Requirement: Public API runs the commands lazily
`fenolite.api` MAY import `cli` inside a function body only, for `fenolite.api.run`; the layering test SHALL list such edges in its `LAZY` table and SHALL fail a top-level one, naming it. `import fenolite.api` MUST NOT import any module of `fenolite.cli`.

#### Scenario: Lazy edge only
- **GIVEN** `src/fenolite/api/commands.py` importing `fenolite.cli.main` inside a function, then at the top of the module
- **WHEN** `uv run pytest tests/unit/test_import_graph.py -k "lazily or loads_no_command"` runs
- **THEN** the first passes, the second fails naming `api → cli`, and a fresh `import fenolite.api` loads no `fenolite.cli` module
