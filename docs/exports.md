# Exports and renders

`fenolite export` produces the files a board house needs, and `fenolite render` produces pictures of the
board for review. Both run KiCad's own `kicad-cli` (9.0 or 10.0): Fenolite writes no Gerber itself.
The normative text is in `docs/cli-contract.md` ("export", "render") and
`openspec/specs/manufacturing-exports/spec.md`.

## What Fenolite adds

- **The project is never touched.** `kicad-cli` writes files next to the board it opens, so it only sees
  a copy of the project (the same copy set as `fenolite check`).
- **Nothing is written without `--confirm`.** `--dry-run` runs the tool on the copy and shows the plan:
  every file, its size and its SHA-256.
- **All or nothing.** If one kind fails, no file is written, so a folder never holds a partial set.
- **A manifest.** `--manifest` adds the files to `fenolite-artifacts.json`: which file came from which
  board, by which tool version, with its hashes. `fenolite manifest` then says what was verified about
  each file of the project.

## What Fenolite does not claim

The content of every exported file is KiCad's. Fenolite claims the set of files, their hashes, the
board or schematic they came from and, for a STEP, the model files it gave the run; it does not read or
check the fabrication data. Check the board first
(`fenolite check`), and look at the files in a Gerber viewer before you send them.

## Export

```
fenolite export build/blink --out fab --all --manifest --dry-run
fenolite export build/blink --out fab --all --manifest --confirm
```

`PATH` is a `.kicad_pcb`, a `.kicad_pro` or a project folder. `--out` is relative to the working
directory. Use a fresh `--out` folder for each export: writing over an older export leaves `.bak`
files next to every file (or pass `--no-backup`).

| flag | files under `--out` | `kicad-cli` options (fixed) |
|---|---|---|
| `--gerbers` | `gerbers/<stem>-<layer>.gbr` per layer, `gerbers/<stem>-job.gbrjob` | `--no-protel-ext --layers <list>` |
| `--drill` | `drill/<stem>-PTH.drl`, `drill/<stem>-NPTH.drl` | `--format excellon --excellon-units mm --excellon-separate-th --drill-origin absolute` |
| `--pos` | `pos/<stem>-pos.csv` | `--format csv --units mm --side both` |
| `--ipcd356` | `netlist/<stem>.d356` | none |
| `--all` | the four kinds above, and no document kind | |
| `--altium-rul` | `<stem>.RUL`: the project's rules as an Altium rule file | no tool runs |

The Gerber layers are every copper layer in stack order, then `F.Mask`, `B.Mask`, `F.Paste`, `B.Paste`,
`F.SilkS` and `B.SilkS` where the board has them, then `Edge.Cuts`. Courtyard and fabrication layers
are left out. KiCad names a Gerber after the layer name it shows, so the silkscreen files end in
`F_Silkscreen.gbr` and `B_Silkscreen.gbr`.

`--altium-rul` is not part of `--all`. It reads `<stem>.kicad_dru` beside the board and writes each
rule that has an exact Altium form as one record of a rule file, which Altium's PCB Rules editor imports
into a board (Design » Rules, right-click, Import Rules): a way to give a PcbDoc you keep the rules of
the script without building it again. `result.rules` names what was written and what was not, with the
reason (`docs/altium.md`, "Rules"); a project without a rule that can be written gives `export.failed`
and no file. The file is Fenolite's own, at the level `INFERRED`: that Altium imports it as written is
not yet confirmed (`H-A-RULE-FILE`).

v0.1 has one way to export each kind; these options are the whole list. Two options are never passed:

- `--check-zones` would refill zones in the copy before plotting, so the files would not show the board
  as it is. Fill the board with `fenolite fill`, check it, then export.
- `--board-plot-params` would make the files depend on plot settings stored in the board.

**The job file states the stack-up.** `kicad-cli` writes `<stem>-job.gbrjob` beside the Gerbers, and that
file states a thickness for every layer only when the board's `setup` holds a complete stack-up. A board
without one gets KiCad's default: 0.035 mm copper, 0.01 mm masks, equal FR4 dielectrics that fill the
board thickness, and the finish `None`. `export --gerbers` then gives one `export.stackup-default` info
(`where` `gerbers`), so the default is not taken for the design's; declare the stack-up with
`design.stackup()` or in KiCad's Board Setup. The note changes no file and does not stop the writes: only an error does (change c0101; measurements in `docs/evidence/kicad-stackup.md`).

