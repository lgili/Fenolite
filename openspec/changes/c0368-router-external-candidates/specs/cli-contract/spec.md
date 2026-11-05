## ADDED Requirements

### Requirement: External candidate review
The route command SHALL accept repeatable --propose-with for octilinear proposals and for regenerating their accept/reject decisions. Confirmation MUST consume reviewed staged bytes without running a tool again. Changed declared tool inputs MUST invalidate the plan.

#### Scenario: Review external proposal bytes
- **GIVEN** a supported local adapter generates a scoped candidate
- **WHEN** its acceptance is reviewed and subsequently confirmed
- **THEN** the staged copper is written without rerunning the external process

### Requirement: Candidate adapter discovery
Capabilities router entries SHALL add external_candidates metadata, null for unsupported adapters, describing supported local scope and availability. Availability SHALL be null when tools were not queried.

#### Scenario: Discover without running tools
- **GIVEN** capabilities is requested with --no-tools
- **WHEN** candidate adapters are described
- **THEN** no process starts and their availability remains unknown

### Requirement: External candidate provenance
External candidate rows and their acceptance rows SHALL report tool router/version, tool-input and job fingerprints and an honest determinism declaration.

#### Scenario: Tool identity remains reviewable
- **GIVEN** an external candidate is proposed
- **WHEN** its facts are read
- **THEN** tool-byte and job fingerprints are visible and no deterministic-tool guarantee is invented

#### Scenario: Regenerate the explicit candidate limit
- **GIVEN** external proposals used an explicit --candidates limit for internal shapes
- **WHEN** their generated acceptance command is run
- **THEN** that limit is permitted and repeated, while external adapters add their own alternatives separately

## MODIFIED Requirements

### Requirement: Brief capabilities
`fenolite capabilities --brief` SHALL answer the first question of an agent in a reply whose size is bounded: what is installed here, what can it do, and where to read more. The default result of `capabilities` MUST stay as it is.
- With `--brief`, `result` MUST hold exactly the keys `fenolite_version`, `commands`, `targets`, `tools`, `routers`, `guide`, `starters` and `sends_data_offsite`.
- `commands` MUST list every command that is not hidden, sorted by name, each with exactly `name`, `summary` and `mutates`, `summary` being the command's help line.
- `targets` MUST hold exactly `build`, `kicad` and `default`: `build` is the sorted list of choices of `build --target` (`altium` and `kicad`), read from the command's description; `kicad` and `default` are the target majors and the default target of the `kicad` backend's entry in the default view. The brief view MUST NOT state an evidence level or the word `experimental` for a target: the status of each Altium write kind stays in the default view ("Backends in capabilities", "Experimental features in capabilities", "Evidence matrix in capabilities").
- `tools` and `sends_data_offsite` MUST equal the default view's.
- `routers` MUST list the registered routers sorted by name, each with exactly `name`, `available`, `reason` and `external_candidates`, the first two from `Router.available()`; with `--no-tools`, `available()` MUST NOT be called and both values MUST be `null`. `external_candidates` (change c0368) is `null` for a router without candidate support, else the router's candidate capability object.
- `guide` MUST list `guide.pages()` with exactly `topic`, `title` and `summary`, and `starters` MUST list `guide.starters()` with exactly `name` and `summary`.
- The JSON of the brief `result` with `--no-tools` MUST be under 300 bytes per listed command plus 3 500 bytes, and MUST hold none of the keys `backends`, `experimental`, `extras` and `matrix`; a test MUST check both.
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
- **THEN** it is under 300 bytes per listed command plus 3 500 bytes, and holds no `experimental` key

#### Scenario: Default view unchanged
- **WHEN** `uv run fenolite capabilities --json --no-tools` runs
- **THEN** `result` holds the keys it held before this requirement, with `backends`, `experimental` and `matrix` unchanged
