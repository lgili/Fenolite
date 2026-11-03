## 0. Entry check

- [x] 0.1 Read `openspec/specs/design-model/spec.md`, `openspec/specs/canonical-serialization/spec.md`,
  `docs/design-model.md` and the open questions of the design; record the maintainer's answers under this
  task. Proof: `openspec validate c0218-model-schema-1-0 --strict`.
  - 2026-10-27: the maintainer accepted the recommended answers of questions 1 and 2 (roadmap, "Open decisions",
    row 49): the version is `"1.0"`, and a reader refuses a newer minor. Question 3 is task 1.2.

## 1. Review and fixtures

- [x] 1.1 `tools/model_review.py`: the list of every model dataclass, field, type, default and extension-bag key
  with its readers (scenario "The review lists every field"). Proof: `uv run python tools/model_review.py`
  writes the list.
- [x] 1.2 **Maintainer.** Decide keep, rename or drop for each item of 1.1; record the decisions under this
  task. Proof: the record under this task.
- [x] 1.3 `tools/model_fixtures.py`: build `examples/blink_2layer` with each tag `v0.1.0` to `v0.5.0` in a
  temporary worktree and commit `tests/data/model/<tag>/` with the tag's commit in a `SOURCE` file. Proof:
  `uv run python tools/model_fixtures.py --check` finds every folder and its commit.

## 2. Versions and migration

- [x] 2.1 `fenolite.model.migrate` (`Step`, `STEPS`, `migrate`) with the step `"0" -> "1.0"` and the decisions
  of 1.2; `SCHEMA_VERSION = "1.0"`, `parse_version` and `readable`; the `v1` layer schemas, the `v0` files
  kept (scenarios "A build writes 1.0", "The v0 schemas stay"). Proof: `uv run pytest tests/unit/model tests/unit/test_schema_drift.py -q`.
