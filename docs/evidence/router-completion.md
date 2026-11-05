# Router completion review evidence (c0370)

## Scope

c0370 adds no routing algorithm. It proves that the reviewed stages of c0222-c0369 compose on authored
boards, that the reply of `route --propose` states completion truthfully (`result.completion`,
`docs/routing.md`, "Proposals"), and that accepted, manual and locked copper survive later passes, scoped
tidy, interruption and conversion. Every board here is authored for Fenolite: `examples/routing/acceptance.py`
(CC0, its own SplitMix64 mixer), `tests/_completion_project.py` and `tests/_families_project.py`. No
third-party board, router code or measurement enters these proofs.

## Local proofs — 2026-11-04

- Acceptance generator: `tests/unit/routing/test_completion_fixtures.py`, 15 passed. Script SHA-256 of
  seeds (1, 2, 40) and (1, 4, 150) pinned and equal on Python 3.11 and 3.13.
- Completion facts: `tests/unit/routing/test_completion_report.py`, unit and authored-bench cases for
  `proposed`, `unknown` (a timeout, cancellation or explicit search/round bound before any candidate, or
  unmeasured facts), `no-candidate`, `rejected` and `not-attempted`; `complete` is never true.
- Reviewed stages (`tests/kicad/routing/test_completion_workflow.py`): 5 passed on the local `kicad-cli`
  10.0.6 and 5 passed in the pinned `kicad/kicad:9.0.9` image run locally. Accept, a tidy scoped to the
  approved net and a second pass are separate reviewed transactions on two and four layers. Hand-drawn
  copper (no copper marker) and locked copper keep every item although an unscoped chamfer plans to cut the
  bend; KiCad DRC opens fall 2 -> 1 -> 0 with no violation type growing; a signal during an accept or tidy
  write leaves every file's bytes and the same reviewed plan writes afterwards; `search-max-states=1`
  writes nothing and reports `unknown`.
- Families together (`tests/kicad/routing/test_completion_families.py`): role-aware search over a saved
  ground reference negotiates a crossing pair into one bundle, a missing external tool refuses the run
  (exit 6, `FEN-6001`, nothing written), the viewer refuses a lone bundle member and writes the whole unit,
  and an ordinary search pass closes the last connection; KiCad DRC opens fall 3 -> 1 -> 0. The pinned
  external tools themselves are judged only by `test_external_candidates.py` in the router CI job.
- KiCad-to-Altium readback (`tests/unit/altium/test_router_completion_readback.py`): 2 passed. Every
  KiCad track of the routed completion board returns from Fenolite's reading of the converted PcbDoc with
  its net, layer, width and lock, each end within one Altium unit after one translation.

## Limits and open gates

- Altium: the readback is Fenolite reading what Fenolite wrote, `INFERRED`. Opening the converted
  document in Altium Designer and running its DRC is a separate maintainer gate, not performed.
- KiCad: local runs are not exact-head CI. `H-K-*` rows stay `UNKNOWN` until the required pinned jobs judge
  the exact head.
- Scale: measurements up to about 150 parts are recorded by `tests/kicad/routing/test_completion_scale.py`
  in CI; thresholds come only from those recorded measurements. Wall-clock time is telemetry, never a
  pass criterion, and a run cut by its budget is never called exhaustive.
- No global completion, optimality, electrical certification or manufacturing approval is claimed.
