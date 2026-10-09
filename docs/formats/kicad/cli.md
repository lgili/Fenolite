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
| `sch` has the subcommands `erc`, `export` and `upgrade` only: there is no schematic import (10.0 adds `pcb import` and nothing for schematics). An Altium schematic document is not read: on the built `tests/data/altium/tree/`, `sch export netlist --format kicadxml -o out.net tree.SchDoc`, `sch export netlist -o out.net tree.PrjPcb`, `sch upgrade tree.SchDoc` and `sch erc -o erc.rpt tree.SchDoc` answer "Failed to load schematic" on 10.0.6; on 9.0.9 the same, except that `sch upgrade` of a `.SchDoc` is refused as a usage error. Only the GUI importer reads a `.SchDoc`; an Altium schematic LIBRARY is converted by `sym upgrade` (local run in the pinned images `kicad/kicad:10.0.6@sha256:18693567…` and `kicad/kicad:9.0.9@sha256:e638b79b…`, 2026-10-09; change c0086, task 5.2) | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | — |

## Refill on a copy

| fact | source | label | hypothesis |
|---|---|---|---|
| `pcb drc --format json --severity-all --refill-zones --save-board -o drc.json BOARD` refills zones and saves the board beside its report in KiCad 10.0; these options are absent from KiCad 9.0 | S-0022, S-0037 | KICAD-VERIFIED (10.0.x, 9.0.x) | H-K-FILL-SAVE |
| With an authored board of either target major, 10.0.6 writes a saved board, a `.kicad_prl` and `drc.json` in the run folder | S-0020 | KICAD-VERIFIED (10.0.x) | H-K-FILL-SAVE |
| `docker run --rm --pull never --platform linux/amd64 -v HOST:/w -w /w -e KICAD_CONFIG_HOME=/w/config -e LANG=C -e LC_ALL=C IMAGE kicad-cli …` runs a named image with the copied project mounted at `/w`; the runner never pulls an image | S-0205 | INFERRED | H-K-CLI-DOCKER |

## Per-run state

Parallel `kicad-cli` processes on one machine must not share state that the tool writes outside its run
folder (c0153). Each run of the package runner therefore gets its own temporary, runtime, cache and state
folders under `<run folder>/.fenolite-state/` (`cli.private_state`), next to its own `KICAD_CONFIG_HOME`;
the folders are removed with the run folder. Configuration and data folders are not moved: KiCad's
configuration is already `KICAD_CONFIG_HOME`, and fonts and user data are only read.

| fact | source | label | hypothesis |
|---|---|---|---|
| A process on a POSIX system takes `TMPDIR` as the folder for its temporary files; Python's `tempfile`, as an example of the convention, tries `TMPDIR`, then `TEMP`, then `TMP` | S-0703, S-0705 | INFERRED | H-K-CLI-STATE |
| `XDG_RUNTIME_DIR` names a per-user folder for runtime files (sockets, named pipes) that only the user may read and write (mode 0700); `XDG_CACHE_HOME` and `XDG_STATE_HOME` name the user's cache and state folders | S-0704 | INFERRED | H-K-CLI-STATE |
| `KICAD_CONFIG_HOME` moves KiCad's configuration folder | S-0045 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-CLI-HELP |
| Under parallel runs on one machine, `kicad-cli` 9.0.9 and 10.0.6 have printed "Invalid lock file '/tmp/org.kicad.kicad/instances/kicad-cli-<major>.0'": the tool keeps an instance lock file named by its program and major in a folder `org.kicad.kicad/instances` of the shared temporary folder, the same file for every process of that major. Runs that printed it lost their usual result: an unloadable schematic gave no "Failed to load schematic" (kicad-9 job, 2026-10-08), a broken drawing sheet gave no "Error loading drawing sheet" (kicad-9 job, 2026-10-08; c0082 on 10.0.6), and an import added the warning (c0051, kicad-10 job) | S-0020 | INFERRED | H-K-CLI-STATE |
| With `TMPDIR`, `TMP` and `TEMP` naming a private folder, the instance folder `org.kicad.kicad/instances` is created in that folder, so runs with different folders share no lock file; eight runs at once with private folders give their usual result and print no lock message (`tests/kicad/check/test_parallel_runs_oracle.py`, the `kicad-9` and `kicad-10` jobs of CI run https://github.com/lgili/Fenolite/actions/runs/37836186018, 2026-10-08) | S-0020, S-0703 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-CLI-STATE |
| The Docker runner keeps the caller's environment for the `docker` client (a rootless daemon's socket is under `XDG_RUNTIME_DIR`); each container (`--rm`) has its own `/tmp` | S-0205, S-0704 | INFERRED | H-K-CLI-DOCKER |

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
| `pcb export step` | present | present |
| `pcb export pdf` | present | present |
| `pcb export dxf` | present | present |
| `fp upgrade` | present | present |
| `sym upgrade` | present | present |
| `sch erc` | present | present |
| `sch export netlist` | present | present |
| `sch export pdf` | present | present |
| `jobset run` | present | present |

