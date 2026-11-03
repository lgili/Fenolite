## ADDED Requirements

### Requirement: Run read-only commands from the page
A live server given a runner SHALL accept `POST /run` with a command name, a document id of the tree and options, start one job and answer its id; `GET /run/<job>` SHALL report its state, progress and, when done, the reply; `GET /runs` SHALL say which commands and options the page may offer. A second run while one runs MUST be refused with 409 and the running job's id.

#### Scenario: A check run from the page
- **GIVEN** a live server over a copy of `two_layer.kicad_pcb` with the real runner
- **WHEN** `uv run pytest tests/unit/view/test_server.py -k run_check` posts `check` with stages `model.validate` and `copper.clearance` and polls the job
- **THEN** the job ends `done` with exit 0 or 5, and its review holds those two stages with their evidence

#### Scenario: One run at a time
- **GIVEN** a live server whose fake runner blocks
- **WHEN** a second run is posted
- **THEN** the answer is 409 and names the running job

### Requirement: Allowed run commands
A run SHALL be one of `check`, `analyze`, `ready` and `equivalent`, on the tree's file of the given document, with only the options of its allow-list checked by type and choice. A command line, a path, an unknown option, `check --exclude` or `--reason`, or a document outside the project MUST be refused with 400, and the command MUST run as `fenolite <command> --json` in a child process in the project folder.

#### Scenario: Refused requests
- **WHEN** `uv run pytest tests/unit/view/test_runs.py` validates `tidy`, `check` with `exclude`, `analyze` with an unknown kind, an option holding a path and a document id listed as not present
- **THEN** each is refused with its reason, and `check` with stage `drc.kicad` on the board is accepted

### Requirement: Run request guard
`POST /run` and `POST /run/<job>/cancel` SHALL be accepted only with this server's `Host`, a same-server `Origin` when one is sent, the header `X-Fenolite-Run: 1`, a JSON type and a body of at most 16 KiB; any other request MUST be refused with 403 or 413 and start nothing.

#### Scenario: A request from another origin
- **WHEN** `uv run pytest tests/unit/view/test_server.py -k run_guard` posts a run with another `Origin`, then without the header, then with a 17 KiB body
- **THEN** the answers are 403, 403 and 413, and the fake runner was never called

### Requirement: Run progress and cancel
A running job SHALL report its progress records and elapsed time, and `POST /run/<job>/cancel` SHALL stop its child process and end the job `cancelled`. A job that passes the run timeout MUST end `timeout`. The page MUST show the running command, its progress and a Cancel control, and say that a cancelled or timed-out run changed nothing.

#### Scenario: Cancel a blocked run
- **GIVEN** a live server whose fake runner blocks until cancelled
- **WHEN** `uv run pytest tests/unit/view/test_server.py -k run_cancel` posts a run, then cancels it
- **THEN** the job ends `cancelled`, the review of the document is unchanged, and a new run is accepted

### Requirement: Run results in the review
A finished `check` run SHALL replace, stage by stage, the stages of the same name in the document's session reply, and the page SHALL redraw the review cards and the Messages markers from it. `analyze` results SHALL appear as finding groups, and `ready` and `equivalent` findings SHALL be listed with Locate. Each stage MUST keep its own input hash, evidence and limits.

#### Scenario: Stages merged by name
- **GIVEN** a session reply with stages `model.validate` and `copper.clearance`, and a new reply with `copper.clearance` only, on another input hash
- **WHEN** `uv run pytest tests/unit/view/test_project_review.py -k merge` merges them
- **THEN** `copper.clearance` and its findings come from the new reply, `model.validate` stays, and its card is Limited for the changed revision

#### Scenario: A failed DRC card from a run
- **GIVEN** the exported page served with stubbed run routes whose reply holds one DRC error at a point
- **WHEN** `uv run pytest tests/visual/test_run.py -k drc` runs DRC from its card
- **THEN** the card reads Failed with the stage's evidence, and one marker is drawn at the point

### Requirement: Runs only on request in a live server
The page SHALL start a run only on a user's action, never on opening a document or on a save. Run controls SHALL appear only in a page served with a runner; an exported page and a page served with `--no-run` MUST show none and keep the recorded results.

#### Scenario: An exported page
- **GIVEN** the exported page of `two_layer.kicad_pcb`
- **WHEN** `uv run pytest tests/visual/test_run.py -k export` opens the project review
- **THEN** no Run control is shown, and no request to `/run` or `/runs` is made
