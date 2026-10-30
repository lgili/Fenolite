## MODIFIED Requirements

### Requirement: Critical route failures
A planned group that is not routed SHALL appear in the reply with one reason (`no-room`, `too-long`, `no-layer`, `near-switching`, `isolation`, `role-check`, `drc`, `pads`, `unconfirmed`) and one proposal (`confirm`, `allow-via`, `free-corridor`, `move-part`, `rip`, `raise-limit`, `power-copper`) with its command and a `render --region` command. An `unrouted` or `refused` entry MUST also hold `propose`, the command `route --propose --group NAME`. A group MUST NOT be skipped silently.

#### Scenario: A blocked pair is reported
- **GIVEN** the `open` variant of `bms` with a part added across the path between the shunt and the monitor
- **WHEN** `fenolite route <board> --router octilinear --roles critical --dry-run --json` runs
- **THEN** the Kelvin pair's entry has status `unrouted`, reason `no-room`, proposal `free-corridor` naming the part, a `render --region` command, `propose` naming its group, and one `route.role-unrouted`

## ADDED Requirements

### Requirement: Leftover opens of role copper are proposed
`fenolite.roles.proposals.subjects` SHALL give each open connection after phases 1 and 2 one subject: `fanout` (a pad apart from its net's zone on another layer, within reach), `join` (islands of a net with role copper, or a `roles.copper-blocked` edge), `role-net` (an open connection of an unconfirmed inferred role net), else `connection`; and each phase-2 group `unrouted` or `refused` one `group` subject. Proposals MUST NOT be written as copper without `--accept`.

#### Scenario: The leftovers of phase 1
- **GIVEN** the six role-copper variants built, their roles confirmed as the reference tests do, after `route --roles critical --confirm`
- **WHEN** `uv run pytest tests/unit/roles/test_proposal_reference.py -k leftovers` proposes on each
- **THEN** the buck's `C3-2` is a `fanout` subject (its connection ends at `J2-2`, a through-hole pad on the plane), the half-bridge's Kelvin-source pads apart from their source pours `join` subjects, the two open connections of the bms `FET_S` `role-net` subjects with the alternative `confirm`, each with a candidate that closes it without a new finding of warning or above

### Requirement: Role-net candidates are labelled
A candidate of a `role-net` subject SHALL use the net's class width and carry the fact `current: not-declared`, and its proposal MUST hold the alternative `confirm` with the commands `fenolite roles PATH --accept NET --dry-run` and `fenolite copper PATH --dry-run`.

#### Scenario: An inferred net between two switches
- **GIVEN** the bms role-copper variant with `FET_S` inferred and not confirmed
- **WHEN** `uv run pytest tests/unit/roles/test_proposals.py -k role_net` lists its subjects
- **THEN** each open connection of `FET_S` is a `role-net:FET_S:<a>~<b>` subject, each candidate has `current: not-declared`, and the `confirm` alternative names both commands

### Requirement: Proposals on the reference boards
After phases 1, 2 and 4 each role-copper reference variant SHALL have no open connection, the `good_roles` variants no role finding of warning or above, and the `bad_roles` variants exactly their designed routing findings, when the test locks per proposal that holds an open connection the first candidate in reply order that lowers `open` and brings no new copper-check or role finding of warning or above, and rejects each `group` proposal whole.

#### Scenario: Fully connected
- **WHEN** `uv run pytest tests/unit/roles/test_proposal_reference.py -k complete` runs the chain on the six variants
- **THEN** each has zero open connections and the listed role findings, and `--propose` on each result gives `route.proposal-none`

#### Scenario: KiCad finds no unconnected item
- **WHEN** `uv run pytest tests/kicad/roles/test_proposal_drc.py` runs KiCad's DRC on each accepted variant after a refill, in the jobs `kicad-9` and `kicad-10`
- **THEN** no `unconnected_items` remain and no violation type has more entries than after phase 2

#### Scenario: Good variants need nothing
- **WHEN** `fenolite route <good variant> --router octilinear --propose --json` runs on the three `good` variants
- **THEN** each reply holds no proposal and one `route.proposal-none`

### Requirement: Proposals on both backends
An accepted role-copper variant converted with `fenolite convert --to altium` SHALL read back with every accepted track and via at its position and width with `locked` true, and every corridor of an accepted group candidate as a pour keep-out region on its layer.

#### Scenario: Same accepted copper in Altium
- **WHEN** `uv run pytest tests/unit/roles/test_proposal_reference.py -k altium` converts the six accepted variants and reads them back
- **THEN** the accepted copper and its locks match the KiCad model to 1 µm
