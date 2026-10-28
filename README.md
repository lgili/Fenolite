# Fenolite

**Headless, agent-first PCB design automation in Python.** Fenolite lets an engineer — or an AI
coding agent — generate, open, verify, compare, convert and export printed-circuit-board projects
from Python code or a JSON-speaking command line, without a GUI. KiCad is the first backend (its
files, with `kicad-cli` as the verification oracle); a second backend for another major commercial
format family follows.

> **Status: version 0.5.** A design script becomes a KiCad project with a board and a schematic, for
> KiCad 9.0 and 10.0. The loop of the agent guide works on two-layer boards: the board is placed, routed
> by an external router, filled, checked by KiCad's own design-rule check and exported to fabrication
> files. The schematic is judged by KiCad's own electrical rules check, by its netlist and by its
> schematic parity test. Version 0.5 adds `fenolite convert`: a project is converted between KiCad and
> Altium, or written for the older KiCad major, with a report of what is kept, changed or lost, and every
> conversion is read back and compared with its source through the public `equivalent`. It also adds
> board slots and the copper-to-edge check. What was proved for this version, what waits for the next one,
> and the limits are in `docs/release/v0.5.md` (`docs/release/v0.4.md`, `docs/release/v0.3.md`,
> `docs/release/v0.2.md` and `docs/release/v0.1.md` for the versions before). Every Altium write and every
> conversion to or from Altium is experimental: no write kind has the evidence to leave that state yet, and
> most Altium evidence is `INFERRED` or an author report.

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

## What version 0.5 does

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
  experimental: `capabilities` lists missing proofs per kind. The AD 26.5 kit has
  32 passed steps and a published supplemental archive; the acceptance project
  passed on KiCad 10.0.6 within its comparison profile. See
  [measured acceptance](docs/evidence/altium-acceptance.md); no write kind graduates yet.

- **The agent guide.** `fenolite guide` prints the guide that ships in the package, `fenolite skill
  install` puts it where an agent finds it, `fenolite init` writes a starter project, and
  `fenolite fetch freerouting` installs the pinned router (`docs/cli-contract.md`).
- **Larger boards.** 6 and 8 copper layers, stack-ups, outlines with arcs and cut-outs, holes, rule areas,
  board texts and dimensions, differential pairs, impedance targets, net lengths and meanders, via
  protection, net ties and waivers, placement rules and part heights (`docs/dsl.md`); `route` keeps plane
  nets to their planes and is bounded by `--timeout`, and `fenolite ready` says whether a project is
  electrically ready. What each change ships, and what waits for the next release, is in
  `docs/release/v0.4.md`.
- **Fabrication documents.** `fenolite export` writes IPC-2581, ODB++, STEP, PDF and DXF, and fabrication
  and assembly drawings (`docs/exports.md`, `docs/drawings.md`); `fenolite testpoints` reports fiducials and
  test points.
- **Conversion.** `fenolite convert SRC --to {kicad,altium} --out DIR` converts a project from KiCad to
  Altium, from Altium to KiCad, or between KiCad majors, with a report of what is kept, changed or lost per
  kind and reason; a lossy conversion stops unless `--allow-lossy` is given, and every conversion is read
  back and compared with its source (`docs/conversion.md`). Both Altium directions are experimental.
- **The KiCad downgrade.** `fenolite --kicad-version 9 convert <project> --to kicad --out <dir>` writes a
  project saved by KiCad 10 for KiCad 9, each newer construct resolved by a capability table proved on
  9.0.9 (`docs/conversion.md`).
- **`equivalent` in the library.** `fenolite.api.equivalent` compares two designs from Python, with the
  result schema `fenolite.equivalent.v0`, and a KiCad schematic is a side of the comparison
  (`docs/equivalence.md`).
- **Slots and the board edge.** `design.slot()` adds a milled slot, overlapping cut-outs and slots are
  merged (the `geo` extra), and `fenolite check` reports copper too close to the board edge, a cut-out or a
  slot, and drilled holes that break into them (`docs/dsl.md`, `docs/cli-contract.md`). What each change of
  0.5 ships, and what waits for the next release, is in `docs/release/v0.5.md`.

After 0.5, on the branch of change c0176:

- **A board viewer.** `fenolite view PATH` shows the boards of an Altium or KiCad project in a browser,
  without either tool: the project's documents in a side panel, the layers as tabs along the bottom, Top and
  Bottom views, net highlight, measurement, a 3D view with part bodies, and the paths of an `analyze` reply
  on top. `--serve` serves it live on `127.0.0.1`; `--export` writes one standalone page (`docs/viewer.md`).

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

The ten commands an agent runs, from an empty folder to fabrication files. They start from a starter
project made of built-in parts and use the built-in router, so `kicad-cli` is the only tool they need; a
real board is routed by an external router or by copper written in the script.
`fenolite guide start --text` prints the agent guide, which explains each command and what to do when one
fails (in this repository: `src/fenolite/agent/skill/SKILL.md`), and `fenolite skill install` copies it
to where an agent reads skills:

```fenolite-loop
fenolite capabilities --brief --json
fenolite init blink --confirm --json
fenolite build blink/design.py --out blink/build --dry-run --json
fenolite build blink/design.py --out blink/build --confirm --json
fenolite place blink/build --strategy grid --confirm --json
fenolite route blink/build --router direct --confirm --json
fenolite fill blink/build --confirm --json
fenolite check blink/build --json
fenolite export blink/build -o blink/fab --all --manifest --confirm --json
fenolite render blink/build -o blink/views --svg --png --confirm --json
```

A board that passes `fenolite check` is not therefore a good board. The guide also holds eleven practice
pages, which start at `fenolite guide board-practice --text`. They cover the schematic and part ratings,
the floorplan, power paths, grounds and current sensing, high-voltage spacing, EMC and protection,
routing, assembly and test access, the review before handing a board over, and working on files that a
person also edits. They give rules, the failures the
rules prevent, and how to check each one. They give no limit values: those come from your standard,
your fabricator and your datasheets.

An agent without a shell reaches the same commands through `fenolite mcp`, a server of the Model Context
Protocol on standard input and output that needs no other package: every command is a tool whose reply is
its envelope, a writing tool is a dry run until it confirms the plan it returned, and the guide's pages are
its resources (`docs/mcp.md`). With `--allow-edit` it also writes the design script through a plan, and a
render's views come back as images that an agent can look at.

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

Optional extras: `geo` (polygon booleans), `kicad-ipc` (live KiCad session), `oracles` (Gerber re-parsers
and the MCP client used in tests), `dev`. Routers need no extra: they run as separate programs, and the MCP
server `fenolite mcp` needs none either (`docs/mcp.md`).

## Licence and provenance

Apache-2.0 (`LICENSE`, `NOTICE`). Format knowledge comes only from public sources; see `LEGAL.md`
for the clean-room rules and `CONTRIBUTING.md` for how to contribute. Every CI run and every commit
(after `make hooks`) passes a residue scan (`tools/residue/`) that blocks absolute paths, internal
identifier shapes and known non-public files; see `docs/provenance.md` for the provenance rules. AI agents working in this
repository: read `AGENTS.md` first.
