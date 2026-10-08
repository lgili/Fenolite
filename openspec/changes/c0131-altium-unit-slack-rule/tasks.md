## 0. Derivation

- [x] 0.1 Work out, before proposing, what the file unit is in nanometres, by how much the conversion to whole nanometres can move each kind of item, and what "one file unit per item of the pair" gives for each pair kind; write it into the design, with an open decision wherever the worst case is above the rule. Write the MODIFIED delta from the text the design names. Proof: `openspec validate c0131-altium-unit-slack-rule --strict --no-interactive` passes.
  - **2026-10-07.** The unit is 2.54 nm. Bounds per item: track and via 0.96 nm, a vertex of a pour 0.71 (1.21 at a bridge), a round pad 2.37, a rectangular pad 3.18, an arc the check's own band of 1 001 nm. The rule gives 5.08 nm for a pair; in whole nanometres, rounded down, 5: the constant of c0088. Two open decisions are in the design: the 25 findings that are 3.1 to 7.9 units short, which the rule cannot reach, and a pad against a rectangular pad (5.55 and 6.36 nm), which the rule does not cover and no document shows. The arc of c0127 was read on the branch `c0127-c0128-rewrite-followups` (commit `5b07b481`): it changes the arc's bag, not the three points the check reads. Validation: valid.

## 1. The rule

- [x] 1.1 Replace the constant by the derived ones (`FILE_UNIT_NM`, `SLACK_UNITS_PER_ITEM`, `PAIR_SLACK_NM`, `UNIT_SLACK_NM`), with the derivation in the docstring and one row on `docs/formats/altium/import.md`. Proof: `uv run pytest tests/unit/backends/altium/test_frame.py tests/unit/test_format_facts.py tests/unit/test_provenance.py -q`; `uv run pyright src`.
  - **2026-10-07.** `_with_unit_slack` is unchanged; the view can only lower a rule's value, and since every pair has two items one constant is the rule applied pair by pair. `checks/` is not touched.
- [x] 1.2 Tests at the bound and one nanometre inside it on authored Altium records; cite the test that KiCad judging is strict. Proof: `uv run pytest tests/unit/backends/altium/adapter/test_rules.py -k "one_file_unit or one_nanometre" -q`; `uv run pytest tests/unit/checks/test_copper.py -k strict_comparison -q`.
  - **2026-10-07.** Records: gaps of 254 000, 253 995 (two units inside, the bound) and 253 992 nm (three units inside): no finding, no finding, one. The file's grid is the unit, so "one nanometre inside" is tested on the model (253 994 nm: one finding). `test_strict_comparison` (c0029) is the KiCad-side test: exactly at the clearance no finding, 1 nm inside one; it is cited in the spec's scenario and not copied.

## 2. Measurement

- [x] 2.1 Measure the eight public PCB documents again: per document the findings the slack removes, by shortfall, and the findings of the class of `-03` and `-01` that stay. Update `docs/evidence/altium-roundtrip.md` and the design. Proof: `FENOLITE_HEAVY=1 uv run pytest tests/corpus/test_altium_copper.py -k "not parity" -q`.
  - **2026-10-07.** Removed: 626, 0, 359, 118, 232, 0, 112, 4 628 (6 075; all 1 to 4 nm short). Stay: 2 on `-01`, 7 on `-03`, 16 on `-08` (8 to 20 nm short). Every count equals the one before this change: the constant did not move. `test_copper` asserts for every document that each finding the slack removes is short by `UNIT_SLACK_NM` at most; its pinned rule counts hold.

## 3. Closing

- [x] 3.1 Update `docs/cli-contract.md`, `CHANGELOG.md`, `openspec/README.md`, `docs/roadmap.md` and `LEGAL-ANNEX.md`; regenerate the evidence matrix last; run the fast checks on this tip of the stack. Proof: `uv run python tools/gen_evidence_matrix.py`; `make check-fast`; `openspec validate --all --strict`; after `git add -A`, `uv run pytest tests/residue tests/corpus/test_manifest.py tests/unit/test_evidence_matrix_page.py -q`.
  - **2026-10-07.** The changelog line says in bold that no finding changes (there is no change of behaviour to announce). The counts of the runs are in the final report of the stack.
- [ ] 3.3 The maintainer's Altium session 2, steps D4 to D6 of `openspec/changes/c0088-altium-light-drc/design.md` ("Session 2: the same copper in Altium's own check"): required, not optional. Proof: c0131's design holds his one-line answer under "Decisions (2026-10-07)", and the follow-up it names is opened or closed.
  - **2026-10-07.** Open: no Altium step is run by an agent. The document, the rule, the pad, the net and the places are written out; nothing is built.
  - **2026-10-08 (release 0.3.0).** The answer is in the design, "Decisions (2026-10-07)", item 5 (S-0616): D4 done with the Clearance rules only; D5, Altium Designer 26.5.0 shows 0 violations where Fenolite reports 7; D6, pad `J2-1` shows 63.78 × 63.78 mil (two decimals), which agrees with 63.7795 mil. The follow-up that the design names for N = 0 is proposed as c0152 and not opened, so the task stays open until it is.
- [ ] 3.2 Run the full suite once on the rebased branch. Proof: `make check` passes.
  - **2026-10-07.** Not run here: the coordinator runs it once at the merge.
