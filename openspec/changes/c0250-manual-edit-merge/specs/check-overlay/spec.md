## ADDED Requirements

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
