## Why

v0.1 is defined by eight acceptance items (plan, v0.1 "Aceitação"), and no change proves them together. Four deliverables are still unowned: the second example board (`board_40parts`, item 1), the agent session that closes the loop in ten turns or fewer (item 7), the end of the staged CI matrix (plan §7.3) and the release gate. c0013, c0020 and c0021 also hand work over to this change.

This change adds no feature: it adds the proofs that v0.1's features work together, and the record that says so.

## What Changes

- `examples/board_40parts/design.py` (new, CC0): forty parts from the authored mini library on a two-layer board, with modules, a netclass and manual placement of the two controllers.
- Acceptance tests (new): the loop `build → place → route → fill → check → export → render` on both examples in the `routing` job; the finished boards are recorded and checked on both majors: DRC, net comparison, byte-identical rebuild with fills and routes kept, a moved footprint kept by a rebuild.
- `agent/SKILL.md` (new) and `AGENTS.md`: the loop in ten commands. A test runs exactly the commands the skill lists.
- CI: `unit` gains `windows-latest` and Python 3.11 and 3.13; a `wheel` job (build, residue scan of the wheel, clean install without dependencies); `kicad-10` also fetches `--uses project`.
- `docs/release/v0.1.md` (new): one row per acceptance item, with its test, its job and its result; a guard test checks that every row names an existing test.
- Version `0.1.0` in the package and its alias; `CHANGELOG.md` gets its `[0.1.0]` section; the roadmap moves v0.1 to done.
- Hypotheses `H-K-REL-LOOP40`, `H-G-REL-WINDOWS`.

The tag, the GitHub Release and the PyPI publication are the maintainer's actions; no task performs them.

Budget: 5.75 days against the roadmap's 5; the cut order is in the design.

## Capabilities

### New Capabilities
- `release-gate`: the acceptance suite, the second example, the agent guide and its test, the release record, the version.

### Modified Capabilities
- `ci-baseline`: MODIFIED "Unit CI job on two operating systems" and "kicad-10 oracle job"; ADDED "Wheel job".

## Non-goals

- Any new command, flag, model field or format fact.
- Tagging, publishing or announcing the release.
- The `macos-app` nightly job of plan §7.3: the maintainer's local runs on macOS with KiCad 10.0.6 are recorded in the release record instead; the job moves to v0.2a.
- A live language-model session in CI: the recorded session of item 7 is the maintainer's, and CI runs the scripted loop.
- Fixing a failing acceptance item inside this change: a failure is fixed in the change that owns the behaviour, or the item is recorded as not met.

## Evidence level required

- Items 1, 3, 4, 6 and 8: `KICAD-VERIFIED (9.0.x, 10.0.x)`, by the acceptance suite and the tests of the owning changes, in the `kicad-9` and `kicad-10` jobs.
- Item 2: `CORPUS-VERIFIED` and `KICAD-VERIFIED (10.0.x)` by c0020's corpus tests.
- Items 5 and 7: mechanical (consistency suite, `wheel` job, scripted loop); the recorded agent session is `UNVERIFIED` evidence and is labelled so.
- The release record states, per item, `met`, `met with a recorded limit` or `not met`. Only the maintainer writes the final verdict.

## Impact

- New example, acceptance tests and recorded boards, `agent/SKILL.md`, `docs/release/v0.1.md`; changed `ci.yml`, `AGENTS.md`, `README.md`, `CHANGELOG.md`, the roadmap, the version strings.
- Depends on every v0.1 change: c0015, c0016, c0020, c0022, c0024 and c0028 to c0031; on c0021 and c0023 only if they stay in v0.1.
- No runtime dependency. Windows needs portability fixes in the test helpers.
