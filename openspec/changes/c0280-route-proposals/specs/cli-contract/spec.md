## ADDED Requirements

### Requirement: Route proposal mode
`fenolite route` SHALL take the modes `--propose`, `--accept ID`/`--reject ID`, `--replay` and `--forget ID`, exclusive with each other (accept and reject may combine) and with `--roles`, `--rip`, `--escape`, `--order`, `--pairs-as-nets` and `--require-complete`, else `FEN-2001`. They MUST need a router with feature `propose`, else `FEN-2001`. `--propose` MUST write nothing and return no `plan_id`.

#### Scenario: Wrong router
- **WHEN** `fenolite route <board> --router direct --propose` runs
- **THEN** the exit code is 2, stderr carries `FEN-2001`, and the hint names `octilinear`

#### Scenario: Proposing writes nothing
- **GIVEN** the `bad_roles` variant of `examples/roles/buck_shunt` built in `tmp_path`, after `route --roles critical --confirm`
- **WHEN** `uv run pytest tests/unit/cli/test_route_propose.py -k writes_nothing` runs `fenolite route <board> --router octilinear --propose --json`
- **THEN** the exit code is 0, `result.proposals` is not empty, the reply holds no `plan_id`, and every file of the folder keeps its SHA-256

### Requirement: Proposal reply without a score
In propose mode `result` SHALL hold `mode`, `order` (`generation`), `open`, `proposals`, `rejected`, `locked` and `next`. Each proposal MUST hold `id`, `subject`, `kind`, `net`, `ends`, `region`, `candidates`, `reason` and `alternatives`; each candidate `id`, `source`, `relaxed`, `items`, `geometry`, `facts` and `rejected`. No proposal or candidate MAY hold `score`, `rank`, `best`, `recommended` or `cost`.

#### Scenario: Closed keys
- **WHEN** `uv run pytest tests/unit/cli/test_route_propose.py -k keys` proposes on the three `bad_roles` variants
- **THEN** every proposal and candidate has exactly the listed keys, and proposals are sorted by kind (`fanout`, `join`, `role-net`, `group`, `connection`) then subject

### Requirement: Candidate facts
Each candidate's `facts` SHALL hold `closes`, `open` (`before`, `after`), `copper_check` (`before`, `after`, `new`), `vias`, `length`, `layers`, `bends`, `conflicts`, `fill` and `not_evaluated`, and when measured `roles` (`before`, `after`, `new`, `cleared`), `drc` and `loop`. A fact not measured MUST be named in `not_evaluated` with a reason of the closed list `no-gate`, `no-role-loop`, `outside-role-reach`, `no-kicad-cli`, `budget`, `external-trial-failed`.

#### Scenario: Facts of a fan-out
- **GIVEN** the role-copper buck variant that holds the open pad `C3-2`, after phase 2
- **WHEN** `uv run pytest tests/unit/cli/test_route_propose.py -k fanout_facts` proposes without `--gate drc`
- **THEN** the `fanout:GND:C3-2` proposal has a candidate with one via, `open.after` one below `open.before`, no `new` copper-check finding, and `drc` named in `not_evaluated` with `no-gate`

### Requirement: Proposals without a candidate
A subject without a candidate SHALL be listed with `candidates` empty, one reason of `no-room`, `no-layer`, `too-long`, `near-switching`, `isolation`, `pads`, `all-rejected`, `budget`, and alternatives of `free-corridor`, `move-part`, `allow-via`, `raise-limit`, `power-copper`, `confirm`, `external-router`, `edit-script`, each with a command and a `render --region` command, and one `route.proposal-open`. No subject MAY be left out silently.

#### Scenario: A blocked connection
- **GIVEN** an authored bench whose connection is walled in by another net's copper on every layer
- **WHEN** `uv run pytest tests/unit/cli/test_route_propose.py -k blocked` proposes
- **THEN** the proposal has no candidate, reason `no-room`, the alternative `free-corridor` naming the wall, a `render --region` command, and the issues hold one `route.proposal-open`

### Requirement: KiCad DRC of candidates
With `--gate drc`, propose mode SHALL pack candidates, in reply order, into batches without two candidates of one subject or two that conflict, judge each batch once through `api.trial(..., gate=True)` with each candidate's items as one `together` set, and give each candidate the new violations naming its items as `drc.new` with `KICAD-VERIFIED` evidence. Without `kicad-cli` it MUST exit 6.

