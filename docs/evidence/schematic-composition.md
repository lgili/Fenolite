# Schematic composition evidence

Composition remains `INFERRED`. The `blocks-v1` algorithm and all synthetic circuits were authored
for Fenolite. Its native encoding reuses the public-source facts already recorded in
`docs/formats/altium/schematic-ascii.md` (S-0002, S-0130, S-0131, S-0140); no new format fact or
third-party parser source was needed.

Measured by automated proofs: deterministic grouping and quarter-turn geometry; all symbol units;
fixed integer grids; collision/overflow and bounded search findings; safe local wiring and label
fallback; native ASCII/binary project-wide identity, pin assignment and connectivity readback;
reviewed transactional artifacts; saved native replay and changed-baseline refusal. The before/after
example is authored in `examples/schematic_blocks/`.

Unmeasured: native Altium GUI acceptance and editing quality, exact font metrics, and an independent
native electrical oracle. No author report is claimed. Shared preview geometry is an estimate:
reserved interface/template areas are shaded, text uses conservative boxes and power markers are
schematic approximations. Unsupported template occupancy refuses composition. Fixed template paper
is rounded down to the native 10 mil grid, by less than 0.254 mm, to keep electrical endpoints exact.

The maintainer can review the example `.SchDoc` files and report overlap, text readability,
orientations and native connectivity. That future report must name the Altium version and reviewed
artifacts before any evidence promotion.
