## ADDED Requirements

### Requirement: Via re-net probe
`tests/kicad/copper/test_via_renet.py` (markers `needs_kicad`, major-aware) SHALL record on 9.0.9 and 10.0.6 what KiCad does with a via whose copper touches a track of another net (`H-K-VIA-RENET`). The benches MUST be built with c0018's `tests/kicad/rules/_rulebench.Builder`, written with `write_board` for the running major, with a `{}` project and the rules text `(version 1)` next to them:
- **Dangling.** A 0.6 mm via of net `GND` whose disc overlaps a 0.25 mm `F.Cu` track of net `VIN` by 0.05 mm, with no other `GND` copper.
- **Anchored.** The same via with a `GND` track ending at its centre.
- **Probes**, each `present` or `absent`:
  - `copper-renet-export` and `copper-renet-anchored-export`: the IPC-D-356 export (`KicadCli.export_ipcd356`, read with `read_ipcd356`) lists the bench's only via record under `VIN`;
  - `copper-renet-drc` and `copper-renet-anchored-drc`: the DRC report (`KicadCli.drc`, `read_drc_report`) holds a `shorting_items` violation naming the via's uuid;
  - `copper-renet-resave`, on 10.0 only: after `KicadCli.upgrade_board`, `read_board` gives the via the net `VIN`.
- The DRC types that name the via's uuid MUST be recorded, sorted, per major in `docs/formats/kicad/copper.md` as supporting data.
- `H-K-VIA-RENET` MUST become `KICAD-VERIFIED` on a major only when `copper-renet-export` records `present`, `copper-renet-drc` records `absent` and, on 10.0, `copper-renet-resave` records `present`. Otherwise the row MUST record the observed outcomes, be marked refuted on that major, and name a `-2` successor stating them. No requirement of this change depends on the outcome.

#### Scenario: Re-net recorded on both majors
- **WHEN** `uv run pytest tests/kicad/copper/test_via_renet.py` runs on 9.0.9 and on 10.0.6
- **THEN** the four probes of 9.0.9 and the five of 10.0.6 hold `present` or `absent`, and `uv run pytest tests/kicad/test_probe_results.py` passes against the committed `docs/evidence/kicad/probes/<version>.json`

#### Scenario: Fenolite flags the bench
- **GIVEN** the design of the dangling bench
- **WHEN** `uv run pytest tests/unit/checks/test_copper.py -k renet_bench` runs `check_copper` on it
- **THEN** it reports one `copper.short` naming the via and the track, on `F.Cu`

### Requirement: Copper verdict parity canaries
`tests/kicad/copper/test_copper_parity.py` (markers `needs_kicad`, major-aware) SHALL compare the verdicts of `check_copper` with those of `kicad-cli pcb drc` on authored benches, on 9.0.9 and 10.0.6 (`H-K-COPPER-SHAPES`, `H-K-COPPER-RESOLVE`) and on 10.0.6 for zone fills (`H-K-COPPER-ZONES`).
- **Benches.** A bench whose rows need a project setting (net classes or the board minimum) MUST be written through c0010's triad path with the canary of c0010's `tests/_netclass_bench.py`, scoped by a `net` condition to `CANARY_A`, as c0010's net-class oracle does, because the unconditional canary rule would govern every pair over the classes; a custom rule of such a bench MUST come after the canary rule. Every other bench MUST follow "Rules proofs carry a canary" with `_rulebench.Builder` and a `{}` project, its rules selecting the probe nets only, so the canary pair stays under the canary rule. This change extends `_rulebench.Builder` with `arc_pair`, `via_pair`, `pad_track`, `tht_track` and `fill_track` rows, which both kinds of bench use. Every bench MUST fail with "rules file not loaded" when its canary violation is missing.
- **Rows.** Per pair kind (track–track, arc–track, via–track, via–via, SMD pad–track with `Mini_R_0603`, pad–pad of two footprints, through-hole pad–track on `B.Cu` with `Mini_LED_THT_3mm`, and, on 10.0.6 with a target-10 board, zone fill–track), one row per edge gap: an overlap of 50 µm, a touch (0), `c − 10 µm`, `c` and `c + 10 µm`, each pair on two probe nets of its own.
- **Zone clearance of the fill rows.** The zone of a fill row MUST carry `(connect_pads (clearance 0))`, inserted by token edit into the written board, so that KiCad's verdict rests on `c` alone: without it KiCad applies its default zone clearance of 0.5 mm to the fill, and `check_copper` does not apply the zone's own clearance (`copper-check`, "Supported cases are documented against KiCad's DRC").
- **Clearance sources.** `c` = 0.2 mm, given once by a clearance rule, once by a net class on both nets, and once by the project's `board.design_settings.rules.min_clearance` above the classes, set as c0010's `test_netclass_drc.py::test_floor` sets it.
- **Resolution rows.** A rule below the class value, a rule above it, two classes (the larger governs), a floor above a rule, a rule with severity `ignore`, and an `item_kind track` rule on an arc pair.
- **Verdicts.** KiCad's verdict for a row MUST be `short` when a `shorting_items` violation names both items' uuids, `clearance` when a `clearance` violation does, and `clean` otherwise (`H-K-DRC-TYPES`, `H-K-DRC-UUID`). Fenolite's verdict MUST come from `check_copper` on the board read back with `read_board`, with the bench's project and rules texts applied by `design_rules_from_texts` for the running major (so the switches follow c0026's tables) and the pads of c0028's frame. They MUST be equal on every row except the touch rows, whose KiCad type is recorded only (probe `copper-touch-type`, `present` when it is `shorting_items`).
- **Boundary.** Rows at `c − 1 µm` and `c − 1 nm` MUST be recorded only, as `copper-boundary-1um` and `copper-boundary-1nm` (`present` when KiCad reports the violation).
- **Zones.** Two filled zones of different nets and equal priority whose outlines overlap on `F.Cu` MUST be recorded as `copper-zone-overlap` (`present` when a violation names both zone uuids), as supporting data for the Fenolite rule "Zone outline overlaps" (`copper-check`), which does not depend on it.
- **Probes.** Each pair kind and each resolution case MUST be recorded as `copper-parity-<kind>` or `copper-resolve-<case>`: `equal` when every row agrees, `different` otherwise.

#### Scenario: Parity on both majors
- **WHEN** `uv run pytest tests/kicad/copper/test_copper_parity.py` runs on 9.0.9 and on 10.0.6
- **THEN** every `copper-parity-*` and `copper-resolve-*` probe records `equal` (the fill row on 10.0.6 only), and every bench's canary violation is present

#### Scenario: Rule below the class value
- **GIVEN** a pair 0.3 mm apart, both nets in a class of 0.5 mm, and a rule of 0.1 mm on the pair after the canary rule, on a class bench with the scoped canary
- **WHEN** the resolution row runs
- **THEN** KiCad's verdict and that of `check_copper` are equal, and the probe `copper-resolve-rule-below-class` records `equal`

#### Scenario: Missing canary fails
- **GIVEN** a `DrcReport` without the canary violation, as DRC gives when KiCad drops the rules file
- **WHEN** the hermetic `uv run pytest tests/kicad/copper/test_parity_bench.py` passes it to the parity test's verdict helper
- **THEN** the call fails the test with a message saying the rules file was not loaded, and neither passes nor skips
