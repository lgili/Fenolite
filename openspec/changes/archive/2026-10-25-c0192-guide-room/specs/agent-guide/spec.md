## MODIFIED Requirements

### Requirement: Generated guide pages
`tools/gen_agent_guide.py` SHALL write the parts of the guide that are lists, from the code that defines them, and SHALL have a mode that only checks.
- It MUST write `references/commands.md` (topic `commands`): for each public command, in name order, its name, summary and whether it writes, and its arguments from `fenolite.cli.describe.describe` (flags, type, choices, default, help).
- In `references/commands.md`, a command's usage line MUST show only `[OPTIONS]` (when the command has optional flags), its required options and its positionals. Each option's line MUST name the placeholder of the full usage line after its last flag, such as `--target {altium,kicad}`; a choice placeholder replaces the list of choices. The lines MUST NOT repeat what the head of the page states once: the types `string` and `boolean`, `required` and `optional`, and the flags `--dry-run`, `--confirm` and `--plan`.
- It MUST write `references/dsl-reference.md` (topic `dsl-reference`): for each name of `fenolite.dsl.__all__` that is not in `DSL_NOT_TAUGHT`, in name order, its kind (class, function or constant), its signature from `inspect.signature`, and the first sentence of its docstring.
- It MUST write the index of pages of the start page between its two marker lines.
- Each generated page MUST say in its first line after the front matter that it is generated and by which tool.
- `--check` MUST write nothing and MUST exit 1, naming each file that would change, when the files are not current; otherwise it exits 0.
- The output MUST be deterministic: two runs give the same bytes.
- `make check-fast` MUST run `tools/gen_agent_guide.py --check`.

#### Scenario: Pages are current
- **WHEN** `uv run python tools/gen_agent_guide.py --check` runs on a clean checkout
- **THEN** it exits 0

#### Scenario: Drift is reported
- **GIVEN** a command's help line changed in the test's copy of the registry
- **WHEN** `uv run pytest tests/unit/agent/test_pages.py -k generated` runs the generator's check on it
- **THEN** it exits 1 and names `references/commands.md`

#### Scenario: The page commands is compact
- **WHEN** `uv run pytest tests/unit/agent/test_pages.py -k generated` reads the page `commands`
- **THEN** the section `route` has the usage line `fenolite route [OPTIONS] --router NAME PATH`, its `--router` line starts `` `--router NAME`: ``, the line of `catalog --kind` is `` `--kind {footprint,symbol}` ``, and no usage line holds `[--`