## Documents

Six more kinds are documents for a manufacturer or an enclosure designer. Each is selected by its own
flag (`--all` does not select them), runs with one fixed argument list on KiCad 9 and 10, and is written
under `--out` like the four kinds above.

```
fenolite export build/blink --out fab --step --ipc2581 --manifest --dry-run
fenolite export build/blink --out docs --pdf --sch-pdf --confirm
```

| flag | files under `--out` | `kicad-cli` call (fixed) | hashes that compare |
|---|---|---|---|
| `--ipc2581` | `ipc2581/<stem>.xml` | `pcb export ipc2581 --version C --units mm --precision 6` | none |
| `--odb` | `odb/<stem>.zip` | `pcb export odb --compression zip --units mm` | none |
| `--step` | `3d/<stem>.step` | `pcb export step --subst-models`, with the model files below | none |
| `--pdf` | `pdf/<stem>-<layer>.pdf` per layer | `pcb export pdf --mode-separate --layers <list> --common-layers Edge.Cuts --include-border-title` | `content_sha256` |
| `--dxf` | `dxf/<stem>-<layer>.dxf` per layer | `pcb export dxf --mode-multi --output-units mm --layers <list>` | `sha256` |
| `--sch-pdf` | `schematic/<stem>.pdf` | `sch export pdf <stem>.kicad_sch` | `content_sha256` |

- **Board PDF.** One file per layer: the layers of the Gerbers, then `F.Fab` and `B.Fab` where the board
  has them, then `Edge.Cuts`. Every page also carries the outline and the frame of the drawing sheet.
- **DXF.** One file per layer, in millimetres and in the coordinates of the board file: `Edge.Cuts`,
  then `F.Fab`, `B.Fab`, `F.CrtYd` and `B.CrtYd` where the board has them. KiCad names the courtyard
  files `F_Courtyard` and `B_Courtyard`.
- **STEP.** The board body and the bodies of the parts whose model files were found. No origin option
  is passed: the model lies at the coordinates of the board file with y negated, so an outline from
  (100, 100) to (176, 192) mm gives points from x 0 to 176 mm and y −192 to 0 mm. Copper is not exported.
- **IPC-2581 and ODB++.** One file each: IPC-2581 version C uncompressed, ODB++ as a zip.
- **A preset changes no document kind.** `--preset` reaches `--gerbers`, `--drill` and `--pos` only.
- **Options never passed:** `--check-zones`, `--board-plot-params`, `--variant` (KiCad 10 only),
  `--drawing-sheet` and `--define-var` (they would replace what the project says).

### Which hashes compare

`result.repeat` gives, for each selected kind, what two exports of an unchanged board share. It is a
property of the kind, measured on both KiCad majors, not of one file.

| `repeat` | kinds | meaning |
|---|---|---|
| `bytes` | `pos`, `ipcd356`, `dxf` | two exports are byte-equal: compare `sha256` |
| `content` | `gerbers`, `drill`, `pdf`, `sch-pdf` | they differ only in date-bearing lines: compare `content_sha256` |
| `none` | `ipc2581`, `odb`, `step` | they differ beyond their dates. `content_sha256` equals `sha256`, and **neither hash tells whether the board changed**: the hash identifies a file, not the board's content |

Until staged plans exist (change c0120), a `--dry-run` of a `none` kind shows other hashes than the
`--confirm` that follows writes, because each is a run of its own.

### 3D models

In this page "model" means a 3D model *file* (STEP or VRML) that a footprint names with `(model …)`.
The extruded `bodies` of a footprint definition (the volumes an Altium build can write) are not files
and reach no STEP through `export`.

`kicad-cli` leaves out a body whose file it cannot find and still exits 0, and Fenolite runs it without
your KiCad settings. So Fenolite finds the files itself, copies them into the run and reports them:
the STEP holds exactly the models that `result.models` lists. For a path
`${KICAD<N>_3DMODEL_DIR}/<rel>` the sources are tried in this order:

1. `project`: `<board folder>/3dmodels/<rel>`, the copies of `fenolite models --vendor`;
2. `env`: the variable `KICAD<N>_3DMODEL_DIR` of your environment;
3. `kicad-config`: the same variable set in KiCad (its `kicad_common.json` of major N);
4. `install`: the `3dmodels` folder of the KiCad install;
5. `cache`: a file fetched with `tools/kicad_libs_fetch.py --models` whose SHA-256 is still its stamp entry.