The rows of `pcb export step`, `pdf` and `dxf` and of `sch export pdf` were added by change c0116 and recorded on
10.0.6 on 2026-10-07 and on 9.0.9 (the pinned image, local run) on 2026-10-08.

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
| `pcb export gerbers` has `--layers`, `--no-protel-ext`, `--no-x2`, `--no-netlist`, `--disable-aperture-macros`, `--precision`, `--subtract-soldermask`, `--use-drill-file-origin`, `--include-border-title`, `--exclude-refdes` and `--exclude-value` on 9.0.9 and 10.0.6 | S-0020, S-0022, S-0037 | INFERRED | H-K-EXPORT-OPTIONS |
| `pcb export drill` has `--format`, `--excellon-units`, `--excellon-separate-th`, `--drill-origin`, `--excellon-mirror-y`, `--excellon-min-header`, `--excellon-zeros-format`, `--excellon-oval-format`, `--generate-map`, `--map-format` and `--gerber-precision` on both majors | S-0020, S-0022, S-0037 | INFERRED | H-K-EXPORT-OPTIONS |
| `pcb export pos` has `--format`, `--units`, `--side`, `--exclude-dnp`, `--exclude-fp-th`, `--smd-only`, `--use-drill-file-origin` and `--bottom-negate-x` on both majors; `--format ascii` writes a `.pos` file and `--format gerber` a `.gbr` file | S-0020, S-0022, S-0037 | INFERRED | H-K-EXPORT-OPTIONS |
| Two runs on one board differ only in the lines that start with `%TF.CreationDate`, `G04 Created by KiCad`, `; DRILL file` or `; #@! TF.CreationDate`, and in the job file's `"CreationDate":` line | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-EXPORT-REPEAT |
| The position CSV and the IPC-D-356 file are byte-equal across two runs | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-EXPORT-REPEAT |
| In the position CSV (`Ref,Val,Package,PosX,PosY,Rot,Side`), `Ref`, `Val` and `Package` are in double quotes and the numbers and the side are bare; `Val` is the footprint's Value and `Package` the footprint's name without its library (measured on the authored board and on the built blink, c0064) | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-POS-ROWS |
| Without a DNP option, the position CSV lists a footprint that has the attribute `dnp` and leaves out one that has `exclude_from_pos_files` (measured on the built blink with both flags set, c0064) | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-POS-ROWS |
| `Rot` is the stored angle printed with 6 decimals in the range above −180° up to 180°: 180° is `180.000000` and 270° is `-90.000000`, on the top and on the bottom side (measured on the built blink turned to those angles, c0064) | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-POS-ROWS |
| `--check-zones` exists on 10.0 only and refills zones before plotting; Fenolite never passes it | S-0022, S-0037 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-CLI-HELP |
| `pcb export svg --mode-single -o <file> --layers <list>` writes one SVG on both majors; `--mirror` mirrors it | S-0020, S-0022, S-0037 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-EXPORT-RENDER |
| `pcb render --side top\|bottom --width W --height H -o <file>.png` writes a PNG no larger than that size (368 × 280 for 400 × 300) with no display | S-0020, S-0022, S-0037 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-EXPORT-RENDER |
| `pcb export ipc2581`, `odb`, `step`, `pdf` and `dxf` and `sch export pdf` exist on 9.0.9 and 10.0.6; 10.0.6 adds `pcb export 3dpdf`, `ps`, `stats`, `stpz` and `u3d` (c0116) | S-0020, S-0022, S-0029, S-0037 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-EXPORT-DOCS |
| Options of one major only: `--variant` (all six commands), `--bom-rev` (ipc2581), `--check-zones` (odb, pdf, dxf), `--scale` (pdf, dxf), `--bg-color` and `--no-property-popups` (pdf), `--no-extra-pad-thickness` (step) and `--draw-hop-over` (sch pdf) on 10.0.6; `--plot-invisible-text` (pdf, dxf) on 9.0.9. Fenolite passes none of them | S-0020, S-0022, S-0029, S-0037 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-EXPORT-DOCS |
| Equal defaults on both majors, which Fenolite passes explicitly where they decide the file: ipc2581 `--precision 6`, `--version C`, `--units mm`; odb `--precision 2`, `--compression zip`, `--units mm`; dxf `--output-units in` (Fenolite asks for `mm`) | S-0020, S-0022, S-0037 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-EXPORT-DOCS |
| `pcb export ipc2581 -o <folder>/<stem>.xml`, `pcb export odb -o <folder>/<stem>.zip` and `pcb export step -o <folder>/<stem>.step` each write the one file named; the STEP run prints `STEP file '<path>' created.` and `Export time … s` | S-0020, S-0029 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-EXPORT-DOCS |
| `pcb export pdf --mode-separate --layers <list> -o <folder>/` and `pcb export dxf --mode-multi --layers <list> -o <folder>/` write one file per listed layer, `<stem>-<layer name as KiCad shows it, dots as underscores>.pdf` or `.dxf` (`F_Courtyard` for `F.CrtYd`, `F_Silkscreen` for `F.SilkS`); `--common-layers Edge.Cuts` and `--include-border-title` add the outline and the frame to every PDF page | S-0020, S-0029 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-EXPORT-DOCS |
| `pcb export pdf --mode-multipage -o X` writes the file X on 10.0.6 and a folder `X/` holding `<stem>.pdf` on 9.0.9; with `-o <folder>/`, multipage or no mode exits 2 on 10.0.6. Fenolite uses `--mode-separate` only | S-0020, S-0029 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-EXPORT-DOCS |
| `pcb export dxf` without a mode prints on 10.0.6 that its behaviour will change in a future release to match `--mode-multi`; Fenolite always passes `--mode-multi` | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-EXPORT-DOCS |
| `sch export pdf -o <folder>/<stem>.pdf <root>.kicad_sch` writes one PDF with one page per sheet instance of the hierarchy | S-0020, S-0029 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-EXPORT-DOCS |
| No document holds the user's name or a temporary path; a PDF's `/Title` is its file name | S-0020, S-0029 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-EXPORT-DOCS |
| Two runs of `pcb export dxf` on one board are byte-equal | S-0020, S-0029 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-EXPORT-DOCS-REPEAT |
| Two runs of `pcb export pdf` or `sch export pdf` differ only in the line `/CreationDate (D:…)`, written as `D:2026:10:05:21:44:59` by 10.0.6 and as `D:20261005135825` by 9.0.9 | S-0020, S-0029 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-EXPORT-DOCS-REPEAT |
| Two STEP exports of one board differ beyond the `FILE_NAME(` line (date and output name): entity numbers and colour entities differ, and the files are not equal even as sets of lines | S-0020, S-0029 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-EXPORT-DOCS-REPEAT |
| An IPC-2581 file holds the date in `<HistoryRecord … origination="…" … lastChange="…">` and `<AvlHeader … datetime="…"/>`; without those lines two runs are equal on 9.0.9 and not on 10.0.6, where contour points and line order vary | S-0020, S-0029 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-EXPORT-DOCS-REPEAT |
| An ODB++ zip differs on every run; written as a folder (`--compression none`, 63 files for a four-layer board), `misc/info` and `steps/pcb/eda/data` hold dates, and on 10.0.6 six front-layer `features` files also vary | S-0020, S-0029 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-EXPORT-DOCS-REPEAT |
| A STEP exported with no origin option lies at the coordinates of the board file with y negated: an outline from (100, 100) to (176, 192) mm gives points from x 0 to 176 mm and y −192 to 0 mm; `--board-only` leaves the component bodies out | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-EXPORT-MODELS |
| `sch export pdf` plots a page for a sheet whose file is missing, prints only `Plotted to '…'` and `Done.` and exits 0, on both majors; Fenolite therefore refuses such a hierarchy before the run | S-0020, S-0029 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-EXPORT-SHEETS |
| The page of `pcb export pdf` is the board's paper whatever the extent of the board: an outline of 158 × 179 mm from (100, 100) mm on A4 gives `/MediaBox [0 0 841.896 595.296]` (A4 landscape), with and without `--include-border-title` | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-EXPORT-PDF-PAGE |

