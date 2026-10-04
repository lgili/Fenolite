## 1. Registers

- [x] 1.1 Register `H-K-DSL-MINIMUM` in `docs/hypotheses.md` (backend `kicad`, level `INFERRED`, the test and criterion of `design.md`, result `pending; observed at proposal time (2026-10-04)` with the observation of design "Context"). No new source.

  Proof: `uv run pytest tests/unit/test_hypotheses_register.py -q`; `grep -c '^| H-K-DSL-MINIMUM ' docs/hypotheses.md` prints `1`.

## 2. DSL and model

- [x] 2.1 Add `MINIMUM_KINDS`, `MinimumSpec` and `Rules.minimum(...)` to `src/fenolite/dsl/design.py`; add `KEYS["rule"]` and the rule conversion to `src/fenolite/dsl/convert.py`. Write `tests/unit/dsl/test_minimums.py` for the scenarios "Board and class minimums in the model", "Call order does not matter", "Refused calls" (`design-dsl`) and "Rule ids from the kind and the class" (`design-model`).

  Proof: `uv run pytest tests/unit/dsl -q`.

## 3. Builds

- [x] 3.1 Write `tests/unit/lens/test_build_minimums.py` and `tests/unit/cli/test_build_minimums_command.py` (script to files through `fenolite build`) for the scenarios "Built rules and minimums", "Unchanged without minimums" and "Rebuild replaces the minimums" (`design-dsl`). No writer change is expected; fix `lens/build.py` only if a scenario fails.

  Proof: `uv run pytest tests/unit/lens/test_build_minimums.py tests/unit/cli/test_build_minimums_command.py -q`.
- [x] 3.2 Add the `design-rules` info to `lens.altium._not_lowered` and test the scenarios "Minimums are reported, not written" and "No rules, no report" (`altium-build`) in the same test files.

  Proof: `uv run pytest tests/unit/lens/test_build_minimums.py tests/unit/cli/test_build_minimums_command.py -q -k altium`.

## 4. Oracle

- [x] 4.1 Write `tests/kicad/build/test_script_rules_oracle.py` with the six cases of `kicad-oracle` "Script rule minimums are enforced by kicad-cli", for targets 9 and 10. Record the outcome in the `H-K-DSL-MINIMUM` row with the level the runs support.

  Proof: `uv run pytest tests/kicad/build/test_script_rules_oracle.py -rA` on the local `kicad-cli` 10.0.6 (`FENOLITE_KICAD_CLI` names it when it is not on `PATH`) passes with no skip.

  Outcomes (2026-10-04):
  - `kicad-cli` 10.0.6 (macOS): 12 passed (six cases, targets 9 and 10).
  - `kicad-cli` 9.0.9 (pinned image, already present; only the tool ran in the container, through a wrapper named by `FENOLITE_KICAD_CLI`, on the files built on the host): 6 passed (target 9), 6 skipped by major.
  - The CI jobs `kicad-9` and `kicad-10` have not run this file yet.

## 5. Documentation

- [x] 5.1 `docs/dsl.md`: the API line, the section "Design rules" (kinds, scopes, priorities, what KiCad files hold them, the class-clearance rule of design Decision 4, the Altium report) and the `rule` key row. `docs/design-model.md`: the key row. `docs/altium.md`: the `altium.not-lowered` row.

  Proof: `uv run pytest tests/unit/dsl tests/unit/test_format_facts.py -q`; `grep -c 'rules.minimum' docs/dsl.md` prints at least `3`.

## 6. Closing

- [x] 6.1 Run the tests and the residue scan.

  Proof: `make check-fast`; `uv run pytest tests/unit/dsl/test_minimums.py tests/unit/lens/test_build_minimums.py -q`; `openspec validate c0054-dsl-rule-constructor --strict`.
- [x] 6.2 Update the evidence labels: the `H-K-DSL-MINIMUM` row holds the level and the dated result of the runs made.

  Proof: `uv run pytest tests/unit/test_hypotheses_register.py -q`.
- [x] 6.3 Update `CHANGELOG.md` under `## [Unreleased]`.

  Proof: `grep -c 'c0054' CHANGELOG.md` prints at least `1`.
