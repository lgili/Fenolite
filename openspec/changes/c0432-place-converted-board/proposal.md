# c0432: place on a converted board

## Why

`place` cannot move anything on a board converted from Altium (`convert --to kicad`, then `place`; S-1910 to
S-1919):

- (a) Findings already on the board, on parts the command does not move, refuse the move as errors:
  `place.courtyard-overlap` between parts left where they were, `place.outside-outline` for parts in a
  board cut-out. `--force` writes, but the reply still fails on findings the move did not make.
- (b) A converted board keeps each part's lock, so every moved part is `place.locked`. `--force` moves it;
  the hint does not say why the part is locked.
- (c) `--strategy group --shift/--turn` moves only the copper that joins the group's pads to nothing else.
  A via in a moved pad, or a track from a moved pad to another part, stays (`place.copper-left`), and the
  copper check then finds the moved pad on its own old copper (`place.group-failed`).

## What Changes

- The legality check also judges the board before the moves. A finding of the layout after the moves that
  the board before has too, word for word, and that names no moved part, is `place.existing` (warning): it
  never refuses the write. Every other finding is judged as before.
- `place.locked`'s hint says that a converted or imported board keeps each part's lock, and that `--force`
  moves it.
- A group move drags the copper on its pads: a via that touches a moved pad and no pad of another part
  moves with the group, and the end of a track that touches a moved pad or a moved via moves with them
  (the track stretches). The copper the group joins to nothing else moves whole, as before.
- Tests on authored boards: the built blink project of the place tests, and the authored Altium
  `routed` sample converted to KiCad, flip included.

## Impact

- `src/fenolite/cli/cmd_place.py`, `src/fenolite/cli/place_group.py`, `src/fenolite/backends/kicad/replace.py`,
  `src/fenolite/placement/codes.py`; `explain.toml`, `docs/placement.md`, `docs/cli-contract.md`.
- One new warning code, `place.existing`. Exit codes unchanged.