#### Scenario: Batches of candidates
- **GIVEN** a stand-in gate that reports a clearance violation on the items of one candidate
- **WHEN** `uv run pytest tests/unit/cli/test_route_propose.py -k drc_batches` proposes with `--gate drc` on a bench of two subjects with three candidates each
- **THEN** the gate runs three times, only that candidate has a `drc.new` entry, and the others have `drc.new` empty

### Requirement: Accept and reject through a reviewed plan
`--accept ID` SHALL recompute the candidates of the ids' subjects and plan, in one plan, the board with each candidate's items `locked` (group candidates with c0244's corridors) and the decision record; `--reject ID [--reason TEXT]` plans the record only. An unknown id MUST give `route.proposal-unknown` and two candidates of one subject or clashing copper `route.proposal-conflict` (errors, no write).

#### Scenario: Accept, then confirm
- **GIVEN** the buck role-copper variant and the id C of a candidate of `fanout:GND:C3-2`
- **WHEN** `uv run pytest tests/unit/cli/test_route_propose.py -k accept` runs `--accept C --dry-run`, then `--confirm --plan <plan_id>`
- **THEN** the dry run writes nothing; the confirm writes the board with a locked track and via and the record holding C, both in `receipt`

#### Scenario: Unknown and conflicting ids
- **WHEN** the same test runs `--accept c-0000000000000000 --dry-run`, then `--accept` with two candidates of one subject
- **THEN** both exit 5 with `FEN-5001`, the first with `route.proposal-unknown` naming the id, the second with `route.proposal-conflict`, and nothing is planned

#### Scenario: A rejected candidate stays out
- **GIVEN** a candidate R rejected with `--reject R --reason "crosses the gate loop" --confirm`
- **WHEN** `--propose` runs, then `--propose --show-rejected`
- **THEN** the first lists no R and holds one `route.proposal-rejected`, the second lists R with `rejected` true

### Requirement: Route decision record
Accepted and rejected decisions SHALL be kept in `fenolite.route-decisions.v0`, canonical JSON with no clock, at `.fenolite/route-decisions.json` for a built project and `<board stem>.route-decisions.json` beside any other board: `locked` entries (candidate, proposal, subject, net, ends, items, corridors, relaxed, plan) and `rejected` entries (id, subject, reason), sorted. A malformed record MUST be `FEN-3004`.

#### Scenario: A stable record
- **WHEN** `uv run pytest tests/unit/routing/test_decisions.py` writes a record, reads it and writes it again, and reads a record with an unknown key
- **THEN** the bytes are equal, and the second read raises the error that `route` maps to `FEN-3004`

### Requirement: Replay and forget of decisions
`--replay` SHALL plan the items of each locked entry missing from the board when its ends still land in copper of its net and the items pass the copper check; otherwise `route.proposal-stale` with `moved`, `blocked` or `net-gone`. `--forget ID` MUST plan removing the entry and, for a locked one, its items and corridors. A board holding every entry MUST plan no write.

#### Scenario: Replay on a fresh build
- **GIVEN** the accepted buck variant's record copied beside a fresh build of the same script into another folder
- **WHEN** `uv run pytest tests/unit/cli/test_route_propose.py -k replay` runs `--replay --confirm` twice
- **THEN** the first writes the accepted items with their ids, the board equals the accepted one byte for byte, and the second plans no write

### Requirement: View command shows route proposals
`fenolite view` SHALL take `--proposals run|FILE`: `run` runs `route BOARD --router octilinear --propose` read-only for each KiCad board shown, `FILE` reads a saved reply. `result.proposals` MUST count proposals and candidates, and the evidence MUST be the lower of the scene's and the reply's. A file that is not a propose reply MUST be `FEN-3004`; `run` on an Altium document `FEN-2001`.

#### Scenario: Proposals joined to a view
- **WHEN** `uv run pytest tests/unit/cli/test_view_cmd.py -k proposals` runs `fenolite view <buck role-copper board> --proposals run --export page.html --confirm --json`, then with a `check` reply as `--proposals`
- **THEN** the first writes a page whose scene holds `proposals` and counts them in `result.proposals`, and the second exits 3 with `FEN-3004`
