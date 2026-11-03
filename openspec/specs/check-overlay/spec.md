# check-overlay Specification

## Purpose
`fenolite view --check` places the findings of a `fenolite check` reply on the board or sheet shown, as markers in the colour of their severity, and lists every finding in a Messages panel grouped by rule with its stage's evidence (change c0188).
## Requirements
### Requirement: Findings on the board
`fenolite view BOARD --check FILE` SHALL draw a marker for each finding of the `check` reply that has a position, on its layer, and SHALL list every finding in a Messages panel grouped by rule.

#### Scenario: Two findings
- **GIVEN** an authored `check` reply with one clearance error at a point and one finding without a position
- **WHEN** `uv run pytest tests/unit/view/test_check_overlay.py` builds the overlay
- **THEN** one marker is drawn and the panel lists two findings

### Requirement: Edit conflicts on the board
`fenolite view BOARD --check FILE` SHALL also accept the reply of `fenolite build` or `fenolite sync --to-source`, and SHALL draw each `sync.conflict` of it as an error marker on the footprint whose `fenolite.path` is the path of the conflict's key, listing it in the Messages panel with its key, reason, base, code and CAD values; a conflict whose part has no footprint on the board shown MUST be listed without a marker.

#### Scenario: Conflict marked on its footprint
- **GIVEN** the reply of a blink build that exited 5 with one `sync.conflict` naming `R1#value`, saved as `reply.json`
- **WHEN** `fenolite view B/blink.kicad_pcb --check reply.json --export page.html` runs and `uv run pytest tests/unit/view/test_check_overlay.py -k conflict` reads the page
- **THEN** the page holds one error marker at `R1`'s position and a Messages entry with `R1#value`, `both-changed`, `330`, `470` and `4k7`

### Requirement: Conflict resolution from the viewer
The viewer MUST offer copyable `build --take … --dry-run` commands. With `--serve --edit` (`--allow-actions`), conflict Properties SHALL show base, code and CAD values and offer the allowed takes. A take MUST use the existing plan-review dialog as Pending review; confirmation MUST replay `--confirm --plan`, and receipt/undo MUST use the reviewed scope. Static pages MUST send no action request.

#### Scenario: Command lines offered
- **GIVEN** the same page
- **WHEN** the conflict's Messages entry is read
- **THEN** it holds the command lines with `--take code:R1#value` and `--take cad:R1#value`, and the page sends no request

#### Scenario: Workbench reviews a take
- **GIVEN** a served authored project and a bound `R1#value` conflict
- **WHEN** Take CAD is planned and confirmed
- **THEN** Properties shows all three values, the plan lists its inputs and writes, only the reviewed bytes are applied, and a receipt offers a reviewed undo

### Requirement: Bound conflict source execution
A take SHALL accept only a session finding index and an allowed side. The server MUST bind the script hash, selected board/output and available base/build records before source execution. Only a take MAY use its bound authoring root when that root contains the output. Review MUST show source context and all plan inputs/writes. Stale inputs, path escapes and unbound keys MUST be refused; other actions MUST retain their original root.

#### Scenario: Conflict source changed
- **GIVEN** a conflict loaded from a build reply
- **WHEN** its source script changes before planning, or an input changes after review
- **THEN** planning or confirmation refuses the stale context and writes nothing

### Requirement: Findings resolved by subject
`fenolite view --check FILE` SHALL resolve a finding that has an entry in the reply's `result.subjects` by its subjects first: a component or pad by its id or name in the scene's parts and pads, a net by its name, and SHALL fall back to the forms of `where` only for a finding without subjects or whose subjects are not in the scene. The Messages panel SHALL list each subject's name under its finding.

#### Scenario: A finding with an empty where
- **GIVEN** an authored `check` reply with one `circuit.rating-voltage` finding whose `where` is empty and whose subjects name the component `C1` and the net `V12`
- **WHEN** `uv run pytest tests/unit/view/test_check_overlay.py -k subjects` builds the overlay on the matching scene
- **THEN** the finding gets a box around `C1`, the panel lists `C1` and `V12` under it, and a reply without `result.subjects` resolves as before
