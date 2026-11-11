# c0488: through-hole pads of a four-layer board convert to Altium

## Why

Converting a 4-layer KiCad board to Altium (`fenolite convert --to altium`, and `build --target altium`,
which since c0480 goes through the same writer) can fail with one `convert.unexplained` error per
through-hole pad. The conversion's verification compares each pad's copper span
(`checks.equivalence.norm.copper_span`, level 3 `pad-copper` in `checks.equivalence.levels`). The source
pad spans `top,inner,bottom`; the pad read back from the written document spans `top,bottom` (or the
reverse). No report row explains the difference, so the command exits 5 and writes nothing. On the
maintainer's board (private; codes and counts only) every through-hole pad gave this error.

Two things are wrong:

- The span of a pad on every copper layer depends on the number of layers. A through-hole pad is on all
  copper layers on both sides; the comparison should say so, whatever the stack.
- The read-back pad has no inner layer. The Altium reader gives a Multi-Layer pad the layers of the
  document's copper chain (`adapter.pads`, `layers.copper_names`). So the written document's chain lacks
  the inner layers, or the reader does not see them. The candidate places are the writer's stack fallback
  to the two outer layers (`lower._stack` when `pcbrecords.stack_problem` refuses the stack, and
  `lower._built_stack` for a build), and the reader's chain (`adapter.layers.LayerMap`) for planes or
  carried signal ids (c0466 `_signal_ids`).

## What Changes

- A plated pad with a hole whose layers name every copper layer of its board has the copper span `all`,
  which equals `all` on the other side for any layer count.
- The document written from a board with inner copper layers holds them in its stack, and its Multi-Layer
  pads read back on all of them. A stack that the writer refuses keeps its existing `altium.not-lowered`
  row, which explains the loss.
- An authored 4-layer fixture (signal inner layers, and one plane) runs convert and build end to end.

## Impact

- `src/fenolite/checks/equivalence/norm.py` (`copper_span`, `span_text`), `checks/equivalence/levels.py`.
- `src/fenolite/backends/altium/lower.py` (`_stack`, `_built_stack`) and/or
  `src/fenolite/backends/altium/adapter/layers.py`, as task 1.1 finds.
- `docs/formats/altium/pcb-copper.md` if a format fact changes.
- New authored fixture under `tests/data/` with its `tests/data/MANIFEST.toml` entry.
