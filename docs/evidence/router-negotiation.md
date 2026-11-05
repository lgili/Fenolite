# Negotiated router evidence (c0367)

## Contract before algorithm implementation — 2026-11-03

S-1310 contributes the published concept of iterative congestion penalties over provisional demand.
No third-party implementation, formula, seed, pseudocode or figure is copied. The bounded PCB
algorithm, geometry tests and software penalty coefficients are authored for Fenolite.
The paper concerns FPGA resources; it proves no PCB clearance, completion or electrical claim.

Provisional routes belong only to this job. Original copper, manual/locked routes, accepted decisions
and corridors never enter the set the negotiator can remove. Current provisional demand and
nonnegative history influence A* without relaxing fixed geometry or electrical exclusions.
Stable subject ordering, explicit round/state/via limits and one deadline bound all retries.
Final candidates must pass joint swept geometry, connection checks and existing copper/role judges.
No provisional overlap or incomplete bundle escapes on a bound, interruption or failed judgment.

A bundle hashes a schema tag, all canonical member payloads and the complete input fingerprint.
Members name exactly one bundle and cannot be independently accepted, rejected, replayed or forgotten.
Legacy v0 decision bytes remain unchanged; bundle-bearing records use an explicit newer schema
and unsupported future records fail rather than discard decisions. Decision writes, board writes,
stale-input protection, receipts and rollback share the existing reviewed-plan transaction.

## Local implementation proofs — 2026-11-03

- Bundle contract: 6 passed, exit 0, including order-independent identity and legacy bytes.
- Bounded kernel: 12 passed, exit 0. Independently crossing paths negotiate a legal joint detour;
  exhaustion/interruption exposes no provisional copper, and original locked geometry stays fixed.
- Candidate gate: 11 passed, exit 0, plus 52 architecture tests. Both judges and the adapter's
  connection check remain authoritative. Reversed subject input also preserves bundle identity.
- Record/CLI lifecycle: initial combined proof 25 passed, exit 0. Additional completed proofs cover
  selected-subset regeneration, global-prefix replay compatibility (8 cases), HV replay refusing
  missing limits and accepting supplied limits, and explicit historic-membership conflict recovery.
- Existing independent proposal/replay/forget regression: 5 passed, exit 0. An old c0366 usage
  expectation was updated because requirements are now intentionally accepted for bundle replay;
  the new authored HV lifecycle case proves fail-closed behavior rather than merely removing coverage.
- Agent guide: 55 passed, exit 0; generated references, tested controls/fields, all existing budgets.
- Native KiCad 10.0.6: final 4 passed, exit 0, 33.34 seconds. Two/four-layer joint alternatives
  close both physical open connections without increasing violation counts; locked and named-pair
  negatives preserve board bytes and the native report. This does not establish pinned KiCad 9 parity.
- Final broad focused regression: 210 passed, exit 0, 174.41 seconds, including all new record/CLI
  cases, the prior role-search cases, architecture and guide coverage.
- Strict OpenSpec validation, Ruff and format checks pass. First local quick gate recorded one existing start-page wording failure; it was interrupted after
that failure (exit 130; 10521 passed and 39 skipped before interruption), never a passing run.
Required start-page wording was restored without changing the test or increasing size budgets.
The next quick gate was also interrupted (not passed) when final direct-API review found that
proposal-only negotiation options could be silently ignored without subjects. A focused red/green
regression now verifies rejection before ordinary routing; 94 routing/architecture tests passed, exit 0. Final complete quick gate passed, exit 0: 15774 passed, 43 skipped, 666.28 seconds.
Command: `make check-fast PYTEST_PARALLEL="-n 8 --maxprocesses 8 --dist loadfile -x -vv --tb=short"`.
This selects the full quick suite; stop-on-failure/verbosity do not filter tests. Source remained
frozen during that completed run. Earlier interrupted/failed runs are not substituted for it;
  failed iteration attempts are not counted as passes.

During iteration, fixtures exposed net registration/edge-rule mistakes. Focused regression also
caught the superseded c0366 replay usage expectation. The implementation retains package layering,
never relaxes the architecture guard, and adds no runtime dependency to the core.

H-G-ROUTE-NEGOTIATE and H-G-ROUTE-BUNDLE are INFERRED from authored proofs.
H-K-ROUTE-NEGOTIATE remains UNKNOWN until required pinned CI judges the exact implementation head.
No global completion, convergence, continuous optimality, electrical certification or native Altium
verification is claimed. Full validation/closing/archive remain open and no push is authorized.

## Authored proof sources

These hashes identify local proof inputs, not an unpublished commit or a CI run.

| Source | SHA-256 |
| --- | --- |

| `tests/_negotiatebench.py` | `9a3bd878efbcc2f2299bb10117e9b9b6b09542fba855c0d0d6099a345f612505` |
| `tests/_negotiate_project.py` | `3ea5e1d9294c9446763a3a1bbbedacfc38b5dd4298a3c780927adb5d93a2a176` |
| `tests/unit/routing/test_bundle_contract.py` | `6efee71ab1509725991a4198ef95e36886ddfccd47f9534cb9a738aaa997799d` |
| `tests/unit/routing/test_bundle_decisions.py` | `8aa5244fa26388989f01300b8937de8c0ce4450d8a52b8a8f74644c8957ab816` |
| `tests/unit/routing/test_negotiate.py` | `2e571ed2e0b4a2a6cb7066f0d6209ca9ce8cda074fcfce80bbd2124ddc4f89d0` |
| `tests/unit/routing/test_negotiate_candidates.py` | `1f6dd30c5e56677b82653294d2aa4364705adeea021dc59fa2505aaab0c7ebb9` |
| `tests/unit/cli/test_route_bundles.py` | `1dc6a75c74b6c728bd2da70e8dcda93ed854a956a3890d6b91414deea966732a` |
| `tests/kicad/routing/test_negotiate.py` | `a31c019ba42995d110a0caeac8ec1279bc1398be4b02a678816645b5e15c773d` |
