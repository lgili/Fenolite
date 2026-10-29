# assembly-test-features Specification

## Purpose
TBD - created by archiving change c0118-assembly-test-features. Update Purpose after archive.

## Requirements

### Requirement: Test-point report rows
`fenolite.exports.testpoints.report(design, pads, *, side="both") -> Report` SHALL list the test points, fiducials and non-plated holes of a board read from its file, where `pads` are the board's pads in the board frame (`BoardPad`, from the backend's frame) and `side` is `top`, `bottom` or `both`.
- **Test points.** One `TestPointRow(ref, path, pad, net, position, side, access, shape, size, drill)` per pad whose model pad has `fab_property == "test_point"`: `ref` the component's reference, or the footprint id when it has no component; `path` the component path or `""`; `pad` the pad number; `net` the net name, or `""` on no net; `position` the pad's position in the board frame; `side` the footprint's side; `shape`, `size` and `drill` those of the pad.
- **Access.** A side is open when the pad's board layers hold both its copper layer and its mask layer (`F.Cu` and `F.Mask`, or `B.Cu` and `B.Mask`): a probe reaches the pad only there. `access` MUST be `both` when both sides are open, `top` or `bottom` when only that side is, and `none` when neither is.
- **Fiducials.** One `FiducialRow(ref, path, position, side, scope, size)` per footprint that holds a pad marked `fiducial_global` or `fiducial_local`: the position and size of its first such pad, and `scope` `global` or `local`.
- **Holes.** One `HoleRow(ref, path, position, drill, length, tooling)` per `np_thru_hole` pad: the hole's centre, its drill, the slot length or `None`, and `tooling` true exactly when the footprint's lib id starts with `Fenolite_Assembly:ToolingHole_` (`testpoints.TOOLING_PREFIX`).
- With `side` `top` or `bottom`, test points whose `access` does not include that side, and fiducials of the other side, MUST be left out; holes are always listed.
- Rows MUST be in natural order of `ref`, then of the pad number. Lengths are integers in nanometres; no float is used.

#### Scenario: Access from layers
- **GIVEN** a board with four pads marked `test_point`: an SMD pad on `F.Cu` and `F.Mask`, an SMD pad on `B.Cu` and `B.Mask`, a through-hole pad on `F.Cu`, `B.Cu`, `F.Mask` and `B.Mask`, and an SMD pad on `F.Cu` only
- **WHEN** `report` runs with `side="both"`
- **THEN** their `access` values are `top`, `bottom`, `both` and `none`

#### Scenario: Tooling holes among holes
- **GIVEN** a board with the footprints `Fenolite_Assembly:ToolingHole_3mm` of `TH1` and `Fenolite_Holes:NPTH_3.2mm` of `H1`
- **WHEN** `report` runs
- **THEN** it holds two hole rows, with `tooling` true for `TH1` only, and drills of 3 mm and 3.2 mm

#### Scenario: One side
- **GIVEN** the board of "Access from layers" with a global fiducial on each side
- **WHEN** `report` runs with `side="bottom"`
- **THEN** it holds the bottom and through-hole test points, the bottom fiducial and every hole

### Requirement: Test-point coverage
`Report.coverage` SHALL be `Coverage(side, eligible, covered, uncovered)`:
- `eligible` MUST count the nets that hold at least two pads of the board, test-point pads included; pads on no net do not count.
- `covered` MUST count the eligible nets that hold a test point whose `access` includes `side`; for `both`, any `access` other than `none`.
- `uncovered` MUST list the other eligible nets by name, in sorted order.

#### Scenario: Coverage per side
- **GIVEN** a board with the net `A` (two pads and a top test point), `B` (three pads, no test point), `C` (one pad and a bottom test point) and `D` (one pad)
- **WHEN** `report` runs with `side="both"` and with `side="top"`
- **THEN** the first gives `eligible == 3`, `covered == 2` and `uncovered == ("B",)`, and the second `covered == 1` and `uncovered == ("B", "C")`

### Requirement: Assembly and test findings
`fenolite.exports.testpoints.findings(report, design, *, min_coverage=None, min_pitch=None, min_fiducials=None) -> tuple[Issue, ...]` SHALL judge a report, with these codes, which join `exports.codes.ISSUE_CODES` and `docs/cli-contract.md`:

| code | severity | given when |
|---|---|---|
| `testpoint.none` | info | no pad of the board carries the test-point mark |
| `testpoint.no-net` | warning | a test point is on no net |
| `testpoint.covered` | warning | a test point's `access` is `none` |
| `testpoint.coverage-low` | error | `min_coverage` is given and `covered × 100 < min_coverage × eligible` |
| `testpoint.too-close` | error | `min_pitch` is given and the centres of two test points whose `access` shares a side are closer than `min_pitch`; one issue per pair |
| `fiducial.too-few` | error | `min_fiducials` is given and a side that the report covers holds a footprint with the attribute `smd`, without `dnp` and without a fiducial pad, and fewer global fiducials than `min_fiducials`; one issue per side |

