# Contributing to Fenolite

Thank you for helping. Fenolite is spec-driven, agent-friendly and strict about provenance.

## Workflow

1. **One change per pull request.** Every change starts as an OpenSpec change under
   `openspec/changes/<id>/` (`proposal.md`, `design.md`, `specs/`, `tasks.md`). No code lands
   without one. See `openspec/README.md`.
2. Implement the tasks in order; each task names the command that proves it.
3. While you work, run `make check-fast`: ruff, ruff format, pyright, the residue scan and the tests
   that need no `kicad-cli`, corpus or KiCad libraries. Run `make check` (the same checks and every
   test) once before pushing; CI runs the same steps. Both run the tests on parallel workers; see
   `tests/README.md`, "Parallel runs".
4. Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/)
   (`feat(model): …`, `fix(kicad): …`, `docs: …`, `test: …`, `chore: …`).
5. **Agent evaluation.** `tools/agent_eval` measures whether a fresh AI agent can use Fenolite
   (`tools/README.md`, "Agent evaluation"). `make agent-eval TASK=led-indicator RUNNER=replay` plays a
   task's reference solution without any agent, and the test suites do the same, so a change that
   breaks a solution fails them: repair the solution, or the code. A run with a real agent costs money:
   only a maintainer starts one, by hand, with `--yes`, one task first, never from CI and never from an
   agent session. Record it with `--record` in `docs/evidence/agent-eval.md`; a row is one sample and
   supports no release claim.

## Parallel worktrees

Several contributors or agents often work at once, each in its own worktree on one machine. A full
suite uses every core, so two of them at once are slower than one after the other.

- While working on a task, run `make check-fast` and the tests of the files you touched, for
  example `uv run pytest tests/kicad/board/test_x.py -q`.
- Run `make check` once, on the rebased branch, right before the merge.
- Never start several full suites at the same time on one machine. If one is running, wait for it.

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
