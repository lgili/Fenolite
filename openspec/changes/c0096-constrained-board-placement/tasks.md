# Tasks

- [x] 0.1 Register the neutral architecture and source/hypothesis plan. Proof: `openspec validate c0096-constrained-board-placement --strict`.
- [x] 1.1 Add mechanical DSL/model fields and schema compatibility. Proof: `uv run pytest tests/unit/dsl/test_board_mechanics.py tests/unit/dsl/test_convert.py tests/unit/dsl/test_ids.py -q`; `uv run python tools/gen_schemas.py --check`.
- [x] 1.2 Add neutral requests, reservations and checker interface with existing hard geometry. Proof: `uv run pytest tests/unit/placement/test_mechanical_constraints.py tests/unit/placement/test_constrained_legality.py tests/unit/test_import_graph.py -q`.
- [x] 1.3 Implement finite deterministic proposals and placement assessment without electrical readiness. Proof: `uv run pytest tests/unit/placement/test_constrained.py -q`.
- [x] 1.4 Add CLI check adapter, confirmed write/readback and both-face previews. Proof: `uv run pytest tests/unit/cli/test_place_constrained.py tests/unit/placement/test_placement_preview.py tests/unit/cli/test_place_cmd.py tests/unit/placement/test_cli_checker.py -q`.
- [x] 2.1 Run tests/residue and handover gates: `openspec validate --all --strict`; `make check-fast`; `uv run pytest tests/corpus/test_manifest.py -q`; `uv run python tools/gen_schemas.py --check`; `uv run python tools/gen_evidence_matrix.py --check`; touched corpus and KiCad placement/frame tests.
- [x] 2.2 Record hypotheses, protocol limitations and public facts. Proof: `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_format_facts.py tests/unit/test_provenance.py -q`.
- [x] 2.3 Update Unreleased and deliver one signed local commit. Proof: `git diff --check`; `python3 tools/dco_check.py origin/dev..HEAD`. No archive before coordinator integration.

## Review corrections

- [x] R1. Refuse DSL board holes for KiCad with a located FEN-3004 script error; keep Altium lowering. Proof: `uv run pytest tests/unit/cli/test_build_mechanical_review.py -q` (new regression fails before correction).
- [x] R2. Bound candidate enumeration by every group region for the footprint, including a far-corner region. Proof: `uv run pytest tests/unit/placement/test_constrained.py -q` (new far-region regression fails before correction).
- [x] R3. Default DSL keepouts to all board copper layers; empty-layer model keepouts judge nothing. Proof: `uv run pytest tests/unit/dsl/test_board_mechanics.py tests/unit/placement/test_constrained_legality.py -q` (new regressions fail before correction).
- [x] R4. State and pin the board-kept keepout rebuild policy; choose to_model-only intent/anchor metadata and remove the lens duck-typed anchor access. Proof: `uv run pytest tests/unit/cli/test_build_mechanical_review.py tests/unit/dsl/test_board_mechanics.py tests/unit/test_import_graph.py -q`.
- [ ] R5. Use the integrated copper relation and typed body-volume provider when both corrected dependencies exist on origin/dev. Proof: `uv run pyright src`; `uv run pytest tests/unit/test_import_graph.py tests/unit/placement/test_cli_checker.py -q`. Pending: origin/dev lacks c0097 relation and c0099 body_volumes; do not invent their contract.
- [x] R6. Copy complete living requirements into MODIFIED deltas for Place command, Identifier derivation and Board and placements in the DSL; separate the DSL package export delta. Proof: `openspec validate --all --strict`.
- [x] R7. Rename image status to estimated, define the general drill-reservation provenance rule, use neutral test wording and regenerate schemas. Proof: `uv run pytest tests/unit/dsl/test_board_mechanics.py tests/unit/placement/test_mechanical_constraints.py -q`; `uv run python tools/gen_schemas.py --check`.
- [x] R8. Remove status/baseline/delivery notes, correct zones docstring and explicit test encoding, document the eight coordinator-owned API conflicts. Proof: `openspec validate --all --strict`; `uv run pytest tests/unit/test_hypotheses_register.py -q`; `git diff --check`.
- [x] R9. Record all requested proof commands, counts and exit codes, and deliver one local signed commit based on origin/dev with subject ending (c0096). No push, merge, archival or full suite.