- Distances MUST be compared exactly, on squares of integers.
- The hint of `testpoint.none` MUST name `design.test_point()` and `Footprint.pad(fab_property="test_point")`, and say that KiCad's library test points carry no mark.
- Without the three values no error is given: Fenolite ships no target (plan D6).
- `testpoints.EVIDENCE` MUST be `Evidence(Level.INFERRED, hypotheses=("H-K-TESTPOINT-D356", "H-K-PAD-FABPROP"))` until both rows are `KICAD-VERIFIED (9.0.x, 10.0.x)` in `docs/hypotheses.md`.

#### Scenario: No values, no errors
- **GIVEN** a board with one covered test point and one test point on `F.Cu` without a mask layer
- **WHEN** `findings` runs without values
- **THEN** it gives one `testpoint.covered` warning naming the second, and no error

#### Scenario: Targets missed
- **GIVEN** a report with `eligible == 4` and `covered == 3`, two top test points whose centres are 1.9 mm apart, and a top side with SMD parts and one global fiducial
- **WHEN** `findings` runs with `min_coverage=80`, `min_pitch=mm(2)` and `min_fiducials=3`
- **THEN** it gives one `testpoint.coverage-low`, one `testpoint.too-close` naming both test points, and one `fiducial.too-few` naming the top side

#### Scenario: Unmarked board
- **GIVEN** a board whose test points are KiCad library footprints without a mark
- **WHEN** `findings` runs
- **THEN** it gives one `testpoint.none` info whose hint names both ways to mark a pad

### Requirement: Test-point placement
`fenolite testpoints BOARD --place --side top|bottom` SHALL add one probe, the generated test point of `design.test_point`, for each eligible net (`Test-point coverage`) that the side does not reach and `--nets` matches, under the mutation protocol, and SHALL report the coverage before and after in `result.place`. A net without a site MUST give `testpoint.no-site` with the nearest site and its blocker.

#### Scenario: Coverage raised to every net
- **GIVEN** an authored two-layer board with six eligible nets and room around each, none with a bottom test point
- **WHEN** `uv run pytest tests/unit/exports/test_testpoint_place.py -k cover` runs `fenolite testpoints <board> --place --side bottom --confirm --json`
- **THEN** `result.place.before.covered` is 0, `result.place.after.covered` is 6, and Fenolite's copper check finds nothing new on the written board

#### Scenario: A net without room
- **GIVEN** the same board with one more net whose copper lies only under a bottom part's courtyard
- **WHEN** `uv run pytest tests/unit/exports/test_testpoint_place.py -k no_site` runs the command
- **THEN** that net stays uncovered and the issues hold one `testpoint.no-site` naming the courtyard of that part

### Requirement: Probe sites
A site SHALL lie on a grid of `--grid` (2.54 mm) within `--reach` (5 mm) of an anchor of the net on the side's outer layer (pad centre, via, track or arc end), nearest first, joined by one straight track of the net's class width. Probe and track MUST keep the clearance in force from other copper, holes and earlier probes, the edge clearance from the edge, and miss the side's courtyards, silkscreen and forbidding rule areas; probes keep `--min-pitch` (1.27 mm).

#### Scenario: Sites nearest first
- **WHEN** `uv run pytest tests/unit/exports/test_testpoint_place.py -k sites` lists the sites of one anchor
- **THEN** they come by distance, then by y and x, each within the reach

### Requirement: Placed test points checked
Before writing, Fenolite's copper check SHALL judge the board with and without the probes, and a probe whose pad or track a new finding names MUST NOT be written (`testpoint.check-failed`). With `--drc`, `kicad-cli` DRC SHALL run on the board before and after; a type that grows, the footprint-library types aside, MUST give `testpoint.drc-new` and nothing is written; without one the reply is `KICAD-VERIFIED`.

#### Scenario: KiCad finds nothing new
- **GIVEN** the authored benches, probed from the bottom and from the top
- **WHEN** `uv run pytest tests/kicad/assembly/test_testpoint_place_oracle.py` runs the command with `--drc --confirm`
- **THEN** no DRC type grows but `lib_footprint_issues`, the unconnected items stay as they were, and the evidence is `KICAD-VERIFIED`

### Requirement: Placed test points kept by a rebuild
A probe SHALL be written as a footprint without `fenolite.path` and its track as board copper, so that a rebuild of the design script keeps both as a board-only footprint (`layout.board-only`) and a kept track. The reply SHALL hold `testpoint.board-only` (info) naming the probes.

#### Scenario: A rebuild keeps the probes
- **GIVEN** the built blink with probes placed from the top
- **WHEN** `uv run pytest tests/unit/exports/test_testpoint_place.py -k rebuild` builds the script again over that board
- **THEN** every probe and its track are on the rebuilt board and the build reports `layout.board-only`

### Requirement: Test-point placement codes
`testpoint.no-site` (warning), `testpoint.check-failed` (warning), `testpoint.drc-new` (error) and `testpoint.board-only` (info) SHALL be registered with `fenolite explain`. `--grid`, `--reach`, `--size`, `--nets`, `--drc` and `--kicad-cli` without `--place`, and `--place` with `--side both`, MUST be refused with `FEN-2001`.

#### Scenario: Options refused
- **WHEN** `uv run pytest tests/unit/exports/test_testpoint_place.py -k refusals` runs the command with `--grid 1mm` alone or `--place` with no side
- **THEN** the exit code is 2 with `FEN-2001` naming the option
