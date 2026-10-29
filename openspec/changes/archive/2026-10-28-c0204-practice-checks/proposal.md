## Why

Package 7 of change c0175 ("Practice checks"), split into a change of its own as c0175's design allows and as
the maintainer asked on 2026-10-28. A board can pass every design rule and still be a bad board: a pin left
open by a cut-out drawn after the last fill, a decoupling capacitor far from its pin along the copper, high
voltage under a metal can, a thermal relief too thin for its current, copper that floats, a sense line beside
a switching node. The practice pages of the agent guide teach these faults; no command measured them. The
copper graph of c0198, the segment intersection of c0199 and the reference test of c0202 make the checks
cheap, except for one input they all need: the copper of a zone whose stored fill is missing or stale.

## What Changes

- `fenolite.analysis.pour`: every zone layer in a copper state (`saved_fill`, `simulated`, `outline`), a
  stale-fill test, and a simulated pour on a raster of square cells for a zone whose fill is missing or stale.
- `fenolite.analysis.practice`: the kinds `connectivity` (the groups of pads of each net with every pour in its
  state), `dead` (fill islands joined to no pad, copper far from its pads), `decoupling` (the nearest
  capacitor of each power-input pin along copper, and the loop area), `bodies` (copper of a class under the
  plan view of selected parts) and `relief` (the width of the spokes of a thermal relief against the net's
  current).
- `fenolite.analysis.coupling`: the kind `coupling`, which ranks aggressor and victim pairs by
  `Σ ℓ / (1 + (s/h)²)`, gives their broadside overlap and each victim's reference coverage.
- The requirements file gains the optional tables `[[decoupling]]` and `[[body_copper]]`, without defaults.
- `fenolite analyze` gains the six opt-in kinds and the options `--pour-grid`, `--dead-distance`,
  `--aggressor` and `--victim`; six issue codes join the table.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `board-analyses`: ADDED "Copper states of the practice checks", "Simulated pour", "Connectivity kind",
  "Dead copper", "Decoupling distance", "Copper under part bodies", "Thermal relief width", "Coupling screen",
  "Practice requirement tables", "Practice kinds in the analyze command" and "Practice check codes".

## Non-goals

- The kinds `necks`, `loops` and `balance`, the tables `[[neck]]` and `[[loop]]`, and `--kinds power
  --split` of c0175's package 7: they are not among the six kinds of c0175's decision 7 and stay in c0175
  (requirement "Pour shape checks", tasks 5.5 to 5.7).
- An exact polygon pour: without the `geo` extra the core has no polygon union or difference, so the
  simulation is a raster (design, decision 2). It has no thermal spokes, no minimum width and no clearance
  around holes without copper.
- Walking a simulated pour for `decoupling`, and measuring the spokes of a simulated pour for `relief`: both
  read stored fills only and say so.
- Net classes of a KiCad board: they live in the project file, which `analyze` does not read.
- A requirement row for `coupling`: the score ranks pairs and is never judged.

## Evidence level required

`INFERRED` (`H-G-PRACTICE-POUR`, `H-G-PRACTICE-GROUPS`, `H-G-PRACTICE-DEAD`, `H-G-PRACTICE-DECOUPLING`,
`H-G-PRACTICE-BODIES`, `H-G-PRACTICE-RELIEF`, `H-G-PRACTICE-COUPLING`), on the authored benches of
`tests/_practicebench.py`, whose values are known by construction.

## Impact

- `src/fenolite/analysis/pour.py`, `practice.py`, `coupling.py`, `requirements.py`, `codes.py`,
  `src/fenolite/cli/cmd_analyze.py`, `explain.toml`, tests, `docs/analyses.md`, `docs/cli-contract.md`,
  `docs/hypotheses.md`, the guide's `board-practice` page and generated command page, `CHANGELOG.md`.
