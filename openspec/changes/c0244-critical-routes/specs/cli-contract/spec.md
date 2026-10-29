## ADDED Requirements

### Requirement: Route command role mode
`fenolite route` SHALL take `--roles critical`, `--group NAME` (repeatable) and `--roles-file FILE`. It MUST plan only the open connections of confirmed or declared role groups, and give the job to a router with feature `roles`, else exit 2 with `FEN-2001`. With `--roles`, `--nets`, `--escape` and `--pairs-as-nets` MUST be `FEN-2001`. Writes follow the mutation protocol.

#### Scenario: Wrong router
- **WHEN** `fenolite route <board> --router direct --roles critical --dry-run` runs
- **THEN** the exit code is 2, stderr carries `FEN-2001`, and the hint names `octilinear`

#### Scenario: No roles
- **GIVEN** a board with no stored or declared role
- **WHEN** `fenolite route <board> --router octilinear --roles critical --dry-run` runs
- **THEN** the exit code is 0, nothing is planned, and the issues hold one `route.role-none`

### Requirement: Role route result
In role mode `result.roles` SHALL hold one entry per planned group, sorted by tier and name, with `group`, `kind`, `status` (`routed`, `complete`, `kept`, `refused`, `unrouted`, `skipped`), `connections`, `findings_before`, `findings_after`, `copper` and `corridors`, plus `reason` and `proposal` (`kind`, `text`, `command`) when not routed. The verdict MUST count role connections only.

#### Scenario: The reply of an open buck
- **GIVEN** the `open` variant of `examples/roles/buck_shunt` with its groups confirmed
- **WHEN** `uv run pytest tests/unit/roles/test_critical_reference.py -k reply` runs `fenolite route <board> --router octilinear --roles critical --dry-run --json`
- **THEN** `result.roles` names the hot loop and the Kelvin pair as `routed` and both gate loops as `complete`, and no `route.unrouted` is given
