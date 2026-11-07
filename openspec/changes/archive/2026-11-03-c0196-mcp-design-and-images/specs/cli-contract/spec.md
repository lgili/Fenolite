## ADDED Requirements

### Requirement: Edit command
`fenolite edit PATH (--content-file FILE | --edits-file FILE)` SHALL write a text file of a design through the write protocol.
- PATH MUST be a `*.py`, a `*.toml`, an `fp-lib-table` or a `sym-lib-table` of UTF-8 text, at most 1 MB.
- `--content-file` gives the whole text; `--edits-file` a JSON list of `{"old", "new"}`, each `old` found exactly once, else `FEN-3004`.
- The plan's `result` MUST hold `path`, `created`, `lines_added`, `lines_removed` and a unified `diff`.

#### Scenario: An exact edit planned and written
- **WHEN** `uv run pytest tests/unit/cli/test_edit_cmd.py -k exact` edits a copied starter script with one pair, first with `--dry-run`, then with `--confirm --plan`
- **THEN** the dry run writes nothing and its diff shows the one changed line, and the confirmation writes the new text

### Requirement: Edit checks without running
The result of `fenolite edit` SHALL parse before it is planned: a `.py` file with `ast.parse`, a `.toml` file with `tomllib`; a failure SHALL be `FEN-3004` with the line, and the design script SHALL NOT be imported or run.

#### Scenario: An edit that breaks the script is refused
- **WHEN** the test applies a pair that leaves an unclosed parenthesis
- **THEN** the exit code is 3, the error is `FEN-3004` with the line, and no plan is staged

#### Scenario: An old text found twice
- **WHEN** the test applies a pair whose `old` occurs twice
- **THEN** the error is `FEN-3004` naming the pair and the count 2

### Requirement: MCP edit option
`fenolite mcp --allow-edit` SHALL list the tool `fenolite_edit`; without it the tool SHALL NOT be listed, and `--read-only` SHALL win over it. The option's help SHALL say that a client that may edit a design script and build it may run code as the user.

#### Scenario: Edit listed only on request
- **WHEN** `uv run pytest tests/unit/cli/test_mcp_cmd.py -k allow_edit` lists the tools with and without `--allow-edit`
- **THEN** `fenolite_edit` is in the first list only, and not with `--allow-edit --read-only`
