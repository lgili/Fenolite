## ADDED Requirements

### Requirement: Tools folder
`fenolite.core.tools` SHALL name the one folder in which Fenolite keeps external tools that the user asked it to fetch, and SHALL create nothing by itself.
- `tools_dir() -> Path` MUST return, in this order: the value of `FENOLITE_TOOLS_DIR` (`TOOLS_ENV`) when it is set; `$XDG_CACHE_HOME/fenolite/tools` when that variable is set; `~/Library/Caches/fenolite/tools` when `sys.platform` is `darwin`; `%LOCALAPPDATA%\fenolite\tools` when it is `win32` and the variable is set; `~/.cache/fenolite/tools` otherwise.
- A relative `FENOLITE_TOOLS_DIR` MUST raise `ValueError` naming the variable; the command line maps it to exit 2.
- `tool_path(name, file) -> Path` MUST return `tools_dir() / name / file`.
- Neither function MUST create a folder, read a file or run a program. The environment MUST be read at each call.
- The module MUST import the standard library only (`package-layering`: `core`).
- `docs/routing.md` MUST name the folder per platform and the variable.

#### Scenario: Explicit folder
- **GIVEN** `FENOLITE_TOOLS_DIR` set to an absolute folder of the test
- **WHEN** `uv run pytest tests/unit/core/test_tools.py -k explicit` calls `tool_path("freerouting", "freerouting-2.4.1.jar")`
- **THEN** it returns that folder joined with `freerouting/freerouting-2.4.1.jar`, and the folder was not created

#### Scenario: Platform defaults
- **GIVEN** `FENOLITE_TOOLS_DIR` unset, and `sys.platform`, `XDG_CACHE_HOME`, `LOCALAPPDATA` and the home folder patched in turn
- **WHEN** `tools_dir()` is called
- **THEN** it returns the folder of the rule above for each of the four cases

#### Scenario: Relative folder refused
- **GIVEN** `FENOLITE_TOOLS_DIR` set to `tools`
- **WHEN** `fenolite fetch freerouting --dry-run` runs
- **THEN** the exit code is 2 and the message names `FENOLITE_TOOLS_DIR`

### Requirement: Fetched tools decision record
`docs/adr/0007-fetching-external-tools.md` SHALL record the rule under which Fenolite downloads an external tool, with the six sections of `docs/adr/README.md` and the status `Accepted`, dated with the maintainer's decision of 2026-10-05, which he confirmed on 2026-10-07. The record MUST name the row of "Open decisions" in `docs/roadmap.md` that holds the decision, and that row MUST exist.
- The decision MUST state: a download happens only inside `fenolite fetch`, only with `--confirm`, only from the address of a table row whose source is registered in `docs/evidence/sources.md`, and only when size and SHA-256 match the row; Fenolite bundles no tool and imports nothing from one; a tool under a copyleft licence stays a separate program (ADR-0004); no other command opens a network connection for a tool.
- The alternatives MUST name bundling the jar, a download on the first `route`, and leaving the install manual, each with the reason it was not chosen.
- `docs/adr/0006-specctra-and-freerouting.md` MUST gain one dated line under its Decision 3 that says the jar may be downloaded by `fenolite fetch` (ADR-0007), and its other sentences MUST stay.
- `docs/adr/README.md` MUST list ADR-0007, and `LEGAL-ANNEX.md` MUST hold a row for the command, the ADR and the files they touch.

#### Scenario: Record present and well formed
- **WHEN** `uv run pytest tests/unit/test_adrs.py tests/unit/test_legal_docs.py` runs
- **THEN** it passes with ADR-0007 listed, its six sections present and its status `Accepted`, and the row number that the record names is a row of "Open decisions" that holds `fenolite fetch`

#### Scenario: Earlier decision amended, not rewritten
- **WHEN** `git diff` of `docs/adr/0006-specctra-and-freerouting.md` is read for this change
- **THEN** it adds one line that names ADR-0007 and removes none

## MODIFIED Requirements

