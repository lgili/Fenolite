# The `fenolite` CLI contract (v0)

Normative text: `openspec/specs/cli-contract/spec.md` and `openspec/specs/package-layering/spec.md`.
This page is the short human version. The contract is frozen at 1.0; before that, a breaking change
bumps the schema id.

## Output

- **JSON when stdout is not a terminal**, text when it is. `--json` / `--text` override.
- One JSON document per invocation on stdout, followed by a newline.
- `--fields a,b.c` keeps only those dotted paths of `result` (the rest of the envelope stays); the `plan` of a mutating command is part of `result`, so `--fields` keeps it only when listed.

## Envelope — `schemas/fenolite.envelope.v0.json`

```json
{
  "ok": true,
  "command": "capabilities",
  "schema": "fenolite.capabilities.v0",
  "input": null,
  "result": {"...": "..."},
  "issues": [{"code": "kicad.drc.clearance", "severity": "error", "message": "...",
              "where": "...", "hint": "...", "retryable": false}],
  "evidence": {"level": "UNVERIFIED", "oracle": null, "hypotheses": []},
  "receipt": null,
  "elapsed_ms": 12
}
```

`input` is `{path, sha256, kind, format_version}` when the command read a design file.
`receipt` is `{written: [{path, sha256}], backup: [path]}` when the command wrote files.

## Errors — `schemas/fenolite.error.v0.json`

Whenever the exit code is not 0, stderr carries exactly one error object
`{code, message, hint, retryable, where}` (JSON mode) or one line `error FEN-NNNN: message (hint)`
(text mode). The first digit of the code equals the exit code.

## Exit codes

| Code | Meaning | Error family |
|---|---|---|
| 0 | success | — |
| 1 | internal failure (a bug) | `FEN-1xxx` |
| 2 | usage error | `FEN-2xxx` |
| 3 | input unreadable or from a future format version | `FEN-3xxx` |
| 4 | confirmation required (nothing was written) | `FEN-4xxx` |
| 5 | verification produced findings of severity `error` (same code as `kicad-cli`) | `FEN-5xxx` |
| 6 | external tool missing or incompatible | `FEN-6xxx` |
| 7 | operation not representable without loss | `FEN-7xxx` |

Errors raised by the library inside a command keep a registered code: a Fenolite exception whose class
has a `cli_code` becomes that code, a plain `FormatError` becomes `FEN-3004`, and any other exception is
`FEN-1001`. For a `FormatError` the message is the bare message and `where` is `file:locator:@offset`;
an exception's own `hint` replaces the registry hint. When such an exception carries `issues` (a
non-empty sequence of issues, as `LossyWriteError`, `UnresolvedLibrariesError` and `LayoutExistsError`
do), they are put in the envelope's `issues`, so a refusal says which lib ids, nets or files it refused.

| Code | Meaning | Raised by |
|---|---|---|
| `FEN-3002` | input uses a newer format version than supported | `FutureFormatError` (editing a future file) |
| `FEN-3003` | input format version older than the oldest supported | `UnsupportedFormatError` (hint names the `kicad-cli … upgrade` command) |
| `FEN-3004` | malformed input file | any other `FormatError` (syntax, missing version, …), and `DesignScriptError` (a design script that raised, or that binds no `design`) |
| `FEN-3005` | geometry in the input cannot be represented | `GeometryError` (the message names the geometry code and the points) |
| `FEN-7001` | operation would lose information | `LossyWriteError` (a KiCad write meets content the target cannot hold; the hint names `--allow-lossy` only when every loss is droppable) |
| `FEN-7002` | target format version older than the input; downgrade is not supported | `DowngradeRefusedError` |
| `FEN-7003` | input from KiCad 8.0 is read-only; writing needs a KiCad 9.0 or newer source | `LegacyEditRefusedError` (hint names `kicad-cli pcb upgrade`) |

## Writing files

Commands that write are **mutating**. They never write unless asked:

| Invocation | Effect | Exit |
|---|---|---|
| `fenolite <cmd> … --dry-run` | `result.plan` lists every file that would be written; nothing is written | 0 |
| `fenolite <cmd> …` | same plan, error `FEN-4001`, nothing is written | 4 |
| `fenolite <cmd> … --confirm` | atomic writes (temporary file + rename), `.bak` of overwritten files unless `--no-backup`, `receipt` with SHA-256 | 0 |

