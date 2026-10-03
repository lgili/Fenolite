## ADDED Requirements

### Requirement: Observed board paths are inventoried
`tests/kicad/test_token_census.py::test_observed_paths` (markers `needs_kicad`, `needs_corpus`, `kicad_min_major(10)`) SHALL compare the head chains of boards that `kicad-cli` 10.0.6 writes with those of boards that 9.0 wrote, and SHALL fail when a chain that only 10.0 writes is neither an inventory row nor proved readable by 9.0.9.
- **Sets.** The 10.0-written set MUST be the `pcb upgrade --force` copies, made in memory on 10.0.6, of the 21 readable non-heavy demo boards and of the three third-party boards, plus every cached native board whose header maps to major 10. The 9.0-written set MUST be every cached native non-heavy demo board with header `20241229` and `generator_version "9.0"`.
- **Chains.** A chain is the list of heads from the root to a node, with numeric heads read as `#`, as `Inventory.match` reads them ("Path matching").
- **Suspects.** A chain of the 10.0-written set that occurs in no board of the 9.0-written set is a suspect. Each suspect MUST be accounted for in one of three ways: it matches a token row (`load_inventory().match(FileKind.BOARD, chain)` is not `None`); one of its ancestor chains matches a token row whose `since_major` is 10 or later, because the writer gates that parent for target 9 with its children; or it is named in the test's mapping `FLOOR_CHAINS`, each entry of which cites an inventory example whose committed fuzz results load on 9.0.9.
- **Pending.** Suspects of the first run that cannot get a row or an example within this change MAY be listed in the explicit mapping `PENDING_CHAINS`, each with the change that will resolve it. An entry that is no longer a suspect MUST fail the test, so the list cannot go stale. `H-K-TOK-CENSUS` MUST stay `INFERRED` while `PENDING_CHAINS` is not empty.
- **Record.** The counts (chains of each set, suspects, suspects matched by a row, suspects accounted for by an ancestor's row, floor chains, pending chains) MUST be written through `tests/_boards.py::census` and copied into `docs/evidence/kicad-board-read.md`, as counts and head names only.

#### Scenario: Census on 10.0.6
- **GIVEN** the `rt0` corpus cached and `kicad-cli` 10.0.6
- **WHEN** `uv run pytest tests/kicad/test_token_census.py -rA` runs with `FENOLITE_CENSUS_OUT` set
- **THEN** every suspect matches a token row, has an ancestor with a 10.0 row, or is in `FLOOR_CHAINS` or `PENDING_CHAINS`, and the counts are written to the census file

#### Scenario: Uninventoried chain detected
- **GIVEN** a synthetic 10.0-written tree holding the chain `kicad_pcb/fenolite_probe`, which no 9.0-written tree, inventory row or floor entry holds
- **WHEN** `uv run pytest tests/kicad/test_token_census.py -k suspects_detected` runs the census function on it
- **THEN** the function returns `kicad_pcb/fenolite_probe` as an unresolved suspect

#### Scenario: Skipped on KiCad 9
- **GIVEN** the `kicad-9` job with `kicad-cli` 9.0.9
- **WHEN** `uv run pytest tests/kicad/test_token_census.py` runs
- **THEN** `test_observed_paths` is skipped and nothing fails
