# Router role-field evidence (c0366)

## Scope and provenance — 2026-11-03

Only authored Fenolite fixtures are inputs. Existing registered primary sources S-0851, S-0852,
S-0854 and S-0890 motivate confirmed switching/ground intent and user-supplied insulation distances;
no new physical limit, table, third-party router code or private board is introduced. The existing
H-G-ROLE-NEAR-SW profile is reused. Costs are authored software heuristics, not source-derived
physical predictions. Routing consumes frozen data without importing the roles/check packages.

Ground reference uses the existing current-fill validator, then accepts only saved polygons on
adjacent copper layers, with a resolved board boundary. Simulation, outlines, stale, island-marked
and validation-limited fills remain unknown. Coverage is a swept whole-segment lower bound;
switching exposure is a whole-segment upper bound. Unconfirmed reference length does not establish
an absence of copper. Neither bound certifies return impedance, EMC or safety.

Explicit pair limits are conservative all-layer XY projections of the largest declared clearance,
creepage, embedded and laminate-insulation distance. This is not a creepage or field solver.
Aggressor zones use a disclosed conservative outline envelope. Inferred net/group roles never
become binding. Hard exclusions and final copper/confirmed-group judges cannot be traded for
length; joint acceptance recompiles against all newly proposed copper before planning writes.

## Local focused proofs

- Layer-boundary correction: 102 tests (import graph plus all field/candidate proofs), exit 0.
- Contract: 9 authored tests, exit 0.
- Compiler: 15 authored tests, exit 0 (model/edge boundary paths also exercised by native proofs).
- Costs/hard constraints: 8 authored tests, exit 0, including a longer referenced detour.
- Candidate/CLI: 18 authored tests, exit 0; provenance, conservative facts, final judges,
  joint-acceptance rejection and reviewed dependency invalidation, including sidecar creation.
- Guide: 54 tests, exit 0; generated command list, tested options/fields and existing size limits.
- Native KiCad 10.0.6: 6 cases, exit 0. Two/four-layer valid-reference and stale-reference detours
  are reviewed, accepted with DRC gating and close one physical connection without increasing DRC
  violation counts. Missing HV limits refuse before any write and preserve the original DRC result.
- Prior c0365 search/CLI/field regression: 57 tests, exit 0 after the integration.

During iteration, authored tests caught API spelling mistakes in fixtures, a missing fixture import,
a fact key mismatch, guide size limits and the real distinction between model outlines and read
Edge.Cuts graphics. Failed/interrupted attempts are not passes; the counts above name completed
successful reruns. Native output is locally observed evidence, not pinned-CI graduation.

## Reproducible authored input/test sources

Hashes identify the local proof inputs, not an unpublished commit or a CI run.

| Source | SHA-256 |
| --- | --- |
| `tests/_rolefieldbench.py` | `11ea554c4f0d1ad7df0d9de69c9a9574f104d26de006526a776727fc21c0f35c` |
| `tests/_rolefieldproject.py` | `acab7d5ee8f49547cc596ee106fc681cda2cba5a83b4f927d3198dbd45603051` |
| `tests/_search_project.py` | `0664f2b64e6c1f1eb163673de2080705b77e20fc46b5515ca9838ee8fb6b483c` |
| `tests/unit/roles/test_search_fields_contract.py` | `7a1c22e1730a2b57b9e15af7683b27cfeff293b69461fc54728bf1ddb93e641b` |
| `tests/unit/roles/test_search_fields.py` | `3d8d566e2ca709b9d06d16c008d63d63736056b8ac6f7f0308e66803e9c6f7f2` |
| `tests/unit/routing/test_search_fields.py` | `b3b0d723b26534f04ab2caf02228f6a7cd1c5104f5aaf8d75705f06f2b5e863e` |
| `tests/unit/routing/test_search_role_candidates.py` | `e5eadf71341c97e99a63ceebac9d7115a23a79683eb55fb262d15482611dc690` |
| `tests/kicad/routing/test_search_roles.py` | `9d51cfc17130358c6e29d082aa1c308208e029bb589d45b54b6b49252a9f53e2` |

## Closing status

First full quick gate: exit 2; 1 failed, 15706 passed, 43 skipped, 1483.97 seconds.
The sole failure was the existing import-graph guard: roles must not import routing. The compiler
was moved to CLI orchestration without weakening the guard. Final complete quick gate passed, exit 0: 15707 passed, 43 skipped in 1114.54 seconds.
Command: `make check-fast PYTEST_PARALLEL="-n 8 --maxprocesses 8 --dist loadfile -x"`.
This includes all quick tests (stop-on-failure does not filter the test selection), Ruff, format,
Pyright and residue checks. No source changed during that final run. Exact-head GitHub CI is unavailable: the user authorized a local
commit of c0365 and explicitly prohibited pushing. A local c0366 commit is authorized on 2026-11-03; pushing remains forbidden and the change is unarchived.
H-G-SEARCH-ROLE-FIELDS and H-G-SEARCH-ROLE-COSTS are INFERRED from authored proofs.
H-K-SEARCH-ROLE-DRC remains UNKNOWN until required pinned CI targets judge the exact implementation
commit. Local KiCad 10.0.6 success does not establish KiCad 9 parity, native Altium verification,
arbitrary-board completion, exhaustive exploration or electrical certification.

## Exact-head CI — 2026-11-05

CI run 41968083051 (head 5f46b8d7) concluded success: H-K-SEARCH-ROLE-DRC is KICAD-VERIFIED (9.0.x, 10.0.x). Earlier statements that this row stays `UNKNOWN` until CI are superseded by this run. Native Altium and maintainer checks named above stay open.