### Requirement: Freerouting plugin
`fenolite.routing.plugins.specctra.freerouting.FreeroutingRouter` SHALL route through Freerouting (S-0220), run as a subprocess, and SHALL be registered as `freerouting` in the entry-point group `fenolite.routers`.
- **Location.** The jar is the constructor's `path`, else `FENOLITE_FREEROUTING_JAR`, else the file `fenolite.core.tools.tool_path("freerouting", f"freerouting-{PINNED_VERSION}.jar")` when it exists ("Tools folder"); `java` is the constructor's `java`, else `FENOLITE_JAVA`, else `java` on `PATH`. The environment and the tools folder MUST be read when the router is used, not when it is constructed, because the registry holds one instance per process. A `path` of the form `docker:<image>` MUST run that image instead, with the run folder mounted and `--network none`. `fenolite route --router freerouting --router-path PATH` names the jar or the image. `jar_source` MUST say which of the three gave the jar: `argument`, `env` or `fetched`, or `None` without a jar.
- **Availability.** `available()` MUST be false with a reason when the jar is missing or `java -version` gives a major below `JAVA_MIN = 25`, and MUST start no router. The reason for a missing jar MUST name the command `fenolite fetch freerouting --confirm` and the variable `FENOLITE_FREEROUTING_JAR`. The version MUST be learned without running the jar: `PINNED_VERSION` when the jar's manifest names the build revision of the pinned tag (`PINNED_REVISION`, S-0223), else the version in the file name `freerouting-<version>.jar`, else `unknown`.
- **Run.** The plugin MUST write the design file with `write_dsn`, from the job's `extra` (`board_pads`, `outline`), into a fresh temporary directory and run `java -jar <jar> -de board.dsn -do board.ses -mp <passes> -mt 1 -da --gui.enabled=false` there, with `HOME` set to that directory and a timeout (900 s by default). `-da` MUST always be passed and MUST NOT be removable through router options. The only router option is `max-passes=N` (default 20); any other option, and a value that is not a positive integer, MUST be ignored with `route.option-ignored` (warning), a code of `routing.codes.ISSUE_CODES`. The board defaults passed to `write_dsn` are the values of the design's `Default` class, else 0.2 mm width and clearance and a 0.6 mm via with a 0.3 mm drill, as in `fenolite route`.
- **Outline.** A job whose `extra` lacks the pads or holds no outline ring MUST give `route.tool-failed` (error) and start no router: a design file needs the board outline.
- **Result.** The session MUST be read with `read_session` and `to_copper`. A missing or unreadable session, and a timeout, MUST give `route.tool-failed` (error) and no copper. `routed` holds the job's nets that got copper and `unrouted` the others; the findings of the writer and of the reader are part of the result's issues.
- **Pin.** `PINNED_VERSION` MUST be `"2.4.1"`; another version MUST give `route.tool-unpinned` (warning).
- **Data.** `sends_data_offsite` MUST be `True` until `H-G-DSN-OFFLINE` is recorded as `present`, and `False` after; while it is `True`, `fenolite route` refuses the router without `--allow-offsite` (c0016).
- Fenolite MUST NOT import or vendor Freerouting. It MUST NOT download it either, except through `fenolite fetch freerouting --confirm` (`cli-contract`, "Fetch command"): the plugin, `fenolite route`, `fenolite doctor` and `fenolite capabilities` MUST open no network connection.
- **Messages.** When the jar is missing, `fenolite route --router freerouting` MUST exit 6 with `FEN-6001` and the hint `run 'fenolite fetch freerouting --confirm'`. The `freerouting` entry of `doctor`'s `result.routers` MUST hold `source`, the value of `jar_source`.

#### Scenario: Fake java
- **GIVEN** `tests/_fakefreerouting.py`, a fake `java` that records its arguments and writes the authored session for the two-pad board
- **WHEN** `uv run pytest tests/unit/routing/test_freerouting.py -k route` routes the two-pad job
- **THEN** the result holds the session's tracks, and the recorded arguments hold `-de`, `-do`, `-mt 1`, `-da` and `--gui.enabled=false`

#### Scenario: Through the command
- **GIVEN** the two-pad board written as a KiCad board, a fake jar and the fake `java`
- **WHEN** `uv run pytest tests/unit/cli/test_route_cmd.py -k freerouting_through` runs `fenolite route two_pads.kicad_pcb --router freerouting --router-path <jar> --allow-offsite --dry-run`
- **THEN** the exit code is 0, `result.routed` is `["A"]`, and the plan holds the board

#### Scenario: Board without an outline
- **GIVEN** a board without a closed outline
- **WHEN** the plugin routes
- **THEN** the result holds `route.tool-failed` naming the outline, and no router run was recorded

#### Scenario: Java too old
- **GIVEN** a fake `java` whose `-version` prints `17.0.2`
- **WHEN** `available()` is called
- **THEN** it is false with a reason naming Java 25, and no router run was recorded

#### Scenario: Analytics cannot be re-enabled
- **WHEN** the plugin routes with the option `da=false`
- **THEN** the recorded arguments still hold `-da`, and the result holds a warning naming the ignored option

#### Scenario: No session
- **GIVEN** a fake `java` that exits 0 and writes nothing
- **WHEN** the plugin routes
- **THEN** the result has no copper and one `route.tool-failed` error

#### Scenario: Fetched jar is found
- **GIVEN** no `FENOLITE_FREEROUTING_JAR`, `FENOLITE_TOOLS_DIR` naming a folder that holds `freerouting/freerouting-2.4.1.jar` (a fake jar), and the fake `java`
- **WHEN** `uv run pytest tests/unit/routing/test_freerouting.py -k fetched` asks the router for `available()` and `jar_source`
- **THEN** it is available, `jar_source` is `fetched`, and setting `FENOLITE_FREEROUTING_JAR` to another fake jar makes `jar_source` `env`

#### Scenario: Missing jar names the command
- **GIVEN** no jar in any of the three places
- **WHEN** `uv run pytest tests/unit/cli/test_route_cmd.py -k missing_jar` runs `fenolite route two_pads.kicad_pcb --router freerouting --dry-run`, and `fenolite doctor --json`
- **THEN** the first exits 6 with `FEN-6001` and a hint that holds `fenolite fetch freerouting --confirm`, and the `freerouting` entry of the second has `available: false`, `source: null` and a reason that names the same command

#### Scenario: No connection outside fetch
- **GIVEN** `urllib.request.urlopen` and `socket.create_connection` patched to raise
- **WHEN** `uv run pytest tests/unit/cli/test_fetch_cmd.py -k no_connection` runs `route --dry-run` with the fake jar, `doctor --no-run` and `capabilities --no-tools`
- **THEN** each exits as it does without the patches
