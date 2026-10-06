# The `fenolite` CLI contract (v0)

Normative text: `openspec/specs/cli-contract/spec.md` and `openspec/specs/package-layering/spec.md`.
This page is the short human version. The contract is frozen at 1.0; before that, a breaking change
bumps the schema id.

## Output

- **JSON when stdout is not a terminal**, text when it is. `--json` / `--text` override.
- One JSON document per invocation on stdout, followed by a newline.
- `--limit N` and `--cursor TOKEN` page a command's main list, and `--format concise` keeps one issue
  per code (see "Paged results" and "Concise output").
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
`receipt` is `{written: [{path, sha256}], backup: [path], id, undo}` when the command wrote files
(see "Receipt identity").

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

A design rule of a kind the target major does not check is refused the same way, with the issue
`rules.kind-unchecked`: a `creepage` rule and `--kicad-version 9`. With `--allow-lossy` the rule is left
out of the `.kicad_dru` and reported as `rules.dropped-for-target`; it stays in `.fenolite/rules.json`.

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

`--altium-outjob {on,off}` (change c0087) writes `<name>.OutJob`, an Altium output job, beside the PCB
document of an Altium build: `on` is the default, `off` writes none, and a build without a PCB document
writes none either. The job holds the containers `fab` (a folder) and `doc` (a PDF) and six outputs: Gerber,
NC drill, pick and place and bill of materials for `fab`, a schematic print and a PCB print for `doc`. Its
write kind is `altium_outjob`, and a new project file lists it after the PCB document. Fenolite runs no
output: the job is run in Altium. `--altium-outjob-preset FILE` names the export preset the job is made for
(the TOML file of `export --preset`). The writer maps no option of a preset to a key of the job yet, so every
output keeps Altium's defaults and `result.outjob.defaults` lists the options the preset sets, as sorted
`table.key` texts, for you to set in Altium. Either option with `--target kicad`, and the preset with
`--altium-outjob off`, is a usage error (`FEN-2001`, exit 2); a preset that cannot be read or is malformed
fails as it does for `export`. `result.outjob` is `null` without a job and otherwise holds `file`, `preset`
(`null`, or `file` and `sha256`), `media` (`name` and `type` per container), `outputs` (`kind`, `type`,
`name`, `category`, `document`, `enabled` and `medium` per output) and `defaults`. A kept project file that
does not list the job gives the info `altium.outjob-not-listed`.

A script that names a drawing sheet with `design.sheet(drawing_sheet=…)` gets it on every schematic document
of an Altium build (change c0087), with the fields and variables of `design.title_block(…)` as sheet
parameters. `result.drawing_sheet` is `null` without one and otherwise holds `source` (the path as written in
the script), `items` and `pages` (`file`, `paper`, `width` and `height` in nm per schematic document). A
layout that does not fit the paper of `sheet()` gives the warning `altium.sheet-paper` and a larger page. A
part of the sheet that the Altium form cannot carry is a loss with an `altium.sheet.*` code: without
`--allow-lossy` the build exits 7 with `FEN-7001` and writes nothing (`docs/altium.md`, "Drawing sheet").


Since change c0086 `modules` gives every module at any depth a sheet of its own: a module's sheet holds
its own parts and one sheet symbol per module directly below it, and its file is
`<name>_<module path with "." for "/">.SchDoc` (`<name>_io.leds.SchDoc` for the module `io/leds`).
`--altium-symbols {graphics,generic}` (default `graphics`; a usage error `FEN-2001` without
`--target altium`) picks how a resolved symbol is drawn: from its own graphics, or as one rectangle per
part. The default changed the files of an Altium build; `generic` gives the files of earlier versions,
byte for byte.
`--altium-directions {on,off}` (default `on`; a usage error `FEN-2001` without `--target altium`) picks
the I/O type of ports and sheet entries: `on` writes output, input or bidirectional where the pin types
on the net say so (`docs/altium.md`, "Port directions"), `off` leaves every one unspecified.
`result.schematic` holds `sheets`, `symbols` (`graphics` or `generic`), `symbols_drawn` (library symbols drawn from their own graphics),
`symbols_simplified` (those drawn as a rectangle), `buses` (bus blocks drawn), `parameters` (hidden
component parameters written), `directions` (`on` or `off`) and `directed` (ports and sheet entries that
carry a direction); it is `null` for a refused build. The info `altium.bus-flattened` names a bus of the
design that is drawn as its nets.

`--copper-from BOARD.kicad_pcb` (with `--target altium` only; a usage error `FEN-2001` otherwise, and for
a path that is not a file) copies the tracks, arcs, vias and zones of a routed KiCad board of the same
design into `<name>.PcbDoc`, after checking that the board matches the design; the board's placements
win (`docs/altium.md`, "Copper"). The board is read in-process: a board the reader refuses exits 3
with its `FEN-3xxx` code, and the reader's issues and evidence join the build's.

`result.copper` is present whenever the PCB document is planned (`null` otherwise): `source` (`none`,
`model`, `script` or `board`), `from` (the path given to `--copper-from`, else `null`), `layers`,
`planes` (layer name to net name), `tracks`, `arcs`, `vias`, `zones`, `net_classes` (counts of what
is written) and `placements_from_board`. `result.pcb` (change c0085) is `null` without a PCB document; with one it holds `written`, the number of model items the document holds per kind (`footprint`, `pad`, `track`, `arc`, `via`, `zone`, `text`, `graphic`, `keep-out`, `hole`, `body`, `rule`), and `not_lowered`, the kinds with items it does not hold and their number. With `--copper-from`, `result.copper_input` holds the board's
`path`, `sha256`, `kind` (`kicad-board`) and `format_version`; the envelope's `input` stays the script.

`result.rules` (change c0084) is `null` when the build is refused, else `written` and `not_lowered`:
the script's rules that the PCB document holds (`kind`, `selector`, `rule`: the name of the Altium rule)
and those it does not (`kind`, `selector`, `reason`: `no-counterpart`, `scope-unsupported`,
`value-unsupported`, `unit-loss`, or `no-document` when no PCB document is planned). Each rule of
`not_lowered` gives one `altium.not-lowered` **warning** with `where` `design-rules/<kind>`; no issue
has the `where` `design-rules` alone (`docs/altium.md`, "Rules").

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

A build for the KiCad target also checks the interfaces of the design (`docs/dsl.md`, "Typed interfaces"):

| code | severity | meaning |
|---|---|---|
| `build.diff-pair-name` | warning | the two nets of a `diff_pair` or `usb2` interface are not a differential pair for KiCad by name; the hint proposes a name |
| `build.i2c-pullup-missing` | warning | a line of an `i2c` interface has no two-pin part to the `hv` net of a `power` interface |

## `build`

`fenolite build DESIGN.py --out DIR [--discard-layout] [--vendor all|project] [--schematic write|skip]
[--schematic-layout readable|grid]
[--target kicad|altium]
[--altium-format binary|ascii] [--altium-sheets flat|modules] [--altium-outjob on|off]
[--altium-outjob-preset FILE] [--altium-symbols graphics|generic] [--altium-directions on|off]
[--copper-check refuse|warn]` runs the design script
(your own code: never run it on an untrusted script) and plans the files of a KiCad project under `DIR`
(`docs/dsl.md`). It is mutating. `--discard-layout` replaces outputs edited since the last build.
`--vendor all` (the default) copies the placed footprints of every library into `DIR/lib/`; the copies
keep their library's licence. `--vendor project` copies only those of project tables, and each other
footprint gives the info `build.global-library`. `result.vendored` lists the copied files and
`result.libraries` the row origin of each lib id.

A pin marked with `no_connect` that a net also lists, once designators are resolved to pin numbers, is
refused: `build.no-connect-on-net` (error) with `--target kicad`, `model.no-connect-on-net` (error) with
`--target altium`; the exit code is 5 and nothing is written. The marks are kept in
`.fenolite/circuit.json`; in a KiCad build each mark becomes a no-connect flag of the schematic, and no
other written KiCad file depends on them (`docs/dsl.md`, "No-connect marks").

