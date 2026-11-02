## 0. Entry check

- [x] 0.1 Read `openspec list`, the living specs this change touches (`package-layering`, `cli-contract`, `verification-loop`) and the changes it builds on (c0252, c0253, c0254, c0268, c0269, c0270, c0271). Write under this task, with the date and the base commit:
  - the final names of `@block`, `param`, `b.schematic`, `stimulus`, `b.layout(reuse=...)` and `fenolite blocks capture`;
  - c0253's expectation functions and the rating keys `power`, `voltage` and `current` of c0248's records;
  - c0254's generator signatures, the module of `PI` (the π enclosure) and of the I2C mode constants, and whether a public `i2c_mode_limits(mode, bus_capacitance)` exists (if not, task 1.4 adds it over the same table, one formula and two callers);
  - c0254's shipped families: the resistor family of E96 1 % and E24, and a capacitor family of ± 10 % with a voltage rating, in case 0603 (the worked numbers of `design.md` assume them; recompute each scenario with c0254's solver and update the numbers before code if a family differs);
  - c0254's registered id of UM10204, and the next free `S-` numbers;
  - where c0268 puts its catalog code, so that the layering row of `specs/package-layering/` names only the block modules.

  Entry review — 2026-11-01, base `5d8afc2f5d98375aeb4ee548ae1d30487cb61f86`.
  The combined prerequisite candidate contains c0252/53/54 and c0268/69/70/71 plus c0273.
  Final APIs: `@block(id=..., version=...)`, `param(..., unit=...)`,
  `b.schematic(schematic_group(...))`, `fenolite.testing.stimulus(..., ref=...)`,
  `b.layout(reuse=..., copper=True)`, `fenolite blocks capture BOARD --instance PATH -o FILE`.
  Expectations: `within`, `at_least`, `at_most`, `value_of`, `rating_of`, `voltage_of`,
  `current_of`; device keys `power`, `voltage`, `current`, with `abs_max`/`operating` limits.
  Generators: `voltage_divider(..., target=Range, vin=Range, current=Range, series=...)`,
  `rc_lowpass(..., corner=Range, c=PartQuery)`, `led_resistor(..., current=Range, vf=..., vs=...)`,
  `i2c_pull_ups(..., bus_capacitance=Range, vdd=..., mode=...)`.
  Existing π/ln enclosures lived in `pick.generators`; I2C facts in
  `pick.generators.pullup.MODES`, source S-0941. No public mode helper existed.
  This change shares them through `core.generator_limits` and DSL `gen.PI` /
  `gen.i2c_mode_limits`, reusing the exact table and one maximum-resistance formula.
  Verified families: `Fenolite:R_0603_E96_1pct`, `Fenolite:R_0603_E24_5pct`,
  `Fenolite:C_0603_X7R_50V` (10 %, 50 V). Solver probes reproduce 137k/52.3k,
  1.58k/100nF and 649Ω. Catalog discovery remains in `cli.blocksrc`, with records
  in `dsl.record`; starter bodies import DSL/core/stdlib only. Sources S-1120..1125
  are reserved, with S-0941 reused. Required parameter units are checked before the body.
  Full-gate proof remains open: the coordinating branch owns the serialized `make check-fast`
  and exact-head CI run; focused dependency proofs run here.

  Proof: `openspec validate c0272-starter-blocks --strict`; `make check-fast`.

  Entry proof completed 2026-11-02 on `ea762411cbb24bc5f9ba5a16d8b372ae7c720568`: root
  ran the serialized `make check-fast` from 09:45:03 to 10:17:02 UTC, exit 0
  (19564 passed, 55 skipped; JUnit records zero failures/errors). Fresh OpenSpec
  1.16.0 strict validation of this change also passes without warnings. The
  preceding API/family/expectation entry remains applicable: `core.generator_limits`
  and `dsl.gen` provide the shared enclosures/mode helper, and S-1120..1125 are
  now registered alongside S-0941. The five authored layout assets remain distinct
  from the still-required manual GUI work of task 2.1.
  This dated proof supersedes the earlier missing-fast-gate blocker only.
  Independent CI, native/manual, corpus, external-library and release criteria
  remain unchanged. The source-bound receipt, log and JUnit hashes are recorded
  in [the integration validation record](../c0319-integration-repairs/validation.md).

