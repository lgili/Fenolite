# KiCad command line (`kicad-cli`)

What Fenolite relies on when it runs `kicad-cli`: the grammar of its help pages, which commands exist
per major (the matrix that `fenolite doctor` reports), the side effects of a run, and the files that
`fenolite check` copies for a DRC run. This page is written in Fenolite's own words from running the
binary (S-0020) and from the published manuals (S-0022 for 10.0, S-0037 for 9.0). No KiCad or
argument-parser source was read. Sources are listed in `docs/evidence/sources.md`.

## Help pages

| fact | source | label | hypothesis |
|---|---|---|---|
| `kicad-cli <words> --help` exits 0 and prints a `Usage:` line first | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-CLI-HELP |
| On the page of a command group, the `Usage:` line ends with one `{a,b,…}` group listing its subcommands, comma-separated without spaces | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-CLI-HELP |
| On the page of a leaf command, each long option appears in the `Usage:` line as a bracketed group that starts with `--name`, followed by a value placeholder when the option takes one; a repeatable option is followed by `...` (10.0.6) | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-CLI-HELP |
| The words before the group or the options vary: 10.0.6 prints `kicad-cli pcb` on the `pcb` page and `pcb export` on the `pcb export` page, 9.0.9 prints only the last word (`pcb`, `export`, `drc`); Fenolite's parser ignores them | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-CLI-HELP |
| The root page lists the groups `fp`, `jobset`, `pcb`, `sch`, `sym` and the command `version`, on 9.0.9 and 10.0.6 | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-CLI-HELP |
| Even a `--help` run creates a configuration folder under `KICAD_CONFIG_HOME`: a per-version subfolder (`9.0`, `10.0`) holding `kicad.json`, `kicad_common.json` and a `colors` folder, on 9.0.9 and 10.0.6 | S-0020, S-0045 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-CLI-HELP |

## Command matrix

`fenolite doctor` reads at most nine help pages per binary (the root page, the groups that exist, and
`pcb drc`) and reports each row of `helpmatrix.MATRIX` as present or absent. A row is present when its
last word is a subcommand, or its option a long option, on its parent's page.

| fact | source | label | hypothesis |
|---|---|---|---|
| `pcb import` exists in 10.0 and not in 9.0 | S-0022, S-0037 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-00 |
| `pcb drc --refill-zones` and `--save-board` exist in 10.0 only | S-0022, S-0037 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-01 |
| `pcb upgrade` exists in 10.0 and not in 9.0 | S-0022, S-0037 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-CLI-HELP |
| `pcb drc --format`, `--severity-all` and `--schematic-parity`, and `pcb export ipcd356`, `pos` and `svg`, exist in 9.0 and 10.0 | S-0022, S-0037 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-CLI-HELP |

## Copy set of a check

`kicad-cli` writes into the folder it runs in, so `fenolite check` gives it only a copy of the files a
DRC run reads, planned by `projectset.project_set` and copied by the runner into a fresh temporary
folder.

| fact | source | label | hypothesis |
|---|---|---|---|
| A board is paired with `<stem>.kicad_pro` and `<stem>.kicad_dru` by its file stem | S-0045 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-CHECK-COPYSET |
| `pcb drc` reads only the board, `<stem>.kicad_pro`, `<stem>.kicad_dru`, the project `fp-lib-table` and the library folders its rows name as `${KIPRJMOD}/<rel>`, so a run on that copy set reports what a run on a copy of the whole folder reports | S-0045, S-0046, S-0022, S-0037 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-CHECK-COPYSET |
| `pcb drc` and `pcb export` write `<stem>.kicad_prl` next to the board and never rewrite `<stem>.kicad_pro` | S-0045, S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-PRO-PRL |

## Measured matrix

The `check-help-*` probes pinned in `docs/evidence/kicad/probes/` (`tests/kicad/check/test_help_matrix.py`):

| row | 9.0.9 | 10.0.6 |
|---|---|---|
| `pcb drc` | present | present |
| `pcb drc --format` | present | present |
| `pcb drc --severity-all` | present | present |
| `pcb drc --schematic-parity` | present | present |
| `pcb drc --refill-zones` | absent | present |
| `pcb drc --save-board` | absent | present |
| `pcb upgrade` | absent | present |
| `pcb import` | absent | present |
| `pcb render` | present | present |
| `pcb export ipcd356` | present | present |
| `pcb export pos` | present | present |
| `pcb export svg` | present | present |
| `pcb export gerbers` | present | present |
| `pcb export drill` | present | present |
| `pcb export stats` | absent | present |
| `pcb export ipc2581` | present | present |
| `pcb export odb` | present | present |
| `fp upgrade` | present | present |
| `sym upgrade` | present | present |
| `sch erc` | present | present |
| `sch export netlist` | present | present |
| `jobset run` | present | present |

Every page that `command_matrix` reads parsed on both versions. On 9.0.9 the rows `pcb import`,
`pcb upgrade`, `pcb export stats`, `pcb drc --refill-zones` and `pcb drc --save-board` are absent; every
row is present on 10.0.6.

## Measured copy set

The probe `check-copyset` (`tests/kicad/check/test_copy_set.py`) recorded `equal` on 9.0.9 and
`equal` on 10.0.6: for the authored built project with a KiCad-written `.kicad_prl`, a
`sym-lib-table` and `notes.txt`, DRC on the copy set reports the same violations and unconnected items
as DRC on a copy of the whole folder. The whole-folder run is repeated, so a board whose KiCad report
changes between identical runs gives `inconclusive` instead of a false difference.

## Exports and renders

`fenolite export` and `fenolite render` (change c0024) run these commands on a copy of the project.

| fact | source | label | hypothesis |
|---|---|---|---|
| `pcb export gerbers -o <folder>/ --no-protel-ext --layers <list>` writes one file per layer, named `<stem>-<layer name with dots as underscores>.gbr`, and the job file `<stem>-job.gbrjob` | S-0020, S-0022, S-0037 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-EXPORT-FILES |
| `pcb export drill -o <folder>/ --format excellon --excellon-units mm --excellon-separate-th --drill-origin absolute` writes `<stem>-PTH.drl` and `<stem>-NPTH.drl` | S-0020, S-0022, S-0037 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-EXPORT-FILES |
| `pcb export pos --format csv --units mm --side both -o <file>` and `pcb export ipcd356 -o <file>` each write the one file named | S-0020, S-0022, S-0037 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-EXPORT-FILES |
| The file name of a Gerber uses the layer name KiCad shows (`F.Silkscreen` for `F.SilkS`), which the board's layer table gives as the user name | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-EXPORT-FILES |
| On 10.0 an export run also writes `<stem>.kicad_prl` next to the board copy; 9.0 does not | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-EXPORT-FILES |
| Two runs on one board differ only in the lines that start with `%TF.CreationDate`, `G04 Created by KiCad`, `; DRILL file` or `; #@! TF.CreationDate`, and in the job file's `"CreationDate":` line | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-EXPORT-REPEAT |
| The position CSV and the IPC-D-356 file are byte-equal across two runs | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-EXPORT-REPEAT |
| `--check-zones` exists on 10.0 only and refills zones before plotting; Fenolite never passes it | S-0022, S-0037 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-CLI-HELP |
| `pcb export svg --mode-single -o <file> --layers <list>` writes one SVG on both majors; `--mirror` mirrors it | S-0020, S-0022, S-0037 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-EXPORT-RENDER |
| `pcb render --side top\|bottom --width W --height H -o <file>.png` writes a PNG no larger than that size (368 × 280 for 400 × 300) with no display | S-0020, S-0022, S-0037 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-EXPORT-RENDER |
