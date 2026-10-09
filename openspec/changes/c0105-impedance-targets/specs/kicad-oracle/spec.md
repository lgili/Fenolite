## ADDED Requirements

### Requirement: Impedance targets pass the oracle
The KiCad test suite SHALL settle `H-K-PRO-TUNING-DRC` and `H-K-DRU-IMPEDANCE` with the bench of `tests/kicad/impedance/_zbench.py`: a four-copper board written by `write_triad` with a stack-up written by c0101 (0.2 mm, 1.065 mm and 0.2 mm dielectrics, 35 µm copper), the classes `SE50` (a track on `F.Cu`, one on `B.Cu`) and `USB90` (a pair on `F.Cu`), class clearances of 0.2 mm, and the canary scoped to its own net. Every verdict MUST come from the JSON report ("DRC verdicts come from the JSON report"), and a run whose canary does not fire MUST fail.
- `tests/kicad/impedance/test_tuning_drc.py` (marker `needs_kicad`, 10.0 only) MUST record, from profiles written by `tuning.lower_profile`: `pro-tuning-width` (a 50 µm narrower track reported as `track_width` at `error` and at `warning` of `tuning_profile_track_geometries`, and not at `ignore`), `pro-tuning-exact` (1 µm wider and 100 nm narrower both reported), `pro-tuning-norow`, `pro-tuning-missing` (`missing_tuning_profile`), `pro-tuning-gap` (`diff_pair_gap_out_of_range` at a 50 µm wider gap), `pro-tuning-single-under-diff`, `pro-tuning-rule-governs` (a custom class rule replaces the check), `pro-tuning-gap-clearance` (no clearance finding between the pair at a gap below the class clearance, at `ignore`) and `pro-tuning-gap-clearance-rule` (the same with a board-wide custom clearance rule of 0.2 mm, recorded either way).
- `tests/kicad/impedance/test_impedance_rules.py` (both majors) MUST record `dru-impedance-width`: the per-layer rules of "Impedance targets in the DSL" report a track 1 µm above `max` and one 50 µm below `min` on their layers, and nothing on a track of the class on a layer without a rule.
- A design with both targets, built for each major, MUST load in `pcb drc` with no `missing_tuning_profile` and the canary firing; its tracks drawn at the targets' widths and gap MUST get no `track_width` and no `diff_pair_gap_out_of_range` finding, while one drawn 50 µm narrower gets one `track_width` finding.
- The outcomes MUST be recorded in both probe files, and the facts written to `docs/formats/kicad/project.md`, `rules.md` and `drc.md` with their sources and labels. When `pro-tuning-gap-clearance-rule` records a clearance finding, `build.impedance-gap-clearance` MUST also apply to target 10 when a custom clearance rule governs the pair.

#### Scenario: Profiles on 10.0.6
- **WHEN** `uv run pytest tests/kicad/impedance/test_tuning_drc.py -rA` runs on the local KiCad 10.0.6
- **THEN** each of the eight measured `pro-tuning-*` probes records the outcome of the design's measurements, `pro-tuning-gap-clearance-rule` holds an outcome, and the canary fires in every run

#### Scenario: Rules and the built design on both majors
- **WHEN** `uv run pytest tests/kicad/impedance/test_impedance_rules.py -rA` runs on the local KiCad 10.0.6 and inside the pinned 9.0.9 image
- **THEN** `dru-impedance-width` records `present` on both majors, and the built design gives exactly one `track_width` finding, on the narrowed track
