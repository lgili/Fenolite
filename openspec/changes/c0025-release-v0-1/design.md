## Context

- **Scope.** The v0.1 deliverables that no change owns: the second example board, the agent session of acceptance item 7 with `AGENTS.md` and a skill file, the end of the staged CI matrix (plan §7.3) and the release gate. Hand-overs: `--uses project` in the `kicad-10` fetch (c0013 Open Questions; c0021 Open Questions, default c0025) and c0020's acceptance test on the second board (c0020 Open Questions).
- **The eight acceptance items** (plan, v0.1), in Fenolite's words:
  1. Both examples pass KiCad's DRC with no violation and no unconnected item on 9.0.x and 10.0.x; the net-assignment comparison finds no difference; the two negative tests are detected with a location; RT1 equals the model; a second `build` gives identical bytes with fills and routes kept; a moved footprint keeps its position through a rebuild and the tracks are intact.
  2. Every demo board (9.0 and 10.0 tags) and the public third-party boards of the corpus pass RT0, RT1 and RT2, and the opaque count reappears on write.
  3. A router plugin leaves no unconnected item on the blink, with KiCad's DRC as the judge.
  4. A generated `.kicad_wks` is accepted by `--drawing-sheet`, A3 and A4 from one file.
  5. The consistency suite passes for every command; every output validates against schema v0; the wheel installs with no dependency; `doctor` reports `kicad-cli`, the routers and the subcommand matrix.
  6. `check` on a demo project is read-only.
  7. An agent session closes the loop on the blink in ten turns or fewer, with every output labelled.
  8. The token fuzz holds on both images: 9.0 rejects exactly the tokens marked for 10.0.
- **What exists.** The blink (`examples/blink_2layer`); the authored mini library (a 32-pin controller, a 0603 resistor, a through-hole LED) in 9.0 and 10.0 forms; CI jobs `unit` (ubuntu and macOS, Python 3.12), `kicad-10`, `kicad-9`; `release.yml` (build, residue scan of the artefacts, trusted publishing, a check that the tag equals both version strings); version `0.0.1.dev0`.
- **What the other v0.1 changes give.** `fill` (c0015), `place` and the legality check (c0022), `route`, the `routing` job and the gate verdict (c0016; c0023 if kept), `export` and `render` (c0024), DRC findings, the net comparison, RT2 and the negative tests (c0020), board-frame pads and script copper (c0028), the copper check (c0029), fields (c0030), zone settings (c0031).
- **Tools per job.** The `kicad-9` and `kicad-10` jobs hold no router, and `kicad-cli` 9.0 cannot refill zones (`H-K-01`). A container job cannot start a container. So the full loop cannot run inside `kicad-9`.
- **Fake tools.** `tests/_fakecli.py` writes a `#!/bin/sh` wrapper, which Windows cannot execute.
- **Constraints.** Clean-room: the example is authored for Fenolite. Stdlib only. The roadmap gives this change 5 days.

## Goals / Non-Goals

**Goals:**
- One place that says, per acceptance item, which test proves it, in which job, and with what result.
- The loop proved end to end on two boards and two majors, by tests that run in CI.
- An agent guide whose commands are executed by a test, so it cannot go stale.
- The CI matrix the plan promises for the end of v0.1.

**Non-Goals:**
- Everything under "Non-goals" in the proposal.

## Decisions

1. **Order of work.** The example first, then the loop and its recorded boards, then the guide, CI, the record and the version. The version changes last, in its own commit, after every row of the record has a result.

2. **`examples/board_40parts/design.py`.** Forty parts from the mini library only, so no library file is added:
   - two controllers (`Mini:Mini_QFP32_IC`), twenty resistors, eighteen LEDs: an LED bar, each controller driving nine LEDs through nine resistors, plus two pull-up resistors;
   - written with modules (one `Module` per controller with its LEDs), one netclass for the supply nets, a board of 100 mm × 80 mm, two copper layers, a `GND` zone on the bottom layer (c0031);
   - the two controllers placed by hand and locked; every other part left to `place --strategy grid`;
   - its own `fp-lib-table` and `sym-lib-table`, as the blink has;
   - header: SPDX `CC0-1.0` and the authored-for-Fenolite line.
   - Rejected: new footprints for variety (capacitors, a connector). They add library work and prove nothing the loop needs; v0.2a's schematic change may add them.
   - Rejected: the official libraries. The example must build with no fetch.

