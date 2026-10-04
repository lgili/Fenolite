## ADDED Requirements

### Requirement: Via re-net probe
`tests/kicad/copper/test_via_renet.py` (markers `needs_kicad`, major-aware) SHALL record on 9.0.9 and 10.0.6 what KiCad does with a via whose copper touches a track of another net (`H-K-VIA-RENET`). The benches MUST be built with c0018's `tests/kicad/rules/_rulebench.Builder`, written with `write_board` for the running major, with a `{}` project and the rules text `(version 1)` next to them. Each holds a 0.6 mm via of net `GND` whose disc overlaps a 0.25 mm `F.Cu` track of net `VIN` by 0.05 mm:
- **Padded.** The track ends on pad 1 of a placed `Mini_R_0603`, which is on `VIN`; there is no other `GND` copper. This is the reported case.
- **Tied.** The padded bench, and a `GND` track that joins the via to pad 1 of a second `Mini_R_0603`, on `GND`: both nets own a pad.
- **Dangling.** No footprint: the via and the track only.
- **Anchored.** No footprint: the dangling bench with a `GND` track ending at the via's centre.
- **Probes**, each `present` or `absent`:
  - `copper-renet-export` (padded) and `copper-renet-tied-export`: the IPC-D-356 export (`KicadCli.export_ipcd356`, read with `read_ipcd356`) lists the bench's only via record under `VIN`;
  - `copper-renet-drc` (padded), `copper-renet-dangling-drc`, `copper-renet-anchored-drc`, and on 9.0 only `copper-renet-tied-drc`: the DRC report (`KicadCli.drc`, `read_drc_report`) holds a `shorting_items` violation naming the via's uuid;
  - `copper-renet-dangling-merged` and `copper-renet-anchored-merged`: the DRC report describes the via and the `VIN` track with one net name (the name in square brackets of an item's description);
  - `copper-renet-resave` (padded) and `copper-renet-dangling-resave`, on 10.0 only: after `KicadCli.upgrade_board`, `read_board` gives the via the net of the `VIN` track.
- **What is not pinned.** A probe MUST have one outcome on every run of a version. Two outcomes were measured to differ between runs of one unchanged bench and MUST NOT be probes; `docs/formats/kicad/copper.md` records their counts as supporting data: which of the two net names a cluster without pads takes (and so the via's export net on the dangling and anchored benches on 10.0), and whether 10.0.6 reports the `shorting_items` violation of the tied bench.
- The DRC types that name the via's uuid MUST be recorded, sorted, per bench and per major in `docs/formats/kicad/copper.md` as supporting data.
- `H-K-VIA-RENET` MUST become `KICAD-VERIFIED` on a major only when `copper-renet-export` records `present`, `copper-renet-drc` records `absent` and, on 10.0, `copper-renet-resave` records `present`. Otherwise the row MUST record the observed outcomes, be marked refuted on that major, and name a `-2` successor stating them. No requirement of this change depends on the outcome.

#### Scenario: Re-net recorded on both majors
- **WHEN** `uv run pytest tests/kicad/copper/test_via_renet.py` runs on 9.0.9 and on 10.0.6
- **THEN** the eight probes of 9.0.9 and the nine of 10.0.6 hold `present` or `absent`, and `uv run pytest tests/kicad/test_probe_results.py` passes against the committed `docs/evidence/kicad/probes/<version>.json`

#### Scenario: Fenolite flags the bench
- **GIVEN** the design of the dangling bench
- **WHEN** `uv run pytest tests/unit/checks/test_copper.py -k renet_bench` runs `check_copper` on it
- **THEN** it reports one `copper.short` naming the via and the track, on `F.Cu`

### Requirement: Copper verdict parity canaries
`tests/kicad/copper/test_copper_parity.py` (markers `needs_kicad`, major-aware) SHALL compare the verdicts of `check_copper` with those of `kicad-cli pcb drc` on authored benches, on 9.0.9 and 10.0.6 (`H-K-COPPER-SHAPES`, `H-K-COPPER-RESOLVE`) and on 10.0.6 for zone fills (`H-K-COPPER-ZONES`).
- **Benches.** A bench whose rows need a project setting (net classes or the board minimum) MUST be written through c0010's triad path with the canary of c0010's `tests/_netclass_bench.py`, scoped by a `net` condition to `CANARY_A`, as c0010's net-class oracle does, because the unconditional canary rule would govern every pair over the classes; a custom rule of such a bench MUST come after the canary rule. Every other bench MUST follow "Rules proofs carry a canary" with `_rulebench.Builder` and a `{}` project, its rules selecting the probe nets only, so the canary pair stays under the canary rule. This change extends `_rulebench.Builder` with `arc_pair`, `via_pair`, `pad_track`, `tht_track` and `fill_track` rows, and with net classes and model rules, which both kinds of bench use. Every bench MUST fail with "rules file not loaded" when its canary violation is missing.
- **Rows.** Per pair kind (track–track, arc–track, via–track, via–via, SMD pad–track with `Mini_R_0603`, pad–pad of two footprints, through-hole pad–track on `B.Cu` with `Mini_LED_THT_3mm`, and, on 10.0.6 with a target-10 board, zone fill–track), one row per edge gap: `c − 10 µm`, `c` and `c + 10 µm`, each pair on two probe nets of its own. An arc pair has no row at `c`: at exactly the clearance its band may report (`copper-check`, "Clearance findings").
- **No overlapping or touching row.** KiCad's verdict on copper of two nets that touches is not repeatable: without a pad on both nets it treats the copper as one net and reports nothing, and with one 10.0.6 reports the short in about half of its runs ("Via re-net probe"). Such rows MUST NOT be compared or pinned; `check_copper`'s shorts are proved by its own exact tests, and the re-net probes record KiCad's side.
- **Zone clearance of the fill rows.** The zone of a fill row MUST carry `(connect_pads (clearance 0))` and `(filled_areas_thickness no)`, inserted by token edit into the written board, so that KiCad's verdict rests on `c` alone: without them KiCad applies its default zone clearance of 0.5 mm to the fill, and `check_copper` does not apply the zone's own clearance (`copper-check`, "Supported cases are documented against KiCad's DRC").
- **Clearance sources.** `c` is given once by a clearance rule on the probe nets (0.2 mm), once by the net class of both nets (0.3 mm), and once by the project's `board.design_settings.rules.min_clearance` above the classes (0.4 mm), set as c0010's `test_netclass_drc.py::test_floor` sets it. The three values differ from each other, and the last two from the template's `Default` class clearance of 0.2 mm, so each source is told from the others.
- **Resolution rows.** A rule below the class value, a rule above it, two classes (the larger governs), a floor above a rule (the rule governs on both majors, `H-K-PRO-MIN-RULE-2`), a rule with severity `ignore`, and an `item_kind track` rule on an arc pair. Each case MUST hold a row that KiCad reports and a row that it does not.
- **Verdicts.** KiCad's verdict for a row MUST be `short` when a `shorting_items` violation names both items' uuids, `clearance` when a `clearance` violation does, and `clean` otherwise (`H-K-DRC-TYPES`, `H-K-DRC-UUID`). Fenolite's verdict MUST come from `check_copper` on the board read back with `read_board`, with the bench's project and rules texts applied by `design_rules_from_texts` for the running major (so the switches follow c0026's tables) and the pads of c0028's frame. They MUST be equal on every row.
- **Boundary.** Rows at `c − 1 µm` and `c − 1 nm` MUST be recorded only, as `copper-boundary-1um` and `copper-boundary-1nm` (`present` when KiCad reports the violation).
- **Zones.** Two filled zones of different nets and equal priority whose outlines overlap on `F.Cu` MUST be recorded on 10.0.6 as `copper-zone-overlap` (`present` when a violation names both zone uuids), as supporting data for the Fenolite rule "Zone outline overlaps" (`copper-check`), which does not depend on it.
- **Probes.** Each pair kind and each resolution case MUST be recorded as `copper-parity-<kind>` or `copper-resolve-<case>`: `equal` when every row agrees, under each clearance source for a pair kind, and `different` otherwise.
- **Hermetic half.** `tests/kicad/copper/test_parity_bench.py` MUST check without `kicad-cli`, for targets 9 and 10, that `check_copper` gives a clearance finding on every row below `c` and none on the others.

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
