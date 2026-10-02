## ADDED Requirements

### Requirement: Zone settings pass the oracle
The meaning of zone settings SHALL be proved with `kicad-cli` on benches built through the model API and written by `write_board` for the running major. Every run MUST go through c0009's runner on copies. The probes MUST be recorded per version ("Probe results per kicad-cli version").
- **Bench.** `tests/kicad/zones/_zonebench.py` builds the zone canary: a two-layer 40 × 30 mm board; a `GND` pour on `F.Cu` over a 2 × 2 mm SMD pad and a 1.7 mm round THT pad on `GND`; a 1 × 1 mm SMD pad and a 1.7 mm THT pad on `SIG`; a closed `SIG` track ring around an island of the pour; and two `SIG` tracks that leave a 0.2 mm channel of pour between their clearances. Each case sets the zone settings, a pad's or a footprint's `zone_connect`, or a `.kicad_dru` rule.
- **Probes first (10.0.6).**
  - `zone-defaults-t10`: a zone written without `connect_pads`, `min_thickness` and `fill`, re-saved by `pcb upgrade --force`, holds the children that `zones.emit_settings(ZoneSettings(), filled=False, locked=False, major=10)` gives.
  - `zone-fat9`, on both majors: in the Gerber that `pcb export gerbers -l B.Cu` plots for `created_board()` written for target 9, the region of zone `GND_POUR` has the extreme coordinates of its fill polygon. A copy without `(filled_areas_thickness no)` reaches `min_thickness / 2` further on each side.
  - Stop rule: when either outcome differs, the defaults or the target-9 form are corrected from the observation before group 3 of the tasks starts.
- **Refill (10.0.6).** `pcb drc --refill-zones --save-board` runs on copies. The saved board is read with `read_board`, and its fills are measured with c0005's exact predicates (`point_in_ring`, exact crossings of segments):
  - A thermal zone gives four spokes, on the axes of the SMD pad and at 45° on the round THT pad, with the corners of the relief ring clear. `solid` puts every probe of both pads in the fill, and `none` puts none there. `thru_hole_only` is solid on the SMD pad and thermal on the THT pad.
  - A pad's `zone_connect` 0 to 3 overrides the zone. A footprint's `zone_connect` 2 makes its pads solid, unless a pad says otherwise.
  - The gap between the fill and each `SIG` pad lies in [c, c + 5 µm]. c is the larger of the zone clearance and the clearance that the `Default` class (0.2 mm) or a `.kicad_dru` rule gives.
  - The spoke width equals `thermal_spoke_width`, and the gap of the relief equals `thermal_gap`, each within 1 µm.
  - The island is removed for `always`, kept as an `island` fill for `never`, kept for `below_area` with 10 mm², and removed for `below_area` with 50 mm².
  - The channel is filled with `min_thickness` 0.15 mm, and empty with 0.25 mm.
  - A hatched fill of 1 mm bars and 1.5 mm holes at 0° has bars and holes of those widths within 5 µm.
- **9.0.9.** The board of every case, written for target 9, MUST load: `pcb drc` exits 0 and writes a report. `zone-fat9` MUST hold.
- **Build.** The blink pour variant of `design-dsl` "Zones in a build" MUST load on both majors. On 10.0.6, its refilled board MUST hold a `GND` fill on `B.Cu`.
- **Fact recorded for the copper check.** Probe `zone-clearance-drc`, on 10.0.6: `pcb drc` without refill reports a `clearance` violation for an authored fill 0.3 mm from a `SIG` pad when the zone clearance is 0.5 mm, and none when it is 0.1 mm. Fenolite's behaviour does not depend on this probe.

#### Scenario: Connection modes on 10.0.6
- **GIVEN** `kicad-cli` 10.0.6
- **WHEN** `uv run pytest tests/kicad/zones/test_zone_oracle.py -k connection -rA` runs
- **THEN** the thermal, solid, none and `thru_hole_only` cases and the pad and footprint overrides give the probe patterns above

#### Scenario: Clearance in force
- **GIVEN** `kicad-cli` 10.0.6
- **WHEN** `uv run pytest tests/kicad/zones/test_zone_oracle.py -k clearance -rA` runs
- **THEN** the measured gap lies in [c, c + 5 µm] for a zone clearance of 0.3 mm (c is 0.3 mm), for 0.1 mm (c is 0.2 mm, from the class), and for 0.3 mm with a 0.6 mm rule on `SIG` (c is 0.6 mm)

#### Scenario: Thermal geometry, islands and minimum thickness
- **GIVEN** `kicad-cli` 10.0.6
- **WHEN** `uv run pytest tests/kicad/zones/test_zone_oracle.py -k geometry -rA` runs
- **THEN** the spoke width, the relief gap, the four island cases, the two channel cases and the hatch widths match the rules above

#### Scenario: Defaults and the target-9 plot
- **WHEN** `uv run pytest tests/kicad/zones/test_zone_probes.py -rA` runs on 10.0.6, and in the pinned 9.0.9 image
- **THEN** `zone-defaults-t10` gives `equal` on 10.0.6, and `zone-fat9` gives `equal` on both majors

#### Scenario: Every form loads on 9.0.9
- **GIVEN** the pinned 9.0.9 image
- **WHEN** `uv run pytest tests/kicad/zones/test_zone_oracle.py -k load -rA` runs
- **THEN** every case board written for target 9, and the target-9 blink pour variant, load with exit 0 and a DRC report

#### Scenario: Probe outcomes pinned
- **WHEN** `uv run pytest tests/kicad/test_probe_results.py -q` runs on 10.0.6 and in the 9.0.9 image
- **THEN** it passes, and `docs/evidence/kicad/probes/10.0.6.json` and `9.0.9.json` hold the outcomes of the `zone-*` probes of their major
