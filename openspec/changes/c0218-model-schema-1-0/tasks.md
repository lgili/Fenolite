## 0. Entry check

- [ ] 0.1 Read `openspec/specs/design-model/spec.md`, `openspec/specs/canonical-serialization/spec.md`,
  `docs/design-model.md` and the open questions of the design; record the maintainer's answers under this
  task. Proof: `openspec validate c0218-model-schema-1-0 --strict`.
  - 2026-10-27: the maintainer accepted the recommended answers of questions 1 and 2 (roadmap, "Open decisions",
    row 49): the version is `"1.0"`, and a reader refuses a newer minor. Question 3 is task 1.2.

## 1. Review and fixtures

- [ ] 1.1 `tools/model_review.py`: the list of every model dataclass, field, type, default and extension-bag key
  with its readers (scenario "The review lists every field"). Proof: `uv run python tools/model_review.py`
  writes the list.
- [ ] 1.2 **Maintainer.** Decide keep, rename or drop for each item of 1.1; record the decisions under this
  task. Proof: the record under this task.
- [ ] 1.3 `tools/model_fixtures.py`: build `examples/blink_2layer` with each tag `v0.1.0` to `v0.5.0` in a
  temporary worktree and commit `tests/data/model/<tag>/` with the tag's commit in a `SOURCE` file. Proof:
  `uv run python tools/model_fixtures.py --check` finds every folder and its commit.

## 2. Versions and migration

- [ ] 2.1 `fenolite.model.migrate` (`Step`, `STEPS`, `migrate`) with the step `"0" -> "1.0"` and the decisions
  of 1.2; `SCHEMA_VERSION = "1.0"`, `parse_version` and `readable`; the `v1` layer schemas, the `v0` files
  kept (scenarios "A build writes 1.0", "The v0 schemas stay"). Proof: `uv run pytest tests/unit/model tests/unit/test_schema_drift.py -q`.
- [ ] 2.2 `canonical.load_dir` migrates in memory and gives `model.migrated`; future versions refused with
  `FEN-3002` (scenarios "Every release's folder loads", "A current folder is not migrated", "A newer minor is
  refused", "A v0 board validates after migration"). Proof: `uv run pytest tests/unit/model/test_migrate.py -q`.
- [ ] 2.3 Run the step on every model folder the unit tests and the examples build, and on each document of
  `tests/data/model/`. Proof: `uv run pytest tests/unit/model/test_migrate.py -q -k corpus_of_the_tests`.
- [ ] 2.4 `fenolite migrate DIR` (scenarios of "Migrate command"); `docs/cli-contract.md`, "migrate"; the
  agent guide (run `uv run python tools/gen_agent_guide.py`); `model.migrated` in `fenolite explain`. Proof:
  `uv run pytest tests/unit/cli/test_migrate_cmd.py tests/consistency tests/unit/agent/test_pages.py tests/unit/cli/test_explain_cmd.py -q`.
- [ ] 2.5 `docs/design-model.md`: the version rule and the list of what each version added; the notes of
  each earlier change that "`schema_version` stays `0`" point to it. Proof: `uv run pytest tests/unit/test_design_model_page.py -q`
  (new: the rule and the version list are present).

## 3. Closing

- [ ] 3.1 Run the tests and the residue scan. Proof: `make check-fast`.
- [ ] 3.2 Update the evidence labels: none changes; no format claim. Proof:
  `uv run pytest tests/unit/test_hypotheses_register.py -q`.
- [ ] 3.3 Update `CHANGELOG.md` under `## [Unreleased]`, with the decisions of 1.2. Proof:
  `uv run pytest tests/unit/test_release_record.py -q`.
