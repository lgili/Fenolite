## ADDED Requirements

### Requirement: DRC report limits are probed
`tests/kicad/check/test_drc_limits.py` SHALL settle `H-K-DRC-LIMITS` on `kicad-cli` 9.0.9 and 10.0.6 with an authored bench, and `backends.kicad.drc.REPORT_LIMITS` SHALL hold only values that its probes record.
- The bench `tests/kicad/check/_limitsbench.py` MUST be authored for Fenolite and written by code: a board of 400 mm × 400 mm with a `{}` project and a rules file, holding N copies of one small construct that gives exactly one violation of one type, laid out on a grid so that no copy touches another. It MUST cover these thirteen types: `clearance`, `unconnected_items`, `track_dangling`, `via_dangling`, `copper_edge_clearance`, `track_width`, `hole_to_hole`, `hole_clearance`, `annular_width`, `silk_overlap`, `courtyards_overlap`, `lib_footprint_issues` and `shorting_items`. It is a second bench beside `_limitbench.py` (c0051), which keeps proving the canary's verdict at the `clearance` limit and is not changed.
- The probes, registered in `tests/kicad/_probes.py` and recorded in `docs/evidence/kicad/probes/<version>.json`, MUST be: `drc-limit-<type>` for each of the thirteen types at 700 copies, whose outcome is the number of entries `kicad-cli pcb drc --format json --severity-all` writes for the type; `drc-limit-below`, the same for `track_dangling`, `silk_overlap` and `unconnected_items` at 150 copies; `drc-limit-all-track-errors`, the count of `track_dangling` at 700 copies with `--all-track-errors`; and `drc-limit-keys`, the sorted top-level keys of the report.
- The test MUST compare each recorded count with `REPORT_LIMITS[major]`: equal for every type, except that `clearance` on 9.0.9 MUST be at least 499 and below 700 (`H-K-DRC-LIMIT`: that major passes the limit by a few). The counts at 150 copies MUST be 150.
- A probe that records another count than the hypothesis states MUST stop the change: the table and the hypothesis row are corrected first, and a type whose count differs between two runs MUST be taken out of `per_type` and named in the register.
- `docs/formats/kicad/drc.md` MUST hold one fact row per measured type and major, with the sources S-0020 and S-0029, the hypothesis and its label.

#### Scenario: Limits on both majors
- **WHEN** `uv run pytest tests/kicad/check/test_drc_limits.py -rA` runs on the local `kicad-cli` 10.0.6 and in the pinned 9.0.9 image
- **THEN** on both, the thirteen `drc-limit-<type>` probes equal `REPORT_LIMITS[major]` (`clearance` on 9.0.9 between 499 and 699), `drc-limit-below` records 150 for its three types, and `drc-limit-all-track-errors` records the same count as `drc-limit-track_dangling`

#### Scenario: The report has no key for a cut
- **WHEN** the same test reads `drc-limit-keys` in both probe files
- **THEN** the keys are `$schema`, `coordinate_units`, `date`, `ignored_checks`, `included_severities`, `kicad_version`, `schematic_parity`, `source`, `unconnected_items` and `violations`, and none of them marks a type as cut

#### Scenario: Check marks the bench
- **GIVEN** the bench with 700 copies of the `track_dangling` construct
- **WHEN** `uv run pytest tests/kicad/check/test_drc_limits.py -k check` runs `fenolite check <bench> --stages drc.kicad --json` on both majors
- **THEN** `summary.limits` holds `{"type": "track_dangling", "reported": 199, "limit": 199}`, and the issues hold one `check.report-limit` warning whose `where` is `kicad.drc.track-dangling`
