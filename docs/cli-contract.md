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

## `catalog`

`fenolite catalog list [--kind symbol|footprint] [--query TEXT]` returns stable, offline catalog
entries with `lib_id`, kind, category, summary, evidence level and registered source ids.
`fenolite catalog show LIB_ID` returns the same metadata and a compact definition summary. Neither
command reads library tables or runs external tools. The initial generic catalog is documented in
`docs/catalog/README.md`; every non-`KICAD-VERIFIED` land dimension remains explicitly marked.

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

`--altium-sheets {flat,modules}` picks the sheets of the Altium schematic (change c0037): `flat` (the
default, one sheet, the bytes of earlier releases) or `modules` (a top sheet with one sheet symbol per
top-level module, one `<name>_<module>.SchDoc` per module, ports and sheet entries, and signal harnesses
with their `<sheet stem>.Harness` definition files, write kind `altium_harness`). Any other value, or the
option with `--target kicad` (given or by default), is a usage error (`FEN-2001`, exit 2), and nothing is
written. `result` holds five more keys in both modes: `sheet_mode` (`flat` or `modules`), `sheets` (the
schematic file names, the top sheet first), `ports`, `sheet_entries` and `harnesses` (the number of
harness types drawn). The hierarchy has five issue codes of its own: the errors
`altium.sheet-name-collision`, `altium.harness-name`, `altium.harness-net-shared` and
`altium.harness-power-net` (exit 5, in both modes), and the info `altium.sheets-not-in-project` (a kept
project file does not list the module sheets and harness files).

`--copper-from BOARD.kicad_pcb` (with `--target altium` only; a usage error `FEN-2001` otherwise, and for
a path that is not a file) copies the tracks, arcs, vias and zones of a routed KiCad board of the same
design into `<name>.PcbDoc`, after checking that the board matches the design; the board's placements
win (`docs/altium.md`, "Copper"). The board is read in-process: a board the reader refuses exits 3
with its `FEN-3xxx` code, and the reader's issues and evidence join the build's.

`result.copper` is present whenever the PCB document is planned (`null` otherwise): `source` (`none`,
`model`, `script` or `board`), `from` (the path given to `--copper-from`, else `null`), `layers`,
`planes` (layer name to net name), `tracks`, `arcs`, `vias`, `zones`, `net_classes` (counts of what
is written) and `placements_from_board`. With `--copper-from`, `result.copper_input` holds the board's
`path`, `sha256`, `kind` (`kicad-board`) and `format_version`; the envelope's `input` stays the script.

`source` is `script` when the script declares copper intents (`Design.track`, `Design.via`,
`Design.stitch`) and `--copper-from` is absent: the intents are resolved by the KiCad build of the
script, run in memory (no KiCad file is planned), and the script's zones travel with them. An error of
that build (`kicad.copper.*`, `kicad.frame.*`, `build.*`) exits 5 with no planned file and
`result.copper` `null`; its `kicad.copper.*` and `kicad.frame.*` warnings and infos and its
`layout.unplaced` warnings join `issues`. With `--copper-from` the board wins: the intents are not
resolved, and one `altium.not-lowered` info names them.

The copper codes of the Altium build:

| code | severity | when |
|---|---|---|
| `altium.copper-stack` | error | the board's copper layers are not `F.Cu`, `B.Cu` or `F.Cu`, `In1.Cu`, `In2.Cu`, `B.Cu`, their count differs from `copper`, or a plane names a layer that is not an inner layer or a net the design does not hold |
| `altium.copper-layer` | error | a track, arc, via or zone names a layer outside the board's copper layers |
| `altium.via-unsupported` | error | a via is blind, buried or micro, or does not span the top and the bottom layer |
| `altium.zone-unsupported` | error | a zone has fewer than three outline points, or names no layer |
| `altium.copper-invalid` | error | a track of zero length, a width of 0 or less, a drill not below its diameter, or a net id that names no net |
| `altium.plane-copper` | error | a track or arc lies on a plane layer, or a zone on a plane layer has another net than the plane |
| `altium.copper-board-mismatch` | error | a copper source does not match the design: a component, a footprint, a pad net or the outline |
| `altium.copper-net-missing` | error | copper of a source is on a net whose name the design does not hold |
| `altium.copper-no-document` | error | a copper source is given and the PCB document is not planned |
| `altium.zones-unpoured` | info | polygons are written without poured copper |
| `altium.plane-zone-merged` | info | a zone on a plane layer with the plane's net is left to the plane |
| `altium.placement-from-board` | info | components are placed as the board of `--copper-from` places them, not as the script requests |

A script with `planes` built for the KiCad target gives one `build.plane-not-lowered` info per plane.

## `build`

