## ADDED Requirements

### Requirement: Tie removal by id
`fenolite.analysis.ties.analyze_ties(design, *, pads, ties)` SHALL prove whether named items are the only joint of their nets' copper.
- A tie MUST be a part (`Tie.of_part(REF)`, its pads) or copper items (`Tie.of_items(IDS)`: tracks, arcs, vias or zones by model id, native id or locator).
- Items MUST be removed by their ids alone, never because their copper lies near a tie or inside its box.
- The graph MUST join the copper items of the tie's nets that touch on a layer, as `touch_groups` does.

#### Scenario: Removal by area is not used
- **GIVEN** the authored board `ground()` of `tests/_groundties.py`, where the track `t2` of the power area ends inside the box of the tie `t1` without touching its copper
- **WHEN** `uv run pytest tests/unit/analysis/test_ties.py -k area` proves the tie `t1`
- **THEN** `t2` is not removed and `Q2-1` stays in the power group

### Requirement: Tie groups
`analyze_ties` SHALL give one `TieRow` per tie that names something on the board.
- The row MUST hold the removed items and `groups`: the sorted `REF-PIN` pads of each connected part that touches the tie after the removal, the groups sorted.
- `split` MUST be true with two or more groups.
- `zones` MUST be `filled`, `unfilled` (a zone of the tie's nets without fill, which also adds `analysis.input-missing`) or `none`.

#### Scenario: A single tie splits the net
- **GIVEN** the authored board `ground()` of `tests/_groundties.py`, whose `GND` copper is a power area and a control area joined only by the track `t1`
- **WHEN** `uv run pytest tests/unit/analysis/test_ties.py -k single` proves the tie `t1` with the domains `PWR=Q*` and `CTL=U*`
- **THEN** the row holds the two groups `Q1-1, Q2-1` and `U1-1`, `split` is true, and no issue is reported

### Requirement: Tie findings
`analyze_ties` SHALL report a tie that is not the only joint, or that names or joins nothing.
- One group MUST be `analysis.tie-parallel` (error), with the shortest other path between the tie's sides in the row's `path`.
- A tie that touches fewer than two items MUST be `analysis.tie-dangling` (warning), and a name that matches nothing `analysis.tie-unmatched` (warning).
#### Scenario: A parallel tie through a via
- **GIVEN** the board `ground(via=True)`: the board of "Removal by area is not used" with a via in each area and a `B.Cu` track between them
- **WHEN** `uv run pytest tests/unit/analysis/test_ties.py -k parallel` proves the tie `t1`
- **THEN** the row holds one group, and the issues hold one `analysis.tie-parallel` whose path runs fill, via, track, via, fill


### Requirement: Tie domains
`analyze_ties(..., domains=DOMAINS)` SHALL check that a split leaves each domain on its own side.
- `DOMAINS` MUST name two domains, each a list of `REF-PIN` patterns.
- After a split, a group that holds pads of both domains MUST be `analysis.tie-extra` (error), naming the stray pad of the domain with fewer pads in the group.

#### Scenario: A control pad in the power area
- **GIVEN** the board `ground(intruder=True)`, with the control pad `U2-1` inside the power area
- **WHEN** `uv run pytest tests/unit/analysis/test_ties.py -k extra` proves the tie `t1` with the domains `PWR=Q*` and `CTL=U*`
- **THEN** the row is split, its `extra` is `U2-1`, and one `analysis.tie-extra` names `U2-1`

### Requirement: Sense nets
`analyze_ties(..., sense=NETS)` SHALL check that the copper of each sense net touches another net only through a net-tie part.
- A node of a sense net that touches a node of another net MUST be `analysis.sense-shared` (error), naming both, unless the two are pads of one footprint in one net-tie group.
- A sense net without copper MUST be `analysis.tie-unmatched` (warning).

#### Scenario: A sense track that leaves from a pour
- **GIVEN** the authored board `sense()`, where `ISENSE_P` starts on the pour of `DC_BUS` beside the shunt pad
- **WHEN** `uv run pytest tests/unit/analysis/test_ties.py -k sense` checks the sense nets `ISENSE_P` and `ISENSE_N`
- **THEN** the issues hold one `analysis.sense-shared` naming the track and the fill, and `ISENSE_N`, which leaves through the net tie of the shunt, has none

### Requirement: Isolation islands
`fenolite.analysis.ties.isolation_islands(design, *, barriers)` SHALL report the islands of the nets of the circuit once the barrier parts are removed.
- Every part that is not a barrier MUST join the nets of its pins; nets without a pin are left out.
- Each island MUST hold its sorted nets and the barrier parts with a pin on it. It MUST read no copper.

#### Scenario: Islands across an isolator
- **GIVEN** the authored design `isolated()`, whose nets on the two sides of `U5` are joined only through `U5`
- **WHEN** `uv run pytest tests/unit/analysis/test_ties.py -k islands` runs with the barrier `U5`
- **THEN** the result holds two islands, `A1, A2` and `B1, B2`, each bounded by `U5`

### Requirement: Ties and domains kinds in the analyze command
`fenolite analyze` SHALL accept `ties` and `domains` in `--kinds` as kinds that are not in the default set.
- `ties` takes `--tie REF` (repeatable), `--tie-item ID[,ID...]` (one tie per option, repeatable), `--domains A=GLOB,B=GLOB` and `--sense NET[,NET...]` (repeatable), and needs a tie or a sense net.
- `domains` takes `--barrier REF[,REF...]` (repeatable) and needs it.
- `docs/cli-contract.md` MUST document the kinds and their options under `analyze`.

#### Scenario: Usage errors of the kinds
- **WHEN** `fenolite analyze <board> --kinds current --tie NT1` or `fenolite analyze <board> --kinds domains` runs
- **THEN** the exit code is 2 and stderr holds `FEN-2001`

### Requirement: Ties and domains results
With the kinds `ties` and `domains`, `fenolite analyze` SHALL return their rows and judge their findings.
- `result.ties`, `result.sense` and `result.domains` MUST hold the rows, and `result.summary` their counts; `result.inputs` gains the options of the kinds that ran.
- An option without its kind, a kind without its option, `--domains` without two names, or an empty name MUST be `FEN-2001` (exit 2). An error finding gives exit 5.

#### Scenario: Ties through the command
- **GIVEN** the boards of `tests/_groundties.py` written as KiCad boards in `tmp_path`
- **WHEN** `uv run pytest tests/unit/cli/test_analyze_ties.py` runs `fenolite analyze <board> --kinds ties --tie-item <uuid of t1> --json`, and the same with the parallel via
- **THEN** the first exits 0 with a split row and the folder unchanged, and the second exits 5 with `analysis.tie-parallel`

### Requirement: Ties analysis codes
The table of analysis issue codes SHALL hold `analysis.tie-parallel`, `analysis.tie-extra` and `analysis.sense-shared` with severity `error`, and `analysis.tie-dangling` and `analysis.tie-unmatched` with severity `warning`.

#### Scenario: Tie codes in the table
- **WHEN** `uv run pytest tests/unit/analysis/test_findings.py -k tie_codes` runs
- **THEN** each of the five codes has its one severity, and `issue("analysis.tie-parallel", ..., severity="warning")` raises `ValueError`
