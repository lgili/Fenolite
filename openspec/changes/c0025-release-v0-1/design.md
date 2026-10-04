## Context

- **Scope.** The v0.1 deliverables that no change owns: the second example board, the agent session of acceptance item 7 with `AGENTS.md` and a skill file, the end of the staged CI matrix (plan §7.3) and the release gate. Hand-overs: `--uses project` in the `kicad-10` fetch (c0013 Open Questions; c0021 Open Questions, default c0025); c0020's acceptance test on the second board (c0020 Open Questions); the DCO check and the history residue scan (c0014 proposal: "CI matrix, wheel job, DCO check and the history residue scan (c0025)").
- **Repaired on 2026-10-04.** The proposal was written before c0049 (parallel test runs) and before the review of that date. The `ci-baseline` deltas are copied again from the living spec, and Decisions 6 and 8 to 15 hold the corrections.
- **Prerequisites.** Five sibling changes own work that this change needs and does not repeat. They are archived before this change's group 6, and c0054 before task 1.2:
  - c0050: the bound of `tests/unit/geometry/test_transform.py::test_composition_rounds_once`, which breaks `make check` at random;
  - c0051: repeatability of `tests/kicad/check/test_canary.py::test_two_run_demo_boards` in `kicad-10`;
  - c0052: the evidence of the KiCad backend in `capabilities`, packaging metadata and the contents of the source distribution, the `template` section of `docs/cli-contract.md`, the residue gate in `docs/provenance.md`;
  - c0053: script copper in the Altium build;
  - c0054: the rule constructor of the design DSL, which `board_40parts` uses.
- **The eight acceptance items** (plan, v0.1), in Fenolite's words:
  1. Both examples pass KiCad's DRC with no violation and no unconnected item on 9.0.x and 10.0.x; the net-assignment comparison finds no difference; the two negative tests are detected with a location; RT1 equals the model; a second `build` gives identical bytes with fills and routes kept; a moved footprint keeps its position through a rebuild and the tracks are intact.
  2. Every demo board (9.0 and 10.0 tags) and the public third-party boards of the corpus pass RT0, RT1 and RT2, and the opaque count reappears on write.
  3. A router plugin leaves no unconnected item on the blink, with KiCad's DRC as the judge.
  4. A generated `.kicad_wks` is accepted by `--drawing-sheet`, A3 and A4 from one file.
  5. The consistency suite passes for every command; every output validates against schema v0; the wheel installs with no dependency; `doctor` reports `kicad-cli`, the routers and the subcommand matrix.
  6. `check` on a demo project is read-only.
  7. An agent session closes the loop on the blink in ten turns or fewer, with every output labelled.
  8. The token fuzz holds on both images: 9.0 rejects exactly the tokens marked for 10.0.
- **What exists.** The blink (`examples/blink_2layer`); the authored mini library (a 32-pin controller, a 0603 resistor, a through-hole LED) in 9.0 and 10.0 forms; CI jobs `unit` (ubuntu and macOS, Python 3.12), `kicad-10`, `kicad-9`, all on `pytest-xdist` workers (c0049); three schema files (`fenolite.envelope.v0.json`, `fenolite.error.v0.json`, `fenolite.artifacts.v0.json`) beside the model schemas; one row in `docs/evidence/residue-history.md` (`v0.0.1.dev0`); `release.yml` (build, residue scan of the artefacts, trusted publishing, a check that the tag equals both version strings); version `0.0.1.dev0`.
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

0. **Corrections of 2026-10-04, made while implementing.** (a) The KiCad major of a build is chosen with `--kicad-version 9|10`; `--target` chooses `kicad` or `altium`. Where this text says "target 9" or "target 10" it means the major. (b) The loop's router is Freerouting 2.4.1 (c0023), not KiCadRoutingTools (c0016): both gates passed, both run in the `routing` job, and Freerouting's two runs repeat (`dsn-repeat` = `equal`), which KiCadRoutingTools does not promise (`H-K-KRT-REPEAT`). On `board_40parts` the `GND` net is left to the zone, which covers both copper layers, and the script adds one ground via under each controller: with a zone on the bottom layer only, or with the router routing `GND` as tracks, Freerouting left 7 `GND` connections open (measured on 2026-10-04). The tests carry `needs_freerouting`.