3. **Where the loop runs.** Two test folders:
   - `tests/routing/test_acceptance_loop.py` (`needs_kicad`, `needs_router`): the whole loop from `design.py`, for each example and target (9, 10), on `kicad-cli` 10.0.6. It lives under `tests/routing` so that c0016's `routing` job runs it with no change to that job; the job stays optional for merge and is required for release. Steps: `build`, `place --strategy grid`, `route --router <the router of the gate verdict>`, `fill`, `check`, `export --all --manifest`, `render --svg --png`, every one with `--confirm` into a temporary folder.
   - `tests/kicad/acceptance/test_finished.py` (`needs_kicad`): runs on **both** majors against the finished boards of Decision 4.
   - Rejected: the loop inside `kicad-9`. It has no router and cannot refill.

4. **Finished boards are recorded.** `tests/data/acceptance/<example>_t<9|10>/` holds the project the loop produced (`.kicad_pro`, `.kicad_pcb`, `.kicad_dru`, the library tables), written by `test_acceptance_loop.py` when `FENOLITE_ACCEPTANCE_WRITE=1`, each with a row in `tests/data/MANIFEST.toml` (author: Fenolite; produced by: the loop, with the router name and version and the `kicad-cli` version).
   - They are not regenerated in CI and compared: a router need not repeat (`H-K-KRT-REPEAT`). `test_acceptance_loop.py` instead asserts the same properties on its fresh result as `test_finished.py` asserts on the recorded one.
   - `test_finished.py`, per recorded project, on the running major (a target-10 project is skipped on 9.0.9 with that reason):
     - `fenolite check` exits 0; `drc.kicad` reports no violation and no unconnected item; the net comparison reports no difference; `roundtrip` is equal (item 1);
     - `fenolite build <design.py> --out <copy>` over a copy of the project plans no write, and a build into the copy twice gives identical bytes (item 1: fills and routes kept);
     - `fenolite place <copy> --strategy manual --move R1=<x>,<y>`, then a rebuild: `R1` is at the moved position, and every track and via of the board is byte-equal to the one before the rebuild (item 1). A move in KiCad's own editor is the maintainer's manual check, recorded in the release record;
     - `fenolite export --all --manifest` and `fenolite render --svg` plan their files (c0024);
     - c0020's two negative tests run on a copy (pad re-netted; track between nets) and are detected with a location (c0020 Open Questions).
   - Rejected: only fresh runs. Then nothing proves the loop's result on 9.0.x.

5. **If no router closes the 40-part board** (`H-K-REL-LOOP40`). The router runs with a 600 s limit. Nets it leaves open are routed with script copper in `design.py` (c0028), the record states how many nets the router closed, and item 1 is `met with a recorded limit`. Item 3 names only the blink.
   - If c0016's gate fails and c0023 is cut or fails, item 3 is `not met`; both examples then carry script copper, and the release decision is the maintainer's.

6. **Agent guide.** `agent/SKILL.md` (front matter `name`, `description`; under 200 lines):
   - when to use Fenolite; `capabilities` first; the exit codes; plan with `--dry-run`, then `--confirm`; evidence levels and what to treat as unconfirmed;
   - one fenced block tagged `fenolite-loop` with the ten commands of the loop, each on one line, on `examples/blink_2layer/design.py` and the folder `build/blink`: `capabilities`, `build --dry-run`, `build --confirm`, `place`, `route`, `fill`, `check`, `export`, `render`, `inspect`;
   - what to do for each non-zero exit code.
   - `AGENTS.md` section "Using the `fenolite` CLI" gains the loop order and a link to the skill; `README.md` gains the same ten lines as its quick start.
   - `tests/unit/test_agent_skill.py` (hermetic): the block exists; it holds at most ten commands; every command word and flag is registered (each line is parsed with the CLI's own parser); the same block appears in `README.md`.
   - `tests/routing/test_acceptance_loop.py::test_skill_block` runs the block's lines verbatim in a temporary folder (the router name replaced by the gate's router when the block names another): every command exits 0, and every envelope holds `evidence.level`. Ten commands are ten turns (item 7).
   - A live session is recorded once by the maintainer in the release record: the model, the date, the number of turns, the final exit codes. It is labelled `UNVERIFIED` and is not a CI gate.
   - Rejected: shipping the skill inside the wheel. The repository is where an agent reads it; `capabilities` already describes the commands.

