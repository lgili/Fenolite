## ADDED Requirements

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