1. **Order of work.** The example first, then the loop and its recorded boards, then the guide, CI, the record and the version. The version changes last, in its own commit, after every row of the record has a result.

2. **`examples/board_40parts/design.py`.** Forty parts from the mini library only, so no library file is added:
   - two controllers (`Mini:Mini_QFP32_IC`), twenty resistors, eighteen LEDs: an LED bar, each controller driving nine LEDs through nine resistors, plus two pull-up resistors;
   - written with modules (one `Module` per controller with its LEDs), one netclass for the supply nets, a board of 100 mm × 80 mm, two copper layers, a `GND` zone on the bottom layer (c0031);
   - board-wide minimums (clearance, track width, via size) stated through the rule constructor of c0054, so the DRC of the finished board judges the script's own rules. This change uses the constructor as c0054 specifies it and adds nothing to it;
   - the two controllers placed by hand and locked; every other part left to `place --strategy grid`;
   - its own `fp-lib-table` and `sym-lib-table`, as the blink has;
   - header: SPDX `CC0-1.0` and the authored-for-Fenolite line.
   - Rejected: new footprints for variety (capacitors, a connector). They add library work and prove nothing the loop needs; v0.2a's schematic change may add them.
   - Rejected: the official libraries. The example must build with no fetch.

3. **Where the loop runs.** Two test folders:
   - `tests/routing/test_acceptance_loop.py` (`needs_kicad`, `needs_freerouting`): the whole loop from `design.py`, for each example and target (9, 10), on `kicad-cli` 10.0.6. It lives under `tests/routing` so that c0016's `routing` job runs it with no change to that job; the job stays optional for merge and is required for release. Steps: `build`, `place --strategy grid`, `route --router freerouting`, `fill`, `check`, `export --all --manifest`, `render --svg --png`, every one with `--confirm` into a temporary folder.
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
   - `README.md` is also rewritten where it is false for v0.1. The status paragraph ("pre-alpha … being bootstrapped") becomes a statement of the version `0.1`, of what works and a link to the release record. A section `## Install` gives `pip install fenolite`; the development install keeps its own heading. The README does not claim byte identity with KiCad's own re-save (`H-K-FMT-INDENT` is `INFERRED`; RT0 is tree identity). `test_agent_skill.py -k readme` checks these textually. The extras line belongs to c0052.
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
   - a fresh virtual environment, `pip install --no-index --find-links dist fenolite` (so a dependency would fail the install), `fenolite capabilities --json` exits 0, and `python -c "import importlib.metadata as m; r = m.requires('fenolite') or []; assert all('extra ==' in x for x in r), r"`;
   - the wheel holds no file under `tests/`, `private/` or `examples/`.
   - Why not `assert not m.requires('fenolite')`: the metadata lists the packages of every extra as `Requires-Dist` with the marker `extra == '<name>'`, so `requires()` is never empty (12 entries on 2026-10-04) and that assertion always fails. The check above was run against the installed metadata on that date: it passes, and it fails for `foo>=1` and for `foo>=1; python_version < "3.12"`.
   - The residue step runs with the public patterns only (Decision 14).

