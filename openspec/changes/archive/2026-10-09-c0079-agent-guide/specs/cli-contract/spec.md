## ADDED Requirements

### Requirement: Command text
`fenolite.cli.api.Result` SHALL have the field `text: str | None = None`, a text that a command wants printed as it is in text mode.
- In text mode, when `text` is set and the command succeeded, stdout MUST start with the status line that every command prints (`fenolite <name>: ok`), one empty line, the text, and one newline; the `input`, `result` and `evidence` lines of the generic rendering MUST NOT be printed.
- When the envelope holds issues or a receipt, their lines MUST follow the text after one empty line, in the form text mode gives them without `text`. An envelope with neither MUST end with the text's newline.
- `--format concise` ("Concise output") MUST fold the issues before they are printed, as it does without `text`, and MUST NOT change the text.
- In JSON mode `text` MUST have no effect: the envelope is unchanged and holds no key for it.
- A command without `text` MUST print as before this requirement.

#### Scenario: Text is printed after the status line
- **GIVEN** `_echo --text-body "line one"`, a hidden option that sets `Result.text`
- **WHEN** `uv run pytest tests/unit/cli/test_output.py -k command_text` runs it with `--text`, and with `--json`
- **THEN** the first stdout is `fenolite _echo: ok`, an empty line and `line one`, and the second is an envelope without that text

#### Scenario: Issues follow the text
- **WHEN** `_echo --text-body "line one" --issue warning --text` runs
- **THEN** stdout is the status line, an empty line, `line one`, an empty line and one line that starts with `warning:`

