# Tasks: c0485-altium-straight-arc-kept

- [x] 1.1 Carry the straight arcs in a conversion to KiCad (`straightarcs`, `to_kicad`), and write them in
  the Altium writer (`lower.KeptStraightArc`, `lower._copper`, `to_altium._carried_straight_arcs`), with
  unit tests.
  - Proof: `uv run --extra geo --extra dev pytest tests/unit/convert/test_altium_straight_arc_c0485.py -q -n 0`
- [x] 1.2 Maintainer board (private, codes and counts only): F2 and F5 write the source's 1 arc and 1508
  tracks, and F2-eq and F5-eq still exit 0.
  - Result 2026-11-11: source, F2 and F5 each hold 1508 tracks and 1 arc (before: 1509 and 0); F2-eq and
    F5-eq exit 0; F5's `convert.changed` no longer names the arc.
