# The length of a net in KiCad

`fenolite.backends.kicad.lengths` computes the length of a net as KiCad's DRC counts it, for the rules
`length` and `skew`. This page lists the KiCad facts that module relies on, in Fenolite's own words.
Sources are listed in `docs/evidence/sources.md`: every fact here was measured with `kicad-cli`
(S-0020 is 10.0.6, S-0029 the pinned 9.0.9 image). The user guide is `docs/analyses.md`, "Length"; the
printed values are in `docs/evidence/length.md`.

KiCad prints the length of a net nowhere but in a DRC violation: `pcb export stats` holds none. A
measurement therefore gives each net a rule `(constraint length (max X))` and reads whether KiCad reports
it: with `X` 1 µm below the length it must, with `X` 1 µm above it must not.

## Facts

| fact | source | label | hypothesis |
|---|---|---|---|
| The DRC length of a net is the sum of the centre-line lengths of all its tracks and arcs, stubs and dangling copper included; a track counts from its end inside a pad, not from the pad edge | S-0020, S-0029 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-NETLEN-TOTAL |
| Each pad of the net adds its `(die_length X)`, in millimetres | S-0020, S-0029 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-NETLEN-TOTAL |
| A through-hole pad adds no height, also when the net changes layer inside it | S-0020, S-0029 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-NETLEN-TOTAL |
| A stored zone fill is not copper a via joins: a via whose only inner copper is a fill of its net adds no height | S-0020, S-0029 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-NETLEN-TOTAL |
| With `board.design_settings.rules.use_height_for_length_calcs` set to `false` in the project file no via adds a height; without a project file, with `{}` and with the key absent, heights count | S-0020, S-0029 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-NETLEN-TOTAL |
| On 10.0.6 the depth of the first copper layer is 0, that of the last the sum of every copper and dielectric thickness, and that of an inner layer the thickness above it plus half its own; masks do not count | S-0020 | KICAD-VERIFIED (10.0.x) | H-K-NETLEN-VIA10 |
| On 10.0.6 a via adds the depth difference between the outermost two copper layers on which a track, an arc or a pad of its net touches it, and nothing with fewer than two; a blind via and a through via between the same two layers add the same | S-0020 | KICAD-VERIFIED (10.0.x) | H-K-NETLEN-VIA10 |
| On 9.0.9 the depth of every copper layer is the thickness above it plus half its own, and a via adds the depth difference between its own two end layers when its net touches it on both, else nothing: a through via between `F.Cu` and an inner layer adds 0 | S-0029 | KICAD-VERIFIED (9.0.x) | H-K-NETLEN-VIA9 |
| A board file without a stack-up node is counted on copper layers of 35 µm and dielectrics that share equally the board thickness of `general` less 20 µm and the copper: 1.51 mm for two layers, 0.48 mm each for four, 0.274 mm for six and 0.1857 mm for eight, at 1.6 mm | S-0020, S-0029 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-NETLEN-STACKUP |
| On 10.0.6 a stack-up node without its silkscreen and paste rows, which KiCad's job file ignores (`H-K-STACKUP-COMPLETE`), is still counted for via heights with its own thicknesses | S-0020 | KICAD-VERIFIED (10.0.x) | H-K-NETLEN-VIA10 |
| A `length` constraint judges `min` and `max` and not `opt`; a net with pads and no copper is judged at length 0 | S-0020, S-0029 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-NETLEN-RULES |
| A `skew` constraint groups the nets its condition selects, each differential pair apart with `(within_diff_pairs)`; the skew of a net is its length less the longest length of its group, and a net is reported when the magnitude exceeds `max`; the longest net is not reported | S-0020, S-0029 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-NETLEN-RULES |
| A violation of either kind names one track or pad of the net and prints the length as `actual X mm` with four decimals; a skew violation also names the net of the longest length | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-NETLEN-RULES |

A row is `KICAD-VERIFIED` for the major whose canary ran on this branch (10.0.6, 2026-10-08). The rows
that name both majors were measured on both on 2026-10-05, on the branch of the review; their canaries ran
on 10.0.6 only since, so they stay `INFERRED` until the `kicad-9` job has run them (`docs/hypotheses.md`).

## Fenolite choices

These are decisions of the code, not facts about KiCad.

- The facts name the major they follow (`LengthFacts.major`): the argument, else the major of the project
  file, else that of the board file, else the default target.
- "Touches" is exact: a track, an arc or a pad copper entry joins a via on a layer when it shares a point
  with the via's disc of its diameter. KiCad's own connectivity was not probed beyond the benches.
- A board file whose stack-up node the reader projects no stack-up from gets no depth (`stackup` is
  `none`): the node's thicknesses are what 10.0.6 counts, but only one such node was measured, and 9.0.9
  was not. The default stack-up is not claimed for it either.
- A die length that is not a non-negative decimal counts as 0 with `kicad.length.bad-die`; `die_delay`
  (10.0 only, a time) is not read.
- A depth is computed exactly and rounded half to even once, so a copper layer of 17.5 µm has its middle
  at a whole nanometre.
