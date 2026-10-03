## ADDED Requirements

### Requirement: Job extras
`routing.protocol.RoutingJob` SHALL gain the field `extra: Mapping[str, object] = {}`, which the command fills with data that `routing` cannot type: `board_pads` (the `BoardPad`s of `BoardFrame.board_pads`) and `outline` (the rings of `board_outline`). A router that needs neither MUST ignore it, and the built-in `direct` router and the KiCadRoutingTools plugin MUST behave as before.

#### Scenario: Extras passed by the command
- **GIVEN** a test router that records its job
- **WHEN** `uv run pytest tests/unit/cli/test_route_cmd.py -k extra` runs `fenolite route` with it
- **THEN** the recorded job's `extra` holds `board_pads` and `outline`

### Requirement: Freerouting plugin
`fenolite.routing.plugins.specctra.freerouting.FreeroutingRouter` SHALL route through Freerouting (S-0220), run as a subprocess, and SHALL be registered as `freerouting` in the entry-point group `fenolite.routers`.
- **Location.** The jar is the constructor's `path`, else `FENOLITE_FREEROUTING_JAR`; `java` is `FENOLITE_JAVA`, else `java` on `PATH`. A `path` of the form `docker:<image>` MUST run that image instead, with the run folder mounted and `--network none`.
- **Availability.** `available()` MUST be false with a reason when the jar is missing or `java -version` gives a major below `JAVA_MIN = 25`, and MUST start no router.
- **Run.** The plugin MUST write the design file with `write_dsn` into a fresh temporary directory and run `java -jar <jar> -de board.dsn -do board.ses -mp <passes> -mt 1 -da --gui.enabled=false` there, with `HOME` set to that directory and a timeout. `-da` MUST always be passed and MUST NOT be removable through router options.
- **Result.** The session MUST be read with `read_session` and `to_copper`. A missing or unreadable session MUST give `route.tool-failed` (error) and no copper.
- **Pin.** `PINNED_VERSION` MUST be `"2.4.1"`; another version MUST give `route.tool-unpinned` (warning).
- **Data.** `sends_data_offsite` MUST be `True` until `H-G-DSN-OFFLINE` is recorded as `present`, and `False` after; while it is `True`, `fenolite route` refuses the router without `--allow-offsite` (c0016).
- Fenolite MUST NOT import, vendor or download Freerouting.

#### Scenario: Fake java
- **GIVEN** `tests/_fakefreerouting.py`, a fake `java` that records its arguments and writes the authored session for the two-pad board
- **WHEN** `uv run pytest tests/unit/routing/test_freerouting.py -k route` routes the two-pad job
- **THEN** the result holds the session's tracks, and the recorded arguments hold `-de`, `-do`, `-mt 1`, `-da` and `--gui.enabled=false`

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