A path `${KIPRJMOD}/<rel>` is read from the board's folder (`project`), and any other path (absolute,
or with another variable) is left to `kicad-cli` where it is (`in-place`). A `.wrl` path brings its
`.step` and `.stp` siblings, which KiCad takes in its place.

```
fenolite models build/blink                       # where each model is found; runs no tool
fenolite models build/blink --vendor --confirm    # copy them into build/blink/3dmodels/
```

- Each entry of `result.models` has `path`, `source`, `sha256`, `bytes` and `refs`. Read it after every
  STEP export: a `missing` entry is a part without a body.
- A missing model is the warning `kicad.lib.missing-3d-model` naming the path and its parts; the STEP is
  still written and the exit code stays 0. `export.model-unread` says that Fenolite gave a file and
  `kicad-cli` could not use it.
- `--vendor` copies the located official models into the project's `3dmodels/` folder and changes
  nothing else: the board and its footprints keep their paths. Later exports take the copies first, on
  any machine. KiCad itself reads that folder only if you point `KICAD<N>_3DMODEL_DIR` at it. Deleting
  the folder returns to the other sources.
- The official 3D models are licensed CC-BY-SA 4.0 with the KiCad library exception, like the footprint
  and symbol libraries (`docs/evidence/sources.md`, S-0048 and S-0700). Copies in your project keep
  that licence; this is a statement of the source's licence, not legal advice.
- In the manifest, a STEP entry's `from` names the board only. A changed model file does not mark a STEP
  stale: the models are in `result.models` of the export, and vendored copies are design files of the
  project manifest (kind `3d-model`).

### Schematic PDF

`--sch-pdf` plots `<stem>.kicad_sch` beside the board with every sheet of its hierarchy. Without that
schematic the command exits 3 before any run. `kicad-cli` plots an empty page for a sheet whose file is
missing and reports nothing, so a hierarchy that names a sheet Fenolite cannot give the run (missing,
outside the project folder, in a cycle, or too large to copy) is refused with `export.sheet-missing` and
no file of the export is written. In the manifest, the entry's `from` names the root sheet only: an
edit of a sub-sheet does not mark the PDF stale.

### Page of a board PDF

`kicad-cli` plots on the board's paper whatever the extent of the board. When the outline does not fit
the page, `export.page-too-small` (a warning) names both sizes; the files are written, cut at the page.
Choose a larger paper for the board (`Design.sheet(paper=…)` in a script).

### KiCad boards only

`export` and `models` take a KiCad board (`.kicad_pcb`, `.kicad_pro` or their folder). An Altium
document or project is refused with exit 2 before any tool is looked for: the six documents are written
by `kicad-cli` from a KiCad board, and Fenolite does not convert a board to export it. An Altium build
has its output job instead (`build --target altium`, `docs/altium.md`), which Altium runs.
`--altium-rul` stays what it is: a rule file made from a KiCad project's rules, with no tool.

## Presets

A fabricator's options are yours to state, in a file of your own. `fenolite export … --preset fab.toml`
reads it and gives each key as one `kicad-cli` option; a key you leave out keeps the fixed value of the
table above, so an empty preset and no preset run the same commands. Fenolite ships no preset and knows
no fabricator: take the values from your fabricator's own instructions.

```toml
# fab.toml: an example of the form, not a recommendation
schema = "fenolite.export-preset.v0"

[gerbers]
protel_extensions = true
subtract_soldermask = true

[drill]
units = "in"
map = "pdf"

[pos]
side = "front"
exclude_dnp = true
```

