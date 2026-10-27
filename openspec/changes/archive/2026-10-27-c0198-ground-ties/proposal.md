## Why

Package 2 of change c0175 ("Ground ties"), split into a change of its own as c0175's design allows and as the
maintainer chose on 2026-10-26. c0175 records the failure it answers: a ground tie test removed more copper
than the tie, and so tested another board. A tie between two areas of one ground (or two ground nets joined
by a net-tie part) is right only when it is the only joint; nothing in Fenolite proves that today. Two
neighbouring questions use the same graph: whether a sense net (a Kelvin connection) leaves its element
through copper of another net, and which islands of nets an isolator, a transformer or an earth part
separates.

## What Changes

- `fenolite.analysis.ties`:
  - `analyze_ties` proves each tie by removing exactly its copper, named by id: a part's pads (`--tie REF`)
    or tracks, arcs, vias and zones by model id, KiCad uuid or locator (`--tie-item ID[,ID...]`).
  - It reports the groups of pads left, whether the tie splits, and the shortest other path when it does
    not.
  - With two pad domains (`--domains A=GLOB,B=GLOB`) it names a pad joined to the other domain after the
    split.
  - `--sense NET[,NET...]` checks that a sense net's copper touches another net only through a net-tie
    part.
  - `isolation_islands` gives the islands of nets once the barrier parts are removed (`--kinds domains
    --barrier REF[,REF...]`). It reads no copper.
- `fenolite analyze` gains the opt-in kinds `ties` and `domains` and those options.
- Five issue codes: `analysis.tie-parallel`, `analysis.tie-extra` and `analysis.sense-shared` (errors);
  `analysis.tie-dangling` and `analysis.tie-unmatched` (warnings).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `board-analyses`: ADDED "Ground ties", "Sense nets and isolation islands", "Ties and domains kinds in the
  analyze command" and "Ties analysis codes".

## Non-goals

- The other packages of c0175, which stay there; c0175's MODIFIED "Analyze command" keeps its list of
  options for its own packages.
- `analysis.sense-entry` of c0175's draft (a sense net that reaches its pad from outside the pad's outline):
  no public source recorded here gives a measurable rule for it, so it is left out (design, decision 4).
- A simulated pour when the file holds no fill: c0175's "Practice checks" (package 7) defines it; until then
  an unfilled zone is named, not guessed.

## Evidence level required

`INFERRED`: graph reasoning on the board's own copper, proved on authored benches (`tests/_groundties.py`); no
tool confirms a tie.

## Impact

- `src/fenolite/analysis/ties.py`, `src/fenolite/analysis/codes.py`, `src/fenolite/cli/cmd_analyze.py`, their
  tests, `docs/analyses.md`, `docs/cli-contract.md`, the agent guide's generated command page, `CHANGELOG.md`.
- Size: about 2 design-days (c0175's estimate for the package).