## Determinism

`--seed INT` and `--timestamp ISO8601` fix every generated id and date: the same inputs and flags
produce byte-identical outputs. Keyed ids (placed copies, objects of design scripts) are not generated
and do not depend on `--seed`, and a command that writes no date ignores `--timestamp`; `build` is
such a command, so its outputs are byte-identical whatever both flags say.

## KiCad output

Every command accepts `--kicad-version {9,10}` (default 10) and `--allow-lossy`, before or after the
command name, like `--seed`. A command that writes KiCad files uses `--kicad-version` as the KiCad
major of what it writes, and `--allow-lossy` as permission to drop content that major cannot read:
each dropped part is reported as a warning, and without the flag the command fails with `FEN-7001`
(exit 7). Content the model holds is never dropped, with or without the flag. Any other
`--kicad-version` value is a usage error (`FEN-2001`, exit 2).

## Build target

`fenolite build DESIGN.py --out DIR` takes `--target {kicad,altium}`, default `kicad`. With
`--target kicad`, or without the option, it builds the KiCad project of `docs/dsl.md`. With
`--target altium` it builds an experimental Altium project instead: a project file, a schematic, its
libraries and, for KiCad footprints, a PCB library and an experimental PCB document (`docs/altium.md`).
It reads only the KiCad libraries that KiCad lib ids and footprint links name, `result.target` is the
string `altium`, `result.footprints` and `result.pcb_document` describe the PCB files,
`result.no_connects` counts the No ERC directives written for the pins marked with `no_connect`,
`result.experimental` is `true`, and `--kicad-version` and `--allow-lossy` change none of its bytes.
Any other `--target` value is a usage error (`FEN-2001`, exit 2).

`--altium-format {binary,ascii}` picks the form of the Altium schematic: `binary` (the default, a
compound file, write kind `altium_schdoc_binary`) or `ascii` (c0032's text form, write kind
`altium_schdoc_ascii`). `result.schematic_format` names the form written. Any other value, or the
option with `--target kicad` (given or by default), is a usage error (`FEN-2001`, exit 2), and nothing
is written. A binary schematic too large for the writer gives the error `altium.schematic-too-large`
(exit 5).

## `build`

`fenolite build DESIGN.py --out DIR [--discard-layout] [--vendor all|project] [--target kicad|altium]
[--altium-format binary|ascii]` runs the design script
(your own code: never run it on an untrusted script) and plans the files of a KiCad project under `DIR`
(`docs/dsl.md`). It is mutating. `--discard-layout` replaces outputs edited since the last build.
`--vendor all` (the default) copies the placed footprints of every library into `DIR/lib/`; the copies
keep their library's licence. `--vendor project` copies only those of project tables, and each other
footprint gives the info `build.global-library`. `result.vendored` lists the copied files and
`result.libraries` the row origin of each lib id.

A pin marked with `no_connect` that a net also lists, once designators are resolved to pin numbers, is
refused: `build.no-connect-on-net` (error) with `--target kicad`, `model.no-connect-on-net` (error) with
`--target altium`; the exit code is 5 and nothing is written. The marks are kept in
`.fenolite/circuit.json`, and no written KiCad file depends on them (`docs/dsl.md`, "No-connect marks").

