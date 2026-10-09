# agent-guide Specification

## Purpose
TBD - created by archiving change c0079-agent-guide. Update Purpose after archive.

## Requirements

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
- The table MUST hold `claude-code` → `.claude/skills`, with the source S-0617.
- Every row MUST have a comment naming an id of `docs/evidence/sources.md`, the public page that documents that folder, and a test MUST fail for a row without a registered id.
- A folder MUST be relative and MUST NOT hold `..`.

#### Scenario: Rows are sourced
- **WHEN** `uv run pytest tests/unit/agent/test_guide.py -k agent_dirs` reads the table and the comments beside its rows
- **THEN** every row names a registered source id, and a copy of the module with an unsourced row fails the same check

### Requirement: Guide pages
The agent guide SHALL hold eleven written pages under `src/fenolite/agent/skill/references/`, each teaching one part of making a board with Fenolite, in the form that `fenolite.agent.guide` loads ("Packaged agent guide").
- The topics MUST be `design-script`, `parts`, `footprints`, `placement`, `routing`, `rules`, `checks`, `files`, `fabrication`, `altium` and `recovery`.
- `design-script` MUST teach: the shape of a script and its module-level `design`; `Design`, `Module`, `Net`, `Part`, `connect`, `no_connect` and `Power`; that a length carries a unit; the board frame (origin at the outline's top-left corner, Y down); and the cycle of an edit, `build --dry-run` and `build --confirm`, with what a rebuild keeps. It MUST hold the tested lines of `init`, `build`, `sync` and `template`.
- `parts` MUST teach: that a part needs a symbol id and a footprint; the built-in catalog and `catalog list --query`; KiCad's libraries through tables beside the script; pins by number and by name; `pad_map`; values with units (`ohm`, `farad`, `henry`, `volt`, `amp`, `watt`, `hertz`, `second`) and user properties; and the typed interfaces (`Interface`, `I2C`, `SPI`, `UART`, `USB2`, `Harness`, `DiffPair`). It MUST hold the tested line of `catalog`.
- `footprints` MUST teach `Footprint` and `Symbol` from dimensions, and MUST say that such geometry is `INFERRED` and what a person still checks against the part's datasheet.
- `placement` MUST teach `place()`, sides, rotation and locked placements, staged parts and `place --strategy grid`, `place --move`, and field placement. It MUST hold the tested lines of `place`, `pads`, `neighbors` and `region`.
- `routing` MUST teach the registered routers and what each is for, `route` with `--nets` and `--rip`, the meaning of `unrouted`, scripted copper (`track`, `via`, `stitch`, `via_step`, `arc_to`), zones and `fill`. It MUST hold the tested lines of `route`, `fill` and `net`, and of `fetch` when that command is registered.
- `rules` MUST teach net classes against minimums and selectors (`select`), MUST say that the limits are the user's or the fabricator's and that the page's numbers are examples, and MUST hold the tested line of `analyze`.
- `checks` MUST teach the stages of `check`, the fields of an issue, `explain`, the evidence levels, one fix per iteration, and `--fields`, `--stages`, `--format concise` and `--limit`. It MUST hold the tested lines of `check`, `explain`, `netlist`, `parity`, `doctor` and `capabilities`.
- `files` MUST teach how to read a file that Fenolite did not write, how to tell whether editing it is safe, how to compare two files or two designs, and how to undo a confirmed write. It MUST hold the tested lines of `inspect`, `diff`, `equivalent`, `roundtrip`, `fmt` and `restore`.
- `fabrication` MUST teach `export`, the bill of materials, the position file, the manifest and `render`, and MUST hold the tested lines of `export`, `render`, `bom`, `pnp` and `manifest`.
- `altium` MUST teach `build --target altium` and what it writes. It MUST hold a table with one row per Altium write kind, giving the status (in `write_kinds`, or `experimental`) and the evidence level that `fenolite capabilities --json` reports for that kind, and MUST NOT state a status in any other words; a test MUST compare the table with the reply and fail when they differ. It MUST say that the Altium verification kit is a run that a person performs in Altium Designer, and MUST hold the tested line of `kit`.
- `recovery` MUST follow "Recovery recipes", and MUST hold the tested lines of `guide` and `skill`.
- A public command that this list does not name MUST have its tested line on the page whose subject is closest ("Guide covers the public surface").
- Every page MUST end with a line `Read next:` naming at most three topics that exist.
- The start page MUST hold an index of the pages, one line per topic with its summary, between the lines `<!-- pages:begin -->` and `<!-- pages:end -->`.

#### Scenario: The eleven pages load
- **WHEN** `uv run pytest tests/unit/agent/test_pages.py -k topics` calls `guide.pages()`
- **THEN** it finds `start`, the eleven written topics and the two generated ones, each with a title and a one-line summary, and every `Read next:` names existing topics

#### Scenario: A page through the command line
- **WHEN** `uv run fenolite guide routing --text` runs
- **THEN** the exit code is 0 and the text names `direct`, `--rip`, `design.track` and `fenolite fill`

#### Scenario: Altium status follows capabilities
- **GIVEN** the reply of `fenolite capabilities --json --no-tools`, and a copy of it, made in the test, in which one Altium kind has moved from `experimental` to `write_kinds`
- **WHEN** `uv run pytest tests/unit/agent/test_pages.py -k altium_status` compares the table of the page `altium` with each
- **THEN** the page agrees with the real reply, and the comparison with the copy fails naming the kind

### Requirement: Executable blocks
Every fenced block of the start page and of the written pages SHALL carry a tag that says how the suites prove it, and `tests/unit/agent/test_pages.py` SHALL prove each one.
- `fenolite.agent.guide.blocks(page) -> tuple[Block, ...]` MUST return `Block(tag, argument, lines, line_number)` for every fenced block, `tag` being the first word after the fence and `argument` the rest of that line.
- The tag MUST be one of `fenolite-loop`, `fenolite-cmd`, `fenolite-design`, `fenolite-recipe`, `json` and `text`. A block with another tag or with none MUST fail the test, which names the page and the line.
- **`fenolite-cmd`.** Every line MUST start with `fenolite ` and MUST be accepted by the parser of `fenolite.cli.main.build_parser(discover())`. A line MUST NOT hold `<` or `>`.
- **`fenolite-design`.** The block MUST be a complete design script that names lib ids of the built-in catalog or definitions it authors itself. The test MUST write it to an empty folder and build it with no library table and with `subprocess.run` and `subprocess.Popen` patched to raise: exit 0 and no issue of severity `error`, for targets 9 and 10. With the argument `altium` the test MUST build it with `--target altium` instead, with the same verdict; the notices that an Altium build gives for a kind that has not graduated are warnings and do not fail it.
- **`fenolite-recipe`.** See "Recovery recipes".
- **`json` and `text`** hold samples of output and are not run.
- The generated pages MUST hold no fenced block.

#### Scenario: Every command line parses
- **WHEN** `uv run pytest tests/unit/agent/test_pages.py -k cmd` runs
- **THEN** every line of every `fenolite-cmd` block is accepted by the parser

#### Scenario: Every design builds
- **WHEN** `uv run pytest tests/unit/agent/test_pages.py -k design` runs
- **THEN** every `fenolite-design` block builds for its targets with exit 0 and no error issue, with no subprocess created

#### Scenario: An untested block is refused
- **GIVEN** a copy of a page, made in the test, with a block tagged `python`, and another with a `fenolite-cmd` line `fenolite route blink/build --engine x`
- **WHEN** the block checks run on each copy
- **THEN** the first fails naming the tag and the line, and the second fails naming `--engine`

### Requirement: Recovery recipes
The page `recovery` SHALL give, for each exit code from 2 to 7 and for the commonest findings, a recipe that the suites run: commands with the exit code each must give.
- A recipe MUST be a heading that names the code, at most three sentences, and one block tagged `fenolite-recipe <sandbox>`. Each line of the block MUST be `<command>  # exit N`, optionally followed by `, has <code>`.
- `tests/unit/agent/_sandbox.py::SANDBOXES` MUST map each sandbox name to a function that prepares a folder; an unknown name MUST fail the test.
- `tests/unit/agent/test_recipes.py` MUST, for each recipe, prepare its sandbox in an empty temporary folder, run the lines in order there with subprocess creation patched to raise, and check for each line the exit code and, when a code is named, that it is the `code` of the error object or of an issue of the envelope.
- The page MUST hold recipes for at least: a write without `--confirm` (`FEN-4001`); a wrong flag (`FEN-2001`); an unknown lib id (`FEN-3001`); a script that raises (`FEN-3004`, located by `line:<n>`); two tracks that cross (`copper.short`, exit 5, repaired by `place --move` and `route --rip`); a router that is not installed (exit 6, answered by another router); and a write that the target cannot hold (exit 7).
- Every code of the registry of `fenolite.cli.errors` MUST be named on the page, in a recipe or in a table of the remaining codes with one line each. The registry is read when the test runs, so a code that a later change registers fails the test until the page names it.
- The recipe for two crossed tracks MUST assert the code `copper.short` and the exit code only, and MUST hold a line `fenolite explain copper.short`.
- The page MUST say that the findings of KiCad's own check (`kicad.drc.*`, `kicad.erc.*`) carry KiCad's message, and name the command that lists them.

#### Scenario: Recipes behave as written
- **WHEN** `uv run pytest tests/unit/agent/test_recipes.py` runs
- **THEN** every line of every recipe gives its exit code and its code, in an empty folder, with no subprocess created

#### Scenario: Crossed tracks are repaired
- **WHEN** `uv run pytest tests/unit/agent/test_recipes.py -k crossed` runs that recipe
- **THEN** its check line exits 5 with `copper.short` before the move, and its last check line exits 0

#### Scenario: A recipe that lies fails
- **GIVEN** a copy of the page, made in the test, whose first recipe says `# exit 0` for a write without `--confirm`
- **WHEN** the recipe test runs on it
- **THEN** it fails naming the line, the exit code expected and the one found

#### Scenario: Every error code is named
- **WHEN** `uv run pytest tests/unit/agent/test_pages.py -k fen_codes` compares the registry with the page
- **THEN** every `FEN-` code of the registry is found on the page

### Requirement: Guide covers the public surface
The guide SHALL name every public command and every public name of the design DSL in a block that the suites run, so that a feature cannot be added without being taught.
- Every command of the registry that is not hidden MUST be the command of at least one line of a `fenolite-loop`, `fenolite-cmd` or `fenolite-recipe` block of the start page or of a written page.
- Every name of `fenolite.dsl.__all__` MUST appear, as a whole word, in at least one `fenolite-design` block, or be a key of `fenolite.agent.guide.DSL_NOT_TAUGHT`, a mapping from a name to a one-line reason. A key that is not in `__all__`, and a key that also appears in a design block, MUST fail the test.
- `AGENTS.md` (Workflow) and `CONTRIBUTING.md` MUST say that a change which adds a public command, a public DSL name or a `FEN-` code adds a tested line to a guide page.
- The registry and `__all__` MUST be read when the test runs. A command or a name that is on `dev` when this requirement is implemented is covered by that implementation; one that a later change adds is covered by that change.

#### Scenario: Coverage holds
- **WHEN** `uv run pytest tests/unit/agent/test_pages.py -k coverage` runs
- **THEN** no command and no DSL name is reported

#### Scenario: A new command without a line is reported
- **GIVEN** the registry extended in the test with a command `frobnicate`
- **WHEN** the coverage check runs
- **THEN** it fails and names `frobnicate`

### Requirement: Generated guide pages
`tools/gen_agent_guide.py` SHALL write the parts of the guide that are lists, from the code that defines them, and SHALL have a mode that only checks.
- It MUST write `references/commands.md` (topic `commands`): for each public command, in name order, its name, summary and whether it writes, and its arguments from `fenolite.cli.describe.describe` (flags, type, choices, default, help).
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

### Requirement: Page budgets and writing rules
The pages SHALL stay small enough to be read whole, and SHALL state only what Fenolite does.
- A written page MUST have at most 250 lines and 12 000 bytes. A generated page MUST have at most 600 lines. The files of the skill folder together MUST stay under 150 000 bytes.
- A page MUST NOT name a company, a fabricator, a standard's table, a private path or a person, and MUST NOT hold a change id (`c0000` form) or a hypothesis id (`H-…`).
- A line of prose that holds a call of `rules.minimum` or `rules.netclass` with a number MUST hold the word `example`.
- A sentence that says a result is verified MUST name the evidence label.
- `tests/unit/agent/test_pages.py` MUST check the sizes, the forbidden forms and the `example` rule.

#### Scenario: Budgets hold
- **WHEN** `uv run pytest tests/unit/agent/test_pages.py -k budget` runs
- **THEN** every written page is within 250 lines and 12 000 bytes, every generated page within 600 lines, and the folder under 150 000 bytes

#### Scenario: Forbidden forms are reported
- **GIVEN** a copy of a page, made in the test, that holds `c0042` in a sentence
- **WHEN** the writing-rules check runs on it
- **THEN** it fails naming the page and the line
