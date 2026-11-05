# Design: c0411

## Open points for task 1

1. **Frame.** A definition's rule area is in the footprint's frame, like its pads and graphics. An instance
   holds the placed form, as `FootprintInstance.graphics` does since c0126. Task 1.1 decides whether the
   instance's areas are footprint-local or in the board frame, after the convention `FootprintInstance` uses
   for graphics.
2. **Layers on the bottom side.** Placing on the bottom swaps `F.Cu` and `B.Cu` and maps inner layers by
   the board's stack. A footprint area that names every copper layer keeps naming every copper layer.
3. **Checks.** The copper, placement and keep-out checks iterate `Board.keepouts`. One helper gives the
   board-frame rule areas of a board, its own and its instances', so no check is changed twice.
4. **KiCad read.** A footprint `zone` with `keepout` is projected. A footprint zone without `keepout` (a
   copper zone of a footprint) stays opaque, as today.
5. **Proof.** The authored library and the expectations of c0410's oracle test are reused unchanged. The
   new test also compares Fenolite's `.kicad_mod` with KiCad's after `fp upgrade`.
