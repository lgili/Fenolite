# Bounded router search evidence (c0365)

## Contract recorded before implementation — 2026-11-03

Source S-1309 supplies only the published A* idea: choose a frontier state using the
known cost plus a lower bound on remaining cost, and update a state reached more cheaply.
No router source, third-party implementation, figure, graph or pseudocode is copied.
All graphs and physical fixtures in this change are authored for Fenolite.

The sparse state is `(x_nm, y_nm, copper_layer_index, incoming_direction, vias_used)`.
Direction and via count must not be collapsed into position/layer alone. Movement and
heuristic costs are integers; heuristic admissibility is checked on tiny authored graphs
against an independent label-setting Dijkstra oracle with a linear scan, not the production
priority queue. Deterministic limits bound discovered states as well as work. Clock expiry
is an explicitly different termination reason from exhausting a finite graph or a state cap.

The geometry adapter owns exact endpoint stubs, swept-edge/cutout checks and through-via
clearance across every copper layer. Search never changes the board. Proposed geometry is
still judged by existing copper/role checks and accepted only through a reviewed plan.
No electrical rule, fabrication grid or physical via size is inferred from this algorithm.

| Hypothesis | Required proof | Current evidence |
| --- | --- | --- |
| H-G-SEARCH-GRID | Authored graphs, independent minimum-cost oracle, deterministic/resource-limit cases | INFERRED; focused kernel tests pass locally |
| H-G-SEARCH-GEOMETRY | Authored endpoints, cutouts, diagonal sweeps and four-layer via-barrel obstacles | INFERRED; focused physical tests pass locally |
| H-K-SEARCH-DRC | Pinned KiCad CI judging accepted authored routes | UNKNOWN for pinned CI; local focused KiCad tests pass |

The source does not imply continuous-space optimality, arbitrary-board completion, or a
performance guarantee. Fixed grid/resource limits can miss a physically possible route.

## Local implementation proofs — 2026-11-03

- Contract oracle: 4 tests passed before the kernel was implemented.
- Integer kernel: 16 tests passed, including reopening, stable ties, independent minima, state
  discovery bounds and cancellation. There is no continuous-space optimality claim.
- Geometry: authored two/four-layer cases pass; endpoints stay exact, diagonal sweeps and cutouts
  are checked, and a through via blocked on an inner layer is refused.
- Candidate/CLI tests cover defaults, strict opt-in, explicit bounds and reviewed acceptance.
- `tests/kicad/routing/test_search.py`: 4 passed locally on KiCad 10.0.6. Two/four-layer
  mazes (same-face detours and mandatory through vias) reduce the physical open count by one without increasing existing violation counts;
  injected decision-write failure restores the board and decision record before a successful retry.
- Agent guide: generated and 53 page tests passed, including command examples and budgets.
- Final focused regression: 85 passed (new search proofs plus existing router/CLI proposal tests),
  exit 0. Includes model/named-pair protection, stale-plan refusal and confirmation without rerunning search.

These are local proofs, not exact-head CI. No pinned CI run or native Altium evidence
exists for this implementation yet. The change remains open and unarchived.

## Quick-gate correction — 2026-11-03

The first `make check-fast` reached 15615 passes and four failures in the hypothesis-register
checks. It was interrupted (exit 2), not passed. The three new statements had been authored
before the kernel but appended outside the table read by the register parser. Their rows now
sit inside that table, and the contract proof checks their presence using the real parser.
A complete quick-gate rerun is required; no CI or archive claim follows from the interrupted run.

The correction passed all 58 focused register/contract tests, including the four formerly failing
checks. The complete quick gate is being rerun with four workers; its result is recorded separately.

## Pair fallback correction — 2026-11-03

An additional regression test found that `search=fallback` could keep a fixed-pattern candidate
for an independent differential-pair leg before reaching the search family's pair refusal.
Pair membership is now checked before candidate-family dispatch in both opt-in modes, including
model/named pairs whose other net is not selected. Group templates remain atomic and the default
pattern-only mode is unchanged. The regression first failed, then the focused candidate/geometry/CLI
proof passed (39 tests), including half-selected named pairs through the real CLI.

The second broad quick run was superseded while this correction was being applied and interrupted
with 15555 passes, 42 skips and no failures (exit 2). It is not a passing gate for the final code.
A fresh complete quick run on the frozen pair-protected implementation is required.

## Final local gate — 2026-11-03

`make check-fast PYTEST_MAX_WORKERS=4` completed with exit 0: **15656 passed, 43 skipped**
in 1352.98 s. This run includes the corrected registry and pair-family guard, with no source
changes during its test execution. Ruff, formatting, generated guide checks, strict Pyright
and the configured residue scan also passed. The four authored KiCad cases were rerun after
the pair guard and passed on KiCad 10.0.6 (exit 0, 17.81 s).

The final snapshot supersedes the interrupted snapshots above. No full local `make check`
was run. Required pinned CI on an implementation commit remains unrun. A local commit was authorized
on 2026-11-03; push remains unauthorized. c0365 tasks 1–6 are implemented with focused proofs; closing tasks 7–9
remain open and the change is not archived. c0366–c0370 remain unimplemented proposals.
