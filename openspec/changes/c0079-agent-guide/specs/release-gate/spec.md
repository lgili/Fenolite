## MODIFIED Requirements

### Requirement: Agent guide is executable
`src/fenolite/agent/skill/SKILL.md` SHALL teach the loop from an empty folder to fabrication files, and its commands SHALL be run by tests.
- The file MUST have front matter with `name` and `description`, MUST be under 200 lines, and MUST hold exactly one fenced block tagged `fenolite-loop` with at most ten lines, each a `fenolite` command.
- The block MUST hold, in this order, `capabilities --brief`, `init blink`, `build` with `--dry-run`, `build` with `--confirm`, `place`, `route --router direct`, `fill`, `check`, `export` and `render`. Every line after the first two MUST name `blink/design.py` or a folder under `blink/`, the project that `init` writes (`agent-guide`, "Starter projects").
- The guide MUST state: `capabilities --brief` first; the exit codes 0 to 7; `--dry-run` before `--confirm`; that a level below `KICAD-VERIFIED` is unconfirmed; what to do for each non-zero exit code (`agent-guide`, "Start page").
- `README.md` MUST hold the same block, and `AGENTS.md` MUST name the guide's path and the command `fenolite guide`.
- `tests/unit/test_agent_skill.py` MUST parse each line of the block with the CLI's own argument parser and fail for an unknown command or flag. It MUST also run the first six lines in an empty temporary folder with `subprocess.run` and `subprocess.Popen` patched to raise; each MUST exit 0 and each envelope MUST hold `evidence.level`.
- `tests/kicad/acceptance/test_skill_block.py` MUST run all the lines in order in an empty temporary folder on the running `kicad-cli`, once with `--kicad-version 9` and once with `--kicad-version 10` added to every line that takes it; a target-10 run is skipped on 9.0.x. Each line MUST exit 0, each envelope MUST hold `evidence.level`, and `check` MUST report no design-rule violation and no unconnected item.
- The guide MUST NOT name a company, a private path or a user name.

#### Scenario: Block parses
- **WHEN** `uv run pytest tests/unit/test_agent_skill.py` runs
- **THEN** it finds one `fenolite-loop` block of at most ten lines, each accepted by the parser, the same block in `README.md`, and the commands in the order above

#### Scenario: A stale flag fails
- **GIVEN** a copy of the guide whose block holds `fenolite route blink/build --engine x`
- **WHEN** the block check runs on it
- **THEN** it fails and names `--engine`

#### Scenario: First six lines need no tool
- **WHEN** `uv run pytest tests/unit/test_agent_skill.py -k hermetic_prefix` runs the lines up to `route` with subprocess creation patched to raise
- **THEN** each exits 0, `blink/build/blink.kicad_pcb` exists, and the route's `unrouted` list is empty

#### Scenario: Ten commands close the loop
- **WHEN** `uv run pytest tests/kicad/acceptance/test_skill_block.py -rA` runs on 10.0.6, and on 9.0.9
- **THEN** every line exits 0 for each target the running tool can read, every envelope carries `evidence.level`, `check` reports no violation and no unconnected item, and `blink/fab` holds a manifest and at least one Gerber file
