## Why

v0.1 has eight acceptance items (plan, v0.1 "Aceitação"), and no change proves them together. Still unowned: the second example board, the agent session, the end of the staged CI matrix (plan §7.3) and the release gate. c0013, c0014, c0020 and c0021 hand work over to this change.

This change adds no feature: it adds the proofs, and a record of what was and was not proved.

## What Changes

- `examples/board_40parts/design.py` (new, CC0): forty parts from the authored mini library, with rules from c0054's constructor.
- Acceptance tests (new): the loop `build → place → route → fill → check → export → render` on both examples in the `routing` job; the finished boards are checked on both majors.
- `agent/SKILL.md` (new), `AGENTS.md`, `README.md`: the loop in ten commands, run by a test; the README status and install sections are rewritten.
- CI: `unit` gains `windows-latest` and Python 3.11 and 3.13; a `wheel` job; a `dco` job (c0014's hand-over); `kicad-10` also fetches `--uses project`.
- `docs/release/v0.1.md` (new) with a guard test: one row per acceptance item, and the limits: items 2 and 5, the residue scan (public gate only), the container refill, board outlines.
- Release build: from the tagged commit in a clean checkout, never from the working tree; the history residue scan (public gate) is recorded; `make hooks`.
- Version `0.1.0` in the package, its alias and the alias pin; `CHANGELOG.md` cleaned into `[0.1.0]`.
- Hypotheses `H-K-REL-LOOP40`, `H-G-REL-WINDOWS`.

Budget: 6.75 days; the roadmap gives 5.

## Capabilities

### New Capabilities
- `release-gate`: the example, the acceptance suite, the agent guide, the release record, the release build, the version.

### Modified Capabilities
- `ci-baseline`: MODIFIED "Unit CI job on two operating systems" and "kicad-10 oracle job"; ADDED "Wheel job" and "DCO job".

Delta order for `ci-baseline`: c0016, c0023, c0025. The first two only ADD requirements, so both MODIFIED texts copy the living spec of 2026-10-04 (after c0049).

## Prerequisites

Archived first, and not repeated here:
- c0050: the bound of the geometry composition test.
- c0051: repeatability of the DRC canary test.
- c0052: capabilities evidence, packaging metadata, the contract's `template` section, the provenance page.
- c0053: script copper in the Altium build.
- c0054: the DSL rule constructor, used by `board_40parts`.

## Non-goals

- Any new command, flag, model field or format fact.
- Per-command result schemas: v0.1 has envelope, error and manifest schemas only.
- A Docker-capable CI job; the private residue gate; an outline snapping tolerance: each is a recorded limit.
- Tagging or publishing (the maintainer's actions); the `macos-app` nightly job (v0.2a); a live model session in CI.
- Fixing a failing acceptance item here: the owning change fixes it, or it is recorded as not met.

## Evidence level required

- Items 1, 3, 4, 6 and 8: `KICAD-VERIFIED (9.0.x, 10.0.x)`, in `kicad-9` and `kicad-10`.
- Item 2: `CORPUS-VERIFIED` and `KICAD-VERIFIED (10.0.x)`, with limits: 24 boards, heavy rows excluded, one board not judged for RT2, five boards on 9.0.9.
- Item 5: mechanical, with the schema limit. Item 7: mechanical; the recorded agent session is `UNVERIFIED`.
- Residue: public gate only; the private gate is not run for v0.1.0, and the record says so.
- Rows state `met`, `met with a recorded limit` or `not met`. Only the maintainer writes the verdict.

## Impact

- New: example, tests, recorded boards, `agent/SKILL.md`, `tools/dco_check.py`, `docs/release/v0.1.md`. Changed: `ci.yml`, `AGENTS.md`, `README.md`, `CHANGELOG.md`, the roadmap, two registers, the version strings.
- Depends on every v0.1 change and on c0050 to c0054.
- No runtime dependency.
