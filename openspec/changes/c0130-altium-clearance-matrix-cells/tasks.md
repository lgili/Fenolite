## 0. Entry check and measurement

- [x] 0.1 Read what `item_kind` can say in `src/fenolite/model/rules.py` and how `checks/clearance.py` and `checks/copper.py` apply it; measure the four Clearance records of form C against it and write the table into the design ("Measured before"). Write the MODIFIED deltas from the texts the design names. Proof: `openspec validate c0130-altium-clearance-matrix-cells --strict --no-interactive` passes.
  - **2026-10-07.** `Selector("item_kind", …)` matches `RuleSubject.item_kind`, which the resolver sets to `track` (track, arc), `via`, `pad` or `zone` (a fill); a rule with two selectors applies in either order of the two items. No kind tells an arc from a track or a through-hole pad from a surface pad, and the check holds no item for a free fill, a region, text or a hole. Measured: of the four records one is exact and free of another blocking key (`-08`, priority 4); `-02` and `-06` hold mixed pairs and the option of form D; the other record of `-08` has a scope outside the grammar. The proposal says so in its head. Five MODIFIED requirements, four from c0125's deltas and one from c0088's; `openspec validate c0130-altium-clearance-matrix-cells --strict --no-interactive`: valid.

## 1. Registers

- [x] 1.1 Add the fact rows and "Cells of an object matrix" to `docs/formats/altium/rule-file.md`, the two bag keys to `import.md`, the row `H-A-RULE-CLEARANCE-CELLS` to `docs/hypotheses.md`, and extend the row of S-0558. Proof: `uv run pytest tests/unit/test_provenance.py tests/unit/test_format_facts.py tests/unit/test_hypotheses_register.py tests/unit/backends/altium/read/test_text_tables.py tests/unit/backends/altium/adapter/test_ext.py -q`.
  - **2026-10-07.** No new source: the block S-0590 to S-0594 is not used. Three fact rows (two `INFERRED`, one `CORPUS-VERIFIED` by `test_clearance_forms`).

## 2. Cells

- [x] 2.1 Read a matrix in item kinds (`read_matrix`, `MATRIX_KINDS`), give one rule per exact cell beside the rule of `GAP`, refuse a matrix with a mixed pair with a reason that names it, keep the entries without an item in the bag, and count the cells (`RuleMapping.matrix_cells`). Scenarios "One cell", "Cells of the poured polygons", "A cell without a counterpart", "Cells of a scoped record", "Text that is no matrix". Proof: `uv run pytest tests/unit/backends/altium/read/test_rule_map.py tests/unit/backends/altium/test_rulemap.py -q`.
  - **2026-10-07.** c0125's scenario "A matrix of differing clearances" is replaced: its record (a track-to-track entry equal to `GAP` and a hole entry) now maps, with the hole entry named in the bag. c0084's round-trip tests are green without a change.
- [x] 2.2 Carry the cell rules through the import (bag, native id) and show that a cell governs above the generic rule of its record (scenario "Cell rules in the import"). Proof: `uv run pytest tests/unit/backends/altium/adapter -q`.
  - **2026-10-07.** The order is that of `checks.clearance.rule_precedence` (one priority, the later name governs); the test asks the resolver for via to via, via to track and arc to pad.
- [x] 2.3 Count the cells in the rules source and in the stage summary (`DesignRules.clearance_cells`, `summary.clearance_cells`; scenario "Cells are counted"). Proof: `uv run pytest tests/unit/backends/altium/adapter/test_rules.py tests/unit/checks tests/unit/cli/test_check_altium_copper.py tests/unit/cli/test_build_altium_guard.py -q`.
  - **2026-10-07.** `checks/copper.py` and `checks/clearance.py` are not changed; `checks/documents.py` adds the key beside `unpoured` and `zones_unjudged`. A cell without a counterpart is not scoped to its pairs: design, decision 5, with an open decision for the maintainer.

## 3. Measurement after

- [x] 3.1 Run the copper check on `-02`, `-06` and `-08` (`FENOLITE_HEAVY=1`), explain every finding class, pin the counts, and update `docs/evidence/altium-roundtrip.md` and the design ("Measured after"). Proof: `FENOLITE_HEAVY=1 uv run pytest tests/corpus/test_altium_rule_kinds.py tests/corpus/test_altium_copper.py -k "not parity" -q`.
  - **2026-10-07.** 27 passed. `-02` and `-06`: unchanged (0 rules; 27 and 8 cells unjudged). `-08`: 1 record mapped and 3 unread, a rule of 4 mil and a via-to-via rule of 3.5 mil, 60 253 pairs judged and none for shorts only, 28 shorts and 17 clearance findings, `UNVERIFIED`. The heavy document joins `test_copper`; it was in no copper test before. 16 findings are the class of the unit (8 to 13 nm short; c0131). 28 shorts and 1 clearance finding are a limit of the import (a via without a pad on inner layers), pinned by `test_known_false_findings_of_padless_vias_c0132` and listed for a follow-up; they do not depend on this change.

## 4. Closing

- [x] 4.1 Update `docs/altium.md`, `docs/cli-contract.md`, `CHANGELOG.md`, `openspec/README.md`, `docs/roadmap.md` and `LEGAL-ANNEX.md`; regenerate the evidence matrix last; run the fast checks. Proof: `uv run python tools/gen_evidence_matrix.py`; `make check-fast`; `openspec validate --all --strict`; after `git add -A`, `uv run pytest tests/residue tests/corpus/test_manifest.py tests/unit/test_evidence_matrix_page.py -q`.
  - **2026-10-07.** See the counts in the commit's report: `make check-fast PYTEST_WORKERS=4` and the corpus and oracle tests are run once on the tip of the stack (c0131), which holds this change; the focused proofs above were run on this commit.
- [ ] 4.2 Run the full suite once on the rebased branch. Proof: `make check` passes.
  - **2026-10-07.** Not run here: the coordinator runs it once at the merge.
- [ ] 4.3 Optional, for the maintainer's second session of Altium work: the author report of `H-A-RULE-CLEARANCE-CELLS` (a board made in Altium with a via-to-via cell of 3.5 mil in a rule of 4 mil, two vias 3.7 mil apart and a via and a track 3.7 mil apart; C1 run the rule check with only Clearance enabled; C2 report which of the two pairs is listed). Expected: the via and the track only. Proof: the row in `docs/hypotheses.md` holds the outcome.
  - **2026-10-07.** Open: no Altium step is run by an agent.
