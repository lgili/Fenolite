# Contributing to Fenolite

Thank you for helping. Fenolite is spec-driven, agent-friendly and strict about provenance.

## Workflow

1. **One change per pull request.** Every change starts as an OpenSpec change under
   `openspec/changes/<id>/` (`proposal.md`, `design.md`, `specs/`, `tasks.md`). No code lands
   without one. See `openspec/README.md`.
2. Implement the tasks in order; each task names the command that proves it.
3. Run `make check` (ruff, ruff format, pyright, pytest) before pushing; CI runs the same steps.
4. Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/)
   (`feat(model): …`, `fix(kicad): …`, `docs: …`, `test: …`, `chore: …`).

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
