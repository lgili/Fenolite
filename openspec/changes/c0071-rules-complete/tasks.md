## 0. Entry check

- [ ] 0.1 Read the living `rules-model`, `kicad-file-backend`, `design-dsl` and `kicad-oracle` specs and `openspec list`. Write under this task, with the date: whether another change modified one of the requirements this change modifies (then re-base the MODIFIED text on the living one), and the committed values of `SELECTOR_SUPPORT`, `FLOOR_OVER_RULES`, `RULES_OVER_CLASSES` and `MINIMUM_KEYS`. Proof: `openspec validate c0071-rules-complete --strict --no-interactive` passes after any re-base.

## 1. Probes first

- [ ] 1.1 Add the rows `H-K-DRU-KIND-2`, `H-K-DRU-COURTYARD` and `H-K-PRO-MIN-RULE-3` to `docs/hypotheses.md` (backend `kicad`, level `INFERRED`, the tests and criteria of `design.md`, result `pending`). Proof: `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_provenance.py`.
- [ ] 1.2 Write `tests/kicad/rules/test_rule_kinds_new.py` with the six benches, the scoped canary and the courtyard selection probes, and extend `_rulebench.py` where a bench needs it (a footprint pair at a given courtyard gap, a lone via of a given ring). Record the outcomes, and write the kinds' DRC types to `docs/formats/kicad/drc.md` and the dialect rows to `docs/formats/kicad/rules.md`, with sources S-0020 and S-0029. Proof: `uv run pytest tests/kicad/rules/test_rule_kinds_new.py -rA` on the local KiCad 10.0.6 and inside the pinned 9.0.9 image; `FENOLITE_PROBES_WRITE=1` updates both probe files; `uv run pytest tests/kicad/test_probe_results.py tests/unit/test_format_facts.py`.
- [ ] 1.3 Write `tests/kicad/rules/test_rule_floors.py` with the four `pro-min-rule-<kind>-tM` probes, and record them. Proof: as task 1.2. When a probe records `absent`, write under this task which kind and major take Decision 7's fallback.

## 2. Model and lowering

- [ ] 2.1 Add the six kinds to `RuleKind` and regenerate the rules schema. Proof: `uv run pytest tests/unit/model tests/unit/test_schema_drift.py`; `uv run python tools/gen_schemas.py --check` exits 0.
- [ ] 2.2 Add the constraint table, `KIND_SELECTORS`, `KIND_SUPPORT` (pinned to the probe files), the `Reference` writer for courtyards and `rules.kind-unchecked` to `rulemap` and `lowering` (scenarios of "Rule kinds and limits", "Closed selector grammar", "Kind support by major", "Lowering refuses what it cannot represent" and "Rule issue codes"). Proof: `uv run pytest tests/unit/backends/kicad/test_rulemap.py tests/unit/backends/kicad/test_lowering.py`; `uv run pyright src`.
- [ ] 2.3 Lift the new kinds in `read_rules`, and keep a courtyard rule by membership opaque (scenarios of "Custom rules files are read and written"). Proof: `uv run pytest tests/unit/backends/kicad/test_dru.py tests/unit/backends/kicad/test_lowering.py -k self_check`.
- [ ] 2.4 Apply Decision 7's fallback for every kind and major of task 1.3, if any: the key in `MINIMUM_KEYS`, a scenario in `test_lowering_minimums.py`, and the tables test. Proof: `uv run pytest tests/unit/backends/kicad/test_lowering_minimums.py`.
- [ ] 2.5 Make the unit scenarios that expect `kicad.project.rule-below-minimum` set `FLOOR_OVER_RULES` themselves, as the modified "Conflicts with board-setup minimums are reported" states, and check that no test relies on the old claim. Proof: `uv run pytest tests/unit/backends/kicad/test_lowering_minimums.py`.

## 3. DSL

- [ ] 3.1 Write `src/fenolite/dsl/select.py` and re-export `select` (scenarios of "Selectors in the DSL"). Proof: `uv run pytest tests/unit/dsl/test_select.py tests/unit/test_import_graph.py`.
- [ ] 3.2 Add `Rules.rule`, `RuleSpec` and the model rules in `to_model` (scenarios of "Rule constructor in the DSL" and "Rule minimums in the DSL"), and a design under `tests/data/rules/` with one rule per new kind for the build tests. Proof: `uv run pytest tests/unit/dsl/test_rule_constructor.py tests/unit/dsl tests/unit/cli/test_build_cmd.py`.

## 4. Oracle

- [ ] 4.1 Extend `tests/kicad/rules/test_rule_order.py` with the two `hole_to_hole` rules, and build the rules design of task 3.2 on both majors: its `.kicad_dru` loads, and each rule gives its violation on a bench placed in the design. Proof: `uv run pytest tests/kicad/rules -rA` on both majors.

## 5. Documentation

- [ ] 5.1 Update `docs/formats/kicad/rules.md` (the kind table with DRC types, the per-kind selectors, the scoped canary, the creepage and silk facts), `docs/dsl.md` ("Design rules": `rule()` and `select`) and `docs/cli-contract.md` (`rules.kind-unchecked`). Proof: `uv run pytest tests/consistency tests/unit/test_format_facts.py tests/residue`.

## 6. Closing

- [ ] 6.1 Run the residue and full test suites. Proof: `uv run pytest tests/residue` and `uv run python tools/residue/scan.py` exit 0; `uv run python tools/gen_schemas.py --check` exits 0; `make check` passes; `openspec validate c0071-rules-complete --strict --no-interactive` passes; `gh pr checks` shows `unit`, `kicad-9` and `kicad-10` passing.
- [ ] 6.2 Update the evidence: the three rows become `KICAD-VERIFIED (9.0.x, 10.0.x)` with their per-major outcomes (creepage `absent` on 9.0.9 is part of the verified statement), or record what failed. Proof: `uv run pytest tests/unit/test_provenance.py tests/unit/test_hypotheses_register.py`.
- [ ] 6.3 Add to `CHANGELOG.md` under Unreleased: "Six more rule kinds (hole to hole, hole clearance, annular width, courtyard, silkscreen, creepage) in the model, the `.kicad_dru` writer and reader, and `design.rules.rule()` with selectors from `fenolite.dsl.select`; creepage rules are written for KiCad 10 only". Update `docs/roadmap.md`. Proof: `git diff --stat CHANGELOG.md docs/roadmap.md` lists both files.
