## ADDED Requirements

### Requirement: Roles payload
`fenolite view` SHALL run `fenolite roles BOARD --check` in process and read-only, and `fenolite.view.roles.payload(reply, *, document, sha256, locked)` SHALL turn the reply into `fenolite.view_roles.v0`: its roles with their state, groups, classes, measures, limits and findings unchanged, the code explanations and the locked copper. The page MUST join it to the scene: net to copper, group to pad polygon, finding to place.

#### Scenario: The numbers are the command's
- **GIVEN** the `bad` variant of `buck_shunt` built in `tmp_path`
- **WHEN** `uv run pytest tests/unit/view/test_roles_payload.py` exports the page with `--workspace roles` and runs `fenolite roles <board> --check --json`
- **THEN** every role, group, measure, limit and finding of the embedded payload equals the reply's, and the limits name their origin and source

### Requirement: Net Roles workspace
`fenolite view --workspace roles`, or Window ▸ Workspace ▸ Net Roles, SHALL open a board with the Net Roles panel (tabs Nets, Groups, Classes), the Layers panel with its overlays, the Properties panel (tabs Net, Role, Measures), the Messages panel of the `roles.rules` findings, and a toolbar with the Roles view and Net drop-downs. A document that is not a board MUST be `FEN-2001`.

#### Scenario: The workspace of the bad buck
- **WHEN** `uv run pytest tests/visual/test_roles_workspace.py -k panels` opens the `bad` buck board with `--workspace roles`
- **THEN** each net has a row with its glyph, role, confidence and state, the three groups are listed, and Messages lists the reply's `roles.*` findings

### Requirement: Role rows and properties
A role row SHALL show colour, glyph, net, role with its current, confidence and state (confirmed, declared, inferred, rejected). Properties SHALL show:
- the role's kind, origin and rule, evidence pads, confidence, confirmation, current and working voltage;
- each measure with its analysis and copper state;
- each limit with its source, default or override.

#### Scenario: The switch node explained
- **WHEN** `uv run pytest tests/visual/test_roles_workspace.py -k properties` selects the inferred gate net `GH`, then the hot loop `hot_SW` of the switch node
- **THEN** Properties shows the rule id and pads of `GH`'s role, each measure of `hot_SW` names its analysis, and its loop-ratio limit names its profile default and hypothesis

### Requirement: Role overlays
The Layers panel SHALL offer the overlays Loop areas (hatched loop and bound with area and ratio), Measures (dimension lines on the copper), Corridors (rule areas whose name has the settled corridor prefix), Locked copper and Role copper, each with visibility. A highlighted net or group MUST dim the rest of the board, with its measures drawn on its copper.

#### Scenario: Hot loop on the copper
- **WHEN** `uv run pytest tests/visual -k roles_workspace` renders the `bad` buck with `hot_SW` selected
- **THEN** the screenshot matches its reference within 0.1 %, showing the hatched loop, its area and ratio label, and the rest dimmed

### Requirement: Role writes from the viewer
With `--serve --edit` only, the workspace SHALL confirm, set, reject and forget roles and groups and set currents by running `fenolite roles` with `--dry-run`, showing the plan in a non-modal Pending panel, and writing only on Apply with `--confirm --plan <plan_id>`. The server MUST refuse a confirm for a plan it did not stage, and MUST require the review header.

#### Scenario: Confirm a role from the page
- **GIVEN** a server with `--edit` over a copy of the `bad` buck in `tmp_path`
- **WHEN** `uv run pytest tests/unit/view/test_role_writes.py -k confirm` posts an accept of `SW`, checks the files, then applies the plan
- **THEN** the dry run writes nothing, Apply writes only `<stem>.roles.json`, and the receipt with its SHA-256 is logged in Messages

#### Scenario: Read-only without edit
- **WHEN** the workspace is served without `--edit`, or exported
- **THEN** no action posts to the server, each action offers its `fenolite roles … --dry-run --json` command to copy, and `/roles/plan` answers 403

### Requirement: Undo of viewer writes
Every write the viewer makes SHALL push an undo entry with its exact inverse, computed from the dry-run reply. Ctrl+Z SHALL stage the inverse plan and apply it at once only when the target's SHA-256 equals the receipt's; otherwise it MUST stop in Pending. Redo SHALL mirror undo.

#### Scenario: Undo restores the bytes
- **WHEN** `uv run pytest tests/unit/view/test_role_writes.py -k undo` applies each of the nine write kinds and undoes it
- **THEN** after each undo the role document's bytes equal those before the write; when the write created the file, it holds the canonical empty role set

#### Scenario: Changed file stops undo
- **WHEN** the role document is changed by a command line after a viewer write and Ctrl+Z is pressed
- **THEN** the inverse plan waits in Pending and nothing is written

### Requirement: Router phase status
The workspace SHALL list the router phases in run order 0, 2, 1, 4, 3, each with a state: not run, done, partial n of m, k findings, failed, or not available. Phase 0 comes from the live roles check. Phases 2 and 1 come from replies given with `--report`, bound to the board's SHA-256. A reply for other bytes MUST read Limited.

#### Scenario: Phase 0 only
- **WHEN** `uv run pytest tests/visual/test_roles_workspace.py -k phases` opens the `bad` buck with no report
- **THEN** phase 0 shows its findings count and phases 2, 1, 4 and 3 read not run or not available

### Requirement: Phase results on the canvas
When c0243 or c0244 replies or copper are present, the canvas SHALL draw corridors hatched with their group, locked role copper with a lock glyph, role copper tinted by role, and proposed critical routes dashed with their reason. A proposal SHALL be applied only through its own command under the flow of "Role writes from the viewer", and only when an exact inverse exists.

#### Scenario: Corridors and locks
- **GIVEN** a board holding a rule area with the corridor prefix and a locked track of a role net
- **WHEN** `uv run pytest tests/unit/view/test_roles_payload.py -k corridor` builds the payload
- **THEN** the corridor is listed with its group and layers, and the track is marked locked
