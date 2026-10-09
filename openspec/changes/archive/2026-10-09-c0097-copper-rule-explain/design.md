## Context
c0097 belongs to the new v0.4 and is rebased on current origin/dev. The copper checker already
resolves clearances with backend switches and handles banded arcs near fills. Its numeric findings
and CLI output are the contract. An earlier draft mixed electrical profiles with diagnostics;
this change retains only diagnostic metadata and grouping.

The review found entity-bearing explanations unhashable and arc/fill explanations inconsistent
with the actual judgment. The previously proposed track-size diagnostic has no real producer
and is removed rather than adding a new verdict. Existing second-backend checks supply scoped
item-kind rules and may adjust values before the resolver sees them.

## Goals / Non-Goals
Goals: immutable hashable explanations, faithful actual resolver inputs, full candidate identity,
existing layer/kind precedence, and grouping every finding once without modification.
Non-goals: new verdicts, electrical profiles (c0098), exemptions, design advice, schemas, CLI output,
backend writers, areas, pairs, waivers, impedance and power. No private design data or new source ids.

## Decisions
1. **Attach at judgment.** Store the explanation on the existing finding, with a default of None.
   Rejected computing it later: the selected resolver call and arc baseline are no longer available.
   The arc fallback explains without the zone argument; it never overwrites a governing value.
2. **Candidate value rows.** Frozen rows carry source, value, severity and optional rule id,
   priority, layers and selectors. Subjects and selectors are frozen model values, not entities.
   Rejected Rule entities: their mutable bags make frozen findings unhashable. Rejected source-name
   parsing: rule names need not be unique. New sources add rows, not fields to the explanation.
   The resolver's candidate matcher and class helper are shared; no diagnostic matcher is added.
3. **Relation from pad records.** Footprint ids already supplied by BoardPad identify whether two
   pads belong to one footprint. Rejected inferring identity from display references or geometry:
   reference strings and movement are not identity. This is a fact, never an exemption.
4. **Grouping key is (relation, source).** Sort keys deterministically; keep original finding
   objects in their order within each group. Rejected advice and suppressing intrinsic findings:
   neither explains which rule governed. Findings without explanations remain valid group inputs.
5. **Precedence stays numeric.** Existing rule_precedence determines the row order and winner.
   Backend switches remain explicit. Nonpositive zone arguments normalize to absence, as in resolve.
   Rejected duplicating precedence prose in every value; the guide describes it once.

## Files and public API
| File | Public API or responsibility |
| --- | --- |
| src/fenolite/checks/clearance.py | ClearanceCandidate, ClearanceExplanation, ClearanceResolver.explain |
| src/fenolite/checks/copper.py | optional CopperFinding.explanation, relation, CopperReviewGroup, group_findings |
| tests/unit/checks/test_copper_rule_review.py | authored numerical and immutable value proofs |
| docs/copper-rule-explanations.md | precedence, actual judged inputs and diagnostic limits |
| docs/hypotheses.md | H-G-COPPER-EXPLAIN remains INFERRED |
| CHANGELOG.md | one entry under Unreleased |

No model schema, CLI envelope or backend evidence declaration changes. Removed diagnostic module
and test are not replaced by a producer. Shared test_copper.py and coordinator status pages stay
identical to origin/dev.

## Evidence
Public sources already registered: S-0010 and S-0038 for KiCad rule semantics, S-0020 for public
corpus coverage. No new format fact. Diagnostic metadata is INFERRED; existing oracle and corpus
checks support unchanged numeric behavior, not new metadata verified by a native tool.

| Behavior | Named proof test | Evidence |
| --- | --- | --- |
| intrinsic relation survives movement | test_intrinsic_findings_survive_translation_rotation_and_review | INFERRED |
| candidate identity, hashability and matching order | test_selector_and_precedence_are_explained_without_weakening | INFERRED |
| duplicate rule names | test_duplicate_rule_names_preserve_candidate_identity | INFERRED |
| switches and ignored-rule candidates | test_explanation_preserves_floor_zone_switches_and_ignored_rule | INFERRED |
| actual arc baseline resolver call | test_arc_fill_explains_the_call_that_judged | INFERRED |
| zero/negative zone absence | test_nonpositive_zone_is_absent | INFERRED |
| kind/layer tie and arc normalization | test_item_kind_layer_scope_and_arc_normalization | INFERRED |
| every finding grouped unchanged once | test_grouping_preserves_each_original_once_without_advice | INFERRED |

## Relation to other proposals
Read c0103, c0104, c0114, c0105 and c0115 on review-roadmap-complex-board. Areas and differential
pair subjects will have case-sensitive semantics; this change implements neither. Keepout
findings can lack a clearance explanation. Future pair-gap sources should add candidate rows.
Intentional ties and waivers affect which pairs are judged or accepted; grouping only sorts facts.
Impedance targets govern future track-size analysis, while power findings belong to analyze.
All deltas here are ADDED in copper-rule-explanation, with no copper-check requirement modified.