The rows of the six document kinds (change c0116) were measured on 2026-10-05 on both majors and are probed by
`tests/kicad/export/test_document_probes.py`; the probes are recorded for both majors, and the tests passed in the
`kicad-9` and `kicad-10` jobs of CI run 37772583226 (2026-10-08), so the rows are `KICAD-VERIFIED (9.0.x, 10.0.x)`. How `pcb export step` finds 3D model files is in `libraries.md`, "3D models".

## Importer differences

What `kicad-cli pcb import --format altium` changes in a board, as far as `fenolite equivalent --against
kicad-import` needs it (change c0045). Each rule of
`src/fenolite/backends/kicad/data/altium_import_exclusions.toml` has one row here, named by its rule id;
the counts per document are in `docs/evidence/equivalence-triangle.md`.

| fact | source | label | hypothesis |
|---|---|---|---|
| `pcb import` takes `--output`, `--format` (`auto`, `pads`, `altium`, `eagle`, `cadstar`, `fabmaster`, `pcad` or `solidworks`), `--report-format` (`none`, `json` or `text`) and `--report-file`, and the input file | S-0022 | KICAD-VERIFIED (10.0.x) | H-K-00 |
| An imported board is moved on its sheet as a whole, so an import keeps relative positions only | S-0020 | ORACLE-VERIFIED(kicad-cli) (10.0.6) | H-G-EQ-SHIFT |
| One binary length unit is 2.54 nm, so a length rounds to a whole nanometre in each reader, and the two results may differ by the rounding | S-0002 | INFERRED | H-G-EQ-ROUND |
| `kicad-10.0-value-empty`: on one public document, one component whose comment text the document holds has an empty value in the converted board; the other 417 compared components have equal values | S-0020, S-0188 | INFERRED | H-G-EQ-VALUE |
| `kicad-10.0-paste-pad-pin`: a pad on a paste layer is not imported, so its `REF-PIN` exists in Fenolite's read only (2 pads of one public document; `docs/formats/altium/pcb-read.md`, "What KiCad does not import") | S-0020, S-0161, S-0188 | ORACLE-VERIFIED(kicad-cli) (10.0.6) | H-A-RD-PCB-KICAD-DOC |
| `kicad-10.0-paste-pad`: the same pads at level 3: the footprint in KiCad's board holds no pad of that number | S-0020, S-0161, S-0188 | ORACLE-VERIFIED(kicad-cli) (10.0.6) | H-A-RD-PCB-KICAD-DOC |
| `kicad-10.0-component-copper-pad`: a copper region of a component, and a copper fill of a component without a net, become pads without a number, so the counts of unnumbered pads of a footprint differ (16 such pads on three public documents) | S-0020, S-0161, S-0172, S-0188, S-0199 | ORACLE-VERIFIED(kicad-cli) (10.0.6) | H-A-RD-PCB-KICAD-DOC |
| `kicad-10.0-octagon-shape`: an octagonal pad is a rounded rectangle in the converted board; Fenolite's import gives it a custom shape, and the model has no octagon (2 pads of one public document) | S-0020, S-0176 | INFERRED | H-G-EQ-PADSHAPE |
| A converted length is held in steps of 10 nm; after the translation no footprint position, pad position, pad size or drill of seven public documents differs by more than 9 nm from Fenolite's read | S-0020, S-0002 | ORACLE-VERIFIED(kicad-cli) (10.0.6) | H-G-EQ-ROUND-2 |
| A pad that belongs to no component becomes a footprint without a reference, as in Fenolite's import; a footprint is named by the designator text the board shows | S-0020, S-0161 | ORACLE-VERIFIED(kicad-cli) (10.0.6) | H-G-EQ-FREE-2 |

