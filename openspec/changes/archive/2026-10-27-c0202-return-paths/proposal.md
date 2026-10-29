## Why

Item 3 of the consolidation list the maintainer ordered on 2026-10-26. A signal routed across a gap or a split
of its plane forces its return around the gap. The loop radiates and picks up noise: one of the commonest
causes of emissions and of noisy measurements on a mixed board. The agent guide teaches the rule
(`board-grounds`, "Return paths"), but no command checks it, and the copper graph and the segment
intersection of c0198 and c0199 make the check cheap.

## What Changes

- `fenolite.analysis.returns.analyze_returns`, for the nets that a pattern selects:
  - The parts of each track's centre line with no reference copper on a neighbouring copper layer are
    spans.
  - A span inside the track is a crossing of a gap (`analysis.return-split`, warning). A span at its end
    is an edge, listed only.
  - Each via is paired with the nearest via of a reference net; with a distance, a farther one is
    `analysis.return-via` (warning).
- `fenolite analyze` gains the opt-in kind `returns` with `--net GLOB` (shared with `length`),
  `--reference NET[,NET...]` and `--via-distance LENGTH`.
- `CutLine` of the crossing analysis becomes public and is shared.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `board-analyses`: ADDED "Return paths", "Returns kind in the analyze command" and "Return path codes".

## Non-goals

- The coupling screen of c0175's package 7, whose "share of length with its return plane under it" this
  analysis gives per net; the score stays there.
- Planes that are not stored fills (an unfilled zone); the board is filled first.
- Field solving: the check is geometric and says where, not how much.

## Evidence level required

`INFERRED` (`H-G-RETURN-PATH`), on an authored bench whose gap and edge are known by construction.

## Impact

- `src/fenolite/analysis/returns.py`, `codes.py`, `crossings.py`, `src/fenolite/cli/cmd_analyze.py`,
  `explain.toml`, tests, `docs/analyses.md`, `docs/cli-contract.md`, the guide's `board-grounds` page,
  `CHANGELOG.md`.