| table | key | values | default |
|---|---|---|---|
| `gerbers` | `layers` | a list of KiCad layer names | the board's copper, mask, paste, silkscreen and edge layers |
| | `protel_extensions` | bool | false |
| | `x2`, `netlist_attributes`, `aperture_macros` | bool | true |
| | `precision` | 5 or 6 | KiCad's |
| | `subtract_soldermask`, `use_drill_file_origin`, `include_border_title`, `exclude_refdes`, `exclude_value` | bool | false |
| `drill` | `format` | `excellon`, `gerber` | `excellon` |
| | `units` | `mm`, `in` | `mm` |
| | `separate_th` | bool | true |
| | `mirror_y`, `minimal_header` | bool | false |
| | `origin` | `absolute`, `plot` | `absolute` |
| | `zeros` | `decimal`, `suppressleading`, `suppresstrailing`, `keep` | KiCad's |
| | `oval_format` | `route`, `alternate` | KiCad's |
| | `map` | `none`, `pdf`, `gerberx2`, `ps`, `dxf`, `svg` | `none` |
| | `gerber_precision` | 5 or 6, with `format = "gerber"` | KiCad's |
| `pos` | `format` | `csv`, `ascii`, `gerber` | `csv` |
| | `units` | `mm`, `in` | `mm` |
| | `side` | `front`, `back`, `both` | `both` |
| | `exclude_dnp`, `exclude_fp_th`, `smd_only`, `use_drill_file_origin`, `bottom_negate_x` | bool | false |

- Every key maps to an option that `kicad-cli` 9.0 and 10.0 both have. Options of one major only, and
  the two options that would make the files depend on more than the board as it is (`--check-zones`,
  `--board-plot-params`), cannot be given.
- The Excellon keys (`units`, `separate_th`, `mirror_y`, `minimal_header`, `zeros`, `oval_format`) are
  refused with `format = "gerber"`, and `gerber_precision` without it.
- A wrong table, key or value stops the command before any run (exit 3), naming the `table.key`.
- What an option does to a file is KiCad's and your fabricator's to judge. Six keys change nothing on a
  board that has nothing for them to act on, such as `drill.oval_format` on a board without an oval hole.

## The manifest

`fenolite-artifacts.json` (schema `schemas/fenolite.artifacts.v0.json`) says which file came from which
design, by which tool, with its hashes and what was verified about it. One format has two writers:

- **A producing command** (`export`, `render`, `bom`, `pnp`) with `--manifest` adds its files to the
  manifest of its output folder. Every entry it writes is `generated`.
- **`fenolite manifest`** writes the project manifest next to the board: the design files and the
  artefacts of the folders it is given, each with a state.

| field | meaning |
|---|---|
| `schema` | `fenolite.artifacts.v0` |
| `fenolite` | the Fenolite version |
| `generated` | the time of the run; pass `--timestamp` for a fixed value |
| `board.path`, `board.sha256`, `board.format_version` | the board file (name relative to the project folder), its SHA-256 and its KiCad format version |
| `tool.name`, `tool.version` | the tool of the run that wrote the manifest: `kicad-cli` and its version, or `fenolite` when no tool ran |
| `project.board`, `project.schematic` | the board and the root schematic, each `path`, `sha256`, `format_version`, or `null` |
| `check` | `null`, or the check behind the states: `stages` (each `name`, `status`, `level`, `oracle`) and `tool_version` |
| `states` | the number of entries per state |
| `artifacts[]` | one entry per file, sorted by `path` |

Each entry has `path` (relative to the manifest's folder; in a project manifest, to the project folder),
`kind`, `layer` (the canonical layer name of a Gerber, else `null`), `bytes`, `sha256`,
`content_sha256`, `evidence`, and:

| field | meaning |
|---|---|
| `state` | one of the five states below |
| `held` | why the entry is not one state higher (`native-verified: drc.kicad reported errors`), or `""` when no higher state applies to its kind |
| `stale` | true when a file was made from a board or schematic that has another SHA-256 now |
| `from` | the SHA-256 of each source the file was made from (`board`, `schematic`); empty for a design file |
| `tool` | what wrote the file (`kicad-cli 10.0.6`, `fenolite 0.2.0`), or `null` for a file neither wrote, or one edited since |

Kinds: `gerbers`, `drill`, `pos`, `ipcd356`, `ipc2581`, `odb`, `step`, `pdf`, `dxf`, `sch-pdf`
(`export`), `render`, `bom`, `pnp`, and for design files
`kicad_pcb`, `kicad_sch`, `kicad_pro`, `kicad_dru`, `kicad_mod`, `kicad_sym`, `kicad_wks`, `lib-table`,
`3d-model` (a file below the project's `3dmodels/` folder) and `file` (any other file of a library
folder). `layer` is also set for each file of `pdf` and `dxf`. The manifest holds no absolute path and does not list
itself. A manifest written by v0.1 has none of the fields from `project` on; it is still read, and its
entries count as `generated`.

`evidence` is the level of the entry's own claim: which files a tool wrote, with which hashes (the
level of the run, so `INFERRED` for an export with a preset, and the level of the document kinds for
their files). For a
design file the entry claims a hash only, so it is `UNVERIFIED`; what was verified about the file is its
`state`, and the levels of the stages behind it are in `check`.

