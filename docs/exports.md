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

The content of every exported file is KiCad's. Fenolite claims the set of files, their hashes and the
board they came from; it does not read or check the fabrication data. Check the board first
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
| `--all` | the four kinds | |

The Gerber layers are every copper layer in stack order, then `F.Mask`, `B.Mask`, `F.Paste`, `B.Paste`,
`F.SilkS` and `B.SilkS` where the board has them, then `Edge.Cuts`. Courtyard and fabrication layers
are left out. KiCad names a Gerber after the layer name it shows, so the silkscreen files end in
`F_Silkscreen.gbr` and `B_Silkscreen.gbr`.

v0.1 has one way to export each kind; these options are the whole list. Two options are never passed:

- `--check-zones` would refill zones in the copy before plotting, so the files would not show the board
  as it is. Fill the board with `fenolite fill`, check it, then export.
- `--board-plot-params` would make the files depend on plot settings stored in the board.

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

Kinds: `gerbers`, `drill`, `pos`, `ipcd356` (`export`), `render`, `bom`, `pnp`, and for design files
`kicad_pcb`, `kicad_sch`, `kicad_pro`, `kicad_dru`, `kicad_mod`, `kicad_sym`, `kicad_wks`, `lib-table`
and `file` (any other file of a library folder). The manifest holds no absolute path and does not list
itself. A manifest written by v0.1 has none of the fields from `project` on; it is still read, and its
entries count as `generated`.

`evidence` is the level of the entry's own claim: which files a tool wrote, with which hashes (the
level of the run, so `INFERRED` for an export with a preset). For a
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

To know whether two exports hold the same fabrication data, compare `content_sha256`. For the position
file and the netlist the two hashes are equal, because those files carry no date. The files themselves
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
you and does not refuse a board with findings: the order is yours to keep. `fenolite manifest`, run last,
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
