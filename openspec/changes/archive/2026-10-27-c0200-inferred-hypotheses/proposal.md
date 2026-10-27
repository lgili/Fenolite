## Why

The v1.0 freeze of `docs/roadmap.md` asks "no `INFERRED` without a hypothesis": every claim that is not
verified names the hypothesis and the test that would settle it. On 2026-10-26, eighteen `Evidence` values of
the package were `INFERRED` with no hypothesis, two of them added the same day by c0198 and c0199. The rule is
cheap to keep now and costly to recover at the freeze, so the maintainer chose it as the first item of the
consolidation list of 2026-10-26.

## What Changes

- Eight hypotheses registered in `docs/hypotheses.md`, each with its settling tests: `H-G-MODEL-OWN` (a built
  design or a model is Fenolite's own write), `H-G-PLACE-RULES`, `H-G-CATALOG`, `H-G-IMP-TABLE`,
  `H-G-VIEW-SCENE`, `H-A-LAYOUT-REPLAY` (c0164's schematic layout replay), `H-G-TIES` (c0198) and
  `H-G-CROSSINGS` (c0199).
- Each of the eighteen sites cites one of them, or `H-A-KIT-STABLE` for a kit run that verifies nothing.
- A test reads the package source and fails on an `Evidence(Level.INFERRED)` without hypotheses.
  - It allows a call that is an argument of `Evidence.combine`: such a call only caps the level, and
    `combine` merges the hypotheses of the others.
  - It allows one named exception with its reason: no Altium document among the written files.
- Three tests that compared the old evidence now expect the cited hypothesis.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `verification-evidence`: ADDED "Inferred evidence names a hypothesis".

## Non-goals

- Raising any level. The rows are `INFERRED`; what would raise them (an oracle, a kit run) is each row's
  settling test.
- The other v1.0 rule, "no `UNVERIFIED` outside `experimental`", which needs its own census.

## Evidence level required

The register test (`tests/unit/test_hypotheses_register.py`) and the new source test.

## Impact

- `docs/hypotheses.md`, eighteen sites under `src/fenolite/`, `tests/unit/test_inferred_hypotheses.py`, three
  tests, `CHANGELOG.md`. Replies whose evidence was bare `INFERRED` now list a hypothesis.
- Size: half a design-day.
