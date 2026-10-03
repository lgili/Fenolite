# Fenolite

**Headless, agent-first PCB design automation in Python.** Fenolite lets an engineer — or an AI
coding agent — generate, open, verify, compare, convert and export printed-circuit-board projects
from Python code or a JSON-speaking command line, without a GUI. KiCad is the first backend (its
files, with `kicad-cli` as the verification oracle); a second backend for another major commercial
format family follows.

> **Status: pre-alpha.** The repository is being bootstrapped. Nothing here is ready for real
> boards yet. Follow `openspec/changes/` to see what is being built and in which order.

*Fenolite* is the Portuguese word for phenolic board material — the laminate many of us etched our
first circuit boards on.

## Principles

- **Agent-first CLI.** JSON on stdout when not attached to a terminal, a fixed envelope, typed
  errors, a small exit-code vocabulary, and writes only with `--confirm` (`--dry-run` shows the plan).
- **Evidence on every answer.** Each result says how it was verified (see below). Nothing is
  claimed that was not checked.
- **No silent information loss.** What Fenolite does not understand in a file is preserved, and a
  lossy operation stops unless explicitly allowed.
- **Small, exact model.** Integer nanometres and microdegrees, stable ids, canonical JSON that
  diffs cleanly in Git.
- **Stdlib-only core.** `pip install fenolite` installs no other package; heavier features are
  optional extras.
- **Your templates, not ours.** Sheet frames and title blocks are generated from your own spec;
  Fenolite ships no organisation's templates, rules or libraries.

The model is described in `docs/design-model.md`; the CLI contract in `docs/cli-contract.md`. Fabrication
files and review renders (`fenolite export`, `fenolite render`) are described in `docs/exports.md`.

## Evidence labels

| Label | Meaning |
|---|---|
| `KICAD-VERIFIED` | accepted by `kicad-cli` of the stated version, and the claim confirmed by its output |
| `ORACLE-VERIFIED(<tool>)` | an independent parser or tool agreed |
| `CORPUS-VERIFIED` | round-trip holds on public files listed in the corpus manifest |
| `ALTIUM-VERIFIED(kit)` | confirmed by a native-tool acceptance run with archived results |
| `ALTIUM-VERIFIED(author-report)` | reported by the author from ordinary use; never enough for a release claim |
| `INFERRED` | deduced from public documentation; a hypothesis in `docs/hypotheses.md` tracks it |
| `UNKNOWN` | bytes or fields preserved without interpretation |
| `UNVERIFIED` | default for anything new |

A command's overall label is the lowest label of the steps it ran.

## Install (development)

```bash
git clone <this repository>
cd fenolite
uv sync --extra dev
uv run fenolite --version
make check
```

Talk to it like an agent does:

```bash
uv run fenolite capabilities --json --fields tools          # what is installed here
uv run fenolite capabilities --text                         # the same, for humans
echo $?                                                     # 0 ok, 2 usage, 4 confirm, 5 findings …
```

Optional extras: `geo` (polygon booleans), `kicad-ipc` (live KiCad session), `route` (Freerouting
client), `mcp` (MCP server), `oracles` (Gerber re-parsers used in tests), `dev`.

## Licence and provenance

Apache-2.0 (`LICENSE`, `NOTICE`). Format knowledge comes only from public sources; see `LEGAL.md`
for the clean-room rules and `CONTRIBUTING.md` for how to contribute. Every CI run and every commit
(after `make hooks`) passes a residue scan (`tools/residue/`) that blocks absolute paths, internal
identifier shapes and known non-public files; see `docs/provenance.md` for the provenance rules. AI agents working in this
repository: read `AGENTS.md` first.
