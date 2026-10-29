## ADDED Requirements

### Requirement: Writing actions are opt-in
A live server SHALL accept writing actions only when started with actions allowed; otherwise every action route MUST answer 403 and `GET /actions` MUST say why. The page SHALL show writing controls only when `GET /actions` reports them enabled, and an exported page MUST show none.

#### Scenario: Actions not allowed
- **GIVEN** a live server over a copy of `two_layer.kicad_pcb` started without actions
- **WHEN** `uv run pytest tests/unit/view/test_server.py -k actions_off` posts a guarded `silk` plan
- **THEN** the answer is 403, the runner was never called, and `GET /actions` reports `enabled` false with its reason

### Requirement: Plan review before a write
An action SHALL first run its command's dry run and report the plan: the files with their sizes and digests, the issues and the evidence. When the plan replaces the open board, the server SHALL compare the scene of the staged bytes with the current scene, and the page SHALL draw that comparison on the board. A plan with an error finding MUST NOT be confirmable.

#### Scenario: A designator plan previewed
- **GIVEN** a live server with actions allowed over a copy of `two_layer.kicad_pcb`
- **WHEN** `uv run pytest tests/unit/cli/test_view_actions.py -k silk_plan` plans `silk` with designators
- **THEN** the job holds a plan of one write of the board with its digests, the preview lists the moved designators, and the board file is unchanged

### Requirement: Confirm by plan
Confirm SHALL write only a plan that this server planned in this session for the same action and document, by running the command with `--confirm --plan ID`. Every write of the plan MUST lie under the project root. A target or input that changed since the review MUST give `FEN-4002`, and the page MUST offer a new review.

#### Scenario: The file changed after the review
- **GIVEN** a `silk` plan of a copy of `two_layer.kicad_pcb`, and the file then rewritten with one track less
- **WHEN** `uv run pytest tests/unit/cli/test_view_actions.py -k changed` confirms the plan
- **THEN** the job ends with exit 4 and `FEN-4002`, and the file keeps the rewritten bytes

### Requirement: Receipt and undo
A confirmed action SHALL return its receipt, which the page SHALL show before it reloads the document. Undo SHALL plan `restore` on a receipt of the session and write it only on Confirm; backups MUST always be kept.

#### Scenario: Write and undo
- **GIVEN** a live server with actions allowed over a copy of `two_layer.kicad_pcb`
- **WHEN** `uv run pytest tests/unit/cli/test_view_actions.py -k undo` plans and confirms `silk`, then plans and confirms the undo of its receipt
- **THEN** the first receipt names the board and its backup, and after the undo the board's SHA-256 equals the original

### Requirement: Allowed actions
An action SHALL be one of `fill`, `tidy`, `silk`, `testpoints`, `waive`, `move`, `shift`, `turn`, `export` and `bom`, built from its fixed template with typed options. A word, a path outside the project root, an unknown reference, a malformed length, a reason with a line break or `--no-backup` MUST be refused with 400, and no action MAY write an Altium document.

#### Scenario: Refused actions
- **WHEN** `uv run pytest tests/unit/view/test_actions.py` validates an `export` to `../out`, a `move` of an unknown reference, a `waive` whose reason holds a line break and a `silk` of an Altium board
- **THEN** each is refused with its reason, and `move` of `R1` by lengths in mm gives the words of `place --move`

### Requirement: Action request guard
Action routes SHALL apply the run request guard with the header `X-Fenolite-Action: 1` and SHALL require the session token that `GET /actions` returns to a guarded request; a request without them MUST be refused with 403. An action and a run MUST NOT run at the same time.

#### Scenario: A request without the token
- **GIVEN** a live server with actions allowed
- **WHEN** `uv run pytest tests/unit/view/test_server.py -k action_guard` posts a plan without the token, then with a wrong one, then while a run is in progress
- **THEN** the answers are 403, 403 and 409, and nothing was planned