### Requirement: Command description
`fenolite.cli.describe` SHALL describe the arguments of every registered command as data taken from the command's own parser, so that documentation and other front ends never declare them a second time.
- `describe(command) -> CommandDescription` MUST return `name`, `summary` (the command's help line), `mutates`, `usage` (one line starting with `fenolite <name>`) and `arguments`, a tuple of `Argument(name, flags, kind, type, choices, default, required, repeatable, help)` in the parser's order.
- `kind` MUST be `positional`, `option` (takes a value) or `flag` (takes none). `type` MUST be `integer` or `number` for a parser type of `int` or `float`, `boolean` for a flag, and `string` otherwise. `flags` holds the option strings, empty for a positional. `choices` is a sorted list or `null`. `default` is a JSON value or `null`. `repeatable` is true for an argument that may be given more than once or takes several values.
- The global flags (`--json`, `--text`, `--fields`, `--limit`, `--cursor`, `--format`, `--seed`, `--timestamp`, `--no-backup`, `--kicad-version`, `--allow-lossy`, and those a later change adds) MUST NOT be in `arguments`; `global_arguments()` MUST return them once, read from the same parser. `--dry-run` and `--confirm` MUST be in the `arguments` of a mutating command and of no other.
- `describe` MUST build the description from the parser that `fenolite.cli.main.build_parser` gives the command, MUST run no command and MUST have no side effect.
- `CommandDescription.to_json()` and `Argument.to_json()` MUST return plain JSON values with exactly the fields above.
- A test MUST fail, for any registered command, when an option string that its `--help` prints is missing from its description or from `global_arguments()`, and when the description holds one that `--help` does not print.

#### Scenario: Build is described
- **WHEN** `uv run pytest tests/unit/cli/test_describe.py -k build` calls `describe` on the `build` command
- **THEN** `arguments` holds a `positional` for the design script, the `option` `--out` with `required` true, the `option` `--target` with the choices `altium` and `kicad`, and the flags `--dry-run` and `--confirm`; and it holds no `--json`

#### Scenario: Read-only command has no protocol flags
- **WHEN** `describe` is called on `check`
- **THEN** no argument has the flag `--confirm`, and `mutates` is `false`

#### Scenario: Global flags are listed once
- **WHEN** `uv run pytest tests/unit/cli/test_describe.py -k global_flags` calls `global_arguments()`
- **THEN** it holds `--limit` with the type `integer`, `--cursor`, and `--format` with the choices `concise` and `detailed`, and no command's `arguments` holds any of the three

#### Scenario: Descriptions agree with help
- **WHEN** `uv run pytest tests/unit/cli/test_describe.py -k agrees_with_help` runs over the command registry
- **THEN** for every command the option strings of its description and of `global_arguments()` equal the option strings found in its `--help` text, apart from `-h` and `--help`

### Requirement: Brief capabilities
`fenolite capabilities --brief` SHALL answer the first question of an agent in a reply whose size is bounded: what is installed here, what can it do, and where to read more. The default result of `capabilities` MUST stay as it is.
- With `--brief`, `result` MUST hold exactly the keys `fenolite_version`, `commands`, `targets`, `tools`, `routers`, `guide`, `starters` and `sends_data_offsite`.
- `commands` MUST list every command that is not hidden, sorted by name, each with exactly `name`, `summary` and `mutates`, `summary` being the command's help line.
- `targets` MUST hold exactly `build`, `kicad` and `default`: `build` is the sorted list of choices of `build --target` (`altium` and `kicad`), read from the command's description; `kicad` and `default` are the target majors and the default target of the `kicad` backend's entry in the default view. The brief view MUST NOT state an evidence level or the word `experimental` for a target: the status of each Altium write kind stays in the default view ("Backends in capabilities", "Experimental features in capabilities", "Evidence matrix in capabilities").
- `tools` and `sends_data_offsite` MUST equal the default view's.
- `routers` MUST list the registered routers sorted by name, each with exactly `name`, `available` and `reason`, from `Router.available()`; with `--no-tools`, `available()` MUST NOT be called and both values MUST be `null`.
- `guide` MUST list `guide.pages()` with exactly `topic`, `title` and `summary`, and `starters` MUST list `guide.starters()` with exactly `name` and `summary`.
- The JSON of the brief `result` with `--no-tools` MUST be under 300 bytes per listed command plus 2 000 bytes, and MUST hold none of the keys `backends`, `experimental`, `extras` and `matrix`; a test MUST check both.
- `--brief` and `--command` MUST exclude each other (exit 2, `FEN-2001`). `--fields` MUST work on the brief result. `--format concise` MUST be accepted with `--brief` and MUST NOT change `result`: it folds issues, and the view chooses the result.
- `docs/cli-contract.md` MUST describe the brief view under "Discovery".

#### Scenario: Brief view
- **WHEN** `uv run fenolite capabilities --brief --no-tools --json` runs
- **THEN** the exit code is 0, `result` has exactly the eight keys, `result.commands` names `build` with a non-empty `summary` and `mutates` true and holds no `_echo`, `result.targets.build` is `["altium", "kicad"]`, `result.routers` names `direct` with `available` `null`, `result.guide[0].topic` is `start`, and `result.starters` names `blink`

#### Scenario: Router availability
- **GIVEN** no Freerouting jar and no `FENOLITE_KRT`
- **WHEN** `uv run pytest tests/unit/cli/test_capabilities_brief.py -k routers` runs `capabilities --brief --json`
- **THEN** `direct` has `available` true and a `null` reason, and `freerouting` has `available` false and a reason

#### Scenario: Size bound
- **WHEN** `uv run pytest tests/unit/cli/test_capabilities_brief.py -k size` measures the brief result
- **THEN** it is under 300 bytes per listed command plus 2 000 bytes, and holds no `experimental` key

#### Scenario: Default view unchanged
- **WHEN** `uv run fenolite capabilities --json --no-tools` runs
- **THEN** `result` holds the keys it held before this requirement, with `backends`, `experimental` and `matrix` unchanged

### Requirement: Command view of capabilities
`fenolite capabilities --command NAME` SHALL return the description of one command.
- `result` MUST hold exactly `command` and `global_arguments`. `result.command` MUST be that command's entry of the default view's `commands`, extended with `summary`, `usage` and `arguments` from `fenolite.cli.describe.describe`; `result.global_arguments` MUST be `describe.global_arguments()` as JSON.
- A hidden command MUST be described when it is named exactly.
- An unknown name MUST exit 2 with `FEN-2001` and a hint that names the three closest command names.
- The view MUST run no tool, with or without `--no-tools`.
- `docs/cli-contract.md` MUST describe the view and the fields of an argument under "Discovery".

#### Scenario: One command
- **WHEN** `uv run fenolite capabilities --command route --json` runs
- **THEN** the exit code is 0, `result.command.name` is `route`, `result.command.mutates` is true, `result.command.arguments` holds the option `--router`, and `result.global_arguments` holds `--fields`

#### Scenario: Unknown command
- **WHEN** `fenolite capabilities --command rout` runs
- **THEN** the exit code is 2 and the hint names `route`

### Requirement: Guide command
`fenolite guide [TOPIC]` SHALL be registered by `src/fenolite/cli/cmd_guide.py` with `mutates=False`, and SHALL print the pages of the packaged agent guide (`agent-guide`, "Packaged agent guide") for the installed version, running no tool.
- **Without a topic.** `result` MUST hold exactly `version` and `topics`; `topics` lists `guide.pages()` in order, each with exactly `topic`, `title`, `summary` and `lines`. The command text MUST be one line per page, `<topic>: <summary>`.
- **With a topic.** `result` MUST hold exactly `topic`, `title`, `summary`, `text` and `version`. The command text ("Command text") MUST be the page's `text`, unchanged.
- An unknown topic MUST exit 2 with `FEN-2001` and a hint that names the closest topics, or all topics when none is close.
- The output MUST be deterministic and MUST hold no absolute path. The envelope evidence is `UNVERIFIED`.
- `example_args` MUST be `("start",)`. `docs/cli-contract.md` MUST have a section `guide`.

#### Scenario: List of pages
- **WHEN** `uv run fenolite guide --json` runs
- **THEN** the exit code is 0, `result.topics[0].topic` is `start`, and every entry has a one-line `summary`

#### Scenario: One page as text
- **WHEN** `uv run fenolite guide start --text` runs
- **THEN** stdout is the status line, an empty line and the body of `SKILL.md` without its front matter

#### Scenario: Unknown topic
- **WHEN** `fenolite guide strat` runs
- **THEN** the exit code is 2 and the hint names `start`

### Requirement: Skill command
`fenolite skill show` and `fenolite skill install [--agent NAME | --dir DIR] [--agents-md]` SHALL be registered by `src/fenolite/cli/cmd_skill.py` with `mutates=True`, and SHALL copy the packaged skill folder to where an agent reads it, only through the mutation protocol.
- **`show`.** It MUST plan no write, and `result` MUST hold exactly `name`, `description`, `version`, `files` (each `path`, `bytes` and `sha256`, of `guide.skill_files()`) and `agents` (each `agent` and `dir`, of `guide.AGENT_DIRS`).
- **`install`, the folder.** The target is `DIR`, or the folder of `guide.AGENT_DIRS[NAME]`; `--agent` and `--dir` MUST exclude each other, and an unknown agent MUST exit 2 with a hint that names the agents and `--dir`. The command MUST plan one write per file of `guide.skill_files()`, at `<target>/fenolite/<path>`.
- **`install`, the version line.** The planned `SKILL.md` MUST be the packaged file followed by the line `<!-- installed from fenolite <version> -->`; every other file MUST be planned byte for byte.
- **`install`, the pointer.** With `--agents-md` the command MUST also plan `AGENTS.md` in the working directory. Its content MUST be: for a missing file, `guide.AGENTS_SECTION` between the lines `<!-- fenolite:begin -->` and `<!-- fenolite:end -->`; for a file that holds both marker lines, the same file with everything between them replaced by the section; for a file without them, the file followed by an empty line and the marked section. A file that holds one marker without the other MUST exit 3 with `FEN-3004`.
- `guide.AGENTS_SECTION` MUST tell an agent to run `fenolite guide start --text` before a task about a circuit board, MUST name `fenolite capabilities --brief`, and MUST be at most 12 lines.
- `install` with none of `--agent`, `--dir` and `--agents-md` MUST exit 2 with `FEN-2001`.
- **Result.** `result` MUST hold `action`, `target` (or `null` with `--agents-md` alone), `files` (the paths planned) and `version`.
- The command MUST run no tool and open no connection.
- `example_args` MUST be `("show",)` and `mutation_example_args` `("install", "--dir", "skills")`. `docs/cli-contract.md` MUST have a section `skill`.

#### Scenario: Install into a named folder
- **WHEN** `uv run pytest tests/unit/cli/test_skill_cmd.py -k install_dir` runs `fenolite skill install --dir skills --confirm --json` in an empty folder
- **THEN** `skills/fenolite/SKILL.md` exists, its last line names the Fenolite version, its text before that line equals the packaged file, and the receipt lists every written file with its SHA-256

#### Scenario: Install for an agent
- **WHEN** `fenolite skill install --agent claude-code --dry-run --json` runs
- **THEN** the plan lists `.claude/skills/fenolite/SKILL.md` and nothing is written

#### Scenario: Pointer section is idempotent
- **GIVEN** an `AGENTS.md` with two lines of the user's own text
- **WHEN** `fenolite skill install --agents-md --confirm` runs twice
- **THEN** after the first run the file holds the user's two lines, an empty line and the marked section; the second run plans a file with the same bytes; and `AGENTS.md.bak` holds the user's original file after the first run

#### Scenario: Nothing asked
- **WHEN** `fenolite skill install --dry-run` runs
- **THEN** the exit code is 2 and the hint names `--agent`, `--dir` and `--agents-md`

### Requirement: Init command
`fenolite init DIR [--starter NAME] [--name NAME] [--force]` SHALL be registered by `src/fenolite/cli/cmd_init.py` with `mutates=True`, and SHALL write a starter project (`agent-guide`, "Starter projects") into `DIR`.
- `--starter` MUST default to `blink`; an unknown starter MUST exit 2 with `FEN-2001` and a hint that names the starters.
- The design name MUST be `--name`, else the last component of `DIR`; a name that does not match `^[A-Za-z0-9][A-Za-z0-9_.-]*$` MUST exit 2 with a hint that names `--name`.
- The command MUST plan one write per file of `guide.render_starter(starter, name)`, at `DIR/<file>`.
- When `DIR/design.py` exists, the command MUST exit 2 with `FEN-2001` and a hint that names `--force`, unless `--force` is given; with it the mutation protocol's backup applies.
- `result` MUST hold `starter`, `name`, `design` (the path of the script) and `next`: the two command lines `fenolite build <design> --out DIR/build --dry-run --json` and the same with `--confirm`. A test MUST parse both with the command line's own parser.
- The command MUST run no tool. `example_args` MUST be `("proj", "--dry-run")` and `mutation_example_args` `("proj",)`. `docs/cli-contract.md` MUST have a section `init`.

#### Scenario: New project
- **WHEN** `uv run pytest tests/unit/cli/test_init_cmd.py -k new_project` runs `fenolite init board --confirm --json` in an empty folder, and then the first command of `result.next`
- **THEN** `board/design.py` exists, starts with the `CC0-1.0` line and names the design `board`, and the build's dry run exits 0

#### Scenario: Existing script is kept
- **GIVEN** `board/design.py` written by the user
- **WHEN** `fenolite init board --confirm` runs, and then `fenolite init board --force --confirm`
- **THEN** the first exits 2 with a hint naming `--force` and leaves the file, and the second replaces it and keeps the user's text in `board/design.py.bak`

#### Scenario: Name that is not a design name
- **WHEN** `fenolite init "my board" --dry-run` runs
- **THEN** the exit code is 2 and the hint names `--name`
