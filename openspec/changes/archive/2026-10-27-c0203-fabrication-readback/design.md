## Context

`fenolite export` runs `kicad-cli` on a copy of the board and holds the files as artefacts before it plans
their writes (`exports.plan.Artifact`). The mutation protocol writes nothing beside an error finding, so a
check that runs on the artefacts and reports errors keeps a bad set of files from being written.

## Decisions

1. **The subset, observed.** No public specification of Excellon is registered. The subset is the one
   `kicad-cli` writes with the options `fenolite export` passes, observed on a bench whose holes are known
   by construction and recorded as `KICAD-VERIFIED` facts. The Gerber facts rest on S-0125 and the same
   observation. Anything else is refused, never guessed.
2. **Contours by joining pieces.** KiCad writes each outline edge as its own `D02`/`D01` pair. Contours are
   found by joining pieces end to end. Each contour's box takes the ends of its pieces and the axis
   extremes on its arcs, and is matched to a ring of the board's boundary within the boundary's arc band
   plus 1 µm.
3. **Holes as a multiset.** Each hit or slot takes the first unmatched board hole of the same plating,
   diameter (1 µm) and ends (either order); what is left on either side is a finding. A slot's ends are the
   centres of its stadium, as `BoardPad.hole` holds them.
4. **Rows, not parts.** Every position row must match its footprint, but a footprint without a row is not a
   finding, since `exclude_from_pos_files` leaves parts out on purpose.
5. **In the export, before the plan.** `--readback` reads the board again through the backend for the pads
   and the boundary (`analysis.board_boundary`, which `exports` may not import; the command does).
   `READBACK_FILTER` is the test seam that stands for a writer defect.

## Risks / Trade-offs

- A preset that changes the drill format, the units or the Gerber precision cannot be read back; the
  finding says so, and the export without `--readback` still works.
- KiCad 9 may write numbers differently; the reader takes `20.` and `20.0`, and the `kicad-9` job checks it.

## Open Questions

None.