## Bill of materials

`fenolite bom` (change c0064) runs `sch export bom` on a copy of the schematic, once, and reads the file
back (`backends/kicad/bom.py`). Everything below was measured by running the binary (S-0020) on schematics
that `fenolite build` wrote; no manual page is cited.

| fact | source | label | hypothesis |
|---|---|---|---|
| `sch export bom` exists on 9.0.9 and 10.0.6, and its help page lists `--fields`, `--labels`, `--group-by`, `--sort-field`, `--sort-asc`, `--filter`, `--exclude-dnp`, `--include-excluded-from-bom`, `--field-delimiter`, `--string-delimiter`, `--ref-delimiter`, `--ref-range-delimiter`, `--keep-tabs`, `--keep-line-breaks`, `--preset`, `--format-preset` and `--output` on both; 10.0.6 adds `--variant` | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-BOM-CSV |
| With `--fields <list>` and `--labels <the same list>`, the first line is the labels, each in double quotes, separated by commas; every cell of every row is in double quotes too. These are the tool's default delimiters | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-BOM-CSV |
| Without `--group-by` there is one row per reference: two parts of one value are on two rows, and a symbol with three units is on one row | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-BOM-CSV |
| The field `${DNP}` is `DNP` for a symbol marked `(dnp yes)` and empty for the others; the DNP part is listed | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-BOM-CSV |
| A symbol whose reference starts with `#` (a power flag) and a symbol marked `(in_bom no)` are not listed | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-BOM-CSV |
| A user property named in `--fields` gives its column, with the value of each symbol that has it; a field that no symbol has gives an empty column, and the run exits 0 | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-BOM-CSV |
| The call without `--fields` writes the header `"Refs","Value","Footprint","Qty","DNP"` and one row per part, on both majors | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-BOM-CSV |
| For a project that `build` wrote, the rows equal the parts of the built model: reference, value, footprint, DNP mark, description, datasheet and user properties | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-BOM-MODEL |