`fenolite build DESIGN.py --out DIR [--discard-layout] [--vendor all|project] [--target kicad|altium]
[--altium-format binary|ascii] [--altium-sheets flat|modules] [--copper-check refuse|warn]` runs the design script
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
zones), `fills` (zones whose fills were kept and dropped), `aliases` (new path → old path),
`reader_infos` (a count of the board reader's infos) and `fields`: three sorted lists of
`"<component path>:<field name>"`, `kept` (an unlocked `Part.field()` request differs from the board's
field, which wins), `forced` (a locked request changed a board field) and `carried` (a field of a
re-placed footprint took the board's values); all three are empty without an existing board
(`docs/lens.md`, "Footprint fields").

A script may declare copper (`docs/dsl.md`, "Copper"; `docs/copper.md`). The build resolves it after
placement, and the KiCad `result.copper` reports `intents`, `tracks` and `vias` (created), and
`regenerated`, `stale` and `duplicates` (from the merge with an existing board; 0 without one). A
copper error (a `kicad.copper.*` issue of severity error) exits 5 and writes nothing; the
`kicad.copper.*` and `kicad.frame.*` codes are listed in `docs/copper.md`. With intents, the envelope
evidence also combines the copper and board-frame evidence, which are `INFERRED`. `--seed`,
`--timestamp` and `PYTHONHASHSEED` change no byte of a build with intents.

**Copper guard.** Before a KiCad build plans its writes, it judges the copper of the triad it is about
to write with the copper check of `check` (`copper.clearance`, below): the planned board is read back,
the planned project and rules files give the clearance in force, and copper kept from an existing board
is judged with the rest. `--copper-check refuse` (the default) adds the `copper.*` issues as they are,
so a `copper.short` or a `copper.clearance` error exits 5 and writes nothing. `--copper-check warn`
reports those errors as warnings, with ` (copper guard in warn mode)` at the end of the message, and
writes. There is no way to switch the guard off. `result.copper_check` holds `mode`, `ran` (false when
the build was already refused), `shorts`, `clearance`, `rules` (`min_clearance`,
`opaque_clearance_rules`, `unread`) and `evidence`. The guard runs on `--dry-run` too, reads and writes
no file, and runs no tool. `--copper-check` with `--target altium` is a usage error. A Python caller of
`build_design` is not guarded (`docs/dsl.md`, "Copper guard").

**Placement guard.** The same planned board is then judged by the placement legality check
(`docs/placement.md`): the courtyards of the placed parts against each other and against the outline.
Parts that the build staged (`result.staged`) are not judged. Every `place.*` issue is reported at most
as a warning, so a build never exits 5 for placement; the codes are those of the table under "place".
`result.placement` holds `ran` (false when the build was refused) and `counts`, the number of issues by
code. The guard runs on `--dry-run` too, reads and writes no file, and runs no tool. With
`--target altium` there is no `result.placement`. A Python caller of `build_design` is not guarded; it
calls `placement.check` itself (`docs/placement.md`).

## Discovery

`fenolite capabilities` lists commands (`name`, `mutates`, `schema`, `hidden`), backends,
experimental features, installed extras, detected external tools (`kicad-cli`, `java`, `docker`) with
versions, and whether any enabled feature sends data off the machine. Agents should call it first.
A command whose examples need an external tool also lists `example_tools` (`export` and `render`:
`kicad-cli`); the test suites run such examples against a fake of the tool, and every other command's
examples run with no subprocess.

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
 "write_kinds": ["altium_harness", "altium_prjpcb", "altium_schdoc_ascii", "altium_schdoc_binary",
                 "altium_schlib"],
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

The backend's `evidence` is the lowest of what its `read` and `write` return for an arbitrary board, so
it is `INFERRED` although the two rows it names are stronger in `docs/hypotheses.md`
(`H-K-PCB-READ` is `CORPUS-VERIFIED`, `H-K-PCB-WRITE` is `KICAD-VERIFIED`). A row states what its test
covered: the corpus boards round-trip, and the test boards load in KiCad. The report states what holds
for any file. The level is never stronger than a row it names
(`tests/unit/test_capability_evidence.py`); a command that runs `kicad-cli` on your board reports the
stronger level in its own envelope.

`operations` lists only what the backend implements (`detect`, `read`, `write`, `lower`,
`validate`); an operation that is absent is not available yet. A backend that writes lists `write`,
the kinds it writes, its `targets` (oldest first), the `default_target` used when none is named, and
whether a file read at a newer version can be written for an older target (`downgrade`). Listing backends runs no external
tool, so the entry is the same with `--no-tools`. The `kicad-cli` entry of `result.tools` is found
by `fenolite.backends.kicad.cli.find_kicad_cli()`.

## route

`fenolite route PATH --router NAME [--nets GLOB]... [--rip] [--include-zone-nets] [--router-path PATH] [--router-python PATH] [--router-option KEY=VALUE]... [--allow-offsite] [--timeout SECONDS] [-o FILE]` routes selected nets. `PATH` accepts a board, matching project or folder. External tools receive a temporary model-authored project copy; only routed tracks, arcs and vias are merged back. `--rip` removes unlocked copper on selected nets. `--out` is relative to the working directory. The normal dry-run/confirm receipt protocol applies.

`result` contains `board`, `router`, `tool_version`, `selected`, `routed`, `unrouted`, `tracks`, `vias`, `ripped`, `fills_stale` and up to 20 sanitised `log` lines. Evidence is `UNVERIFIED`; run `check` after routing and refill zones before checking.

| code | severity | when |
|---|---|---|
| `route.bad-item` | error | a router returned malformed copper |
| `route.copper-removed` | warning | the router dropped existing copper |
| `route.fill-stale` | info | changed copper invalidated filled zones |
| `route.option-ignored` | warning | a `--router-option` the router does not support was ignored |
| `route.project-unread` | warning | the project file beside the board could not be read, so every net takes the default class values |
| `route.tool-failed` | error | the external router failed |
| `route.tool-missing` | error | the configured router is unavailable |
| `route.tool-unpinned` | warning | external router checkout is not the supported pinned version |
| `route.unrouted` | warning | a selected net remains unrouted, or the router reports open connections: a net with copper is still listed under `unrouted` when the router says it left one of its connections open |
| `route.zone-net-skipped` | info | a zone net was omitted without the inclusion flag |

`fenolite route --router freerouting` runs Freerouting through a Specctra design file. `--router-path` names its jar (or `docker:<image>`), `--router-option max-passes=N` its passes; the board needs a closed outline. Its issues also carry the `specctra.*` codes: `specctra.unknown-padstack` and `specctra.session-moved` (error, no copper is taken), `specctra.pad-approximated` (warning), `specctra.rounded`, `specctra.renamed` and `specctra.unknown-list` (info). While the router is listed with `sends_data_offsite: true`, the command exits 2 without `--allow-offsite`. See `docs/routing.md`.

## fill

`fenolite fill PATH [--from REFILLED] [-o FILE] [--kicad-cli PATH] [--timeout SECONDS]` computes zone
copper on a copy using KiCad 10 and writes only the fills into the original board's KiCad major (9 or
10). `PATH` accepts a board, matching project file or project folder. `--from` reads a board already
refilled by KiCad and runs no external tool. `--out` chooses a file relative to the working directory;
otherwise the board is replaced. The command follows the usual `--dry-run` plan and `--confirm`
receipt and backup protocol. A board without a netted zone produces `zone.none` and no write.

`result` holds `board`, `target`, `changed`, `zones` (id, name, layers, fill and island counts, filled
flag), `tool_version` and `tool_writes`. A matching refill by zone UUID is required; a mismatch gives
`zone.fill-mismatch` (error) and no write. A refill whose polygons cannot be expressed in the target
major is refused. `--from` evidence stays `INFERRED`; a tool run uses the refill evidence and names
the tool version. An installed KiCad 9 alone cannot refill: use KiCad 10, `--from`, or
`--kicad-cli docker:<image>`.

| code | severity | when |
|---|---|---|
| `zone.fill-mismatch` | error | a zone UUID occurs in only one of the two boards |
| `zone.fill-unstable` | warning | a lifted fill is not reproduced by another refill |
| `zone.none` | info | the board has no netted zone to refill |

## check

`fenolite check PATH [--stages A,B] [--kicad-cli PATH] [--timeout SECONDS]` checks a KiCad project
read-only. `PATH` is a `.kicad_pcb`, a `.kicad_pro` (the board of its stem) or a folder holding one
`.kicad_pro` (else one `.kicad_pcb`). `kicad-cli` only ever sees a copy of the files a DRC run reads
(board, `<stem>.kicad_pro`, `<stem>.kicad_dru`, `fp-lib-table` and its `${KIPRJMOD}` libraries, the
drawing sheet): nothing under the project folder is created or changed. `--timeout` defaults to 300 s.
`--kicad-cli docker:<image>` runs the same copied project in a named local image; a missing image
returns `FEN-6001` with a `docker pull` hint.
The input is *built* when `.fenolite/meta.json` or `.fenolite/build.json` exists next to the board.

The stages run in this order (`STAGE_ORDER`); `--stages` selects a subset, and unselected stages are left
out. Without `--stages`, every stage runs except `roundtrip.rt2` (`DEFAULT_STAGES`), which costs two
re-saves and three DRC runs and is selected by name. `drc.kicad`, `netlist.assignment_compare` and
`roundtrip.rt2` and `zone.fill` need `kicad-cli` (`ORACLE_STAGES`): selecting any of them runs the tool pre-flight.
`copper.clearance` needs no tool: `--stages copper.clearance` runs on a machine without KiCad.

| stage | runs on | evidence |
|---|---|---|
| `model.validate` | the board model (native) or the `.fenolite/` model (built) | the reader's level (native), `INFERRED` (built) |
| `erc.lite` | built input only; skipped with `native-input` otherwise | `INFERRED` (`H-K-CHECK-ERC`) |
| `copper.clearance` | Fenolite's own exact check of shorts and clearance on the board model, native and built alike, with the rules of `<stem>.kicad_pro` and `<stem>.kicad_dru`; no tool runs | the lowest of the copper check (`INFERRED`), the board reader and the project and rules readers; `UNVERIFIED` when part of the copper or of the rules went unjudged |
| `zone.fill` | KiCad 10 refills a private copy of the project board; compares saved copper polygons per zone | refill evidence; `UNVERIFIED` when any zone is unfilled or stale |
| `drc.kicad` | `kicad-cli pcb drc` on the copy set, with the rules canary; every violation becomes a located issue | DRC report reader and oracle combined, `kicad-cli <version>`; `UNVERIFIED` without a report or with a rules issue |
| `netlist.assignment_compare` | the pad nets of the model (built input), of the re-read board and of `kicad-cli pcb export ipcd356`, compared as partitions | the lowest of the reader, the export and, on built input, `INFERRED`; `UNVERIFIED` without an export |
| `roundtrip` | RT1 of the board, native and built alike | the reader's level |
| `roundtrip.rt2` | opt-in: KiCad's DRC on the board and on Fenolite's re-dump of it gives the same violations | the DRC report reader, the oracle and the RT2 runs combined; `UNVERIFIED` when a report is missing |
| `render` | opt-in: runs only when `--stages` names it; plots the four views of `fenolite render` on the copy set and writes nothing | the plot evidence, `kicad-cli <version>`; `UNVERIFIED` when no view was produced |

Each `result.stages[]` entry is `{name, status, reason, evidence, summary}`. `status` is `ok` (ran, no
error issue), `errors` (ran, at least one) or `skipped`, with `reason` `native-input`, `read-refused`,
`cache-unreadable`, `unsupported-oracle`, `oracle-unsupported` or `oracle-unstable` (two refill runs differ; never counted in the
envelope). A skipped stage carries `UNVERIFIED`. The envelope evidence is the lowest level of
the stages that ran and of those skipped for `read-refused` or `cache-unreadable`; `UNVERIFIED` when
none counts. `result.project` holds `board`, `built`, `files` and `skipped`, names relative to the
project folder. The `drc.kicad` summary holds `tool_version`, `canary`, `canary_reason`,
`canary_removed`, `violations`, `by_type`, `by_severity`, `unconnected`, `excluded`, `tool_writes`,
`violations_judged` and `types`. Whenever a report exists, each violation and unconnected item is one
issue and `violations_judged` is `true`; `types` maps each emitted `kicad.drc.<type>` code to KiCad's raw
type. The `zone.fill` summary holds `tool_version`, `zones`, `current`, `unfilled` and `stale`. An unrouted board therefore exits 5: its unconnected items are errors. The `render` summary holds
`tool_version` and `views` (`name`, `bytes`, `sha256`; sorted by name); the hash of an SVG leaves out its
`<title>` line, where `kicad-cli` 9.0 writes the date, so two checks give the same output.

**Copper check.** `copper.clearance` judges tracks, arcs, vias, pads and zone fills as exact shapes
(`docs/geometry.md`, "Thick shapes"). Two items of different nets that share a copper layer are judged:
copper that touches is `copper.short`, always an error, and copper closer than the clearance in force
is `copper.clearance`. The clearance in force comes from the project's own files: the last matching
`clearance` rule of the rules file, else the larger clearance of the two nets' classes, raised to the
board minimum; a rule of severity `ignore` silences its pairs for clearance, never for shorts. The
comparison is strict, so a gap equal to the clearance is clean. Each item pair gives at most one
finding, on the first layer where it applies. `where` names both items, sorted by kind: `REF-PIN` for
a pad and the item's locator in the board file otherwise (a fill is named by its zone). The message
gives both nets, the layer, a point in millimetres and, for a clearance finding, the gap, the clearance
and its source (`rule:<name>`, `class:<name>` or `floor`). The summary holds `layers`, `items` (counts
per kind), `pairs`, `judged`, `shorts`, `clearance`, `zone_overlaps`, `unset_pairs`, `unsupported`,
`approximated`, `arc_tol`, `max_clearance` and `rules` (`min_clearance`, `opaque_clearance_rules`,
`unread`). A project without net classes and without rules has no clearance in force: its copper is
judged for shorts only, and `copper.clearance-unset` says for how many pairs. The check does not replace
KiCad's DRC: `docs/formats/kicad/copper.md` lists what it supports and where it differs, and why it
exists (KiCad loads a via that touches a track of another net on that track's net and reports no
short).

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
report; `kicad-cli` then runs twice. KiCad stops reporting `clearance` violations near 499 per run, and
on a board with more it can leave the canary's own violation out. A canary run whose report holds 499
or more `clearance` violations and no canary violation is therefore `inconclusive` with the reason
`clearance-limit` (`kicad.drc.rules-unchecked`), never `absent`: on such a board `check` cannot tell
whether the rules were loaded.

**Repeatability.** Fenolite adds no difference of its own: two `check` runs on one project with one
`kicad-cli` give the same output apart from `elapsed_ms` whenever KiCad repeats its reports. KiCad
writes its DRC report in another order from run to run, which `check` sorts away. On boards with hundreds
of violations KiCad also does not repeat the report itself. Measured on the KiCad demo boards with
10.0.6 (`docs/evidence/kicad-check.md`), the difference stays within three types:

- the issues `kicad.drc.clearance`, `kicad.drc.hole-clearance` and `kicad.drc.unconnected-items` can
  name other items and positions, and their counts can change;
- so can the `drc.kicad` summary values counted from them (`violations`, `unconnected`, `by_type`,
  `by_severity`, `types`), and the stage status and the exit code when one of these issues decides them;
- on a board with 499 or more `clearance` violations, the canary state can be `fired` in one run and
  `inconclusive` (`clearance-limit`) in the next.

Every issue of another code, the other stages and `tool_writes` repeat. Compare two runs of a large
board by the codes outside those three, or run `roundtrip.rt2`, which leaves out what KiCad does not
repeat.

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
| `render.failed` | warning | the `render` stage could not produce a view; `where` is the view name. Never an error: a render is not a gate |
| `copper.short` | error | copper of two nets touches or overlaps on a shared copper layer; `where` names both items |
| `copper.clearance` | error, warning | a gap below the clearance in force; the governing rule sets the severity, and a class or board-minimum value gives an error |
| `copper.zone-overlap` | warning | zones of different nets and equal priority overlap on a shared layer |
| `copper.rules-incomplete` | warning | a clearance rule stayed opaque, a project file was not read, or no rules source was given |
| `copper.item-unsupported` | warning | copper items left out of the check, one issue per kind; `where` is the kind |
| `copper.clearance-unset` | info | item pairs judged for shorts only, because no clearance is in force for them |
| `zone.unfilled` | warning | KiCad's refill produces copper but the saved board has none for a zone |
| `zone.fill-stale` | warning | the saved fill polygons differ from a KiCad refill |
| `zone.fill-unchecked` | info | the selected tool cannot refill zones, or two refill runs differ; the stage is skipped |

`model.*` findings and reader codes pass through unchanged; among them `model.no-connect-on-net`
(error) names a pin that is marked as not connected and that a net lists (`docs/design-model.md`). Exit codes: 0 without an error issue, 5
with one, 2 for a usage error (ambiguous folder, unknown stage), 3 for a missing path or a board that
neither Fenolite nor KiCad reads (the envelope still holds the issues), and 6 when a stage that needs
`kicad-cli` is selected and it is missing (`FEN-6001`; the hint names `--stages model.validate,erc.lite,roundtrip`),
of an unsupported major, or older than the board's format (`FEN-6002`). Two runs on the same project
give the same stdout apart from `elapsed_ms`.

## export

`fenolite export PATH --out DIR [--gerbers] [--drill] [--pos] [--ipcd356] [--all] [--manifest]
[--kicad-cli PATH] [--timeout SECONDS]` writes the fabrication files that `kicad-cli` produces from a
copy of the board `PATH` names (resolved as for `check`). Fenolite writes no Gerber itself: the tool runs
once per kind on the copy set of `check`, so the project folder never changes, and every file it wrote
becomes a planned write under `DIR` (relative to the working directory). The mutation protocol applies:
`--dry-run` runs the tool and shows the plan, `--confirm` writes. `--all` selects the four kinds; a call
that selects none exits 2. `--timeout` defaults to 300 s and applies to each run.

| kind | `kicad-cli` call | files under `DIR` |
|---|---|---|
| `--gerbers` | `pcb export gerbers --no-protel-ext --layers <copper in stack order, masks, pastes, silkscreens, Edge.Cuts>` | `gerbers/<stem>-<layer>.gbr`, `gerbers/<stem>-job.gbrjob` |
| `--drill` | `pcb export drill --format excellon --excellon-units mm --excellon-separate-th --drill-origin absolute` | `drill/<stem>-PTH.drl`, `drill/<stem>-NPTH.drl` |
| `--pos` | `pcb export pos --format csv --units mm --side both` | `pos/<stem>-pos.csv` |
| `--ipcd356` | `pcb export ipcd356` | `netlist/<stem>.d356` |

`--check-zones` and `--board-plot-params` are never passed, so the files show the board as it is.
`--manifest` adds `DIR/fenolite-artifacts.json` (`schemas/fenolite.artifacts.v0.json`; `docs/exports.md`).
`result` holds `board`, `out`, `kinds`, `artifacts` (`path`, `kind`, `layer`, `bytes`, `sha256`,
`content_sha256`; sorted by path), `tool_version` and `tool_writes` (files the tool wrote outside its
output folders, such as `<stem>.kicad_prl`). When a kind fails, nothing is planned or written, so a
folder never holds a partial set.

| code | severity | when |
|---|---|---|
| `export.failed` | error | a kind's run exited non-zero, wrote no file or timed out (`retryable: true`); `where` is the kind |
| `export.kind-unavailable` | error | the running `kicad-cli` major cannot export the kind; no tool run |

Exit codes: 0 when the files are planned or written, 4 without `--dry-run` or `--confirm`, 5 with an
issue above, 2 for a usage error, 3 for a missing path or a board Fenolite cannot read, 6 when
`kicad-cli` is missing (`FEN-6001`), of an unsupported major or older than the board's format
(`FEN-6002`). The evidence is `exports.EVIDENCE` with the oracle `kicad-cli <version>`: Fenolite claims
the file set and the hashes, and the content of each file is KiCad's.

## render

`fenolite render PATH --out DIR [--svg] [--png] [--width PX] [--height PX] [--kicad-cli PATH]
[--timeout SECONDS]` writes review views of the board, through `kicad-cli` on the same copy set and
with the same protocol and tool errors as `export`. `--svg` plots `front.svg` (`F.Cu`, `F.SilkS`,
`F.Fab`, `Edge.Cuts`) and `back.svg` (the back layers, mirrored) with `pcb export svg --mode-single`;
`--png` renders `top.png` and `bottom.png` with `pcb render`, at most `--width` by `--height` pixels
(defaults 1600 and 1200, each from 64 to 8192). A call with neither flag exits 2. `result` holds `board`,
`out`, `views` (`path`, `kind`, `bytes`, `sha256`; sorted by path) and `tool_version`.

| code | severity | when |
|---|---|---|
| `render.failed` | warning | a view was not produced; `where` is the view name, and the other views are still written |

A render is a review artefact, never a gate: `render` exits 0 whenever the tool is found.

## inspect

`fenolite inspect FILE [--summary | --streams] [--limit-bytes N]` runs no tool. `--summary` is the
default view: boards, footprint files and symbol libraries (file or `.kicad_symdir`) use their reader;
`.kicad_sch` and `.kicad_wks` are read header-only, with counts of root children by head. `result` holds
`kind`, `format_version`, `major`, `status`, `generator`, `generator_version`, `counts`, `opaque_count`
(boards only) and `model_findings` (the `model.*` findings counted by severity, not reported as issues).
`input.path` is the file name. `.kicad_pro`, `.kicad_dru` and other non-S-expression files exit 2
(`FEN-2001`); a file beginning with the compound-file signature has a hint to use `--streams`. A read
error exits 3 with its code.

`--streams` selects an MS-CFB container by its bytes, regardless of its extension, and reads only its
storage and stream tree. `--summary` and `--streams` together exit 2 (`FEN-2001`). `--limit-bytes N`
sets the reader's `Limits.max_file_bytes` for this view; it must be a positive integer. The default is
1,073,741,824 bytes. For this view, `result` holds `kind` (`compound_file`), `format_version` (major as
a string), `major`, `minor`, `sector_size`, `mini_sector_size`, `sectors`, `fat_sectors`, `difat_sectors`,
`directory_entries`, `root_clsid` (lower-case hex or `null`), `counts` (`storages`, `streams`, total
stream `bytes`) and `entries`. Entries are in depth-first name order without the root: storages have
`path`, `type` and child count; streams have `path`, `type`, `size` and their byte `sha256`. `input`
contains the file name, file `sha256`, `kind` (`compound_file`) and major `format_version`. The envelope
evidence is `CompoundFile.evidence`; reader notes appear in `issues` and do not change exit 0. A malformed
container or a limit failure exits 3 with `FEN-3004` and a located `cfb.*` message; a missing file exits
3 with `FEN-3001`. Note and structural rule codes are listed in `docs/altium.md` under "Reading a compound
file". Note codes are `cfb.note.minor-version`, `cfb.note.header-fields`, `cfb.note.partial-sector`,
`cfb.note.fat-marks`, `cfb.note.high-size-bits`, `cfb.note.long-chain`, `cfb.note.entry-fields`,
`cfb.note.tree-order` and `cfb.note.orphan-entries`. Structural rules are `cfb.signature`,
`cfb.truncated`, `cfb.header`, `cfb.difat`, `cfb.chain`, `cfb.shared-sector`, `cfb.directory`,
`cfb.name`, `cfb.duplicate-name`, `cfb.size` and `cfb.limit`.

## doctor

`fenolite doctor [--kicad-cli PATH]... [--no-run]` reports the external tools. `result.kicad_cli` holds
one entry per `kicad-cli` candidate (each `--kicad-cli`, `FENOLITE_KICAD_CLI`, `kicad-cli` on `PATH`
(`kicad-cli.exe` and the other `PATHEXT` names on Windows), KiCad's default Windows install folders
`<Program Files>\KiCad\10.0\bin` and `…\9.0\bin` (source `windows-install`), the macOS application
bundle; one entry per binary) with `path`, `source`, `version`, `major`,
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

## place

`fenolite place PATH [--strategy grid|manual] [--move REF=X,Y[,ROT[,SIDE]]]... [--only REF,…]
[--pitch L] [--gap L] [--margin L] [--force] [-o OUT]` moves footprints of the board that `PATH` names
(a `.kicad_pcb`, a `.kicad_pro` or a project folder) and runs no tool. It is a mutating command: nothing
is written without `--confirm`, and the plan holds one write, the board at `-o` or in place, or none when
nothing moved. The user guide is `docs/placement.md`.

- `--strategy grid` (the default without `--move`) places every footprint that is off the board, or
  those of `--only`, in component-path order on a grid: `--pitch` (default `0.5mm`) is the grid step,
  `--gap` (default `0.5mm`) the space kept around each courtyard box, and `--margin` (default `1mm`) the
  distance kept from the bounding box of the outline. Parts keep their rotation and side.
- `--move REF=X,Y[,ROT[,SIDE]]` (repeatable; it implies `--strategy manual`) moves one footprint. `X`
  and `Y` are lengths with a unit (`12mm`, `0.5in`), relative to the top-left corner of the bounding box
  of the board outline, Y down, as in the script's `place()`; without an outline they are relative to
  the file origin. `ROT` is an angle in degrees and `SIDE` is `top` or `bottom`. A new rotation or side
  re-places the footprint from its library definition, found through the project's `fp-lib-table`.
- After the moves, the legality check judges the whole layout. With a `place.*` error and without
  `--force` the command plans no write and exits 5; with `--force` it writes and still reports the
  issues. `--force` also moves a footprint that is locked on the board.

`result` holds `board`, `strategy`, `moved` (`ref`, `path`, `from` and `to`, each with `x` and `y` in
nanometres, `rotation` in microdegrees and `side`; sorted by reference), `unplaced` (the references
still off the board) and `legality` (the number of issues by code). The evidence is
`placement.EVIDENCE`: a placement is never a verdict, and KiCad's DRC judges the board.

| code | severity | when |
|---|---|---|
| `place.courtyard-overlap` | error | two courtyards on the same face overlap; `where` is `REF1,REF2`, sorted |
| `place.outside-outline` | error | a courtyard leaves the board outline or enters a cut-out |
| `place.no-definition` | error | a rotation or side change of a footprint whose library definition is not found |
| `place.locked` | error | a footprint that is locked on the board, without `--force` |
| `place.unknown-ref` | error | `--move` or `--only` names a reference that the board does not hold |
| `place.edge-clearance` | warning | a courtyard is closer to the board edge than the edge clearance |
| `place.no-room` | warning | the grid found no place for a part; it stays where it was |
| `place.copper-left` | warning | a moved footprint had copper ending on its pads; the copper stays |
| `place.script-locked` | warning | the part has a locked placement in `.fenolite/`; the next build restores it |
| `place.no-extent` | info | a footprint has neither a courtyard nor pad copper; it is not judged |
| `place.no-outline` | info | the board has no closed outline; only courtyard overlaps are judged |

`fenolite build` reports the same legality codes for the board it is about to write, each at most as a
warning (`result.placement` holds `ran` and `counts`): a build never refuses for placement.
`result.routers` lists registered routers; `--no-run` lists names without availability probes. The `freerouting` entry also holds `java` (the first line of `java -version`), `java_major` and `java_ok` (`java_major >= 25`): a jar without a suitable Java gives `doctor.tool-unsupported` naming Java 25, and a missing jar `doctor.tool-missing`.

## analyze

`fenolite analyze PATH [--kinds current,clearance,creepage] [--requirements FILE] [--temp-rise KELVIN]
[--copper-thickness [LAYER=]LENGTH]... [--via-plating LENGTH] [--board-thickness LENGTH]
[--pair NET_A NET_B]... [--within LENGTH] [--arc-tol LENGTH]` measures the current capacity of tracks,
arcs and vias, and the clearance and creepage of pairs of nets, on a board that a registered backend
reads. It is read-only: it runs no tool and writes no file. The user guide is `docs/analyses.md`.

**Fenolite measures and the user decides.** No reply claims conformance to a standard. Fenolite ships no
requirement value and assumes no thickness and no temperature rise: an input that is not given leaves
items out, which are counted (`analysis.input-missing`). A finding exists only against a requirement of
the user's file.

- `--kinds` selects the analyses (default: all three). `clearance` and `creepage` come from one pass; an
  unselected kind is left out of each row.
- `--requirements FILE` names a TOML file of schema `fenolite.requirements.v0` (integers only, units in
  the key names): currents per net or net class, distances per pair, and an optional table from voltage
  to distance that is looked up without interpolation.
- `--temp-rise` is a temperature rise in kelvin with at most three decimals. A current row of the
  requirements file gives its own rise for its nets.
- `--copper-thickness LENGTH` gives the copper thickness of every layer and `LAYER=LENGTH` that of one
  layer (repeatable); `--via-plating` the plating of a via barrel; `--board-thickness` the thickness of
  the board, which the paths around the board edge need.
- `--pair NET_A NET_B` (repeatable) measures one pair. `--within LENGTH` measures every pair of nets
  with a gap on a layer below that length. A distance row of the requirements file selects the pairs it
  matches. A search stops at the largest requirement of the pair; a pair named by `--pair` alone is
  searched without a limit.
- `--arc-tol` is the chord error of polygonised copper arcs (default `1um`).
- Lengths need a unit (`35um`, `1.6mm`).

`result` holds:

- `current`: one row per track, arc and via with `kind`, `where`, `entity_id`, `net`, `layer`, `at`,
  `width`, `thickness`, `area_nm2`, `external`, `temp_rise_mk`, `capacity_ma` and `in_range`;
- `distances`: one row per pair with `net_a`, `net_b`, `gaps` (one measure per copper layer that carries
  both nets), `clearance` and `creepage`. A measure holds `low` and `high` in nanometres, `layer`,
  `points`, `items` and `bounded`;
- `summary`: per analysis, the counts; `current.nets` names the weakest item of each net, `current.fit`
  the source id of the fit, and `distances.faces_alone` the pairs measured on each face alone because the
  board thickness or outline is unknown;
- `inputs`: the option values in force and the boundary (`source`, `band`, `cutouts`).

A requirement `r` is judged the same way for every measure: `high < r` is an error, `low < r ≤ high` a
warning (`-undecided`), `low ≥ r` nothing. An error gives exit code 5. An unknown kind, a malformed option
or `--pair` without exactly two different names is a usage error (`FEN-2001`, exit 2); an unreadable
requirements file is `FEN-3004` (exit 3). Every reply carries `evidence.level` `INFERRED`, or
`UNVERIFIED` when an item or an input was left out.

| code | severity | when |
|---|---|---|
| `analysis.current-exceeded` | error | the capacity of an item is below the current its net requires |
| `analysis.clearance-below` | error | the clearance is below the requirement |
| `analysis.clearance-undecided` | warning | the requirement lies inside the interval of the clearance, or of a gap inside the laminate |
| `analysis.creepage-below` | error | the creepage is below the requirement |
| `analysis.creepage-undecided` | warning | the requirement lies inside the interval of the creepage, or the search was bounded |
| `analysis.embedded-below` | error | a gap on an inner layer is below `embedded_nm` |
| `analysis.fit-out-of-range` | warning | rows computed outside the range its source states for the fit |
| `analysis.input-missing` | warning | an input that Fenolite does not assume is absent; the items left out are counted |
| `analysis.item-unsupported` | warning | copper that could not be shaped, per kind, or a conductor outside the board |
| `analysis.requirement-unmatched` | warning | a requirement row that matches no net, or a voltage above every step |

## template

`fenolite template build SPEC --target kicad -o OUT` builds a drawing sheet (`.kicad_wks`) from a
`*.sheet.toml` specification and runs no tool. The actions are `build` and `import` ("template import"
below); `--target` and `-o`/`--out`
are required, and `kicad` is the only target. It is a mutating command: without `--confirm` it exits 4
with `FEN-4001` and writes nothing, `--dry-run` shows the plan and exits 0, and `--confirm` writes `OUT`
and returns the `receipt`. The plan holds one write of kind `kicad_wks`. The format of the specification
and the shipped examples are in `docs/sheet-templates.md`.

`result` holds:

- `sheet`: `name`, `sizes` (the page sizes the specification lists), `items` (the number of sheet items)
  and `tokens` (the sorted token names its texts use; a user parameter is `param:<name>`);
- `target` (`kicad`) and `kicad_version` (the `--kicad-version` major, 10 by default). The major selects
  the writer's check only: the written bytes are the same for 9 and 10;
- `drawn`: per listed size, the `texts` and `lines` KiCad will draw on that page, and `resolved`, the
  texts with an empty title block (a token without a value is an empty string; `paper` and the sheet
  number are filled);
- `output`: `OUT` as given;
- `plan` on a dry run or an unconfirmed run.

`input` names the specification with its SHA-256 and the kind `sheet-toml`. The evidence is `INFERRED`
(`H-K-WKS-CORNER`): the command does not open the sheet in KiCad.

| exit | error | when |
|---|---|---|
| 0 | none | a dry run, or a confirmed write |
| 2 | `FEN-2001` | a missing `--target` or `-o`, or a target other than `kicad` |
| 3 | `FEN-3001` | the specification is missing or unreadable |
| 3 | `FEN-3004` | the specification is malformed; `where` is `<file>:<key path>` of the first problem |
| 4 | `FEN-4001` | neither `--dry-run` nor `--confirm` |
| 7 | `FEN-7001` | the writer refuses an item for the target; `--allow-lossy` drops it with a warning |

A malformed specification reports every problem at once, as one issue each:

| code | severity | when |
|---|---|---|
| `template.unknown-key` | error | a key or table outside the closed set |
| `template.bad-value` | error | a wrong type or value, a missing required key, or a TOML syntax error |
| `template.resolution` | error | a length that is not a whole number of micrometres |
| `template.unknown-token` | error | a cell `token` or a `label` that is not a valid token text |
| `template.unproven-value` | error | a number missing from `[provenance.values]` when provenance is required |
| `template.cell-overlap` | error | two cells cover one grid position |
| `template.cell-outside` | error | a cell leaves the grid |
| `template.zone-letters` | error | more than 8 letter rows on a listed size |
| `template.bitmap-not-png` | error | a `[bitmap]` file without the PNG signature |
| `template.too-wide` | warning | a title block wider or taller than the margin box of a listed size |

### template import

`fenolite template import SRC --target kicad -o OUT` is the second action of the command: it imports an
Altium sheet template (`.SchDot`, or a `.SchDoc` with an applied template, binary or ASCII) into the neutral
drawing sheet and writes it as a `.kicad_wks`, through the same mutation protocol. The form is taken from the
content. The sheet's name is the stem of `SRC`. The format and the report are described in
`docs/sheet-templates.md`, "Importing an Altium sheet template".

`result` holds:

- `sheet`: `name`, `items` and `tokens`, as for `build` (there is no `sizes`);
- `source`: `form` (`binary` or `ascii`), `style` (the sheet style number, `null` for a custom sheet),
  `paper`, `portrait`, and `width` and `height`, the drawing area in nanometres as oriented;
- `imported`: per record kind (a decimal string), the number of records that gave at least one item;
- `reported`: the `where` of each record that gave none, in record order;
- `strings`: each distinct special string of the template with its neutral text;
- `parameters`: the names of the sheet-level parameters, without their values;
- `target`, `kicad_version` and `output`, as for `build`;
- `drawn`: one entry, keyed by `source.paper`, with the `texts` and `lines` predicted on the template's own
  page and `resolved`, the texts with an empty title block;
- `plan` on a dry run or an unconfirmed run.

`input` names `SRC` with its SHA-256 and the kind `altium-sheet`. The envelope's `issues` hold the importer's
issues (`altium.sheet.*`), then the writer's. The evidence is `INFERRED` (`H-A-RD-SHT-SAME`,
`H-K-WKS-CORNER`): no second reader of an Altium schematic exists, and the command does not open the sheet in
KiCad.