7. **`unit` matrix.** The living requirement keeps its name ("Unit CI job on two operating systems") although it now lists three: OpenSpec matches a MODIFIED requirement by name, and no archived change renames one. `ubuntu-latest` × Python 3.11, 3.12, 3.13; `macos-latest` × 3.12; `windows-latest` × 3.12 (five runs). The steps do not change.
   - Windows portability (`H-G-REL-WINDOWS`): `tests/_fakecli.py` writes, on Windows, a `.cmd` wrapper next to the Python script; tests compare paths through `as_posix()`.
   - Fallback: a test that still needs a POSIX executable is skipped on Windows through one helper, `tests/_resources.py::posix_tools`, with the reason `posix-only fake tool`; the number of such skips is written in the release record and must be below 5 % of the collected tests. If more, the Windows run is `continue-on-error` and moves to v0.2a (cut 1).

8. **`wheel` job.** On `ubuntu-latest`, Python 3.12, every push and pull request:
   - `uv build --out-dir dist` and `uv build packaging/phenolite --out-dir dist`;
   - `uv run --no-project python tools/residue/scan.py` (the artefact scan of `release.yml`);
   - a fresh virtual environment, `pip install --no-index --find-links dist fenolite` (so a dependency would fail the install), `fenolite capabilities --json` exits 0, and `python -c "import importlib.metadata as m; assert not m.requires('fenolite')"`;
   - the wheel holds no file under `tests/`, `private/` or `examples/`.

9. **`kicad-10` fetch.** Step 6 becomes `tools/corpus_fetch.py --uses rt0 --uses project --exclude-uses heavy`, so c0013's read-only test runs on real demo projects in CI (item 6). The cache key is unchanged (the manifest's hash).

10. **Release record.** `docs/release/v0.1.md`:
    - a table `| item | statement | proof | job | result |`, one row per acceptance item part (about twenty rows), `proof` a pytest node id or a file under `tests/`;
    - the CI run of the release commit (URL), the tool versions, the router and its version;
    - the recorded limits (Decisions 5 and 7), the manual checks (GUI move; live agent session) with their dates;
    - what v0.1 does not do, from the roadmap's gap table;
    - `## Verdict`: `pending`, set by the maintainer.
    - `tests/unit/test_release_record.py`: every `proof` names an existing test file, and the function when one is given; every `result` is `met`, `met with a recorded limit`, `not met` or `pending`; no row is `pending` once `__version__` is `0.1.0`; the eight items are all present.
    - Rejected: a script that computes the verdict from CI. The result of a row is read from the named job of the release commit and written by hand; the guard keeps the table honest about what exists.

11. **Version.** `__version__ = "0.1.0"` in `src/fenolite/__init__.py` and `version = "0.1.0"` in `packaging/phenolite/pyproject.toml`, one commit, last. `CHANGELOG.md`: `## [Unreleased]` becomes `## [0.1.0] - <date>` with a new empty Unreleased above. `docs/roadmap.md`: v0.1 done, the released line updated.
    - The tag `v0.1.0`, the GitHub Release and so the PyPI publication (`release.yml`) are the maintainer's. An alpha tag before it (`v0.1.0-alpha1`, roadmap) is independent of this change.

12. **Merge and release gates.** Merge: `unit`, `wheel`, `kicad-10`, `kicad-9` (as today, plus `wheel`). Release: those, plus `routing` on the release commit, plus the record's verdict.

## Files and public API

| file | content |
|---|---|
| `examples/board_40parts/design.py`, `fp-lib-table`, `sym-lib-table` (new) | Decision 2 |
| `examples/README.md` (extended) | the new row |
| `tests/routing/test_acceptance_loop.py`, `tests/routing/_loop.py` (new) | `run_loop(example, target, router, out) -> LoopResult(steps, board)`; `test_loop`, `test_skill_block` |
| `tests/kicad/acceptance/test_finished.py` (new) | Decision 4 |
| `tests/data/acceptance/{blink_2layer,board_40parts}_t{9,10}/` (new) | recorded projects, with `MANIFEST.toml` rows |
| `agent/SKILL.md` (new); `AGENTS.md`, `README.md` (extended) | Decision 6 |
| `tests/unit/test_agent_skill.py`, `tests/unit/test_release_record.py` (new) | guards |
| `.github/workflows/ci.yml`; `tests/unit/test_ci_workflow.py` (extended) | Decisions 7 to 9 |
| `tests/_fakecli.py`, `tests/_resources.py` (extended) | the Windows wrapper; `posix_tools` |
| `docs/release/v0.1.md` (new) | Decision 10 |
| `src/fenolite/__init__.py`, `packaging/phenolite/pyproject.toml`, `CHANGELOG.md`, `docs/roadmap.md` | Decision 11 |

