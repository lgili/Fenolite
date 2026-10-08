# Fenolite

**Headless, agent-first PCB design automation in Python.** Fenolite lets an engineer — or an AI
coding agent — generate, open, verify, compare, convert and export printed-circuit-board projects
from Python code or a JSON-speaking command line, without a GUI. KiCad is the first backend (its
files, with `kicad-cli` as the verification oracle); a second backend for another major commercial
format family follows.

> **Status: version 0.3.** A design script becomes a KiCad project with a board and a schematic, for
> KiCad 9.0 and 10.0. The loop below works on two-layer boards: the board is placed, routed by an
> external router, filled, checked by KiCad's own design-rule check and exported to fabrication files.
> The schematic is judged by KiCad's own electrical rules check, by its netlist and by its schematic
> parity test. Version 0.3 adds the write side of the second backend: `build --target altium` writes a
> complete Altium project, and Altium files are checked and compared without a tool. What was proved for
> this version, and its limits, are in `docs/release/v0.3.md` (`docs/release/v0.2.md` and
> `docs/release/v0.1.md` for the versions before). Every Altium write is experimental: no write kind has
> the evidence to leave that state yet, and most Altium evidence is `INFERRED` or an author report.

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

The model is described in `docs/design-model.md`; the CLI contract in `docs/cli-contract.md`.

## What version 0.3 does

- **The schematic.** `fenolite build` writes the schematic of the design beside the board, one sheet
  per module, which KiCad's ERC and parity test accept on 9.0 and 10.0 (`docs/schematic.md`).
- **Checks.** `fenolite check` runs KiCad's ERC and DRC, compares the netlist of the schematic with the
  model and the board, and compares schematic and board without a tool (`fenolite netlist`,
  `fenolite parity`).
- **Tables and files.** The bill of materials and the placement table (`fenolite bom`, `fenolite pnp`)
  are rendered through a column template that you write (`docs/assembly.md`). Fabrication files and
  review renders (`fenolite export`, `fenolite render`) are described in `docs/exports.md`, and
  `fenolite manifest` lists every design file and artefact with its SHA-256 and a state.
- **Small questions.** `diff`, `roundtrip`, `fmt`, `explain`, `restore`, `net`, `region`, `neighbors`
  and `pads` answer one thing each, with paging and a concise form.
- **The layout is kept.** A board edited in KiCad survives a rebuild, also when a module or a net is
  renamed, and `fenolite sync --to-source` writes the placements into the source tree (`docs/lens.md`).
- **The design script.** Six more rule kinds (hole to hole, hole clearance, annular width, courtyard,
  silkscreen, creepage), exact quantities, typed interfaces, and your own drawing sheet and title block
  (`docs/dsl.md`, `docs/sheet-templates.md`).
- **Altium files are read.** `inspect`, `check`, `diff` and `equivalent` take Altium documents,
  libraries and projects, read-only and without a tool (`docs/altium.md`, `docs/equivalence.md`), and
  `fenolite analyze` measures current capacity, clearance and creepage on a board
  (`docs/analyses.md`). What is proved of this, and one known defect, are in the release record.
- **Altium files are written.** `fenolite build --target altium` writes the PCB document (stacks of up to
  16 signal layers, blind and buried vias, texts, keep-outs, holes, polygons and the script's rules), the
  schematic documents per module, both libraries, the project file, an output job and the drawing sheet;
  `fenolite check` judges copper and parity on Altium input, `equivalent --level 5` compares routing, and
  `fenolite kit` builds the Altium verification kit (`docs/altium.md`, `docs/altium-kit.md`). All of it is
  experimental: the release record says per file kind what is proved and what is missing.

## Evidence labels

| Label | Meaning |
|---|---|
| `KICAD-VERIFIED` | accepted by `kicad-cli` of the stated version, and the claim confirmed by its output |
| `ORACLE-VERIFIED(<tool>)` | an independent parser or tool agreed |
| `CORPUS-VERIFIED` | round-trip holds on public files listed in the corpus manifest |
| `ALTIUM-VERIFIED(kit)` | confirmed by a native-tool acceptance run with archived results: a run of the verification kit that `fenolite kit` builds, checks and records ([docs/altium-kit.md](docs/altium-kit.md)) |
| `ALTIUM-VERIFIED(author-report)` | reported by the author from ordinary use; never enough for a release claim |
| `INFERRED` | deduced from public documentation; a hypothesis in `docs/hypotheses.md` tracks it |
| `UNKNOWN` | bytes or fields preserved without interpretation |
| `UNVERIFIED` | default for anything new |

A command's overall label is the lowest label of the steps it ran.

## Install

```bash
pip install fenolite
```

It installs no other package. `fenolite capabilities --json` then says which external tools it found:
`kicad-cli` (KiCad 9.0 or 10.0) for the checks, the fills and the exports, and a router. It runs on Linux, macOS
and Windows.

## The loop

The ten commands an agent runs, from a design script to fabrication files (`agent/SKILL.md` explains
each one and what to do when one fails):

```fenolite-loop
fenolite capabilities --json
fenolite build examples/blink_2layer/design.py --out build/blink --dry-run --json
fenolite build examples/blink_2layer/design.py --out build/blink --confirm --json
fenolite place build/blink --strategy grid --confirm --json
fenolite route build/blink --router freerouting --confirm --json
fenolite fill build/blink --confirm --json
fenolite check build/blink --json
fenolite export build/blink -o build/blink/fab --all --manifest --confirm --json
fenolite render build/blink -o build/blink/views --svg --png --confirm --json
fenolite inspect build/blink/blink.kicad_pcb --json
```

## Install for development

```bash
git clone <this repository>
cd fenolite
uv sync --extra dev
uv run fenolite --version
make check-fast   # lint, format, types, residue scan and the tests that need no external tool
make check        # everything, on parallel workers: the gate before a merge
```

Talk to it like an agent does:

```bash
uv run fenolite capabilities --json --fields tools          # what is installed here
uv run fenolite capabilities --text                         # the same, for humans
echo $?                                                     # 0 ok, 2 usage, 4 confirm, 5 findings …
```

Optional extras: `geo` (polygon booleans), `kicad-ipc` (live KiCad session), `mcp` (MCP server),
`oracles` (Gerber re-parsers used in tests), `dev`. Routers need no extra: they run as separate programs.

## Licence and provenance

Apache-2.0 (`LICENSE`, `NOTICE`). Format knowledge comes only from public sources; see `LEGAL.md`
for the clean-room rules and `CONTRIBUTING.md` for how to contribute. Every CI run and every commit
(after `make hooks`) passes a residue scan (`tools/residue/`) that blocks absolute paths, internal
identifier shapes and known non-public files; see `docs/provenance.md` for the provenance rules. AI agents working in this
repository: read `AGENTS.md` first.