| exit | error | when |
|---|---|---|
| 0 | none | a dry run, or a confirmed write |
| 2 | `FEN-2001` | an action other than `build` or `import`, a missing `--target` or `-o`, or a target other than `kicad` |
| 3 | `FEN-3001` | `SRC` is missing or unreadable |
| 3 | `FEN-3004` | `SRC` is not an Altium schematic, its record 0 is not the sheet record, or its sheet style is unknown |
| 4 | `FEN-4001` | neither `--dry-run` nor `--confirm` |
| 7 | `FEN-7001` | the import would lose something and `--allow-lossy` is not given, or the writer refuses an item; the envelope's `issues` name every loss, on a dry run too |

The twelve `altium.sheet.*` codes: `not-representable`, `not-template-content`, `builtin-not-drawn`,
`outside`, `image-not-kept`, `image-size`, `unknown-string`, `dynamic-string` and `style-dropped` are
warnings (losses); `appearance`, `rounded` and `builtin-drawn` are infos.
## bom

`fenolite bom PATH [--source kicad|model] [--template FILE] [--out FILE] [--against OTHER]` gives the bill
of materials of the project `PATH` names (resolved as for `check`) as a neutral table, rendered through a
column template that the user writes (`docs/assembly.md`). Fenolite ships no template of any assembly
service; without `--template` the built-in default applies, whose column names are Fenolite's field names.

