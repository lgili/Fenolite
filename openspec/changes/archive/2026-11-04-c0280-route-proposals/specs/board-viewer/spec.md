## ADDED Requirements

### Requirement: Route proposals on a board
`fenolite.view.proposals.overlay(reply, scene)` SHALL turn a `route --propose` reply into `scene.proposals` (`fenolite.view_proposals.v0`): per proposal its id, kind, net, subject, box, reason and alternatives; per candidate its id, source, polylines and via points per layer in scene units and its facts unchanged; the locked decisions as `locked` entries. A value the reply does not hold MUST be left out, and no score MAY be added.

#### Scenario: The buck's proposals joined to its scene
- **GIVEN** the buck role-copper variant after phase 2 and its `route --propose` reply
- **WHEN** `uv run pytest tests/unit/view/test_proposals.py -k joined` joins the reply to the scene
- **THEN** the `fanout:GND:C3-2` proposal is boxed around `C3-2`, each candidate's via lies at its reply position in scene units, every facts object equals the reply's, and no key named `score`, `rank` or `recommended` exists

### Requirement: Accept and reject from a served page
A live server with `--allow-actions` SHALL accept the run `proposals` (no option) and the actions `route-accept` (`candidates`: candidate ids of the session's proposal data) and `route-reject` (`candidates`: candidate or proposal ids, `reason`), planned as `route PATH --router octilinear --accept …` and `--reject … --reason …` through c0303's plan, confirm and undo. Any other id MUST be refused with 400.

#### Scenario: Accept a candidate from the page
- **GIVEN** a live server with `--allow-actions` over a copy of the buck role-copper variant and its proposal data
- **WHEN** `uv run pytest tests/unit/view/test_actions.py -k route_accept` plans `route-accept` with a candidate id of the data, then with `c-0000000000000000`
- **THEN** the first gives the words `route --router octilinear --accept=<id> -- <board>` and a plan, and the second is refused with 400 naming the id
