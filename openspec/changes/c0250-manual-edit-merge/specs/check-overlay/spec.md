## ADDED Requirements

### Requirement: Edit conflicts on the board
`fenolite view BOARD --check FILE` SHALL also accept the reply of `fenolite build` or `fenolite sync --to-source`, and SHALL draw each `sync.conflict` of it as an error marker on the footprint whose `fenolite.path` is the path of the conflict's key, listing it in the Messages panel with its key, reason, base, code and CAD values; a conflict whose part has no footprint on the board shown MUST be listed without a marker.

#### Scenario: Conflict marked on its footprint
- **GIVEN** the reply of a blink build that exited 5 with one `sync.conflict` naming `R1#value`, saved as `reply.json`
- **WHEN** `fenolite view B/blink.kicad_pcb --check reply.json --export page.html` runs and `uv run pytest tests/unit/view/test_check_overlay.py -k conflict` reads the page
- **THEN** the page holds one error marker at `R1`'s position and a Messages entry with `R1#value`, `both-changed`, `330`, `470` and `4k7`

### Requirement: Conflict resolution from the viewer
The viewer SHALL NOT write anything for a conflict. It MUST offer the two `fenolite build … --take <side>:<key> --dry-run` command lines to copy; when c0245's workbench runs with `--serve --edit`, its actions "Take code" and "Take CAD" MUST run them and apply a plan only through its Pending panel (`--confirm --plan <plan_id>`).

#### Scenario: Command lines offered
- **GIVEN** the same page
- **WHEN** the conflict's Messages entry is read
- **THEN** it holds the command lines with `--take code:R1#value` and `--take cad:R1#value`, and the page sends no request