- `--source model` lists the parts of the `.fenolite/` model of a built project, or of the board read for
  any other project. It runs no tool.
- `--source kicad`, the default, is the bill that `kicad-cli` exports from the project's schematic. It is
  **not available yet** (it arrives with the schematic writer, together with `--kicad-cli` and
  `--timeout`). Until then the command never falls back: without a `<stem>.kicad_sch` next to the board it
  exits 3 with `FEN-3001`, with one it exits 2 with `FEN-2001`, and both hints name `--source model`.
- `--against OTHER` reads `OTHER` as `PATH`, with the same source and template, and adds `result.changes`:
  what changed from `OTHER` to `PATH`.

`result` holds `source`, `template` (the file name without its folder, or `default`), `columns` (the
column names), `lines` (one object per line, keyed by column name, with the text the file would hold),
`counts` (`parts`, `lines`, `dnp`, `left_out`) and, with `--against`, `changes` (each `key`, the values of
the grouping fields; `change`, one of `added`, `removed`, `changed`; `a_refs`, the references in `OTHER`;
`b_refs`, those in `PATH`). No value holds a date or an absolute path, and two runs on an unchanged
project give the same output apart from `elapsed_ms`.

It is a mutating command that writes only with `--out FILE`: the plan then holds one write of kind `bom`,
the CSV bytes of the table, and the mutation protocol applies (4 without `--dry-run` or `--confirm`).
Without `--out` nothing is planned and the exit code is 0. The project folder never changes.

