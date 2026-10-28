## Why

The rest of package 7 of change c0175 ("Practice checks"), as c0175's design allows: c0204 took the six
kinds of c0175's decision 7 and left the kinds `necks`, `loops` and `balance`, the tables `[[neck]]` and
`[[loop]]` and `--kinds power --split` in c0175, under the requirement "Pour shape checks" (its tasks 5.5
except `relief`, 5.6 and 5.7). The guide page `board-power` tells the agent to find the necks of a pour, to
keep switching loops small and to share the current of parallel paths; no command measured any of them.
c0204's raster pour (`analysis/pour.py`) gives the copper of every zone in a stated state, and c0115's power
paths give an interval of the resistance of a path but no share of its current.

## What Changes

- `fenolite.analysis.shapes`: the kinds `necks` (places where a pour narrows below the width of a `[[neck]]`
  row: necks between wider copper, long thin tips, slivers), `loops` (the area of the path through the pads
  of a `[[loop]]` row, along copper where the pads share a net, and its change against a baseline board)
  and `balance` (the copper joined to each pad of a two-pad SMD part near the pad, for tombstoning).
- `fenolite.analysis.split`: a resistive solve on a raster of a power path's copper, giving the share of the
  current of each track, arc, fill and via, and the resistance of the path, bracketed by the interval of
  `power` on the same board.
- The requirements file gains the optional tables `[[neck]]` and `[[loop]]`, without defaults.
- `fenolite analyze` gains the three opt-in kinds and the options `--split` (with `power`) and
  `--loop-baseline FILE` (with `loops`); `--pour-grid` serves them too. Two issue codes join the table.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `board-analyses`: ADDED "Neck kind", "Tips and slivers", "Loop kind", "Balance kind", "Current split",
  "Pour shape tables", "Pour shape kinds in the analyze command" and "Pour shape codes".

## Non-goals

- A polygon offset of the copper: without the `geo` extra the core has none, so widths are measured on the
  raster of c0204 (design, decision 1), to within one cell.
- Judging the share of the current: `--split` reports each element's share and current, and does not turn
  an `analysis.path-undecided` of `power` into a finding. The solve is a raster estimate, not a field
  simulation of the board.
- A requirement row for `balance`: the copper of the two pads is reported, never judged.
- Walking a simulated pour for `loops`: as for `decoupling` (c0204), only stored fills are walked.

## Evidence level required

`INFERRED` (`H-G-SHAPE-NECK`, `H-G-SHAPE-LOOP`, `H-G-SHAPE-BALANCE`, `H-G-POWER-SPLIT`), on the authored
benches of `tests/_shapebench.py` and `tests/_power.py`, whose values are known by construction.

## Impact

- `src/fenolite/analysis/shapes.py`, `split.py`, `practice.py` (a path along copper), `requirements.py`,
  `codes.py`, `src/fenolite/cli/cmd_analyze.py`, `explain.toml`, tests, `docs/analyses.md`,
  `docs/cli-contract.md`, `docs/hypotheses.md`, `docs/evidence/matrix.md`, the guide's `board-power` page
  and generated command page, `CHANGELOG.md`.