Over an existing project, `build` preserves the layout (`docs/lens.md`): the board, project and rules
files are merged, and `build.layout-exists` (`FEN-7001`) now guards only `fp-lib-table`,
`sym-lib-table` and the vendored footprints and symbol libraries under `lib/`. `--discard-layout` reads no existing file and builds from scratch.
`result.preserved` reports `board` (whether an existing board was read), `kept`, `replaced` and `added`
(component paths), `orphans` and `board_only` (references), `dropped` (counts of tracks, arcs, vias and
zones), `fills` (zones whose fills were kept and dropped), `aliases` (new path → old path),
`reader_infos` (a count of the board reader's infos) and `fields`: three sorted lists of
`"<component path>:<field name>"`, `kept` (an unlocked `Part.field()` request differs from the board's
field, which wins), `forced` (a locked request changed a board field) and `carried` (a field of a
re-placed footprint took the board's values); all three are empty without an existing board
(`docs/lens.md`, "Footprint fields"). `pad_zones` holds two sorted lists of
`"<component path>:<pad number>"`: `kept` (an unlocked `Part.zone_connection()` request differs from
the setting of a board pad, which wins) and `forced` (a locked request replaced the setting of a board
pad); both are empty without an existing board (`docs/lens.md`, "Pad zone connections"). Their issues
are `kicad.pad.zone-overridden` (info), `kicad.pad.zone-forced` (warning) and
`kicad.pad.zone-unknown-pad` (error: exit 5, nothing written).

A script may declare copper (`docs/dsl.md`, "Copper"; `docs/copper.md`). The build resolves it after
placement, and the KiCad `result.copper` reports `intents`, `tracks`, `arcs` and `vias` (created), and
`regenerated`, `stale` and `duplicates` (from the merge with an existing board; 0 without one). A
copper error (a `kicad.copper.*` issue of severity error) exits 5 and writes nothing; the
`kicad.copper.*` and `kicad.frame.*` codes are listed in `docs/copper.md`. With intents, the envelope
evidence also combines the copper and board-frame evidence, which are `INFERRED`. `--seed`,
`--timestamp` and `PYTHONHASHSEED` change no byte of a build with intents. A via of kind `buried` needs
`--kicad-version 10`: for KiCad 9 the board writer refuses it and the build exits 7 (`FEN-7001`).

**Copper guard.** Before a KiCad build plans its writes, it judges the copper of the triad it is about
to write with the copper check of `check` (`copper.clearance`, below): the planned board is read back,
the planned project and rules files give the clearance in force, and copper kept from an existing board
is judged with the rest. `--copper-check refuse` (the default) adds the `copper.*` issues as they are,
so a `copper.short` or a `copper.clearance` error exits 5 and writes nothing. `--copper-check warn`
reports those errors as warnings, with ` (copper guard in warn mode)` at the end of the message, and
writes. There is no way to switch the guard off. `result.copper_check` holds `mode`, `ran` (false when
the build was already refused), `shorts`, `clearance`, `rules` (`min_clearance`,
`opaque_clearance_rules`, `unread`) and `evidence`. The guard runs on `--dry-run` too, reads and writes
no file, and runs no tool. With `--target altium` the guard judges the PCB document instead (below,
"Copper guard of an Altium build"). A Python caller of
`build_design` is not guarded (`docs/dsl.md`, "Copper guard").

**Placement guard.** The same planned board is then judged by the placement legality check
(`docs/placement.md`): the courtyards of the placed parts against each other and against the outline.
Parts that the build staged (`result.staged`) are not judged. Every `place.*` issue is reported at most
as a warning, so a build never exits 5 for placement; the codes are those of the table under "place".
`result.placement` holds `ran` (false when the build was refused) and `counts`, the number of issues by
code. The guard runs on `--dry-run` too, reads and writes no file, and runs no tool. With
`--target altium` there is no `result.placement`. A Python caller of `build_design` is not guarded; it
calls `placement.check` itself (`docs/placement.md`).

## `sync`

`fenolite sync DESIGN.py --out DIR --to-source [--check]` copies the layout of a built project into the
source tree (`docs/lens.md`, "sync" and "placements.toml"). It is a mutating command: the writes follow
"Writing files", `.bak` files included. It runs `DESIGN.py` as `build` does and starts no external tool.

- `--to-source` is required (exit 2, `FEN-2001` without it), so a later direction cannot change what a
  bare `sync` does.
- The board `DIR/<design name>.kicad_pcb` must exist: otherwise exit 3, `FEN-3001`, with the hint to run
  `fenolite build` first. The refusals of a build over an existing board apply unchanged.
- **Writes** go beside the design script, not under `DIR`: `placements.toml`, and
  `schematic-placements.toml` when `DIR` holds the schematic of the design; each only when its text
  would change. A run that changes nothing plans nothing and asks for no confirmation.
- **`--check`** plans nothing and reports one `sync.would-change` (error) per file that would change,
  naming its first differing table: exit 5 when a committed file is stale, 0 otherwise. `--check` with
  `--confirm` is a usage error (exit 2).
- **`result`**: `design`, `out`, `board` (the file name), `placements` (the number of entries),
  `unplaced` (matched parts that lie off the board and stay out of the file), `orphans` and `board_only`
  (references), `symbols` (the number of tables of `schematic-placements.toml`, or `null` when `DIR`
  holds no schematic), `files` (the names that change) and `script_output`.
- **Issues**: those of the board read, and the `sync.*` codes of `docs/lens.md`: `sync.would-change`
  (error), `sync.orphan`, `sync.net-dropped`, `sync.value-differs` and `sync.symbol-off-grid`
  (warnings).
- Two runs on equal inputs plan equal bytes.

`build` writes the drawing sheet that `design.sheet(drawing_sheet=…)` names as `<name>.kicad_wks`
(`docs/dsl.md`, "Drawing sheet and title block"). `result.drawing_sheet` holds `source` (the path in
the script), `file` and `items`, or `null`. A source that is missing exits 3 with `FEN-3001`, and one
that does not parse with `FEN-3004`, before anything is planned.

`build` reads `placements.toml` beside the script when it exists (`docs/lens.md`, "placements.toml").
`result.preserved` gains `module_aliases` and `net_aliases` (new → old, empty without an existing board)
and `source`, with `file` (`placements.toml` or `null`), `used` (component paths placed from the file),
`stale` and `unknown`. An invalid file gives `layout.source-invalid` (exit 5, nothing written); a file
that is not TOML or has another `schema` exits 3 with `FEN-3004`.

**Schematic.** A KiCad build also writes the schematic of the design (`docs/schematic.md`):
`DIR/<name>.kicad_sch`, one `DIR/lib/<nickname>.kicad_sym` per symbol library the design uses, and
`DIR/sym-lib-table`. `--schematic write` is the default; `--schematic skip` writes the files of a build
without a schematic, and is a usage error with `--target altium`. The sheet holds every unit of every
part's symbol, a global label of the net at each connected pin, a no-connect flag at each pin marked with
`no_connect`, and a power flag on each net of a `Power` interface that no power output drives. The board
follows the sheet: the pad of each unconnected pin is on a net named as KiCad names it
(`unconnected-(U1-PA1-Pad2)`), a `/` in a net name is stored as `{slash}`, and each footprint carries the
path of its symbol; the `.fenolite/` model holds none of this. `result.schematic` holds `file`, `paper`
(the root's), `sheets` (their number, the root included), `files` (the child sheet files), `symbols`,
`labels`, `no_connects` and `wires` (counted over every sheet), `satellites`, `power_flags`, `libraries`
(the symbol library files) and `unconnected_pads`, and is `null` with `skip`.

`--schematic-layout readable` (the default) gives each module that holds a part a sheet of its own,
`DIR/sheets/<module path with "." for "/">.kicad_sch`, named by a box on the sheet above it, and puts a
2-pin part beside the IC pin it connects to, joined by one wire. Nets cross sheets by their global
labels, so net names stay those of the script; a footprint of a part in a module carries the path
`/<sheet uuids>/<symbol uuid>`. `--schematic-layout grid` writes the one flat sheet of v0.2a, without
wires. The option is a usage error with `--target altium`. An edited child sheet is replaced like the
root; a child sheet of the last build that the design no longer has is left in place, with
`build.sheet-stale`. `schematic-placements.toml` beside the script fixes symbol
positions. The schematic is a view of the script: a schematic changed since the last build is replaced,
with `build.schematic-replaced` and a `.bak` copy, while an edited `sym-lib-table` or symbol library is
refused like any vendored file. With `--vendor project`, a symbol of a row that is not a project row is
embedded in the sheet and gets no project library (`build.global-library`). Before any file is returned, the build reads the
nets of the sheet it generated back from the sheet, without any tool, and compares them with the circuit:
a difference is a defect of the generator and stops the build (`build.schematic-netlist-differs`).

| code | severity | when |
|---|---|---|
| `build.schematic-too-large` | error | the units of one sheet do not fit an A0 page |
| `build.sheet-file-collision` | error | two modules give one child sheet file |
| `build.schematic-netlist-differs` | error | the nets read back from the generated sheet are not those of the circuit; nothing is written |
| `build.symbol-short` | error | two symbols placed by the placements file have a pin at one point |
| `build.symbol-placement-invalid` | error | a placement is off the 1.27 mm grid, has an unknown key or a rotation or mirror that is not allowed |
| `build.reserved-library` | error | the design names or authors a symbol library `fenolite` |
| `build.symbol-overlap` | warning | the cell of a placed symbol overlaps another cell |
| `build.symbol-placement-unknown` | warning | the placements file names no unit of the design |
| `build.schematic-replaced` | warning | a schematic file, the root or a child sheet, changed since the last build is replaced |
| `build.sheet-stale` | warning | a child sheet of the last build is no sheet of the design any more; the file is left in place |
| `kicad.sch.unconnected-name-unproven` | warning | the net name of an unconnected pin is not written, so its pad stays on no net |
| `kicad.sch.dropped-too-new` | warning | `--allow-lossy` removed a token of an embedded symbol that the target does not read |
| `kicad.sch.pin-off-grid` | info | a library pin is not on the 1.27 mm grid |
| `kicad.sch.power-pin-shown` | info | a hidden power-input pin is embedded visible |

The board reader gives a net stored with `{slash}` the name with the slash; when another net of the board
already has that name it keeps its stored spelling (`kicad.board.net-name-collision`, info).

## Discovery

`fenolite capabilities` lists commands (`name`, `mutates`, `schema`, `hidden`), backends,
experimental features, the evidence matrix, installed extras, detected external tools (`kicad-cli`, `java`, `docker`) with
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
 "write_kinds": ["kicad_pcb", "kicad_mod", "kicad_dru", "kicad_pro", "kicad_wks", "kicad_lib_table"],
 "targets": [9, 10], "default_target": 10, "downgrade": "unsupported",
 "operations": ["detect", "read", "write", "lower", "validate"],
 "evidence": {"level": "INFERRED", "oracle": null, "hypotheses": ["H-K-PCB-READ", "H-K-PCB-WRITE"]}}
```

Two backends are listed, `altium` before `kicad`: find a backend by its `name`, never by its position.
The entry `altium` (change c0043) reads and does not write, so it lists no target:

```json
{"name": "altium",
 "read_kinds": ["altium_pcbdoc", "altium_pcblib", "altium_prjpcb", "altium_schdoc_ascii",
                "altium_schdoc_binary", "altium_schlib"],
 "write_kinds": [], "targets": [], "default_target": null, "downgrade": "unsupported",
 "operations": ["detect", "read"],
 "evidence": {"level": "INFERRED", "oracle": null, "hypotheses": ["H-A-IMP-NETLIST", "…"]}}
```

The Altium writers are not part of that report: they stay under `result.experimental`.

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

`result.matrix` is the evidence matrix (change c0067): one entry per backend package and file kind,
sorted by `backend` and then `kind`, with exactly the keys `backend`, `kind`, the five operations,
`verified_by` and `experimental`. It also lists packages that are not registered backends, such as the
`specctra` codec. An operation holds the label of its evidence, or `null` when the package does not
implement it for that kind:

| operation | meaning |
|---|---|
| `detect` | the package names the kind of a file from its name or its content |
| `read` | a reader builds a model object from a file of the kind |
| `write` | a writer produces a file of the kind from a model object that Fenolite created |
| `roundtrip_exact` | a file read and written back for the same version, unchanged in between, keeps its whole content, modelled or not |
| `roundtrip_modified` | a file read, changed through the model and written keeps everything the change did not touch, or the write is refused |

```json
{"backend": "kicad", "kind": "kicad_pcb", "detect": "INFERRED", "read": "INFERRED",
 "write": "INFERRED", "roundtrip_exact": "INFERRED", "roundtrip_modified": "INFERRED",
 "verified_by": ["H-K-PCB-READ", "H-K-PCB-WRITE", "H-K-TOK-CONSTANTS"], "experimental": []}
```

A label states what holds for an arbitrary file of the kind, so it is often weaker than the rows it
names: `verified_by` lists the hypothesis ids behind the row, sorted, and `docs/evidence/matrix.md`
shows the level that `docs/hypotheses.md` holds for each. A label is never stronger than a row it
names (`tests/unit/test_evidence_register.py`). An operation listed in `experimental` may change its
output, its options or its issue codes in any release; an operation labelled `UNVERIFIED` is always
listed there, and every write kind of `result.experimental` has a row whose `write` is experimental.
Listing the matrix runs no external tool, so it is the same with `--no-tools`. Every label comes from
a declaration in the code (`fenolite.backends.matrix`), and a backend module that declares nothing
fails the test suite.

## Altium import

Reading an Altium file through the registered backend `altium` (change c0043, `docs/altium.md`, "Reading
Altium files") gives issues of the closed table `fenolite.backends.altium.adapter.IMPORT_ISSUE_CODES`,
after the readers' own issues and before the `model.*` findings. An error issue never stops an import.

| code | severity | meaning |
|---|---|---|
| `altium.import.bad-stack` | error | the copper chain of the board record holds fewer than two layers; the board is read with `F.Cu` and `B.Cu` |
| `altium.import.sheet-loop` | error | a sheet symbol names one of its own ancestors; the import does not descend |
| `altium.import.bad-length` | warning | a length text is not a decimal number in `mil` or `mm`; the entity that needs it is not mapped |
| `altium.import.bad-geometry` | warning | a width, a diameter, a hole or a radius of 0 or less, or a region of fewer than three vertices; the record is not mapped |
| `altium.import.layer-outside-stack` | warning | a primitive lies on a layer id outside the copper chain and the layer table; it goes to `Altium.<id>` (one issue per id) |
| `altium.import.duplicate-net` | warning | two net records hold one name; they are one net |
| `altium.import.unknown-member` | warning | a net class lists a name that is no net |
| `altium.import.padstack-unknown` | warning | a pad's stack mode or hole shape is outside the table; the pad gets no padstack |
| `altium.import.via-span` | warning | a via's start or end layer is outside the copper chain; it is read as a through via |
| `altium.import.no-designator` | warning | a schematic component has no designator record; its reference is empty |
| `altium.import.sheet-missing` | warning | a sheet symbol names a sheet that is not among the inputs; its entries stay named points |
| `altium.import.repeated-sheet` | warning | a `Repeat(` statement that is not instantiated (it does not parse, its bounds are reversed, or it would pass 256 instances): one instance is read |
| `altium.import.channels` | info | a sheet is named by more than one sheet symbol, or by a sheet symbol with a `Repeat` statement: one channel per symbol or per index, named by the board or by the project's designator format |
| `altium.import.channel-naming` | warning | channel components that the designator format could not name (they are `<designator>@<channel>`); a sheet entry `Repeat(NAME)` whose parent bus is missing or too short; components of `Repeat` channels that no board component links to; channel components that the PCB document names otherwise than the format |
| `altium.import.scope-unknown` | warning | the project's hierarchy mode has no known meaning; the automatic scope is used |
| `altium.import.duplicate-net-name` | warning | two nets end with one name; the later one is renamed `<name>#<k>` |
| `altium.import.duplicate-sheet-name` | warning | two sheet symbols of one sheet have one designator; the second module path gets `#2` |
| `altium.import.bus-width` | warning | two bus identifiers that join have different widths; the common prefix is joined |
| `altium.import.harness-nested` | warning | a harness entry carries a harness of its own; it is not resolved |
| `altium.import.pcb-only-component` | warning | a component of the PCB document links to no schematic component; it is added to the circuit |
| `altium.import.document-skipped` | warning | a document of a project is outside the project folder, missing or unreadable; the design is built from the rest |
| `altium.import.zone-hole-outside` | warning | count of holes of poured regions that lie outside their region's outline; they are dropped and the fill is solid there |
| `altium.import.inexact` | info | counts of lengths and angles that were rounded; the originals are in the entities' `altium` bags |
| `altium.import.multi-class` | info | count of nets in more than one net class; the first class by name is kept |
| `altium.import.zone-arc` | info | count of zones whose outline holds an arc vertex; their model outline is empty |
| `altium.import.copper-shape` | info | count of fills and regions on copper, imported as graphics with their net in the bag |
| `altium.import.scope` | info | the net identifier scope that was used |
| `altium.import.option-ignored` | info | a project option that the import does not apply (`AppendSheetNumberToLocalNets`) |
| `altium.import.pin-map` | info | count of pin map records that name several pads, no pad, or a pad another pin holds: one pad per pin is compared, the record is kept in the component's bag |
| `altium.import.bus-member` | info | count of bus members without a net |
| `altium.import.harness-entry` | info | count of harness entries without a net |
| `altium.import.extra-board` | info | a project lists more than one PCB document; only the first is read |
| `altium.import.linked-by-designator` | info | count of PCB components linked to a schematic component by designator, not by unique-id path |
| `altium.import.pcb-only-net` | info | count of nets of the PCB document that the sheets do not hold; they are added to the circuit |
| `altium.import.rule-unmapped` | info | count of rule records of one rule kind that do not map, with the mapper's reasons |
| `altium.import.unmapped` | info | counts, by kind, of the records that gave no model entity, and the storages kept as bytes |

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
When a schematic of the board's stem lies beside it (`<stem>.kicad_sch`), the copy also holds what an
ERC run reads: that schematic, the sheet files its hierarchy reaches, `sym-lib-table` with the
`${KIPRJMOD}` symbol libraries it names (a `.kicad_sym` file or a folder of them) and the schematic's
drawing sheet. A schematic of another stem, a sheet file the hierarchy does not reach and a
`sym-lib-table` without that schematic are never copied. A sheet file outside the project folder or
missing is listed in `project.skipped` (`outside-root`, `missing`).
`--kicad-cli docker:<image>` runs the same copied project in a named local image; a missing image
returns `FEN-6001` with a `docker pull` hint.
The input is *built* when `.fenolite/meta.json` or `.fenolite/build.json` exists next to the board.

The stages run in this order (`STAGE_ORDER`); `--stages` selects a subset, and unselected stages are left
out. Without `--stages`, every stage runs except `roundtrip.rt2` (`DEFAULT_STAGES`), which costs two
re-saves and three DRC runs and is selected by name. `erc.kicad`, `drc.kicad`, `netlist.assignment_compare` and
`roundtrip.rt2` and `zone.fill` need `kicad-cli` (`ORACLE_STAGES`): selecting any of them runs the tool pre-flight.
`copper.clearance` needs no tool: `--stages copper.clearance` runs on a machine without KiCad.
`parity` needs none either for a project that `build` wrote.

| stage | runs on | evidence |
|---|---|---|
| `model.validate` | the board model (native) or the `.fenolite/` model (built) | the reader's level (native), `INFERRED` (built) |
| `erc.kicad` | `kicad-cli sch erc` on the copy set, built and native input alike; every violation becomes a located issue. Skipped with `no-schematic` when the project has no `<stem>.kicad_sch` | ERC report reader and oracle combined, `kicad-cli <version>`; `UNVERIFIED` without a report |
| `copper.clearance` | Fenolite's own exact check of shorts and clearance on the board model, native and built alike, with the rules of `<stem>.kicad_pro` and `<stem>.kicad_dru`; no tool runs | the lowest of the copper check (`INFERRED`), the board reader and the project and rules readers; `UNVERIFIED` when part of the copper or of the rules went unjudged |
| `zone.fill` | KiCad 10 refills a private copy of the project board; compares saved copper polygons per zone | refill evidence; `UNVERIFIED` when any zone is unfilled or stale |
| `drc.kicad` | `kicad-cli pcb drc` on the copy set, with the rules canary; every violation becomes a located issue | DRC report reader and oracle combined, `kicad-cli <version>`; `UNVERIFIED` without a report or with a rules issue |
| `parity` | Fenolite's own comparison of the board with `<stem>.kicad_sch`, and of symbol pins with footprint pads (`parity` below); no tool for a schematic that `build` wrote, else the schematic netlist of `kicad-cli` when another stage built the oracle | the lowest of the comparison (`INFERRED`, `H-K-PARITY-OWN`) and of the netlist it used |
| `netlist.assignment_compare` | the pad nets of the model (built input), of the re-read board, of `kicad-cli pcb export ipcd356` and, when the project has a schematic, of `kicad-cli sch export netlist`, compared as partitions | the lowest of the reader, the exports that were read and, on built input, `INFERRED`; `UNVERIFIED` without the board's export |
| `roundtrip` | RT1 of the board, native and built alike | the reader's level |
| `roundtrip.rt2` | opt-in: KiCad's DRC on the board and on Fenolite's re-dump of it gives the same violations | the DRC report reader, the oracle and the RT2 runs combined; `UNVERIFIED` when a report is missing |
| `render` | opt-in: runs only when `--stages` names it; plots the four views of `fenolite render` on the copy set and writes nothing | the plot evidence, `kicad-cli <version>`; `UNVERIFIED` when no view was produced |

Each `result.stages[]` entry is `{name, status, reason, evidence, summary}`. `status` is `ok` (ran, no
error issue), `errors` (ran, at least one) or `skipped`, with `reason` `native-input`, `read-refused`,
`cache-unreadable`, `no-schematic` (`erc.kicad` on a project without a schematic of the board's stem),
`unsupported-oracle`, `oracle-unsupported`, `netlist-unavailable` (`parity` on a schematic that Fenolite
does not read itself, in a run without `kicad-cli`) or `oracle-unstable` (two refill runs differ; never counted in the
envelope). A skipped stage carries `UNVERIFIED`. The envelope evidence is the lowest level of
the stages that ran and of those skipped for `read-refused` or `cache-unreadable`; `UNVERIFIED` when
none counts. `result.project` holds `board`, `built`, `files` and `skipped`, names relative to the
project folder. The `drc.kicad` summary holds `tool_version`, `canary`, `canary_reason`,
`canary_removed`, `violations`, `by_type`, `by_severity`, `unconnected`, `excluded`, `tool_writes`,
`violations_judged`, `parity`, `parity_judged` and `types`. Whenever a report exists, each violation,
unconnected item and parity entry is one issue and `violations_judged` is `true`; `types` maps each
emitted `kicad.drc.<type>` code to KiCad's raw type. The `erc.kicad` summary holds `tool_version`,
`sheets` (the sheets of the report), `violations`, `by_type`, `by_severity`, `excluded`,
`ignored_checks` (the checks the project sets to ignore; KiCad 10 lists them, KiCad 9 does not),
`types` and `tool_writes`. The `zone.fill` summary holds `tool_version`, `zones`, `current`, `unfilled` and `stale`. An unrouted board therefore exits 5: its unconnected items are errors. The `render` summary holds
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

**ERC.** `erc.kicad` is KiCad's own electrical rules check of the schematic, run on the copy set like
the DRC; it replaces the three rules of `erc.lite`, which are no stage of a KiCad check any more
(`--stages erc.lite` is a usage error). The stage needs the schematic and no board model, so it runs on
built and on native input, and also when Fenolite cannot read the board. The code is `kicad.erc.`
followed by KiCad's type with `_` as `-` (`pin_not_connected` gives `kicad.erc.pin-not-connected`); the
severity is the report's, which follows `erc.rule_severities` of the project; an excluded entry is
`info`. `where` lists the items in report order: `REF-PIN` for a pin, `REF` for a symbol, the text of a
label, and `<sheet>@<x>,<y>` (the sheet path and the position on the sheet in millimetres) for an item
that cannot be named, such as a wire, or a symbol of a sheet that is used twice when KiCad lists the
violation under the root sheet. A schematic `kicad-cli` cannot load gives `check.oracle-failed` on the
stage; the board is still judged by the other stages. The isolated `kicad-cli` sees no global library
table, as for footprints: a native project that takes its symbols from KiCad's global libraries gets one
`kicad.erc.lib-symbol-issues` warning per symbol, which says that the library was not found in this run
and nothing about the symbol. A built project carries its symbols (`lib/*.kicad_sym` and
`sym-lib-table`), so its report has none.

**Parity.** When the project has a schematic of the board's stem, the DRC run also asks KiCad to compare
the board with it (`--schematic-parity`). Each entry of that comparison is a `kicad.drc.<type>` finding
(`net_conflict`, `missing_footprint`, `extra_footprint`, `footprint_symbol_mismatch`, warnings by KiCad's
defaults), located like any other; `summary.parity` counts them and `summary.parity_judged` says that
the comparison was made. When KiCad cannot load the schematic it writes no report at all with that
option, so `check` runs the DRC again without it: the copper findings and their evidence stand, and
`kicad.drc.parity-unchecked` (warning) says that the board was not compared, with KiCad's own line.
A project without a schematic has `parity_judged` `false` and no such issue.

**The `parity` stage.** After `drc.kicad`, Fenolite compares the board with the schematic itself
(`checks.parity`; the command `parity` below describes the findings and the counts). It is skipped with
`no-schematic` without `<stem>.kicad_sch`, and with `netlist-unavailable` when the schematic holds wires,
sheets or power symbols and the run has no `kicad-cli` (the stage alone never starts the tool: it uses
the oracle that `drc.kicad`, `erc.kicad` or another oracle stage built).

- When `drc.kicad` judged parity in the same run, KiCad is the authority: the findings that KiCad also
  reports are not reported twice. They are compared with KiCad's entries by type and key, and each
  difference is one `parity.oracle-differs` (warning) that names the type, the key and the side that
  reports it. So Fenolite's comparison is checked against KiCad on every such run.
- Otherwise the findings are reported as `parity.*` issues, and an error among them fails the stage:
  `fenolite check DIR --stages parity` finds a board that disagrees with its schematic on a machine
  without KiCad.
- `parity.pin-without-pad` and `parity.pad-without-pin` are always reported.
- `summary` holds `netlist` (`own` or `oracle`), `compared` (whether KiCad's entries were compared),
  `differences`, and the counts of the command's `summary`.

**Assignment compare.** Elements are `REF-PIN`. Two sources agree when they put the same elements
together, whatever the nets are called; pads on no net form one class. The pairs are (`model`, `board`)
on built input and (`board`, `export`) always. When `<stem>.kicad_sch` lies beside the board, KiCad's
netlist of that schematic is a further source, `schematic`: it is compared with the model on built input
(`model`, `schematic`), and with the board on native input or when the model cannot be loaded
(`schematic`, `board`). So one source is the hub of each input and a wrong pin is reported once. A
schematic that `kicad-cli` cannot export gives `check.oracle-failed`, and the other pairs are still
compared. A difference names the element that moved. Elements only
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
| `check.cache-unreadable` | warning | `.fenolite/` cannot be loaded; `model.validate` is skipped |
| `check.footprint-unresolved` | error | a non-DNP component has no footprint reference or instance |
| `check.symbol-unresolved` | error | a built component that carries `fenolite.path` has no symbol reference; a board-only footprint added in KiCad, without that key, is not asked for one (`docs/lens.md`) |
| `check.rt1-failed` | error | RT1 failed; `where` is the first difference |
| `check.oracle-failed` | error | `kicad-cli` wrote no DRC report, ERC report or netlist export, or timed out (`retryable: true`) |
| `check.copy-skipped` | info | a file or folder the project names was left out of the copy |
| `kicad.drc.rules-not-loaded` | error (built), info (native) | the canary is `absent`, or a rules file has no project file next to it |
| `kicad.drc.rules-unchecked` | warning | the canary is `inconclusive`; the message names the reason |
| `kicad.drc.parity-unchecked` | warning | the DRC run was asked to compare the board with its schematic and KiCad did not do it; the copper findings stand |
| `kicad.drc.<type>` | error, warning, info | one per DRC violation, unconnected item or schematic parity entry; `<type>` comes from KiCad's type |
| `kicad.erc.<type>` | error, warning, info | one per ERC violation of the schematic; `<type>` comes from KiCad's type, and an excluded one is `info` |
| `parity.missing-footprint` | error | a component of the schematic has no footprint of its reference |
| `parity.extra-footprint` | error | a footprint has no component of its reference and is not marked as not in the schematic |
| `parity.duplicate-footprints` | error | a footprint has the reference of an earlier one; one per further footprint |
| `parity.net-conflict` | error | a pad's net differs from the net of its pin; a pad on no net and a pad that no pin names included |
| `parity.pin-without-pad` | error, warning | a pin number that no pad of the footprint has; an error when other pins are on its net |
| `parity.footprint-mismatch` | warning | the value, the library footprint or the do-not-populate and exclude-from-BOM flags differ |
| `parity.oracle-differs` | warning | Fenolite's comparison and KiCad's parity test of the same run disagree on one entry |
| `parity.pad-without-pin` | info | a numbered copper pad on no net that no pin names |
| `netlist.assignment-differs` | error | an element whose net block differs between the two sources of a pair |
| `netlist.uncovered` | info | elements that one side of a pair does not cover, per reason |
| `check.rt2-failed` | error | a violation whose count differs between the original and the re-dump |
| `check.rt2-unstable` | info | violations that differ between DRC runs of one file; the message says when RT2 is therefore not judged |
| `erc.lite.output-conflict` | warning | document input only: two or more driving outputs on one net |
| `erc.lite.power-undriven` | warning | document input only: a power input without a power output or a power interface |
| `erc.lite.floating-pin` | warning | document input only: a pin on no net that `no_connect` does not mark |
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
| `check.document-missing` | warning | document input: the project file lists a document that does not exist |
| `check.rta0-failed` | error | document input: a container copy lost or changed a storage or a stream; `where` is `<document>:<stream path>` |
| `check.rta1-failed` | error | document input: a stream's records differ after encoding and reading again; `where` is `<document>:<stream>#<record>` |
| `check.rta1-normalised` | info | document input: streams whose records are equal and whose encoded bytes differ |
| `check.rta2-failed` | error | document input: the built model and a reading of the written documents differ inside the written scope |
| `check.roundtrip-unjudged` | info | document input: a document whose level was not judged; the message names the reason |

`model.*` findings and reader codes pass through unchanged; among them `model.no-connect-on-net`
(error) names a pin that is marked as not connected and that a net lists, `model.duplicate-bus-index` (error) a bus that uses an index twice, and `model.body-height` (error) a component body whose height is below its standoff (`docs/design-model.md`, change c0043). Exit codes: 0 without an error issue, 5
with one, 2 for a usage error (ambiguous folder, unknown stage), 3 for a missing path or a board that
neither Fenolite nor KiCad reads (the envelope still holds the issues), and 6 when a stage that needs
`kicad-cli` is selected and it is missing (`FEN-6001`; the hint names `--stages model.validate,roundtrip`),
of an unsupported major, or older than the board's format (`FEN-6002`). Two runs on the same project
give the same stdout apart from `elapsed_ms`.

### check on Altium input

`fenolite check PATH` also checks the documents of a backend whose project is a set of documents
(change c0044): an Altium document or library (`.SchDoc`, `.PcbDoc`, `.SchLib`, `.PcbLib`), a project
file (`.PrjPcb`) or a folder that holds exactly one project file. This *document input* is looked for
before a KiCad board. It is read-only and runs no tool: no `kicad-cli` is looked for, and `--kicad-cli`
and `--timeout` are accepted and ignored. A folder that holds a KiCad project or board beside an Altium
project file is ambiguous, and a folder with Altium files and without exactly one project file is
refused (both `FEN-2001`, exit 2, the hint naming the candidates).

The stages are `DOCUMENT_STAGES`, in this order; `--stages` selects a subset (all by default), and a
name of the KiCad list such as `drc.kicad` is a usage error whose hint lists them.

| stage | what it does | evidence |
|---|---|---|
| `model.validate` | the `model.*` findings of the schematic reading and of the PCB reading (`where` starts with `schematic:` or `pcb:`), with the readers' own issues; on built input, those of the stored model | the readings; `INFERRED` on built input |
| `erc.lite` | the three ERC lite rules on the schematic reading (pin types and No ERC marks come from the sheets), or on the stored model of built input | `INFERRED` (`H-K-CHECK-ERC`, `H-A-VER-ERC`) |
| `copper.clearance` | the copper check of `check` on the PCB reading, built and native input alike: shorts, clearance and zone overlaps, with the pads of the Altium board frame and the Clearance rules the document holds (below) | the reading and the check (`H-A-DRC-SAME`); `UNVERIFIED` when part of the copper or of the rules was not judged |
| `parity` | the PCB reading against the schematic reading, as `parity` below: references, values, footprint names, nets, pins and pads | `INFERRED` (`H-K-PARITY-OWN`, `H-A-DRC-PARITY`) |
| `netlist.assignment_compare` | the partition compare of the pairs (`schematic`, `pcb`) on native input, (`model`, `schematic`) and (`model`, `pcb`) on built input; no export is needed | the lowest of the readings compared (`H-A-IMP-NETLIST`) |
| `roundtrip.rta0` | RT-A0 of every compound file of the set: a copy through the reader and the compound writer keeps every storage and stream | `EVIDENCE_RT_A0`; `UNVERIFIED` when a copy fails |
| `roundtrip.rta1` | RT-A1 of every document: every typed stream gives equal records after encoding and reading again | the reader's level per kind; `UNVERIFIED` when a stream fails |
| `roundtrip.rta2` | RT-A2 on built input: the stored model against the readings of the documents the build wrote, inside the written scope (`docs/altium.md`, "Round trips") | `INFERRED` (`H-A-VER-RTA2-2`) |

A stage is skipped with one of these reasons: `native-input` (`roundtrip.rta2` on files that no
Fenolite build wrote), `no-schematic` (`erc.lite` and `parity` without a schematic document),
`single-source` (`netlist.assignment_compare` without two sources; `copper.clearance` and `parity`
without a PCB document), `not-judged` (no document of the set can be judged
by the stage: a project file alone for `roundtrip.rta0`, a library alone for `model.validate`),
`read-refused` and `cache-unreadable`. Only the last two count in the envelope evidence. No stage
carries `ORACLE-VERIFIED`, `KICAD-VERIFIED` or `ALTIUM-VERIFIED`: only Fenolite reads the files.

- `result.project` holds `backend` (`altium`), `project` and `board` (names or `null`), `built`, `files`
  (the document names, sorted), `documents` (`{name, kind, role}`) and `skipped` (`{name, reason}` with
  the reason `missing` for a document the project file lists and that does not exist, also reported as
  `check.document-missing`). Names are relative to the project's folder. `input` describes the file that
  `PATH` names, or the project file for a folder, with its SHA-256 and read kind.
- The summary of a container stage holds `level`, `documents` (judged), `streams`, `failed` and
  `unjudged` (a count per reason: `too-large`, `writer-refused`, `not-a-container`, `read-refused`); RT-A1
  adds `records`, `bytes_equal` and `opaque_count`. The summary of `roundtrip.rta2` holds `level`, `holds`,
  `differences`, `compared` (the entity kinds compared per side) and `not_in_model` (per side, the count
  of each board kind that only the reading holds, which is not compared).
- **`copper.clearance` on a PCB document.** The codes and severities are those of the KiCad stage
  (`copper.short`, `copper.clearance`, `copper.zone-overlap`, `copper.clearance-unset`,
  `copper.rules-incomplete`, `copper.item-unsupported`); board-edge clearance is not part of the copper
  check on any backend. The summary is that of the KiCad stage plus `unpoured` and `zones_unjudged`.
  What the stage does not judge is said, and any of these lowers it to `UNVERIFIED`:
  - an **unpoured polygon** is no copper: `unpoured` counts them, with one `copper.item-unsupported`
    (a build writes its polygons unpoured, so a built board with zones says this until Altium repours);
  - an **internal plane** is drawn in negative: the lines and arcs without a net on its layer are no
    copper and are taken out, and one `copper.item-unsupported` (`where` is `plane`) counts the planes;
  - a **Clearance rule outside the rule table** (an object matrix, a layer scope) may govern any pair:
    `rules.opaque_clearance_rules` counts them, with one `copper.rules-incomplete`;
  - a **filled zone that no clearance applies to** is judged for shorts only: `zones_unjudged` counts
    them, with one `copper.rules-incomplete` (`where` is `zone`). A polygon holds no clearance of its
    own, so a pour is never judged against the model's default of 0.5 mm.
  A clearance of the document is judged 5 nm lower than written: the document counts in units of
  2.54 nm, and copper that is exactly its clearance apart reads up to 4 nm closer in nanometres.
- **`parity` on a project.** The summary is that of the KiCad stage with `netlist` = `own`,
  `compared` = `false` and `differences` = 0: no tool judges parity here. Two spellings are read as
  one, because they differ between the two documents of every project: the library of a footprint
  (only its name is compared), and the name of a net whose pads are the pads of one net of the board.
- A document that cannot be read gives one `check.read-refused` error whose `where` starts with its
  name. When it is the only document, the command exits 3 with the error's FEN code, as for a KiCad
  board; inside a project the other documents are still checked and the exit code is 5.
- Exit codes: 0 without an error issue, 5 with one, 2 for a usage error, 3 for a missing path or an
  unreadable single document, and never 6.

### Copper guard of an Altium build

`fenolite build --target altium` judges the copper of the PCB document it is about to write (change
c0088), on `--dry-run` and `--confirm` alike: the planned bytes are read back with the Altium reader,
the rules are those the document holds, and the copper check of `check` runs on the result. A
`copper.short` refuses the build (exit 5, nothing written). Every other copper error is reported as a
warning whose message ends with ` (reported, not refused: the Altium copper guard refuses shorts)`,
and the files are written. `--copper-check warn` reports the short as a warning too, with
` (copper guard in warn mode)`, and writes; there is no way to switch the guard off.
`result.copper_check` holds `mode`, `ran` (false without a PCB document), `shorts`, `clearance`,
`unpoured`, `rules` and `evidence`; the evidence is `UNVERIFIED` when the document holds unpoured
polygons, which the guard cannot judge. No file is read from disk and no tool runs.

## export

`fenolite export PATH --out DIR [--gerbers] [--drill] [--pos] [--ipcd356] [--all] [--altium-rul] [--manifest]
[--preset FILE] [--kicad-cli PATH] [--timeout SECONDS]` writes the fabrication files that `kicad-cli` produces from a
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

`--altium-rul` (change c0084) writes `DIR/<stem>.RUL`: the rules of the project's rules file
(`<stem>.kicad_dru`) as an Altium rule file, which Altium's PCB Rules editor imports. It runs no tool, so
alone it needs no `kicad-cli` (`tool_version` is `null` and the evidence has no oracle), and `--all`
does not select it. A rule is written exactly or not at all (`docs/altium.md`, "Rules"):
`result.rules` holds `written` (`kind`, `selector`, `rule`) and `not_lowered` (`kind`, `selector`,
`reason`). When the rules file is missing or no rule has an exact Altium form, `export.failed` with
`where` `altium-rul` is reported and nothing is planned. The artefact's kind is `altium-rul`; its
manifest entry names `fenolite <version>` as its tool and the level of the rule map (`INFERRED`), and
an envelope that holds it is `INFERRED`.
`--preset FILE` applies your fabrication options from a TOML file (`docs/exports.md`, "Presets"): it
is read before any run, and each of its keys replaces one option of the table above. A preset that is
not TOML, has another `schema`, or holds an unknown table, key or value exits 3 with `FEN-3004`,
naming the `table.key`; a preset that cannot be read exits 3 with `FEN-3001`. With `pos.format`, the
position file ends in `.csv`, `.pos` or `.gbr`. `result.preset` holds `file` (the name as given) and
`sha256`, or `null`; with a preset the evidence also names `H-K-EXPORT-OPTIONS`.
`--manifest` adds the files to `DIR/fenolite-artifacts.json` (`schemas/fenolite.artifacts.v0.json`;
`docs/exports.md`): the entries of an existing manifest are kept, those of equal paths replaced, each
new entry `generated` with `from` holding the board's SHA-256 and `tool` `kicad-cli <version>`. A file
there that is not a manifest gives `manifest.unreadable` (see "manifest"), and nothing is planned.
`result` holds `board`, `out`, `kinds`, `artifacts` (`path`, `kind`, `layer`, `bytes`, `sha256`,
`content_sha256`; sorted by path), `tool_version` and `tool_writes` (files the tool wrote outside its
output folders, such as `<stem>.kicad_prl`). When a kind fails, nothing is planned or written, so a
folder never holds a partial set.

| code | severity | when |
|---|---|---|
| `export.failed` | error | a kind's run exited non-zero, wrote no file or timed out (`retryable: true`); `where` is the kind. For `altium-rul`: the rules file cannot be read, or no rule has an exact Altium form |
| `export.kind-unavailable` | error | the running `kicad-cli` major cannot export the kind; no tool run |

Exit codes: 0 when the files are planned or written, 4 without `--dry-run` or `--confirm`, 5 with an
issue above, 2 for a usage error, 3 for a missing path or a board Fenolite cannot read, 6 when
`kicad-cli` is missing (`FEN-6001`), of an unsupported major or older than the board's format
(`FEN-6002`). The evidence is `exports.EVIDENCE` with the oracle `kicad-cli <version>`: Fenolite claims
the file set and the hashes, and the content of each file is KiCad's.

## render

`fenolite render PATH --out DIR [--svg] [--png] [--width PX] [--height PX] [--manifest]
[--kicad-cli PATH] [--timeout SECONDS]` writes review views of the board, through `kicad-cli` on the same copy set and
with the same protocol and tool errors as `export`. `--svg` plots `front.svg` (`F.Cu`, `F.SilkS`,
`F.Fab`, `Edge.Cuts`) and `back.svg` (the back layers, mirrored) with `pcb export svg --mode-single`;
`--png` renders `top.png` and `bottom.png` with `pcb render`, at most `--width` by `--height` pixels
(defaults 1600 and 1200, each from 64 to 8192). A call with neither flag exits 2. `result` holds `board`,
`out`, `views` (`path`, `kind`, `bytes`, `sha256`; sorted by path) and `tool_version`. `--manifest`
merges the views that were produced into `DIR/fenolite-artifacts.json` as `export` does, each with
the kind `render`; a view that failed has no entry.

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
`input.path` is the file name. `.kicad_pro`, `.kicad_dru` and every other file that no backend reads exit 2
(`FEN-2001`); such a file beginning with the compound-file signature has a hint to use `--streams`. A read
error exits 3 with its code.

An Altium file (`.PcbDoc`, `.SchDoc`, `.PcbLib`, `.SchLib`, `.PrjPcb`; change c0044) is summarised from
the Altium readers, with the same keys: `kind` is its read kind (`altium_pcbdoc`,
`altium_schdoc_binary`, `altium_schdoc_ascii`, `altium_pcblib`, `altium_schlib`, `altium_prjpcb`),
`format_version` the version text of its header (`6.0`, `5.0`; `null` for a project file), `major`,
`generator` and `generator_version` are `null`, and `status` is `supported`. `counts` holds, for a PCB
document, the board counts plus `components` and `rules`; for a schematic `components`, `pins`, `nets`,
`wires`, `labels`, `power_ports`, `ports`, `sheet_symbols` and `no_connects`; for a schematic library
`symbols`, `units` and `pins`; for a PCB library `footprints`, `pads` and `graphics`; for a project file
`documents`, `missing` and one count per document role. `opaque_count` is that of the file's RT-A1
verdict (records kept without a typed class plus streams kept whole), `result.streams` holds the
stream counts `typed` and `opaque`, and a project file adds `result.documents` (`{name, kind, role,
exists}`). The envelope evidence is that of the file's reading.

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

`fenolite template build SPEC --target kicad|altium -o OUT [--size NAME] [--altium-format binary|ascii]`
builds a drawing sheet (`.kicad_wks`, or a `.SchDot` for the target `altium`, below) from a
`*.sheet.toml` specification and runs no tool. The actions are `build` and `import` ("template import"
below); `--target` and `-o`/`--out`
are required, and the targets are `kicad` and, for `build`, `altium`. It is a mutating command: without `--confirm` it exits 4
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
| 2 | `FEN-2001` | a missing `--target` or `-o`, a target other than `kicad` and `altium`, `--size` or `--altium-format` without `build --target altium`, or a size the specification does not list |
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

With `--target altium` (change c0087) `build` writes an Altium sheet template (`.SchDot`) instead: one
write of kind `altium_schdot`, a schematic document without components that holds the frame, the zones and
the title block as drawn lines and texts on a custom sheet of the paper's size. A template has one size:
`--size NAME` picks it among the sizes the specification lists (default: the first; another name is a usage
error), and `--altium-format {binary,ascii}` picks the form (default `binary`). Both options are usage
errors with `--target kicad` and with the action `import`. `result` holds `sheet`, `target`, `drawn` (for
the one size) and `output` as above, no `kicad_version`, and `altium`: `format`, `size`, `width` and
`height` (nm), `lines`, `texts`, `parameters` (the names of the sheet parameter records) and `strings` (the
special strings written). The evidence is `INFERRED` (`H-A-SCHDOT-READBACK`, `H-A-SCHDOT-OPEN`,
`H-A-SCHDOT-STRINGS`): Fenolite's own import reads the template back, and Altium has not opened it. What the
template keeps of the sheet, and what is a loss that needs `--allow-lossy` (`FEN-7001`, exit 7), is in
`docs/sheet-templates.md`, "Building an Altium sheet template".

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

`fenolite bom PATH [--source kicad|model] [--template FILE] [--out FILE] [--manifest] [--against OTHER]
[--kicad-cli PATH] [--timeout SECONDS]` gives the bill
of materials of the project `PATH` names (resolved as for `check`) as a neutral table, rendered through a
column template that the user writes (`docs/assembly.md`). Fenolite ships no template of any assembly
service; without `--template` the built-in default applies, whose column names are Fenolite's field names.

- `--source kicad`, the default, is the bill that `kicad-cli` exports from the project's schematic,
  `<stem>.kicad_sch` next to the board: `sch export bom` with one row per reference, run on a copy of the
  schematic, of the project file and of every other `.kicad_sch` under the project folder. Fenolite reads
  the rows back and groups them itself. `--kicad-cli` and `--timeout` (300 s) are as for `export`. A
  project without that schematic exits 3 with `FEN-3001` and a hint that names `--source model`: the
  command never falls back to the other source.
- `--source model` lists the parts of the `.fenolite/` model of a built project, or of the board read for
  any other project. It runs no tool.
- `--against OTHER` reads `OTHER` as `PATH`, with the same source and template, and adds `result.changes`:
  what changed from `OTHER` to `PATH`.

`result` holds `source`, `template` (the file name without its folder, or `default`), `columns` (the
column names), `lines` (one object per line, keyed by column name, with the text the file would hold),
`counts` (`parts`, `lines`, `dnp`, and `left_out`, which is `null` for the `kicad` source: KiCad does not
say what it leaves off a bill) and, with `--against`, `changes` (each `key`, the values of
the grouping fields; `change`, one of `added`, `removed`, `changed`; `a_refs`, the references in `OTHER`;
`b_refs`, those in `PATH`). No value holds a date or an absolute path, and two runs on an unchanged
project give the same output apart from `elapsed_ms`.

With either source, a line is all DNP or all fitted: a DNP part never shares a line with a fitted part,
whether or not the template's `group_by` names `dnp`. Lines are in the natural order of their first
reference, DNP lines included. The `key` of a line of DNP parts ends with one more value, `DNP`, when
`group_by` is not empty and does not name `dnp`.

It is a mutating command that writes only with `--out FILE`: the plan then holds one write of kind `bom`,
the CSV bytes of the table, and the mutation protocol applies (4 without `--dry-run` or `--confirm`).
Without `--out` nothing is planned and the exit code is 0. The project folder never changes.
`--manifest` (for `bom` and for `pnp`) also plans `fenolite-artifacts.json` in the folder of `FILE`,
merged as `export` merges it, with one entry of kind `bom` or `pnp`: `tool` `fenolite <version>`,
`from` the board's SHA-256, `evidence` the level of the envelope. Without `--out` it exits 2
(`FEN-2001`).

| code | severity | when |
|---|---|---|
| `assembly.template-invalid` | error | the template has an unknown table or key, an unknown field, two columns with one name, an empty column list or a value outside its set; one issue per problem, `where` is the key path; the command exits 3 with `FEN-3004` |
| `bom.property-missing` | info | a column names a `property:<NAME>` that no part has; the column is empty; `where` is the column name |
| `bom.field-unsupported` | error | with the `kicad` source, the template names a property that has a comma in its name, which cannot be asked of `kicad-cli`; the command exits 3 with `FEN-3004`; `--source model` reads it |

Exit codes: 0, 4 as above, 2 for a usage error, 3 for a missing path, a template that cannot be read
(`FEN-3001`) or is invalid (`FEN-3004`), or a `.fenolite/` model that cannot be read (`FEN-3004`). With the
`kicad` source: 3 without a schematic (`FEN-3001`), when `kicad-cli` writes no bill or times out, or when
its bill does not have the header that was asked for (`FEN-3004`); 6 when `kicad-cli` is missing
(`FEN-6001`), of an unsupported major or older than the board's format (`FEN-6002`).

The evidence of the `kicad` source is `bom.EVIDENCE_KICAD` (`H-K-BOM-CSV`) with the oracle
`kicad-cli <version>`. The evidence of the `model` source is `bom.EVIDENCE_MODEL` (`H-K-BOM-MODEL`) for a
project that Fenolite built and that has its schematic, because only there were the two sources
compared; for any other input it is `INFERRED`, combined with the evidence of the board read.

## pnp

`fenolite pnp PATH [--template FILE] [--side top|bottom|both] [--out FILE] [--manifest]` gives the placement
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
## diff

`fenolite diff A B [--view model|tree|records] [--ext]` lists the differences between two inputs. It writes
nothing and runs no tool. A difference is a result, not a finding: the exit code is 0 whether or not the
inputs differ, and `result.equal` says it.

`A` and `B` are each a KiCad board, a schematic, a footprint file, a symbol library (file or
`.kicad_symdir` folder), or a folder that holds `.fenolite/meta.json` (the built model). Both must be of one family: two designs
(boards and built models, in any mix), two libraries, or two schematics. A schematic is one file: a
sub-sheet is compared by naming its own file.

An Altium document, library or project file, or a folder that holds exactly one Altium project file, is
an input too (change c0044): it is read into the model by the Altium backend, so the model view compares
it with any other design or library, a KiCad board included. Its `kind` is its read kind
(`altium_pcbdoc`, `altium_schdoc_ascii`, …).

- **`--view model`** (the default) compares the two models entity by entity. Ids, KiCad uuids and
  provenance never take part, so a rebuilt board equals itself.
  - Entities with a name are matched by it: `component` by reference, `net` by name (a net without a
    name by its sorted members), `netclass`, `layer` and `interface` by name, `module` by path,
    `no_connect` by `REF-PIN`, `footprint` by the reference of its component, `pad` by `REF-NUMBER`
    (`#<k>` for the k-th further pad of one number), and in a library `footprint_def` and `symbol_def` by
    `<library>:<name>`. An entity on one side only is `removed` (only in `A`) or `added` (only in `B`),
    with the path `/<kind>/<key>`; a field that differs is `changed`, with `/<kind>/<key>/<field>`.
  - Copper and graphics (`track`, `arc`, `via`, `zone`, `keepout`, `text`, `graphic`, `hole`, `rule`,
    `stack_layer`) have no name: two of them match when every field is equal. A moved track is therefore
    one `removed` and one `added`, with the path `/<kind>/<n>`.
  - In a schematic, `symbol` is matched by `<ref>#<unit>`, `sheet_ref` by its name and `lib_symbol` (an
    embedded symbol) by its name; `label` and `no_connect_flag` have no name and match by content. The
    paper, the title block and the pages are `/sheet/<field>`. Wires, junctions and buses are not
    modelled, so only `--ext` and the tree view see them.
  - The values a design holds once (`outline`, `finish`, `sheet`, `title_block`) are `/design/<field>`.
    The design's name is not compared.
  - A key is one path segment: `/` in a name is written `~1` and `~` is written `~0`, so the net `/SDA`
    is `/net/~1SDA`.
  - A moved footprint is exactly one change, `/footprint/<ref>/position`: pad positions are stored
    relative to their footprint.
  - `--ext` also compares the content Fenolite keeps without modelling it, as a hash per entity (`ext`).
- **`--view tree`** compares the parsed trees of two KiCad S-expression files of one kind (`.kicad_pcb`,
  `.kicad_mod`, `.kicad_sch`, `.kicad_sym`, `.kicad_wks`). It answers "did anything at all change",
  unmodelled content included, without a list: `result.first_difference` is the locator of the first
  node that differs (or `null`) and `result.heads` gives, per root child head whose count differs, its
  count in `a` and in `b`.

- **`--view records`** compares two Altium files of one read kind stream by stream, with the readers'
  own record codecs. Streams are matched by path: a stream on one side only is `removed` or `added`
  at `/<stream>`, and a stream the reader keeps whole whose bytes differ is `changed` at `/<stream>`,
  with the SHA-256 of each side. The records of a typed stream are aligned by their longest common
  subsequence, so one inserted record is one `added` and no later record is reported: a record on one
  side only is `removed` or `added` at `/<stream>#<index>` (its own side's index, the stream header
  being record 0), and two unaligned records at the same place of one record kind are one `changed`
  at `/<stream>#<index of A>`. `a` and `b` name the record kind and the keys or fields that differ; a
  value is shown only when its text is at most 80 bytes, else as its length and SHA-256. `summary` is
  per stream, and the changes are in stream and record order. The two forms of a schematic are two
  kinds: this view converts nothing. Any other pair of inputs is a usage error whose hint names
  `--view model`, and so is `--view tree` on an Altium file.

`result` holds `view`, `equal`, `a` and `b` (each `{path, kind}`; `kind` is `kicad_pcb`, `kicad_mod`,
`kicad_sym`, `kicad_sch`, `fenolite_model` or an Altium read kind), `summary` (per entity kind, or per stream in the
records view: `added`, `removed`, `changed`),
`differences` (objects `{path, change, a, b}`, sorted by path; `a` and `b` are compact JSON texts),
`total` and `truncated`. `differences` is a paged list with a default limit of 200 (see "Paged
results"). `issues` holds only the readers' issues, those of `A` first; `input` describes `A`. The
evidence is the lowest of the two readings; a built model counts as `INFERRED`.

| exit | error | when |
|---|---|---|
| 0 | none | the inputs were compared, equal or not |
| 2 | `FEN-2001` | an input that nothing reads, inputs of two families or two kinds, a folder in the tree view |
| 3 | `FEN-3001` | an input does not exist |
| 3 | `FEN-3002`, `FEN-3003`, `FEN-3004` | an input cannot be read |

## roundtrip

`fenolite roundtrip PATH [--level rt0|rt1|rt2] [--kicad-cli PATH] [--timeout SECONDS]` says up to which
level Fenolite reads a KiCad file and writes it back without loss. Run it before editing a file that
Fenolite did not write. It writes nothing; RT2 runs `kicad-cli` on copies.

| level | what holds |
|---|---|
| `rt0` | parsing the file, printing it and parsing it again gives an equal tree (any of the five S-expression kinds) |
| `rt1` (default) | RT0, and the backend's same-version rebuild of a board or of a schematic gives an equal tree, an equal model and the same unmodelled content. For a kind without a rebuild `result.rt1` is `not-applicable` and the level reached is `rt0` |
| `rt2` | RT1, and KiCad's DRC gives the same violations for the board and for Fenolite's re-dump of it; when the project has a schematic of the board's stem, KiCad's ERC also gives the same violations for the project and for Fenolite's re-dump of its sheets. `PATH` may then be a project file or folder |

`result` holds `kind`, `level` (the highest level that holds, or `none`), and per level asked an object
`{passed, difference}`, with `opaque_count` for `rt1`, and for `rt2` also `judged`, `normalised`, `runs`,
`before`, `after`, `unstable` and `differences`. A level after a failed one is `not-run`. When KiCad does
not repeat its own DRC report on a board, RT2 is not judged: `judged` is `false`, the level stays `rt1`
and nothing fails.

| code | severity | when |
|---|---|---|
| `roundtrip.failed` | error | a level does not hold; `where` is the first difference |

`check.oracle-failed` and `check.rt2-unstable` of the RT2 stage pass through.

For a project with a schematic, `result.rt2.schematic` holds `passed`, `difference`, `judged`,
`exact`, `violations`, `violations_redump`, `redumped` and `kept` (the sheet files re-dumped, and
those Fenolite cannot read, which stay as they are). KiCad's ERC does not repeat its report item by
item: for one violation it can name another of the pins or labels involved in each run. The runs are
therefore compared by the sheet, type, severity and exclusion of every violation, counts included,
and not by the items. When the two runs on the project as it is differ in these, the schematic is not
judged. When the re-dump differs from the first run in these, RT2 fails; `difference` names the type,
the sheet and the two counts. `exact` is `true` when the items of the three reports agree too; it is
information and changes no verdict. The level is `rt2` only when
the board's RT2 and the schematic's both hold; a schematic that is not judged leaves it at `rt1`
without an error. No ERC report at all gives `check.oracle-failed`.

| exit | error | when |
|---|---|---|
| 0 | none | every level asked holds, or RT2 is not judged |
| 2 | `FEN-2001` | a file of another kind, or `--level rt2` on a file that is not a board |
| 3 | `FEN-3001`, `FEN-3004` | the file is missing or does not parse |
| 5 | `FEN-5001` | a level failed |
| 6 | `FEN-6001`, `FEN-6002` | `--level rt2` without a supported `kicad-cli` |

## fmt

`fenolite fmt PATH [--check]` gives a KiCad S-expression file (`.kicad_pcb`, `.kicad_mod`, `.kicad_sch`,
`.kicad_sym`, `.kicad_wks`) Fenolite's canonical print: the file is parsed and printed again, so its tree
does not change, only its layout. Use it for small diffs under version control. It is not KiCad's own
formatter: KiCad may lay the file out again when it saves it, and the tree is still the same.

- `--check` writes nothing: `result.formatted` says whether the file already is its canonical print, and
  a file that is not gives the error `fmt.would-change` and exit 5.
- Without `--check` it is a mutating command: one planned write of the canonical text when the file
  differs (`--dry-run` shows it, `--confirm` writes it and keeps a `.bak`), and no plan and exit 0 when
  the file is already canonical.

`result` holds `kind`, `formatted`, `lines` (of the file) and `first_difference` (the number of the
first line that differs, or `null`). Formatting a formatted file changes nothing: this fixed point is
tested on the whole corpus (`H-K-FMT-IDEMPOTENT`, `docs/evidence/kicad-fmt-identity.md`).

| code | severity | when |
|---|---|---|
| `fmt.would-change` | error | `--check` on a file that is not canonical; `where` is `<file>:<line>` |

| exit | error | when |
|---|---|---|
| 0 | none | the file is canonical, a dry run, or a confirmed write |
| 2 | `FEN-2001` | a `.kicad_pro` (JSON, kept byte for byte), a `.kicad_dru`, or any other file |
| 3 | `FEN-3001`, `FEN-3004` | the file is missing or does not parse |
| 4 | `FEN-4001` | the file would change and neither `--dry-run` nor `--confirm` was given |
| 5 | `FEN-5001` | `--check` on a file that would change |
| 7 | `FEN-7001` | the tree holds comments below the root, which the printer would lose |

## explain

`fenolite explain CODE` says what an error code (`FEN-NNNN`) or an issue code (`check.rt1-failed`) means
and what to do about it. The texts are packaged with Fenolite, so the command needs no file and no
network. `result` holds `code`, `kind` (`error` or `issue`), `exit_code` (for an error code, else
`null`), `severities` (for an issue code), `meaning`, `fix`, `see` (a section of this page) and `family`.

A code that a tool's own type completes, such as `kicad.drc.clearance`, is explained by the entry of its
family, and `result.family` is then `kicad.drc.*`. An unknown code exits 2 with `FEN-2001`, and the hint
names the three closest codes. A test keeps the table complete: every code of every issue-code table and
of the error registry has an entry.

## restore

`fenolite restore RECEIPT [--in DIR]` puts back the backups of one confirmed write. `RECEIPT` is a file
that holds the envelope of that write (or only its `receipt` object), or `-` to read it from stdin;
`--in` is the working directory that write ran in (default: the current one). The receipt is the undo
token: keep the envelope of a write you may want to undo.

```
fenolite build design.py --out build --confirm --json > last-write.json
fenolite restore last-write.json --dry-run --json
fenolite restore last-write.json --confirm --json
```

- Nothing is restored unless every file of `written` still has the SHA-256 the write gave it. One changed
  file refuses the whole restore: a half-undone build is worse than none.
- For every path of `backup`, the content of the `.bak` file is written back to its file.
- **`restore` deletes nothing.** A file the write created, or wrote with `--no-backup`, stays as it is and
  is reported with `restore.kept`.
- It is itself a mutating command (`--dry-run`, `--confirm`): the content it replaces becomes the new
  `.bak`, so the receipt of a restore undoes the restore.
- A receipt path that is absolute or leaves the folder is refused as malformed.

`result` holds `id` (of the receipt read), `restored` and `kept` (paths), and `changed` when refused.

| code | severity | when |
|---|---|---|
| `restore.changed-since` | error | a written file is missing or changed since the write; nothing is planned |
| `restore.backup-missing` | error | a backup of the receipt does not exist; nothing is planned |
| `restore.nothing` | error | the receipt kept no backup |
| `restore.kept` | info | a written file without a backup stays as it is |

| exit | error | when |
|---|---|---|
| 0 | none | a dry run, or a confirmed restore |
| 3 | `FEN-3001`, `FEN-3004` | the receipt or `--in` is missing, or the receipt is not one |
| 4 | `FEN-4001` | neither `--dry-run` nor `--confirm` |
| 5 | `FEN-5001` | the restore was refused; read `issues` |

## Receipt identity

The `receipt` of a confirmed write holds, beside `written` and `backup`:

- `id`: the first 16 hex digits of the SHA-256 of the compact JSON, with sorted keys, of
  `{"backup": …, "written": …}`. No clock, seed or folder takes part: equal writes have equal ids.
- `undo`: `fenolite restore - --confirm` when a backup was kept (pipe the envelope to it), else `null`.

Both fields are optional in `schemas/fenolite.envelope.v0.json`, so an envelope written before they
existed still validates.

## Paged results

`--limit N` and `--cursor TOKEN` cut the main list of a command to one page. `fenolite capabilities`
lists, per command, `paged` (the list: a path in `result`, or `issues`) and `default_limit`.

| command | paged list | default limit |
|---|---|---|
| `check`, `analyze` | `issues` | none |
| `diff` | `result.differences` | 200 |
| `manifest` | `result.differences` with `--verify`, else `result.artifacts` | none |
| `net` | `result.nets`, or `result.net.pads` with a net name | none |
| `region` | `result.items` | none |
| `neighbors` | `result.neighbors` | none |

- With a limit in force, the list holds the items `offset` to `offset + limit - 1` and `result.page` is
  `{path, limit, offset, total, next}`: `total` is the length of the whole list and `next` the cursor of
  the following page, or `null` on the last. Without a limit the list is whole and `page` is absent.
- A cursor is `<offset>.<digest>`, the digest being the first 8 hex digits of the SHA-256 of the compact
  JSON, with sorted keys, of the whole list. Paging keeps no state: every call computes the whole result
  and cuts it. Pass `--cursor` with the same `--limit` as the page before.
- **The exit code, `ok`, the error on stderr and every count in `result` come from the whole result,
  never from the page.**
- `--fields` applies after paging and can keep `page`.

| exit | error | when |
|---|---|---|
| 2 | `FEN-2001` | `--limit` below 1, or on a command without a paged list |
| 2 | `FEN-2001` | a malformed cursor, an offset past the end, a cursor without a limit in force |
| 2 | `FEN-2001` | the result changed since the cursor was issued: start again without `--cursor` |

## Concise output

`--format concise` keeps, for each issue code, the first issue in the envelope's order and drops the
others, and adds `result.issues_summary`: one object per code, sorted by code, with `code`, `count` and
`by_severity`. An agent that fixes one problem per iteration reads one issue per kind and the counts.
Paging of `issues` applies to the list that `concise` leaves; `ok` and the exit code come from the whole
result. `--format detailed` is the default and changes nothing.

## net

`fenolite net PATH [NAME]` describes the nets of a board from the board model; `PATH` is a board, a
project file or a project folder. It runs no tool. It says what a net holds, never whether it is
connected: missing connections are KiCad's `unconnected_items` (`fenolite check`).

- Without `NAME`, `result.nets` holds one row per net, sorted by name: `name`, `class`, `pads`, `tracks`
  (tracks and arcs), `vias`, `zones` and `length`, the summed centre-line length of its tracks and arcs.
- With `NAME`, `result.net` holds `name`, `class`, `pads` (each `where` as `REF-PIN`, `layers`,
  `position`), `copper` (per layer: `tracks`, `arcs`, `length`), `vias` (`position`, `layers`,
  `diameter`, `drill`), `zones` (`name`, `layers`, `filled`) and `box`, the bounding box of its pads and
  copper (`{x0, y0, x1, y1}`, or `null`).

Every length is integer nanometres, in the frame of the board file. An unknown net exits 2 with
`FEN-2001`, and the hint names the closest net names. The evidence is the lowest of the board reader
and of the board frame.

## netlist

`fenolite netlist PATH [--source kicad|fenolite] [--min-pins N] [--kicad-cli PATH] [--timeout SECONDS]`
lists the components and nets of a KiCad project's schematic. It writes nothing. `PATH` is a
`.kicad_sch`, or a board, a project file or a project folder resolved as for `check`, whose schematic is
`<stem>.kicad_sch` beside the board.

- **`--source kicad`** (the default) runs `kicad-cli sch export netlist --format kicadsexpr` on copies of
  the schematic, the sheets it names and the project's copy set, and reads the export. It answers for
  every schematic KiCad loads: wires, buses, hierarchies and power symbols are KiCad's to resolve.
- **`--source fenolite`** reads the root sheet itself and runs no tool. It answers only for a sheet that
  `build` generated (symbols, global labels on pin ends, no-connect flags, Fenolite's power flags), where
  the nets follow from the points alone (`docs/schematic.md`, "The netlist of a generated sheet"). Any
  other sheet exits 7 with `FEN-7001`, and `issues` holds one `kicad.sch.netlist-unsupported` per reason,
  the reason first in the message: `wire`, `label-kind`, `sheet`, `undefined-symbol`, `label-off-pin`,
  `two-names`, `shared-point`, `frame` or `hidden-power`.

`result` holds:

- `schematic`, the file name, and `source`;
- `components`, sorted by the natural order of the reference: `ref`, `value`, `footprint` and
  `properties` (the fields other than the reference and the value);
- `nets`, sorted by name: `name`, `class` (the net class KiCad reports; `""` from the source
  `fenolite`, which does not read the project file), `unconnected` and `pins`, each `{ref, pin, type}`,
  sorted by reference and pin. `type` is the electrical type of the pin, followed by `+no_connect` under
  a no-connect flag. `unconnected` is true for a net of one pin that KiCad named `unconnected-(…)`;
- `counts`: `components`, `nets`, `pins`, `unconnected` and `below_min_pins`, over every net.

`--min-pins N` leaves the nets with fewer than `N` pins out of `nets` and counts them in
`counts.below_min_pins`; `--min-pins 2` hides the nets of single pins. The default is 1.

Nothing of a run reaches the output: no date, no temporary path and no absolute path, so two runs on
unchanged files print the same document apart from `elapsed_ms`.

Exit codes: 0; 2 for a usage error, an ambiguous folder or `--min-pins` below 1 (`FEN-2001`); 3 for a
missing path or a project without a schematic (`FEN-3001`), and for a schematic that `kicad-cli` cannot
load or an export Fenolite cannot read (`FEN-3004`, with the tool's first line); 6 when `--source kicad`
finds no `kicad-cli` (`FEN-6001`; the hint names `--source fenolite`), when it is unsupported
(`FEN-6002`) or when it times out (`FEN-6001`, retryable); 7 for `--source fenolite` on a sheet outside
its grammar. The evidence is that of the source: the export reader's and the oracle's, with
`kicad-cli <version>` as the oracle, or that of Fenolite's own netlist (`H-K-NETLIST-OWN`).
## parity

`fenolite parity PATH [--netlist auto|own|kicad] [--kicad-cli PATH] [--timeout SECONDS]` compares the
board of a KiCad project with its schematic, and the pins of each symbol with the pads of its footprint
(`fenolite.checks.parity`). It writes nothing. `PATH` is a board, a project file or a project folder
resolved as for `check`; the schematic is `<stem>.kicad_sch` beside the board, with every sheet it names.

`PATH` may also be an Altium project file, a project folder, or a PCB document beside the one project
file that lists it (change c0088). The board is then the project's PCB document and the schematic side
comes from its schematic documents, read by Fenolite: no tool runs, `netlist` is `own`, `--netlist
kicad` exits 2, and `schematic` names the first schematic document. The library of a footprint and the
name of a net whose pads agree are not compared ("check on Altium input"). A project without a PCB
document or without a schematic document exits 3 (`FEN-3001`).

- **Matching.** Components and footprints are matched by reference only. A symbol that is not on the
  board and a reference that starts with `#` are no components. A footprint marked as not in the
  schematic is never extra. Of several footprints of one reference, the first on the board is compared.
- **Nets** come from a netlist of the schematic. `--netlist auto` (the default) reads a schematic that
  `build` generated itself, without any tool, and runs `kicad-cli sch export netlist` on copies for any
  other schematic; `own` never runs a tool and exits 7 (`FEN-7001`, with the reasons of
  `kicad.sch.netlist-unsupported`) outside that grammar; `kicad` always runs the tool.
- **Net names** are compared as KiCad's parity test compares them: `{slash}` and `/` are one spelling,
  and a further pad of a pin on no net may carry that pin's net name followed by `_<n>`.

`result` holds `board` and `schematic` (file names), `netlist` (`own` or `kicad`), `findings` and
`summary`. Each finding is `{code, severity, key, field, schematic, board}`: `key` is the reference, or
`REF-PAD` for a pad or a pin; `field` is `value`, `footprint` or `attributes` for a
`parity.footprint-mismatch`; `schematic` and `board` are the two values. `issues` holds one issue per
finding, `where` its key. The codes are those of `check` above; the first five are KiCad's parity types
`missing_footprint`, `extra_footprint`, `duplicate_footprints`, `footprint_symbol_mismatch` and
`net_conflict`, and KiCad reports a pin without a pad as a `net_conflict` of the footprint.

`summary` holds the number of findings per code and three derived counts: `refs_one_side` (missing plus
extra footprints), `connections_missing` (pads on no net whose pin has one) and `nets_split` (schematic
nets whose pads are on another board net, or on more than one).

Exit codes: 0; 5 when a finding is an error; 2 for a usage error or an ambiguous folder; 3 for a missing
path or a project without a schematic (`FEN-3001`) and for a schematic that `kicad-cli` cannot load
(`FEN-3004`); 6 when the nets must come from `kicad-cli` and it is missing (`FEN-6001`), unsupported
(`FEN-6002`) or timed out; 7 for `--netlist own` on a schematic outside the grammar. The evidence is
`INFERRED`: the comparison agrees with KiCad's parity test on the public demos of both majors
(`H-K-PARITY-OWN`), which are not every project. With `kicad-cli` installed, `fenolite check` gives
KiCad's own verdict and checks this comparison against it.

## region

`fenolite region PATH --box X1,Y1,X2,Y2 [--layer NAME] [--kinds a,b]` lists what a rectangle of the board
holds. `--box` is two corners, in any order, as four lengths with units (`10mm,5mm,30mm,20mm`), in the
frame of the board file; the rectangle is closed.

`result.items` holds objects `{kind, where, net, layer, box}`, sorted by kind (`footprint`, `pad`,
`track`, `arc`, `via`, `zone`, `text`) and then by `where`; `result` also holds `box`, `layer` and
`counts` per kind.

| kind | touches the rectangle when | `where` |
|---|---|---|
| `pad`, `track`, `arc`, `via` | the exact gap between its copper and the rectangle is 0 (an arc within 1 µm) | `REF-PIN` for a pad, else the item's locator in the file |
| `footprint` | the bounding box of its courtyard on its own side meets it | the reference |
| `zone` | the bounding box of its outline meets it, so a zone may be listed whose copper does not reach it | the item's locator |
| `text` | its position lies in it | the item's locator |

With `--layer`, only items on that layer are listed; a footprint counts for the copper layer of its
side, and an item on several layers is listed once. A length without a unit, a rectangle without area and
an unknown kind exit 2 with `FEN-2001`.

## neighbors

`fenolite neighbors PATH REF [--radius L]` lists the footprints near one part. `--radius` is a length
with a unit, 5 mm by default.

`result.part` holds `ref`, `position`, `rotation`, `side` and `box` (of its courtyard); `result.radius`
is the radius in nm; `result.neighbors` holds one row per other footprint whose courtyard lies within the
radius, sorted by distance and then reference: `ref`, `distance` (the gap between the two courtyards in
nm, rounded up; 0 when they touch or overlap), `overlap`, `side` and `shared_nets` (sorted names).

Only footprints on a side the part is on are neighbours; a part with through-hole pads is on both. A
footprint without a courtyard is judged by the hull of its pads, and one without pads by its position
(`kicad.frame.no-courtyard`). An unknown reference exits 2 with `FEN-2001`, and the hint names the
closest references.

## pads

`fenolite pads PATH [REF [NUMBER]] [--origin X,Y]` lists the pads of a board in the board frame: where a
pad is, on which layers and on which net. It is the query to run before writing a track by hand
(`docs/dsl.md`, "Copper"). It is read-only: it reads the board model, runs no tool and writes no file.

- `PATH` is a `.kicad_pcb`, a `.kicad_pro` or a project folder, resolved as `check` resolves it.
- `REF` keeps the pads of one part, matched by component path first, else by reference. `NUMBER` keeps
  the pads that carry that number.
- `--origin X,Y` takes two lengths with units (default `0mm,0mm`). Every `position` and `box` is reported
  relative to it. A design script places its board at `BOARD_ORIGIN`, (100 mm, 100 mm), so
  `--origin 100mm,100mm` gives the numbers that `place()`, `Design.track` and `Design.via` take.

`result` holds:

- `origin`: `[x, y]`, the origin in nanometres;
- `count`: the number of listed pads;
- `pads`: one object per pad, in board order and pad order:

| key | value |
|---|---|
| `where` | `REF-NUMBER`, or `REF` for a pad without a number |
| `ref`, `number` | the reference of the part and the pad number |
| `index` | the position of the pad among the pads of its footprint with the same number, from 0: the value that `Part.pad(number, index=…)` takes |
| `kind` | `smd`, `thru_hole`, `np_thru_hole` or `connect` |
| `position` | `[x, y]`, where a track ends on the pad, and where its hole is |
| `rotation` | the pad's angle in the board frame, integer microdegrees |
| `side` | `top` or `bottom`, the side of its footprint |
| `layers` | the pad's layers as the board stores them (`*.Cu` stays a wildcard) |
| `net` | the net's name, or `null` |
| `box` | `[x0, y0, x1, y1]`, the bounding box of the pad's copper over its copper layers, or `null` for a pad without copper. The copper of a pad whose drill has an offset is moved by that offset, as KiCad moves it, so the box need not be centred on `position` |
| `drill` | the drill size (the shorter size of a slot), or `null` |

Lengths are integer nanometres. `input` names the board with its SHA-256. The evidence is the board
read's combined with the board frame's (`frame.EVIDENCE`).

| exit | error | when |
|---|---|---|
| 0 | none | the pads are listed |
| 2 | `FEN-2001` | no part `REF` on the board (the hint names the closest references), no pad `NUMBER` on the part (the hint names its pad numbers), or an `--origin` that is not two lengths with units |
| 3 | `FEN-3001` | the board does not exist or cannot be resolved |

## equivalent

`fenolite equivalent A [B] [--level N] [--tolerance-nm N] [--tolerance-udeg N] [--tolerance-ppm N]
[--frame absolute|relative] [--ignore-ref GLOB]… [--exclusions FILE --profile NAME] [--against kicad-import]
[--kicad-cli PATH] [--timeout SECONDS]` says whether two designs are equivalent, level by level, and locates
every difference at `REF` or `REF-PIN`, and at the net for routing. It is read-only. With two paths it runs no tool. `docs/equivalence.md`
defines the levels, the kinds of difference, the tolerance rules and the exclusion file.

Each of `A` and `B` is one of:

- a `.fenolite/` folder (it holds `meta.json` or `build.json`): the built design, backend `fenolite`;
- a `.kicad_pro` file or a project folder, resolved to its board as `check` resolves it;
- any other file that a backend reads into a design: a KiCad board, an Altium PCB document, schematic
  document or project file.

| option | meaning |
|---|---|
| `--level N` | run the levels 1 to `N` (1 components, 2 netlist, 3 footprints, 4 placement, 5 routing). The default is the highest level both sides hold: 5 when both have footprints and copper (a track, an arc or a via), 4 when both have footprints, else 2. Pass `--level 4` to compare two routed boards without their routing |
| `--tolerance-nm N`, `--tolerance-udeg N` | how far two lengths (per coordinate) and two angles may differ; non-negative integers, default 0 |
| `--tolerance-ppm N` | level 5 only: two routed lengths are equal within the larger of `--tolerance-nm` and `N` parts per million of the longer one; a non-negative integer, default 0 |
| `--frame absolute\|relative` | `relative` removes one translation, the per-axis lower median of the footprint positions of `B` minus `A`; default `absolute` |
| `--ignore-ref GLOB` | leave out the components whose reference matches (repeatable) |
| `--exclusions FILE --profile NAME` | apply the rules of one profile of an exclusion file. The profile also gives the frame and the tolerances; an option on the command line overrides its value |
| `--against kicad-import` | instead of `B`: convert `A`, an Altium PCB document, with `kicad-cli pcb import` (10.0 only) and compare Fenolite's read of `A` with the read of the converted board, under the `kicad-import` profile of the running version line |
| `--kicad-cli PATH`, `--timeout SECONDS` | the tool of `--against` and its time limit (default 300 s) |

`result` holds:

| key | value |
|---|---|
| `level` | the highest level that ran |
| `equivalent` | `true` when no difference remains outside the rules |
| `sides` | `a` and `b`, each with `path` (the name without its folder), `sha256` (of a file; `null` for a folder), `backend` (`kicad`, `altium`, `fenolite` or `kicad-import`), `netlist_source` (`board` or `circuit`), `components` and `footprints` (counts); side `b` of `--against` also has `tool_version` |
| `tolerances` | `length_nm`, `angle_udeg` and `length_ppm` |
| `frame`, `translation` | the frame, and `[x, y]`, the translation removed from side `b` |
| `levels` | one object per level run: `level`, `name`, `compared`, `differences`, `excluded` and `notices` (counts) and `summary`. The summary of level 5 holds `nets` (compared), `pieces`, `vias` and `length` (totals of side `a` and `b` over those nets), `unjudged`, `nets_unpaired`, `zones_unfilled`, `copper_no_net` and `unshaped` |
| `differences`, `excluded` | objects `{level, kind, where, field, a, b}`, in level order and then by `where`; an excluded one also has `rule` |
| `notices` | objects of the same form for what level 5 reports without failing: `route-stub` and `route-unjudged` |
| `profile` | `null`, or `name`, `tool_version` and `rules` (the count of rules) |

`issues` holds one error per difference that no rule excludes, then one warning or info per notice, then
one `equiv.excluded` info per rule that matched, then the notices of the triangle, then the readers' warnings and infos of `A` and of `B`.
The evidence is the lowest of the two readings (a built design counts as `INFERRED`); with `--against`,
`evidence.oracle` is `kicad-cli`.

| code | severity | meaning |
|---|---|---|
| `equiv.component-missing` | error | a reference that only one side holds |
| `equiv.ref-ambiguous` | error | a reference that a side holds more than once, or an empty reference |
| `equiv.value`, `equiv.dnp` | error | the value or the do-not-populate flag of a component differs |
| `equiv.pin-missing` | error | a `REF-PIN` of a common component that only one side holds |
| `netlist.assignment-differs` | error | a `REF-PIN` whose net block differs (the code of `check`'s assignment comparison) |
| `equiv.footprint-missing` | error | a common component placed on one side only |
| `equiv.footprint-name` | error | the footprint names differ (the library nickname is not compared) |
| `equiv.pad-missing` | error | different counts of pads of one number |
| `equiv.pad-kind`, `equiv.pad-shape`, `equiv.pad-size`, `equiv.pad-drill`, `equiv.pad-position`, `equiv.pad-rotation`, `equiv.pad-copper` | error | a field of a pad differs, in the footprint's frame |
| `equiv.side`, `equiv.position`, `equiv.rotation` | error | the placement of a footprint differs |
| `equiv.route-missing` | error | one side has copper on a net and the other has none |
| `equiv.route-connectivity` | error | the copper of a net joins other pads on one side than on the other |
| `equiv.route-vias` | error | for the same joined pads, the via counts per pair of copper layers differ |
| `equiv.route-length` | error | for the same joined pads, the routed length on a copper layer differs beyond the tolerance |
| `equiv.route-stub` | warning | the copper that reaches no pad (stubs, lone vias) differs in number of pieces or in length; it does not fail the comparison |
| `equiv.route-unjudged` | info | a net whose connectivity depends on a zone without a fill was not judged |
| `equiv.excluded` | info | a rule of the profile matched differences (count and reason) |
| `equiv.import-message` | info | a warning or error of `kicad-cli`'s import report, counted by text |
| `equiv.no-exclusion-profile` | warning | no profile for the running `kicad-cli` version line: no rule, the relative frame, tolerance 0 |
| `equiv.oracle-failed` | error | `kicad-cli` wrote no board, or one that the KiCad reader refuses; no level ran |

| exit | error | when |
|---|---|---|
| 0 | none | equivalent up to the level, outside the rules |
| 5 | none | a difference remains, or `equiv.oracle-failed` |
| 2 | `FEN-2001` | neither `B` nor `--against`, or both; a level above what both sides hold (the message names the side without footprints, or without copper for level 5) or above 5; a bad value; `--exclusions` without `--profile` or the reverse; a profile the file lacks; an input no backend reads, or a library; `--against` on anything but an Altium PCB document |
| 3 | `FEN-3001` | an input does not exist |
| 3 | the reader's code | an input or the exclusion file cannot be read |
| 6 | `FEN-6001`, `FEN-6002` | `--against` without `kicad-cli`, or with a major other than 10 |

## manifest

`fenolite manifest PATH [--artifacts DIR]... [--stages a,b] [--no-check] [--verify] [--out FILE]
[--kicad-cli PATH] [--timeout SECONDS]` writes the project manifest: one `fenolite-artifacts.json`
(`schemas/fenolite.artifacts.v0.json`) that lists every design file of the project `PATH` names and the
artefacts of the folders it is given, each with its SHA-256 and a state (`docs/exports.md`, "States").
`PATH` is resolved as for `check`. `--out` defaults to `fenolite-artifacts.json` next to the board. The
mutation protocol applies, and the manifest is the only file the command plans.

- **Design files.** The board, its project and rules files, the footprint table with the libraries it
  names under the project folder and the drawing sheet (the copy set of `check`), then the schematic
  `<stem>.kicad_sch` with the sheets it names, and the symbol table with its libraries. A library folder
  is listed file by file. `tool` is `fenolite <version>` for a file whose hash `.fenolite/build.json`
  records, and `null` for any other.
- **Artefacts.** Each `--artifacts DIR` lies inside the project folder (else exit 2) and contributes the
  entries of `DIR/fenolite-artifacts.json`, the file that `--manifest` of `export`, `render`, `bom` and
  `pnp` writes. Every path is relative to the project folder, and every file is hashed again.
- **Check.** Unless `--no-check` is given, the stages `--stages` names (default: those of `check`) run
  exactly as `check` runs them, with the same pre-flight and tool errors, and the RT1 verdict of every
  sheet is taken as `roundtrip` takes it. The issues of the check are the command's issues. The manifest
  is planned whether or not the check found errors: an entry then has the state that holds.
  `--no-check` runs no stage and no tool, and every entry is `generated`.
- **`--verify`** reads the manifest and compares it with the files on disk. It writes nothing and runs no
  check and no tool. `--out DIR/fenolite-artifacts.json` verifies the manifest of an artefact folder
  instead: a manifest without a design file names its files from its own folder. It does not combine with `--no-check`, `--stages` or `--artifacts` (exit 2).

`result` holds `manifest` (the path of the file), `project` (`board` and `schematic`, each `path`,
`sha256` and `format_version`, or `null`), `states` (the number of entries per state), `artifacts`
(`path`, `kind`, `state`, `stale`, `held`; sorted by path) and `check` (`stages`, each `name`, `status`,
`level` and `oracle`, and `tool_version`; `null` without a check). With `--verify` it holds `verified`
(true when no listed file is missing or changed) and `differences` (`path`, `code`) in place of `check`.
`artifacts`, or `differences` under `--verify`, is the paged list. With `--timestamp`, two runs on
unchanged files plan byte-identical manifests.

| code | severity | when |
|---|---|---|
| `manifest.unreadable` | error | a `fenolite-artifacts.json` that is not JSON, has another schema id or another shape: an artefact folder then contributes nothing, and a producing command with `--manifest` plans no file |
| `manifest.missing` | warning; error under `--verify` | a listed file does not exist; when writing, it is left out |
| `manifest.changed` | warning; error under `--verify` | a listed file has another SHA-256; when writing, it is listed as it is now, without `tool` and `from`, so it stays `generated` |
| `manifest.stale` | warning | a file made from a board or schematic that has another SHA-256 now |
| `manifest.unlisted` | info | a file under an artefact folder that no entry lists; it is not added |

Exit codes: 0 when the manifest is planned or written, or verified; 4 without `--dry-run` or
`--confirm`; 5 with an error issue (after the write, when `--confirm` is given); 2 for a usage error;
3 for a missing path, a board Fenolite cannot read or, under `--verify`, a missing manifest
(`FEN-3001`) or one that cannot be read (`FEN-3004`); 6 when a stage needs `kicad-cli` and none is found
(`FEN-6001`; the hint names `--no-check` and `--stages`) or it is unsupported (`FEN-6002`). The evidence
is that of the stages that ran, combined as `check` combines them, with the schematic reader's when a
sheet was judged; it is `UNVERIFIED` with `--no-check` and `--verify`.

## kit

`fenolite kit build --out DIR [--samples DIR]`, `fenolite kit verify DIR`, `fenolite kit record DIR --out
REPO` and `fenolite kit status [--repo DIR] [--samples DIR]` are the Altium verification kit: a fixed
acceptance run that a person performs in Altium Designer on their own machine, and whose results are files
(`docs/altium-kit.md`). Nothing starts or drives Altium.

```
fenolite kit build --out kit --confirm --json
fenolite kit verify kit --json
fenolite kit record kit --out . --dry-run --json
fenolite kit status --json
```

- **`build`** writes the kit under the rules of "Writing files": `kit.json` (schema
  `fenolite.altium-kit.v0`), `STEPS.md`, `kit_script.pas`, one folder per sample and `results/form.json`.
  It builds the scripts under `examples/kit/` of a source checkout (`--samples` names another folder) and
  runs no external tool. Without `--seed` and `--timestamp` it uses seed 0 and `2026-01-01T00:00:00Z`, so
  two builds of one commit are equal byte for byte. `result` holds `kit_sha256`, `samples` with their
  digests, `steps`, `scripted` and `files`.
- **`verify`** is read-only. `result` holds `steps` (per step `outcome`: `pass`, `fail` or `skipped`, its
  `reasons`, `scripted` and its `pending` checks), `hypotheses` (per register row `pass`, `fail`,
  `skipped` or `pending`, and `form` when the verdict rests on a typed value), `privacy` (file, byte
  offset, kind and string of what looks like a home folder or a login name), `kit_problems`,
  `form_problems`, `synthetic` and `passed`.
- **`record`** is a mutating command. It writes `results.zip` beside `DIR` and the run record
  `REPO/docs/evidence/altium-kit/<run id>.json` (schema `fenolite.altium-kit-run.v0`), and lists in
  `result.rows` the register rows whose label may change, each with `label`, `form` and the `result` text
  of its row. It refuses a synthetic run, a kit whose files differ from `kit.json`, a form that is not
  sound, and a record that exists with other content (`kit.record-refused`, exit 5, nothing planned).
- **`status`** is read-only: `result.runs` lists the committed records of the repository and
  `result.stale` the register rows whose kit run is stale. In a folder without a record both are empty.
- The evidence is `ALTIUM-VERIFIED(kit)` only for `verify` and `record` of a run in which every step
  passed and that is not synthetic; it is `INFERRED` otherwise.

| code | severity | when |
|---|---|---|
| `kit.file-changed` | error | a file of the kit is missing or differs from its digest in `kit.json` |
| `kit.form` | error | `results/form.json` is not sound as a whole (schema, tool version, system, date, fields) |
| `kit.step-failed` | error | a result file fails a check, or a typed value is not the expected one |
| `kit.record-refused` | error | `record` wrote nothing; the message says why |
| `kit.synthetic` | warning | the form does not say that a tool performed the run |
| `kit.privacy` | warning | a result file holds what looks like a home folder or a login name |
| `kit.stale` | warning | `status`: a row's kit run is stale |
| `kit.step-skipped` | info | a step was not done |
| `kit.pending` | info | a check of a step waits for a change that is not implemented, and was not run |

| exit | error | when |
|---|---|---|
| 0 | none | a dry run or a confirmed write; `verify` with no failed step; `status` |
| 2 | `FEN-2001` | an argument that the action does not take, or a missing `--out` or `DIR` |
| 3 | `FEN-3001` | `DIR` holds no `kit.json`; the sample scripts are missing or do not build |
| 4 | `FEN-4001` | `build` or `record` with neither `--dry-run` nor `--confirm` |
| 5 | `FEN-5001` | a step failed, a kit file changed, the form is not sound, or `record` refused |
