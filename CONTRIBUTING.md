# Contributing to Fenolite

Thank you for helping. Fenolite is spec-driven, agent-friendly and strict about provenance.

## Workflow

1. **One change per pull request.** Every change starts as an OpenSpec change under
   `openspec/changes/<id>/` (`proposal.md`, `design.md`, `specs/`, `tasks.md`). No code lands
   without one. See `openspec/README.md`.
2. Implement the tasks in order; each task names the command that proves it.
3. While you work, run `make check-fast`: ruff, ruff format, pyright, the residue scan and the tests
   that need no `kicad-cli`, corpus or KiCad libraries, plus focused tests for the affected files.
   Complete validation (`make check`) runs in GitHub CI, including when working on the maintainer's
   Windows PC or in another local worktree. Publish an authorized batch to its working branch and
   verify the required CI jobs on that exact commit before merge or archive. Never treat an
   interrupted local run as passed. See `tests/README.md`, "Parallel runs".
4. Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/)
   (`feat(model): …`, `fix(kicad): …`, `docs: …`, `test: …`, `chore: …`).
5. **Agent evaluation.** `tools/agent_eval` measures whether a fresh AI agent can use Fenolite
   (`tools/README.md`, "Agent evaluation"). `make agent-eval TASK=led-indicator RUNNER=replay` plays a
   task's reference solution without any agent, and the test suites do the same, so a change that
   breaks a solution fails them: repair the solution, or the code. A run with a real agent costs money:
   only a maintainer starts one, by hand, with `--yes`, one task first, never from CI and never from an
   agent session. Record it with `--record` in `docs/evidence/agent-eval.md`; a row is one sample and
   supports no release claim.
5. **The agent guide follows the code.** A change that adds a public command, a public DSL name or a
   `FEN-` code adds a tested line to a page of the agent guide
   (`src/fenolite/agent/skill/references/`): a `fenolite-cmd` line for a command, a use in a
   `fenolite-design` block for a name (or a reason in `fenolite.agent.guide.DSL_NOT_TAUGHT`), a row of
   the page `recovery` for a code. `tests/unit/agent/test_pages.py` names what is missing. The pages
   `commands` and `dsl-reference` are generated: run `uv run python tools/gen_agent_guide.py` after a
   change of a command's arguments or of `fenolite.dsl`; `make check-fast` runs its `--check`.
   A `fenolite-design` block is built for KiCad 9 and 10; the fence argument `altium` builds it for
   Altium instead, and `kicad10` for KiCad 10 alone, for a feature that a KiCad 9 board cannot hold
   (`fenolite.agent.guide.DESIGN_TARGETS`).

## The viewer's visual tests

`tests/visual` draws one authored fixture per scene kind of `fenolite view` (KiCad and Altium boards and
sheets, footprint and symbol libraries, a Draftsman drawing, an output job) in Chromium and compares each
screenshot with its reference in `tests/visual/refs/`. Within two levels per channel, at most 0.1 % of the
pixels may differ. Interaction tests check selection, measurement, the unit switch and cross-probing.

- They need Node with Playwright 1.63.0 and its Chromium (`npm install playwright@1.63.0`, then
  `npx playwright install chromium`; `FENOLITE_PLAYWRIGHT` may name the package's folder) and skip without
  them. `make check-fast` does not run them; `make visual` does, and so does CI's `viewer` job.
- Chromium draws every text with DejaVu (`tests/visual/fonts.conf`, `fonts-dejavu-core` 2.37-8 of Ubuntu
  24.04), so the references hold on other machines with that package.
- After an intended change of what the page draws, run `uv run python tools/update_view_refs.py` (or name
  the fixtures to rewrite), look at every image it wrote, and commit them with the change. A failing test
  leaves its screenshot and a difference image (changed pixels in magenta) beside it; CI keeps them as the
  `viewer-differences` artefact.

## Parallel worktrees

Several contributors or agents often work at once, each in its own worktree on one machine. A full
suite uses every core, so two of them at once are slower than one after the other.

- While working on a task, run `make check-fast` and the tests of the files you touched, for
  example `uv run pytest tests/kicad/board/test_x.py -q`.
- Complete validation runs in CI on the rebased branch; check the required jobs on that exact commit
  before the merge. Keep local work to `make check-fast` and focused proofs.
- Never start several full suites on one machine. CI's parallel jobs use separate runners.

## Developer Certificate of Origin

Every commit MUST carry a `Signed-off-by:` trailer certifying the
[Developer Certificate of Origin 1.1](https://developercertificate.org/):

```bash
git commit -s -m "feat(core): add integer length units"
```

By signing off you state that you wrote the contribution or have the right to submit it under
the Apache License 2.0.

## Provenance rules (read `LEGAL.md`)

- Learn formats only from public documentation and from files you are entitled to read.
- Never decompile vendor software; never copy, transcribe or compile third-party parser code
  or grammar files into Fenolite. Reading public sources for facts is fine: record each fact in
  `docs/formats/` with its source.
- Never add files, values, names, templates or examples that belong to an employer or any other
  organisation. Test data is authored for Fenolite or fetched from public sources listed in the
  corpus manifest.
- Copyleft tools run only as external processes; they never become dependencies.

## Allowed vs forbidden derivation

| Allowed | Forbidden |
|---|---|
| Reading a public format page and writing in `docs/formats/kicad/pcb.md`: "a `via` node carries `(at X Y)`, `(size D)`, `(drill D)`, `(layers A B)` — source S-0007", then implementing the parser from that page. | Opening a GPL parser's source, copying or paraphrasing its function that reads `via` nodes, or converting its grammar file into a Python parser. |
| Measuring a record layout on a public, licence-compatible sample file and recording the offsets with the file's manifest id. | Measuring anything on files you are not entitled to share or use (for example an employer's boards) or reusing values measured on them earlier. |
| Running a copyleft tool as a subprocess and comparing its output with Fenolite's (an oracle). | Adding that tool, or a library that links it, to `pyproject.toml`. |
| Writing an example board from scratch for `examples/`. | Recreating a board, template, title block, rule set or part list you know from work. |

## Code style

- Python ≥ 3.11, stdlib-only core, full type hints (`pyright` strict on `src/`).
- Every `.py` file starts with the SPDX and copyright lines (see any existing file).
- Lengths are integer nanometres; angles are integer microdegrees; no floats in the model.

## Releases

A release is a pushed tag `vX.Y.Z`: the release workflow checks, builds, publishes to PyPI and creates
the GitHub Release. The steps are in [`docs/releasing.md`](docs/releasing.md).