No change under `src/fenolite/` except the version string.

## Sources registered by this change

None: this change reads no format fact. S-0235 to S-0239 stay unused.

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-K-REL-LOOP40 | The router of c0016's gate verdict leaves no unconnected item on `board_40parts` for targets 9 and 10 within 600 s, and the finished board passes KiCad's DRC | `tests/routing/test_acceptance_loop.py::test_loop` | on 10.0.6: `check` exits 0 for both targets with no script copper in `design.py`. If not, Decision 5 applies and the row records the number of nets the router closed |
| H-G-REL-WINDOWS | The unit, consistency and residue suites pass on `windows-latest` with Python 3.12, with fewer than 5 % of the tests skipped as `posix-only fake tool` | the `unit (windows-latest, py3.12)` run | the run passes and its summary gives the skip count. If not, Decision 7's cut applies |

Ids used without changing their level: `H-K-01`, `H-K-KRT-ROUTE`, `H-K-KRT-REPEAT`, `H-K-FILL-LIFT`, `H-K-EXPORT-FILES`, `H-K-PLACE-MOVE`.

## Evidence level per behaviour (before merge)

| behaviour | level required | proof |
|---|---|---|
| Loop on both examples, both targets | KICAD-VERIFIED (10.0.x) fresh; KICAD-VERIFIED (9.0.x, 10.0.x) on the recorded boards | `test_acceptance_loop.py`, `test_finished.py` |
| Rebuild identity, moved footprint | mechanical, judged on files KiCad accepts | `test_finished.py` |
| Agent guide | mechanical | `test_agent_skill.py`, `test_skill_block` |
| CI matrix, wheel | mechanical | `test_ci_workflow.py`; the jobs' runs |
| Release record | each row at the level of its proof | `test_release_record.py` |

## Budget (5.75 days; the roadmap gives 5)

| work | days |
|---|---|
| `board_40parts` | 1.0 |
| loop test, recorded boards | 1.0 |
| finished-board tests on both majors | 1.0 |
| agent guide and its tests | 0.75 |
| `unit` matrix and Windows portability | 0.75 |
| `wheel` job, `--uses project` | 0.5 |
| release record, version, closing | 0.75 |
| **total** | **5.75** |

Cut order: (1) the Windows run (to v0.2a, recorded); (2) Python 3.13; (3) `board_40parts` routed by the router (Decision 5's script copper). Not optional: the loop on the blink on both majors, the wheel job, the guide's executed block, the record.

## Risks / Trade-offs

- [An acceptance item fails late] → the record says `not met`, the fix goes to the owning change, and the version commit waits. This change never weakens a test to pass.
- [Recorded boards go stale when a writer changes] → `test_finished.py` rebuilds over them and requires no planned write; a writer change that alters bytes fails there and the boards are recorded again in the same pull request.
- [The grid placer and the router fight on a dense board] → the board is 100 mm × 80 mm for forty small parts; the grid pitch is in `design.py`.
- [Windows runners are slow or flaky] → one run, no KiCad; cut 1.
- [The fetch of demo projects makes `kicad-10` slower] → the cache holds them; heavy rows stay excluded.

## Migration Plan

Additive, except the version. To roll back before the tag, revert the version commit; after the tag, releases are not withdrawn and a fix is `0.1.1`.

## Open Questions

- **Release with a `met with a recorded limit` row?** Default: yes, the record names it; `not met` blocks the version commit unless the maintainer writes the exception in the record.
- **Python 3.14.** Default: not in the matrix until its release is supported by the pinned tools.
- **Is the `routing` job required for merge after v0.1?** Default: no (c0016); it is required for a release.
- **An alpha tag before this change.** The roadmap names `v0.1.0-alpha1`; the maintainer decides, and it needs nothing from this change.
