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
- **A command's own text.** A command may return a text of its own (`Result.text` in
  `fenolite.cli.api`); `fenolite guide` does, for a page. In text mode stdout is then the status line
  (`fenolite <name>: ok`), one empty line and that text as it is, in place of the `input`, `result` and
  `evidence` lines. When the envelope holds issues or a receipt, their lines follow the text after one
  empty line, in the form they have for any other command. In JSON mode the text has no effect: the
  envelope is the same and holds no key for it. `--format concise` folds the issues before they are
  printed and does not change the text. A command that failed prints as any other.

- **In process.** `fenolite.api.run(command, *args, cwd=..., seed=..., timestamp=...)` runs a command
  through the same dispatcher and returns the exit code, this envelope and the error object as values,
  printing nothing; `--help`, `--text`, `restore -` and `view --serve` are usage errors there
  (`docs/api.md`; change c0206).

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
`receipt` is `{written: [{path, sha256}], backup: [path], id, undo, plan}` when the command wrote files
(see "Receipt identity"); `plan` is the id that `--confirm --plan` named, else `null`.

## Errors — `schemas/fenolite.error.v0.json`

Whenever the exit code is not 0, stderr carries exactly one error object
`{code, message, hint, retryable, where}` (JSON mode) or one line `error FEN-NNNN: message (hint)`
(text mode). The first digit of the code equals the exit code. Without `--progress` the error object is
the only thing Fenolite writes on stderr; with it, progress records may come first, each on a line of its
own, and the error object is the last line (see "Progress"). No exit leaves a traceback: an exception
that no handler maps, a failed write and a signal each end in one registered code (`FEN-1001`,
`FEN-1002`, `FEN-1003`, or `FEN-1004` when rollback is incomplete).

## Exit codes

| Code | Meaning | Error family |
|---|---|---|
| 0 | success | — |
| 1 | internal failure: inspect the code; FEN-1004 requires manual recovery | `FEN-1xxx` |
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

Exit 1 is not always a bug. `FEN-1004` (`retryable` false) means rollback was incomplete: preserve the
remaining recovery files and inspect them before any retry. `FEN-1001` (`retryable` false) means a software
bug: report it. `FEN-1002` and `FEN-1003`
(`retryable` true) say that a write failed or that the command was stopped, that nothing was changed,
and that the same command can be run again.