- [x] R9.1. Document all three constrained placement issue codes in the CLI contract without changing its closed-set guard. Proof: `uv run pytest tests/unit/placement/test_place_codes.py -q` (existing guard failed before the documentation correction).

- [ ] R10. Regenerate the MODIFIED "Board and placements in the DSL" and "Identifier derivation" deltas from the living text and rewrite the ADDED "Mechanical primitives and locked anchors" without `Design.hole(key, …)`, `Design.keepout(…)`, `Design.holes`/`Design.keepouts` and the rows `hole`/`keepout` of `fenolite.dsl.KEYS` (the maintainer's decision 2 of 2026-10-07; c0102 and c0103 "Relation to c0096"). Proof: `openspec validate c0096-constrained-board-placement --strict`.
  - 2026-10-08, integration on `v04-codex`: c0102 and c0103 were on the branch first, so c0096 was taken without those calls, rows, the `to_model` lowering, the KiCad `FEN-3004` refusal and the board-kept keep-out rebuild rule. Kept: `MechanicalIntent`, `Hole.intent`, `Keepout.intent`, `FootprintInstance.anchor`, `Part.place(…, anchor=)`, the planner, the CLI strategy and the previews. `tests/unit/dsl/test_convert.py` (hole ids) was dropped, `tests/unit/dsl/test_board_mechanics.py` and `tests/unit/cli/test_build_mechanical_review.py` were rewritten around the anchor. The spec deltas still describe the branch's calls; this task rewrites them.

## Review proof results — 2026-10-07

| Command | Own exit code | Result |
|---|---|---|
| `openspec validate --all --strict` | 0 | 69 passed, 0 failed (69 items) |
| `make check-fast PYTEST_MAX_WORKERS=4` | 0 | 9397 passed, 17 skipped in 608.10s (0:10:08) |
| `uv run --isolated --python 3.11 --extra dev pytest tests/unit -q -n 4 -p no:cacheprovider` | 0 | 9118 passed, 2 skipped in 1645.48s (0:27:25) |
| `uv run pytest tests/corpus/test_manifest.py tests/residue -q` | 0 | 85 passed in 430.00s (0:07:10) |
| `uv run python tools/gen_schemas.py --check` | 0 | No differences |
| `uv run python tools/gen_evidence_matrix.py --check` | 0 | No differences |
| `uv run pyright src` | 0 | 0 errors, 0 warnings |
| `python3 tools/dco_check.py origin/dev..HEAD` | 0 | No differences |
| `env PYTEST_ADDOPTS='-n 4 --dist loadfile' uv run pytest tests/unit/placement tests/unit/dsl tests/unit/model tests/unit/lens tests/unit/analysis tests/unit/checks tests/unit/cli tests/unit/backends/altium/test_roundtrip.py tests/unit/test_import_graph.py tests/unit/test_hypotheses_register.py -q` | 0 | 3056 passed in 1593.55s (0:26:33) |
| `uv run pytest tests/unit/placement/test_place_codes.py -q` | 0 | 4 passed in 2.05s |
| `uv run pytest tests/unit/analysis/test_surface.py::test_round_board_is_searched_in_seconds -q` | 0 | 1 passed in 8.40s |
| `uv run pytest tests/unit/test_hypotheses_register.py -q` | 0 | 36 passed in 30.68s |

The first broad runs failed because the CLI contract omitted three issue codes; the original guard was retained and passed after the documentation correction. Timing failures under concurrent worktree load were repeated without altering their limits: surface search 31.83 s initially, 8.40 s in the focused retry; Python 3.11 clipping deadline 252.29 ms initially and 0.62 ms on Hypothesis replay. Complete initial and final logs accompany the handover report. No cases were removed or newly skipped.

R5 remains pending because origin/dev at 17234727 lacks the corrected c0097 relation and c0099 body-volume contracts. No push, merge, archival or full make check was performed.
