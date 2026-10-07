## ADDED Requirements

### Requirement: Packaged agent guide
The package `fenolite.agent` SHALL hold everything an AI agent needs to start using Fenolite from an installed wheel: a skill folder, its pages and starter projects, with `fenolite.agent.guide` as their only reader.
- The files MUST be `src/fenolite/agent/skill/SKILL.md`, the pages `src/fenolite/agent/skill/references/<topic>.md`, and one folder `src/fenolite/agent/starters/<name>/` per starter with `starter.toml` and `design.py.tmpl`. The repository root MUST NOT hold an `agent/` folder.
- `SKILL.md` MUST start with front matter of exactly `name` and `description`, and `name` MUST equal `guide.SKILL_NAME`, `fenolite`. A page MUST start with front matter of exactly `topic`, `title` and `summary`; `topic` MUST match `[a-z0-9-]+`, MUST equal the file's stem and MUST NOT be `start`; `summary` MUST be one line of at most 160 characters.
- `guide.pages() -> tuple[Page, ...]` MUST return `Page(topic, title, summary, text)` for the page `start` first and then every page of `references/` sorted by topic. The page `start` is the body of `SKILL.md`: its `title` is that body's first heading and its `summary` the front matter's `description`. `text` is the file without its front matter.
- `guide.page(topic)` MUST return one page and raise `KeyError` for an unknown topic. `guide.skill_files()` MUST return every file of `skill/` as `SkillFile(path, data)`, with `path` relative to `skill/` in POSIX form, sorted.
- A missing or unknown front-matter key, a duplicate topic and a malformed topic MUST raise `guide.GuideError` naming the file.
- `guide` MUST read through `importlib.resources.files("fenolite.agent")`, MUST import the standard library only, and MUST open no network connection and run no program.
- A wheel built from the repository MUST contain every file named above.
- No module, class, command or capability of the agent guide MUST hold the word `kit`: that name belongs to the Altium verification kit (`altium-verification`; the command `fenolite kit`).

#### Scenario: Guide loads from the installed package
- **WHEN** `uv run pytest tests/unit/agent/test_guide.py -k loads` calls `guide.pages()`, `guide.skill_files()` and `guide.starters()`
- **THEN** the first page is `start` with a non-empty title and summary, `skill_files()` holds `SKILL.md`, and `starters()` holds `blink`

#### Scenario: Malformed page is refused
- **GIVEN** a copy of the skill folder, made in the test, with a page whose front matter lacks `summary`, and another whose `topic` differs from its file name
- **WHEN** the loader reads each copy
- **THEN** it raises `GuideError` naming the file

#### Scenario: Wheel carries the guide
- **WHEN** the `wheel` CI job installs the built wheel in a clean environment and runs `fenolite guide start --text` and `fenolite init blink --dry-run --json` from an empty folder
- **THEN** both exit 0, the first prints the start page, and the plan of the second lists `blink/design.py`

#### Scenario: Guide stays stdlib-only
- **WHEN** `uv run pytest tests/unit/test_import_graph.py` runs
- **THEN** it passes with `fenolite.agent` importing no other `fenolite` package and no third-party package

### Requirement: Start page
`src/fenolite/agent/skill/SKILL.md` SHALL be the one page an agent reads first, under 200 lines, and every statement of it SHALL hold for the installed version.
- It MUST state: `fenolite capabilities --brief --json` first; `fenolite guide <topic> --text` as the way to read a page; the exit codes 0 to 7 with what to do for each; `--dry-run` before `--confirm`; that an evidence level below `KICAD-VERIFIED` is unconfirmed; one fix per iteration, judged by `fenolite check`.
- It MUST hold exactly one fenced block tagged `fenolite-loop` (`release-gate`, "Agent guide is executable"), say what each step is for, and say that `place` and `fill` change nothing on the starter and when they matter.
- It MUST say that the pages printed by `fenolite guide` belong to the installed version and that a copied skill folder names the version it came from in its last line.
- It MUST keep a section on the commands that answer small questions between the steps, and that section MUST name `inspect`, `pads`, `doctor` and every other public command that `agent/SKILL.md` named at the commit before it moved. `tests/unit/test_agent_skill.py` MUST hold that list of names and fail for one that the page no longer names.
- It MUST say that `capabilities --json` holds `result.matrix`, the reply to read before choosing an operation on a file kind, and that the status of each Altium write kind is read there; it MUST NOT give that status as a fixed word of its own.
- It MUST say, in one sentence, that the Altium verification kit (`fenolite kit`) is a run that a person performs in Altium Designer and is not the agent guide.
- It MUST NOT name a company, a private path or a user name, and MUST NOT state a design-rule value as a rule.

