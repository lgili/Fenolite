# Guidance for AI agents working on Fenolite

Read this file before changing anything. Humans: this is also the short version of `CONTRIBUTING.md`.

## Workflow

1. **OpenSpec first.** Every change lives in `openspec/changes/<id>/` with `proposal.md`,
   `design.md`, `specs/` and `tasks.md`. Do not write code that no task asks for. Implement tasks
   in order, tick `- [x]` only after the task's proof command passed.
2. **One fix per iteration.** Make one focused change, run its proof, then move on.
3. **While iterating:** `make check-fast` (ruff check, ruff format --check, pyright src, residue scan,
   and the tests that need no `kicad-cli`, corpus or KiCad libraries) plus the tests of the files you
   touched, for example `uv run pytest tests/kicad/board/test_x.py -q`.
4. **Before finishing:** `make check` (the same checks and every test, on parallel workers) must pass.
   Run it once, on the rebased branch, right before the merge. Never start several full suites at
   the same time on one machine: agents in parallel worktrees use `make check-fast`.
5. Update `CHANGELOG.md` under `## [Unreleased]` for every change.
6. **Teach what you add.** A change that adds a public command, a public DSL name or a `FEN-` code
   adds a tested line to a page of the agent guide (`src/fenolite/agent/skill/references/`):
   `tests/unit/agent/test_pages.py` fails until it does. After a change of a command's arguments or of
   `fenolite.dsl`, run `uv run python tools/gen_agent_guide.py`.

## Hard rules

- **Clean-room.** Never add code, constants, seeds, fixtures, statistics, vocabularies, templates or
  examples taken from an employer, a private project or any organisation. Test data is authored for
  Fenolite or fetched from public sources declared in the corpus manifest.
- **Format knowledge from public sources only.** Record each fact in `docs/formats/<backend>/*.md`
  with its source (listed in `docs/evidence/sources.md`) and an evidence label. Never copy or
  transcribe third-party parser code or grammar files, and never decompile vendor software.
- **No runtime dependencies in the core.** `pyproject.toml` `dependencies` stays empty; third-party
  packages go to an extra and are imported lazily.
- **Copyleft only across a process boundary.** Run GPL/AGPL tools as subprocesses; never import them.
- **Never commit** anything under `private/`, KiCad official library files, or absolute user paths.
- Every `.py` file starts with the SPDX and copyright lines.

## Conventions

- The design model (entities, ids, units, canonical JSON) is described in `docs/design-model.md`.

- Lengths: integer nanometres. Angles: integer microdegrees. No floats in the model.
- Evidence labels: `KICAD-VERIFIED`, `ORACLE-VERIFIED(<tool>)`, `CORPUS-VERIFIED`,
  `ALTIUM-VERIFIED(kit|author-report)`, `INFERRED`, `UNKNOWN`, `UNVERIFIED` (lowest wins).

## Using the `fenolite` CLI (contract v0, `docs/cli-contract.md`)

1. Start with `fenolite capabilities --json`: commands, extras, external tools and their versions.
2. Output is JSON whenever stdout is not a terminal; pass `--json` anyway to be explicit. Use
   `--fields a,b.c` to keep the reply small.
3. Read the exit code first: 0 ok, 1 bug, 2 usage, 3 bad input, 4 confirmation required,
   5 findings (read `issues`), 6 external tool missing, 7 lossy operation refused. On non-zero,
   stderr holds one error object with `code`, `message`, `hint`, `retryable`.
4. Writing commands never write by default: run with `--dry-run`, check `result.plan`, then re-run
   with `--confirm`. The `receipt` lists every written file with its SHA-256.
5. Pass `--seed` and `--timestamp` when you need byte-identical outputs.
6. Every reply carries `evidence.level`; treat anything below `KICAD-VERIFIED` as unconfirmed.
7. The loop is `capabilities`, `build`, `place`, `route`, `fill`, `check`, `export`, `render`, `inspect`:
   `src/fenolite/agent/skill/SKILL.md` holds the ten commands and what to do for each exit code.
   `fenolite guide start --text` prints that page for the installed version.