Over an existing project, `build` preserves the layout (`docs/lens.md`): the board, project and rules
files are merged, and `build.layout-exists` (`FEN-7001`) now guards only `fp-lib-table` and the
vendored footprints under `lib/`. `--discard-layout` reads no existing file and builds from scratch.
`result.preserved` reports `board` (whether an existing board was read), `kept`, `replaced` and `added`
(component paths), `orphans` and `board_only` (references), `dropped` (counts of tracks, arcs, vias and
zones), `fills` (zones whose fills were kept and dropped), `aliases` (new path → old path) and
`reader_infos` (a count of the board reader's infos).

## Discovery

`fenolite capabilities` lists commands (`name`, `mutates`, `schema`, `hidden`), backends,
experimental features, installed extras, detected external tools (`kicad-cli`, `java`, `docker`) with
versions, and whether any enabled feature sends data off the machine. Agents should call it first.

`result.experimental` lists, sorted by `name`, the features that may change their output, options or
issue codes in any release. Each entry has exactly the keys `name`, `command`, `option`, `write_kinds`
and `evidence` (written as a backend's evidence), and its level is never one that counts as verified for
a release. Listing them runs no external tool, so the list is the same with `--no-tools`. An
experimental feature appears in `result.backends` only when it is a registered backend. Today the list
holds two entries, which share no write kind: the Altium PCB writer (`altium-pcb-writer`, write kinds
`altium_pcbdoc` and `altium_pcblib`, change c0035) and the Altium schematic writer:

```json
{"name": "altium-pcb-writer", "command": "build", "option": "--target altium",
 "write_kinds": ["altium_pcbdoc", "altium_pcblib"],
 "evidence": {"level": "INFERRED", "oracle": null, "hypotheses": ["H-A-PCB-DOC-BOTTOM", "…"]}}
{"name": "altium-schematic-writer", "command": "build", "option": "--target altium",
 "write_kinds": ["altium_prjpcb", "altium_schdoc_ascii", "altium_schdoc_binary", "altium_schlib"],
 "evidence": {"level": "INFERRED", "oracle": null, "hypotheses": ["H-A-PRJ-KEEP", "H-A-PRJ-OPEN", "…"]}}
```

Each entry of `result.backends` is one backend's capability report, sorted by name:

```json
{"name": "kicad", "read_kinds": ["kicad_pcb", "kicad_mod", "kicad_sym"],
 "write_kinds": ["kicad_pcb", "kicad_mod", "kicad_dru", "kicad_pro", "kicad_wks"],
 "targets": [9, 10], "default_target": 10, "downgrade": "unsupported",
 "operations": ["detect", "read", "write", "lower", "validate"],
 "evidence": {"level": "INFERRED", "oracle": null, "hypotheses": ["H-K-PCB-READ", "H-K-PCB-WRITE"]}}
```

`operations` lists only what the backend implements (`detect`, `read`, `write`, `lower`,
`validate`); an operation that is absent is not available yet. A backend that writes lists `write`,
the kinds it writes, its `targets` (oldest first), the `default_target` used when none is named, and
whether a file read at a newer version can be written for an older target (`downgrade`). Listing backends runs no external
tool, so the entry is the same with `--no-tools`. The `kicad-cli` entry of `result.tools` is found
by `fenolite.backends.kicad.cli.find_kicad_cli()`.

## check

`fenolite check PATH [--stages A,B] [--kicad-cli PATH] [--timeout SECONDS]` checks a KiCad project
read-only. `PATH` is a `.kicad_pcb`, a `.kicad_pro` (the board of its stem) or a folder holding one
`.kicad_pro` (else one `.kicad_pcb`). `kicad-cli` only ever sees a copy of the files a DRC run reads
(board, `<stem>.kicad_pro`, `<stem>.kicad_dru`, `fp-lib-table` and its `${KIPRJMOD}` libraries, the
drawing sheet): nothing under the project folder is created or changed. `--timeout` defaults to 300 s.
The input is *built* when `.fenolite/meta.json` or `.fenolite/build.json` exists next to the board.

The stages run in this order (`STAGE_ORDER`); `--stages` selects a subset, and unselected stages are left
out. Without `--stages`, every stage runs except `roundtrip.rt2` (`DEFAULT_STAGES`), which costs two
re-saves and three DRC runs and is selected by name. `drc.kicad`, `netlist.assignment_compare` and
`roundtrip.rt2` need `kicad-cli` (`ORACLE_STAGES`): selecting any of them runs the tool pre-flight.

| stage | runs on | evidence |
|---|---|---|
| `model.validate` | the board model (native) or the `.fenolite/` model (built) | the reader's level (native), `INFERRED` (built) |
| `erc.lite` | built input only; skipped with `native-input` otherwise | `INFERRED` (`H-K-CHECK-ERC`) |
| `drc.kicad` | `kicad-cli pcb drc` on the copy set, with the rules canary; every violation becomes a located issue | DRC report reader and oracle combined, `kicad-cli <version>`; `UNVERIFIED` without a report or with a rules issue |
| `netlist.assignment_compare` | the pad nets of the model (built input), of the re-read board and of `kicad-cli pcb export ipcd356`, compared as partitions | the lowest of the reader, the export and, on built input, `INFERRED`; `UNVERIFIED` without an export |
| `roundtrip` | RT1 of the board, native and built alike | the reader's level |
| `roundtrip.rt2` | opt-in: KiCad's DRC on the board and on Fenolite's re-dump of it gives the same violations | the DRC report reader, the oracle and the RT2 runs combined; `UNVERIFIED` when a report is missing |

Each `result.stages[]` entry is `{name, status, reason, evidence, summary}`. `status` is `ok` (ran, no
error issue), `errors` (ran, at least one) or `skipped`, with `reason` `native-input`, `read-refused`,
`cache-unreadable` or `unsupported-oracle` (the oracle lacks the stage's operation; never counted in the
envelope). A skipped stage carries `UNVERIFIED`. The envelope evidence is the lowest level of
the stages that ran and of those skipped for `read-refused` or `cache-unreadable`; `UNVERIFIED` when
none counts. `result.project` holds `board`, `built`, `files` and `skipped`, names relative to the
project folder. The `drc.kicad` summary holds `tool_version`, `canary`, `canary_reason`,
`canary_removed`, `violations`, `by_type`, `by_severity`, `unconnected`, `excluded`, `tool_writes`,
`violations_judged` and `types`. Whenever a report exists, each violation and unconnected item is one
issue and `violations_judged` is `true`; `types` maps each emitted `kicad.drc.<type>` code to KiCad's raw
type. An unrouted board therefore exits 5: its unconnected items are errors.

**Findings.** The code is `kicad.drc.` followed by KiCad's type in lower case with `_` as `-`
(`shorting_items` gives `kicad.drc.shorting-items`). The severity is the report's, which follows the
project's `rule_severities`; an excluded entry is `info`, and an unknown severity is `error`. `where`
lists the items in report order: `REF-PIN` for a numbered pad, `REF` for a footprint or an unnumbered
pad, the item's locator in the board file for a track, via or zone, and `@<x>,<y>` (the report position
in millimetres) when the item cannot be named. The message is `<type>: <description>` without temporary
or absolute paths.

**Assignment compare.** Elements are `REF-PIN`. Two sources agree when they put the same elements
together, whatever the nets are called; pads on no net form one class. The pairs are (`model`, `board`)
on built input and (`board`, `export`) always. A difference names the element that moved. Elements only
one side covers are `netlist.uncovered` infos, per reason: `not-exported`, `unmatched-record`,
`net-label-ambiguous` (two net names share their last 14 characters), `below-min-pins` or
`not-in-<source>`. The summary holds `pairs` (`a`, `b`, `common`, `only_a`, `only_b`, `differences`),
`min_pins` and `unnumbered`.

**RT2.** The summary holds `holds`, `judged`, `normalised` (both sides re-saved with `pcb upgrade` on
KiCad 10.0), `runs` (`original` and `redump` counts), `before` and `after` (violations and unconnected
items of the first original run and of the first re-dump run), `unstable` and `differences`. KiCad does
not repeat its own DRC report on boards with hundreds of violations, so violations that differ between
runs of one file are left out and counted (`check.rt2-unstable`). A difference between the board and the
re-dump is an error (`check.rt2-failed`) only when nothing is unstable; otherwise `judged` is `false`,
the stage is `ok` with level `UNVERIFIED`, and RT2 says nothing about that board.

**Rules canary.** KiCad drops a rules file with one error whole and still reports success, so
`drc.kicad` appends a clearance rule on a net of its own to a copy of `<stem>.kicad_dru` and inserts two
tracks of that net beyond the board in a copy of the board. Its state is `fired` (the rules were
loaded), `absent` (they were not), `inconclusive` (with `canary_reason`) or `not-applicable` (no rules
file, or no project file next to it). The canary tracks can change other violations of a large board,
so on KiCad 9.0 and 10.0 the canary run gives only the state and a second, plain run gives the counted
report; `kicad-cli` then runs twice.

| code | severity | when |
|---|---|---|
| `check.read-refused` | error | Fenolite cannot read the board; the message starts with the FEN code, `where` is `file:locator:@offset` |
| `check.cache-unreadable` | warning | `.fenolite/` cannot be loaded; both model stages are skipped |
| `check.footprint-unresolved` | error | a non-DNP component has no footprint reference or instance |
| `check.symbol-unresolved` | error | a built component that carries `fenolite.path` has no symbol reference; a board-only footprint added in KiCad, without that key, is not asked for one (`docs/lens.md`) |
| `check.rt1-failed` | error | RT1 failed; `where` is the first difference |
| `check.oracle-failed` | error | `kicad-cli` wrote no DRC report or netlist export, or timed out (`retryable: true`) |
| `check.copy-skipped` | info | a file or folder the project names was left out of the copy |
| `kicad.drc.rules-not-loaded` | error (built), info (native) | the canary is `absent`, or a rules file has no project file next to it |
| `kicad.drc.rules-unchecked` | warning | the canary is `inconclusive`; the message names the reason |
| `kicad.drc.<type>` | error, warning, info | one per DRC violation or unconnected item; `<type>` comes from KiCad's type |
| `netlist.assignment-differs` | error | an element whose net block differs between the two sources of a pair |
| `netlist.uncovered` | info | elements that one side of a pair does not cover, per reason |
| `check.rt2-failed` | error | a violation whose count differs between the original and the re-dump |
| `check.rt2-unstable` | info | violations that differ between DRC runs of one file; the message says when RT2 is therefore not judged |
| `erc.lite.output-conflict` | warning | two or more driving outputs on one net |
| `erc.lite.power-undriven` | warning | a power input without a power output or a power interface |
| `erc.lite.floating-pin` | warning | a pin on no net that `no_connect` does not mark |

`model.*` findings and reader codes pass through unchanged; among them `model.no-connect-on-net`
(error) names a pin that is marked as not connected and that a net lists (`docs/design-model.md`). Exit codes: 0 without an error issue, 5
with one, 2 for a usage error (ambiguous folder, unknown stage), 3 for a missing path or a board that
neither Fenolite nor KiCad reads (the envelope still holds the issues), and 6 when a stage that needs
`kicad-cli` is selected and it is missing (`FEN-6001`; the hint names `--stages model.validate,erc.lite,roundtrip`),
of an unsupported major, or older than the board's format (`FEN-6002`). Two runs on the same project
give the same stdout apart from `elapsed_ms`.

## inspect

`fenolite inspect FILE [--summary]` summarises one KiCad file and runs no tool. Boards, footprint
files and symbol libraries (file or `.kicad_symdir`) are read by their reader; `.kicad_sch` and
`.kicad_wks` are read header-only, with counts of the root children by head. `result` holds `kind`,
`format_version`, `major`, `status`, `generator`, `generator_version`, `counts`, `opaque_count` (boards
only) and `model_findings` (the `model.*` findings counted by severity, not reported as issues).
`input.path` is the file name. `.kicad_pro`, `.kicad_dru` and other files exit 2 (`FEN-2001`); a read
error exits 3 with its code.

## doctor

`fenolite doctor [--kicad-cli PATH]... [--no-run]` reports the external tools. `result.kicad_cli` holds
one entry per `kicad-cli` candidate (each `--kicad-cli`, `FENOLITE_KICAD_CLI`, `kicad-cli` on `PATH`,
the macOS application bundle; one entry per binary) with `path`, `source`, `version`, `major`,
`supported`, `selected`, `matrix` (each command and option of the matrix `true`, `false` or `"unknown"`,
read from the help pages through the package runner) and `evidence`. `result.by_major` maps each major
to its candidates' paths; `result.java` (`path`, `version`, `major`) and `result.docker` (`path`,
`version`, `daemon`) are `null` when missing. `--no-run` lists the candidates and runs no tool.

| code | severity | when |
|---|---|---|
| `doctor.tool-missing` | warning | a tool is absent, or `--kicad-cli` or `FENOLITE_KICAD_CLI` names a missing file |
| `doctor.tool-unsupported` | warning | a candidate's major is not 9 or 10, or it reports no version |
| `doctor.help-unparsed` | warning | a help page did not parse |

`doctor` exits 0. Its evidence is the help-matrix evidence with the oracle of the selected candidate
when every help page parsed, `UNVERIFIED` otherwise and with `--no-run`.
