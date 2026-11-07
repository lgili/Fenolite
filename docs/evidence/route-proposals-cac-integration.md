# Route proposals on circuits-as-code

Integration record, 2026-11-01. The base is
`8e1b93627830911743cc748d8e7d5f3b0083207d`; the merged router head is
`13419373315b7ba197862f9340c98f2a5dbbb293`, including c0300 to c0305.
The router head has all 13 jobs successful in
[CI run 41294183261](https://github.com/lgili/Fenolite/actions/runs/41294183261).
That run does not establish CI on this integration commit.

The merge keeps the base check pipeline and `circuit.rules`, its LF-preserving library fetches and
output-path validation. Its finding subject ids and copyable edit-conflict resolution commands survive
the move from the old page to TypeScript. Role-group aliases remain available alongside subject lookup.
The old HTML file is removed; the committed bundle is generated from the merged sources.

Documentation and hypothesis rows from both sides are retained. No source id or numeric FEN code is
added. Proposal facts remain `INFERRED`; Altium readback is not an Altium author report. The existing
KiCad distinction remains: zero unconnected items after a KiCad 10 refill, and violation no-growth on
both majors, with the documented stand-in fill on KiCad 9.

The combined written pages exceeded the unchanged guide budgets. Viewer instructions now have a
focused `viewer` topic, while `files` keeps a tested entry and pointer. The topic index and command
references are generated. Written pages remain within 12,000 bytes and 250 lines.

Focused proofs passed:

| Proof | Result |
|---|---|
| `pytest tests/unit/routing tests/unit/view/test_check_overlay.py -q` | 192 passed |
| Proposal subjects, reference boards, proposal CLI, proposal overlays, critical routes and role routes | 98 passed; includes the six complete/accept/replay and Altium readback variants |
| Viewer page, bundle, overlay and project review; capabilities, provenance, hypotheses and CI workflow | 158 passed |
| `pytest tests/unit/cli/test_view_cmd.py -q` excluding the four TCP-server cases | 26 passed, 4 deselected |
| `pytest tests/unit/agent -q -m 'not needs_kicad and not needs_corpus and not needs_libs'` | 117 passed, 19 deselected |
| `pytest tests/residue tests/consistency -q -m 'not needs_kicad and not needs_corpus and not needs_libs'` | 698 passed, 41 expected mutating-command skips, 7 deselected |
| `ruff check .`; `ruff format --check .`; `pyright src` | passed; zero type errors or warnings |
| `tools/build_viewer.py --check`; guide, evidence-matrix and Altium-graduation generator checks | passed |
| OpenSpec 1.16.0 strict validation, c0280 and c0300 to c0305 | seven changes valid |
| `tools/residue/scan.py`; `git diff --check` | zero residue hits; whitespace clean |

All Python commands use the worktree's own offline dev and geo environment. The focused proof does not
claim a complete integration gate, fresh KiCad oracle runs, browser visual checks, or TCP server tests.
Task 7.2 stays open for the serialized complete gate and required CI jobs on the exact integration head.
The separate c0250 conflict-workbench task still owns typed Take code / Take CAD actions; this merge
preserves the copyable command fallback and the existing viewer plan/confirm/receipt APIs for it.