| Code | Meaning | Raised by |
|---|---|---|
| `FEN-1002` | a write failed; nothing was changed | the dispatcher, when a file of the plan cannot be written: the message names the path, relative to the working directory, and the system's reason (retryable; see "All-or-nothing writes") |
| `FEN-1003` | stopped by a signal; nothing was written | the dispatcher, after SIGTERM or SIGINT and a completed rollback (retryable; see "Signals") |
| `FEN-1004` | rollback incomplete; some files may have changed | the dispatcher, when restoring a target or backup fails; exit 1, retryable false; inspect `result.recovery` before manual recovery |
| `FEN-3002` | input uses a newer format version than supported | `FutureFormatError` (editing a future file) |
| `FEN-3003` | input format version older than the oldest supported | `UnsupportedFormatError` (hint names the `kicad-cli … upgrade` command) |
| `FEN-3004` | malformed input file | any other `FormatError` (syntax, missing version, …), and `DesignScriptError` (a design script that raised, or that binds no `design`) |
| `FEN-3005` | geometry in the input cannot be represented | `GeometryError` (the message names the geometry code and the points) |
| `FEN-3006` | fetched file does not match the pinned size or SHA-256 | the dispatcher, for a deferred write whose bytes differ from what the plan declared (see [fetch](#fetch)); the message holds the digest that was expected and the one that was found, and nothing is written |
| `FEN-3007` | input file is kept only online by a sync client | `snapshot`, `publish` and `refs`, before any read: the message names the files that a sync client keeps online only (see [snapshot](#snapshot)); retryable once they are available offline |
| `FEN-4002` | the plan named by `--plan` cannot be written as reviewed | the dispatcher, for `--confirm --plan ID`: the message names the first reason (see "Staged plans"); nothing is written |
| `FEN-6003` | download failed | `fenolite fetch NAME --confirm` without `--from` (retryable; the hint names `--from FILE`) |
| `FEN-7001` | operation would lose information | `LossyWriteError` (a KiCad write meets content the target cannot hold; the hint names `--allow-lossy` only when every loss is droppable) |
| `FEN-7002` | target format version older than the input; no downgrade was asked (hint: convert the project with `fenolite convert <project> --to kicad --kicad-version <target>`) | `DowngradeRefusedError` |
| `FEN-7003` | input from KiCad 8.0 is read-only; writing needs a KiCad 9.0 or newer source | `LegacyEditRefusedError` (hint names `kicad-cli pcb upgrade`) |
| `FEN-7004` | the design lock would change under --frozen; nothing was written | `LockFrozenError` of `build --frozen` (hint: build without `--frozen`, review `result.lock.changes`, commit the lock, then build frozen); `issues` holds one `lock.changed` per change |

## Writing files

Commands that write are **mutating**. They never write unless asked:

| Invocation | Effect | Exit |
|---|---|---|
| `fenolite <cmd> … --dry-run` | `result.plan` lists every file that would be written and `result.plan_id` names the plan; nothing is written | 0 |
| `fenolite <cmd> …` | same plan and id, error `FEN-4001` whose hint names `--confirm --plan <id>`, nothing is written | 4 |
| `fenolite <cmd> … --confirm --plan ID` | the plan that a review saw is written, without running the command again (see "Staged plans") | 0 |
| `fenolite <cmd> … --confirm` | one run that plans and writes: atomic writes (temporary file + rename), `.bak` of overwritten files unless `--no-backup`, `receipt` with SHA-256 | 0 |

`--plan` without `--confirm`, and `--plan` with `--dry-run`, exit 2 with `FEN-2001`.

### Staged plans

A review followed by a plain `--confirm` runs the command twice: every tool runs again, and a command
whose tool stamps its files (`export`: Gerber and drill files carry their creation time) then writes
other bytes than the plan showed. `--confirm --plan ID` writes the reviewed bytes instead.

- **The id.** `result.plan_id` is the first 16 hex digits of the SHA-256 of the canonical JSON of: the
  command name; its arguments without the run flags; the working directory; the SHA-256 of every input
  the command declares; and, per planned write, its path, kind, size, SHA-256 and the SHA-256 of the file
  it would replace (`null` when there is none). No clock and no seed takes part, so the same dry run on
  the same files gives the same id. A command that plans no write gets no id.
- **Run flags** change how a run happens, not what it plans, and take no part in the id: `--dry-run`,
  `--confirm`, `--plan`, `--json`, `--text`, `--fields`, `--limit`, `--cursor`, `--format`, `--progress`,
  `--seed`, `--timestamp`, `--no-backup`, `--timeout` and `--kicad-cli`.
- **Declared inputs.** `build`: the design script and the `--copper-from` board. `place`, `route`, `fill`,
  `export`, `render`, `pnp`, `sync` and `models`: the board and the other files of its project that the
  command read. `bom`: the board, and the root schematic with `--source kicad`. `manifest`: every design
  file and artefact manifest it hashed. `kit`: the documents it packs. `fmt` and `template`: their input
  file. `restore`: the receipt file, the written files and the `.bak` files. `fetch`: the file of
  `--from`. A target is not declared: it is bound through the digest of the file it replaces.
- **The checks.** `--confirm --plan ID` refuses with `FEN-4002` (exit 4), naming the first reason, when
  the working directory, the command or its arguments differ from the plan's; when a declared input or a
  target has another SHA-256 than at the review (a target that did not exist must still not exist); or
  when a staged file is damaged. A refusal writes nothing and keeps the staged plan, except a damaged
  one. Otherwise the staged bytes are written, the reply repeats the reviewed `result`, `issues`,
  `evidence` and `input` (shaped by the run flags of this call), and `receipt.plan` is the id. The
  receipt is an ordinary one: `fenolite restore` undoes it.
- **The state folder.** The planned bytes are kept outside the user's tree, under `plans/<id>/` of
  `~/.cache/fenolite/state`. `FENOLITE_STATE_DIR` names another folder when it is an absolute path, and
  `off` turns the store off. The store keeps at most 16 plans and 512 MiB, dropping the oldest first,
  drops a plan older than 7 days, and removes a plan once it is written. It holds nothing the command did
  not plan, and it can be deleted at any time. A run that writes nothing creates no file in the working
  directory, the project or the output folder.
- **Not staged.** When the plan cannot be kept (the store is off, not writable, or smaller than the
  plan), the reply holds one `plan.not-staged` warning and still gives the id. `--confirm --plan ID` then
  runs the command once and writes only when the new plan has the id `ID`, else `FEN-4002`: the id always
  binds what is written, and the store only saves the second run. A plan with a deferred write is always
  planned again, because its bytes do not exist before `--confirm`.

| code | severity | when |
|---|---|---|
| `plan.not-staged` | warning | the planned bytes could not be kept in the state folder; the message gives the reason |

### All-or-nothing writes

A command writes every file of its plan or rolls back a failed write. The new contents are first written beside their
targets, and every file that will be replaced is kept; only then are the targets replaced, in plan
order. When a write fails and rollback completes, every replaced target and `.bak` is put back and
newly written targets are removed. Cleanup of temporary files is best effort if the filesystem also
refuses deletion. The reply is then the envelope with `ok`
false, the plan in `result` and `receipt` `null`, and one `FEN-1002` object: exit 1, `retryable` true, the
failing path relative to the working directory, the system's reason, no absolute path and no traceback.
A receipt of an earlier command still restores, and under `--plan` the staged plan stays for the retry.
If rollback itself fails or is interrupted, the reply instead carries **FEN-1004**, exit 1 and
`retryable: false`. Other restoration steps are still attempted, but cleanup leaves the remaining recovery
files in place. `ok` is false, `receipt` is null, and `result.recovery.failed` names incomplete restoration
paths while `result.recovery.preserved` lists the remaining files to inspect. These fields remain present
even with `--fields`. Recovery paths resolve from the working directory, including `../` for files
outside it; on different Windows volumes, only the structured result uses an absolute path. Error text
uses relative paths (or file names outside the working directory).
Under `--plan`, the staged plan remains for inspection; automatic replay is not recommended.

Preserve those files before manual recovery: `.keep` files can hold original targets or earlier backups,
`.tmp` files hold proposed new bytes, and a `.bak` may hold a moved original. Compare contents with previous
receipts before restoring the intended state, then review a new dry-run plan. FEN-1004 never claims that
nothing changed. A forced stop such as SIGKILL or a machine failure can also leave a partial write without
an error reply; filesystem transactions across multiple files are not promised.

### Error findings plan no write

A command whose issues hold one of severity `error` plans, stages and writes nothing: `result.plan` and
`result.plan_id` are absent, `receipt` is `null` and the exit code is 5, with `--dry-run`, with `--confirm`
and with neither. The rule holds in the dispatcher, for every command. The exceptions write on purpose:
`place --force`, where writing beside an error is what the flag asks for, and the two commands whose
write is the report of the findings, `manifest` (the manifest records the states that the check found)
and `kit record` (the record holds the failed steps of the run).

### Signals

SIGTERM and SIGINT (Ctrl+C) stop a command cleanly: the tool processes it started (`kicad-cli`, `java`,
a router) are stopped with it, a write in progress is put back, the record of a route keeps the router
runs that had finished (see [route](#route)), and the reply is the envelope with `ok` false and one
`FEN-1003` object (exit 1, `retryable` true, "stopped by a signal; nothing was written") after completed
rollback. If rollback itself fails, FEN-1004 takes precedence and retains recovery files. A second signal
does not cut the clean-up. On Windows a Ctrl+C is handled the same way, and a forced stop of the process
(`TerminateProcess`) cannot be handled; SIGKILL cannot be handled on any system, and can leave temporary
files and a tool process behind.

### Progress

`--progress` makes a command write progress records on stderr while it runs: one when a unit of work
starts, one when it ends, and one at least every 10 seconds, so that a caller can tell a long step from
a dead one. In JSON mode a record is one line

```json
{"progress": {"command": "check", "event": "step", "step": "drc.kicad", "index": 3, "total": 5, "detail": "", "elapsed_ms": 1200}}
```

with `event` `step` (a unit starts), `done` (it ends; `detail` says how) or `alive`; `index` and `total`
are integers or `null`. In text mode it is one line that starts with `progress: <command>: `. The units
are: one per stage of `check`, named by the stage; one per router process of `route` (for
KiCadRoutingTools a group of nets, named by its first net and the count of the others; for Freerouting a
tier, `freerouting` or `freerouting tier <n>`); the `refill` of `fill`; one per kind of
`export`; one per view of `render`. Every other command gives `alive` records only. A record holds no
path of the machine. Records carry times, so the determinism rule does not cover them; stdout is the
same with and without the flag, apart from `elapsed_ms`. Without `--progress` nothing but the error
object is written on stderr.

**Deferred writes.** A command may plan a file whose bytes are costly to obtain, such as a download,
without obtaining them (`PlannedWrite.source`, with the `size` and the `sha256` the bytes must have). The
plan lists such a file with its declared `bytes` and `sha256`, as it lists any other. Without `--confirm`
the source is never called. With `--confirm` it is called once, before any file of the command is written,
and what it returns is compared with the declared size and digest: a difference exits 3 with `FEN-3006`
and nothing is written, not even the command's other files.

## Determinism

`--seed INT` and `--timestamp ISO8601` fix every generated id and date: the same inputs and flags
produce byte-identical outputs. Keyed ids (placed copies, objects of design scripts) are not generated
and do not depend on `--seed`, and a command that writes no date ignores `--timestamp`; `build` is
such a command, so its outputs are byte-identical whatever both flags say.

## `catalog`

`fenolite catalog list [--kind symbol|footprint|device] [--query TEXT]` returns stable, offline catalog
entries with `lib_id`, kind, category, summary, evidence level and registered source ids; without `--kind`
the list holds symbols, footprints and the shipped devices (change c0248, `docs/devices.md`), and a device
entry also holds `id`. `fenolite catalog show LIB_ID [--kind ...]` returns the same metadata and a compact
definition summary; for a device (`--kind device`, or an id that no symbol or footprint has) it returns
the `record`, its `digest`, `edited` and `shadowed` (functions hidden by attributes of `Part`), and the
`check_device` issues against the catalog symbol and footprint. Neither
command reads library tables or runs external tools. The initial generic catalog is documented in
`docs/catalog/README.md`; every non-`KICAD-VERIFIED` land dimension remains explicitly marked.

`fenolite catalog view --out FILE [--kind symbol|footprint] [--query TEXT]` plans one standalone HTML
browser of the matching installed definitions. This action is new in 0.6.0 (c0234). Its result holds `count`, `counts.symbols`,
`counts.footprints`, `out`, `filters` and `export` (`bytes`, `sha256`). The standard mutation protocol
applies: `--dry-run` reviews the plan, and `--confirm --plan ID` writes its exact staged bytes. The page
needs no network, external CAD executable or intermediate library file. Equal definitions and filters
produce equal bytes. Existing list/show calls still need no confirmation and write nothing.

The page uses the existing symbol and footprint library viewer, with only the nonempty virtual library
documents, exact IDs, category/summary, source IDs, pin roles and pad inspection. Evidence stays
`INFERRED`; previewing generic roles or a land pattern is not device-pinout or fabrication acceptance.
The Properties panel starts collapsed; click it or use Tab followed by Enter or Space to inspect the
metadata. Evidence stays visible in its summary. Symbol property text stays in the details rather than
over the drawing; footprint fabrication and
courtyard layers are initially visible. Exact pad information remains available by selecting a pad.
`view` with no `--out`, a positional ID on `view`, or `--out` on list/show gives `FEN-2001` (exit 2).
Empty view filters give `FEN-3001` (exit 3), a hint to change the filters and no write; empty list filters
keep returning a successful empty list.

`fenolite catalog import --symbol LIB:SYM --footprint LIB:FP --id NS:NAME --out FILE [--pin
FUNCTION=PIN[:PAD[+PAD]]]... [--manufacturer T] [--mpn T] [--datasheet URL] [--ref-prefix P]` plans one
write of kind `device`: a device template (`docs/devices.md`) with `evidence = "UNVERIFIED"` and a
`[provenance]` stamp (`tool`, the two lib ids, the date of `--timestamp` or today in UTC, and the record's
SHA-256). Its result holds `device`, `out`, `functions`, `digest`, `replaces` and `evidence`. Catalog ids
resolve offline; other lib ids through the library tables of the folder of `--out`. A symbol pin without a
pad of its number and no `--pin` is `catalog.pin-without-pad` (error, exit 5, no write); a pad no pin names
is `catalog.pad-unmapped` (warning). Onto an existing file that was edited after its stamp (or is not a
device record) the import exits 7 with `FEN-7001` unless `--allow-lossy` is given; onto an unedited file it
plans the replacement. The import options on `list`, `show` or `view` give `FEN-2001`.

## KiCad output

Every command accepts `--kicad-version {9,10}` (default 10) and `--allow-lossy`, before or after the
command name, like `--seed`. A command that writes KiCad files uses `--kicad-version` as the KiCad
major of what it writes, and `--allow-lossy` as permission to drop content that major cannot read:
each dropped part is reported as a warning, and without the flag the command fails with `FEN-7001`
(exit 7). Content the model holds is never dropped, with or without the flag. Any other
`--kicad-version` value is a usage error (`FEN-2001`, exit 2).

A check severity of the script (`design.rules.severity()`) whose key the target major does not have is
refused the same way, with `kicad.project.unknown-check`; with `--allow-lossy` it is left out and
reported as `kicad.project.dropped-check`.

A design rule of a kind the target major does not check is refused the same way, with the issue
`rules.kind-unchecked`: a `creepage` rule and `--kicad-version 9`. With `--allow-lossy` the rule is left
out of the `.kicad_dru` and reported as `rules.dropped-for-target`; it stays in `.fenolite/rules.json`.

**Stack-up (c0101).** `read_board` projects the `stackup` child of `setup` into `Board.stackup` and keeps
`setup` as it is written (`docs/formats/kicad/board.md`, "Stack-up"). Reader codes:
`kicad.board.stackup-unused` (warning) for a node KiCad does not use, whose job file then states no
thickness; `kicad.board.stackup-unmodelled` (info) for a complete node with a value the model cannot hold
exactly; `kicad.board.stackup-thickness` (warning) for a board thickness that differs from the sum of the
layers. Writer codes: `kicad.board.stackup-invalid` (error, never dropped by `--allow-lossy`) for a
stack-up that cannot be written complete, and `kicad.board.stackup-rewritten` (info) naming the values of
a replaced node that the model does not hold. A board that is read and written back without a change of
its stack-up keeps the bytes of `setup` and `general`.

## Build target

`fenolite build DESIGN.py --out DIR` takes `--target {kicad,altium}`, default `kicad`. With
`--target kicad`, or without the option, it builds the KiCad project of `docs/dsl.md`. With
`--target altium` it builds an experimental Altium project instead: a project file, a schematic, its
libraries and, for KiCad footprints, a PCB library and an experimental PCB document (`docs/altium.md`).
It reads only the KiCad libraries that KiCad lib ids and footprint links name, `result.target` is the
string `altium`, `result.footprints` and `result.pcb_document` describe the PCB files,
`result.no_connects` counts the No ERC directives written for the pins marked with `no_connect`,
`result.experimental` is true when at least one emitted kind remains experimental;
one `altium.experimental` info lists those kinds. The envelope combines the write
cells of emitted kinds with input evidence; kept documents and cache files add no
write claim. `--kicad-version` and `--allow-lossy` change none of its bytes.
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

`--altium-layout {grid,blocks}` (c0165) selects legacy cells or functional block composition.
Omission inherits `design.schematic_layout(mode="blocks")`, otherwise keeps legacy bytes. An explicit
`grid` contradicting DSL declarations, or the flag on KiCad, is `FEN-2001` (exit 2). Active DSL
composition on KiCad is bad script input (exit 3). Blocks keep the electrical sheet hierarchy and
every symbol unit. Hard `composition.*` findings refuse all writes (exit 5); label fallback is info.
`result.schematic_composition` holds `fenolite.schematic-composition.v0`: algorithm, evidence, nm units,
baseline origin, replayed sheets, limits, per-sheet regions, blocks, placements, attachment decisions,
connection metrics and findings. Confirmation writes `.fenolite/schematic-composition.json` and
`.fenolite/schematic-preview/<sheet>.svg` in the same transaction. Synced native bytes remain authoritative;
changed intent/baselines yield `build.altium-layout-conflict` even with `--discard-layout`. Text metrics
and native acceptance remain `INFERRED`. See `docs/schematic-composition.md`.

`--altium-outjob {on,off}` (change c0087) writes `<name>.OutJob`, an Altium output job, beside the PCB
document of an Altium build: `on` is the default, `off` writes none, and a build without a PCB document
writes none either. The job holds the containers `fab` (a folder) and `doc` (a PDF) and six outputs: Gerber,
NC drill, pick and place and bill of materials for `fab`, a schematic print and a PCB print for `doc`. Its
write kind is `altium_outjob`, and a new project file lists it after the PCB document. Fenolite runs no
output: the job is run in Altium. `--altium-outjob-preset FILE` names the export preset the job is made for
(the TOML file of `export --preset`). Since change c0138 the Gerber output of the job carries its complete
settings record and every output the key `OutputDefault<i>=0`; the writer maps one option of a preset,
`gerbers.precision`, to the decimals of that record (4 without it). No other output carries a setting, so
those keep Altium's defaults, and `result.outjob.defaults` lists the other options the preset sets, as sorted
`table.key` texts, for you to set in Altium. Either option with `--target kicad`, and the preset with
`--altium-outjob off`, is a usage error (`FEN-2001`, exit 2); a preset that cannot be read or is malformed
fails as it does for `export`. `result.outjob` is `null` without a job and otherwise holds, in this order,
`file`, `media` (`name` and `type` per container), `outputs` (`kind`, `type`, `name`, `category`,
`document`, `enabled` and `medium` per output), `gerber`, `defaults` and `preset` (`null`, or `file` and
`sha256`). `result.outjob.gerber` (change c0138) says what the Gerber record of the job holds, with the keys
in this order: `unit` (`"Metric"`), `decimals` (an integer), `layers` (one object with `id`, the long layer
id, and `name` per plotted layer, in the order of the record: only layers the board has) and `outline`, the
object `{"plotted": false, "reason": "…"}`: **the Gerber set of the job holds no plot of the board outline**,
and `reason` says why and what to do in Altium. An existing project file that does not list the job
is written again with the job listed, and its old bytes are kept as `<name>.PrjPcb.bak`, when it is as a
build wrote it (its SHA-256 is the one `.fenolite/build.json` records, as in a folder built by 0.2.x or with
`--altium-outjob off`): it is then in `result.files` and not in `result.kept`. Any other existing project
file is kept, and one that does not list the job gives the info `altium.outjob-not-listed`, whose hint says
how to list it. The infos about a kept project file (`altium.pcb-not-in-project`,
`altium.schlib-not-in-project`, `altium.sheets-not-in-project`, `altium.outjob-not-listed`) are given only
for documents that the kept file, read with Fenolite's project reader, does not list; a kept file that
cannot be read gets them for every document, with a hint that says so. `.fenolite/build.json` keeps the
digest of a kept project file whose bytes are the ones it recorded before, and of no other kept file; a
kept file is never in `result.files` or in the receipt. A job that an earlier build wrote into the folder and that differs from
the one the build writes now (every job written before change c0138 does) is replaced, with the old bytes
kept as `<name>.OutJob.bak`, when the folder's `.fenolite/build.json` records its digest; a job that was
edited since, or whose record is gone, is refused like any edited output (exit 7, `FEN-7001`) unless
`--discard-layout` is given.

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
`--altium-pour {computed,outline}` (change c0215; default `computed`; a usage error `FEN-2001` without
`--target altium`) is the pour mode of the PCB document: `computed` writes the copper of each polygon as
Fenolite pours it with Altium's rules (experimental; `docs/altium.md`, "Computed pours"), `outline` writes
the polygons unpoured, as earlier versions did. Without the `geo` extra the default writes the outline with
one `altium.pour-unavailable` warning, and an explicit `computed` exits 6 (`FEN-6001`). `result.pcb.pour`
holds `mode`, `poured`, `unpoured` (reason → count), `evidence` and `hypotheses`.
`--altium-bodies {off,extruded}` (change c0121; default `extruded` since change c0155; a usage error `FEN-2001` without
`--target altium`) picks what the build does with the component bodies of the board's footprints:
`off` writes none and reports each with `altium.not-lowered` (`where` = `body/<id>`); `extruded`
writes each extruded body that has an outline and a height above its standoff into the PCB document
(and the bodies of a footprint definition into the PCB library) and reports the others. With `off`
every file is the file of earlier versions, byte for byte; a design whose footprints hold no body
gives those bytes with `extruded` too, and a script declares no body with an outline today. **The
default changed in change c0155** (the maintainer's decision of 2026-10-09, after step X8 of the author
report was reported as expected, `docs/evidence/altium-pcb.md`): without the option the build writes the
extruded bodies, and `result.pcb.bodies` is `extruded`; `off` gives the earlier files. The write is
experimental: two keys of a written body are stand-ins (`docs/altium.md`, "Component bodies"). The evidence for the record is thin: its keys were measured on 1272 saved extruded bodies of five public documents of three repositories, 1265 of them from one repository, and the written bodies were opened in Altium Designer 26.5 by the maintainer alone (an author report).
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
is written) and `placements_from_board`. `result.pcb` (specified by change c0085; **returned by the command since change c0121**: until then the key was missing from the JSON result of every Altium build, and only the library's build summary held it; it stands after `copper`, and no written file changed with it) is `null` without a PCB document; with one it holds `written`, the number of model items the document holds per kind (`footprint`, `pad`, `track`, `arc`, `via`, `zone`, `text`, `graphic`, `dimension`, `keep-out`, `hole`, `cutout` (change c0168), `body`, `rule`), `not_lowered`, the kinds with items it does not hold and their number, and `bodies` (change c0121), the value of `--altium-bodies` that was used (`off` or `extruded`): with `extruded`, `written.body` counts the component bodies written and `not_lowered.body` the others. With `--copper-from`, `result.copper_input` holds the board's
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
| `altium.zones-unpoured` | info | polygons are written without poured copper (pour mode `outline`) |
| `altium.zones-poured` | info | polygons are poured by Fenolite (pour mode `computed`, experimental) |
| `altium.zone-unpoured` | warning | one polygon is written with its outline only: the reason the engine refused it |
| `altium.pour-unavailable` | warning | the default pour mode needs the `geo` extra: the polygons are written unpoured |
| `altium.plane-zone-merged` | info | a zone on a plane layer with the plane's net is left to the plane |
| `altium.placement-from-board` | info | components are placed as the board of `--copper-from` places them, not as the script requests |

A script with `planes` built for the KiCad target gives each plane layer the row type `power` in the board (also on a rebuild, after the layout merge; a type the board holds on another layer stays), and one `build.plane-zone-missing` warning per plane whose net has no zone on its layer: the copper of a plane is the zone that `design.zone(<net>, layers=("<layer>",))` draws. `build.plane-not-lowered` is no longer given (change c0107).

A build for the KiCad target also checks the interfaces of the design (`docs/dsl.md`, "Typed interfaces"):

| code | severity | meaning |
|---|---|---|
| `build.diff-pair-name` | warning | the two nets of a `diff_pair` or `usb2` interface are not a differential pair for KiCad by name; the hint proposes a name |
| `build.diff-pair-gap-shadowed` | warning | the two nets of a pair interface are in a net class with a pair gap, and KiCad would report two tracks laid at that gap: a clearance rule above the gap governs between them, or the board minimum clearance is above the gap and no `diff_pair_gap` rule selects the pair; the hint names `design.rules.pair(…, clearance=…, gap_min=…)` |
| `build.i2c-pullup-missing` | warning | a line of an `i2c` interface has no two-pin part to the `hv` net of a `power` interface or of a `power` port (change c0252) |

A build for either target also runs the circuit rules on the model it builds (change c0252; "Circuit
stage" under `check`): the nine `circuit.*` codes join the envelope with their severities, and an error
(`circuit.rail-voltage`, `circuit.rail-current`, `circuit.rail-sources`, `circuit.logic-level`) stops the
write, so the build exits 5 and writes nothing.

A build for the KiCad target also checks the blocks of the design (`docs/dsl.md`, "Blocks"; change c0251):

| code | severity | meaning |
|---|---|---|
| `build.port-unused` | warning | a port of a block instance that is not `optional` has nothing outside the block on its members; `where` is `<block path>/<port>` |
| `build.block-net-escape` | warning | a script-named net joins pins inside and outside a block instance without a port of that block; `where` is `<block path>:<net>`, the hint "declare a port" |

A build for either target applies the catalog's default pin-to-pad map (change c0147,
`docs/catalog/sources.md`) and reports each part it applies it to:

| code | severity | meaning |
|---|---|---|
| `build.pad-map-default` | warning | a part of an anode-first catalog symbol (`Fenolite:LED`, `Diode`, `Zener_Diode`, `Schottky_Diode`, `Photodiode`) on a catalog land whose pad 1 is the cathode gives no `pad_map`, and the build applied `{"1": "2", "2": "1"}`; the issue names the part (`where`), the land and the map, and the hint the `pad_map=` to write |

## `build`

`fenolite build DESIGN.py --out DIR [--discard-layout] [--vendor all|project] [--schematic write|skip]
[--schematic-layout readable|grid]
[--target kicad|altium]
[--altium-format binary|ascii] [--altium-sheets flat|modules] [--altium-layout grid|blocks] [--altium-outjob on|off]
[--altium-outjob-preset FILE] [--altium-symbols graphics|generic] [--altium-directions on|off]
[--altium-bodies off|extruded] [--altium-pour computed|outline]
[--copper-check refuse|warn] [--lock FILE] [--frozen] [--take SIDE[:TARGET]]...` runs the design script
(your own code: never run it on an untrusted script) and plans the files of a KiCad project under `DIR`
(`docs/dsl.md`). It is mutating. `--discard-layout` replaces outputs edited since the last build.
`--vendor all` (the default) copies the placed footprints of every library into `DIR/lib/`; the copies
keep their library's licence. `--vendor project` copies only those of project tables, and each other
footprint gives the info `build.global-library`. `result.vendored` lists the copied files and
`result.libraries` the row origin of each lib id.

The design lock (change c0249; `docs/dsl.md`, "Reference designators and the design lock") gives the
parts written without a ref their refs. `build` reads `<script stem>.lock` beside the script, or the file
of `--lock FILE` (relative to the working directory), and plans it as a write of kind `lock` when its
canonical bytes change, also for `--target altium`. A design whose parts all have explicit refs and that
has no lock file gets none, and `result.lock` is `null`. Otherwise `result.lock` holds `file` (relative to
the script folder when the lock is inside it, else its file name), `exists`, `written`, `frozen` and
`changes`: one `{"section", "key", "before", "after", "reason"}` per change, sorted by section and key, the
reason one of `assigned`, `released`, `moved`, `explicit`, `taken`, `prefix-changed` and `design-renamed`.
New refs are listed there only; the issues are `lock.ref-released` and `lock.ref-taken` (warnings),
`lock.ref-moved`, `lock.ref-explicit`, `lock.ref-prefix-changed` and `lock.design-renamed` (infos).
`--frozen` refuses any change of the lock with exit 7 and `FEN-7004`, one `lock.changed` (error) per change
in `issues`, and nothing written, also under `--dry-run`; a frozen build never writes the lock, and a lock
that differs in formatting only is no change. A malformed lock is `FEN-3004`; a newer schema, or content in
the reserved sections `picks` and `pins`, is `FEN-3002`.

Every placed footprint holds a `Reference` and a `Value` field. A footprint of the built-in catalog or
of `dsl.Footprint` carries both in the project library and on the board (`docs/dsl.md`, "Authored
footprints"). A footprint read from a library file that lacks one gets it on the board at the same
default placement, and the build gives one `build.field-added` info per such lib id, naming the fields.

A pin marked with `no_connect` that a net also lists, once designators are resolved to pin numbers, is
refused: `build.no-connect-on-net` (error) with `--target kicad`, `model.no-connect-on-net` (error) with
`--target altium`; the exit code is 5 and nothing is written. The marks are kept in
`.fenolite/circuit.json`; in a KiCad build each mark becomes a no-connect flag of the schematic, and no
other written KiCad file depends on them (`docs/dsl.md`, "No-connect marks").

A part with an unused-pin request (`part.unused_no_connect(keep=...)`, change c0247) gets a mark on every
pin that is open once nets and explicit marks are resolved, except the kept pins and pins of type
`no_connect`; both targets resolve the request the same way. An open must-connect pin (type `power_in`)
gives `build.must-connect-unconnected` (error, exit 5, nothing written) with the hint to connect it or list
it in `keep=`. A part used through its ends `a`/`b` or a connection helper whose symbol has other than two
pins gives `build.not-two-terminal` (error, exit 5, nothing written), naming the ref and the pin count
(`docs/dsl.md`, "Connection helpers").

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

**Edits made in KiCad** (change c0250, `docs/lens.md`, "Three-way merge"). Positions, rotations, values
and footprints are merged three ways between the script with `edits.toml` (beside the script; a legacy
`placements.toml` when there is none, `edit.legacy-file` when both are there), the board and schematic
in `DIR`, and the base record `DIR/fenolite-base.json` that every build writes (a planned write, in the
receipt and in `.fenolite/build.json`). `result.preserved.edits` holds `kept`, `code`, `taken` and
`unrecorded` (sorted `"<path>#<property>"` keys) and `conflicts` (records: `key`, `reason`, `base`, `code`,
`cad`); `result.preserved.source.file` names the file read. A property changed on both sides to
different values, or an edit of `edits.toml` made over a script value that changed since, is a
`sync.conflict` (error): exit 5 and nothing written. `--take SIDE[:TARGET]`, repeatable, resolves it:
`SIDE` is `code`, `cad`, `board` or `schematic`, `TARGET` a component path or a key `PATH#PROPERTY`, none
for every conflict; the most specific take wins. A malformed value or two sides for one target is a usage
error (exit 2, `FEN-2001`); a take that matches no conflict gives `edit.take-unused` (warning). The info
codes `edit.unrecorded`, `edit.code-wins` and `edit.base-missing` never fail a build, and
`edit.base-invalid` (warning) reads a broken base record as none. A base record changed by hand is
refused as `build.layout-exists` (exit 7).

The outline of the script is judged before anything is placed (`docs/dsl.md`, "Board"):
`kicad.outline.invalid` (error: exit 5, nothing written) for rings that cross or touch, a cut-out or slot
outside the board, a cut-out inside another and a slot of a size that is no slot's, and
`kicad.outline.zone-short` (warning) for a zone without an outline that an arc of the board ring bulges
beyond. Cut-outs and milled slots that overlap are written as one ring, their union, with
`kicad.outline.merged` (info) naming the items; the union needs the `geo` extra, and without it the build
stops with `kicad.outline.overlap` (error: exit 5, nothing written; hint `pip install 'fenolite[geo]'`;
change c0167). Writing a model through the API, `write_board` refuses the same overlap with
`kicad.board.outline-overlap` and a model with holes outside every footprint (`Board.holes`) with
`kicad.board.free-hole`, both `FEN-7001` (exit 7). Over an existing board, a new outline or a new
copper count of the script is applied (`docs/lens.md`, "Outline changes" and "Copper count changes"):
`kicad.outline.replaced` (info), `kicad.outline.forced` (warning) and `kicad.outline.copper-dropped`
(warning) for the outline, and `kicad.layers.added` (info), `kicad.layers.removed` (warning) and
`kicad.layers.stackup-reset` (warning) for the layers. Copper that no longer fits the outline, or that
lies on a removed layer, is dropped: run the build with `--dry-run` first to read the counts in
`issues`. `layout.outline-kept` (warning) stays for an outline edited in KiCad, which wins unless the
script says `board(..., locked=True)`, and `layout.copper-mismatch` (error) for a layer table that
Fenolite does not create.

A script may declare copper (`docs/dsl.md`, "Copper"; `docs/copper.md`). The build resolves it after
placement, and the KiCad `result.copper` reports `intents`, `tracks`, `arcs` and `vias` (created), and
`regenerated`, `stale` and `duplicates` (from the merge with an existing board; 0 without one). A
copper error (a `kicad.copper.*` issue of severity error) exits 5 and writes nothing; the
`kicad.copper.*` and `kicad.frame.*` codes are listed in `docs/copper.md`. With intents, the envelope
evidence also combines the copper and board-frame evidence, which are `INFERRED`. `--seed`,
`--timestamp` and `PYTHONHASHSEED` change no byte of a build with intents. A via of kind `buried` needs
`--kicad-version 10`: for KiCad 9 the board writer refuses it and the build exits 7 (`FEN-7001`).

A script may declare rule areas, keep-outs, texts, graphics and dimensions (`docs/dsl.md`, "Rule areas"
and "Board drawings"). `result.board_items` reports the counts `rule_areas`, `texts`, `graphics` and
`dimensions` of the script, and `result.preserved.board_items` the counts `regenerated` and `stale` of
the merge with an existing board (0 without one): script items are written again on every build, with
`kicad.board-item.regenerated` (info) for one that was edited in KiCad and `kicad.board-item.stale`
(warning) for one whose call is gone (`docs/lens.md`, "Board items declared in the script"). A rule that
selects a rule area by a name that the board about to be written does not hold stops the build:
`build.area-unknown` (error, exit 5, nothing written), with the hint to declare the area with
`design.rule_area()` or to remove the selector. The copper guard reports copper in a keep-out as
`copper.keepout`, copper too close to the board edge, a cut-out or a slot as `copper.edge-clearance`, and
the two findings of drilled holes, `copper.hole-in-cutout` and `copper.hole-overlap` (change c0169).

A script may also declare meanders (`Design.meander`; `docs/dsl.md`, "Meanders"; change c0106). The
build resolves them right after the copper, for the major of `--kicad-version`, and `result.copper`
then also holds `meanders`, the count of meanders that changed copper (the key is absent from the
reply of a script without meanders). The codes are `kicad.meander.bad-intent`, `kicad.meander.bad-shape`,
`kicad.meander.too-long`, `kicad.meander.no-room`, `kicad.meander.bad-match` and `kicad.meander.inexact`
(errors: exit 5, nothing written), `kicad.meander.no-segment` (warning) and `kicad.meander.not-needed`
(info); `docs/copper.md` lists them. With meanders the envelope evidence also combines the meander
and length evidence (`INFERRED`). `--seed`, `--timestamp` and `PYTHONHASHSEED` change no byte of a
build with meanders, and a second build over the first writes the same bytes.

**Copper guard.** Before a KiCad build plans its writes, it judges the copper of the triad it is about
to write with the copper check of `check` (`copper.clearance`, below): the planned board is read back,
the planned project and rules files give the clearance in force, and copper kept from an existing board
is judged with the rest. `--copper-check refuse` (the default) adds the `copper.*` issues as they are,
so a `copper.short` or a `copper.clearance` error exits 5 and writes nothing. `--copper-check warn`
reports those errors as warnings, with ` (copper guard in warn mode)` at the end of the message, and
writes. There is no way to switch the guard off. `result.copper_check` holds `mode`, `ran` (false when
the build was already refused), `shorts`, `clearance`, `edge_clearance`, `rules` (`min_clearance`,
`opaque_clearance_rules`, `unread`), `evidence` and `waivers`. The design's `copper.*` waivers
(`design.waive()`) are applied before the mode: a waived finding is `info` in `refuse` and in `warn`
mode, so it neither refuses the build nor gains the warn note. `result.copper_check.waivers` holds
`matched` (waiver name → findings) and `unmatched` (names); the guard reports no stale waiver itself,
`check` does ("Waivers" below). The guard runs on `--dry-run` too, reads and writes
no file, and runs no tool. With `--target altium` the guard judges the PCB document instead (below,
"Copper guard of an Altium build"). A Python caller of
`build_design` is not guarded (`docs/dsl.md`, "Copper guard").

**Placement guard.** The same planned board is then judged by the placement legality check
(`docs/placement.md`): the courtyards of the placed parts against each other, against the outline and
against the rule areas of the board that forbid footprints. The placement rules of the script
(`design.near()`) are judged on the pads of the same board. Parts that the build staged
(`result.staged`) are not judged; a rule that names one gives `placement.rule-skipped`. Every `place.*`
and `placement.*` issue is reported at most as a warning, so a build never exits 5 for placement; the
codes are those of the tables under "place" and "check".
`result.placement` holds `ran` (false when the build was refused), `counts`, the number of issues by
code, and `rules`, the counts of the rules by family (`{"near": {"judged", "failed", "skipped"}}`, and
`{"height": {"judged", "failed", "unknown"}}` when the design holds a height limit, change c0140; the
heights are those of the built model). The guard runs on `--dry-run` too, reads and writes no file, and runs no tool. With
`--target altium` there is no `result.placement` and no rule is judged: one `altium.not-lowered` info
(`where` `placement-rule`) names the count of the stored rules, which `fenolite check` judges. A Python caller of `build_design` is not guarded; it
calls `placement.check` itself (`docs/placement.md`).

`result.stackup` (c0101) is `null` when the written board holds no stack-up, and otherwise
`{"source": "script" | "board", "thickness": <nm>, "copper": <copper entries>}`: `source` names whose
stack-up the written board holds. Against an existing board the board's stack-up wins over an unlocked
`design.stackup()` that differs (`kicad.stackup.overridden`, info), and `stackup(locked=True)` replaces it
(`kicad.stackup.forced`, warning); a `model.stackup-*` error refuses the build. A script without
`stackup()` builds every file with the bytes it had before (`docs/lens.md`, "Stack-up across rebuilds").

**Via protection (c0112).** A script states how vias are tented, covered, plugged, capped and filled with
`protect()`, `protection=` and `design.via_protection()` (`docs/dsl.md`, "Via protection"). Codes of the
build: `kicad.board.via-protection-too-new` (error, exit 7 with `FEN-7001`, never dropped by
`--allow-lossy`) when `--kicad-version 9` meets a covering, plugging, capping or filling of `True`;
`kicad.via.protection-overridden` (info) when the board's default is kept over an unlocked script default
that differs; `kicad.via.protection-forced` (warning) when a locked script default replaced the board's;
`kicad.via.protection-not-exported` (info) when vias take a covering, plugging, capping or filling from
the board default only, which `kicad-cli` 10.0.6 writes to no fabrication file. With `--target altium`,
one `altium.not-lowered` info whose `where` is `via-protection` names the vias whose covering, plugging,
capping or filling stays in the model and, when the design states a protection, the vias with a tenting
side stated nowhere (`docs/altium.md`, "Via protection"). No flag is added, and a script that states no
protection builds every file with the bytes it had before.

## `sync`

`--target kicad` is the default. `--target altium` captures complete native schematic sheets into
`altium-schematic-layout.json` beside the script, after validating their identities and connectivity
against the generated baselines in `DIR/.fenolite/altium-generated/`. Its result holds `target`, `sheets`
and `files`; `--check` reports a stale snapshot with `sync.would-change`. Altium builds replay these bytes
only when the fresh generated baseline matches; otherwise `build.altium-layout-conflict` refuses all
writes. Captures that change circuitry give `sync.altium-connectivity-changed`; incomplete or unresolved
inputs give `sync.altium-unverified`. Both exit 5. The mutation protocol and input bindings apply to every
native sheet and baseline. Scope, evidence and recovery: `docs/altium-schematic-layout.md`.

`fenolite sync DESIGN.py --out DIR --to-source [--check]` copies the layout of a built project into the
source tree (`docs/lens.md`, "sync" and "edits.toml"). It is a mutating command: the writes follow
"Writing files", `.bak` files included. It runs `DESIGN.py` as `build` does and starts no external tool.
It reads the base record `DIR/fenolite-base.json`, `edits.toml` beside the script (otherwise a legacy
`placements.toml`, whose entries it carries into `edits.toml`: `sync.placements-migrated`) and the
schematic; a broken file exits 3 (`FEN-3004`). `--take` is a `build` option: here it is a usage error
(exit 2, `FEN-2001`, hint "resolve the conflict with fenolite build --take, then sync"). `sync` records;
it never resolves.

- `--to-source` is required (exit 2, `FEN-2001` without it), so a later direction cannot change what a
  bare `sync` does.
- The board `DIR/<design name>.kicad_pcb` must exist: otherwise exit 3, `FEN-3001`, with the hint to run
  `fenolite build` first. The refusals of a build over an existing board apply unchanged.
- **Writes** go beside the design script, not under `DIR`: `edits.toml` (the values the next build would
  write that differ from the script's, each over the script value), and `schematic-placements.toml` when
  `DIR` holds the schematic of the design; each only when its text would change. A run that changes
  nothing plans nothing and asks for no confirmation. A `sync.conflict` plans nothing.
- **`--check`** plans nothing and reports one `sync.would-change` (error) per file that would change,
  naming its first differing table: exit 5 when a committed file is stale or a property is in conflict
  (`sync.conflict`), 0 otherwise. `--check` with `--confirm` is a usage error (exit 2).
- **`result`**: `design`, `out`, `board` (the file name), `placements` (the number of parts whose position
  or rotation `edits.toml` holds), `edits` (the keys captured), `pending` (code changes the next build
  writes over an unchanged CAD value), `conflicts` (records),
  `unplaced` (matched parts that lie off the board and stay out of the file), `orphans` and `board_only`
  (references), `symbols` (the number of tables of `schematic-placements.toml`, or `null` when `DIR`
  holds no schematic), `files` (the names that change) and `script_output`.
- **Issues**: those of the board read, and the `sync.*` codes of `docs/lens.md`: `sync.would-change` and
  `sync.conflict` (errors), `sync.orphan`, `sync.net-dropped`, `sync.value-differs` (now only for parts
  without a base entry) and `sync.symbol-off-grid` (warnings), and `sync.placements-migrated` (info).
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
| `build.reserved-library` | error | the design names or authors a symbol library `fenolite`, or needs a power flag and holds a symbol `PWR_FLAG` in the library that holds the flag |
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

`fenolite capabilities` lists commands (`name`, `mutates`, `schema`, `hidden`), the flags every
command accepts (`global_flags`, `--progress` among them) and those of the mutation protocol
(`mutation_flags`: `--dry-run`, `--confirm`, `--plan`), backends,
experimental features, the evidence matrix, installed extras, detected external tools (`kicad-cli`, `java`, `docker`,
`gmsh`) with versions, and whether any enabled feature sends data off the machine. Agents should call it first.
A command whose examples need an external tool also lists `example_tools` (`export` and `render`:
`kicad-cli`); the test suites run such examples against a fake of the tool, and every other command's
examples run with no subprocess.

`result.experimental` lists, sorted by `name`, the features that may change their output, options or
issue codes in any release. Each Altium entry has the keys `name`, `command`, `option`, `write_kinds`,
`missing` (conditions per kind) and `evidence` (written as a backend's evidence), and its level is never one that counts as verified for
a release. Listing them runs no external tool, so the list is the same with `--no-tools`. An
experimental feature appears in `result.backends` only when it is a registered backend. Today the list
holds three entries, which share no write kind: the Altium PCB writer (`altium-pcb-writer`, write kinds
`altium_pcbdoc` and `altium_pcblib`, change c0035), the Altium schematic writer,
and `altium-support-writer` for the remaining matrix kinds (OutJob and SchDot).
Graduated kinds are excluded; an empty feature entry is omitted. The following
examples abbreviate the additional `missing` mapping:

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

Altium `write_kinds` are computed from the evidence matrix: only kinds that
satisfy the graduation rule appear there. The current nine kinds still remain
under `result.experimental`; no current kind is promoted. Packaged decisions are
checked against the register, own-readback tests, RT-A3 and current committed kit
evidence by `uv run python tools/gen_altium_graduation.py --check`. Discovery of
an installed wheel needs neither checkout evidence files nor external tools.

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

Each entry of `result.routers` holds `name`, `description`, `sends_data_offsite`, `builtin` and
`features` (change c0110): the sorted list of what the router takes beyond single nets, `pairs` and
`escape`, read from the router's `features` attribute without running anything. A router without the
attribute lists none. `direct` and `freerouting` list none; `kicadroutingtools` lists the features whose
gate outcomes hold (`docs/evidence/routing.md`, "Pairs and escape (c0110)"). `route` gives a router no
differential pair and no escape request unless it lists the feature. `short` (change c0228) marks a router
of short connections, not of whole boards, and `roles` (change c0244) a router that takes the role routes of
`--roles`: `octilinear` lists `pairs`, `roles` and `short`.

### The brief view and the command view

The default result grows with every backend and file kind. Two other views of the same command answer
an agent's first questions in a small reply; the default result is unchanged by them.

**`fenolite capabilities --brief`** says what is installed here, what it can do and where to read more.
`result` holds exactly:

| key | content |
|---|---|
| `fenolite_version` | the installed version |
| `commands` | every command that is not hidden, sorted by name: `name`, `summary` (its help line) and `mutates` |
| `targets` | `build`: the values of `build --target`, read from that command's parser (`altium`, `kicad`); `kicad`: the KiCad majors a build can target; `default`: the major written without `--kicad-version` |
| `tools` | as in the default view |
| `routers` | the registered routers, sorted by name: `name`, `available` and `reason` (why it is not available, else `null`) |
| `guide` | the pages of `fenolite guide`: `topic`, `title`, `summary` |
| `starters` | the starter projects of `fenolite init`: `name`, `summary` |
| `sends_data_offsite` | as in the default view |

- A router's availability comes from its own check, which runs `java -version` at most and never starts
  the router. With `--no-tools` no check runs, and `available` and `reason` are `null`.
- `targets.build` says that a target exists. It says nothing about how far the target is verified:
  the brief view holds no evidence level. Read `result.matrix`, `result.experimental` and
  `result.backends` of the default view for that, per file kind.
- The brief result is bounded: with `--no-tools` its JSON is under 300 bytes per listed command plus
  2 000 bytes, and a test keeps it there.
- `--brief` chooses another `result` for this one command; `--format concise` folds the issues of any
  command. They may be given together, and `--fields` works on the brief result.

**`fenolite capabilities --command NAME`** describes one command. `result` holds exactly `command` and
`global_arguments`. `command` is the command's entry of the default view (`name`, `mutates`, `schema`,
`hidden`, and `example_tools`, `paged` and `default_limit` when it has them) with three more keys:
`summary`, `usage` (one line that starts with `fenolite <name>`) and `arguments`. `global_arguments`
lists once the flags that every command takes (`--json`, `--fields`, `--kicad-version` and the others).
A hidden command is described when it is named exactly. The view runs no tool.

The arguments are read from the command's own parser (`fenolite.cli.describe`), so they cannot differ
from what `--help` prints, and `--dry-run` and `--confirm` are among the arguments of a mutating command
only. Each argument has exactly these fields:

| field | content |
|---|---|
| `name` | the name the parser stores the value under |
| `flags` | the option strings, such as `["-o", "--output"]`; empty for a positional |
| `kind` | `positional`, `option` (takes a value) or `flag` (takes none) |
| `type` | `integer`, `number`, `boolean` (a flag) or `string` |
| `choices` | the accepted values, sorted, or `null` |
| `default` | a JSON value, or `null` |
| `required` | whether the command line must hold it |
| `repeatable` | whether it may be given more than once or takes several values |
| `help` | its help text |

`--brief` and `--command` exclude each other (exit 2, `FEN-2001`). An unknown `NAME` exits 2 with
`FEN-2001`, and the hint names the three closest command names.

## Altium import

Reading an Altium file through the registered backend `altium` (change c0043, `docs/altium.md`, "Reading
Altium files") gives issues of the closed table `fenolite.backends.altium.adapter.IMPORT_ISSUE_CODES`,
after the readers' own issues and before the `model.*` findings. An error issue never stops an import.

| code | severity | meaning |
|---|---|---|
| `altium.import.bad-stack` | error | the copper chain of the board record holds fewer than two layers; the board is read with `F.Cu` and `B.Cu` |
| `altium.import.sheet-loop` | error | a sheet symbol names one of its own ancestors; the import does not descend |
| `altium.import.bad-length` | warning | a length text is not a decimal number in `mil` or `mm`; the entity that needs it is not mapped; exception: component bodies are retained with unknown projection |
| `altium.import.body-unknown` | warning | a body has unproved projection, model type or extent; retained with projection_unknown |
| `altium.import.model-unread` | warning | an embedded 3D model's stream is missing or does not inflate (`fenolite view`, change c0193); its body keeps no model |
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
| `altium.import.pin-map` | info | count of pin map records that name no pad, or a pad another pin holds: such a pad is left off the pin and the record is kept in the component's bag; a record of several pads is applied and not counted |
| `altium.import.bus-member` | info | count of bus members without a net |
| `altium.import.harness-entry` | info | count of harness entries without a net |
| `altium.import.extra-board` | info | a project lists more than one PCB document; only the first is read |
| `altium.import.linked-by-designator` | info | count of PCB components linked to a schematic component by designator, not by unique-id path |
| `altium.import.pcb-only-net` | info | count of nets of the PCB document that the sheets do not hold; they are added to the circuit |
| `altium.import.rule-unmapped` | info | count of rule records of one rule kind that do not map, with the mapper's reasons |
| `altium.import.unmapped` | info | counts, by kind, of the records that gave no model entity, and the storages kept as bytes |

## route

`fenolite route PATH --router NAME [--nets GLOB]... [--order GLOBS]... [--rip] [--include-zone-nets] [--no-plane-fanout] [--require-complete] [--router-path PATH] [--router-python PATH] [--router-option KEY=VALUE]... [--allow-offsite] [--timeout SECONDS] [--escape REF[=grid|perimeter]]... [--pairs-as-nets] [--roles critical [--group NAME]... [--roles-file FILE]] [--gate drc [--kicad-cli PATH]] [-o FILE]` routes the nets that still have open connections. `PATH` accepts a board, matching project or folder. External tools receive a temporary model-authored project copy; only routed tracks, arcs and vias are merged back. `--out` is relative to the working directory. The normal dry-run/confirm receipt protocol applies.

- **Selection.** A net is selected when it matches `--nets`, has two or more pads and has an open connection on the board, computed from the board after the rip (`docs/analyses.md`, "Open connections"). Copper of its own does not exclude a net; a closed net is never given to the router; a zone net needs `--include-zone-nets`.
- **`--rip`** removes the tracks, arcs and vias of the matching nets first, but keeps locked copper and script copper (`result.rip_kept`).
- **Verdict.** `routed` and `unrouted` are the selected nets without and with an open connection after the merge, whatever the router listed.
- **Write.** The board is planned when the command added a track, an arc or a via, no issue is an error, and the text changed or `--out` is given. Copper of nets that stay open is written too.
- **`--require-complete`.** A selected net still open adds `route.incomplete`, plans no write and exits 5.
- **`--timeout SECONDS`** is the time budget of the whole routing step, for every router: each process a router starts gets the time that is left. Without it the router's own default applies (900 s for `kicadroutingtools` and `freerouting`); no value stands for the default, so `--timeout 600` is 600 s. A value that is not a positive number exits 2 with `FEN-2001`. The built-in `direct` router starts no process and ignores it. When the budget ends, the copper of the router runs that finished is merged and planned as any routed copper, the run under way is stopped and gives none, and one `route.budget-exhausted` (warning) is reported; the exit code stays 0 when no issue is an error. Run `route` again to continue with the nets still open.
- **`--order GLOBS`** (repeatable; `fnmatch` globs on the net name, several separated by commas: `--order "GATE_*,SENSE_*" --order "*"`; change c0197) puts the selected nets in tiers: a net takes the index of the first value one of whose globs it matches, and a net that matches none comes last. An empty glob exits 2 with `FEN-2001`. A router routes tier after tier, and the copper of earlier tiers is fixed for later ones. `--order` changes no selection.
- **Rules.** The design gets the net classes of the project file and the lifted rules of the rules file beside the board, and the project's `min_copper_edge_clearance` as one board-wide `edge_clearance` rule. A file that cannot be read gives `route.project-unread`.
- **Plane layers and plane nets.** A copper layer of the KiCad type `power` is a plane layer (`result.plane_layers`), and a net with a zone on one is a plane net. A plane net is never given to a router, also with `--include-zone-nets`; each one that `--nets` selects gives `route.plane-net`. `--rip` rips the selected plane nets as other nets.
- **Plane fan-out.** Before the router runs, each SMD pad of a selected plane net gets one short track and one through via, found by a deterministic search (`docs/routing.md`, "Plane fan-out"); a pad without room gives `kicad.fanout.failed` and stays open. `--no-plane-fanout` skips the step. The copper is written also when no net goes to a router or the router adds nothing. `result.plane_fanout` holds `nets` (the plane nets fanned out, sorted), the counts `pads`, `joined`, `tracks` and `vias`, and `failed` (`REF-NUMBER` of each pad left open, in board order); with `--no-plane-fanout`, `nets` is empty and the counts are 0.
- **Differential pairs.** Two selected nets that KiCad pairs by name (`docs/routing.md`, "Differential pairs and escape") and that share a class with a pair width and gap form a pair (`routing.pairs.job_pairs`). A router whose `features` (below) lack `pairs` gets neither net: each pair gives `route.pair-skipped`, whose hint names `--pairs-as-nets` and the routers that route pairs. A pair with one net selected, nets in two classes, or no pair width or gap is left out the same way. `--pairs-as-nets` gives the two nets as single nets to any router, with one `route.pair-uncoupled` per pair.
- **Escape.** `--escape REF[=grid|perimeter]` (repeatable, `fnmatch` on references) asks a router with the feature `escape` to escape the pads of the matching parts before it routes; the kind is found from the centres of the part's surface pads unless given, and a suffix other than `=grid` or `=perimeter` exits 2 with `FEN-2001`. A pattern that matches no part, a part without a selected net, and every request to a router without the feature give `route.escape-skipped`.
- **Width guard.** A routed track or arc narrower than the width the job gave its net (the pair width for a pair net) gives one `route.width-below-job` per net, naming the smallest width and the width asked; the copper is kept. With `freerouting` the hint names `--router-option fanout=off`.
- **Routing layers.** A net's tracks may use the copper layers that are not plane layers and that no `no_tracks` rule forbids to it; a selected net left with none gives `route.no-layer` and is not routed.
- **`--gate drc`** judges the copper the command adds or removes with `kicad-cli` DRC and writes the board without the tracks and vias that bring new findings ([DRC gate](#drc-gate)); the verdict and the counts are those of the kept board.
- **Resumed.** The copper of each router process that finished is kept in the state folder until the board is written. The same call made again on the same board reuses it and does not route those nets again: the reply then holds one `route.resumed` info and `result.resumed` (`runs`, `nets`), and `tracks` and `vias` count the reused copper too. Without a record `result.resumed` is `null`. See `docs/routing.md`, "The job record". The recorded copper is merged after the plane fan-out, as the router of the earlier call saw the board. A dry run that the budget cut keeps the record, so the same dry run made again goes on with the nets that were not attempted.

`result` contains `board`, `router`, `tool_version`, `selected`, `routed`, `unrouted`, `open`, `connections`, `tracks`, `vias`, `ripped`, `rip_kept`, `fills_stale`, `budget`, `runs`, `not_attempted`, `resumed`, `plane_layers`, `plane_fanout`, `pairs`, `escape`, `gate` ([DRC gate](#drc-gate)) and up to 20 sanitised `log` lines. `pairs` lists `{name, positive, negative, width, gap, routed}` for the pairs given to the router (`routed`: both nets are in `routed`), and `escape` lists `{ref, kind, pitch, nets}` for the escape requests given to it; `selected` names every net given to the router, pair nets included. `open` holds one object per net of `unrouted`, sorted by name: `net`, `islands` and `connections`, each connection with `a` and `b` (`kind`: `pad`, `track`, `arc` or `via`; `where`; `position`; `layers`) and `length` in nanometres; `--limit` and `--cursor` page it. `connections` holds `before` and `after`, the open connections of the selected nets before the router and after the merge. `rip_kept` holds `locked` and `script`, the items of the ripped nets that `--rip` kept. `fills_stale` is true when the board has fills and the command added copper. `budget` holds `seconds` (the budget the step ran with: `--timeout`, else the router's default; `null` for a router without one), `spent` (the seconds the router took, rounded to 0.1; 0.0 for a router without a budget) and `exhausted` (whether the budget ended before every run was done). `runs` holds one object per process the router started, in order: `tier`, `nets` (a count), `seconds` (rounded to 0.1) and `outcome` (`done`, `failed`, or `cut` for the run the budget stopped). `not_attempted` lists the nets of the runs that were never started; they are in `unrouted` too. `spent` and the `seconds` of a run are wall-clock times and differ from one run to the next. `resumed` is `null`, or holds `runs` and `nets`: the router runs of an earlier call whose copper was reused, and the nets they routed. Evidence is `UNVERIFIED` (`KICAD-VERIFIED` after `--gate drc` left no new finding); run `check` after routing and refill zones before checking. The exit code is 5 for `route.bad-item`, `route.tool-failed` or `route.incomplete`, and 0 otherwise.

| code | severity | when |
|---|---|---|
| `route.bad-item` | error | a router returned malformed copper |
| `route.budget-exhausted` | warning | the budget of the step (`--timeout`) ended before every router run was done: the message gives the budget, the nets of the run that was stopped and the nets not attempted; the copper of the finished runs is kept and written |
| `route.check-refused` | warning | the octilinear router removed the copper of a connection because the copper check found something new on it; the message names the net and the finding |
| `route.constraint-not-sent` | warning | the router takes no option for plane layers or for the layers a net is kept to (KiCadRoutingTools); one per run, naming them |
| `route.copper-removed` | warning | the router dropped existing copper |
| `route.escape-skipped` | warning | an `--escape` pattern matched no part, the part has no selected net, or the router has no `escape` feature |
| `route.fill-stale` | info | changed copper invalidated filled zones |
| `route.incomplete` | error | with `--require-complete`, a selected net still has an open connection after the merge: the number of open nets and the first five; nothing is written |
| `route.net-declared` | info | Freerouting: nets outside the job stayed declared in the design file, because their class clearance is larger than the default rule; the message gives their count and the first five |
| `route.no-layer` | warning | track layer rules forbid every routing layer to a selected net; it is not routed |
| `route.optimizer-cut` | info | Freerouting with `optimize=on`: the optimizer run wrote no session in the time left; the copper of the first run is kept |
| `route.option-ignored` | warning | a `--router-option` the router does not support was ignored |
| `route.pair-not-routed` | warning | the octilinear router left a pair open: no shape gave coupled tracks in clearance, every shape was longer than `max-length`, or a net of the pair has other than two pads |
| `route.pair-skipped` | warning | a differential pair was left out with both its nets: the router has no `pairs` feature, one net is not selected, the nets are in two classes, the class has no pair width or gap, or the router does not pair names of that form; the hint names the way out |
| `route.pair-uncoupled` | info | with `--pairs-as-nets`, a pair was routed as two single nets |
| `route.partial` | info | the router returned copper for a net that stays open; the copper is kept and written, and the message gives the number of items |
| `route.plane-net` | info | a plane net that `--nets` selects is not given to a router; its pads reach the plane through fan-out vias |
| `route.project-unread` | warning | the project file or the rules file beside the board could not be read: without the project every net takes the default class values, without the rules file the rules are not given to the router |
| `route.resumed` | info | the copper of router runs that finished in an earlier call of the same job was reused; the message gives the number of runs and of nets |
| `route.role-kept` | info | role mode: a group that copper already joins still has role findings and was left as it is; the message names the findings, the hint `--rip` |
| `route.role-none` | info | role mode: no confirmed or declared gate loop or Kelvin pair to route; nothing is planned |
| `route.role-placement` | info | role mode: a gate loop's placement bound is above the user's `gate_max`; the message gives both |
| `route.role-refused` | warning | role mode: a routed group was removed whole because a role finding got worse; the message names the group, the code and both measures |
| `route.role-unconfirmed` | info | role mode: inferred groups were not routed; the message gives their count and names |
| `route.role-unrouted` | warning | role mode: a gate loop or Kelvin pair was not routed; the message gives the reason, and `result.roles` the proposal and its commands |
| `route.tool-failed` | error | the external router failed |
| `route.tool-missing` | error | the configured router is unavailable |
| `route.tool-unpinned` | warning | external router checkout is not the supported pinned version |
| `route.unrouted` | warning | a selected net still has an open connection after the merge: the message gives the number of open connections and the shortest one, and says so when the router listed the net as routed |
| `route.width-below-job` | warning | routed copper is narrower than the width the job gave its net; the message gives the smallest width and the width asked |
| `route.zone-net-skipped` | info | a zone net was omitted without the inclusion flag |
| `kicad.fanout.failed` | warning | no fan-out via fits beside an SMD pad of a plane net; the pad stays open, and the message names the pad, the net and what blocked the first candidate |

**Role mode** (change c0244). `--roles critical` routes the open connections of the board's confirmed or
declared gate loops and Kelvin pairs, and nothing else, with a router whose features list `roles`
(`octilinear`); another router is `FEN-2001` with a hint naming those that have it. The roles come from
`.fenolite/rules.json` of a built project, else the role document beside the board, or `--roles-file FILE`;
`--group NAME` (repeatable) limits the plan to the named groups. `--group` or `--roles-file` without
`--roles`, and `--nets`, `--escape`, `--order` or `--pairs-as-nets` with it, are `FEN-2001`. No group to
route gives exit 0 with one `route.role-none`. The routed tracks and vias are locked; each routed branch
gets a rule area `role.corridor.<group>.<net>` that forbids pours only, replacing one of that name.
`--rip` removes the branches of the planned groups first, keeping locked and script copper (`rip_kept`).
`--gate drc` judges each group's copper and corridors together. `--require-complete` adds one
`route.incomplete` (exit 5, nothing written) when a group stays unrouted or refused. The verdict counts
role connections: `selected`, `routed` and `unrouted` hold the nets of the role routes, `connections` the
role connections before and after, and no `route.unrouted` is given. `result.roles` holds one entry per
group of the plan, sorted by tier and name: `group`, `kind` (`gate_loop`, `kelvin_pair`, `hot_loop`),
`status` (`routed`, `complete`, `kept`, `refused`, `unrouted`, `skipped`), `connections` (`key`, `net`, `a`,
`b`, `layer`, `form`: `single`, `pair`, `side-by-side`, `stacked` or `plane-return`, `length`, `vias`),
`findings_before` and `findings_after` (`code`, `severity`, `measure`), `reason` and `proposal` (`kind`,
`text`, `command`, `region`) when not routed, `copper` and `corridors` (ids). `plane_fanout` is `null`. The
role options of `octilinear` are `gate-vias`, `kelvin-vias`, `keep-away`, `z-shapes`, `rounds` and
`max-length` (no default in role mode); see `docs/routing.md`, "Role mode".

`fenolite route --router octilinear` (change c0228) is built in, runs no process and places no via: for each open connection it tries a straight segment, 45° then straight, straight then 45° and the two L shapes on each allowed layer, and keeps the first that keeps the clearance in force plus 2 µm from other nets' copper and holes, the edge clearance, and no acute angle at its ends. `--router-option max-length=LENGTH` (default 20 mm) bounds a shape: a connection longer by every shape stays open with `route.unrouted`; `--router-option rounds=N` (default 3) routes the failed connections first in the next round. A pair of two pads per net is routed as two tracks at the pair gap (`route.pair-not-routed` otherwise). The copper check judges the result, and a connection with a new finding is removed (`route.check-refused`). Its features are `pairs`, `short` (a router of short connections, not of whole boards) and `roles` (the role mode of `--roles critical`, change c0244). The job's `extra` gives every router `clearance` and `copper_check` (`docs/routing.md`, "octilinear").

`fenolite route --router freerouting` runs Freerouting through a Specctra design file. `--router-path` names its jar (or `docker:<image>`), `--router-option max-passes=N` its passes, `--router-option optimize=on` adds a run with its optimizer on the time left (the optimizer is off otherwise), and `--router-option fanout=off` turns its fanout stage off (it is on by default); its automatic neck-down is always off; the board needs a closed outline. The design file declares only the nets of the job, and one run is made per tier. `--router kicadroutingtools` runs one process per group of nets of equal track width and via sizes; `--router-option group-nets=N` splits a group, and its options `nets`, `output` and `overwrite` are ignored. Its issues also carry the `specctra.*` codes: `specctra.unknown-padstack` and `specctra.session-moved` (error, no copper is taken), `specctra.pad-approximated` and `specctra.plane-skipped` (warning: a zone on a plane layer without an outline gives no plane), `specctra.rounded`, `specctra.renamed`, `specctra.unknown-list`, `specctra.rule-not-sent` (a rule the file cannot carry) and `specctra.rule-widened` (a layer clause dropped from a clearance rule) (info). The file declares the plane layers `(type power)` with one plane per zone, keeps nets to their layers with `use_layer`, and carries class clearances, class-to-class clearances, widths per layer and the edge clearance (`docs/routing.md`, "What each router is given"). While the router is listed with `sends_data_offsite: true`, the command exits 2 without `--allow-offsite`. See `docs/routing.md`. The jar is `--router-path`, else `FENOLITE_FREEROUTING_JAR`, else the file that `fenolite fetch freerouting --confirm` installed in the tools folder ([fetch](#fetch)); without a jar the command exits 6 with `FEN-6001` and the hint `run 'fenolite fetch freerouting --confirm'`. `route` itself opens no network connection.

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

## tidy

`fenolite tidy PATH [--nets GLOB]... [--prune] [--straighten] [--chamfer] [--zones] [--leg LENGTH] [-o FILE] [--drc | --gate drc] [--kicad-cli PATH] [--timeout SECONDS]` cleans the routed copper of a KiCad board, and `fenolite tidy PATH [--nets GLOB]... --report [--compare REFERENCE]` reports its routing style (changes c0208 and c0214; `docs/copper.md`, "Copper tidy"). `PATH` accepts a board, matching project or folder; `--out` is relative to the working directory, otherwise the board is replaced. The usual `--dry-run` plan and `--confirm` receipt protocol applies.

- **Steps.** `--prune`, `--straighten` and `--chamfer` select steps; with none, all three run, in the order `prune`, `straighten`, `chamfer`. `--nets GLOB` (repeatable, `fnmatch` on net names) narrows the nets; without it every net is tidied.
- **Prune** removes, pass after pass, each unlocked track or arc with a free end (an end whose disc of the track width touches no pad, via, track, fill or zone outline of its net) and each unlocked via joined on fewer than two copper layers, only when its net keeps its connected groups without it; one that would split its net stays with `tidy.kept`.
- **Straighten** replaces each run (two or more unlocked tracks of one net, layer and width chained through joints that join nothing else, touching nothing of the net between its two ends) by a shape of at most three segments at 0°, 45° or 90° with fewer weighted turns (45° weighs 1, 90° weighs 3, an acute turn is never made, a turn inside a pad the run ends on is free, joints with tracks at the ends count), when it keeps the net's groups and adds no copper-check finding. Nets of a differential pair or selected by a `length`, `skew` or `diff_pair_skew` rule stay, with `tidy.straighten-skipped`.
- **Chamfer** replaces each joint of exactly two unlocked horizontal or vertical tracks of one net, layer and width at 90°, where nothing else of the net touches, by a 45° track. The leg is `--leg`, else twice the width, and at most half of the shorter track; a track that two chamfers cut to nothing is removed. A horizontal or vertical track that ends at 90° on the middle of a track of its net, layer and width, or on the joint of two collinear ones, gets a 45° entry on the side with more bar. With `--zones` (which needs the chamfer step), each convex right-angle corner of the outline of an unlocked zone of a selected net is cut by a 45° edge (legs `--leg`, else 1 mm, at most half of each edge), unless an item of the net that touched the outline would lose its contact; a cut zone loses its fill. A chamfer that changes its net's groups, or adds a copper-check finding, is undone with `tidy.chamfer-undone`.
- **Never touched.** Locked tracks, arcs and vias and script copper (`docs/copper.md`), and every net that holds copper that could not be shaped (`tidy.net-skipped`).
- **Check.** Each edit is judged by the copper check with the rules of the project beside the board (`check`, stage `copper.clearance`), and the whole tidied board once more: a finding it lacked before gives `tidy.check-failed` and no write.
- **`--drc`** runs `kicad-cli` DRC (`--kicad-cli`, else the tool `check` finds; exit 6 without one) on copies of the board as it is and as tidy would write it, with the project files. A violation type with more entries after gives `tidy.drc-new` and no write; otherwise the evidence is `KICAD-VERIFIED` with the tool version.
- **`--gate drc`** judges the edits with `kicad-cli` DRC instead and writes the board without the edits whose items bring new findings, each edit kept or undone whole ([DRC gate](#drc-gate)); `--drc` with it is a usage error.
- **`--report`** runs no step and plans nothing (no `--dry-run` needed; a step option, `--zones`, `--leg`, `--drc`, `--gate` or `--out` with it is a usage error). Per net class (from the project beside the board, else `Default`) and copper layer it counts the joints of two track ends at 45° (`joints_45`), at 90° (`joints_90`), `acute` and `other`, the `jogs` (tracks shorter than three widths between two turning joints) and the length per track width; and per class the vias. Each acute joint is a `tidy.acute` warning. `--compare REFERENCE` (implies `--report`) adds the same table of another KiCad board.

`result` holds `board`, `target`, `steps`, `nets` (the number of selected nets), `changed`, `edits`, `counts` (edits per `<step>.<reason>`), `removed` and `added` (item counts), `copper_check` (`before`, `after` and `new` finding counts), `drc` (`null`, or `tool_version`, `before`, `after` and `new`, the violation types that grew), `gate` ([DRC gate](#drc-gate)), `fills_stale` and `style` (`before` and `after`, the `counts` of the style report). Each edit holds `step`, `reason` (`free-end`, `via-under-two-layers`, `fewer-turns`, `right-angle`, `t-joint` or `zone-corner`), `net`, `layer` (`null` for a via or a zone corner), `at` (`x`, `y` in nanometres) and the ids `removed`, `replaced` and `added`; `--limit` and `--cursor` page `edits`. The board is planned when an edit was made and no issue is an error. Evidence is `INFERRED` (`H-K-TIDY-DRC`, `H-K-CONN-PARITY` and the rows of the copper check), `UNVERIFIED` when the copper check could not judge all of the board, and `KICAD-VERIFIED` after `--drc` found nothing new. The exit code is 5 for `tidy.check-failed` and `tidy.drc-new`, 0 otherwise. Under `--report`, `result` holds `board`, `steps` (empty), `changed` (false), `report` and `compare` (`null`, or the reference's `board` path with its own `rows`, `vias` and `counts`); `report` holds `rows` (`netclass`, `layer`, `joints_45`, `joints_90`, `acute`, `other`, `jogs`, `widths` as `width` and `length` in nanometres), `vias` (`netclass`, `count`) and `counts` (the sums); the evidence is `INFERRED` (`H-G-TIDY-STYLE`).

| code | severity | when |
|---|---|---|
| `tidy.check-failed` | error | the copper check finds on the tidied board a finding the board before lacks; nothing is written |
| `tidy.drc-new` | error | with `--drc`, a DRC violation type has more entries on the tidied board; nothing is written |
| `tidy.acute` | warning | with `--report`, two tracks of one net meet at an angle below 90° |
| `tidy.net-skipped` | warning | a selected net holds copper that could not be shaped and is left as it is |
| `tidy.project-unread` | warning | the project or rules file beside the board could not be read; the copper check runs without it |
| `tidy.chamfer-undone` | info | a chamfer, a T-joint entry or a zone cut was undone: it changed its net's groups, added a copper-check finding or left an item without its zone |
| `tidy.fill-stale` | info | tidy changed copper of a board with filled zones; run `fill` before `check` |
| `tidy.kept` | info | a track or an arc with a free end stays because its net would fall apart without it |
| `tidy.straighten-skipped` | info | a net in a differential pair or with a length rule keeps its runs as they are |

## library

`fenolite library PATH --out LIB.pretty | --diff LIBRARY` makes a footprint library from a KiCad board, or
reports how a library differs from it (change c0223; `docs/conversion.md`, "3D models", for the derived
libraries of a conversion). `PATH` accepts a board, matching project or folder.

- **`--out`** (a relative `.pretty` folder) plans one `<name>.kicad_mod` per footprint, under the usual
  `--dry-run` plan and `--confirm` receipt protocol, written for the board's major. Each footprint is the
  board's instance brought back to its origin, rotation 0 and the top side (placement, uuid, path and pad
  nets dropped; Reference `REF**`, Value the name), named after the name of its library link. A second
  instance of one name that differs, its uuids aside, is written as `<name>_2` (then `_3`) with
  `library.instances-differ`.
- **`--diff LIBRARY`** compares each derived footprint with `LIBRARY/<name>.kicad_mod` and writes nothing,
  even with `--out`: `pads` (number, kind, shape, size, position, angle, layers, drill), `silkscreen` and
  `courtyard` (the graphics on `F.SilkS`/`B.SilkS` and `F.CrtYd`/`B.CrtYd`), `models` (the paths) and
  `fields` (the properties other than Reference and Value); a file the folder lacks is `missing`.

`result` holds `board`, `library` (the folder written or compared) and either `footprints` (`name`,
`source`, `refs`) or, with `--diff`, `drift` (`name`, `kinds`); `--limit` and `--cursor` page that list.
Evidence is `INFERRED` (`H-K-LIB-FROM-BOARD`). The exit code is 5 when a footprint drifted, 2 without
`--out` or `--diff` or for an `--out` that is not a relative `.pretty` folder, 0 otherwise.

| code | severity | when |
|---|---|---|
| `library.drift` | error | with `--diff`, a footprint differs from the library's or the library lacks it |
| `library.instances-differ` | warning | two instances of one name differ; the second is written as `<name>_2` |
| `library.not-local` | warning | a bottom-side footprint could not be flipped back; it is left out |

## check

`fenolite check PATH [--stages A,B] [--kicad-cli PATH] [--timeout SECONDS]` checks a KiCad project
read-only (`--exclude` alone writes: "Writing a DRC exclusion" below). `PATH` is a `.kicad_pcb`, a `.kicad_pro` (the board of its stem) or a folder holding one
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
`circuit.rules`, `length.rules`, `placement.rules` and `roles.rules` need none either, and are default
stages. `parity` needs none either for a project that `build` wrote.

| stage | runs on | evidence |
|---|---|---|
| `model.validate` | the board model (native) or the `.fenolite/` model (built) | the reader's level (native), `INFERRED` (built) |
| `circuit.rules` | Fenolite's own judge of the interface parameters of the `.fenolite/` model (change c0252, "Circuit stage" below): rails, logic levels, bus pull-ups, companions and split device ports; no tool runs and no board is read. Skipped with `no-model` without a model (a native board) and with `no-parameters` when the model holds nothing to judge | `INFERRED`, lowered to the lowest evidence label of the device records whose ports it judged |
| `erc.kicad` | `kicad-cli sch erc` on the copy set, built and native input alike; every violation becomes a located issue. Skipped with `no-schematic` when the project has no `<stem>.kicad_sch` | ERC report reader and oracle combined, `kicad-cli <version>`; `UNVERIFIED` without a report |
| `copper.clearance` | Fenolite's own exact check of shorts and clearance on the board model, native and built alike, with the rules of `<stem>.kicad_pro` and `<stem>.kicad_dru`; no tool runs | the lowest of the copper check (`INFERRED`), the board reader and the project and rules readers; `UNVERIFIED` when part of the copper or of the rules went unjudged |
| `length.rules` | Fenolite's own verdict on the `length`, `skew` and `diff_pair_skew` rules of `<stem>.kicad_dru` (`docs/analyses.md`, "Length rules in check"), on the net lengths as the target KiCad major counts them; no tool runs | the lowest of the stage (`INFERRED`, `H-K-NETLEN-RULES`), the board reader, the rules readers and the length facts; `UNVERIFIED` with `length.input-missing` |
| `placement.rules` | Fenolite's own placement rules and measures on the board model, without a tool: on a project that `build` wrote, the `near` rules of `.fenolite/rules.json` judged on the pad positions; on every board, the wire length and the congestion of the placement (`docs/placement.md`) | the board reader's level when no rule was judged; the lowest of it and `INFERRED` when one was |
| `roles.rules` | the net roles of the board judged against its copper, as `fenolite roles --check` judges them (`roles` below, `docs/roles.md`): the roles of `.fenolite/rules.json` of a built project or of the role document beside the board, with the inferred ones; no tool runs. Skipped with `no-roles` when the board has no stored or declared role | `INFERRED`, with the role hypotheses and the analyses' evidence |
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
does not read itself, in a run without `kicad-cli`), `no-frame` (`placement.rules` when the reader gives
no pad positions), `no-roles` (`roles.rules` on a board without a stored or declared role), `no-model`
and `no-parameters` (`circuit.rules`) or `oracle-unstable` (two refill runs differ; never counted in the
envelope). A skipped stage carries `UNVERIFIED`. The envelope evidence is the lowest level of
the stages that ran and of those skipped for `read-refused` or `cache-unreadable`; `UNVERIFIED` when
none counts. `result.project` holds `board`, `built`, `files` and `skipped`, names relative to the
project folder. The `drc.kicad` summary holds `tool_version`, `canary`, `canary_reason`,
`canary_removed`, `violations`, `by_type`, `by_severity`, `unconnected`, `excluded`, `tool_writes`,
`violations_judged`, `parity`, `parity_judged`, `types` and `limits`. Whenever a report exists, each violation,
unconnected item and parity entry is one issue and `violations_judged` is `true`; `types` maps each
emitted `kicad.drc.<type>` code to KiCad's raw type. The `erc.kicad` summary holds `tool_version`,
`sheets` (the sheets of the report), `violations`, `by_type`, `by_severity`, `excluded`,
`ignored_checks` (the checks the project sets to ignore; KiCad 10 lists them, KiCad 9 does not),
`types` and `tool_writes`. The `zone.fill` summary holds `tool_version`, `zones`, `current`, `unfilled` and `stale`. An unrouted board therefore exits 5: its unconnected items are errors. The `render` summary holds
`tool_version` and `views` (`name`, `bytes`, `sha256`; sorted by name); the hash of an SVG leaves out its
`<title>` line, where `kicad-cli` 9.0 writes the date, so two checks give the same output.

**Circuit stage.** `circuit.rules` (change c0252) stands right after `model.validate`, in the KiCad and
the document pipeline alike, and reads only the `.fenolite/` model of a built project; `fenolite build` runs
the same judge on the model it builds and adds its issues to the envelope, an error stopping the write. A
rail is the `hv` net of a `power` interface or port: its voltage is the intersection of the values that the
design rail and the `out` power ports set, its sources are the `out` power ports and its loads the `in`
ones; a block's `out` port hides the `out` ports inside it on the same rail (its promise replaces them), and
a block's `in` port that states `current` hides the `in` ports inside it. Two logic ports with the same
reference rail always pass; otherwise three worst-case comparisons are made (high, low and withstand), and a
threshold that is not stated is reported, never assumed. On an I2C line the pull-up rail drives the high
level. The codes:

| code | severity | when |
|---|---|---|
| `circuit.rail-voltage` | error | the set voltages of a rail do not meet, or the rail is not within the range an `in` power port accepts |
| `circuit.rail-current` | error | the sum of the loads' upper draws exceeds the sum of the sources' lower capacities |
| `circuit.rail-sources` | error | two or more sources drive a rail that is not `shared`, unless every source port has `share` |
| `circuit.rail-unset` | warning | ports state limits and no voltage is set, or loads state a draw and no source states a capacity |
| `circuit.logic-level` | error | across reference rails: output high below input high, output low above input low, or the driver's rail above the reader's `abs_max` |
| `circuit.logic-unknown` | warning | across reference rails, a value one of those comparisons needs is not stated |
| `circuit.bus-pullup` | warning | an I2C pull-up goes to a rail other than the bus reference, lies outside the accepted `pullup` range, or gives more current than a bus port's `output_current_max` |
| `circuit.requires-missing` | warning | a declared companion (`pullup`, `supply`, `chip_select`) is absent |
| `circuit.port-split` | warning | the pins of one member of a device port are on two nets; that member is not judged |

The summary holds `rails`, `judged` (the rails with a voltage to judge against), `halves` and, since
change c0253, `requirements` and `corners`. Waivers of `circuit.*` findings come with change c0274.

**Contracts in the circuit stage** (change c0253; `docs/contracts.md`). The same stage judges the electrical
contracts: each device part's `abs_max` ratings (derated by the script's `design.derating` policy; Fenolite
ships no derating value) and `operating` ranges (exact) against the voltages and currents its nets carry,
the expectations of `design.expect` and `b.expect`, and the test rig of `design.rig`. Applied values come
only from what the user stated: a rig element, a rail, a declared or confirmed net role, a ground. The
command resolves each component's `fenolite.device` record (the design's own records at build; at check,
`devices/` of the project folder or of its parent, then the shipped devices) and classifies the parts with
`fenolite.roles.classify`, and passes both to the stage (`checks` imports neither the catalog nor the
roles). `summary.halves` is `{"rails": "ran" | "no-parameters", "contracts": "ran" | "no-contracts"}`;
the stage is skipped with `no-parameters` only when both halves have nothing (`no-contracts`: no device part,
no expectation and no rig element). The thirteen contract codes:

| code | severity | when |
|---|---|---|
| `circuit.rating-voltage` | error | a voltage across a two-pin part, of a pin from its device's ground function, or between two functions (`[[limits]]`) exceeds the `abs_max` rating or the derated limit |
| `circuit.rating-current` | error | a regulator's output (the loads of its `out` power port's rail), an inductor's or a shunt's series current, or a single pin's net current exceeds the rating |
| `circuit.rating-power` | error | a resistor's or shunt's worst-case power (V²/R, or I²R of a shunt) exceeds the rating |
| `circuit.rating-temperature` | error | the ambient range (`design.operating`) is not within the `abs_max` temperature range less the margin |
| `circuit.operating-range` | error | an applied range is not within an `operating` range |
| `circuit.expect-failed` | error | an expectation holds for none of the ranges |
| `circuit.expect-unsure` | warning | an expectation holds for part of the ranges |
| `circuit.expect-unknown` | warning | an expectation reads a handle that cannot be resolved or bounded |
| `circuit.value-conflict` | warning | stated sources of different kinds give one net voltages that do not overlap |
| `circuit.device-changed` | warning | the record resolved now differs from the digest the build recorded |
| `circuit.value-unknown` | info, warning | rows not judged for a missing input: one count, or one warning per row under `design.contracts(unknown="warning")` |
| `circuit.rating-missing` | info, warning | parts without a record or without a rating for a check that applies |
| `circuit.policy-missing` | info | ratings judged at 100 % because no derating rule covers them |

Every row and expectation whose value reads a rig supply is also evaluated at each corner (each supply at
its minimum and at its maximum, `bench=max,aux=min`); a failing row's issue names its failing corners, and
the corners never change a verdict. `summary.corners` is the number of corners, or `too-many-supplies`
above six supplies. The stage evidence is `INFERRED` with `H-G-CIRCUIT-EXAMPLE`, lowered to the lowest label
of the device records whose limits it judged.

**The requirement table** (change c0253). `summary.requirements` of `circuit.rules` and of `roles.rules`,
and `result.requirements` of `fenolite roles --check`, are lists of rows sorted by `id`: `id`
(`<code>:<subject>[:<key>]`, such as `circuit.rating-voltage:C1:voltage` or `circuit.expect:buck1/expect#1`),
`check` (the code the row reports), `entities` (entity ids), `subject`, `quantity`, `unit`, `value` (or
`null`) and `limit`, each `{range, text, source, basis}` where `range` is c0246's encoding (`unit`, and `low`
and `high` as `{m, e}`) and `source` is `device`, `role`, `policy` or `user`, the limit also with `evidence`
and `kind` (`abs_max`, `operating`, `requirement`); `corners` (`{corner, status, text}`), `status` (`pass`,
`fail`, `unsure`, `unknown`), `severity` and `missing` (what is not stated, for an `unknown` row). No number
of the table is a JSON float.

**Length rules.** `length.rules` (KiCad input only; the Altium pipeline neither runs nor names it)
judges the rules of the kinds `length`, `skew` and `diff_pair_skew` of the project's rules file on the
total length of each net, as KiCad counts it for the major of the project file (tracks, arcs, via heights
from the stack-up, die lengths; `fenolite analyze --kinds length` gives the same totals). A net is governed
by the last matching rule of its kind in KiCad's rule order; `skew` and `diff_pair_skew` count as one kind,
since KiCad writes both as its `skew` constraint. A total below `min` or above `max` of a length rule is
`length.out-of-range`, with the rule's severity; `opt` is not judged, and a net of pads only is judged at
length 0. A skew rule groups the nets it governs (a `diff_pair_skew` rule each pair apart); a net whose
length differs from the longest of its group (ties to the first name) by more than `max` is
`length.skew-out-of-range`, with the rule's severity; the longest net is never reported. Without a rules
source or without length facts, `length.input-missing` says what was judged without. The summary holds
`rules` (`{"length": n, "skew": n}`), `nets` (the governed nets judged), `major` and `stackup` (of the
facts, `null` when none were asked for). The stage is skipped with `read-refused`.

**Placement rules.** `placement.rules` judges the `near` rules of a built project
(`design.near()`, `docs/dsl.md`) on the pad positions of the board, pad centre to pad centre, and measures
every board. Its summary holds `rules`, the counts by rule family (`{"near": {"judged", "failed",
"skipped"}}`, every count 0 on native input; on a built project with a height limit also
`{"height": {"judged", "failed", "unknown"}}`, change c0140, `docs/placement.md`, "Height limits"), and
`measures`: `nets`, `hpwl` and `ratsnest` in nanometres,
`longest` (five nets), `left_out` (`zone_nets`, `one_pad_nets`, `off_board`) and `congestion` (`cell`,
`pitch`, `tracks_per_layer`, `busiest`, `layers_needed`; `null` for a board without an outline). The pitch
is the track width plus the clearance of the net class `Default` of the project file. A rule of severity
`error` that fails gives exit code 5. Keep-outs are not judged here: KiCad's DRC reports a part in a rule
area that forbids footprints in `drc.kicad`. The stage is skipped with `read-refused`, with
`cache-unreadable` on a built project whose `.fenolite/` cannot be loaded, and with `no-frame`.

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

**Board edge** (change c0169). Every copper item is also judged against each ring of the board's edge
that the backend's frame gives (`BoardFrame.board_edges`): the board ring, each cut-out and each slot,
overlapping ones merged as the board file holds them. A ring is named `board`, `cut-out <k>`,
`slot <name>` or the names of a merged group joined by ` + ` for a built model, and `board` and
`edge ring <k>` for a board read from its edge graphics. The edge is a line of width 0: the gap is
measured to the line, and the stroke of the edge graphic does not count (`H-K-EDGE-CENTRE`). The limit
is the last `edge_clearance` rule that selects the item (as for `clearance`), else the board minimum:
on KiCad the project's `min_copper_edge_clearance`, 0.5 mm when the project does not set it; on Altium
the board-wide `BoardOutlineClearance`. A board-wide rule governs below and above the minimum on 9.0.x
and 10.0.x (`H-K-EDGE-RESOLVE`). A gap strictly below the limit gives one `copper.edge-clearance` per
item and ring, on the first layer where it applies, with the rule's severity (`error` for the board
minimum); `where` names the item and the ring, and the message gives the gap, the limit and its source
(`rule:<name>` or `floor`). Copper wholly outside the board or inside a cut-out, far from the edge, is
not reported. An arc of the edge is polygonised at 1 µm and widened by its band, so copper within 1 µm
of the limit near a curved edge may be reported where KiCad does not; a zone fill, which KiCad's filler
cuts to the limit around the true arc, is judged against the arc narrowed by its band instead, so a fill
within 1 µm of the limit near a curved edge may go unreported. A frame without `board_edges`
gives `copper.rules-incomplete`, and a board whose edge does not close `copper.item-unsupported` with
`where` `edge`. Every drilled hole (a pad's drill, round or slot, unplated ones included; a via's drill;
a board hole) is judged too: `copper.hole-in-cutout` when its area overlaps a cut-out or slot or crosses
the board ring, `copper.hole-overlap` when two holes overlap (two copies of one hole are not). No value
applies to holes: hole-to-hole and hole clearance stay KiCad's DRC's. The summary adds
`edge_clearance`, `edges` (`rings`, `judged`, `unset_items`, `max`), `holes`, `hole_in_cutout` and
`hole_overlap`. A board whose copper lies too close to its edge, which `check` never reported before,
now gains these findings, as KiCad's DRC always gave them.

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

**Report limits.** KiCad's DRC report stops at a fixed number of entries per type, and no key of the report
says so. `summary.limits` of `drc.kicad` says which counts were cut:

- a list, sorted by `type`, of `{type, reported, limit}`: one entry per violation type, and for
  `unconnected_items`, whose count reached its limit. `reported` is the count that `by_type` or `unconnected`
  gives; the board holds **at least** that many, so the count is a lower bound;
- `[]`: every count is under its limit, so every count is complete;
- `null`: nothing is known (no report was written, or the tool is a version whose limits nobody measured).

Each entry also gives one `check.report-limit` warning after the findings of the stage; its `where` is the
code of the type (`kicad.drc.track-dangling`, `kicad.drc.unconnected-items`). The mark changes nothing else:
the status of the stage, its evidence, the canary state and the exit code are what they are without it. The
other findings of a marked type are not in the report: repair the reported ones and check again to see the
next ones. A count equal to its limit is marked too, because KiCad 9.0.9 can write a few more than 499
`clearance` entries and an unmeasured type is taken to stop at 199. The code is not a `kicad.drc.*` code: it
describes the report, not the board.

| type | limit, KiCad 9.0 | limit, KiCad 10.0 | label |
|---|---|---|---|
| `clearance` | 499 (9.0.9 writes up to a few more) | 499 | `KICAD-VERIFIED (9.0.x, 10.0.x)` |
| `unconnected_items` | 499 | 499 | `KICAD-VERIFIED (9.0.x, 10.0.x)` |
| every other type | 199 | 199 | `KICAD-VERIFIED (10.0.x)` for the eleven types of the bench and `KICAD-VERIFIED (9.0.x)` for ten of them (not `hole_clearance`, which 9.0.9 does not report on the bench); `INFERRED` for a type no probe measured |

The limits are measured on an authored bench (`H-K-DRC-LIMITS`; `docs/formats/kicad/drc.md`, "Report limits").
The 9.0 column is the bench's run in the pinned 9.0.9 image.

**Repeatability.** Fenolite adds no difference of its own: two `check` runs on one project with one
`kicad-cli` give the same output apart from `elapsed_ms` whenever KiCad repeats its reports. KiCad
writes its DRC report in another order from run to run, which `check` sorts away. On boards with hundreds
of violations KiCad also does not repeat the report itself. Measured on the KiCad demo boards with
10.0.6 (`docs/evidence/kicad-check.md`), the difference stays within three types:

- the issues `kicad.drc.clearance`, `kicad.drc.hole-clearance` and `kicad.drc.unconnected-items` can
  name other items and positions, and their counts can change;
- so can the `drc.kicad` summary values counted from them (`violations`, `unconnected`, `by_type`,
  `by_severity`, `types`, and the entries of `limits` for those three types), the `check.report-limit`
  warnings of those three types, and the stage status and the exit code when one of these issues decides
  them;
- on a board with 499 or more `clearance` violations, the canary state can be `fired` in one run and
  `inconclusive` (`clearance-limit`) in the next.

Every issue of another code, the other stages and `tool_writes` repeat. Compare two runs of a large
board by the codes outside those three, or run `roundtrip.rt2`, which leaves out what KiCad does not
repeat.

| code | severity | when |
|---|---|---|
| `check.read-refused` | error | Fenolite cannot read the board; the message starts with the FEN code, `where` is `file:locator:@offset` |
| `check.cache-unreadable` | warning | `.fenolite/` cannot be loaded; `model.validate` is skipped |
| `check.roles-unreadable` | error | `roles.rules`: the role document beside the board (or the roles of `.fenolite/rules.json`) cannot be read |
| `check.footprint-unresolved` | error | a non-DNP component has no footprint reference or instance |
| `check.symbol-unresolved` | error | a built component that carries `fenolite.path` has no symbol reference; a board-only footprint added in KiCad, without that key, is not asked for one (`docs/lens.md`) |
| `check.rt1-failed` | error | RT1 failed; `where` is the first difference |
| `check.oracle-failed` | error | `kicad-cli` wrote no DRC report, ERC report or netlist export, or timed out (`retryable: true`) |
| `check.copy-skipped` | info | a file or folder the project names was left out of the copy |
| `check.report-limit` | warning | the count of one DRC type reached the limit of KiCad's report (499 or 199 entries), so it is a lower bound; `where` is the code of the type, and `summary.limits` of `drc.kicad` lists every such type |
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
| `copper.short` | error, info | copper of two nets touches or overlaps on a shared copper layer; `where` names both items; `info` when a waiver accepts it |
| `copper.clearance` | error, warning, info | a gap below the clearance in force; the governing rule sets the severity, and a class or board-minimum value gives an error; `info` when a waiver accepts it |
| `copper.zone-overlap` | warning, info | zones of different nets and equal priority overlap on a shared layer; `info` when a waiver accepts it |
| `copper.keepout` | error | a track, arc, via or pad lies in a keep-out whose settings forbid its kind, on a layer of the keep-out; `where` names the item and the area. Fills are never reported |
| `copper.edge-clearance` | error, warning | copper closer to the board edge, a cut-out or a slot than the edge clearance in force; the governing rule sets the severity, the board minimum gives an error; `where` names the item and the ring. No waiver applies |
| `copper.hole-in-cutout` | error | a drilled hole breaks into a cut-out or a slot, or crosses the board edge; `where` names the hole's item and the ring |
| `copper.hole-overlap` | warning | two drilled holes overlap; `where` names both items |
| `check.waiver-unmatched` | warning | a waiver of the design script that was judged matched no finding; `where` is the waiver's name |
| `check.exclusion-stale` | warning | a DRC exclusion stored in the KiCad project no longer applies: `moved` or `gone` |
| `copper.rules-incomplete` | warning | a clearance rule stayed opaque, a project file was not read, or no rules source was given |
| `copper.item-unsupported` | warning | copper items left out of the check, one issue per kind; `where` is the kind |
| `copper.clearance-unset` | info | item pairs judged for shorts only, because no clearance is in force for them |
| `zone.unfilled` | warning | KiCad's refill produces copper but the saved board has none for a zone |
| `zone.fill-stale` | warning | the saved fill polygons differ from a KiCad refill |
| `zone.fill-unchecked` | info | the selected tool cannot refill zones, or two refill runs differ; the stage is skipped |
| `placement.too-far` | error, warning | a part of a `near` rule has no selected pad within the rule's distance of a pad of the anchor; the rule sets the severity, and `place` and `build` report it as a warning at most |
| `placement.rule-unresolved` | error | a placement rule names a part or a pad that the board does not hold; a warning in `place` and `build` |
| `placement.rule-skipped` | info | a placement rule names a part that lies off the board, so it is not judged for it |
| `placement.too-tall` | error, warning | a part under a rule area with a height limit is taller than the limit; the limit sets the severity, and `place` and `build` report it as a warning at most |
| `placement.height-unknown` | warning | a part under a rule area with a height limit has no known height (no body on the board or in the `.fenolite/` model) |
| `length.out-of-range` | error, warning | a net's total length lies outside the `min` and `max` of its governing `length` rule; the rule sets the severity; `where` is the net |
| `length.skew-out-of-range` | error, warning | a net's length differs from the longest net of its skew group by more than the `max` of its governing `skew` or `diff_pair_skew` rule; the rule sets the severity; `where` is the net |
| `length.input-missing` | warning | `length.rules` had no rules source (`where` `rules`) or no length facts (`where` `lengths`), so via heights and die lengths are not counted |
| `check.document-missing` | warning | document input: the project file lists a document that does not exist |
| `check.rta0-failed` | error | document input: a container copy lost or changed a storage or a stream; `where` is `<document>:<stream path>` |
| `check.rta1-failed` | error | document input: a stream's records differ after encoding and reading again; `where` is `<document>:<stream>#<record>` |
| `check.rta1-normalised` | info | document input: streams whose records are equal and whose encoded bytes differ |
| `check.rta2-failed` | error | document input: the built model and a reading of the written documents differ inside the written scope |
| `check.rta3-failed` | error | document input, `roundtrip.rta3`: the reading of a document and the reading of its rewrite differ inside the written scope; `where` is the path of the difference |
| `check.rta3-unwritten` | info | document input, `roundtrip.rta3`: the counts, per kind, of what the rewritten documents do not hold; never part of the verdict |
| `check.roundtrip-unjudged` | info | document input: a document whose level was not judged; the message names the reason |

`model.*` findings and reader codes pass through unchanged; among them `model.no-connect-on-net`
(error) names a pin that is marked as not connected and that a net lists, `model.duplicate-bus-index` (error) a bus that uses an index twice, `model.body-height` (error) a component body whose height is below its standoff (`docs/design-model.md`, change c0043), and `model.pin-pad-map` (error) a pin-to-pad map that holds a pair twice, an empty text, or a pad that two pins name (change c0123), and `model.corner-ratio` (error) a pad whose `corner_ratio` is outside 0 to 500 000 ppm of its shorter side or that is no rounded rectangle, with `where` the pad's id (change c0126). `model.stackup-order`, `model.stackup-copper` and `model.stackup-value` (errors) name a stack-up whose entries are out of order, whose copper entries are not the board's copper layers, or that holds a thickness or a decimal the model does not accept (`docs/design-model.md`, "Stack-up"; change c0101). Signed intervals are in the mounted-face frame, positive outwards and authoritative over height/standoff; `model.body-volume` (error) reports missing or reversed bounds. Unknown projection bypasses legacy height validation (change c0099). Exit codes: 0 without an error issue, 5
with one, 2 for a usage error (ambiguous folder, unknown stage), 3 for a missing path or a board that
neither Fenolite nor KiCad reads (the envelope still holds the issues), and 6 when a stage that needs
`kicad-cli` is selected and it is missing (`FEN-6001`; the hint names `--stages model.validate,roundtrip`),
of an unsupported major, or older than the board's format (`FEN-6002`). Two runs on the same project
give the same stdout apart from `elapsed_ms`.

### Waivers

A design script accepts one finding with `design.waive(code, *items, reason=…)` (`docs/dsl.md`,
"Waivers"). The build stores the waivers in `.fenolite/findings.json`, and `check` on a built project, of
either target, applies them. A native project has no waiver.

- **Effect.** A finding that a waiver matches keeps its code and `where`, takes severity `info`, and its
  message ends with ` (waived by <name>: <reason>)`. No finding is removed, so the counts of a stage do
  not change; a stage whose every error was waived has status `ok`. Waivers change no evidence.
- **Matching.** The codes are equal, each item of the waiver names one item of the finding, one to one
  and in any order (as a glob, or letter for letter), and with `min_gap` the gap of a `copper.clearance`
  finding is at least that. The items of a copper finding are the two parts of its `where`; those of a
  DRC finding are the locations of its items.
- **Stages.** `copper.*` waivers are applied by `copper.clearance`, on both pipelines; `kicad.drc.*`
  waivers by `drc.kicad`. No other stage takes a waiver: ERC and parity findings are never waived.
- **Stale waivers.** A waiver is judged when the stage of its code ran with a verdict. A judged waiver
  that matched nothing gives `check.waiver-unmatched` (warning), `where` its name. A waiver of
  `kicad.drc.clearance`, `hole-clearance`, `unconnected-items` or `shorting-items` is applied when it
  matches and never judged, because KiCad does not repeat those entries from run to run.
- **`result.waivers`** holds `declared` (the count), `matched` (name → findings, for judged waivers),
  `unmatched` (names) and `unjudged` (name → `stage-not-run` or `not-repeatable`). On Altium input every
  `kicad.drc.*` waiver is `stage-not-run`: that pipeline has no DRC stage.

**KiCad's own exclusions.** A KiCad project stores the entries its user excluded in the DRC dialog, each
with a position, two item uuids and a comment. `pcb drc` ignores an exclusion that matches nothing
without a message, so `check` says what became of each: the issue of an excluded entry ends with
` (excluded in the project: <comment>)`, and an exclusion that no longer applies gives
`check.exclusion-stale` (warning), `moved` when an entry of its type and items is reported again
(KiCad matches the marker position to the nanometre) and `gone` when none is. `summary.exclusions` of
`drc.kicad` holds `stored`, `live`, `stale` and `unjudged`; exclusions of the four types above are not
judged. Two keys of one type, position and item pair in both orders are one accepted exception (the form
`--exclude` writes): both are live when the report marks an entry of that type and those two items, in
either order, as excluded, else both unjudged (one of the four types) or both stale with one warning.
`summary.accepted` of `drc.kicad` lists each such exception: `type`, `items` (the two uuids), `comment`,
`state` (`live`, `stale` or `unjudged`) and `reported` (an entry of that type names the two items).

### Writing a DRC exclusion

`fenolite check PATH --exclude CODE:ITEM_A[:ITEM_B] --reason TEXT [--dry-run | --confirm]` (KiCad input,
change c0209) runs no stage: it stores one DRC exclusion in the board's project file
(`<stem>.kicad_pro`, created as `{}` with the list when missing) under the mutation protocol, and writes
nothing else. `CODE` is KiCad's type (`unconnected_items`) or the finding's code
(`kicad.drc.unconnected-items`); each `ITEM` is a KiCad uuid or an item's name as the finding's `where`
prints it (`R1-1`, `/kicad_pcb/segment[0]`), in either order; `ITEM_B` is left out for an entry of one item.
`--reason` is required and becomes the exclusion's comment. Without `--exclude`, `check` plans no write, so
`--dry-run` and `--confirm` change nothing.

- **Lookup.** `pcb drc` runs on a copy; exactly one entry must match, else `check.exclusion-unmatched` or
  `check.exclusion-ambiguous` (errors, exit 5, nothing written).
- **Key.** A key needs the marker position, which the report does not give (`docs/formats/kicad/drc.md`,
  "Written exclusions"). A second run on a copy stores one probe key per anchor of the two items and per
  order; the comment KiCad puts on the entry names the position. None applies: `check.exclusion-unlocated`
  (error, exit 5). An entry already excluded takes the position of its stored key.
- **Write.** The exclusion is stored in both orders of its two items, each `[key, reason]`; a key already
  stored is not repeated, and when both are, `check.exclusion-present` (info) and no plan. A third run on a
  copy must show the entry excluded with the reason before the write is planned.
- **Result.** `result.project` (the project file, relative to the working directory), `tool_version` and
  `exclusion`: `type`, `code`, `items` (`uuid`, `name`), `reason`, `position` (`{x, y}` in nm, `null` when
  unlocated) and `keys`. Evidence `KICAD-VERIFIED` (`H-K-DRC-EXCLUSION`). Without a `kicad-cli`: exit 6.

### Trial edits

`fenolite.api.trial(board, edit, *, kicad_cli=None, refill=True, gate=False, timeout=300)` (change c0209)
is the library form of a DRC-gated edit; `route` and `tidy` take it as `--gate drc` ([DRC gate](#drc-gate)).
`together` (change c0225) names groups of the edit's ids that the gate drops as one. `edit` takes the board model
and returns the edited model and the ids of the items it added, removed or changed. The unedited and the
edited model are written for the board's major and checked by `pcb drc` on copies with the project files,
the zones refilled first on KiCad 10 (`trial.not-refilled`, warning, on 9 for a board with zones). A
finding of the edited copy is new when the unedited copy holds fewer entries of its type and item set; it
names the edit's items whose uuids it holds. With `gate=True` the named items are dropped (an added item
removed, a changed one put back) and the trial runs again until no new finding names an item of the edit.
`TrialResult` holds `board_text` (the board to write), `findings`, `kept`, `dropped` (each item with its
findings), the entry counts `baseline` and `edited`, `runs`, `refilled`, `tool_version`, `evidence`
(`KICAD-VERIFIED`, `H-K-DRC-TRIAL`) and `issues`. Nothing is written; `ToolMissingError` (`FEN-6001`)
without a `kicad-cli`.

### DRC gate

`fenolite route` and `fenolite tidy` take `--gate drc` (change c0225). The command makes its edit as
without it; the tracks, arcs, vias, zones and other items that differ between the board as read and as
edited are the edit, judged by `fenolite.api.trial(..., gate=True)` on the board and its project files
([Trial edits](#trial-edits)). The command writes its own model without the items the trial dropped; `tidy`
drops an edit whole (its removed, replaced and added items, joined with any edit that changes one of them).
The `kicad-cli` pre-flight of `check` runs before the edit (`--kicad-cli`, else the tool `check` finds):
without a tool the command exits 6 and routes, tidies and writes nothing. The DRC runs take `tidy`'s
`--timeout`; `route`'s `--timeout` stays the router's budget and the runs take 300 s. `route --kicad-cli`
without `--gate drc` exits 2.

`result.gate` is `null` without the option, else `tool_version` (`null` when the edit held no item and no
DRC ran), `runs`, `refilled`, `items` (the ids judged), `kept` (a count), `dropped` (`{id, findings}`) and
`findings` (the new findings left, which name no item of the edit); each finding holds `type`, `severity`,
`description`, `uuids` and `items`. The write is planned as without the gate. With no finding left the
evidence is the trial's (`KICAD-VERIFIED`, `H-K-DRC-TRIAL`).

| code | severity | when |
|---|---|---|
| `gate.dropped` | warning | an item of the edit is not written: a new DRC finding names it (or another item of its tidy edit); the message gives the first finding |
| `gate.unnamed` | warning | a new DRC finding names no item of the edit; it may be noise of the tool (`H-K-DRC-REPEAT`), and the edit is written |

### check on Altium input

`fenolite check PATH` also checks the documents of a backend whose project is a set of documents
(change c0044): an Altium document or library (`.SchDoc`, `.PcbDoc`, `.SchLib`, `.PcbLib`), a project
file (`.PrjPcb`) or a folder that holds exactly one project file. This *document input* is looked for
before a KiCad board. It is read-only and runs no tool: no `kicad-cli` is looked for, and `--kicad-cli`
and `--timeout` are accepted and ignored. A folder that holds a KiCad project or board beside an Altium
project file is ambiguous, and a folder with Altium files and without exactly one project file is
refused (both `FEN-2001`, exit 2, the hint naming the candidates).

The stages are `DOCUMENT_STAGES`, in this order; `--stages` selects a subset (all by default), and a
name of the KiCad list such as `drc.kicad` is a usage error whose hint lists them. One more stage,
`roundtrip.rta3`, is opt-in (`OPT_IN_DOCUMENT_STAGES`, change c0090): it runs only when `--stages` names
it, because it writes a whole project into a temporary folder and reads it again.

| stage | what it does | evidence |
|---|---|---|
| `model.validate` | the `model.*` findings of the schematic reading and of the PCB reading (`where` starts with `schematic:` or `pcb:`), with the readers' own issues; on built input, those of the stored model | the readings; `INFERRED` on built input |
| `circuit.rules` | the circuit rules of `check` ("Circuit stage") on the stored model of a built project; skipped with `no-model` on native documents and with `no-parameters` when the model holds nothing to judge | `INFERRED`, lowered by the device records it judged |
| `erc.lite` | the three ERC lite rules on the schematic reading (pin types and No ERC marks come from the sheets), or on the stored model of built input | `INFERRED` (`H-K-CHECK-ERC`, `H-A-VER-ERC`) |
| `copper.clearance` | the copper check of `check` on the PCB reading, built and native input alike: shorts, clearance and zone overlaps, with the pads of the Altium board frame and the Clearance rules the document holds (below) | the reading and the check (`H-A-DRC-SAME`); `UNVERIFIED` when part of the copper or of the rules was not judged |
| `placement.rules` | the placement rules and measures of `check` on the PCB reading: on built input the `near` rules of the stored model judged on the pad positions of the Altium board frame; on every PCB document the wire length and the congestion. No stage judges a part in a keep-out on Altium input | the reading when no rule was judged; the lowest of it and `INFERRED` when one was |
| `roles.rules` | the net roles of the PCB reading, as the stage of the KiCad pipeline judges them, with the pads of the Altium board frame; skipped with `no-roles` without a stored or declared role | `INFERRED` |
| `parity` | the PCB reading against the schematic reading, as `parity` below: references, values, footprint names, nets, pins and pads | `INFERRED` (`H-K-PARITY-OWN`, `H-A-DRC-PARITY`) |
| `netlist.assignment_compare` | the partition compare of the pairs (`schematic`, `pcb`) on native input, (`model`, `schematic`) and (`model`, `pcb`) on built input; no export is needed | the lowest of the readings compared (`H-A-IMP-NETLIST`) |
| `roundtrip.rta0` | RT-A0 of every compound file of the set: a copy through the reader and the compound writer keeps every storage and stream | `EVIDENCE_RT_A0`; `UNVERIFIED` when a copy fails |
| `roundtrip.rta1` | RT-A1 of every document: every typed stream gives equal records after encoding and reading again | the reader's level per kind; `UNVERIFIED` when a stream fails |
| `roundtrip.rta2` | RT-A2 on built input: the stored model against the readings of the documents the build wrote, inside the written scope (`docs/altium.md`, "Round trips"); footprints, pads and copper are compared, and no kind is only counted | `INFERRED` (`H-A-VER-RTA2-3`) |
| `roundtrip.rta3` | opt-in. RT-A3: the project file (else the PCB document, else the first schematic) is read, its model is written as new Altium documents in a temporary folder, and those are read again; the two models are compared inside the written scope | `INFERRED` (`H-A-VER-RTA3`); `UNVERIFIED` when a difference is reported |

A stage is skipped with one of these reasons: `native-input` (`roundtrip.rta2` on files that no
Fenolite build wrote), `model-predates-board` (`roundtrip.rta2` on a project built before change c0090,
whose stored model holds no footprint: build it again), `model-predates-graphics` (`roundtrip.rta2` on a
project built before change c0126, whose stored footprints hold no graphic while its PCB document draws
some: build it again), `no-document` (`roundtrip.rta3` when the write
gives no document of the kind that was read: the schematic writer refuses the circuit),
`no-schematic` (`erc.lite` and `parity` without a schematic document),
`single-source` (`netlist.assignment_compare` without two sources; `copper.clearance`,
`placement.rules`, `roles.rules` and `parity` without a PCB document), `no-frame` (`placement.rules` when
the backend gives no pad positions), `no-roles` (`roles.rules` without a stored or declared role),
`no-model` and `no-parameters` (`circuit.rules`), `not-judged` (no document of the set can be judged
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
  `differences` and `compared` (the entity kinds compared per side: every kind of the written scope).
  The summary of `roundtrip.rta3` holds `level`, `holds`, `differences`, `written` (model items written,
  per kind), `unwritten` (per kind, what the rewritten documents do not hold: model items, and under
  keys that start with `record:` the records and storages of the input that the import maps to no model
  entity), `files` (the names of the written files, none of which stays on disk) and `presentation`
  (`regenerated`: the schematic is generated from the circuit).
- **`copper.clearance` on a PCB document.** The codes and severities are those of the KiCad stage
  (`copper.short`, `copper.clearance`, `copper.zone-overlap`, `copper.clearance-unset`,
  `copper.rules-incomplete`, `copper.item-unsupported`, `copper.edge-clearance`, `copper.hole-in-cutout`,
  `copper.hole-overlap`); the edge rings are the board outline of the document (cut-out regions with
  change c0168), and the board minimum is its board-wide `BoardOutlineClearance`. The summary is that of the KiCad stage plus `unpoured`, `zones_unjudged` and `clearance_cells`
  (`{judged, unjudged}`: the cells of the document's clearance matrices that a rule holds and that none
  holds).
  What the stage does not judge is said, and any of these lowers it to `UNVERIFIED`:
  - an **unpoured polygon** is no copper: `unpoured` counts them, with one `copper.item-unsupported`
    (a build with `--altium-pour outline`, or without the `geo` extra, writes its polygons unpoured, so
    such a board with zones says this until Altium repours);
  - an **internal plane** is drawn in negative: what is drawn on its layer is no copper, and the import
    makes no track of it; one `copper.item-unsupported` (`where` is `plane`) counts the planes;
  - a **Clearance rule outside the rule table** (an object matrix, a layer scope) may govern any pair:
    `rules.opaque_clearance_rules` counts them, with one `copper.rules-incomplete`;
  - a **filled zone that no clearance applies to** is judged for shorts only: `zones_unjudged` counts
    them, with one `copper.rules-incomplete` (`where` is `zone`). A polygon holds no clearance of its
    own, so a pour is never judged against the model's default of 0.5 mm.
  A clearance of the document is judged 9 nm lower than written (change c0152): the document counts
  in units of 2.54 nm, and copper that is exactly its clearance apart reads up to 4 nm closer in
  nanometres (one file unit per item of the pair, 5.08 nm, change c0131); and Altium's own check was
  seen to pass copper 3.5 units (8.89 nm) inside its clearance, held as 9 whole nanometres. Copper
  further inside its clearance than 9 nm is a finding. A KiCad board is judged strictly at the
  nanometre.
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
`edge_clearance`, `unpoured`, `rules`, `evidence` and `waivers` (as on KiCad: the design's `copper.*` waivers are applied
before the mode, so a waived short is `info` and does not refuse the build); the evidence is `UNVERIFIED`
when the document holds unpoured polygons, which the guard cannot judge. No file is read from disk and no tool runs.

## ready

`fenolite ready PATH [--no-kicad] [--kicad-cli PATH] [--timeout SECONDS]` says in one reply whether a
KiCad project is electrically ready for fabrication (change c0098). `PATH` is a board, a project file or
a project folder, as for `check`; Altium input exits 2 with `FEN-2001` (use `fenolite check`). It writes
no file. It gathers findings that Fenolite already computes, and adds three rules:

| check | what it reports | source | needs `kicad-cli` |
|---|---|---|---|
| `nets.open` | one `ready.net-open` per net with open connections, with their number and the shortest | `analysis.connectivity`, as `fenolite net` | no |
| `erc.kicad` | KiCad's ERC findings (`kicad.erc.*`) | the stage of `check`, unchanged | yes |
| `drc.kicad` | KiCad's DRC findings (`kicad.drc.*`), unconnected items included | the stage of `check`, unchanged | yes |
| `pins.unconnected` | one `ready.pin-unconnected` per pin of a fitted part on no net, or alone on its net, that is not of type `no_connect` and carries no no-connect mark (`no_connect()` in a script, a no-connect flag in a schematic) | Fenolite's rule | no |
| `power.nets` | one `ready.power-net-unsized` per power net with neither a track width of its own class (not `Default`) or of a `track_width` rule that selects it (a rule over `all` is a board minimum and does not count), nor a zone | Fenolite's rule | no |
| `parts.fields` | `check.footprint-unresolved` (the rule of `model.validate`) and one `ready.part-value-missing` per fitted part with an empty value | Fenolite's rule | no |

- **Power net.** A net that a `Power` interface names (`source` `interface`), or a net with a pin of type
  `power_in` or `power_out` (`source` `pin-type`). A design whose pins are all `passive` and that declares
  no `Power` interface has no power net.
- **Which design is judged.** Pins, no-connect marks, interfaces, net classes, rules, values and footprints
  come from the `.fenolite/` model of a built project, else from the board as read with the classes and
  rules of the project files. Open connections and zones come from the board as read. A `.fenolite/`
  that cannot be loaded gives `check.cache-unreadable` (warning), and the board's reading stands in.
- **Without `kicad-cli`.** As `check` does for its stages that need the tool, a missing or unsupported
  `kicad-cli` exits 6 (`FEN-6001`, `FEN-6002`), and the hint names `--no-kicad`. With `--no-kicad` no
  tool runs, and `erc.kicad` and `drc.kicad` are `skipped` with reason `no-kicad`. A check that is
  skipped, by that option or by its stage (`erc.kicad` on a project without a schematic:
  `no-schematic`), gives one `ready.check-skipped` warning.
- **Result.** `result.project` (`board`, `built`); `result.ready`, true exactly when no issue has
  severity `error`; `result.complete`, true exactly when no check is skipped; `result.checks`, one entry
  per check in the order of the table, in the form of an entry of `result.stages` of `check` (`name`,
  `status`, `reason`, `evidence`, `summary`); `result.counts`, the number of issues per severity. The
  `summary` of `nets.open` is `{nets, connections}`, of `pins.unconnected` `{pins}`, of `power.nets`
  `{nets: [{net, source, width, zones}]}` with `width` `class:<name>`, `rule:<name>` or `null`, and of
  `parts.fields` `{footprint, value}`; the two KiCad stages keep the summary they have in `check`.
- **Exit codes.** 0 when `result.ready` is true; 5 when it is false, with the findings in `issues`; 6
  for a missing tool, as above; 2 and 3 as for `check`.
- **Evidence.** Each check carries its own: `nets.open` the board read's combined with the query's
  (`H-K-CONN-PARITY`), the KiCad stages theirs, and the three rules `INFERRED` (`H-G-READY-RULES`). The
  envelope holds the lowest of the checks that ran, so `INFERRED` at best: `ready` gathers, `check`
  stays the judge.

```json
{"project": {"board": "blink.kicad_pcb", "built": false}, "ready": true, "complete": true,
 "checks": [{"name": "nets.open", "status": "ok", "reason": "",
             "evidence": {"level": "INFERRED", "oracle": null,
                          "hypotheses": ["H-G-BOTTOM-PLACE", "…", "H-K-CONN-PARITY", "H-K-PCB-READ"]},
             "summary": {"nets": 0, "connections": 0}}, "…"],
 "counts": {"error": 0, "warning": 0, "info": 0}}
```

An open net is reported twice when DRC ran: as `ready.net-open`, computed without a tool, and as
KiCad's `kicad.drc.unconnected-items`. `fenolite net BOARD NAME` lists the open connections of a net.

## export

`fenolite export PATH --out DIR [--gerbers] [--drill] [--pos] [--ipcd356] [--ipc2581] [--odb] [--step] [--pdf]
[--dxf] [--sch-pdf] [--fab-drawing] [--assembly-drawing] [--drawing-spec FILE] [--all] [--altium-rul]
[--manifest] [--preset FILE] [--readback] [--kicad-cli PATH] [--timeout SECONDS]`
writes the fabrication files and documents that `kicad-cli` produces from a
copy of the board `PATH` names (resolved as for `check`) and, for `--sch-pdf`, of its schematic. Fenolite writes no Gerber itself: the tool runs
once per kind on the copy set of `check`, so the project folder never changes, and every file it wrote
becomes a planned write under `DIR` (relative to the working directory). The mutation protocol applies:
`--dry-run` runs the tool and shows the plan, `--confirm` writes. `--all` selects the four fabrication
kinds (`gerbers`, `drill`, `pos`, `ipcd356`) and no document kind; a call
that selects none exits 2. `--timeout` defaults to 300 s and applies to each run.

| kind | `kicad-cli` call | files under `DIR` |
|---|---|---|
| `--gerbers` | `pcb export gerbers --no-protel-ext --layers <copper in stack order, masks, pastes, silkscreens, Edge.Cuts>` | `gerbers/<stem>-<layer>.gbr`, `gerbers/<stem>-job.gbrjob` |
| `--drill` | `pcb export drill --format excellon --excellon-units mm --excellon-separate-th --drill-origin absolute` | `drill/<stem>-PTH.drl`, `drill/<stem>-NPTH.drl` |
| `--pos` | `pcb export pos --format csv --units mm --side both` | `pos/<stem>-pos.csv` |
| `--ipcd356` | `pcb export ipcd356` | `netlist/<stem>.d356` |

`--check-zones` and `--board-plot-params` are never passed, so the files show the board as it is.

The six document kinds (change c0116) are selected one by one, each with one fixed argument list that is
the same on KiCad 9 and 10; `--variant`, `--drawing-sheet` and `--define-var` are never passed either.

| kind | `kicad-cli` call | files under `DIR` | `repeat` |
|---|---|---|---|
| `--ipc2581` | `pcb export ipc2581 --version C --units mm --precision 6` | `ipc2581/<stem>.xml` | `none` |
| `--odb` | `pcb export odb --compression zip --units mm` | `odb/<stem>.zip` | `none` |
| `--step` | `pcb export step --subst-models`, with the 3D model files Fenolite locates | `3d/<stem>.step` | `none` |
| `--pdf` | `pcb export pdf --mode-separate --layers <those of the Gerbers, F.Fab, B.Fab, Edge.Cuts> --common-layers Edge.Cuts --include-border-title` | `pdf/<stem>-<layer>.pdf` | `content` |
| `--dxf` | `pcb export dxf --mode-multi --output-units mm --layers <Edge.Cuts, F.Fab, B.Fab, F.CrtYd, B.CrtYd>` | `dxf/<stem>-<layer>.dxf` | `bytes` |
| `--sch-pdf` | `sch export pdf <stem>.kicad_sch`, with every sheet of the hierarchy | `schematic/<stem>.pdf` | `content` |

- `result.repeat` maps each selected fabrication or document kind to what two exports of one board share:
  `bytes` (the files are byte-equal), `content` (they differ only in date-bearing lines, which
  `content_sha256` leaves out) or `none` (neither hash tells whether the board changed).
- `--step`: Fenolite reads every `(model …)` path of the board, locates each file (the order of the
  sources is under "models") and copies the located ones into the run. `result.models` lists every
  path with `source`, `sha256`, `bytes` and `refs`, and is `[]` without `--step`. A path that is not
  located gives `kicad.lib.missing-3d-model` (warning) and the STEP is written without that body.
- `--sch-pdf` needs `<stem>.kicad_sch` beside the board: without it the call exits 3 (`FEN-3001`) before
  any run. A hierarchy that names a sheet the run cannot be given is refused (`export.sheet-missing`).
- `--preset` changes no document kind: each runs with the arguments of the table whatever the preset holds.
- `PATH` names a KiCad board. An Altium document or project is refused with exit 2 (`FEN-2001`), as for
  the four fabrication kinds.

`--fab-drawing` and `--assembly-drawing` (change c0117; `docs/drawings.md`) write a fabrication drawing
and assembly drawings under `DIR/drawings/`. Each page is one `pcb export pdf --mode-single
--include-border-title --drill-shape-opt 0 -D FENOLITE_DRAWING=<title>` run on a copy of the board that
holds Fenolite's tables, dimensions and added designators as board items (`--layers Edge.Cuts,Dwgs.User`
for the fabrication page, `F.Fab,Edge.Cuts` for the top assembly page, `B.Fab,Edge.Cuts` with `--mirror`
for the bottom one, and `--drawing-sheet` for a sheet the specification names); the fabrication kind also
runs `pcb export drill … --generate-map --map-format pdf --generate-report` and keeps the maps and the
report. These are the only runs that pass `--define-var` or `--drawing-sheet`.

- Each flag selects its kind. A drawing kind counts as a selected kind, needs `kicad-cli` (`FEN-6001`,
  `FEN-6002`, `--timeout` per run), and is not selected by `--all`; `--preset` changes none of its
  arguments, and `result.repeat` maps both kinds to `content`. `result.kinds` lists the drawing kinds
  last, `fab-drawing` first.
- `--drawing-spec FILE` names the drawing specification, a TOML file whose `schema` is
  `fenolite.drawing-spec.v0` (`docs/drawings.md`, "The specification file"). It is read after `PATH`
  is resolved and before any tool runs: without a drawing flag the call exits 2 (`FEN-2001`), a file
  that cannot be read exits 3 (`FEN-3001`), and a file with a problem exits 3 (`FEN-3004`) with every
  problem and its dotted key in the message. Without the option every default applies.
- `PATH` names a KiCad board: an Altium document or project is refused with exit 2 (`FEN-2001`) before
  the specification is read or a tool is looked for.
- `result.drawings` (present when a drawing kind is selected) holds one object per page produced, in the
  order fabrication, assembly top, assembly bottom: `kind`, `path`, `paper`, `portrait`, `sheet`
  (`spec`, `project` or `kicad-default`) and `blocks` (each with `name`, and `at` and `size` in integer
  nanometres), and for an assembly page `side` and `designators_added`.
- A `drawing.*` issue of severity error plans no write, for any selected kind; an info or a warning does
  not change the exit code. With a drawing kind the evidence is combined with `exports.drawings.EVIDENCE`
  (`KICAD-VERIFIED`; `H-K-DRAW-ITEMS`, `H-K-DRAW-PAGE`, `H-K-DRAW-DRILL`), and a manifest entry of a drawing
  kind carries that level, `layer` `null` and the board's SHA-256 in `from`.

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
`content_sha256`; sorted by path), `tool_version`, `tool_writes` (files the tool wrote outside its
output folders, such as `<stem>.kicad_prl`), `repeat` and `models`. `layer` is set for a Gerber and for
each file of `--pdf` and `--dxf`. In the manifest, the `from` of a `sch-pdf` entry holds the SHA-256 of
the root schematic instead of the board's, and the `evidence` of a document entry is the level of
`exports.DOCUMENTS_EVIDENCE`. When a kind fails, nothing is planned or written, so a
folder never holds a partial set; a warning never holds the files back.

`--readback` (change c0203; `docs/exports.md`, "Read-back") reads the Gerber, drill and position files of
the run back with Fenolite's own readers of the subset `kicad-cli` writes, and compares them with the board
before anything is planned: every finding is an `export.readback-*` error, so no file is written. It needs
`--gerbers`, `--drill` or `--pos` (`FEN-2001` otherwise).

| code | severity | when |
|---|---|---|
| `export.failed` | error | a kind's run exited non-zero, wrote no file or timed out (`retryable: true`); `where` is the kind. For `altium-rul`: the rules file cannot be read, or no rule has an exact Altium form |
| `export.readback-outline` | error | `--readback`: the outline does not close into one contour per ring of the board (outer edge, cut-outs, slots), matched by their boxes |
| `export.readback-drill` | error | `--readback`: a hit or slot matches no hole of the board in position, diameter and plating, or a hole has none |
| `export.readback-position` | error | `--readback`: a row of the position file does not match its footprint's position, rotation and side |
| `export.readback-layer` | error | `--readback`: a copper layer, or the outline, has no Gerber file with its file function |
| `export.readback-empty` | error | `--readback`: the file of a copper layer that holds copper draws nothing |
| `export.readback-unsupported` | error | `--readback`: a file holds a construct outside the subset the readers take (another coordinate format, inches, step and repeat, …) |
| `export.kind-unavailable` | error | the running `kicad-cli` major cannot export the kind; no tool run |
| `export.sheet-missing` | error | `--sch-pdf`: the hierarchy names a sheet file that is missing, outside the project folder, in a cycle or too large to copy (`where`); no tool run for the kind |
| `export.model-unread` | warning | `--step`: `kicad-cli` printed that it could not add the model of a part (`where`) whose files Fenolite gave it |
| `export.page-too-small` | warning | `--pdf`: the outline of the board does not fit the page of its paper, so the PDF is cut (`where` is `pdf`) |
| `kicad.lib.missing-3d-model` | warning | `--step`: a model path that no source holds; `where` is the path, and the message names the parts |
| `drawing.no-room` | error | a drawing page's paper does not hold the board box or a block at 1:1; `where` is the block or `board box`, and the message names the smallest paper that holds the page |
| `drawing.drill-mismatch` | error | `--fab-drawing`: the drill table and KiCad's drill report give different counts for a diameter; `where` is the drill file |
| `drawing.sheet-unread` | error | the drawing sheet of the specification or of the project cannot be read or built; `where` is the file; no drawing run |
| `drawing.drill-report-unread` | warning | `--fab-drawing`: KiCad's drill report names no drill file, so the drill table was not checked |
| `drawing.stackup-missing` | info | `--fab-drawing`: the board has no stack-up, so the drawing has no stack-up table |
| `drawing.side-empty` | info | `--assembly-drawing`: no part sits on the bottom, so there is no bottom page |
| `drawing.designators-added` | info | `--assembly-drawing`: references were added to a page (`where` is the side); the message gives the count |

Exit codes: 0 when the files are planned or written, whatever the warnings, 4 without `--dry-run` or
`--confirm`, 5 with an error above, 2 for a usage error, 3 for a missing path, a board Fenolite cannot
read or a missing schematic, 6 when
`kicad-cli` is missing (`FEN-6001`), of an unsupported major or older than the board's format
(`FEN-6002`). The evidence is `exports.EVIDENCE` with the oracle `kicad-cli <version>`: Fenolite claims
the file set and the hashes, and the content of each file is KiCad's. An export that selects a document
kind carries the combination of the selected kinds' evidence: `exports.DOCUMENTS_EVIDENCE` is
`KICAD-VERIFIED` (`H-K-EXPORT-DOCS`, `H-K-EXPORT-DOCS-REPEAT`, `H-K-EXPORT-MODELS`, `H-K-EXPORT-SHEETS`, which
hold on both majors since 2026-10-08).

## models

`fenolite models PATH [--vendor]` lists the 3D model files that the footprints of a KiCad board name and
where Fenolite finds each (change c0116). It runs no tool and makes no request. `PATH` resolves as for
`check`; an Altium document or project is refused with exit 2 (`FEN-2001`).

Each distinct `(model …)` path is located once, from the first source that holds the file:

| path form | sources, in order |
|---|---|
| `${KICAD<N>_3DMODEL_DIR}/<rel>` | `project`: `<board folder>/3dmodels/<rel>`; `env`: the variable in the environment; `kicad-config`: the variable in KiCad's `kicad_common.json` of major N; `install`: the `3dmodels` folder of the KiCad install; `cache`: a fetched file of the pinned tag of major N whose SHA-256 is its stamp entry |
| `${KIPRJMOD}/<rel>` | `project`: `<board folder>/<rel>` |
| any other path | `in-place`: the file where the path says |

- `result.models` holds one object per distinct path, sorted by path: `path`, `source` (one of the
  above, or `missing`), `sha256` and `bytes` (`null` when missing or in place) and `refs` (sorted).
  `result.counts` holds `paths`, `located` and `missing`. The list is paged ("Paged results").
- A path that is not located gives one `kicad.lib.missing-3d-model` (warning); the exit code stays 0.
- `--vendor` plans one copy per located `${KICAD<N>_3DMODEL_DIR}/<rel>` whose source is not `project`,
  at `<board folder>/3dmodels/<rel>` (kind `3d-model`). The mutation protocol applies: a plan asks for
  `--confirm`. The board, its footprints and their model paths never change; later exports read the
  copies first. `fenolite manifest` lists them as design files of kind `3d-model`.
- No value holds an absolute path or a date. The evidence is `KICAD-VERIFIED` (`H-K-EXPORT-MODELS`).

Exit codes: 0, also with missing models; 4 when `--vendor` plans a copy without `--dry-run` or
`--confirm`; 2 for a usage error; 3 for a missing path.

**Stack-up note (c0101).** The Gerber job file states the board's stack-up. When `--gerbers` (or `--all`)
runs on a board whose model holds no stack-up, one `export.stackup-default` (info, `where` `gerbers`)
says that KiCad states its default there: 0.035 mm copper, 0.01 mm masks, equal FR4 dielectrics that fill
the board thickness, and the finish `None`. The note changes no file. An issue of severity `info` does not stop the writes: only an error does (a
warning does not either, change c0116).

## render

`fenolite render PATH --out DIR [--svg] [--png] [--width PX] [--height PX] [--manifest]
[--kicad-cli PATH] [--timeout SECONDS]` writes review views of the board, through `kicad-cli` on the same copy set and
with the same protocol and tool errors as `export`. `--svg` plots `front.svg` (`F.Cu`, `F.SilkS`,
`F.Fab`, `Edge.Cuts`) and `back.svg` (the back layers, mirrored) with `pcb export svg --mode-single`;
`--png` renders `top.png` and `bottom.png` with `pcb render`, at most `--width` by `--height` pixels
(defaults 1600 and 1200, each from 64 to 8192). A call with neither flag, nor `--region`, exits 2. `result`
holds `board`, `out`, `views` (`path`, `kind`, `bytes`, `sha256`; sorted by path) and `tool_version`.
`--manifest` merges the views that were produced into `DIR/fenolite-artifacts.json` as `export` does, each
with the kind `render`; a view that failed has no entry.

### Region renders

`fenolite render PATH --out DIR --region X1,Y1,X2,Y2 [--nets] [--open] [--grid LENGTH] [--cut X1,Y1,X2,Y2]...
[--cut-width LENGTH] [--cut-clearance LENGTH] [--width PX] [--manifest]` draws one rectangle of the board
into `DIR/region.svg` (change c0211). Fenolite draws it from the model and runs no tool, so the same board
gives the same bytes. Every length needs a unit. The corners may come in either order. A rectangle with no
area exits 2, and so does `--region` with `--svg` or `--png`. The region options without `--region` exit 2,
and so do `--cut-width` or `--cut-clearance` without `--cut`.

The SVG holds, clipped to the rectangle, the copper of every item whose box meets it, bottom layer first:
pads, tracks, arcs, the zone copper in its state and the vias. It also holds the holes and slots, the board
edge with its cut-outs, and a grid labelled in millimetres of board coordinates. With `--nets` there is one
label per pad with a net whose position lies in the rectangle; `--open` adds the open connections as straight
lines; each `--cut` adds the cut and its ways per layer, as `analyze --kinds crossings` gives them. Every
element carries a `class` (`pad`, `track`, `arc`, `via`, `zone`, `zone-outline`, `hole`, `slot`, `edge`,
`grid`, `grid-label`, `net-label`, `open`, `cut`, `way`) and `data-*` attributes (`data-net`,
`data-layer`, `data-where`, `data-state`, …), and coordinates are millimetres with the exact digits of their
nanometres.

The zone copper is that of the practice checks (`analysis.pour`): the saved fill, the simulated pour drawn as
its cells, or the zone outline when the pour is too large. The open connections follow that copper.
`result.views` holds `region.svg`, `tool_version` is `null`, and `result.region` holds `x0`, `y0`, `x1`,
`y1`, `grid`, `counts` (elements per class), `copper` (the states used), `zones` (`zone`, `net`, `layer`,
`state`, `reason`), `pour_grid`, `open` (`net`, `a`, `b` with `where`, `x`, `y`, and `length`) and `cuts`
(`cut`, `supply`, `open`, `routed`). The evidence is `INFERRED` (`H-G-REGION-RENDER`), combined with that of
the connections and of the cuts.

| code | severity | when |
|---|---|---|
| `render.failed` | warning | a view was not produced; `where` is the view name, and the other views are still written |
| `render.region-empty` | warning | the region holds no copper, hole or open connection; the file is still written |
| `render.copper-simulated` | info | a zone in the region is drawn from its simulated pour or its outline, not from a saved fill; `where` is the zone |

A render is a review artefact, never a gate: `render` exits 0 whenever the tool is found, and a region render
needs no tool.

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

For a board, `result.stackup` (c0101) is `null` when the board holds no stack-up that KiCad uses, and
otherwise holds `thickness` (the sum of the entries, in nm), `finish`, `impedance_controlled` and
`layers`: one object per entry, top to bottom, with `name`, `kind` and `thickness`, and with
`dielectric_kind`, `material`, `epsilon_r`, `loss_tangent` and `color` when they are set. Footprint files
and symbol libraries do not carry the key. The `kicad.board.stackup-*` codes of the reader are reported as
issues.

For a board, `result.via_protection` (c0112) holds three objects, each with the eight fields
`tenting_front`, `tenting_back`, `covering_front`, `covering_back`, `plugging_front`, `plugging_back`,
`capping` and `filling`. `default` holds the board's effective default as booleans, and `source`: `board`
when the board states a default, `kicad` when KiCad's own applies (tented on both sides, nothing else).
`effective` holds, per field, the number of vias for which the value is true, by their own value or by
the default; `by_default` how many of those take it from the default. On `kicad-cli` 10.0.6 a covering,
plugging, capping or filling counted in `by_default` reaches no fabrication file: the drill side files
and the IPC-2581 export hold only the vias that carry the value themselves. For an Altium PCB document
(`altium_pcbdoc`) the key holds the same three objects: `default` has `source` `altium` and every field
`false`, because an Altium via carries its own tenting flags and no default applies; `effective` counts
the vias whose top and bottom tenting flag is set, under `tenting_front` and `tenting_back`, and 0 for
the six other fields; `by_default` is 0 everywhere. The two flags are `INFERRED` (`H-A-PCB-CU-VIATENT`).
Footprint files, symbol libraries, Altium libraries and schematic documents do not carry the key.

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

`fenolite doctor --sessions PATH` runs no tool and reports instead what may stand between a command and
the user's files (change c0201; `docs/file-safety.md`): `result.sessions` lists every CAD lock file under
`PATH` (`path`, `lock`, `tool`, and `stale` when the file it names is gone), with one `safety.open-session`
each, and `result.online_only` the files a sync client keeps only online, with one `safety.placeholder`
each. Only KiCad's lock file (`~<file name>.lck`, S-0828, S-0829) is known; another tool's lock is not
detected. **Open sessions:** every writing command adds one `safety.open-session` (warning) to its reply
for each file of its plan that has such a lock beside it.

| code | severity | when |
|---|---|---|
| `doctor.tool-missing` | warning | a tool is absent, or `--kicad-cli` or `FENOLITE_KICAD_CLI` names a missing file |
| `doctor.tool-unsupported` | warning | a candidate's major is not 9 or 10, or it reports no version |
| `doctor.help-unparsed` | warning | a help page did not parse |

`doctor` exits 0. Its evidence is the help-matrix evidence with the oracle of the selected candidate
when every help page parsed, `UNVERIFIED` otherwise and with `--no-run`.

## place

`fenolite place PATH [--strategy grid|manual|constrained|regions|reuse|group] [--move REF=X,Y[,ROT[,SIDE]]]...
[--only REF,…] [--pitch L] [--gap L] [--margin L] [--force] [-o OUT]` moves footprints of the board that `PATH` names
(a `.kicad_pcb`, a `.kicad_pro` or a project folder) and runs no tool but with `--drc` ("Layout reuse"). It is a mutating command: nothing
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
- After the moves, the legality check judges the whole layout, the rule areas of the board that forbid
  footprints included. With a `place.*` error and without `--force` the command plans no write and
  exits 5; with `--force` it writes and still reports the issues. `--force` also moves a footprint that
  is locked on the board.
- The grid leaves the bounding box of every rule area that forbids footprints free, as it does for
  cut-outs.
- The placement rules of a built project (`.fenolite/rules.json`, read once with the locked placements)
  are judged on the layout after the moves. Each `placement.*` issue is a warning at most and never
  refuses the write: `check` is the gate.

`result` holds `board`, `strategy`, `moved` (`ref`, `path`, `from` and `to`, each with `x` and `y` in
nanometres, `rotation` in microdegrees and `side`; sorted by reference), `unplaced` (the references
still off the board), `legality` (the number of issues by code), `rules` (the counts of the placement
rules by family, all 0 without rules; the family `height` only when the last build holds a height limit,
judged on the layout after the moves, change c0140) and `measures`: the measures of `placement.rules` (see "check") on
the layout after the moves, with `change`, `hpwl` and `ratsnest` after the moves minus before in
nanometres, both 0 when nothing moved. The evidence is `placement.EVIDENCE`, combined with
`placement.legality.KEEPOUT_EVIDENCE` (`H-K-PLACE-KEEPOUT`) when the board holds a rule area that forbids
footprints and with `INFERRED` when a placement rule was judged: a placement is never a verdict, and
KiCad's DRC judges the board.

| code | severity | when |
|---|---|---|
| `place.courtyard-overlap` | error | two courtyards on the same face overlap; `where` is `REF1,REF2`, sorted |
| `place.outside-outline` | error | a courtyard leaves the board outline or enters a cut-out |
| `place.no-definition` | error | a rotation or side change of a footprint whose library definition is not found |
| `place.locked` | error | a footprint that is locked on the board, without `--force` |
| `place.unknown-ref` | error | `--move` or `--only` names a reference that the board does not hold |
| `place.keepout` | error | a courtyard enters a rule area that forbids footprints, on the face the area's copper layer judges (`F.Cu` the front, `B.Cu` the back); KiCad's DRC reports the same part |
| `place.edge-clearance` | warning | a courtyard is closer to the board edge than the edge clearance |
| `place.no-room` | warning | the grid found no place for a part; it stays where it was |
| `place.copper-left` | warning | a moved footprint had copper ending on its pads; the copper stays |
| `place.script-locked` | warning | the part has a locked placement in `.fenolite/`; the next build restores it |
| `place.keepout-no-courtyard` | warning | the pads of a part without a courtyard lie in a rule area that forbids footprints; KiCad's DRC does not report such a part |
| `place.no-extent` | info | a footprint has neither a courtyard nor pad copper; it is not judged |
| `place.no-outline` | info | the board has no closed outline; only courtyard overlaps are judged |

`fenolite build` reports the same legality codes for the board it is about to write, each at most as a
warning (`result.placement` holds `ran`, `counts` and `rules`): a build never refuses for placement.
`place` and `build` also report the three `placement.*` codes of the table under "check", as warnings at
most.
`result.routers` lists registered routers; `--no-run` lists names without availability probes. The `freerouting` entry also holds `java` (the first line of `java -version`), `java_major` and `java_ok` (`java_major >= 25`): a jar without a suitable Java gives `doctor.tool-unsupported` naming Java 25, and a missing jar `doctor.tool-missing`. It holds `source` too, the place that gave the jar: `argument` (`--router-path`), `env` (`FENOLITE_FREEROUTING_JAR`), `fetched` (the tools folder, see [fetch](#fetch)) or `null` without a jar; the reason of a missing jar names `fenolite fetch freerouting --confirm`.

### Constrained placement request

`place --strategy constrained [--constraints FILE] [--only REF,...] [--max-candidates N]
[--preview-dir DIR]` reports a bounded translation proposal in `result.placement`. The integer JSON
request schema is `fenolite.placement-request.v0`; `constraints` and `objectives` use exact entity
identities. `--force` is refused. Locked and unselected footprints remain fixed.

`result.placement.assessment` reports `findings`, `incomplete` or `checked` for the supplied placement
checks. It retains intrinsic copper findings, missing verifiers, unknown geometry, unplaced parts
and unmet objectives. It establishes no electrical or manufacturing qualification. Exact source
and request hashes accompany the proposal. A missing optional body verifier is explicitly reported.

| code | severity | when |
|---|---|---|
| `place.constraint` | error | supplied hard geometry, group region or mechanical constraints are violated |
| `place.incomplete` | warning | geometry or a required verifier is missing, or the bounded search leaves a footprint unplaced |
| `place.objective` | warning | a requested pad proximity or connection objective is unmet |

SVG previews come from serialized board readback, use the same dry-run/confirm transaction and
receipts, and report the written-board hash. See [placement](placement.md) for frames and objectives.

### Region placement

`place --strategy regions [--barrier REF[,REF...]]... [--group NAME=GLOB[,GLOB...]]...
[--region NAME=X1,Y1,X2,Y2]... [--split x|y] [--only REF,...]` (change c0205) places the staged parts,
or those of `--only`, domain by domain, each domain in its own region of the board, under the same
mutation protocol, legality check, `--force`, `--pitch`, `--gap` and `--margin` as the grid.

- **Domains.** Without `--group`, a domain is an island of `analysis.ties.isolation_islands` once the
  `--barrier` parts are removed, named `D1`, `D2`, … in band order. With `--group`, a domain is the parts
  whose reference matches one of the group's globs (`fnmatch`, case-sensitive; the first group wins), in the
  order given. A part in no domain stays where it was (`place.region-unassigned`).
- **Regions.** `--region NAME=X1,Y1,X2,Y2` (lengths with a unit, from the top-left corner of the outline,
  Y down, as `--move`) gives each group its rectangle; it needs `--group`, and every group needs a region.
  Without it, the bounding box of the outline is cut into one band per domain along `--split` (default:
  the longer side). Each band first gets the widest of its staged boxes plus twice the margin; the rest is
  shared in proportion to the courtyard-box area of the domain's parts. The islands are ordered so that
  the two domains of each barrier are neighbouring bands where a chain allows it.
- **Barriers.** A `--barrier` part whose pins lie in exactly two domains whose regions touch is placed
  first, centred across the boundary between them; otherwise it is packed inside its first domain's
  region (`place.region-barrier`). Parts keep their rotation and side.
- **Packing.** Each region is packed by `placement.grid.place`, inset by `--margin`, around the parts on
  the board and the parts placed before. A part that fits nowhere stays (`place.no-room`).
- **Crossings.** After the moves, every open connection of `analysis.connectivity` whose two ends lie in
  two regions counts against that pair (`place.region-crossing`).

`result.regions` is `null` when nothing was staged, else `source` (`islands` or `groups`), `axis` (`x`,
`y` or `null` with `--region`), `rows` (per region: `name`, `box` relative to the outline's top-left
corner, `nets` (islands only), `parts`, `placed`, `unplaced`, `area` and `used` in nm², `fill_permille`
rounded down), `barriers` (`ref`, `sides`, `status` `boundary`, `inside` or `unplaced`), `unassigned`, and
`crossings` (`between`, `open`, `nets`). The evidence adds `INFERRED` (`H-G-REGION-PLACE`), and
`H-G-TIES` for islands. The options of this strategy with another one are `FEN-2001`, as is a malformed
or inconsistent `--group` or `--region`.

| code | severity | when |
|---|---|---|
| `place.region-unassigned` | warning | a staged part has no net (islands) or matches no group; it stays where it was |
| `place.region-barrier` | warning | a barrier has pins in one domain, or in more than two, or its two regions do not touch; it is packed inside its first domain's region |
| `place.region-crossing` | warning | open connections join pads in two regions after the moves; `where` is `A|B` |

### Layout reuse

`place --strategy reuse --from REFERENCE --only REF[,REF...] [--anchor REF] [--map TARGET=REFERENCE]...
[--copper] [--tolerance L] [--drc]` (change c0210; `--from` implies the strategy) copies the placement,
and with `--copper` the copper, of a block of a reference board onto the `--only` parts of the board,
fitted by their pads, under the same mutation protocol, legality check, placement rules and measures as
the grid (`docs/placement.md`, "Layout reuse"). `REFERENCE` is any board that a backend reads. `--force`
is refused, and the options of this strategy with another one are `FEN-2001`.

- **Pairs.** Each part's reference part has the same reference, or the one `--map TARGET=REFERENCE`
  gives. Pads are paired by number, only numbers that occur once in both footprints. The other pads are
  paired by net partition (change c0227): the pairs by number map each reference net to one target net;
  in a part, a net with one such pad on each side pairs them, and with more each pad pairs with the
  reference pad whose goal lies nearest its image under the fit by number, both ways and within the
  tolerance. Any other pad stays unpaired.
- **Block transform.** A rigid transform (a quarter turn, a mirror and a translation, by least squares)
  is fitted on the pads of `--anchor` (default: the first of `--only`), which stays where it is. A mirror
  is found from the pads, so a reference drawn with the Y axis up is copied correctly.
- **Parts.** Each part is fitted onto the block transform of its reference part's pads, over the same
  candidates; its new angle and side come from the fit. A fit that leaves a pad farther than
  `--tolerance` (default `0.05mm`) from its goal places nothing (`reuse.no-fit`); a part placed on the side
  opposite to the one the block gives it is `reuse.mirror-suspected`. A turn or a side change needs the
  part's library definition through the project's `fp-lib-table` (`place.no-definition`), and a locked
  part is not moved (`place.locked`).
- **Checks.** The moved pads are measured against their goals, and the copper check with the rules of the
  project beside the board compares the board after the moves with the board before; a new finding is
  `reuse.check-failed`. The legality check then judges the layout as for every strategy.
- **`--copper`** copies the reference tracks, arcs and vias joined to the paired pads through tracks,
  arcs, vias and those pads (not through fills or other pads). Each net maps to the target net of the pads
  paired with its pads; a net claimed by two target nets is left out (`net-ambiguous`), and the layers
  mirror in the stack when the anchor lies on the other side than its reference part. Then, pass after
  pass: copies with a free end and vias joined on fewer than two layers are pruned (`tidy.prune`), copies
  in a group that holds neither two pads nor one pad with a fill or copper of the board are an `island`, and copies that
  a new copper-check finding names are left out with the finding's code. The copies that stay are
  locked; the board is planned when a part moved or copper was copied.
- **Zones** (change c0227, with `--copper`): a zone of a block net whose stored fill joins paired pads
  only is copied, outline and fill, through the block transform; a zone read without an outline gets that
  of its fill (`detail` "outline rebuilt from its fill"). A zone that also joins an unpaired pad is
  `zone-beyond-block`, one of a block net without a fill over a paired pad `zone-unfilled`, and a copied
  zone whose group lost the image of one of its pads `pad-lost`. A copied zone gives `reuse.fill-stale`.
- **`--drc`** runs `kicad-cli` DRC (the tool `check` finds; exit 6 without one) on copies of the board as
  it is and as it would be written, with the project files; a violation type with more entries gives
  `reuse.drc-new` and no write.

`result.reuse` holds `reference`, `anchor`, `tolerance`, `transform` (`null`, or `rotation` in
microdegrees, `mirror`, `x` and `y` in nanometres), `flipped`, `parts` (per part `ref`, `reference`,
`matched`, `by_net` (the pads paired by net), `within`, `residual` in nanometres or `null`, `placed`, `moved`, `from`, `to` (`null` when not
placed; `x`, `y`, `rotation`, `side`), `side_changed` and `mirror_suspected`), `copper` (`null` without
`--copper`, else `copied`, `items` with each copy's KiCad `uuid`, its `kind`, its `source` id, reference `net` and `detail`,
`dropped` with `item`, `kind`, `net`, `reason` and `detail`, `counts` by reason and `passes`),
`copper_check` (`before`, `placed` and `new` finding counts) and `drc` (`null`, or `tool_version`,
`before`, `after` and `new`, the violation types that grew). The evidence adds `INFERRED`
(`H-G-REUSE-FIT`, the rows of the copper check with `--copper`, and those of the reference board read);
after `--drc` found nothing new, `KICAD-VERIFIED` (`H-K-REUSE-DRC`) combined with the reference board
read.

| code | severity | when |
|---|---|---|
| `reuse.no-fit` | error | a part, or the anchor, has no paired pad or no fit within the tolerance; it is not placed |
| `reuse.unknown-part` | error | a part is not on the target board, or its reference part not on the reference board |
| `reuse.check-failed` | error | a moved pad is off its goal, or the copper check finds something the board before lacks; nothing is written |
| `reuse.drc-new` | error | with `--drc`, a DRC violation type has more entries on the written board; nothing is written |
| `reuse.mirror-suspected` | warning | a part fits only on the side opposite to the one the block gives it |
| `reuse.project-unread` | warning | the project or rules file beside the board could not be read; the copper check runs without it |
| `reuse.copper-dropped` | info | reference copper of the block was not copied; `where` is the reason |
| `reuse.fill-stale` | info | copper was copied onto a board with filled zones, or a zone with its reference fill; run `fill` before `check` |

### Group moves

`place --turn REF[,REF...] --about X,Y --angle DEGREES` or `place --shift REF[,REF...] --by DX,DY`
(change c0227; either implies `--strategy group`) moves a group of parts rigidly under the same mutation
protocol, legality check, placement rules and measures as the grid. `X,Y` is in the frame of `--move`;
`DEGREES` turns counter-clockwise on screen, as `ROT` of `--move`. `--force` moves locked parts.

- **Parts.** Each part's new placement is the move composed with its placement, so a part on the bottom
  keeps its pads on the moved positions; a turn needs the part's library definition
  (`place.no-definition`). Every moved pad is measured against the move of its old position: farther than
  1 µm is `place.group-failed`.
- **Copper.** Each joined group of a net (tracks, arcs, vias and pads, without fills) that holds a pad of
  the group and no other pad moves with it, and each zone whose stored fill joins pads of the group only
  (`place.fill-stale`). Copper that joins a pad of the group to another pad stays (`place.copper-left`).
  The copper check with the rules of the project beside the board compares the board before and after;
  a new finding is `place.group-failed` and nothing is written.
- **`--pose-search`** with `--turn` and `--about`, and `--within LENGTH` instead of `--angle`, tries the
  four quarter turns about the point with every shift of step `--pitch` (default `0.5mm`) within
  `--within` on each axis (at most 10 000 poses), and writes nothing. The demand of a pose is, per net
  with a pad in the group and one outside, the shortest distance between a moved pad of the group and a
  pad outside, rounded up, summed.

`result.group` holds `refs`, `kind` (`turn`, `shift` or `pose-search`), `transform` (`null` for a search,
or `rotation` in microdegrees and `x`, `y` in nanometres: `p ↦ R·p + (x, y)`), `copper` (`items` and
`zones` moved), `residual` (the largest pad distance from its goal, or `null`), `copper_check` (`null`, or
`before`, `after` and `new` finding counts) and `search` (`null`, or `about`, `within`, `pitch`, `tried`,
`nets` crossing the border, `current`, the demand of the group where it is, and `poses`, the ten of least
demand with `rotation`, `dx`, `dy` and `demand`). The evidence adds `INFERRED` (`H-G-GROUP-MOVE` and the
rows of the copper check).

| code | severity | when |
|---|---|---|
| `place.group-failed` | error | a moved pad is off its goal, the copper check finds something the board before lacks, or a project file beside the board cannot be read; nothing is written |
| `place.fill-stale` | info | a zone moved with the group keeps its moved fill; run `fill` before `check` |

## analyze

`fenolite analyze PATH [--kinds current,clearance,creepage,power,insulation,length,ties,domains,crossings,returns,decoupling,connectivity,bodies,relief,dead,coupling,necks,loops,balance] [--requirements FILE]
[--temp-rise KELVIN] [--copper-thickness [LAYER=]LENGTH]... [--via-plating LENGTH]
[--board-thickness LENGTH] [--pair NET_A NET_B]... [--within LENGTH] [--arc-tol LENGTH]
[--path FROM TO]... [--resistivity NANOOHM_METRES] [--groove-width LENGTH] [--net GLOB]...
[--from REF]... [--tie REF]... [--tie-item ID[,ID...]]... [--domains A=GLOB,B=GLOB] [--sense NET[,NET...]]...
[--barrier REF[,REF...]]... [--cut X1,Y1,X2,Y2]... [--width LENGTH] [--clearance LENGTH] [--reference NET[,NET...]]...
[--via-distance LENGTH] [--pour-grid LENGTH] [--dead-distance LENGTH] [--aggressor GLOB]... [--victim GLOB]...
[--split] [--loop-baseline FILE]` measures the current
capacity of tracks, arcs and vias, and the clearance and creepage of pairs of nets, on a board that a
registered backend reads. On request it also measures power paths (`power`) and the insulation between
layers (`insulation`). It is read-only: it runs no tool and writes no file. The user guide is
`docs/analyses.md`.

**Fenolite measures and the user decides.** No reply claims conformance to a standard. Fenolite ships no
requirement value and assumes no thickness and no temperature rise: an input that is not given leaves
items out, which are counted (`analysis.input-missing`). A finding exists only against a requirement of
the user's file.

- `--kinds` selects the analyses. The default is `current,clearance,creepage`; `power` and `insulation`
  run only when named, so a reply without them holds neither. `clearance`, `creepage` and `insulation`
  come from one pass; an unselected kind is left out of each row.
- `--path FROM TO` (repeatable, with `power`) measures the copper between two sets of pads, `FROM` and
  `TO` each one or more `REF-PIN` names joined by commas. A `[[path]]` row of the requirements file is
  measured and judged. `--resistivity NANOOHM_METRES` is the resistivity of your copper, a decimal number
  of at most three decimals; it is passed on in picoohm-metres, and without it no path has a resistance.
  Fenolite assumes no resistivity. The capacities and the resistance are estimates against your limits,
  not a simulation.
- `--groove-width LENGTH` (with `creepage`) bridges every groove narrower than that width on the creepage
  path; a `groove_nm` of a distance row does the same for its pairs, and the larger of the two governs.
- With `insulation`, each row of `distances` also holds the distance through the laminate between copper
  of the two nets on two layers, from the depths of the board's stack-up. Fenolite assumes no thickness:
  without those depths the value is absent and `analysis.input-missing` names `stack-up`.
- `--path` and `--resistivity` without the kind `power`, and `--groove-width` without the kind
  `creepage`, are usage errors (`FEN-2001`, exit 2).
- The kind `length` (on request, change c0106; `docs/analyses.md`, "Length") measures the nets whose
  name matches a `--net GLOB` (repeatable; shell-style patterns, case-sensitive). `--from REF` or
  `--from REF-PIN` (repeatable) chooses the start pad of the paths of a net; the default is its first
  pad by reference and number. The total of a net is counted as the KiCad major of the global
  `--kicad-version` counts it in its DRC (10 by default). `result.lengths` holds one row per net:
  `net`, `routed`, `vias`, `die`, `total` (their sum), `via_count`, `start` (`REF-PIN` or `null`),
  `paths` (`end`, `length` or `null`, `vias`, `layers`) and `off_path`, all lengths in nm.
  `result.pairs` holds the pair rows (`name`, `p`, `n`, `total_p`, `total_n`, `skew`, `path_skew`), one
  per differential pair whose two nets were both measured: each pair interface of the design (`diff_pair`,
  `usb2`) under its name, then each two measured nets that the pair name rule couples (`docs/dsl.md`,
  "Differential pairs") under their base, sorted by name; `skew` is `total_p - total_n`, and `path_skew`
  the same difference of the two paths when each net has exactly two pads. `result.summary.length` holds `nets`, `major`,
  `stackup` (`board`, `default` or `none`) and `count_vias`, and `result.inputs` gains `nets`, `from`
  and `kicad_version`. The kind judges nothing, so it alone exits 0. On input whose backend gives no
  length facts (an Altium PCB document) the rows hold routed lengths only, `major` is `null`, one
  `analysis.input-missing` names `length facts`, the level is `UNVERIFIED` and `--kicad-version`
  changes nothing. `--net` and `--from` without the kind `length` are usage errors (`FEN-2001`, exit 2).
- The kind `ties` (on request, change c0198; `docs/analyses.md`, "Ground ties") proves ties by removing
  exactly their copper. `--tie REF` (repeatable) names a part, whose pads are removed. `--tie-item
  ID[,ID...]` (repeatable, one tie per option) names tracks, arcs, vias or zones by model id, KiCad uuid or
  locator. `--domains A=GLOB,B=GLOB` names two domains of pads by `REF-PIN` pattern (a name may repeat).
  `--sense NET[,NET...]` (repeatable) names sense nets. The kind needs a tie or a sense net.
  - `result.ties` holds one row per tie that names something: `tie`, `nets`, `removed` (items with `kind`,
    `id`, `where`, `net`, `layer`), `groups` (the pads of each part left that touches the tie), `split`,
    `path` (the shortest other path when there is one group), `extra` (stray pads of a domain) and `zones`
    (`filled`, `unfilled` or `none`).
  - `result.sense` holds one row per sense net with copper: `net`, `items` and `shared` (the items of other
    nets it touches).
  - `result.summary.ties` counts `ties`, `split`, `sense` and `shared`, and `result.inputs` gains `ties`,
    `domains` and `sense`.
- The kind `domains` (on request) reads no copper. With `--barrier REF[,REF...]` (repeatable, required) it
  joins the nets of every other part. `result.domains` holds the islands (`nets`, `barriers`, sorted),
  `result.summary.domains.islands` their count, and `result.inputs.barriers` the barriers.
- The kind `crossings` (on request, change c0199; `docs/analyses.md`, "Barrier crossings") counts the free
  ways across each `--cut X1,Y1,X2,Y2` (repeatable, required, four lengths with units, two different ends)
  on each copper layer. `--width` and `--clearance` give the new track; by default the narrowest class
  width and its class's clearance.
  - `result.crossings` holds one row per cut: `cut`, `a`, `b`, `length`, `width`, `clearance`, `layers`
    (per copper layer: `layer`, `ways` with `start`, `end`, `length`, `tracks`, `a`, `b`, the layer's
    `tracks`, and its `obstacles` with `start`, `end`, `kind`, `where`), `supply` (the tracks of all
    layers), `demand` (per net: `net`, `open`, `routed`), `open` and `routed`.
  - `result.summary.crossings` counts `cuts` and `short`, and `result.inputs` gains `cuts`, `width` and
    `clearance`.
  - `--cut`, `--width` and `--clearance` without the kind, the kind without `--cut`, and a malformed cut
    are usage errors (`FEN-2001`, exit 2). `analysis.crossings-short` is a warning, so the kind alone exits
    0.
- The kind `returns` (on request, change c0202; `docs/analyses.md`, "Return paths") checks the return paths
  of the nets that a `--net GLOB` (repeatable, required) matches. `--reference NET[,NET...]` (repeatable)
  names the reference nets (default: every other net with a fill on a neighbouring copper layer), and
  `--via-distance LENGTH` judges the distance from each via to the nearest reference via.
  - `result.returns` holds one row per net: `net`, `length`, `unreferenced`, `spans` (`layer`, `where`,
    `start`, `end`, `length`, `kind`: `split` or `edge`) and `vias` (`where`, `at`, `nearest`,
    `distance`).
  - `result.summary.returns` counts `nets`, `split` and `edge`; `result.inputs` gains `nets`, `reference`
    and `via_distance`.
  - The kind without `--net`, and `--reference` or `--via-distance` without it, are usage errors
    (`FEN-2001`, exit 2). Its findings are warnings, so the kind alone exits 0.
- The practice kinds (on request, change c0204; `docs/analyses.md`, "Practice checks") report facts and
  judge only against rows of the requirements file:
  - `connectivity`, `dead`, `bodies` and `relief` take each zone layer in a copper state, listed in
    `result.pours` (`zone_id`, `where`, `net`, `layer`, `priority`, `state`: `saved_fill`, `simulated` or
    `outline`, `reason`, `cells`, `dropped`). A zone without a fill, or with a stale fill, is poured on a
    raster of `--pour-grid LENGTH` (default 0.1 mm); `result.inputs.pour_grid` holds it.
  - `result.connectivity` holds one row per net that owns a zone or falls apart: `net`, `groups` (the pads
    of each group), `split`, `copper`; `result.summary.connectivity` counts `nets`, `split`, `simulated`
    and `outline`.
  - `result.dead` holds `net`, `kind`, `where`, `layer`, `reason` (`island` or `far`), `distance`,
    `copper`; `--dead-distance LENGTH` adds the `far` rows. `result.summary.dead` counts `islands`, `far`
    and `dropped`; `result.inputs.dead_distance` holds the option.
  - `result.decoupling` holds one row per pad of a power-input pin: `pin`, `net`, `capacitor`, `distance`
    (along copper), `straight`, `ret`, `loop_area_nm2`, `limit` (of a `[[decoupling]]` row);
    `result.summary.decoupling` counts `pins` and `far`.
  - `result.bodies` holds one row per `[[body_copper]]` row, part and layer with copper of the class:
    `requirement`, `part`, `plan` (`body` or `courtyard`), `layer`, `nets`, `items`, `copper`. Without a
    row the kind reports `analysis.input-missing`.
  - `result.relief` holds one row per pad joined by thermal relief: `pad`, `net`, `zone`, `layer`,
    `copper`, `spokes`, `width`, `milliamps`, `capacity_ma`.
- The kind `coupling` (on request, change c0204; `docs/analyses.md`, "Coupling screen") needs
  `--aggressor GLOB` and `--victim GLOB` (both repeatable). `result.coupling` holds one row per pair,
  sorted by score: `aggressor`, `victim`, `parallel`, `gap`, `score`, `broadside`, `layers`;
  `result.coupling_victims` holds `net`, `length`, `referenced_permille`. `result.summary.coupling` holds
  `pairs`, `victims`, `heights` (the `h` of each layer) and `note`: the score ranks pairs, it is not a
  voltage. `result.inputs` gains `aggressors` and `victims`. Nothing is judged.
- The pour-shape kinds (on request, change c0213; `docs/analyses.md`, "Pour shapes") take the zones in
  their copper states, as the practice kinds do, and list them in `result.pours`:
  - `result.necks` holds one row per place narrower than the `[[neck]]` row of its net: `net`, `layer`,
    `shape` (`neck`, `tip` or `sliver`), `at` (`x`, `y`), `width`, `limit`, `requirement`, `extent` (of a
    tip), `copper`. `result.summary.necks` counts `nets`, `necks`, `tips`, `slivers` and `skipped`.
    Without a row the kind reports `analysis.input-missing`.
  - `result.loops` holds one row per `[[loop]]` row: `name`, `pads`, `area_nm2`, `legs` (`start`, `end`,
    `kind`: `copper` or `straight`, `length`), `limit`, `baseline_nm2`, `change_nm2`; `--loop-baseline
    FILE` measures the rows on that board too, and `result.inputs.loop_baseline` names it.
    `result.summary.loops` counts `loops` and `above`.
  - `result.balance` holds one row per part with two SMD pads on one layer: `part`, `pads`, `layer`,
    `copper_nm2` (one per pad), `ratio_permille`, `copper`. Nothing is judged.
- `--split` (with `power`, change c0213; `docs/analyses.md`, "The split of the current") solves each power
  path on the raster of `--pour-grid`. `result.split` holds one row per path solved: `net`, `start`, `end`,
  `milliamps`, `elements` (`kind`, `where`, `layer`, `share_permille`, `milliamps`), `resistance_uohm`
  (with `--resistivity`), `bounds` (the interval of the power row), `within`, `nodes`, `iterations`,
  `converged`. `result.summary.split` counts `paths` and `unsolved` and gives the `grid`;
  `result.inputs.split` says whether it ran. A path whose thickness, plating or stack-up is missing is not
  solved, and `analysis.input-missing` names what is missing.
- `--pour-grid` without `--split` or one of `connectivity`, `bodies`, `relief`, `dead`, `necks`, `loops` and
  `balance`, `--dead-distance` without `dead`, `--aggressor` or `--victim` without `coupling`, `coupling`
  without both, `--split` without `power` and `--loop-baseline` without `loops` are usage errors
  (`FEN-2001`, exit 2).
- `--tie`, `--tie-item`, `--domains` and `--sense` without the kind `ties`, `--barrier` without `domains`,
  either kind without its option, `--domains` without exactly two names and an empty name in a list are
  usage errors (`FEN-2001`, exit 2).
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
  both nets), `clearance` and `creepage`, and with the kind `insulation` also `insulation` and `sheets`
  (the count of dielectric entries of the stack-up between the two layers). A measure holds `low` and
  `high` in nanometres, `layer`, `points`, `items`, `bounded` and `over`, the names of the conductors of
  other nets, or of none, that the path crosses at no length;
- `power` (with the kind `power`): one row per path with `net`, `start`, `end`, `milliamps`,
  `temp_rise_mk`, `elements`, `resistance_uohm` and `drop_mv`. An element is an active part of a track or
  arc, a via group or a fill, with `kind`, `where`, `layer`, `series`, `area_nm2`, `section` (the
  narrowest section of a fill, a measure), `ports`, `capacity_ma`, `in_range`, `resistance_uohm` and
  `hull_free`. A resistance and a drop are intervals `low` and `high` in microohms and millivolts; `high`
  is `null` when no upper bound is known;
- `summary`: per analysis, the counts; `current.nets` names the weakest item of each net, `current.fit`
  the source id of the fit, and `distances.faces_alone` the pairs measured on each face alone because the
  board thickness or outline is unknown;
- `summary.power`: the counts of paths and elements and the inputs that were missing;
  `summary.distances.grooves` (when a groove width was used): per width, the grooves `bridged` and
  `counted`;
- `inputs`: the option values in force, `paths`, `resistivity_pohm_m` and `groove_nm` among them, and the
  boundary (`source`, `band`, `cutouts`).

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
| `analysis.path-unmatched` | warning | a power path names a pad the board does not hold, or pads of more than one net |
| `analysis.path-open` | warning | the copper of the net does not join the start pads to the end pads |
| `analysis.path-exceeded` | error | an element that carries the whole current of the path has a capacity below it |
| `analysis.path-undecided` | warning | an element whose share of the current is not computed, or whose section is only a bound, has a capacity below the whole current |
| `analysis.drop-above` | error | the low end of the drop is above `drop_mv` |
| `analysis.drop-undecided` | warning | `drop_mv` lies inside the drop interval, or the drop has no high end |
| `analysis.insulation-below` | error | `insulation.high` is below `insulation_nm` |
| `analysis.insulation-undecided` | warning | `insulation_nm` lies inside the insulation interval |
| `analysis.creepage-over` | info | a clearance or a creepage of the pair crosses copper of a third net |
| `analysis.length-open` | warning | pads of a measured net that its copper does not join to the start pad |
| `analysis.length-stub` | info | copper of a measured net on no path from its start pad, with its length |
| `analysis.tie-parallel` | error | removing a tie splits nothing: another path joins its sides |
| `analysis.tie-extra` | error | after a split, a group holds pads of both `--domains` |
| `analysis.tie-dangling` | warning | a tie touches fewer than two copper items, so it joins nothing |
| `analysis.tie-unmatched` | warning | a tie, a sense net or a barrier part names nothing on the board |
| `analysis.crossings-short` | warning | a cut must carry more open connections than the tracks its ways fit on all layers |
| `analysis.return-split` | warning | a track crosses a gap of its reference copper on the neighbouring layer |
| `analysis.return-via` | warning | a via has no reference via within `--via-distance` |
| `analysis.sense-shared` | error | copper of a sense net touches copper of another net outside a net-tie group |
| `analysis.net-split` | warning | the copper of a net, every zone in its copper state, falls into more than one group of pads |
| `analysis.copper-dead` | warning | a fill polygon is joined to no pad of its net |
| `analysis.copper-far` | warning | copper lies farther than `--dead-distance` from every pad of its net |
| `analysis.decoupling-far` | error | a supply pin's nearest capacitor is farther along copper than its `[[decoupling]]` row allows, or none is joined |
| `analysis.body-copper` | error | copper of a class of a `[[body_copper]]` row lies under a part it names on a layer it forbids |
| `analysis.relief-exceeded` | error | the spokes of a thermal relief carry less than the `[[current]]` row of the pad's net |
| `analysis.neck-narrow` | error | a pour narrows below the `min_width_nm` of the `[[neck]]` row of its net: a neck, a tip or a sliver |
| `analysis.loop-area` | error | the closed path through the pads of a `[[loop]]` row encloses more than its `max_area_nm2` |
| `kicad.length.default-stackup` | info | the board holds no stack-up, so via heights are counted on the default stack-up KiCad assumes |
| `kicad.length.bad-die` | warning | a pad's die length is not a non-negative decimal; it counts as 0 |

**Thicknesses from the stack-up (c0101).** A KiCad board whose `setup` holds a complete stack-up gives
`analyze` the copper thickness of each copper layer and the board thickness with no option; an option
keeps winning. `result.inputs.board_thickness_source` is `option`, `stackup` or `null`, and
`result.inputs.stackup` is `null` or `{"thickness": <nm>, "copper": {<layer>: <nm>}}`. A board without a
stack-up and without options gets the `analysis.input-missing` warnings as before.

## copper

`fenolite copper PATH [--roles FILE] [--requirements FILE] [--kinds KIND,...] [--net GLOB]...
[--layers KIND=L,L]... [--ground-layers L,L] [--ground-fill reference|all] [--connection KIND=MODE]...
[--stitch-pitch LENGTH] [--temp-rise KELVIN] [--widen PERMILLE] [--no-corridors] [--regenerate KEY]...
[--gate drc [--kicad-cli PATH]] [--timeout SECONDS] [--dry-run | --confirm [--plan ID]]` generates the
power, switch-node, ground and high-voltage copper of a KiCad board from its confirmed and declared net
roles (schema `fenolite.copper.v0`, change c0243). `PATH` is a `.kicad_pcb`, a `.kicad_pro` or a project
folder that Fenolite built. The user guide is `docs/roles.md`, "Role copper".

- The roles are those that `fenolite roles` stored for the board (or `--roles FILE`) and those of the
  project's `.fenolite/rules.json`. An inferred role that is not confirmed gets no copper
  (`roles.copper-skipped`); a net that already holds the user's zone on a layer gets none there.
- It is a writing command of the mutation protocol ("Writing files"): `--dry-run` plans the board, the
  manifest `.fenolite/role-copper.json` and, when the plan holds role rules (`role.sw.*`, `role.hv.*`),
  the project's `.kicad_dru`; `--confirm --plan ID` writes them together. A plan that changes nothing
  writes nothing: `result.changed` is false and no `plan_id` is given.
- `result.nets` holds one row per role net (`net`, `kind`, `method`, `width`, `max_width`, `layers`,
  `zones`, `skipped`, `vias`); `result.corridors` the corridors of the critical routes, each with its
  `origin` (`provisional`, written by this run, or `found`, phase 2's); `result.cleared` the role findings
  that the copper cleared; `result.kept` the role items the user edited, which are kept
  (`roles.copper-kept`, `--regenerate KEY` to have one generated again); `result.next` the commands to run
  after a write (`fenolite fill`, `fenolite check`).
- The board is judged before and after on the simulated pour; a new role finding of warning or above is
  `roles.copper-worse` (error, exit 5) and nothing is written.
- `--gate drc` refills and checks the planned board with `kicad-cli` (exit 6 without it) and adds
  `result.gate`.
- A `.PcbDoc` and a bad option are `FEN-2001`, exit 2: an Altium board gets role copper through a build of
  its script with `design.role_copper()`. Every reply carries the evidence level `INFERRED`.

## roles

`fenolite roles PATH [--roles FILE] [--net GLOB]... [--kinds KIND,...] [--class REF=CLASS]... [--check]
[--requirements FILE] [--temp-rise KELVIN] [--copper-thickness [LAYER=]LENGTH]... [--via-plating LENGTH]
[--board-thickness LENGTH] [--pour-grid LENGTH] [--split] [--arc-tol LENGTH] [--current NET=AMPS]...
[--accept NET[,NET...]]... [--accept-all [--min-confidence high|medium]] [--set NET=KIND[:KEY=N]...]...
[--reject NET]... [--accept-group NAME]... [--reject-group NAME]... [--dry-run | --confirm [--plan ID]]`
infers, shows, confirms and checks the net roles of a board (schema `fenolite.roles.v0`, change c0222).
`PATH` is a board, or a project folder, that a registered backend reads. The user guide is
`docs/roles.md`.

- Without `--current`, an accept, a set or a reject option the command is read-only. `result.roles` holds
  one row per net (`net`, `kind`, `source`, `rule`, `confidence`, `pads`, `milliamps`, `working_mv`,
  `sensitive`), filtered by `--net` and `--kinds`; `result.loops`, `result.kelvins` and `result.gates` hold
  the groups; `result.classes` the class of each part with its evidence; `result.store` the file the roles
  are kept in (`.fenolite/rules.json` of a project that Fenolite built, else the role document
  `<board stem>.roles.json` beside the board or `--roles FILE`), relative to the board's folder.
- `--class REF=CLASS` states a part's class for the inference (one of the classes of `docs/roles.md`).
- `--check` measures the board against its roles through the analyses of `docs/analyses.md` and adds
  `result.measures` (each with `kind`, `subject`, `analysis`, `copper` and `values`), `result.summary` and
  `result.requirements` (change c0253): the requirement table ("Circuit stage") of the role checks and, for
  a project that Fenolite built, of the stage `circuit.rules` on its `.fenolite/` model, sorted by `id`. A
  `[[current]]` row of `--requirements`, and after it `--current NET=AMPS`, bound the current of their nets
  for the circuit rows too, with source `user` and the row's `source` text, `requirements.toml` or
  `--current` as basis; neither bounds a net that a rig or a rail bounds. Without `--check` the result holds
  no `requirements`. It runs no tool. The measuring options are those of `analyze`, parsed by the same code with the same
  errors; without `--check` each of them is `FEN-2001`, exit 2.
- `--accept`, `--accept-all` (`--min-confidence` keeps roles and groups of at least that confidence),
  `--set NET=KIND[:milliamps=N][:working_mv=N][:sensitive=0|1]`, `--reject NET` (stored as a confirmed
  `signal`), `--accept-group`, `--reject-group` and `--current NET=AMPS` make it a writing command of the
  mutation protocol ("Writing files"): `--dry-run` plans the one file of `result.store.file`, and
  `--confirm --plan ID` writes it; nothing else is written, and the board file never. The reply shows the
  roles as they will be stored. A role that the design script declares cannot be changed here
  (`FEN-2001`): edit the script.
- A malformed role document or `.fenolite/` model is `FEN-3004`, exit 3. A finding against a default limit
  of the role profile is at most a `warning`; an inferred role that is not confirmed gives at most a
  `warning`, so such a run exits 0. Every reply carries the evidence level `INFERRED`.

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
`--manifest` (for `bom`, for `pnp` and for `testpoints`) also plans `fenolite-artifacts.json` in the folder
of `FILE`, merged as `export` merges it, with one entry of kind `bom`, `pnp` or `testpoints`: `tool` `fenolite <version>`,
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

## testpoints

`fenolite testpoints PATH [--side top|bottom|both] [--template FILE] [--min-coverage PERCENT]
[--min-pitch LENGTH] [--min-fiducials N] [--out FILE] [--manifest] [--place [--grid LENGTH] [--reach LENGTH]
[--size LENGTH] [--nets GLOB]... [--drc] [--kicad-cli PATH]]` reports the test points, the fiducials
and the non-plated holes of the board `PATH` names (resolved as for `pnp`, and read from the board file as
`pnp` reads it), and which nets a probe reaches (`docs/assembly.md`, "Test points"). It runs no tool. A
test point is a pad that carries the mark `test_point` and a fiducial is a footprint with a pad marked
`fiducial_global` or `fiducial_local` (`Pad.fab_property`, KiCad's fabrication property of a pad): marks
are read, never footprint names. An Altium document or project is refused as `pnp` refuses it: no Altium
record is known to hold such a mark.

`result` holds:

- `side`, the side a probe comes from (`--side`, default `both`);
- `test_points`: one object per marked pad with `ref` (the reference, or the footprint id of a footprint
  without a component), `path`, `pad`, `net` (`""` on no net), `position` (`[x, y]`), `side` (the
  footprint's), `access`, `shape`, `size` (`[width, height]`) and `drill`. `access` names the sides where
  the pad has both its copper layer and its mask layer: `top`, `bottom`, `both` or `none`. With `--side top`
  or `bottom`, a test point whose `access` does not include that side is left out. This list is the paged
  one (`--limit`, `--cursor`);
- `fiducials`: one object per footprint with a fiducial pad: `ref`, `path`, `position` and `size` of its
  first such pad, `side` and `scope` (`global` or `local`); with one side, only the fiducials of that side;
- `holes`: one object per `np_thru_hole` pad: `ref`, `path`, `position`, `drill`, `length` (of a slot, else
  `null`) and `tooling`, true for a footprint whose library name starts with
  `Fenolite_Assembly:ToolingHole_`. Holes are listed for every side;
- `coverage`: `eligible`, the nets with two pads or more; `covered`, those that hold a test point whose
  `access` includes the side (any access but `none` for `both`); and `uncovered`, the names of the others;
- `counts`: `test_points`, `fiducials_top`, `fiducials_bottom`, `holes`, `tooling_holes`;
- `template`, `units`, `origin` and `y_axis`, the frame of the CSV file.

Every length is an integer in nanometres in the board frame (X to the right, Y down).

`--min-coverage` is an integer from 0 to 100, `--min-pitch` a positive length with a unit (`1.27mm`) and
`--min-fiducials` an integer of at least 1; another value exits 2 (`FEN-2001`). Fenolite ships no target:
without the three values no error is given.

| code | severity | when |
|---|---|---|
| `testpoint.none` | info | no pad of the board carries the test-point mark; the hint names `design.test_point()` and `Footprint.pad(fab_property="test_point")`, and says that KiCad's library test points carry no mark |
| `testpoint.no-net` | warning | a test point is on no net |
| `testpoint.covered` | warning | a test point's `access` is `none`: no side has both its copper and its mask layer |
| `testpoint.coverage-low` | error | `--min-coverage` is given and `covered × 100 < PERCENT × eligible` |
| `testpoint.too-close` | error | `--min-pitch` is given and the centres of two test points whose `access` shares a side are closer than it; one issue per pair, compared exactly on squares of integers |
| `fiducial.too-few` | error | `--min-fiducials` is given and a side that the report covers holds a footprint with the attribute `smd`, without `dnp` and without a fiducial pad, and fewer global fiducials than `N`; one issue per side |
| `pnp.no-outline` | error | `--out` is given, the template has `origin = "outline"` and the board has no closed outline; no file is planned |

`--out FILE` plans one CSV file of kind `testpoints` through the mutation protocol. Its header is
`kind,ref,pad,net,x,y,side,access,width,height,drill`, with `kind` `test_point`, `fiducial`,
`tooling_hole` or `hole` and one row per report row in that order. Positions and sizes are printed in the
origin, Y axis, units and decimals of the template's `[placement]` table, sides by its side names, with
its CSV options, so test points and parts share one frame. No file is planned when a finding is an error.
`--manifest` also plans `fenolite-artifacts.json` in the folder of `FILE` with one entry of kind
`testpoints` (`tool` `fenolite <version>`, `from` the board's SHA-256, `evidence` the level of the
envelope); without `--out` it exits 2 (`FEN-2001`).

Exit codes: 0 without an error finding, 5 with one, 4 without `--dry-run` or `--confirm` when `--out` is
given, 2 for a usage error, 3 for a file that cannot be read. The evidence is `testpoints.EVIDENCE`
(`KICAD-VERIFIED`, `H-K-TESTPOINT-D356` and `H-K-PAD-FABPROP`) combined with the evidence of the board read,
so the reply takes the lower of the two.

### testpoints --place

`--place` (change c0229; `docs/assembly.md`, "Placing test points") needs `--side top` or `--side bottom`
and a `.kicad_pcb`; `--grid`, `--reach`, `--size`, `--nets`, `--drc` and `--kicad-cli` without `--place`, and
`--place` with `--side both`, exit 2 (`FEN-2001`). For each net of `coverage.uncovered` that a `--nets` glob
matches (all by default), in natural order, it adds one probe: the footprint of `design.test_point` (round
surface pad of `--size`, default 1 mm; reference `TP<n>` after the highest in use) on the first free site of a
grid of `--grid` (2.54 mm) within `--reach` (5 mm) of an anchor of the net on the side's outer layer (pad
centre, via, track or arc end), nearest first, then by y and x, joined by one straight track of the net's class
width (0.25 mm without one). Probe and track keep the clearance (the largest of the project's minimum, its class
clearances and 0.2 mm) from other nets' copper, holes and earlier probes, the edge clearance from the edge;
the probe touches no courtyard, silkscreen ink or rule area forbidding footprints or pads of its side, the track
no rule area forbidding tracks; probes keep `--min-pitch` (1.27 mm with `--place`). The probes are written
without `fenolite.path`, the designator on the side's fabrication layer, through the mutation protocol (the
board is replaced; `--out` stays the CSV file). Before writing, Fenolite's copper check with the project's rules
judges the board with and without the probes. With `--drc`, `kicad-cli` DRC runs on copies before and after,
by type, `lib_footprint_issues` and `lib_footprint_mismatch` aside.

The rest of `result` then describes the board as it would be written, and `result.place` holds `side`, `grid`,
`reach`, `size`, `min_pitch`, `clearance`, `edge_clearance`, `nets`, `before` and `after` (`eligible` and
`covered`), `probes` (`ref`, `net`, `position`, `anchor`, `track_length`, `track_width`), `unplaced` (`net`,
`site` or `null`, `blocker`) and `drc` (`tool_version`, `before`, `after`, `new`, or `null`).

| code | severity | when |
|---|---|---|
| `testpoint.no-site` | warning | a net has no free site; the message names the nearest site and its first blocker |
| `testpoint.check-failed` | warning | the copper check finds a new finding with a probe or its track; that probe is not written |
| `testpoint.drc-new` | error | with `--drc`, a DRC type grows; nothing is written |
| `testpoint.board-only` | info | probes were placed: a rebuild keeps them as board-only footprints (`layout.board-only`) |

The evidence is `INFERRED` (`H-K-TP-PLACE`), `KICAD-VERIFIED` with `--drc` and no type grown.

## silk

`fenolite silk PATH [--designators] [--clip] [--margin LENGTH] [--keep] [--refs GLOB]... [--sizes LENGTHS] [--angles 0,90] [--clearance LENGTH] [--gap LENGTH] [--measure auto|kicad|estimate] [-o FILE] [--drc] [--kicad-cli PATH] [--timeout SECONDS]` places the designators of a KiCad board on its silkscreen (change c0212; `docs/assembly.md`, "Designators") and cuts its silkscreen at the mask openings (change c0226; `docs/assembly.md`, "Clipping"). `PATH` accepts a board, matching project or folder; `--out` is relative to the working directory, otherwise the board is replaced. `--designators`, `--clip` or both are required (exit 2 otherwise); with both, the clip runs first and the designators avoid the cut strokes. `--margin` without `--clip` exits 2. The usual `--dry-run` plan and `--confirm` receipt protocol applies; the schema is `fenolite.silk.v0`.

- **Parts.** Every footprint whose visible `Reference` field is on a silkscreen layer, its reference matching `--refs` (repeatable `fnmatch` patterns; default every one). Its text goes on the silkscreen of the part's side, mirrored on the bottom. Other visible silkscreen texts stay where they are and are obstacles.
- **Ink.** The box of each text is measured with `kicad-cli` (`--measure kicad`; `auto`, the default, when a tool is found) and cached in `$FENOLITE_CACHE_DIR/silk` (else the user's cache folder), or estimated from Fenolite's glyph table (`--measure estimate`, or no tool: `silk.estimated`). `docs/formats/kicad/text.md` holds the facts.
- **Obstacles,** per side, kept `--clearance` away (default 0.15 mm): the copper of every pad on the side's outer layer, every drilled hole (pads, vias), the silkscreen strokes of the board and of the footprints, every other silkscreen text, the courtyards of the other parts, and the board edge with its cut-outs and slots. A text also lies inside the board.
- **Candidates and choice.** For each height (`--sizes`, largest first; default the field's height, then the least text height when smaller) and board angle (`--angles`, default `0,90`), twelve places beside the box of the part's courtyard, `--gap` away (default 0.1 mm). The stroke keeps the field's ratio to the height, at least the least stroke and at most a quarter of the size. The cost grows with the distance to the own part and the offset from its middle, with nearness to another part (a text nearer to another part than to its own costs most), with an angle across the part's long side and with a smaller size. Identical parts in a row or a column share one place relative to their parts when all of them are free there; the others are placed most constrained first, and a part without a free place may push one placed text to that text's next free place. A size below the project's `min_text_height` exits 2 (`FEN-2001`).
- **`--keep`** keeps every designator that meets nothing and places only the others.
- **Check.** Every written designator is computed again from its field and must keep the clearance from every obstacle and every other designator, lie inside the board, be at least the project's `min_text_height` and `min_text_thickness` (else 0.8 mm and 0.08 mm), read at 0° or 90° and be mirrored exactly on the bottom; a miss is `silk.check-failed` and nothing is written.
- **`--clip`** cuts every silkscreen line, arc, circle and rectangle or polygon outline of the board and of the footprints (those matching `--refs`) where its ink comes within `--margin` of an opening of its side: the copper of a pad whose layers hold that side's mask, grown by its positive mask expansion (the pad's margin, else the board's `pad_to_mask_clearance`), or a pad's hole. `--margin` defaults to the largest `min` of the `silk_clearance` rules of the `.kicad_dru` beside the board, else 0 (KiCad's DRC applies that rule, not `min_silk_clearance`, between silkscreen and pads: `docs/formats/kicad/drc.md`, "Silkscreen over pads"); the cut keeps 1 µm more. Pieces are written as `fp_line`/`fp_arc` (`gr_line`/`gr_arc` on the board) with the original's stroke and layer and the uuid `uuid5(FENOLITE_NS, "silk-clip:<old uuid>:<n>")`; a piece shorter than its stroke is dropped; an uncut item is written as read. Texts are not cut; a filled shape that meets an opening is `silk.clip-skipped`. A footprint's own items are cut by its own pads once per group of identical instances (name, side, silkscreen and pads), and the same pieces go into each, so `fenolite library` derives one footprint; each changed footprint name is one `silk.footprint-changed`, and a further cut at another part's pads is `silk.cut-by-other`. Every piece is checked again against every opening of its side with the margin (`silk.check-failed`).
- **`--drc`** runs `kicad-cli` DRC on copies of the board as it is and as silk would write it, with the project files; a violation type with more entries after gives `silk.drc-new` and no write; otherwise the evidence is `KICAD-VERIFIED` with the tool version.

`result` holds `board`, `target`, `changed`, `measure` (`null` without `--designators`, else `source`: `kicad-cli <version>` or `estimate`; `texts`; `cached`, the boxes read from the cache), `settings` (`clearance`, `gap`, `sizes`, `angles` in degrees, `keep`, `min_height`, `min_stroke`), `placements` (paged by `--limit` and `--cursor`; one row per part in natural order of `ref`: `ref`, `side`, `status` `placed`, `kept` or `unplaced`; a placed row adds the anchor `x`, `y`, `angle`, `height`, `stroke` and `where` (`above`, `below`, `left`, `right`), an unplaced one its `blocker`), the counts `placed`, `kept` and `unplaced`, `aligned` (the references of each row or column placed on one line), `clip` (`null` without `--clip`, else `margin`, `margin_source` `option`, `rule` or `default`, `openings`, the counts `items`, `pieces` and `dropped`, and `cuts`: one row per owner whose strokes were cut, `owner` (a reference or `board`), `footprint`, `side`, `items`, `pieces`, `dropped`, `by` (`own`, `other` or `board`)), `library` (`null`, or `changed`, the footprint names whose own silkscreen was cut, and `command`, the `fenolite library` line that writes their library) and `drc` (`null`, or `tool_version`, `before`, `after` and `new`). The board is planned when a designator was placed or a stroke was cut and no issue is an error. Evidence is `INFERRED` (`H-K-SILK-CLIP` with `H-K-SILK-MASK` for the clip; `H-K-SILK-DRC` with `H-K-SILK-INK`, or `H-K-SILK-ESTIMATE` for estimated ink, for the designators), and `KICAD-VERIFIED` after `--drc` found nothing new. The exit code is 5 for `silk.check-failed` and `silk.drc-new`, 0 otherwise.

| code | severity | when |
|---|---|---|
| `silk.check-failed` | error | a placed designator or a cut piece fails the check of the written board; nothing is written |
| `silk.drc-new` | error | with `--drc`, a DRC violation type has more entries on the board silk would write; nothing is written |
| `silk.no-place` | warning | no candidate of a part is free; its text stays where it was and is an obstacle for the others |
| `silk.no-outline` | warning | the board has no closed edge; no text is kept inside it |
| `silk.cut-by-other` | warning | with `--clip`, a footprint's silkscreen was also cut at another part's pads; that instance now differs from the others |
| `silk.clip-skipped` | warning | with `--clip`, a filled silkscreen shape meets an opening; it is not cut |
| `silk.estimated` | info | the ink was estimated from the glyph table, not measured |
| `silk.item-skipped` | info | a footprint holds drawn items Fenolite does not model; designators are not kept clear of them and they are not cut |
| `silk.footprint-changed` | info | with `--clip`, a footprint's own silkscreen was cut alike on every instance; its library copy no longer matches |

## impedance

`fenolite impedance PATH [--estimate] [--out FILE]` gives the impedance table of the project `PATH` names
(resolved as for `bom`: a `.kicad_pcb`, a `.kicad_pro` or a project folder; an Altium document gets the
error that `bom` gives for it) for the fabricator: one row per impedance target and layer, sorted by
target, then in stack order (`docs/impedance.md`; change c0105). It runs no tool.

- The design is the `.fenolite/` model of a built project (`result.source` `model`), else the board read
  with its project applied (`project`): the KiCad 10 tuning profiles that a class names become targets.
  No Altium record is read into a target.
- `result` holds `source`, `columns` (`exports.impedance.COLUMNS`), `rows` (one object per row: `target`,
  `kind`, `structure`, `layer`, `references`, `ohms`, `tolerance_percent`, `width`, `gap`, `heights`,
  `epsilon_r`, `classes`, `nets`; lengths in nanometres) and `counts` (`targets`, `rows`, `estimated`,
  `left_out`). A design without targets gives one `impedance.none` info and exits 0.
- `--estimate` adds `estimate` to each row: `{"mohm", "suggested_width", "in_range", "form", "reason"}`
  from `analysis.impedance` for single-ended surface microstrip and stripline rows. `mohm` and
  `suggested_width` are `null` where no form applies, and `reason` says why (`differential`, `structure`,
  `stackup`); `suggested_width` is also `null` when the target has no ohms. The estimates are `INFERRED`
  and omit solder mask, etch, frequency, loss and roughness: they are advice, never written into a
  design. The envelope evidence combines the source's level with `INFERRED`, and is `UNVERIFIED` when a
  row was left out for a missing stack-up or permittivity.
- It is a mutating command that writes only with `--out FILE`: the plan then holds one write of kind
  `impedance`, the CSV bytes of the table (`exports.impedance.render_csv`, with `estimate_ohms` and
  `suggested_width_mm` under `--estimate`), and the mutation protocol applies (4 without `--dry-run` or
  `--confirm`). It takes no `--manifest`, and the table is no manifest entry. The project folder never
  changes. Two runs on an unchanged project give the same output apart from `elapsed_ms`.

| code | severity | when |
|---|---|---|
| `impedance.none` | info | the design holds no impedance target |
| `impedance.no-stackup` | warning | an estimate needs a stack-up that the board lacks, or a row's layers or permittivity are not in it; the rows left out are counted |
| `impedance.estimate-unsupported` | info | rows whose structure has no form: differential, one reference on an inner layer, two references on an outer layer |
| `impedance.mixed-dielectric` | info | a row's height crosses dielectrics of different permittivity, combined in series |
| `impedance.out-of-range` | warning | a row lies outside the stated range of its form |
| `impedance.off-target` | warning | a row's estimate lies outside the target's tolerance; never given without a tolerance |

Exit codes: 0, 4 as above, 2 for a usage error, 3 for a missing path or a `.fenolite/` model or project
file that cannot be read (`FEN-3004`).

## diff

`fenolite diff A B [--view model|tree|records] [--ext] [--allow KINDS] [--three-way THEIRS --out FILE]`
lists the differences between two inputs. It runs no tool, and writes only the merged board of
`--three-way`, under the mutation protocol. A difference is a result, not a finding: the exit code is 0
whether or not the inputs differ, and `result.equal` says it, unless `--allow` gates it.

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
results"). `issues` holds the readers' issues, those of `A` first, then the findings of `--allow` and `--three-way`; `input` describes `A`. The
evidence is the lowest of the two readings; a built model counts as `INFERRED`.

The records view also holds `resave` (change c0207): `{total, streams}`, the count of changed records,
per stream, that differ only in the spelling of their values and are left out of `differences`. Two
values of a property record are one value when both are mil text with one value in units of 1/10 000
mil (rounded half to even), both are decimal numbers of one exact value (an angle in scientific form
included), or both are booleans of one value (`T` and `TRUE`). A key that holds free text (one that ends
with `NAME`, `TEXT`, `DESIGNATOR`, `DESCRIPTION`, `COMMENT`, `PATTERN`, `PATH`, `UNIQUEID`, `GUID`,
`IDENTIFIER`, `REFERENCE` or `LIBRARY`) is compared as written. A changed record keeps only its keys
that differ in value. When a record is classified so, the evidence is at most `INFERRED`
(`H-A-RD-RESAVE`). The model view compares decoded values, so a resave gives it no change
(`docs/formats/altium/pcb-read.md`, "Resave differences").

**Gated differences** (change c0207). `--allow KINDS` takes kinds of the model view, comma-separated
(`track,via`; an empty value allows none). Each change whose kind (the first segment of its path) is
not listed is one `diff.not-allowed` error naming its path in `where`, so the exit code is 5.
`result.allow` lists the allowed kinds. An unknown kind, and `--allow` outside the model view, is
`FEN-2001`.

```
fenolite diff before.kicad_pcb after.kicad_pcb --allow track,via,arc --json
```

**Three-way difference of KiCad boards** (change c0207). `fenolite diff BASE OURS --three-way THEIRS --out
FILE` plans `FILE`: `THEIRS` with the changes from `BASE` to `OURS` applied. The four paths are
`.kicad_pcb` files and the view is the model view; `FILE` may be `THEIRS` itself. The root items of
the three boards are matched by key: `<head> <uuid>` for an item with a `uuid`, the head for a head
without a uuid that each board holds at most once (`setup`, `general`, …), else the compact text. For each
item that differs between `BASE` and `OURS`:

- `THEIRS` holds the item as in `BASE`: the change is `applied`;
- `THEIRS` holds it as in `OURS`: it is `already` there;
- otherwise it is a `diff.conflict` error, `where` the key. A footprint is one item, so a pad changed on
  one side and the footprint moved on the other is a conflict.

The merged file is the bytes of `THEIRS` with the text of each changed item of `OURS` spliced in; an
added item follows the nearest item before it in `OURS`. Boards of two format versions, or with
numbered net tables (KiCad 9 and older) that differ, are `diff.unmergeable`. An error plans nothing, so
nothing is written (exit 5). `result.merge` holds `theirs`, `out`, `items` (`{key, change, status}`),
`applied`, `already`, `conflicts` and `refused` (the reason of `diff.unmergeable`, or `null`). Without
`--confirm` the plan exits 4 (`FEN-4001`). The evidence is `INFERRED` (`H-K-MERGE-ITEMS`): run `check`
on the merged board.

```
fenolite diff base.kicad_pcb ours.kicad_pcb --three-way theirs.kicad_pcb --out merged.kicad_pcb --dry-run
```

| code | severity | when |
|---|---|---|
| `diff.not-allowed` | error | a change of a kind that `--allow` does not list; `where` is its path |
| `diff.conflict` | error | an item changed from `BASE` to `OURS` was also changed in `THEIRS`; `where` is its key |
| `diff.unmergeable` | error | the three boards are of two versions, their numbered net tables differ, or the merge would leave nothing |

| exit | error | when |
|---|---|---|
| 0 | none | the inputs were compared, equal or not, and every change is allowed; or the merge was planned with `--dry-run` or written with `--confirm` |
| 2 | `FEN-2001` | an input that nothing reads, inputs of two families or two kinds, a folder in the tree view, an unknown `--allow` kind, `--allow` or `--three-way` outside the model view, `--three-way` without `--out` or on a file that is not a board, `--out` without `--three-way` |
| 3 | `FEN-3001` | an input does not exist |
| 3 | `FEN-3002`, `FEN-3003`, `FEN-3004` | an input cannot be read |
| 4 | `FEN-4001` | a merge was planned without `--dry-run` or `--confirm` |
| 5 | `FEN-5001` | `diff.not-allowed`, `diff.conflict` or `diff.unmergeable` |

## roundtrip

`fenolite roundtrip PATH [--level rt0|rt1|rt2|rta0|rta1|rta2|rta3] [--kicad-cli PATH] [--timeout SECONDS]` says up to which
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

**Altium input** (change c0090). `fenolite roundtrip PATH --level rta0|rta1|rta2|rta3` takes an Altium
document, project file or project folder and runs the stage `roundtrip.<level>` of the document check
(section "check"); the levels are not a ladder, each is asked for by name, and without `--level` the
input is judged at `rta1`. `result` holds `kind` (`altium`), `level` (the level when it holds, else
`none`), and `<level>`: the stage's `status`, `reason` and summary. For `rta3`, `result.unwritten`
repeats the counts of what the rewritten documents do not hold. The issues are those of the stage
(`check.rta0-failed` to `check.rta3-failed`, `check.rta3-unwritten`, `check.roundtrip-unjudged`), the exit
code is 5 with an error, and nothing is written under the input: RT-A3 writes into a temporary folder
that it removes. A KiCad level on Altium input, and an Altium level on another input, is a usage error
(`FEN-2001`).

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

## snapshot

`fenolite snapshot PATH --out DIR` copies a project after complete-set hash checks (changes c0201 and
c0223; `docs/file-safety.md`). `PATH` is a design file, taken with its companions (the documents of its stem, the
library tables beside it, and every file in its folder that one of those names: sheets, libraries,
library folders, 3D models), or a folder, taken with every project file in it. After the initial reads and
each retry round, a pass over every requested path compares its observed SHA-256 with the bytes held
for the copy. Mismatches are reread within at most three shared retry rounds; previously settled files
are checked again too. The copy is accepted only when a whole pass observes matching hashes.
`DIR/snapshot.json` (schema `fenolite.snapshot.v0`) lists `source` and
`files` (`path`, `sha256`, `size`): it is the receipt of `publish`. It is a mutating command.

The file list is fixed before reading. This does not lock writers or provide an atomic filesystem
snapshot: additions outside the list, saves after a file's final check, and changes restored between
checks can go unseen. Pause writers when the copy must correspond to one application-level save.

- `result` holds `source`, `out`, `files`, `count` and `retries` (the files read again).
- Any hash mismatch at the end of the shared retry budget is `safety.unstable` (error, exit 5): nothing is
  copied, even if that file changed for the first time on the final round.
- `--out` inside the project folder is a usage error (`FEN-2001`, exit 2): a later snapshot would copy the copy.
- A file that a sync client keeps only online stops the command before any read (`FEN-3007`, exit 3).

## publish

`fenolite publish SRC --to DST --receipt RECEIPT [--in DIR] [--skip-changed]` puts an edited copy back over
a project (change c0201). It is a mutating command.

- `RECEIPT` is the `snapshot.json` of the copy (paths relative to the project folder), or the envelope or
  receipt of an earlier confirmed write of Fenolite into `DST` (paths relative to `--in`, default the
  working directory).
- Each file of `SRC` (but `snapshot.json`, backups, lock files and hidden folders) goes to the same path in
  `DST`: added when new, not written when equal, and replaced only when the file of `DST` has the SHA-256
  the receipt recorded for it.
- A file of `DST` changed since the receipt, or that the receipt does not name, is
  `safety.changed-since-receipt` (error, exit 5), and nothing is written. With `--skip-changed` it is
  `safety.skipped` (warning): that file stays, and the others are written.
- `publish` deletes nothing. `result` holds `source`, `to`, `added`, `replaced`, `changed` and `unchanged`
  (a count); the receipt of the write is the next `RECEIPT`.

## refs

`fenolite refs PATH [--repoint OLD=NEW]` lists the paths that the documents of a project hold (change c0201):
the `uri` of each library table row, the `Sheetfile` of each sheet, the first atom of each 3D `model` of
boards and footprints, the two `page_layout_descr_file` keys of a KiCad project, and each `DocumentPath`
of an Altium project. `PATH` is taken as `snapshot` takes it.

- `result.refs` holds per path `document`, `kind` (`library`, `sheet`, `model`, `worksheet`, `document`),
  `value` (as written), `resolved` (`${KIPRJMOD}` is the project folder; `null` through another variable),
  `exists`, `outside` (outside the project folder) and `writable`; `result.count` and `result.rewritten`.
- A path outside the project is `refs.outside` (warning), a path to nothing `refs.missing` (warning), a path
  through another variable `refs.unresolved` (info).
- `--repoint OLD=NEW` rewrites, under the mutation protocol, every path that starts with `OLD` in the KiCad
  documents, replacing only those atoms. An Altium project that holds such a path is `refs.not-writable`
  (warning) and stays as it is. Without `--repoint` the command plans no write.

| code | severity | when |
|---|---|---|
| `safety.unstable` | error | a hash differs from the collected bytes after the shared three-retry-round budget; nothing is copied |
| `safety.changed-since-receipt` | error | a file of the destination changed since the receipt, or the receipt does not name it; nothing is written |
| `safety.skipped` | warning | with `--skip-changed`, such a file is left and the others are written |
| `safety.open-session` | warning | a planned file, or a file under `doctor --sessions`, has a CAD lock file beside it |
| `safety.placeholder` | warning | `doctor --sessions` found a file kept only online |
| `refs.outside` | warning | a document names a path outside the project folder |
| `refs.missing` | warning | a document names a path that resolves to nothing |
| `refs.not-writable` | warning | a document of a format Fenolite does not rewrite holds a path to repoint |
| `refs.unresolved` | info | a path goes through a variable other than `${KIPRJMOD}` |

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
| `models` | `result.models` | none |
| `net` | `result.nets`, or `result.net.pads` with a net name | none |
| `region` | `result.items` | none |
| `neighbors` | `result.neighbors` | none |
| `tidy` | `result.edits` | none |
| `library` | `result.drift` with `--diff`, else `result.footprints` | none |

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
project file or a project folder. It runs no tool. It says what a net holds and which of its connections
are open.

- Without `NAME`, `result.nets` holds one row per net, sorted by name: `name`, `class`, `pads`, `tracks`
  (tracks and arcs), `vias`, `zones`, `length`, the summed centre-line length of its tracks and arcs,
  `islands`, the number of its copper islands, and `open`, the number of its open connections.
- With `NAME`, `result.net` holds `name`, `class`, `pads` (each `where` as `REF-PIN`, `layers`,
  `position`), `copper` (per layer: `tracks`, `arcs`, `length`), `vias` (`position`, `layers`,
  `diameter`, `drill`), `zones` (`name`, `layers`, `filled`), `box`, the bounding box of its pads and
  copper (`{x0, y0, x1, y1}`, or `null`), `islands`, `fill_islands` (islands of zone fill alone, which
  join nothing) and `open`, the list of its open connections: each with `a` and `b` (`kind`, `where`,
  `position`, `layers`) and `length`.
- **Open connections are computed from the board**, not by KiCad (`docs/analyses.md`, "Open
  connections"): copper that touches on a layer is joined, and `open` is the shortest set of connections
  between the islands that hold a pad, a track, an arc or a via. A net of one pad has `islands` 1 and
  `open` 0. The limits of the query apply: a copper drawing that holds a net is not copper of that net in
  the model, so such a net can read open where KiCad reads it closed; the two ends of a connection are
  Fenolite's choice and may differ from the items KiCad names; fills are judged as stored. `fenolite
  check` stays the gate, with KiCad's DRC.

Every length is integer nanometres, in the frame of the board file. An unknown net exits 2 with
`FEN-2001`, and the hint names the closest net names. The evidence is the lowest of the board reader,
of the board frame and of the open-connections query (`H-K-CONN-PARITY`); an item that the query could
not shape gives `analysis.item-unsupported`.

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

`fenolite equivalent A [B] [--level N|S] [--strict] [--tolerance-nm N] [--tolerance-udeg N] [--tolerance-ppm N]
[--pixel-ppm N] [--render-pitch-um N] [--frame absolute|relative] [--ignore-ref GLOB]… [--exclusions FILE --profile NAME] [--against kicad-import]
[--kicad-cli PATH] [--timeout SECONDS]` says whether two designs are equivalent, level by level, and locates
every difference at `REF` or `REF-PIN`, and at the net for routing. It is read-only. With two paths it runs no tool, unless a
KiCad schematic outside the grammar of Fenolite's own netlist needs `kicad-cli`. `docs/equivalence.md`
defines the levels, the kinds of difference, the tolerance rules, the exclusion file and the schematic
side. The command parses its options and calls `fenolite.api.equivalent`, the same comparison as a library
call; its `result` is `EquivalenceResult.to_json()` and follows the schema
`schemas/fenolite.equivalent.v0.json`. The entry `equivalent` of `capabilities` lists `levels`
(`[1, 2, 3, 4, 5, 6, 7, 8, "S"]`) and `sides`, the side kinds it reads.

Each of `A` and `B` is one of:

- a `.fenolite/` folder (it holds `meta.json` or `build.json`): the built design, backend `fenolite`;
- a `.kicad_pro` file or a project folder, resolved to its board as `check` resolves it;
- a root KiCad schematic, a file ending in `.kicad_sch`, read with its sheet tree into a circuit and
  compared at levels 1 and 2 only: through Fenolite's own netlist for a schematic that `build` wrote, else
  through `kicad-cli sch export netlist` (`--kicad-cli`);
- any other file that a backend reads into a design: a KiCad board, an Altium PCB document, schematic
  document or project file.

| option | meaning |
|---|---|
| `--level N` | run the levels 1 to `N` (1 components, 2 netlist, 3 footprints, 4 placement, 5 routing, 6 rules, 7 geometry, 8 presentation). The default is the highest of 1 to 5 both sides hold: 5 when both have footprints and copper (a track, an arc or a via), 4 when both have footprints, else 2. Pass `--level 4` to compare two routed boards without their routing. Levels 6 and 7 need a footprint on both sides (they run level 5 when both sides hold copper); level 8 runs the levels 1 to 7 and then renders both boards; `--level S` (drawn schematics) needs the extraction of change c0276 and exits 2 naming side `a` in this version |
| `--strict` | level 5 also matches every track, arc and via item by item (change c0278); exit 2 below level 5 |
| `--pixel-ppm N`, `--render-pitch-um N` | level 8: the differing pixels a layer may hold in parts per million of its inked pixels (default 1000), and the pixel pitch of a board layer (default 50 µm) |
| `--tolerance-nm N`, `--tolerance-udeg N` | how far two lengths (per coordinate) and two angles may differ; non-negative integers, default 0 |
| `--tolerance-ppm N` | level 5 only: two routed lengths are equal within the larger of `--tolerance-nm` and `N` parts per million of the longer one; a non-negative integer, default 0 |
| `--frame absolute\|relative` | `relative` removes one translation, the per-axis lower median of the footprint positions of `B` minus `A`; default `absolute` |
| `--ignore-ref GLOB` | leave out the components whose reference matches (repeatable) |
| `--exclusions FILE --profile NAME` | apply the rules of one profile of an exclusion file. The profile also gives the frame and the tolerances; an option on the command line overrides its value |
| `--against kicad-import` | instead of `B`: convert `A`, an Altium PCB document, with `kicad-cli pcb import` (10.0 only) and compare Fenolite's read of `A` with the read of the converted board, under the `kicad-import` profile of the running version line |
| `--kicad-cli PATH`, `--timeout SECONDS` | the tool of `--against`, or of a schematic side outside the own netlist's grammar, and its time limit (default 300 s) |

`result` holds:

| key | value |
|---|---|
| `level` | the highest level that ran (0 when the triangle's converter gave no board; `result.tool_version` then names the `kicad-cli`) |
| `equivalent` | `true` when no difference remains outside the rules |
| `sides` | `a` and `b`, each with `path` (the name without its folder), `sha256` (of a file; `null` for a folder), `backend` (`kicad`, `altium`, `fenolite` or `kicad-import`), `netlist_source` (`board`, `circuit` or `schematic`), `components` and `footprints` (counts); side `b` of `--against` also has `tool_version`, and a schematic side `power_symbols`, the count of its `#` references, which are no components |
| `tolerances` | `length_nm`, `angle_udeg` and `length_ppm` |
| `frame`, `translation` | the frame, and `[x, y]`, the translation removed from side `b` |
| `levels` | one object per level run: `level`, `name`, `compared`, `differences`, `excluded` and `notices` (counts) and `summary`. The summary of level 5 holds `nets` (compared), `pieces`, `vias` and `length` (totals of side `a` and `b` over those nets), `unjudged`, `nets_unpaired`, `zones_unfilled`, `copper_no_net` and `unshaped` |
| `differences`, `excluded` | objects `{level, kind, where, field, a, b}`, in level order and then by `where`; an excluded one also has `rule` |
| `notices` | objects of the same form for what level 5 reports without failing: `route-stub`, `route-unjudged` and, with `--strict`, `copper-locked` |
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
| `equiv.track-missing`, `equiv.arc-missing`, `equiv.via-missing` | error | `--strict`: a track, an arc or a via that only one side holds (matched by copper span and geometry) |
| `equiv.track-width`, `equiv.track-net`, `equiv.arc-width`, `equiv.arc-net`, `equiv.via-size`, `equiv.via-drill`, `equiv.via-span`, `equiv.via-net` | error | `--strict`: a field of two matched copper items differs |
| `equiv.copper-locked` | warning | `--strict`: two matched items differ only in their lock; it does not fail the comparison |
| `equiv.netclass-missing`, `equiv.netclass-field`, `equiv.netclass-members`, `equiv.rule-missing`, `equiv.rule-field`, `equiv.ruleset-field`, `equiv.stackup-missing`, `equiv.stackup-field`, `equiv.layer-missing` | error | level 6: a net class, a custom rule, the rule set, the stack-up or the layer table differs |
| `equiv.outline-missing`, `equiv.zone-missing`, `equiv.zone-field`, `equiv.keepout-missing`, `equiv.keepout-field`, `equiv.graphic-missing`, `equiv.text-missing`, `equiv.text-field`, `equiv.field-pose`, `equiv.hole-missing`, `equiv.dimension-missing` | error | level 7: the exact geometry differs (zone fills are never compared) |
| `equiv.render-missing`, `equiv.render-pixels` | error | level 8: a layer drawn on one side only, or rendered masks that differ beyond `--pixel-ppm` |
| `equiv.sheet-missing`, `equiv.symbol-missing`, `equiv.symbol-pose`, `equiv.symbol-field`, `equiv.item-missing`, `equiv.item-field`, `equiv.drawn-net` | error | level S: the drawn schematics differ (needs change c0276) |
| `equiv.excluded` | info | a rule of the profile matched differences (count and reason) |
| `equiv.import-message` | info | a warning or error of `kicad-cli`'s import report, counted by text |
| `equiv.no-exclusion-profile` | warning | no profile for the running `kicad-cli` version line: no rule, the relative frame, tolerance 0 |
| `equiv.oracle-failed` | error | `kicad-cli` wrote no board, or one that the KiCad reader refuses; no level ran |

| exit | error | when |
|---|---|---|
| 0 | none | equivalent up to the level, outside the rules |
| 5 | none | a difference remains, or `equiv.oracle-failed` |
| 2 | `FEN-2001` | neither `B` nor `--against`, or both; a level above what both sides hold (the message names the side without footprints, or without copper for level 5) or outside 1 to 8 and S; `--level S` in this version; `--strict` below level 5; level 8 on a side without a board; a bad value; `--exclusions` without `--profile` or the reverse; a profile the file lacks; an input no backend reads, or a library; `--against` on anything but an Altium PCB document |
| 3 | `FEN-3001` | an input does not exist |
| 3 | the reader's code | an input or the exclusion file cannot be read |
| 6 | `FEN-6001`, `FEN-6002` | `--against` without `kicad-cli`, or with a major other than 10; `FEN-6001` also for a schematic side outside the own netlist's grammar without `kicad-cli` |
| 3 | `FEN-3004` | `kicad-cli` exported no netlist of a schematic side |

## verify-source

`fenolite verify-source SCRIPT --against ORIGINAL [--levels SPEC] [--tolerance-nm N] [--tolerance-udeg N]
[--tolerance-ppm N] [--frame absolute|relative] [--pixel-ppm N] [--render-pitch-um N] [--provenance FILE]
[--record] [--accept KEY --reason TEXT]… [--target 9|10] [--upgrade] [--kicad-cli PATH] [--timeout SECONDS]`
proves that a design script rebuilds an original project (change c0278; `docs/fidelity.md`). It builds
`SCRIPT` as `build` does, for the KiCad major of the original or `--target`, into a temporary folder that it
removes on every exit, reads the build and the original as `equivalent` reads its sides, and compares them
at levels 1 to 7 (level 5 strict), S and 8. It writes nothing unless `--record` is given, and runs no tool
unless `--upgrade` is given. Its `result` follows `schemas/fenolite.verify-source.v0.json`.

| option | meaning |
|---|---|
| `--against ORIGINAL` | a KiCad project folder or `.kicad_pro`, or an Altium `.PrjPcb` |
| `--levels SPEC` | the levels to run, comma-separated ranges and `S` (`1-7,S,8`, the default) |
| `--tolerance-nm N`, `--tolerance-udeg N`, `--tolerance-ppm N`, `--frame` | as `equivalent`; default 0 and `absolute`, or the values of `fidelity.tolerances` of the provenance file; an option overrides the file |
| `--pixel-ppm N`, `--render-pitch-um N` | level 8: default 1000 ppm (or `fidelity.tolerances.pixel_ppm`) and 50 µm |
| `--provenance FILE` | the provenance file; default `PROVENANCE.json` beside `SCRIPT` |
| `--record` | plan one write of the provenance file whose `fidelity.proof` holds the Fenolite version, the date (`--timestamp`), the SHA-256 of the script and of the original's files, the tolerances and each level's status; every other member is kept |
| `--accept KEY --reason TEXT` | accept the difference `<level>:<kind>:<where>` of this run with a reason (one reason for all, or one per key): the entry is listed under `result.new_accepted` and written by `--record` |
| `--target 9\|10` | the KiCad major of the build (default: the original's) |
| `--upgrade` | upgrade a copy of an original older than KiCad 9.0 with `kicad-cli pcb upgrade` |

`result` holds `script` (`name`, `sha256`), `against` (`name`, `backend`, `files`: the SHA-256 of each file
read), `build` (`target`, `files`), `tolerances`, `provenance` (`path`, `accepted`, `record`), `levels` (one
object per level: `level`, `name`, `status` of `equal`, `accepted`, `differs` or `skipped`, the counts
`compared`, `differences`, `excluded` and `notices`, `reason` for a skipped level, and `summary`),
`equivalent`, `differences`, `accepted` (the differences an accepted entry matched, with its id as `rule`)
and `notices`. `issues` holds the equivalence issues of every level ("equivalent"), then the `fidelity.*`
issues, then the readers' and the build's warnings. The evidence combines the reads, the build and
`INFERRED` for level 8 (one renderer draws both sides).

| code | severity | meaning |
|---|---|---|
| `fidelity.build-failed` | error | the build of the script wrote no file; no level ran |
| `fidelity.accepted-unused` | warning | an accepted entry matched no difference in a level that ran |
| `fidelity.level-skipped` | info | a level a side cannot reach, with its reason (`no-footprints`, `no-copper`, `no-board`, `no-schematic`, `drawn-unavailable`, `altium-drawing-unread`, `build-failed`) |
| `fidelity.input-upgraded` | info | `--upgrade` upgraded a copy of the original |

| exit | error | when |
|---|---|---|
| 0 | none | every level run is `equal` or `accepted` |
| 5 | none | a difference is neither excluded nor accepted, or `fidelity.build-failed` |
| 2 | `FEN-2001` | a script that is not a `.py` file; an original no backend reads; a bad `--levels`, tolerance or pitch; `--accept` without `--reason` |
| 3 | `FEN-3001` | an input does not exist |
| 3 | `FEN-3003` | an original older than KiCad 9.0 without `--upgrade` (the hint names `--upgrade` and `kicad-cli pcb upgrade`) |
| 3 | `FEN-3004` | a malformed provenance file, or an accepted entry of a kind of another level (the message names its id) |
| 4 | `FEN-4001`, `FEN-4002` | `--record` without `--confirm`, or a stale plan |
| 6 | `FEN-6001` | `--upgrade` without `kicad-cli` |

## convert

`fenolite convert SRC --to kicad|altium --out DIR [--name NAME] [--altium-bodies extruded|off]
[--altium-pour computed|outline] [--report-ids] [--no-verify]`, with the global `--kicad-version` and `--allow-lossy`, converts a project to
another backend, or to another KiCad major, and says per kind and per reason what it kept, changed and lost
(change c0159; `docs/conversion.md` holds the kinds, the report, the verification and the directions). The
command calls `fenolite.api.convert`; its `result` follows the schema `schemas/fenolite.convert.v0.json`.
It is mutating: `--dry-run` gives `result.plan` with every file under `DIR`, and `--confirm` writes them all
or none, with a `.bak` copy of each file it overwrites unless `--no-backup` is given.

- `SRC` is a `.kicad_pro`, a `.kicad_pcb` or a KiCad project folder, resolved as `check` resolves it; the
  board is completed with the net classes and the custom rules of its project files. An Altium `.PrjPcb`,
  `.PcbDoc` or folder is read too, and is refused until a direction from Altium is registered (c0161).
- The directions are listed under `result.conversions` of `capabilities`: KiCad to Altium (experimental,
  `INFERRED`), and KiCad to KiCad for the major of `--kicad-version`; an entry's `downgrade` says whether a
  target older than the source's major is written. A KiCad project of 10 converted with `--kicad-version 9`
  is a downgrade (change c0162): every file is written for 9 through the capability resolver
  (`docs/formats/kicad/versions.md`, "Downgrade"), the report holds one row per resolver id (kind
  `downgrade:<id>`, group `downgrade`), and a `design` row needs `--allow-lossy`. `build`, `place`, `route`
  and `fill` keep refusing such a source (`FEN-7002`, whose hint names `convert`).
- `DIR` may be an existing folder, but never the source's folder or a folder that holds it.
- Every conversion is verified: the written project is read back with the target backend and compared with
  the source by `fenolite.api.equivalent` under the direction's profile; each difference must be explained
  by an item the report names as lost. `--no-verify` skips the step, and the evidence is then `UNVERIFIED`.

| option | meaning |
|---|---|
| `--to kicad\|altium` | the backend of the converted project |
| `--out DIR` | the folder of the converted project |
| `--name NAME` | the stem of the written files (default: the source's) |
| `--altium-bodies extruded\|off` | write the extruded component bodies into an Altium PCB document (default), or none |
| `--altium-pour computed\|outline` | pour the polygons of an Altium PCB document with Altium's rules (default, experimental; exit 6 without the `geo` extra when asked), or write them unpoured; a usage error with `--to kicad` (change c0215) |
| `--report-ids` | list the ids of the changed and lost items under each reason of the report |
| `--no-verify` | do not read the converted project back |

`result` holds:

| key | value |
|---|---|
| `source` | `path` (the file read: the board of a KiCad project, the project file or document of an Altium one), `backend`, `kind` (`kicad_pcb`, `kicad_pro`, `altium_prjpcb`, `altium_pcbdoc`) and `format_version` (a KiCad board's header version, else `null`) |
| `target` | `backend`, and `major`: the KiCad major of a KiCad target, else `null` |
| `files` | `{name, bytes}` per file of the converted project |
| `report` | `lossy`, `refused` (the `refuse` kinds with losses) and `rows`: per kind, `kind`, `group`, `loss` (`refuse` or `report`), `source`, `written`, `changed`, `lost` and `reasons`, each `{reason, outcome, count}` (`ids` too with `--report-ids`), sorted by count and then reason |
| `equivalence` | `null` with `--no-verify`, else the `result` of `equivalent` with `explained` (the differences that a lost item explains, each with `by`, its kind) and `unexplained` (a count) |
| `experimental` | `true` for a direction that writes Altium documents |

| code | severity | meaning |
|---|---|---|
| `convert.lossy` | warning | with `--allow-lossy`: items of a `refuse` kind are not converted (one per kind, counts per reason) |
| `convert.changed` | info | items of a kind are written in another form that compares equal (one per kind) |
| `convert.no-verify` | warning | the conversion was not read back |
| `convert.schematic-unverified` | warning | a KiCad downgrade: the written root schematic could not be compared with the source's (its netlist needs `kicad-cli`) |
| `convert.unexplained` | error | a difference of the read-back that no lost item explains; nothing is planned |

| exit | error | when |
|---|---|---|
| 0 | none | converted, every difference explained |
| 2 | `FEN-2001` | `SRC` is no KiCad or Altium project, or a pair of backends without a direction; `--out` is the source's folder or holds it; a bad `--name` |
| 3 | `FEN-3001`, the reader's code | `SRC` does not exist, or does not read |
| 4 | `FEN-4001` | neither `--dry-run` nor `--confirm` |
| 5 | `FEN-5001` | a `convert.unexplained` error; nothing is planned |
| 7 | `FEN-7001` | a loss of a `refuse` kind without `--allow-lossy` (the issues name each kind), or a document too large for the Altium writer |

## panel

`fenolite panel PANEL.py --out DIR --target {9,10,altium} [--altium-panel {auto,embedded,flat}]
[--altium-pour {computed,outline}]` writes a
panel: several copies of one built board in rows and columns, with rails, V-score or tabs with mouse bites,
fiducials and tooling holes (change c0173; `docs/panels.md`). `PANEL.py` is a panel script that binds
`panel = Panel(name, board=…)` (`fenolite.dsl.panel`), run in-process as `build` runs a design script.

- **Checks first.** `panel.checks` judge the layout against cited fabricator figures before anything is
  planned: `panel.vscore-copper`, `panel.vscore-shape`, `panel.vscore-spacing`, `panel.vscore-thickness`,
  `panel.tab-copper`, `panel.gap`, `panel.tab-count`, `panel.tab-spacing`, `panel.fiducial-place`,
  `panel.tooling-place`, `panel.size`, and the structural errors `panel.board-outline`, `panel.no-fit`,
  `panel.net-collision`, `panel.source-unreachable` and `panel.altium-cutout`. An error finding plans no
  write: exit 5 (`FEN-5001`) with `result.plan` empty. `fenolite explain <code>` gives each one's fix.
- **Forms.** `--target 9` or `10`: a KiCad panel board `<name>.kicad_pcb` with its `<name>.kicad_pro`, the
  generated footprints under `lib/` and `fp-lib-table`; the source must be a `.kicad_pcb` written for that
  major. `--target altium`: `<name>.PcbDoc` and `<name>.PrjPcb` holding the panel document alone. Both write
  `<name>.panel.json`, the model panel (schema `schemas/fenolite.model.v0/panel.json`).
- **The Altium form.** `--altium-panel auto` (default) writes Altium's Embedded Board Array when
  `pcbdoc.EMBEDDED_ARRAYS` is true and the source is a `.PcbDoc`, otherwise the flattened panel with one
  `altium.panel-flattened` info naming the reason. `embedded` while the gate is off, or with a `.kicad_pcb`
  source, is exit 7 (`FEN-7001`); so is `mirror=True` for any flattened form. `--altium-pour` is the pour
  mode of a flattened panel's document, as for `build` (change c0215), and `result.panel.pour` says what it
  did; exit 6 for an explicit `computed` without the `geo` extra.
- **Writes.** `--dry-run` plans every file under `DIR`; `--confirm` writes them all or none, with
  `.fenolite/<name>.panel-written.json`, the SHA-256 of each file written. A later run refuses a file
  changed since (`panel.output-changed`, exit 5) unless `--discard-layout` replaces it (a `.bak` is kept).
- **Result.** `result.panel` holds `target`, `form` (`kicad`, `flat` or `embedded`), `rows`, `cols`,
  `copies`, `rotation` (µdeg), `size` and `unused` (`w`, `h` in nm; `unused` is what an asked `fit()`
  size leaves), `separations` (edge set → method), `items` (counts of tabs, mouse-bite rows and holes,
  score lines, fiducials and tooling holes) and `score_layer` (the KiCad layer of the score lines);
  `result.files` lists the planned files with their sizes. `evidence.level` is that of the form:
  `KICAD-VERIFIED` (`H-K-PANEL-LOAD`, `-DRILL`, `-NETS`) for a KiCad panel board.
- **Exit codes.** 0; 2 (`FEN-2001`) for `--altium-panel` or `--altium-pour` with a KiCad target, a `.PcbDoc` board for a
  KiCad target, or a board written for another KiCad major than `--target`; 3 (`FEN-3001`) when the script
  or its board is missing, (`FEN-3004`) when the script raises or binds no `panel`; 4 (`FEN-4001`,
  `FEN-4002`); 5 (`FEN-5001`) for error findings; 7 (`FEN-7001`) as above.

## edit

`fenolite edit PATH (--content-file FILE | --edits-file FILE)` writes a text file of a design through the
write protocol (change c0196): a design script (`*.py`), a TOML file (`*.toml`, such as `placements.toml`) or
a library table (`fp-lib-table`, `sym-lib-table`). Any other file is `FEN-2001`; KiCad and Altium documents
are written by the commands that own them.

- `--content-file` holds the whole new text; the file is created when it does not exist.
- `--edits-file` holds a JSON list of `{"old": ..., "new": ...}` pairs, applied in order to the text as it
  stands; each `old` must be found exactly once (else `FEN-3004`, naming the pair and the count), and the file
  must exist (else `FEN-3001`).
- Files are UTF-8 text of at most 1 MB, before and after; the file keeps its line ends.
- The new text must parse: a script with Python's `ast.parse`, a TOML file with `tomllib`; else `FEN-3004`
  with the line, and no plan is staged. The script is never imported or run.
- `result` holds `path`, `kind` (`design-script`, `toml` or `library-table`), `created`, `changed`,
  `lines_added`, `lines_removed`, `diff` (unified, three lines of context, at most 400 lines) and
  `diff_truncated`. An unchanged text plans no write.
- The input files are inputs of the plan: a confirmation refuses (`FEN-4002`) when one changed since the dry
  run.

## mcp

`fenolite mcp [--root DIR] [--read-only] [--tools NAME,...] [--timeout SECONDS] [--list]` serves the public
commands as tools to a client of the Model Context Protocol on standard input and output (change c0195;
`docs/mcp.md`). The client starts it; it serves until its input ends.

- **Standard output** belongs to the protocol while it serves: one JSON-RPC message per line, and no envelope
  after the last one (the command leaves without one). Diagnostics go to standard error as lines
  `fenolite mcp: ...`.
- **Versions:** the modern revision `2026-07-28` (`server/discover`, the version in each request's `_meta`)
  and the `initialize` handshake of `2025-11-25`, `2025-06-18` and `2025-03-26`. `fenolite capabilities`
  lists them as `protocol_versions` of `mcp`.
- **Tools:** `fenolite_<command>` for every public command but `mcp` and `skill`; `view` without `--serve`,
  `--port` and `--no-browser`. A tool's arguments are the command's, by the names of
  `capabilities --command <name>`, plus `fields`, `limit`, `cursor`, `format`, `seed`, `timestamp`,
  `kicad_version` and `allow_lossy` (and `no_backup` for a writing command).
- **Calls** run `python -m fenolite <command> ... --json` in `--root`, one at a time. The result is the
  envelope (exit 0 or 5) or the error object (any other exit), with the exit code in `_meta` `fenolite/exit`;
  `isError` is true for an exit other than 0 and 5. A call longer than `--timeout` (default 600 s), or
  cancelled by the client, is stopped and gives `FEN-1003`.
- **Writes:** a writing tool without `confirm` is the `--dry-run`; with `confirm: true` it needs `plan`, the
  `plan_id` of that dry run, and the server refuses (`FEN-2001`) a plan of another command or one that writes
  outside `--root`. `--read-only` serves no writing tool.
- **Resources:** `fenolite://guide/<topic>` for each page of the agent guide, and `fenolite://capabilities`.
- **`--list`** serves nothing and returns the envelope `result.versions`, `result.root`, `result.tools` and
  `result.resources`.
- **Usage errors** before serving (`--root` not a folder, a name of `--tools` that is not served, a timeout not
  above 0) are `FEN-2001`, exit 2.

## view

`fenolite view PATH [--doc ID] [--overlay FILE]... [--theme THEME] [--cache user|project|off]
[--compare OLD] [--variant NAME] [--check FILE|run] [--report FILE]... [--select REF] [--marks FILE] [--serve [--port N] [--no-browser]] [--export FILE [--docs ID,...]] [--no-review] [--no-models]
[--silk-gap MM] [--mask-expansion MM]` shows the boards and the sheets of a project without the tool that made them (changes c0176,
c0177, c0178 and c0193; `docs/viewer.md`). `PATH` is an Altium `.PrjPcb`, a KiCad `.kicad_pro`, a project folder, a
board, an Altium `.SchDoc` or a KiCad `.kicad_sch`, a library: `.SchLib`, `.PcbLib`, `.kicad_sym`,
`.kicad_mod` or a `.pretty` folder (change c0179), or an Altium Draftsman drawing, `.PCBDwf` (change c0180).

- **Reply.** Without `--serve` and `--export` nothing is written. `result.project` is the project tree
  (`name`, `source`, `project_file`, `groups` of documents with `id`, `name`, `path`, `kind`, `present`,
  `viewable`, `size`), `result.document` the id of the document shown (`--doc`, else the board named as the
  project, else the first board, else the first sheet), `result.summary` its layers and the count of each
  item kind, and `result.notes` what the scene states (derived mask openings, zones without fill, an assumed
  thickness; for a sheet, which drawings are Fenolite's). For an Altium sheet `result.summary` is `kind`
  `"schematic"`, `counts` (components, pins, wires, buses, bus entries, labels, power ports, ports, junctions,
  No ERC marks, sheet symbols, sheet entries, harness connectors, nets, primitives) and `bounds_um`, and
  `evidence.level` is `INFERRED`; a KiCad sheet replies the same way, with `components` counting the symbols
  whose reference does not start with `#` and `symbols` counting all. `evidence.level` of a board is that of
  the backend's read. `result.theme` names the colours of the document shown: `kicad`, `altium`, or
  `kicad:<file>` for a theme given with `--theme`. For a board, `result.summary` also holds `findings`, the count
  per group of the review and of the overlay files, and `models`, `null` in this form (change c0193).
- **Libraries.** For a library, `result.summary` is `kind` `"library"`, `lib` (`"pcb"` or `"schematic"`),
  `counts.items` (one per footprint, or per symbol part or unit) and `items`, the first 50 names. A board
  scene, a footprint's included, lists every pad with its exact size in nanometres.
- **Project review** (c0230). `result.review` and each loaded document scene's `project_review` contain
  status `cards`, raw `stages`, report input `binding`, operation findings and a scope note. Card states
  are `not-run`, `passed`, `failed`, `limited`. Missing/skipped stages are never passes; warning/capped,
  partially covered or unbound results remain limited. Errors remain failed. The Review panel retains
  original finding hints and can locate existing markers without marking a problem fixed.
- **`--report FILE`** (c0230) accepts a complete recorded `convert` or `export` JSON envelope (`command`,
  boolean `ok`, object `result`, array `issues`), once per command; repeat the option to attach both.
  Loading never executes the recorded operation. Missing files return `FEN-3001`, malformed/unsupported
  envelopes `FEN-3004`, duplicate commands `FEN-2001`; no output is planned. Use `--check` for check replies.
  Check/report inputs are tracked by staged HTML plans. A matching input hash binds only the named
  document, not every project input. Missing/mismatched hashes and live changes keep a historical-report
  warning. Conversion receipt/equivalence, experimental and loss status remain explicit; current export
  replies lack affirmative readback attestation, so export status stays limited rather than implying
  fabrication readiness. See `docs/viewer.md`, Project review.
- **Drawings.** For a `.PCBDwf`, `result.summary` is `kind` `"drawing"`, `counts` (`sheets` and the count of
  each item kind: views, tables, texts, lines and so on), `sheets` (their names) and `panel` (the document's
  `IsPanel`). The sheets are drawn from the document's own copy of the board; `evidence.level` is
  `INFERRED`. A board or a drawing that holds an Embedded Board Array gets a note that Fenolite does not draw
  the array.
- **BOM documents and output jobs** (change c0190). A `.BomDoc` and an `.OutJob` of an Altium project are
  viewable: `result.summary` is `kind` `"table"`, `table` (`"bom"` or `"outjob"`), `counts` and `columns`. A
  BOM document is built from the parts of the project's sheets with the document's grouping, catalog,
  columns, aliases and sort (`counts`: `lines`, `parts`, `manual`); opened alone it lists its catalog. An output
  job lists its outputs (`counts`: `outputs`, `groups`) with the folder each container writes to, as the job
  spells it. `evidence.level` is `INFERRED`.
- **Cache** (change c0182). Scenes are cached by the SHA-256 of their input, the theme and a digest of
  Fenolite's code: in the user's cache folder by default (`FENOLITE_CACHE_DIR`, else the platform's cache
  folder), under `.fenolite/view-cache/` of the project with `--cache project`, or not at all with
  `--cache off`. The cache is not a planned write and holds no file bytes. `result.cache` gives `where`,
  `hits` and `misses`.
- **`--compare OLD`** (change c0184) draws, over the document shown, what changed since the board or sheet
  `OLD`, and replies with `result.compare`: `kind`, `old` (name, SHA-256), the counts `added`, `removed`,
  `moved`, `changed` and `zone` (a board) or `net` (a sheet), and `changes`, one line each. `OLD` must be of the
  same kind and tool (`FEN-2001`); a missing `OLD` is `FEN-3001`.
- **`--variant NAME`** (change c0186) opens an Altium project with its variant `NAME` chosen, and replies with
  `result.variant`: `name`, `fitted` and `not_fitted`, counted over the parts of the document shown. A name
  the project does not hold is `FEN-2001`, with the names it holds. The scenes of the project's sheets and
  board carry every variant, so the page can switch between them.
- **`--check FILE|run`** (change c0188) draws the findings of a `fenolite check --json` reply (`FILE`), or
  with `run` of `check` run first in the same process, read-only, on the project file (else on the document
  shown), with its default stages and options. Each finding with a position gets a marker in the colour of its
  severity, on its layer when it states one, and a Messages panel lists every finding grouped by code, errors
  first, with its stage and that stage's evidence. `result.check` gives `error`, `warning`, `info`, `total`
  and `placed` (the findings with a position on the document shown). A file that is not a `check` reply is
  `FEN-3004`; a missing one is `FEN-3001`. ERC findings are placed on sheets only, and the findings of the board
  stages on boards only.
- **`--select REF`** (change c0189) opens the page at the part or net `REF` (`net:NAME` for a net whose name
  is also a reference), and replies with `result.select`: `name` and `found` (whether the document shown holds
  it; when it does not, a note says so). An exported page carries it.
- **`--marks FILE`** (change c0189) names a review file, `fenolite.review.v0` (`schemas/`): marks with `id`,
  `doc` (the document's file name), `x_nm` and `y_nm` (Y down, the document's frame), `note`, `select` and
  `created`. The reply lists them in `result.marks`, each also with `x_mm` and `y_mm`. With `--serve` the page
  saves new and deleted marks to `FILE`, through the server alone, in one atomic replace; the file may be
  missing then, and `result.serve.marks_written` counts the saves. The server takes a mark only from its own
  page on the loopback address (`Host` and `Origin` checked, the header `X-Fenolite-Review: 1` required) and
  only to `FILE`. Without `--serve`, a missing `FILE` is `FEN-3001`; a malformed one is `FEN-3004`. An exported
  page carries the marks and keeps new ones in the browser, to download as a review file. Serving with
  `--marks` is the consent to these writes; without it the server writes nothing.
- **`--theme THEME`** draws the KiCad documents in a KiCad colour theme: a `.json` file, or the name of a theme
  in the `colors` folder of the user's KiCad settings (`docs/formats/kicad/color-theme.md`). A theme that is
  not found is `FEN-3001`, a malformed one `FEN-3004`.
- **`--export FILE`** plans one standalone HTML page holding the tree and the scene of every viewable document
  (only those `--docs` names, by id, path or name; an unknown one is `FEN-2001`), each scene compact and
  gzipped (`fenolite.view_scene.v1`), under the mutation protocol; `result.export` gives its documents, size
  and SHA-256, and a `warning` above 20 MB.
- **`--serve`** writes one progress record with the URL to stderr, serves the page on `127.0.0.1` (port
  8765, or any free port with `--port 0`) until it is interrupted, reloading a document when its file is
  saved, and then replies with `result.serve` (`url`, `seconds`). It opens a browser unless
  `--no-browser`.
- **Review** (change c0193). Unless `--no-review`, a board's review findings are drawn by group (45° corners,
  silkscreen near a mask opening, near other silkscreen or the edge, copper outside the board) with the open
  connections of `analysis.connectivity`, ground nets apart. `--silk-gap MM` is the silkscreen gap (default: the
  design's `silk_clearance` rule, else 0); `--mask-expansion MM` grows the pads' mask openings.
- **Body models** (change c0193). Unless `--no-models`, the 3D models a backend gives (`BodyModelSource`: an
  Altium board's embedded STEP models) are meshed by `gmsh`, run as a separate process, and placed: before the
  page is planned with `--export` (`result.summary.models` counts the bodies per render, `model`, `fitted`,
  `outline`, and the models gmsh could not mesh), after the first scene with `--serve` (the page reloads).
  Without gmsh the bodies are extruded and a note says so.
- **`--overlay FILE`** reads the JSON reply of `fenolite analyze`: every distance row's clearance and
  creepage paths are drawn, and a row that an error or warning names is marked as a finding. It also reads a
  findings file of the schema `fenolite.view_overlay.v0` (change c0193; `docs/viewer.md`).
- **Exit codes.** 0; 2 (`FEN-2001`) for `--serve` with `--export`, a bad `--port`, a port in use (hint: `--port 0`),
  a negative length, an unknown `--doc`, or a
  path that is neither a project file, a board, a sheet, a library nor a drawing; 3 (`FEN-3001`) for a missing
  path, (`FEN-3004`) for an overlay that is neither an `analyze` reply nor a findings file, or a sheet or drawing the reader refuses; 4 (`FEN-4001`,
  `FEN-4002`).

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
  offset, kind and string of what looks like a home folder, another absolute path of the machine or a
  login name: `home-folder`, `absolute-path`, `login-name`), `kit_problems`, `kit_resaved` (the project
  files of samples that the tool saved again with the same documents),
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
| `kit.file-changed` | error | a file of the kit is missing or differs from its digest in `kit.json`, and is not a sample's project file that still lists the sample's documents |
| `kit.form` | error | `results/form.json` is not sound as a whole (schema, tool version, system, date, fields) |
| `kit.step-failed` | error | a result file fails a check, or a typed value is not the expected one |
| `kit.record-refused` | error | `record` wrote nothing; the message says why |
| `kit.synthetic` | warning | the form does not say that a tool performed the run |
| `kit.privacy` | warning | a result file holds what looks like a home folder, another absolute path of the machine or a login name |
| `kit.stale` | warning | `status`: a row's kit run is stale |
| `kit.project-resaved` | info | a sample's project file was saved again by the tool: other bytes, the same documents; nothing fails |
| `kit.step-skipped` | info | a step was not done |
| `kit.pending` | info | a check of a step waits for a change that is not implemented, and was not run |

| exit | error | when |
|---|---|---|
| 0 | none | a dry run or a confirmed write; `verify` with no failed step; `status` |
| 2 | `FEN-2001` | an argument that the action does not take, or a missing `--out` or `DIR` |
| 3 | `FEN-3001` | `DIR` holds no `kit.json`; the sample scripts are missing or do not build |
| 4 | `FEN-4001` | `build` or `record` with neither `--dry-run` nor `--confirm` |
| 5 | `FEN-5001` | a step failed, a kit file changed, the form is not sound, or `record` refused |

## fetch

`fenolite fetch NAME [--from FILE] [--dir DIR]` installs one external tool after checking its size and its
SHA-256 against the values pinned for it. The one tool is `freerouting`: the jar of Freerouting 2.4.1
(GPL-3.0), from the release page of its publisher. **No other command downloads anything**, and this one
makes a request only with `--confirm` ([ADR-0007](adr/0007-fetching-external-tools.md)).

```
fenolite fetch freerouting --dry-run --json
fenolite fetch freerouting --confirm --json
```

- The file goes to the tools folder: `FENOLITE_TOOLS_DIR` (an absolute path), else
  `$XDG_CACHE_HOME/fenolite/tools`, else `~/Library/Caches/fenolite/tools` on macOS,
  `%LOCALAPPDATA%\fenolite\tools` on Windows and `~/.cache/fenolite/tools` elsewhere. `route --router
  freerouting` looks there after `--router-path` and `FENOLITE_FREEROUTING_JAR`. `--dir DIR` installs
  into `DIR` instead, where the router does not look: `result.env` then says which variable to set.
- **The plan** is one file, with the `bytes` and the `sha256` it must have. `--dry-run`, and a run with
  neither flag (exit 4), open no connection and do not read the file of `--from`. A destination that
  already holds the pinned bytes plans nothing and exits 0 with `installed: true`.
- **With `--confirm`** the bytes are obtained first (a [deferred write](#writing-files)): one request to
  the pinned `https` address, with the header `User-Agent: fenolite/<version>`, a timeout of 60 s, no
  parameter and no retry; a redirect is followed only to an `https` address. No design data is sent.
  `--from FILE` reads a copy you already have instead, and the same check applies.
- Nothing is written unless the size and the digest match. The receipt is that of any write.
- The command installs no Java: `result.needs` says what the tool needs before anything is downloaded.

`result` holds `name`, `version`, `file`, `path` (the destination), `bytes`, `sha256`, `url`, `licence`,
`origin` (`network`, `file` with `--from`, or `package`), `installed` (the destination already held the
pinned bytes), `needs`, and `env` (the variable to set, mapped to the destination, with `--dir`; empty
otherwise). The evidence is `UNVERIFIED`: installing a tool proves nothing about a board.

| exit | error | when |
|---|---|---|
| 0 | none | a dry run, a confirmed install, or nothing to do |
| 2 | `FEN-2001` | no `NAME` or an unknown one (the hint lists the names); a relative `FENOLITE_TOOLS_DIR` |
| 3 | `FEN-3001` | the file of `--from` is missing or unreadable |
| 3 | `FEN-3006` | the bytes do not have the pinned size or SHA-256 (the message holds both digests); nothing is written |
| 4 | `FEN-4001` | neither `--dry-run` nor `--confirm` |
| 6 | `FEN-6003` | the download failed (retryable); the hint names `--from FILE` |

## guide

`fenolite guide [TOPIC]` prints the agent guide that ships in the package (`src/fenolite/agent/`): the
pages an AI agent reads before it works on a board. The pages belong to the installed version, need no
file and no network, and the command runs no tool. Its evidence is `UNVERIFIED`: a page is text, and no
tool judged it.

- **Without a topic**, `result` holds `version` (of Fenolite) and `topics`: one `{topic, title, summary,
  lines}` per page, the page `start` first and the others sorted by topic. In text mode the command prints
  one line per page, `<topic>: <summary>`.
- **With a topic**, `result` holds `topic`, `title`, `summary`, `text` (the page without its front matter)
  and `version`. In text mode the command prints the page as it is, after the status line and one empty
  line (see "Output"): `fenolite guide start --text` is how an agent reads a page. The JSON form is for
  programs.

`start` is the body of the skill's `SKILL.md`; the other pages are the files of its `references/` folder.

| exit | error | when |
|---|---|---|
| 0 | none | the list, or one page |
| 2 | `FEN-2001` | an unknown topic; the hint names the closest topics, or all of them when none is close |

## skill

`fenolite skill show` lists the skill folder that ships in the package, and `fenolite skill install
[--agent NAME | --dir DIR] [--agents-md]` copies it to where an agent reads skills. The command runs no
tool and opens no connection. It is a mutating command: `install` writes only with `--confirm`, keeps a
`.bak` of a file it replaces and returns a receipt.

- **`show`** plans nothing. `result` holds `name` (`fenolite`), `description`, `version`, `files` (each
  `path`, `bytes` and `sha256`) and `agents` (each `agent` and `dir`: the agents whose project skill
  folder Fenolite knows from a public source; today `claude-code`, `.claude/skills`).
- **`install --dir DIR`** plans one file per file of the skill, at `DIR/fenolite/<path>`. `--dir` takes
  any folder, so it serves every agent. `--agent NAME` uses the folder of that row of `result.agents`
  instead, relative to the working directory; the two exclude each other.
- **The version line.** The installed `SKILL.md` is the packaged file followed by one line,
  `<!-- installed from fenolite <version> -->`, so a copy that grew stale can be told from the installed
  package. Every other file is copied byte for byte. `fenolite guide` always prints the pages of the
  installed version.
- **`--agents-md`** also plans `AGENTS.md` in the working directory, for agents that read that file and
  no skill folder. The section it keeps is fixed, lies between the lines `<!-- fenolite:begin -->` and
  `<!-- fenolite:end -->`, and tells an agent to run `fenolite guide start --text` before a board task.
  A missing file is created with the section alone; a file without the markers gets an empty line and
  the section appended; a file with both gets the text between them replaced, so a second run plans the
  same bytes. Text outside the markers is never changed.

`result` of `install` holds `action`, `target` (the skill folder, or `null` with `--agents-md` alone),
`files` (the paths planned) and `version`.

| exit | error | when |
|---|---|---|
| 0 | none | `show`; a dry run or a confirmed `install` |
| 2 | `FEN-2001` | `install` with none of `--agent`, `--dir` and `--agents-md`; both `--agent` and `--dir`; an unknown agent (the hint names the agents and `--dir`); an option given to `show` |
| 3 | `FEN-3004` | `AGENTS.md` holds one marker line without the other, or is not UTF-8 text |
| 4 | `FEN-4001` | `install` with neither `--dry-run` nor `--confirm` |

## init

`fenolite init DIR [--starter NAME] [--name NAME] [--force]` writes a starter project into `DIR`: a design
script that names only parts of the built-in catalog, so it builds on a machine with no KiCad library and
no library table. It runs no tool. It is a mutating command: one file per file of the starter is planned,
here `DIR/design.py`, and written with `--confirm`.

- `--starter` chooses the starter (`blink` by default); `fenolite capabilities --brief` lists them.
- The design name is `--name`, else the last part of `DIR`. It must match `^[A-Za-z0-9][A-Za-z0-9_.-]*$`.
- An existing `DIR/design.py` is kept: the command exits 2 unless `--force` is given, and with it the
  replaced script stays beside the new one as `design.py.bak`.

`result` holds `starter`, `name`, `design` (the path of the script) and `next`, the two commands to run
next: `fenolite build <design> --out DIR/build --dry-run --json`, then the same with `--confirm`.

The starter `blink` is a two-pin header, a resistor and a LED on a 30 mm by 20 mm two-layer board, with
every part placed so that `fenolite route --router direct` closes its three nets with straight tracks.

| exit | error | when |
|---|---|---|
| 0 | none | a dry run or a confirmed write |
| 2 | `FEN-2001` | an unknown starter (the hint names them); a name that is not a design name (the hint names `--name`); `DIR/design.py` exists and `--force` is not given |
| 4 | `FEN-4001` | neither `--dry-run` nor `--confirm` |
