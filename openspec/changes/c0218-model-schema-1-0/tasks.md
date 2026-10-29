## 0. Entry check

- [x] 0.1 Read `openspec/specs/design-model/spec.md`, `openspec/specs/canonical-serialization/spec.md`,
  `docs/design-model.md` and the open questions of the design; record the maintainer's answers under this
  task. Proof: `openspec validate c0218-model-schema-1-0 --strict`.
  - 2026-10-27: the maintainer accepted the recommended answers of questions 1 and 2 (roadmap, "Open decisions",
    row 49): the version is `"1.0"`, and a reader refuses a newer minor. Question 3 is task 1.2.
  - 2026-10-29, read on `dev` after changes c0204 to c0229: the MODIFIED block "Schema generation and drift
    control" differs from the living requirement only by the major in the path and the scenario "The v0
    schemas stay"; no requirement of `design-model` is modified. `SCHEMA_VERSION` is still `"0"`,
    `canonical.load_dir` refuses any other version, `schemas/fenolite.model.v0/` holds the 10 files of the
    design and `board.json` 34 closed objects. The release tags are `v0.1.0`, `v0.2.0`, `v0.2.1`, `v0.2.2`,
    `v0.3.0`, `v0.4.0` and `v0.5.0` (task 1.3 builds one fixture per tag).

## 1. Review and fixtures

- [x] 1.1 `tools/model_review.py`: the list of every model dataclass, field, type, default and extension-bag key
  with its readers (scenario "The review lists every field"). Proof: `uv run python tools/model_review.py`
  writes the list.
  - 2026-10-29 on `dev`: 104 dataclasses (the 99 of `fenolite.model`, 9 of them stored in no file, and the
    stored `Point`, `Size`, `Issue`, `Evidence` and `Provenance` of `fenolite.core`), 757 fields, 56
    extension-bag keys (40 Altium, 16 KiCad, the slot pairs counted once). `tests/unit/test_model_review.py`
    holds the scenario.
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