9. **`kicad-10` fetch.** Step 6 becomes `tools/corpus_fetch.py --uses rt0 --uses libs --uses project --exclude-uses heavy`: `--uses project` is added to the living step and nothing is removed. So `tests/kicad/check/test_check_demos.py::test_demo_projects` runs on real demo projects in CI (item 6). The pytest step keeps `-n auto --dist loadfile` (c0049). The cache key is unchanged (the manifest's hash).
   - **Delta order.** `ci-baseline` is touched by c0016, c0023 and c0025, archived in that order. c0016 ADDs "Routing smoke job" and "Router resource"; c0023 ADDs "Freerouting in the routing job". Neither MODIFIES "Unit CI job on two operating systems" or "kicad-10 oracle job", so both MODIFIED texts here are copied from `openspec/specs/ci-baseline/spec.md` as of 2026-10-04. If an earlier change gains a MODIFIED delta on either, this delta is copied again from that text.

10. **Release record.** `docs/release/v0.1.md`:
    - a table `| item | statement | proof | job | result |`, one row per acceptance item part (about twenty rows), `proof` a pytest node id or a file under `tests/`;
    - the CI run of the release commit (URL), the tool versions, the router and its version;
    - `## Recorded limits` (Decisions 5, 7 and 15), the manual checks (GUI move; live agent session) with their dates;
    - `## Release build` (Decision 14);
    - `## Deferred after v0.1`: what v0.1 does not do, from the roadmap's gap table, with per-command result schemas and the outline snapping tolerance named;
    - `## Verdict`: `pending`, set by the maintainer.
    - `tests/unit/test_release_record.py`: every `proof` names an existing test file, and the function when one is given; every `result` is `met`, `met with a recorded limit`, `not met` or `pending`; no row is `pending` once `__version__` is `0.1.0`; the eight items are all present; the limits of Decision 15, the build rule and the history row of Decision 14 are present.
    - Rejected: a script that computes the verdict from CI. The result of a row is read from the named job of the release commit and written by hand; the guard keeps the table honest about what exists.

11. **Version.** `__version__ = "0.1.0"` in `src/fenolite/__init__.py`; `version = "0.1.0"` and `dependencies = ["fenolite==0.1.0"]` in `packaging/phenolite/pyproject.toml` (`tests/unit/test_pyproject_invariants.py::test_alias_distribution_tracks_fenolite` checks both); one commit, last. `CHANGELOG.md`: `## [Unreleased]` becomes `## [0.1.0] - <date>` with a new empty Unreleased above. `docs/roadmap.md`: v0.1 done, the released line updated.
    - The Unreleased section is cleaned in a commit of its own, before the version commit. Today it has two `### Fixed` blocks, entries of up to 1 728 characters, and entries about underscore-named helpers, tests, CI and `.gitignore`. After the cleaning: one block per heading; entries say what a user of the CLI or the library sees; notes about tests, CI and the repository are merged into one closing entry or removed. The guard checks what it can: no repeated `###` heading, and no backticked name starting with an underscore in `[0.1.0]`.
    - Rejected: a length limit per entry. It is arbitrary, and a long entry about a real feature is not wrong.
    - The tag `v0.1.0`, the GitHub Release and so the PyPI publication (`release.yml`) are the maintainer's. An alpha tag before it (`v0.1.0-alpha1`, roadmap) is independent of this change.

12. **Merge and release gates.** Merge: `unit`, `wheel`, `dco`, `kicad-10`, `kicad-9` (as today, plus `wheel` and `dco`). Release: those, plus `routing` on the release commit, plus the record's verdict. `release.yml` does not enforce this gate: it is a convention, and the record names the run.

13. **DCO job.** `CONTRIBUTING.md` requires a `Signed-off-by:` trailer and nothing checks it. On 2026-10-04 one commit of the main branch lacks it (see "Exceptions" below).
    - `tools/dco_check.py [<revision range>]`: standard library, `git log` as a subprocess; every commit reachable from `HEAD` when no range is given; commits with more than one parent are skipped (the checkout of a pull request is a merge commit made by the runner); a commit passes with a line `Signed-off-by: <name> <<address>>`; one output line per failing commit; exit codes 0, 1, and 2 when `git` fails.
    - Job `dco` in `ci.yml`: `actions/checkout@v4` with `fetch-depth: 0`, then `python3 tools/dco_check.py`. No `uv`, no dependency.
    - `tests/unit/test_dco_check.py` builds temporary repositories with `git`, which every unit runner has.
    - **Exceptions (added on 2026-10-04).** The first run found one unsigned commit on the main branch: `19b74bb`, the squash merge of pull request 2 made with the GitHub button, authored by the maintainer. The history of the main branch is not rewritten, so `tools/dco_exceptions.txt` lists full hashes with a reason and the tool skips them. The maintainer confirms each entry; the release record names the file.
    - Rejected: a third-party DCO action or app. It is one more dependency of the release gate, and the rule is ten lines.
    - Rejected: comparing the trailer with the author. The certificate is the signer's statement, and squashed commits are signed by the maintainer.

14. **Release build, history scan, hook** (maintainer's decisions of 2026-10-04).
    - **Where the artefacts are built.** From the tagged commit in a clean checkout: the release workflow's checkout, a fresh clone of the tag, or `git worktree add <dir> v0.1.0`. Never from the maintainer's working tree, which may hold uncommitted and untracked files: a local source distribution packs untracked files. A clean working tree is therefore not a condition of the release. The rule and the commands are in `## Release build` of the record, and the build is rehearsed once before the version commit in a worktree of `HEAD`.
    - **Residue scan: public gate only.** CI and `release.yml` scan with the five public patterns and the public blob list. The private gate is not run for v0.1.0, and no task of this change reads, names or needs a private list. A task runs `uv run python tools/residue/scan.py --history` (public gate) and adds the row `v0.1.0` to `docs/evidence/residue-history.md` with the private gate `not run`. That page's first paragraph says today "Run before each tag with the private token and blob lists configured"; the task corrects it to say that the private gate is optional and was not run for v0.1.0. The record states the same limit.
    - **Pre-commit hook.** `make hooks` installs `tools/hooks/pre-commit`. The hook runs `tools/residue/scan.py --staged`, which works with the public patterns alone, so the task needs no other file. Worktrees share the hooks folder. Proof: `test -x "$(git rev-parse --git-common-dir)/hooks/pre-commit"`.
    - Rejected: a clean working tree as a release condition. The maintainer keeps local files uncommitted, and a clean checkout of the tag removes the risk without touching them.
    - Rejected: a row that says the private gate was on. It was not run.

15. **Limits stated in the record.** The record says what is true, with these fixed entries:
    - **Item 2.** From `docs/evidence/kicad-rt2.md` and `tests/kicad/check/test_corpus_rt.py`: RT0 and RT1 hold on 24 boards (21 readable non-heavy demo boards, 3 third-party boards); 2 rows tagged `heavy` are not run in CI; one demo file is malformed at its tag; RT2 holds on 23 and is not judged on 1, whose DRC report KiCad does not repeat; RT2 on 9.0.9 covers the 5 `rt2-9` rows. The numbers are read again from the evidence page when the record is filled. The row is `met with a recorded limit`.
    - **Item 5, schemas.** `schemas/` holds the envelope, the error and the artefact manifest (and the model). Every envelope names `schema: fenolite.<command>.v0`, and no such file exists. This change adds none (non-goal). The row is `met with a recorded limit` with the sentence "envelope, error and manifest schemas only", and per-command result schemas go to `## Deferred after v0.1` and to the roadmap (task 6.3).
    - **Residue scan.** Public gate only (Decision 14).
    - **Container refill.** `H-K-CLI-DOCKER` is settled by `tests/kicad/fill/test_docker_cli.py::test_container_matches_local`, which skips without Docker or the image. Checked on 2026-10-04: no workflow names Docker; `kicad-9`, `kicad-10` and c0016's `routing` job run inside a container and cannot start one; `unit` and `wheel` hold no KiCad binary to compare with. So the test never runs in CI. The register row and `docs/evidence/kicad-fill.md` record "verified locally only" with the date, the Docker version, the image digest and the `kicad-cli` version; the level stays `INFERRED`.
    - **Board outlines.** 3 of the 21 readable non-heavy demo boards do not chain into a closed outline without a snapping tolerance; `place` reports `place.no-outline` on them. Accepted as a limit of v0.1: `H-G-EDGE-EXACT` and `H-G-PLACE-OUTLINE` stay `INFERRED`, and the tolerance question (1 µm; chaining the edge items of footprints) goes to `## Deferred after v0.1` and to the roadmap. The acceptance items use built boards, whose outlines chain.
    - Not deferred: the DSL rule constructor, which c0054 delivers in v0.1.
    - Rejected: a Docker-capable job now. It needs a KiCad 10.0.6 binary on the runner beside the image, which no job has.
    - Rejected: writing per-command schemas here. Eleven commands, each with a result shape to specify and a consistency test: a change of its own.

## Files and public API

| file | content |
|---|---|
| `examples/board_40parts/design.py`, `fp-lib-table`, `sym-lib-table` (new) | Decision 2 |
| `examples/README.md` (extended) | the new row |
| `tests/routing/test_acceptance_loop.py`, `tests/_acceptloop.py` (new) | `run_loop(example, target, router, out) -> LoopResult(steps, board)`; `test_loop`, `test_skill_block` |
| `tests/kicad/acceptance/test_finished.py` (new) | Decision 4 |
| `tests/data/acceptance/{blink_2layer,board_40parts}_t{9,10}/` (new) | recorded projects, with `MANIFEST.toml` rows |
| `agent/SKILL.md` (new); `AGENTS.md`, `README.md` (extended; README status and install rewritten) | Decision 6 |
| `tools/dco_check.py`, `tests/unit/test_dco_check.py` (new) | `main(argv: list[str] \| None = None) -> int`; Decision 13 |
| `docs/evidence/residue-history.md`, `docs/evidence/kicad-fill.md`, `docs/hypotheses.md` (extended) | the `v0.1.0` row (Decision 14); `H-K-CLI-DOCKER` verified locally only (Decision 15) |
| `tests/unit/test_agent_skill.py`, `tests/unit/test_release_record.py` (new) | guards |
| `.github/workflows/ci.yml`; `tests/unit/test_ci_workflow.py` (extended) | Decisions 7 to 9 and 13 |
| `tests/_fakecli.py`, `tests/_resources.py` (extended) | the Windows wrapper; `posix_tools` |
| `docs/release/v0.1.md` (new) | Decision 10 |
| `src/fenolite/__init__.py`, `packaging/phenolite/pyproject.toml` (version and pin), `CHANGELOG.md`, `docs/roadmap.md` | Decision 11 |

No change under `src/fenolite/` except the version string.

## Sources registered by this change

None: this change reads no format fact. S-0235 to S-0239 stay unused.

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-K-REL-LOOP40 | Freerouting 2.4.1 leaves no unconnected item on `board_40parts` for targets 9 and 10 within 600 s, and the finished board passes KiCad's DRC | `tests/routing/test_acceptance_loop.py::test_loop` | on 10.0.6: `check` exits 0 for both targets with no script copper in `design.py`. If not, Decision 5 applies and the row records the number of nets the router closed |
| H-G-REL-WINDOWS | The unit, consistency and residue suites pass on `windows-latest` with Python 3.12, with fewer than 5 % of the tests skipped as `posix-only fake tool` | the `unit (windows-latest, py3.12)` run | the run passes and its summary gives the skip count. If not, Decision 7's cut applies |

Ids used without changing their level: `H-K-CLI-DOCKER` (its result text changes, Decision 15), `H-G-EDGE-EXACT`, `H-G-PLACE-OUTLINE`, `H-K-FMT-INDENT`, `H-K-01`, `H-K-KRT-ROUTE`, `H-K-KRT-REPEAT`, `H-K-FILL-LIFT`, `H-K-EXPORT-FILES`, `H-K-PLACE-MOVE`.

## Evidence level per behaviour (before merge)

| behaviour | level required | proof |
|---|---|---|
| Loop on both examples, both targets | KICAD-VERIFIED (10.0.x) fresh; KICAD-VERIFIED (9.0.x, 10.0.x) on the recorded boards | `test_acceptance_loop.py`, `test_finished.py` |
| Rebuild identity, moved footprint | mechanical, judged on files KiCad accepts | `test_finished.py` |
| Agent guide | mechanical | `test_agent_skill.py`, `test_skill_block` |
| CI matrix, wheel, DCO | mechanical | `test_ci_workflow.py`, `test_dco_check.py`; the jobs' runs |
| Residue scan of the tree, the wheel and the history | public gate only; the private gate is not run | the CI steps; the `v0.1.0` row of `docs/evidence/residue-history.md` |
| Container refill | INFERRED, verified locally only | `tests/kicad/fill/test_docker_cli.py` on a machine with Docker |
| Output schemas | mechanical; envelope, error and manifest only | `tests/consistency/test_cli_consistency.py` |
| Outline of read boards | INFERRED (3 of 21 demo boards do not chain) | `tests/corpus/test_outline_corpus.py::test_outlines` |
| Release record | each row at the level of its proof | `test_release_record.py` |

## Budget (6.75 days; the roadmap gives 5)

| work | days |
|---|---|
| `board_40parts` | 1.0 |
| loop test, recorded boards | 1.0 |
| finished-board tests on both majors | 1.0 |
| agent guide and its tests | 0.75 |
| `unit` matrix and Windows portability | 0.75 |
| `wheel` job, `--uses project` | 0.5 |
| release record, version, closing | 0.75 |
| DCO tool and job | 0.25 |
| README rewrite, changelog cleaning | 0.5 |
| build rehearsal, history row, recorded limits | 0.25 |
| **total** | **6.75** |

Cut order: (1) the Windows run (to v0.2a, recorded); (2) Python 3.13; (3) `board_40parts` routed by the router (Decision 5's script copper). Not optional: the loop on the blink on both majors, the wheel job, the DCO job, the guide's executed block, the record with its limits.

## Risks / Trade-offs

- [An acceptance item fails late] → the record says `not met`, the fix goes to the owning change, and the version commit waits. This change never weakens a test to pass.
- [Recorded boards go stale when a writer changes] → `test_finished.py` rebuilds over them and requires no planned write; a writer change that alters bytes fails there and the boards are recorded again in the same pull request.
- [The grid placer and the router fight on a dense board] → the board is 100 mm × 80 mm for forty small parts; the grid pitch is in `design.py`.
- [Windows runners are slow or flaky] → one run, no KiCad; cut 1.
- [The fetch of demo projects makes `kicad-10` slower] → the cache holds them; heavy rows stay excluded.
- [A sibling change is late] → task 1.2 waits for c0054 and group 6 for c0050 to c0053: `make check` and the `kicad-10` run are not trusted without c0050 and c0051.
- [The private residue gate is not run] → stated in the record and in the history page; the public patterns and the public blob list are what v0.1.0 claims.
- [Someone builds an artefact from a working tree] → `release.yml` builds from a clean checkout, and the record's `## Release build` gives the local commands.

## Migration Plan

Additive, except the version. To roll back before the tag, revert the version commit; after the tag, releases are not withdrawn and a fix is `0.1.1`.

## Open Questions

- **Release with a `met with a recorded limit` row?** Default: yes, the record names it; `not met` blocks the version commit unless the maintainer writes the exception in the record.
- **Python 3.14.** Default: not in the matrix until its release is supported by the pinned tools.
- **Is the `routing` job required for merge after v0.1?** Default: no (c0016); it is required for a release.
- **Level of `H-K-CLI-DOCKER`.** Default: it stays `INFERRED`, with "verified locally only" in its result; the maintainer may accept a local run as `KICAD-VERIFIED (10.0.x)`.
- **`dco` as a required check.** Default: yes, with `wheel`; branch protection is a repository setting.
- **Milestone of per-command result schemas and of the outline snapping tolerance.** Default: v0.2a for both.
- **Changelog rule.** Default: the two mechanical checks of Decision 11; what counts as an internal note is the editor's judgement.
- **An alpha tag before this change.** The roadmap names `v0.1.0-alpha1`; the maintainer decides, and it needs nothing from this change.