- [x] 2.2 `canonical.load_dir` migrates in memory and gives `model.migrated`; future versions refused with
  `FEN-3002` (scenarios "Every release's folder loads", "A current folder is not migrated", "A newer minor is
  refused", "A v0 board validates after migration"). Proof: `uv run pytest tests/unit/model/test_migrate.py -q`.
- [x] 2.3 Run the step on every model folder the unit tests and the examples build, and on each document of
  `tests/data/model/`. Proof: `uv run pytest tests/unit/model/test_migrate.py -q -k corpus_of_the_tests`.
- [x] 2.4 `fenolite migrate DIR` (scenarios of "Migrate command"); `docs/cli-contract.md`, "migrate"; the
  agent guide (run `uv run python tools/gen_agent_guide.py`); `model.migrated` in `fenolite explain`. Proof:
  `uv run pytest tests/unit/cli/test_migrate_cmd.py tests/consistency tests/unit/agent/test_pages.py tests/unit/cli/test_explain_cmd.py -q`.
- [x] 2.5 `docs/design-model.md`: the version rule and the list of what each version added; the notes of
  each earlier change that "`schema_version` stays `0`" point to it. Proof: `uv run pytest tests/unit/test_design_model_page.py -q`
  (new: the rule and the version list are present).

## 3. Closing

- [ ] 3.1 Run the tests and the residue scan. Proof: `make check-fast`.
- [x] 3.2 Update the evidence labels: none changes; no format claim. Proof:
  `uv run pytest tests/unit/test_hypotheses_register.py -q`.
- [x] 3.3 Update `CHANGELOG.md` under `## [Unreleased]`, with the decisions of 1.2. Proof:
  `uv run pytest tests/unit/test_release_record.py -q`.

## Current-source selective preparation

- [x] 0.2 Review the current-source selective-port packet in c0216 before runtime changes; preserve
  current model0/CLI0 and every later field/validation. Historical bf6532a4 receipts are source material,
  not current test/freeze proof. Final inventories wait for the actual final c0348 source.

## Isolated candidate proof (maintainer decision still pending)

- Preparation is authorized in an isolated candidate only. Task 1.2 is **not** approved, and 2.1 remains
  pending its actual per-item KEEP/RENAME/DROP decision; root activation, CI and archive remain open.
- The generated review records all decisions as PENDING, with null reviewer/date: 175 dataclasses,
  1251 fields and 40 fixed extension keys. The sole addition to actual model0's 174/1247 is the
  four-field migration helper `Step`; all original names/types/defaults are retained.
- Model0 schema snapshots were captured mechanically from clean source
  `cbd1e08550f74810f8287edb6a9c0d0ae61af773`, after current CLI descriptors: 76 version0 schema
  files including ten model layers. Earlier 20-schema reports described the source before c0217's
  actual descriptor expansion. Capture is byte preservation, not a human approval.
- The real offline fixture helper built every tag v0.1.0–v0.5.0 in disposable worktrees; `--check`
  passed for all five originals. SOURCE records retain exact original tag commits and hashes.
- Focused model/schema/review/docs proof: 940 passed. Version/migration/CLI/review controls previously
  passed 102; independent preservation/schema controls passed 208 and guide/docs passed 103.
  Tests retain exact historical layer byte equality; current writer expectations explicitly name 1.0.
- Preserved current BOM-only validation, positive curve-error units, all fonts/False/zero presence,
  and typed intersheet references. The ten original schema hashes and input compatibility are tested.
- `pyright src`: zero errors/warnings; no evidence labels are promoted. CLI remains v0 and package
  remains 0.7.0.dev0. Final consistency, residue, root check-fast and exact-commit CI are separate gates.

- Final consistency/guide-explanation/register/release/review-tool selection: 921 passed, 42 expected
  mutating consistency skips (their direct command tests run separately). Migration fixture controls:
  91 passed, including five per-file numeric-coordinate proofs. Private staged residue scan: zero hits
  across 87 files; five narrow numeric-code waivers cover only the original authored nm-coordinate
  fixture files, and every private/other pattern remains active. Schema/guide/surface generators and
  strict OpenSpec checks pass. Root check-fast/CI and actual maintainer review remain pending.

## Actual maintainer model0 approval, 2026-11-03

The coordinator received actual user approval of the current original model0
review: KEEP all174 classes,1247 fields and40 extension keys, with original
names/types/defaults unchanged and no rename/drop. Per-item shapes and the
reviewed source/report digest are recorded in model0-approved.json. This
supersedes the earlier pending1.2 status, not the factual dates of old proofs.
The existing175/1251 candidate inventory includes only the additional internal
Step helper's four fields; all174/1247 original shapes remain identical. That
helper is migration machinery, not a new original model0 data entity.

- [x] C.4 Verify the recorded approved original shapes against the actual
  current inventory and rerun model/schema/migration controls. Root integration,
  combined fast/exact-head CI and archive remain separate. CLI staysv0.

Actual approved proof: model/review/schema/migrate focused955passed in11.20s. New approval-shape control compares every original class/field type/default and40 extension keys to the actual candidate; only internal Step4 remains additional. No frozen v0 byte snapshot was relabelled. Root final generated checks/fast/exact-head CI remain open.

## Combined activation proof before root integration

Actual immutable source0 7c1789ae and source1 87e71001 complete75-plan captures
contain the same1137 paths and same exits. Exactly63 meta.json files change;
actual parsed metadata differs ONLY in schema_version0→1.0. Every native CAD
file and other canonical circuit/board/rules/manufacturing file is byte-identical.
No build_bytes golden pin refresh is needed or authorized by this proof.
transition-proof.json binds both source commits, full-map hashes and every
changed file hash. All955 model/migration/schema/approval controls pass.
Combined guide/surface/capability/schema controls pass355 after regeneration,
retaining all later0351/0352/0354 teaching and guards. Final root fast/CI remain
open. CLI remainsv0 and package0.7.0.dev0; only canonical schema activates1.0.

The user separately approved the newly disclosed58th CLI command with the exact
reply "Aprovo incluir migrate" after its1.0 folder/dry-plan/confirm/no-CAD-script
scope was explained. This complements the original57-command API review; it
does not rewrite the original reviewed packet or old pending observations.
