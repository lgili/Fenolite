## 0. Entry check

- [ ] 0.1 Read `docs/roadmap.md` and `openspec/changes/`: every v0.1 change is archived or moved to a later milestone by the cut order, and c0016's gate verdict in `docs/evidence/routing.md` names the router. List under this task the changes still open; while any v0.1 change is open, do only tasks 1.x to 4.x and leave group 5 open. Proof: the list and its date are written under this task.

## 1. Registers and the second example

- [ ] 1.1 Add the rows `H-K-REL-LOOP40` (backend `kicad`) and `H-G-REL-WINDOWS` to `docs/hypotheses.md`, level `INFERRED`, result `pending`, with the test and criterion of `design.md`, and the paragraph "Change c0025 (release v0.1) adds …". Proof: `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_provenance.py`; `grep -cE '^\| H-[KG]-REL-' docs/hypotheses.md` prints `2`.
- [ ] 1.2 Write `examples/board_40parts/design.py` with its `fp-lib-table` and `sym-lib-table` (design Decision 2), add its row to `examples/README.md`, and write the new `tests/unit/test_examples.py` (scenarios of "Second example board"). Proof: `uv run pytest tests/unit/test_examples.py tests/residue`; `uv run python tools/residue/scan.py` exits 0.

## 2. Acceptance loop and finished boards

- [ ] 2.1 Write `tests/routing/_loop.py` (`run_loop`) and `tests/routing/test_acceptance_loop.py::test_loop` (requirement "Acceptance loop"). Run it on the blink first. Proof: `FENOLITE_REQUIRE=kicad,router uv run pytest tests/routing/test_acceptance_loop.py -k "loop and blink" -rA` on the local KiCad 10.0.6.
- [ ] 2.2 Run the loop on `board_40parts`. If the router leaves nets open within 600 s, apply design Decision 5: script the remaining copper in `design.py`, and write the two counts under this task. Record the four finished projects with `FENOLITE_ACCEPTANCE_WRITE=1` and declare them in `tests/data/MANIFEST.toml`. Proof: `FENOLITE_REQUIRE=kicad,router uv run pytest tests/routing/test_acceptance_loop.py -k loop -rA`; `uv run pytest tests/residue tests/unit/test_repo_layout.py`; `uv run python tools/residue/scan.py` exits 0.
- [ ] 2.3 Write `tests/kicad/acceptance/test_finished.py` (requirement "Finished boards pass on both majors"), reusing c0020's negative-test helpers, and add `tests/kicad/acceptance` to the `sys.path` list of `tests/kicad/conftest.py`. A failure here is reported to the change that owns the behaviour and is not worked around; note each under this task. Proof: `FENOLITE_REQUIRE=kicad uv run pytest tests/kicad/acceptance -rA` on the local KiCad 10.0.6 and inside the pinned 9.0.9 image.

## 3. Agent guide

- [ ] 3.1 Write `agent/SKILL.md`, the loop block in `README.md` and the link in `AGENTS.md` (design Decision 6), and `tests/unit/test_agent_skill.py` (hermetic scenarios of "Agent guide is executable"). Proof: `uv run pytest tests/unit/test_agent_skill.py tests/residue`.
- [ ] 3.2 Write `test_skill_block` in `tests/routing/test_acceptance_loop.py`. Proof: `FENOLITE_REQUIRE=kicad,router uv run pytest tests/routing/test_acceptance_loop.py::test_skill_block -rA` on the local KiCad 10.0.6.

## 4. CI matrix

- [ ] 4.1 Make the test helpers portable: the `.cmd` wrapper in `tests/_fakecli.py`, `posix_tools` in `tests/_resources.py`, and path comparisons through `as_posix()` where a test compares strings. Extend the `unit` matrix to the five combinations and `tests/unit/test_ci_workflow.py` (MODIFIED "Unit CI job on two operating systems"). Write the Windows skip count under this task; if it is 5 % or more, apply the cut of design Decision 7 and record it. Proof: `uv run pytest tests/unit/test_ci_workflow.py`; the five `unit` runs of the pull request are linked under this task.
- [ ] 4.2 Add the `wheel` job and change the `kicad-10` fetch to `--uses rt0 --uses project`, with their checks in `tests/unit/test_ci_workflow.py` (requirements "Wheel job", "kicad-10 oracle job"). Proof: `uv run pytest tests/unit/test_ci_workflow.py`; the `wheel` and `kicad-10` runs are linked under this task, and the `kicad-10` log shows the demo-project test passed, not skipped.

## 5. Release record and version

- [ ] 5.1 Write `docs/release/v0.1.md` (design Decision 10) with every row `pending`, and `tests/unit/test_release_record.py` (scenarios of "Release record"). Proof: `uv run pytest tests/unit/test_release_record.py`.
- [ ] 5.2 Fill the record from the CI runs of the head commit: `unit`, `wheel`, `kicad-9`, `kicad-10` and `routing`. Write each row's result, the recorded limits, the tool versions and the run URLs. Ask the maintainer for the two manual checks (a footprint moved in KiCad's editor; a live agent session) and write what they report, with dates. Leave `## Verdict` as `pending`. Proof: `uv run pytest tests/unit/test_release_record.py`; `grep -c '| pending |' docs/release/v0.1.md` prints `0`.
- [ ] 5.3 Only when no row is `not met`, or the maintainer has written the exception in the record: set the version to `0.1.0` in `src/fenolite/__init__.py` and `packaging/phenolite/pyproject.toml`, and move the Unreleased entries of `CHANGELOG.md` under `## [0.1.0] - <date>`, in one commit. Do not tag and do not publish. Proof: `uv run pytest tests/unit/test_release_record.py -k version tests/unit/test_pyproject_invariants.py`; `uv build` succeeds.

## 6. Closing

- [ ] 6.1 Run the residue and full test suites. Proof: `uv run pytest tests/residue` and `uv run pytest -q` exit 0; `uv run python tools/residue/scan.py` exits 0; `make check` passes; `openspec validate c0025-release-v0-1 --strict --no-interactive` passes; `gh pr checks` shows `unit` (five runs), `wheel`, `kicad-9`, `kicad-10` and `routing` passing.
- [ ] 6.2 Update the evidence labels: `H-K-REL-LOOP40` becomes `KICAD-VERIFIED (10.0.x)` or records the net counts and the script copper; `H-G-REL-WINDOWS` records the run and its skip count, or the cut. Proof: `uv run pytest tests/unit/test_provenance.py tests/unit/test_hypotheses_register.py`.
- [ ] 6.3 Add to `CHANGELOG.md`: "v0.1 acceptance: a second example board of forty parts, the loop proved on both examples and both KiCad majors, the agent guide `agent/SKILL.md`, the `wheel` job, Windows and Python 3.11/3.13 in CI, and the release record `docs/release/v0.1.md`". Update `docs/roadmap.md`: v0.1 done, the released line, the measured pace. Proof: `git diff CHANGELOG.md docs/roadmap.md`.

_Note: the tag `v0.1.0`, the GitHub Release and the PyPI publication are the maintainer's actions after `## Verdict` is written; they are calendar events, not tasks. The change is archived after the maintainer's verdict._
