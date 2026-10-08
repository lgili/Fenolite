# Impedance targets: probe outcomes (c0105)

The probes of change c0105 and what is known of their outcomes. They settle `H-K-PRO-TUNING-DRC` and
`H-K-DRU-IMPEDANCE` (`docs/hypotheses.md`); `H-K-PRO-TUNING-KEYS` waits for a GUI save, and the
estimates (`H-G-AN-ZMS`, `H-G-AN-ZSL`) have no oracle and stay `INFERRED`.

## Status

Written on 2026-10-08 and **not yet run**: the change was implemented where no `kicad-cli` was available.
The benches are `tests/kicad/impedance/_zbench.py`; the tests are `test_tuning_drc.py` (10.0 only) and
`test_impedance_rules.py` (both majors). The probes join `tests/kicad/_probes.py` in the commit that
records them, because a registered probe without a recorded outcome fails
`tests/kicad/test_probe_results.py`. Until then the first record is the measurement of the design.

## First record: the design's measurements (2026-10-05)

Measured on 10.0.6 on the review branch (scratch benches, not committed), one run of the per-layer rules
on 9.0.9 in the pinned image:

| probe | expected | measured on 2026-10-05 |
|---|---|---|
| `pro-tuning-width` | `present` | a 50 µm narrower `B.Cu` track: `track_width` at `error` and at `warning` of `tuning_profile_track_geometries`, nothing at the template's `ignore` |
| `pro-tuning-exact` | `present` | 1 µm wider and 100 nm narrower both reported: `min` = `max` = the row's width |
| `pro-tuning-norow` | `absent` | a layer without a row is not checked |
| `pro-tuning-missing` | `present` | `missing_tuning_profile` "(Net Class: SE50, Tuning Profile: NOPE)" |
| `pro-tuning-gap` | `present` | `diff_pair_gap_out_of_range` "maximum gap 0.1500 mm; actual 0.2000 mm" |
| `pro-tuning-single-under-diff` | `absent` | a differential profile does not check single tracks of its class |
| `pro-tuning-rule-governs` | `absent` | a custom class `track_width` rule replaces the profile's check |
| `pro-tuning-gap-clearance` | `absent` | at `ignore`, no clearance finding between the pair at a gap below the class clearance |
| `pro-tuning-gap-clearance-rule` | recorded either way | not measured: a board-wide custom clearance rule of 0.2 mm beside the profile |
| `dru-impedance-width` | `present` (both majors) | per-layer `track_width` rules with `min` = `opt` = `max`: "max width 0.3500 mm; actual 0.3510 mm" and "min width 0.3500 mm; actual 0.3000 mm", on 10.0.6 and 9.0.9 |

When `pro-tuning-gap-clearance-rule` records a clearance finding, `build.impedance-gap-clearance` extends
to target 10 where a custom clearance rule governs the pair (task 1.3 of c0105).
