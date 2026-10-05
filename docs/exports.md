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
- **A manifest.** `--manifest` writes `fenolite-artifacts.json`: which file came from which board, by
  which tool version, with its hashes.

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

`fenolite-artifacts.json` (schema `schemas/fenolite.artifacts.v0.json`):

| field | meaning |
|---|---|
| `schema` | `fenolite.artifacts.v0` |
| `fenolite` | the Fenolite version |
| `generated` | the time of the export; pass `--timestamp` for a fixed value |
| `board.path`, `board.sha256`, `board.format_version` | the board file (name relative to the project folder), its SHA-256 and its KiCad format version |
| `tool.name`, `tool.version` | `kicad-cli` and its version |
| `artifacts[]` | one entry per file, sorted by `path` |

Each artefact has `path` (relative to the manifest's folder), `kind`, `layer` (the canonical layer name
of a Gerber, else `null`), `bytes`, `sha256`, `content_sha256` and `evidence`. The manifest holds no
absolute path and does not list itself.

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
you and does not refuse a board with findings: the order is yours to keep.

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