### Merging

`--manifest` never replaces a manifest. The command reads `fenolite-artifacts.json` of its output folder
(`--out DIR` for `export` and `render`, the folder of `--out FILE` for `bom` and `pnp`), replaces the
entries of the files it writes, keeps every other entry as it is, and plans the merged file as one more
write. `board`, `tool` and `generated` become those of this run and `check` becomes `null`. If the file
in the folder is not a manifest Fenolite reads, the command writes nothing at all and reports
`manifest.unreadable`.

```
fenolite export build/blink --out build/blink/fab --all --manifest --confirm
fenolite render build/blink --out build/blink/fab --svg --manifest --confirm
fenolite pnp build/blink --out build/blink/fab/pnp.csv --manifest --confirm
```

### States

A state is read from a result that already exists: a stage of `fenolite check`, the RT1 verdict of
`fenolite roundtrip` for a sheet, and hashes. Nothing is judged a second time. The states are a ladder:
a file has the highest one it reaches **together with every lower one that applies to its kind**, and a
state that is not reached stops the ladder there.

| state | rule | what it does not claim |
|---|---|---|
| `generated` | the file exists and its SHA-256 is recorded | that anything looked at it |
| `checked` | the stages `model.validate` and `copper.clearance` ran on the project with status `ok`, and the file is the one that was hashed; a derived file (Gerber, drill, table, view) also needs its `from` to hold the present hash of a source that is `checked` | that the file itself was read: a Gerber is `checked` because the board it came from was |
| `roundtrip-ok` | board: the stage `roundtrip` is `ok`; schematic sheet: it passes RT1. Other kinds skip this state | that the design is right: only that Fenolite reads and writes the file without loss |
| `oracle-verified` | **unused**: no rule assigns it. It is kept for a tool that is neither the producer of a file nor its format's own application | — |
| `native-verified` | board: the stage `drc.kicad` is `ok` and its evidence is `KICAD-VERIFIED`. The project file, the rules file, the footprint table, the footprint libraries and the drawing sheet reach it exactly when the board does: they are what KiCad loaded to judge it. Schematic sheet, symbol library and `sym-lib-table`: the stage `erc.kicad` is `ok` and its evidence is `KICAD-VERIFIED` | that the board works: KiCad reported no error under the rules of the project, no more |

Two limits are deliberate, and the schematic side has its own stage:

- **A derived file stops at `checked`.** KiCad produced the Gerbers; nothing judged them. The producer
  of a file does not verify it.
- **The schematic side follows KiCad's ERC, not its DRC.** A sheet, a symbol library and
  `sym-lib-table` reach `native-verified` when the stage `erc.kicad` of `check` is `ok` at
  `KICAD-VERIFIED` (change c0062): the ERC loaded the sheets with the libraries the table names. A
  schematic with an ERC error stays at `roundtrip-ok` (`held`: `native-verified: erc.kicad reported
  errors`), whatever the board reaches, and a board with a DRC error does not hold the schematic back.
- **A vendored 3D model stops at `checked`.** KiCad's DRC does not load it, and the STEP export that
  reads it judges nothing about it.
- **A file of unknown origin stays `generated`.** A derived entry without `from` (an entry of a v0.1
  manifest, or a file edited after it was exported) names no source, so nothing can be said about it.

A state belongs to a hash. `export`, `render`, `bom` and `pnp` only ever write `generated`; states come
from `fenolite manifest`, which hashes every file again.

### The project manifest

```
fenolite manifest build/blink --artifacts build/blink/fab --dry-run
fenolite manifest build/blink --artifacts build/blink/fab --confirm
fenolite manifest build/blink --verify
```