## Drawings

The drawing kinds of `fenolite export` (change c0117; `docs/drawings.md`) plot copies of the board with
`pcb export pdf` and take KiCad's drill maps and report. Everything below was measured by running the
binary (S-0020) on the authored bench of `tests/_drawdesign.py`; the outcomes are in
`docs/evidence/kicad-drawings.md`. The probes are recorded on 9.0.9 and 10.0.6, and the tests of
`tests/kicad/drawings/` passed in the `kicad-9` and `kicad-10` jobs of CI run 37772583226 (2026-10-08).

| fact | source | label | hypothesis |
|---|---|---|---|
| At the default scale `pcb export pdf` and `svg --mode-single` draw an item at the page point of its board coordinates; `--mirror` maps x to W − x for the page width W | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-DRAW-PAGE |
| `--drill-shape-opt 0` draws no hole on a plot; the default draws pad holes and no via hole | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-DRAW-PAGE |
| `pcb export pdf` and `pcb export svg` have `--scale` on 10.0.6 | S-0020 | KICAD-VERIFIED (10.0.x) | H-K-DRAW-PAGE |
| `-D NAME=value` sets a text variable for one run, in a board text and in a drawing-sheet text | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-DRAW-ITEMS |
| Without a project sheet, the plotted sheet has borders 10 mm and 12 mm inside the page edges and its title block from (W − 120, H − 44) to (W − 12, H − 12) mm, on A4 to A0 landscape | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-DRAW-SHEET |
| Landscape pages are plotted 297.0022 × 210.0072 (A4), 419.9890 × 297.0022 (A3), 594.0044 × 419.9890 (A2), 840.9940 × 594.0044 (A1) and 1188.9994 × 840.9940 mm (A0) | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-DRAW-SHEET |
| `pcb export drill --excellon-separate-th --generate-map --map-format pdf --generate-report` writes `<stem>-PTH.drl`, `<stem>-NPTH.drl`, one `<stem>-front-in1.drl` for the vias of `F.Cu` to `In1.Cu`, a `<name>-drl_map.pdf` beside each, and `<stem>-drill.rpt` | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-DRAW-DRILL |
| The drill report lists, per drill file, one line per tool with its diameter in millimetres (three decimals) and its hole count; a slot is counted with the round holes of its width; a line of several holes closes with `))` on 10.0.6 | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-DRAW-DRILL |
| `--crossout-DNP-footprints-on-fab-layers` adds strokes over a do-not-populate footprint, `--hide-DNP-footprints-on-fab-layers` removes its fabrication items, `--sketch-pads-on-fab-layers` adds pad outlines and numbers; `--exclude-value` removes value texts of a PDF plot and is no option of `pcb export svg` on 10.0.6 | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-DRAW-ASSEMBLY |
| Two `pcb export pdf` runs of one board differ only in the line `/CreationDate`, two drill reports only in the line `Created on` | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-DRAW-REPEAT |
