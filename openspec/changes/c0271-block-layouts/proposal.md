## Why

c0255 lets a block bring its layout with `b.layout(reuse="buck.kicad_pcb")`: a whole board file, fitted
part by part. That is enough for a project, not for a library. A board file is not tied to the block's
version, nothing notices when a parameter changes the block's parts (an extra part, another case), a board
file cannot be reviewed as text, and a block cannot be placed on the bottom side (c0255's non-goal and open
question 1). Section 3.5 of `docs/research/circuit-blocks.md` (2026-10-29) proposes a versioned layout
artefact: relative placement and copper in the block's own frame, refused when it no longer matches,
captured from a laid-out instance with the fit that c0210 and c0227 already have.

## What Changes

- **`fenolite.block-layout.v0`**: a TOML file beside the block (`layouts/<name>.toml`) holding the block id,
  the block version it was captured for, a `parts_digest` (local paths, footprints, pad numbers) and a
  `nets_digest` (each pad's port or local net), each part's position, rotation and side in the block frame,
  and tracks, arcs, vias and zones by **local pad and local net** (`port:OUT`, `net:FB`).
- **Applied as c0255's level 5.** `b.layout(reuse="layouts/x.toml")` and `inst.layout(reuse=...)` accept
  the file. Positions are composed with the block pose; copper nets are remapped by port and local net as
  c0255's "Nets mapped by port"; c0210's fit runs under that transform to check the pads.
- **Refusal, never a wrong layout.** Another block id is `reuse.layout-block` (error). A different
  `parts_digest` is `reuse.layout-stale` (warning): the layout is not applied and the parts fall to
  staging. A different `nets_digest` places the parts but copies no copper (`reuse.layout-nets`,
  warning). An older version with equal digests applies, with `reuse.layout-older` (info).
- **Mirrored poses.** `inst.place(..., side="bottom")` mirrors the whole block in its frame: every part
  flips to the other side with the footprint flip the model already uses, copper layers map to their
  mirror in the stack (c0210's rule).
- **`fenolite blocks capture BOARD --instance PATH [-o FILE]`** writes the layout of a laid-out instance
  under `--dry-run` / `--confirm --plan`: positions in the frame of the instance's pose, copper chosen by
  c0227's group rule, then a round trip through the same fit that must land every pad within 1 µm.
- **Precedence and edits.** A block layout is level 5 of c0255's precedence; locked `place()`, the board,
  `edits.toml` (c0250) and unlocked `place()` win per part. Its positions and copper are the *code side*
  of c0250's merge.

## Non-goals

- No search for the best pose, no optimiser; no partial layouts applied to a changed part set.
- No board-file reuse change: c0255's `.kicad_pcb` reuse stays as it is.
- No stored zone fill: zones are outlines, filled by `fenolite fill`.
- No editing of the block's Python by `capture`; the user adds `b.layout(reuse=...)`.

## Evidence level required

- Reading, digests, apply and capture: `INFERRED`, unit-tested (`H-G-BLOCK-LAYOUT`: applied pads within
  1 nm of the layout's transform, mirrored included).
- Built boards with block layouts: `KICAD-VERIFIED` read-back on targets 9 and 10; KiCad DRC of laid-out
  usage boards finds nothing (`H-K-BLOCK-LAYOUT-DRC`).

## Impact

- New: `src/fenolite/reuse/blocklayout.py`, `cli/cmd_blocks.py` verb `capture`, `docs/formats/fenolite/block-layout.md`,
  `tests/unit/reuse/test_blocklayout.py`, `tests/unit/cli/test_blocks_capture.py`, `tests/kicad/blocks/`.
- Changed: c0255's `placement/relative.py` (mirrored pose), `dsl/block.py` (`side=`), `cli/cmd_build.py`,
  `reuse/codes.py`, `explain.toml`, `docs/placement.md`, `docs/lens.md`, guide page `placement`, `CHANGELOG.md`.
- Depends on: c0255 (pose, level 5, nets by port), c0268 (block id and version), c0251; reuses c0210 and
  c0227; c0250 when it lands. c0270 tests layouts.
- Size: about 8 design-days (M).