- [x] 0.2 Register the sources of design decision 8 in `docs/evidence/sources.md` (licence, what is used, "read for facts, nothing copied"), and replace the placeholders `S-DIV`, `S-JOULE`, `S-RC`, `S-LED`, `S-INTERVAL`, `S-TVS` in `design.md` with the ids. Proof: `uv run pytest tests/unit/test_provenance.py -q`.

## 1. The five blocks

- [x] 1.1 `fenolite.blocks` package, `__init__`, and the import-graph row (scenario "Blocks stay above the DSL"). Proof: `uv run pytest tests/unit/test_import_graph.py -q`.
- [x] 1.2 `divider.py` with its usage example, tests and golden file (scenarios "Default divider", "Unreachable output", "Two dividers, no collision"). Proof: `uv run pytest src/fenolite/blocks/tests/test_voltage_divider.py -q`; `uv run fenolite blocks test Fenolite:voltage_divider --json`.
- [x] 1.3 `rc.py` with its usage example, tests and golden file (scenarios "Default filter", "A window narrower than the capacitor"). Proof: `uv run pytest src/fenolite/blocks/tests/test_rc_lowpass.py -q`; `uv run fenolite blocks test Fenolite:rc_lowpass --json`.
- [x] 1.4 `led.py` with its usage example, tests and golden file (scenarios "Default indicator", "A pin that cannot drive it", "No forward voltage"). Proof: `uv run pytest src/fenolite/blocks/tests/test_led_indicator.py -q`; `uv run fenolite blocks test Fenolite:led_indicator --json`.
- [x] 1.5 `i2c.py` with its usage example, tests and golden file (scenarios "Value inside the window for every mode", "Two buses"). Proof: `uv run pytest src/fenolite/blocks/tests/test_i2c_pullups.py -q`; `uv run fenolite blocks test Fenolite:i2c_pullups --json`.
- [x] 1.6 `circuit.pullup-parallel` in `checks/circuit/`, `checks.codes`, `explain.toml` and `docs/cli-contract.md` (scenario "Two pull-up sets on one bus"). Proof: `uv run pytest tests/unit/checks/circuit/test_pullup_parallel.py tests/unit/cli/test_explain_cmd.py -q`.
- [x] 1.7 `protect.py` with its usage example (an `Example:` device record authored for it, `UNVERIFIED`, its numbers marked illustrative), tests and golden file (scenarios "Injected current limited by the series resistor", "Clamp above the downstream maximum"). Proof: `uv run pytest src/fenolite/blocks/tests/test_protected_input.py -q`; `uv run fenolite blocks test Fenolite:protected_input --json`.
- [x] 1.8 `H-G-STARTER-ENCLOSURE`: one property test per block evaluating every corner exactly against the judged ranges; register the hypothesis. Proof: `uv run pytest tests/unit/blocks/test_starter_enclosure.py -q`; `uv run pytest tests/unit/test_hypotheses_register.py -q`.

## 2. Layouts

- [ ] 2.1 Lay out each usage board by hand in KiCad (bench style: every port to the connector), capture each with `fenolite blocks capture ... --confirm`, commit the five layouts, and switch each body to `b.layout(reuse=..., copper=True)`; regenerate the golden files under one `--golden` plan (scenario "Layout properties"). Proof: `uv run pytest tests/unit/blocks/test_starter_layouts.py -q`; `uv run fenolite blocks test --json`.
  Partial proof — 2026-11-01: all five exact placements/copper were authored in
  `tools/blocks/starter_layouts.py`, captured with the normal CLI confirm writer, and
  replayed byte-for-byte in `test_starter_layouts.py`. LED cathode polarity and the
  protection's 1 mm pad-to-via ground return are proved. Host connector routing is
  authored in each usage. No GUI layout or human review was performed, so this literal
  manual task remains open despite the focused capture proofs passing.

