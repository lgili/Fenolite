## ADDED Requirements

### Requirement: Role data on a board
`fenolite.view.roles.overlay(reply, scene)` SHALL turn a `roles --check` reply into `scene.roles` (`fenolite.view_roles.v0`): the reply's role rows unchanged with their state and net index, the groups with their pad points and loop measures, the role findings placed on the scene, and counts. A value the reply does not hold MUST be left out.

#### Scenario: The bad buck joined to its scene
- **GIVEN** the `bad` variant of `buck_shunt` built in `tmp_path`
- **WHEN** `uv run pytest tests/unit/view/test_roles.py -k joined` joins its `roles --check` reply to its scene
- **THEN** every role row equals the reply's, `hot_SW` has six points and its area, and `roles.kelvin-outer` is placed at pad `R12-1`

### Requirement: Net roles panel
A board with role data SHALL show a Net roles section in the side bar: a legend with the colour, glyph, name and count of each role kind, a row per role net with glyph, net, kind, current, confidence and state, and a row per group. A net row MUST highlight its net; a group row MUST frame its pads.

#### Scenario: The panel of the bad buck
- **WHEN** `uv run pytest tests/visual/test_roles.py -k panel` opens the `bad` buck exported with `--roles run`
- **THEN** the legend lists the kinds of the reply with their counts, `SW` reads `switch_node`, and a click on `hot_SW` frames its pads

### Requirement: Role overlays
The Layers panel SHALL offer, for a board with role data, toggles for role colours (role copper tinted by role, `signal` untinted), loops (hot and gate loops hatched through their pads with their area) and Kelvin pairs (dashed sense lines). Colour MUST NOT be the only cue: each role has a glyph and each overlay its own hatch or dash.

#### Scenario: Overlays drawn and hidden
- **WHEN** `uv run pytest tests/visual/test_roles.py -k overlays` screenshots the `bad` buck, then turns each toggle off
- **THEN** the loops, sense lines and tint are drawn first and absent after, and the screenshot matches its reference

### Requirement: Role findings in the viewer
The Net roles section SHALL list the role findings by code with a marker on the board, and a selected finding SHALL open in the inspector. `check_overlay` MUST give `roles.*` codes the stage `roles.rules` and place a `where` that names a group or `group:pad` when the scene has role data.

#### Scenario: A Kelvin finding located
- **WHEN** `uv run pytest tests/unit/view/test_check_overlay.py -k roles` places a `check` reply with `roles.kelvin-outer` at `kelvin_R12:R12-1` and `roles.loop-area` at `hot_SW` on a scene, with those groups as aliases
- **THEN** both have stage `roles.rules`, the first is at the centre of `R12-1` and the second boxes the loop's pads

### Requirement: Role section of the inspector
The inspector model of a board net with a role SHALL hold, after its Net section, a Role section with the kind, state, rule, confidence, evidence pads, current, working voltage, sensitivity and the groups holding the net, leaving out what the reply does not hold.

#### Scenario: The role of a gate net
- **WHEN** `uv run pytest tests/unit/view/test_page.py -k role_section` builds the Role section of an inferred gate row under Node
- **THEN** it lists kind `gate`, state `inferred`, rule `GD-1`, its two pads and its gate loop, and no current row

### Requirement: Roles from a served page
A live server SHALL accept the run `roles` (no option) as `fenolite roles --check` on the board, and with `--allow-actions` the action `roles` with `nets` and `groups` that the session's role data shows as inferred, planned as `roles --accept … --accept-group …` on the board. Any other name MUST be refused with 400.

#### Scenario: Confirm a role from the page
- **GIVEN** a live server with `--allow-actions` over a copy of the `bad` buck and its role data
- **WHEN** `uv run pytest tests/unit/view/test_actions.py -k roles` plans `roles` with net `SW`, then with net `NOPE`
- **THEN** the first gives `roles --accept=SW -- <board>`, and the second is refused naming `NOPE`
