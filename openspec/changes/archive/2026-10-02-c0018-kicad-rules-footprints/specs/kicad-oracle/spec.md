## ADDED Requirements

### Requirement: Rules proofs carry a canary
Every oracle test that judges custom rules SHALL run `kicad-cli pcb drc` on a bench that carries the canary, and SHALL pass only when the canary violation is in the DRC JSON report. This covers `tests/kicad/rules/` and every later rules proof that reuses its bench.
- The canary rule MUST be the rule of `tests/data/kicad/tokens/canary/canary.kicad_dru`, read from that file and placed right after `(version 1)`, so that every later rule takes precedence over it. If `H-K-DRU-ORDER` finds that the earlier rule governs on a major, the canary MUST be placed last for that major instead.
- The bench MUST hold the canary pair: two 0.25 mm tracks on nets `CANARY_A` and `CANARY_B` on `F.Cu`, with centres 1 mm apart and at least 10 mm from other copper. The other rules of the bench MUST NOT match them.
- Probe pairs that no later rule governs MUST be more than 3 mm apart, so the canary alone never flags them.
- Benches MUST be built in the test through the model and c0017's `write_board` for the running major, with a `{}` project file next to the board. They MUST NOT be committed.
- DRC MUST run through c0017's `KicadCli.drc` on a copy, with an empty `KICAD_CONFIG_HOME`. It MUST NOT use `--exit-code-violations`. The report MUST be read with c0017's `read_drc_report`, and violations MUST be matched by type and item uuids. The canary violation is the `clearance` violation between the two canary tracks.
- A report without the canary violation MUST fail the test with a message saying the rules file was not loaded. It MUST NOT pass or skip.
- The negative control MUST copy `tests/data/kicad/rules/broken.kicad_dru` (the canary plus a single-quoted rule name) verbatim onto a bench and MUST observe exit 0 without the canary violation on 10.0.6, and on 9.0.9 while `H-K-DRU-QUOTE` holds there. `dru-broken-silent` MUST record the observed outcome on each major. If 9.0.9 loads that file, the 9.0.9 control MUST copy `tests/data/kicad/rules/ten_only.kicad_dru` verbatim instead, which 9.0.9 drops whole (`H-K-TOK-RULES-DRIFT`), and observe the same.
- Each outcome MUST be recorded with c0017's `_probes` helper under a `dru-*` probe id, using c0017's closed outcome set (`present` or `absent` for a violation, `load` or `reject` for a file), and `tests/kicad/test_probe_results.py` MUST compare it with `docs/evidence/kicad/probes/<version>.json` in both KiCad jobs.

#### Scenario: Canary present
- **GIVEN** a bench for the `net` op with a 5 mm rule on net `N1`, a probe pair `N1`/`N2` and a control pair `N3`/`N4`, both 4 mm apart, and the canary
- **WHEN** the test runs on 10.0.6
- **THEN** it passes only because the report holds the `N1`/`N2` violation, no `N3`/`N4` violation, and the canary violation

#### Scenario: Canary absent
- **GIVEN** a `DrcReport` without the canary violation, as DRC gives with exit 0 when KiCad drops the rules file (for example because a rule uses an invented constraint type)
- **WHEN** the hermetic `uv run pytest tests/kicad/rules/test_bench.py` passes that report to `_bench.require_canary`, the check every rules test runs
- **THEN** the call fails the test with a message saying the rules file was not loaded, and neither passes nor skips

#### Scenario: Silent disable reproduced
- **GIVEN** `tests/data/kicad/rules/broken.kicad_dru` copied verbatim onto a bench
- **WHEN** `uv run pytest tests/kicad/rules/test_rule_dialect.py -k broken` runs on 9.0.9 and on 10.0.6
- **THEN** DRC exits 0, the report holds no canary violation, and the probe `dru-broken-silent` records `absent` (on 9.0.9 while `H-K-DRU-QUOTE` holds)

#### Scenario: Probe drift detected
- **GIVEN** a committed `docs/evidence/kicad/probes/10.0.6.json` in which `dru-order-forward` records the outcome `present`
- **WHEN** a run on 10.0.6 records `absent` for that probe
- **THEN** `uv run pytest tests/kicad/test_probe_results.py` fails naming `dru-order-forward` and both outcomes

#### Scenario: Benches never reach the repository
- **WHEN** `uv run pytest tests/kicad/rules -q` runs on the local KiCad 10.0.6
- **THEN** `git status --porcelain` is unchanged afterwards