- [ ] 2.2 KiCad: usage boards of the five blocks for targets 9 and 10 in `tests/kicad/blocks/` (read-back and DRC, c0270 and c0271). Proof: `uv run pytest tests/kicad/blocks` in the KiCad jobs on the pushed head.

  Supplementary proof — local KiCad 9.0.2: five usage readbacks and five full DRC/
  connectivity/parity checks passed; ten target-10 cases were skipped by the installed
  major guard. Exact 9.0.9/10.0.6 CI on the pushed integrated head has not run and remains open.

## 3. Records, docs and guide

- [x] 3.1 Records complete: parameter metadata (c0268's `param`, `REQUIRED` for `protection`, `clamp` and `abs_max`), port docs, sources, and the five rows of the blocks' `VERSIONS.toml` (scenarios "The five blocks are listed", "The starter library passes its own tests", "Sources registered"). Proof: `uv run pytest tests/unit/blocks/test_starter.py tests/unit/blocks/test_versions.py tests/unit/test_provenance.py -q`.
- [x] 3.2 The expectations, usage and layout sections of c0268's `tools/gen_block_docs.py`, and `docs/blocks/` (index and five pages), linked from `docs/dsl.md` (scenario "Pages up to date"). Proof: `uv run pytest tests/unit/blocks/test_block_docs.py tests/consistency -q`; `uv run python tools/gen_block_docs.py --check`.
- [x] 3.3 Agent guide: a tested line for `fenolite.blocks` on `design-script` (the five names and `design.use`), then `uv run python tools/gen_agent_guide.py`. Proof: `uv run pytest tests/unit/agent -q`; `uv run python tools/gen_agent_guide.py --check`.
- [x] 3.4 Write the list of later blocks (decision 10) into `docs/blocks/index.md` under "Later". Proof: `uv run python tools/gen_block_docs.py --check`.

## 4. Closing

- [ ] 4.1 Run `make check-fast`, then the required CI jobs on the pushed head of the branch (unit and KiCad jobs). Proof: `make check-fast`, and the required jobs green on the exact commit.

  Pending: the coordinating branch owns the serialized full local gate and publication.
  No full suite, push or exact-head CI was performed from this worker branch.
- [x] 4.2 Evidence: record the measurements of `H-G-STARTER-ENCLOSURE` in `docs/hypotheses.md`, check that each record's evidence is the lowest of its sources, and regenerate the evidence matrix. Proof: `uv run pytest tests/unit/test_hypotheses_register.py -q`; `uv run python tools/gen_evidence_matrix.py --check`.
- [x] 4.3 Add an entry to `CHANGELOG.md` under `## [Unreleased]`. This waits for `0.7.0.dev0`: on `0.6.0` the v0.6 guard requires `[Unreleased]` empty. Proof: `uv run pytest tests/unit -k changelog -q`.

## Focused proof record — 2026-11-01

- Starter/dependency selection: 392 passed; reviewed-family precedence/proposed exclusion: 2 passed.
- Agent guide plus consistency: 786 passed, 60 expected skips.
- Copied-layout/manual-intent ownership regressions: 54 passed, including cacheless CAD edit/deletion rebuilds.
- Every per-ID `blocks test` and the all-block run: exit 0, five usages and equal goldens, 16 plain tests.
- One reviewed final golden plan writes all five; sources S-1120..1125 were read for facts, nothing copied.
- Source lint/format/types, residue, all generated checks, versions and strict OpenSpec pass.
- Changelog selection: 8 passed, 1 optional-SDK skip.
- No full local gate, manual GUI review, push or exact-version CI claim is made here.
