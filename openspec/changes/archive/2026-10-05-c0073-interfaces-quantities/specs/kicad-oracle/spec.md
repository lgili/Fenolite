## ADDED Requirements

### Requirement: Differential pair names are probed
`tests/kicad/rules/test_diffpair_names.py` (marker `needs_kicad`, major-aware) SHALL settle `H-K-DIFFPAIR-NAMES` on the running `kicad-cli`, with one bench of `tests/kicad/rules/_rulebench.py` holding, per case, two parallel tracks 0.3 mm apart on the case's two nets, one rule per case with the condition `A.inDiffPair('<base>')` and a 3 mm clearance, and the canary scoped to its own net. DRC MUST be judged only from the JSON report.
- Cases and bases: `X_P`/`X_N` (base `X`, and again with base `X_`), `X+`/`X-` (`X`), `X_DP`/`X_DN` (`X_D`), `XP`/`XN` (`X`), `X_DP`/`X_DM` (`X_D`), `X_p`/`X_n` (`X_`) and `X_P`/`X-` (`X`), each case with its own `X`.
- Probe `dru-diffpair-<case>` MUST record `present` when the clearance violation between the case's two tracks is reported, and `absent` otherwise; a run whose canary does not fire MUST fail.
- The outcomes MUST be recorded in both probe files, and the rule MUST be written to `docs/formats/kicad/rules.md` with its sources and label. `build.diff-pair-name` MUST follow the outcomes: a case recorded `present` on a major MUST pass the check, and one recorded `absent` MUST fail it.

#### Scenario: Names on both majors
- **WHEN** `uv run pytest tests/kicad/rules/test_diffpair_names.py -rA` runs on the local KiCad 10.0.6 and inside the pinned 9.0.9 image
- **THEN** the cases `X_P`/`X_N` (both bases), `X+`/`X-`, `X_DP`/`X_DN` and `XP`/`XN` record `present`, the cases `X_DP`/`X_DM`, `X_p`/`X_n` and `X_P`/`X-` record `absent`, and the canary fires in every run