## Risks and Open Questions
Explanations add allocation per finding; existing corpus performance is the regression proof.
A candidate includes selectors and id so duplicate names remain distinguishable. Frozen values
are compatible with Python 3.11; no mapping proxy defaults or extra runtime dependencies.
Backends may adjust limits; the explanation states those judged values and does not reconstruct
original file values. No new source or change id is needed. Native validation of diagnostic
metadata remains open; evidence stays INFERRED. Full-suite execution is reserved for coordinator.

## Implementation notes
The rebase had one conflict, CHANGELOG.md: kept origin/dev text and appended the c0097 line last
under Unreleased. Version and milestone tables were not changed. The gates below ran on the
rebased committed tree; only proof documentation is amended afterward.

### Handover gates (2026-10-07)
Rebase base: `1723472755c16666a19d7b716583c9c9061248cc` (origin/dev at fetch/rebase).
Tested code commit: `aa4eff9cade2e9f2df934d07e5e640984b9ff19d`. Each command's own exit code
was captured directly, without a pipe. Logs are outside the checkout in the c0097-proofs scratch
folder, with the names below. No full `make check`, push, merge or archive was performed.

| Command | Exit | Result/counts | Log |
| --- | --- | --- | --- |
| `openspec validate --all --strict` | 0 | 69 passed, 0 failed | `openspec.log` |
| `make check-fast` | 0 | 9369 passed, 17 skipped | `fast.log` |
| `uv run --isolated --python 3.11 --extra dev pytest tests/unit -q -n 4 -p no:cacheprovider` | 0 | 9090 passed, 2 skipped | `python311.log` |
| `uv run pytest tests/corpus/test_manifest.py tests/residue -q` | 0 | 85 passed | `manifest.log` |
| `uv run python tools/gen_schemas.py --check` | 0 | no differences (no test count) | `schemas.log` |
| `uv run python tools/gen_evidence_matrix.py --check` | 0 | no differences (no test count) | `matrix.log` |
| `python3 tools/dco_check.py origin/dev..HEAD` | 0 | 1 commit checked | `dco.log` |
| `uv run pytest tests/unit/checks -q` | 0 | 493 passed | `checks.log` |
| `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_format_facts.py tests/unit/test_provenance.py -q` | 0 | 66 passed | `facts.log` |
| `FENOLITE_REQUIRE=kicad uv run pytest tests/kicad/copper tests/kicad/rules/test_rule_order.py tests/kicad/rules/test_rule_kinds.py -q` | 0 | 67 passed | `kicad.log` |
| `FENOLITE_REQUIRE=corpus uv run pytest tests/corpus/test_copper_perf.py -q` | 0 | 1 passed | `corpus.log` |

The fast gate includes lint, format, zero type errors and zero residue hits. Its 17 skips are
15 mutating CLI consistency cases, one case-sensitive filesystem test and one opt-in throughput
measurement. The Python 3.11 run skips only the latter two. The corpus test measures costs and
fails on exceptions, not on a time threshold; it does not establish a performance budget.

Earlier iteration proofs exposed an unused import, import ordering and a tasks citation of the
removed hypothesis. Those were corrected without changing any guard test. Focused proofs passed
for hashability, arc/zone consistency, grouping and kind/layer scopes before the handover run.
The required negative search finds no removed API/helper/hypothesis outside this change; the
coordinator status pages and shared test_copper.py have an empty diff against origin/dev.

All seven review fixes are implemented as requested. No disagreement or new id request.
Native verification of the diagnostic metadata remains open (INFERRED), and the coordinator
retains the full-suite and integration work. Final validation, manifest/residue and DCO are
repeated after recording this table and amending the signed commit.


### Post-recording confirmation
After recording the eleven gates and amending, the confirmation below passed on the committed
tree. Task 2.3 was marked only after these proofs passed. The same four commands are repeated
once more after the final task/documentation amendment, with final-*.log files in the scratch
folder. No source or test code changed after the eleven-gate run.

| Command | Exit | Result/counts | Log |
| --- | --- | --- | --- |
| `openspec validate --all --strict` | 0 | 69 passed, 0 failed | `recorded-openspec.log` |
| `uv run pytest tests/corpus/test_manifest.py tests/residue -q` | 0 | 85 passed | `recorded-manifest.log` |
| `python3 tools/dco_check.py origin/dev..HEAD` | 0 | 1 commit checked | `recorded-dco.log` |
| `git diff --check` | 0 | no whitespace findings | `recorded-diff.log` |

The status-page/shared-test comparison exits 0 with empty output. The required removed-API
search exits 1 with no matches (expected negative proof); the branch contains exactly one commit
above origin/dev. The interrupted confirmation was rerun to completion before marking task 2.3.