#### Scenario: Start page states the rules
- **WHEN** `uv run pytest tests/unit/test_agent_skill.py -k rules` reads the file
- **THEN** it finds each statement above, a table row for each exit code 0 to 7, fewer than 200 lines, and no private path

#### Scenario: No command is lost
- **GIVEN** the list, held in the test, of the 22 public commands that `agent/SKILL.md` names at `9aba2dff`: `build`, `capabilities`, `check`, `diff`, `doctor`, `explain`, `export`, `fill`, `fmt`, `inspect`, `kit`, `manifest`, `neighbors`, `net`, `netlist`, `pads`, `place`, `region`, `render`, `restore`, `roundtrip` and `route`
- **WHEN** `uv run pytest tests/unit/test_agent_skill.py -k commands_kept` reads the start page
- **THEN** it finds `fenolite <name>` for each of them and for `guide`, `skill` and `init`

### Requirement: Starter projects
`fenolite.agent.guide` SHALL offer starter projects: design scripts that build with the built-in catalog alone and that the suites take through the loop.
- `guide.starters() -> tuple[Starter, ...]` MUST return `Starter(name, summary, files)` sorted by name, from each folder's `starter.toml` (`summary`, one line). `guide.render_starter(name, design_name) -> Mapping[str, bytes]` MUST return the files to write, here `design.py`, with every token `@NAME@` of the template replaced by `design_name`.
- A template MUST start with the line `# SPDX-License-Identifier: CC0-1.0`, MUST name lib ids of the `Fenolite:` catalog only, MUST bind a module-level `design`, and MUST place every part.
- The starter `blink` MUST exist: a two-pin header, a resistor and a LED on a 30 mm by 20 mm two-layer board, three nets of two pads each, board minimums, and a placement for which the straight track between the two pads of each net touches no other pad and no other track.
- **Hermetic proof.** For every starter and for targets 9 and 10, a test MUST render it, build it with no library table and with subprocess creation patched to raise, and find: exit 0, no issue of severity `error`, every lib id reported as `builtin`, and `result.staged` empty. For `blink` the test MUST then run `fenolite route --router direct --confirm` (three nets routed, none unrouted) and `fenolite check --stages model.validate,copper.clearance` (both stages `ok`).
- **Oracle proof.** `tests/kicad/acceptance/test_skill_block.py` (`release-gate`, "Agent guide is executable") takes `blink` through the whole loop on the running `kicad-cli`.

#### Scenario: Blink builds and routes without a tool
- **WHEN** `uv run pytest tests/unit/cli/test_init_cmd.py -k starter` runs
- **THEN** `blink` builds for both targets with every lib id `builtin` and nothing staged, the `direct` router routes its three nets, and the two check stages are `ok`

#### Scenario: Starter that names a library part is refused by the test
- **GIVEN** a copy of the starter, made in the test, whose resistor names `Device:R`
- **WHEN** the starter test's catalog rule runs on it
- **THEN** it fails and names the lib id

### Requirement: Agent folders table
`fenolite.agent.guide.AGENT_DIRS` SHALL map an agent's name to the project-relative folder that agent reads skills from, and every row SHALL be backed by a public source.
- The table MUST hold `claude-code` → `.claude/skills`, with the source S-0610.
- Every row MUST have a comment naming an id of `docs/evidence/sources.md`, the public page that documents that folder, and a test MUST fail for a row without a registered id.
- A folder MUST be relative and MUST NOT hold `..`.

#### Scenario: Rows are sourced
- **WHEN** `uv run pytest tests/unit/agent/test_guide.py -k agent_dirs` reads the table and the comments beside its rows
- **THEN** every row names a registered source id, and a copy of the module with an unsourced row fails the same check