| code | severity | when |
|---|---|---|
| `assembly.template-invalid` | error | the template has an unknown table or key, an unknown field, two columns with one name, an empty column list or a value outside its set; one issue per problem, `where` is the key path; the command exits 3 with `FEN-3004` |
| `bom.property-missing` | info | a column names a `property:<NAME>` that no part has; the column is empty; `where` is the column name |

Exit codes: 0, 4 as above, 2 for a usage error, 3 for a missing path, a template that cannot be read
(`FEN-3001`) or is invalid (`FEN-3004`), or a `.fenolite/` model that cannot be read (`FEN-3004`). The
evidence of the `model` source is `INFERRED` (`H-K-BOM-MODEL`), combined with the evidence of the board
read when the project was not built by Fenolite.

## pnp

`fenolite pnp PATH [--template FILE] [--side top|bottom|both] [--out FILE]` gives the placement
(pick-and-place) table of the board `PATH` names (resolved as for `check`), rendered through the same kind
of template (`docs/assembly.md`). It runs no tool. The rows always come from the board file, also in a
built project, because `place`, `route` and `fill` write the board and not the `.fenolite/` model.

`result` holds `template`, `columns`, `rows` (one object per row, keyed by column name, with the text the
file would hold), `counts` (`rows`, `top`, `bottom`, `dnp`, `left_out`), `units`, `origin` and `y_axis`.
`--side` (default `both`) keeps the rows of one side. With `--out FILE` the plan holds one write of kind
`pnp`; without it nothing is planned.

| code | severity | when |
|---|---|---|
| `assembly.template-invalid` | error | as for `bom` |
| `pnp.no-outline` | error | the template has `origin = "outline"` and the board has no closed outline; there is no row and no file |

Exit codes: 0, 4 without `--dry-run` or `--confirm` when `--out` is given, 5 with `pnp.no-outline`, 2 for
a usage error, 3 for a missing path or template or an invalid template. The evidence is
`placement.EVIDENCE` (`H-K-PCB-POS`, `H-K-POS-ROWS`) combined with the evidence of the board read. Under
the default template the table holds the content of `kicad-cli pcb export pos`, without the DNP parts and
with rotations printed from 0° up to 360°; `docs/assembly.md` lists the differences.