`fenolite manifest PATH` lists the design files of the project (the board, its project and rules files,
the library tables and the libraries they name inside the project, the schematic and its sheets), takes
the entries of `DIR/fenolite-artifacts.json` for each `--artifacts DIR` inside the project, hashes every
file, runs the stages of `check` and writes `fenolite-artifacts.json` next to the board. The exit code
is 5 when the check found an error; the manifest is written all the same, with the states that hold.
`--no-check` runs nothing and records hashes only. `--stages` selects the stages, as for `check`.

When it writes, the command tells you what it could not carry over: `manifest.missing` (a listed file
is gone and is left out), `manifest.changed` (a listed file was edited: it is listed as it is now,
without `tool` and `from`), `manifest.stale` (the board changed after the file was made) and
`manifest.unlisted` (a file in an artefact folder that no entry lists; it is not added).

`--verify` answers "is this folder still what the manifest says?". It reads the manifest, hashes every
listed file and writes nothing. `result.verified` is false, and the exit code 5, when a listed file is
missing or has another hash; `result.differences` lists each path with its code. It runs no check: it
compares bytes, it does not renew a state. To verify the manifest of one export folder, name it:
`fenolite manifest build/blink --verify --out build/blink/fab/fenolite-artifacts.json`.

### Why two hashes

KiCad stamps the creation date into Gerber and drill files, so two exports of the same board are not
byte-equal. `sha256` is the hash of the file as written. `content_sha256` is the hash of the file
without its date lines: the lines that start with `%TF.CreationDate`, `G04 Created by KiCad`,
`; DRILL file` or `; #@! TF.CreationDate`, and the `"CreationDate":` line of the Gerber job file.

A board PDF and a schematic PDF carry one such line too, `/CreationDate`.

To know whether two exports hold the same fabrication data, compare `content_sha256`. For the position
file, the netlist and the DXF files the two hashes are equal, because those files carry no date. For
IPC-2581, ODB++ and STEP no hash compares ("Which hashes compare"). The files themselves
are never edited: Fenolite writes exactly the bytes KiCad produced.

## Render

```
fenolite render build/blink --out views --svg --png --confirm
```

| flag | files | how |
|---|---|---|
| `--svg` | `front.svg`, `back.svg` (mirrored) | `pcb export svg --mode-single` with the copper, silkscreen, fabrication and `Edge.Cuts` layers of the side |
| `--png` | `top.png`, `bottom.png` | `pcb render`, at most `--width` × `--height` pixels (default 1600 × 1200) |

A render is for looking at, never a gate. A view that cannot be produced gives the warning
`render.failed`; the other views are still written and the exit code stays 0. KiCad keeps the board's
proportions, so a PNG may be smaller than the size asked for.

`fenolite check PATH --stages render` proves that the board plots without writing anything: the stage
reports the size and SHA-256 of each view. It runs only when named.

## Where they sit in the loop

`build` → `place` → `route` → `fill` → `check` → `export` → `render`. `export` does not run `check` for
you and does not refuse a board with findings: the order is yours to keep. After `export --step`, read
`result.models`; when an entry is `missing`, `fenolite models` shows the sources tried. `fenolite manifest`, run last,
records in one file whether that order was kept: an export of a board that changed since is `stale`.

## Assembly tables

`export --pos` writes KiCad's own position file, with KiCad's columns. For a bill of materials and a
placement table in the columns, units and rotation convention that an assembly service asks for, write a
column template and use `fenolite bom` and `fenolite pnp`: see [`docs/assembly.md`](assembly.md), which
also says how the two placement files relate. Fenolite ships no template of any service.

## Evidence

On 2026-10-03 the file sets, the date lines and the renders were measured on `kicad-cli` 9.0.9 and
10.0.6 (`docs/evidence/kicad-export.md`; hypotheses `H-K-EXPORT-FILES`, `H-K-EXPORT-REPEAT`,
`H-K-EXPORT-RENDER` in `docs/hypotheses.md`). Every reply of `export` and `render` carries its evidence
level and the oracle `kicad-cli <version>`.

The six document kinds were measured on 2026-10-05 on both majors and probed again on `kicad-cli` 10.0.6
on 2026-10-07 (`H-K-EXPORT-DOCS`, `H-K-EXPORT-DOCS-REPEAT`, `H-K-EXPORT-MODELS`, `H-K-EXPORT-SHEETS`,
`H-K-EXPORT-PDF-PAGE`). Their probes are not yet recorded for 9.0.9, so an export that selects a
document kind, and `fenolite models`, carry `INFERRED`.
