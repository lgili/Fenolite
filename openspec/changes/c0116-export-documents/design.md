## Context

**Scope.** Milestone v0.4. The complex-board review of 2026-10-05 asks for "a package for a contract manufacturer (Gerber and drill or IPC-2581, BOM, placement table, fabrication and assembly drawings, schematic PDF, 3D model)" and for connectors and mounting holes fixed by an enclosure. c0024 listed "STEP, IPC-2581, ODB++, PDF and DXF exports; schematic exports" among its non-goals with no destination, and its design closed with "PDF. Default: not in v0.1". This change takes the six kinds that `kicad-cli` already writes, the 3D models a STEP needs, and their manifest kinds. Drawings are c0117's; the impedance table is c0105's.

**What exists** (`origin/dev` at `9aba2dff`, read on 2026-10-07):

- `exports/plan.py`: `KINDS` holds `gerbers`, `drill`, `pos` and `ipcd356` as `Kind(name, words, options, folder, file, repeatable, majors)`; `run_kind(cli, kind, board, files, *, major, design=None, args=None)` (`plan.py:152`; `args` is the preset callback of c0074) runs one kind through `KicadCli.export`, takes the files under the kind's folder as artefacts and the others as `tool_writes`; `gerber_layers`, `layer_suffixes`, `SHOWN_NAMES` (the silkscreen names only); `VOLATILE_PREFIXES` per kind.
- `exports/manifest.py`: `ArtifactEntry` holds `path`, `kind`, `layer`, `bytes`, `sha256`, `content_sha256`, `evidence` and, since c0065, `state`, `stale`, `from`, `tool` and `held`; `exports/states.py` holds `DERIVED`, the seven derived kinds; `content_sha256` drops the lines that start with a prefix of the kind; `exports.EVIDENCE` is `KICAD-VERIFIED` (`H-K-EXPORT-FILES`, `H-K-EXPORT-REPEAT`) and every entry carries its level.
- `cli/cmd_export.py`: `--gerbers`, `--drill`, `--pos`, `--ipcd356`, `--all` (the four), `--manifest`, `--preset FILE` (c0074) and `--altium-rul` (c0084, which runs no tool); one `PlannedWrite` per artefact, none when a kind fails. The board comes from `projectset.resolve_board`, which accepts a `.kicad_pcb`, a `.kicad_pro` or a folder of them and nothing else.
- `backends/kicad/cli.py`: `KicadCli.run(args, *, files, env, folders)` copies the inputs into a fresh folder, removes every `KICAD*` variable, sets an empty `KICAD_CONFIG_HOME` and `LANG=C`, and applies `env` last. `DockerCli` runs the same inside an image and sees only the run folder.
- `backends/kicad/helpmatrix.py`: `MATRIX` (through `_EXPORTS`, line 33) holds `pcb export ipc2581` and `odb`, not `step`, `pdf`, `dxf` or `sch export pdf`, so `doctor` cannot say whether a major has them.
- `backends/kicad/libs.py`: `LibraryResolver.expand` resolves `${KIPRJMOD}`, the environment, KiCad's `kicad_common.json` (with `read_common`) and the defaults of one source; an install defines `KICAD<M>_3DMODEL_DIR` as its `3dmodels` folder, a verified cache defines none ("Library sources"). `missing_models(fp)` (`libs.py:719`) has no caller in `src`.
- `backends/kicad/libcache.py` and `tools/kicad_libs_fetch.py`: pins and whole-archive fetches of `kicad-footprints` and `kicad-symbols` only, within `MAX_ARCHIVE_BYTES` (1 GiB) and `MAX_TREE_BYTES` (4 GiB).
- `backends/kicad/sch.py` (c0060): `sheet_files(root)` walks a hierarchy and reports `kicad.sch.sheet-missing`, `-outside` and `-cycle`. `projectset.project_set` (c0062, archived) already holds the schematic of the board's stem, its sheet tree, the symbol table with its `${KIPRJMOD}` libraries and the schematic's drawing sheet. A build writes a schematic with one sheet per module (c0061, c0070).
- `design-dsl`, "Footprints of every row origin are vendored": "no 3D model". Built boards keep the model paths of their library footprints, `${KICAD9_3DMODEL_DIR}/…` for target 9 and `${KICAD10_3DMODEL_DIR}/…` for target 10. `FootprintDef.models` holds paths only, and `FootprintDef.bodies` (`model/library.py:48`) holds extruded volumes, which no KiCad module reads or writes (no `bodies` in `backends/kicad/`).
- `Board.sheet` (`SheetFrameRef`) and `model.presentation.PAPER_SIZES` give the paper of a board.

**Measured on 2026-10-05.** `kicad-cli` 10.0.6 (macOS application) and 9.0.9 (the pinned image, emulated), every run on a copy through `KicadCli.run` or the same environment in the container. Subjects: a generated four-layer design of 100 official footprints (9 distinct models), built for target 10 and for target 9, and the same generator at 400 and 600 parts (target 10); the demo schematics `simulation/subsheets` (three sheets) and the largest demo hierarchy of the 10.0.6 corpus (15 sheets) from the corpus cache. None of this is committed; each fact becomes a probe of this change. The measurements were taken on the review branch (`27ef3ad7`) and were not repeated on `dev`: they are facts of `kicad-cli`, which did not change, and task 1.3 takes every one again as a probe before any code leans on it.

1. *Commands and options.* `pcb export` lists `ipc2581`, `odb`, `step`, `pdf` and `dxf` on both majors, and `sch export` lists `pdf`. 10.0.6 adds `3dpdf`, `ps`, `stats`, `stpz` and `u3d`. Only on 10.0.6: `--variant` (all six), `--bom-rev` (ipc2581), `--check-zones` (odb, pdf, dxf), `--scale` (pdf, dxf), `--bg-color` and `--no-property-popups` (pdf), `--no-extra-pad-thickness` (step), `--draw-hop-over` (sch pdf); only on 9.0.9: `--plot-invisible-text` (pdf, dxf). Equal defaults on both: ipc2581 `--precision 6`, `--version C`, `--units mm`; odb `--precision 2`, `--compression zip`, `--units mm`; dxf `--output-units in`.
2. *Files.* Same names on both majors:

   | command | writes |
   |---|---|
   | `pcb export ipc2581 -o ipc/B.xml B.kicad_pcb` | one XML (1 989 684 bytes on 10.0.6, 1 639 649 on 9.0.9); `--version B` and `--units in` load; `--units inch` exits 1 with "Maximum number of positional arguments exceeded"; `--compress` writes a zip under the name given |
   | `pcb export odb -o odb/B.zip B.kicad_pcb` | one zip (147 862 / 126 562 bytes); `--compression none` writes 63 files under the folder named |
   | `pcb export step -o 3d/B.step B.kicad_pcb` | one STEP; prints `STEP file '3d/B.step' created.` and `Export time … s` |
   | `pcb export pdf --mode-separate --layers F.Cu,B.Cu,Edge.Cuts -o pdf/ B.kicad_pcb` | `pdf/B-F_Cu.pdf`, `pdf/B-B_Cu.pdf`, `pdf/B-Edge_Cuts.pdf`; `--common-layers Edge.Cuts` and `--include-border-title` load (10.0.6: 104 580 bytes without, 125 532 with both, for `F.Cu`) |
   | `pcb export dxf --mode-multi --output-units mm --layers Edge.Cuts,F.Fab,F.CrtYd -o dxf/ B.kicad_pcb` | `dxf/B-Edge_Cuts.dxf`, `dxf/B-F_Fab.dxf`, `dxf/B-F_Courtyard.dxf` |
   | `sch export pdf -o pdf/mainsheet.pdf mainsheet.kicad_sch` | one PDF of 3 pages (68 390 / 70 799 bytes) |

   `pcb export pdf --mode-multipage -o pdf/x.pdf` writes that file on 10.0.6 and a folder `pdf/x.pdf/` holding `B.pdf` on 9.0.9; with `-o pdf/`, multipage or no mode exits 2 on 10.0.6 ("Failed to create file 'pdf/'"). `pcb export dxf` without a mode prints on 10.0.6 that its behaviour "will change in a future release" to match `--mode-multi`. Without `-o`, 10.0.6 writes `B.xml`, `B-odb.zip` and `B.step` next to the board. Every 10.0.6 run also writes `B.kicad_prl`; 9.0.9 writes none. No output holds the user's name or a temporary path; a PDF's `/Title` is its file name.
3. *Time and size on 10.0.6* (one machine, shared with other runs; read the times as ±50 %):

   | kind | 100 parts | 400 parts | 600 parts |
   |---|---|---|---|
   | `ipc2581` | 4.3 to 6.0 s, 2.0 MB | 10.9 s, 7.6 MB | 18.2 s, 11.7 MB |
   | `odb` (zip) | 0.8 to 1.0 s, 0.15 MB | 3.5 s, 0.51 MB | 4.0 s, 0.77 MB |
   | `step`, with models | 7.1 to 17.4 s, 5.0 MB | 11.0 s, 5.3 MB | 10.0 s, 5.4 MB |
   | `pdf`, four copper layers and the outline | — | 1.9 s, 1.3 MB | 2.4 s, 1.9 MB |
   | `dxf`, three layers | 1.3 s, 0.8 MB | 1.5 s, 3.8 MB | 2.0 s, 5.9 MB |

   The STEP's time follows the number of distinct models (9 here), not the number of parts: `--board-only` takes 1.4 s. `sch export pdf` of the 15-sheet demo: 4.0 s, 4.4 MB, 15 pages. In the emulated 9.0.9 image each run on 100 parts takes 1 to 10 s.
4. *Two runs of one board* (three on 10.0.6, two on 9.0.9):
   - DXF: byte-equal on both.
   - Board and schematic PDF: only the line `/CreationDate (D:…)` differs, on both (10.0.6 writes `D:2026:10:05:21:44:59`, 9.0.9 `D:20261005135825`).
   - STEP: besides the `FILE_NAME(` line (date and output name), entity numbers and colour entities differ, on both; the two files are not equal even as sets of lines.
   - IPC-2581: the lines `<HistoryRecord … origination="…" … lastChange="…">` and `<AvlHeader … datetime="…"/>` hold the date. On 9.0.9 the runs are equal without them. On 10.0.6 they are not: five points of one contour differ (`y="2.725071"` against `y="2.7250"`), and lines change order.
   - ODB++ written as a folder: on 9.0.9, 61 of 63 files are byte-equal and `misc/info` (`CREATION_DATE=`, `SAVE_DATE=`) and `steps/pcb/eda/data` (`# <date>`) differ in those lines only; on 10.0.6, 55 of 63 files are byte-equal: `misc/info` and `steps/pcb/eda/data` differ in their dates (and the second in line order), and six front-layer `features` files in line order, five of them in content too. The zip differs on every run.
5. *3D models in the STEP.*
   - With the runner's environment, 10.0.6 takes the models from its application's `3dmodels` folder (3.1 GB in the macOS install): 5 027 847 bytes. Paths rewritten to `${KICAD9_3DMODEL_DIR}` are found there too.
   - `KICAD10_3DMODEL_DIR` naming an empty folder: exit 0, 42 098 bytes (the board alone), and for each of the 100 footprints `Could not add 3D model for <ref>.` and `File not found: ${KICAD10_3DMODEL_DIR}/<rel>` on standard output.
   - The variable naming a folder that holds only the 9 files (2.4 MB), as a path relative to the run folder or as an absolute path: the same STEP. Paths rewritten to `${KIPRJMOD}/3dmodels/<rel>`, with the files in the run: the same STEP.
   - 9.0.9: the image has no `/usr/share/kicad/3dmodels`; the target-9 build gives 42 098 bytes and the same two lines per footprint. With `KICAD9_3DMODEL_DIR` naming the 9 files (absolute or relative): 3 856 496 bytes and 100 `NEXT_ASSEMBLY_USAGE_OCCURRENCE` entries named after the references. With `KICAD10_3DMODEL_DIR` only: the board alone.
   - A STEP that 10.0.6 wrote with `--board-only` for one of our boards, named as the model of every footprint: 100 bodies, 145 679 bytes.
   - A `.wrl` path: with only its `.step` sibling present, no body with or without `--subst-models`; with both files, `--subst-models` takes the `.step` (exit 0, 100 bodies), and without it the run exits 2 with the board alone.
   - `--no-dnp` and `--no-unspecified` change nothing on this board. With no origin option, the board lies at the file's coordinates with y negated: an outline from (100, 100) to (176, 192) mm gives points from x 0 to 176 mm and y −192 to 0 mm.
6. *Schematic PDF with a missing sheet.* Without `subsheet2.kicad_sch`, or without both sub-sheets, the PDF still has 3 pages, the command prints `Plotted to '…'` and `Done.` and exits 0, on 10.0.6 (59 793 and 54 299 bytes instead of 68 382) and on 9.0.9 (60 398 instead of 70 791). Without the project file the PDF is 2 bytes longer and no `.kicad_prl` is written. `sch.sheet_files` walks the 15-sheet demo in 2.4 s with no issue.
7. *Page of a board PDF.* The 600-part board has an outline of 158 × 179 mm from (100, 100) mm and the paper A4. `pcb export pdf --mode-separate --layers Edge.Cuts` gives `/MediaBox [0 0 841.896 595.296]`, A4 landscape, with and without `--include-border-title`, although the outline reaches 279 mm on a page 210 mm high.

**Constraints.** Stdlib only; integers in the model; the files are KiCad's and never edited; no download in tests; GPL tools only as subprocesses.

## Goals / Non-Goals

**Goals:**
- `export` writes the six documents of the review's package that `kicad-cli` already makes, on a copy, with `--confirm`, on both majors; BOM and placement tables stay c0064's, drawings c0117's.
- A STEP holds exactly the models Fenolite reports, from sources a user can see and control, and a missing body never passes silently.
- A schematic PDF never hides an empty page.
- The manifest and the result say which hashes can be compared between two exports.

**Non-Goals:**
- Everything under "Non-goals" in the proposal.
- Options and file sets of the four kinds of c0024: the living "Export presets" (c0074).

## Decisions

1. **Six kinds, one argument list each, the same on both majors.**

   | kind | flag | arguments after the words | output | `repeat` |
   |---|---|---|---|---|
   | `ipc2581` | `--ipc2581` | `-o ipc2581/<stem>.xml --version C --units mm --precision 6` | one file | `none` |
   | `odb` | `--odb` | `-o odb/<stem>.zip --compression zip --units mm` | one file | `none` |
   | `step` | `--step` | `-o 3d/<stem>.step --subst-models`, with the model files and variables of Decision 8 | one file | `none` |
   | `pdf` | `--pdf` | `-o pdf/ --mode-separate --layers <pdf_layers> --common-layers Edge.Cuts --include-border-title` | one file per layer | `content` |
   | `dxf` | `--dxf` | `-o dxf/ --mode-multi --output-units mm --layers <dxf_layers>` | one file per layer | `bytes` |
   | `sch-pdf` | `--sch-pdf` | `sch export pdf -o schematic/<stem>.pdf <stem>.kicad_sch`, with the files of Decision 12 | one file | `content` |

   - KiCad's defaults are passed explicitly where they decide the file (IPC-2581 version, units and precision; ODB++ compression and units), so a later change of default does not change the files without a probe noticing.
   - Never passed: `--check-zones`, which refills zones in the copy; `--board-plot-params`, which makes files depend on settings stored in the board; `--variant`, which exists on 10.0 only; `--drawing-sheet` and `--define-var`, which would replace what the project says.
   - Every option above exists on both majors (measurement 1), so `Kind.majors` is `(9, 10)` for all six and `export.kind-unavailable` stays for later kinds.
   - Rejected: passing `kicad-cli` options through, for c0024's reason (each option changes what a fabricator receives, unchecked). Rejected: preset tables for the new kinds now: "Export presets" maps each key to a flag that `H-K-EXPORT-OPTIONS` proves on both majors, for `gerbers`, `drill` and `pos`; tables for the new kinds need their own option probes and are a follow-up. `run_kind` therefore never calls the preset callback `args` for a document kind, and `export --preset` with a document kind runs that kind with its fixed list.

2. **Board PDF: one file per layer, with the outline and the title block.** `pdf_layers(design)` is `gerber_layers(design)` with `F.Fab` and `B.Fab`, where the board has them, before `Edge.Cuts`; every page also carries `Edge.Cuts` and the drawing sheet's frame. Each file is an artefact with its layer, found as for Gerbers. Rejected: `--mode-multipage`: its `-o` names a file on 10.0.6 and a folder on 9.0.9 (measurement 2). Rejected: a composite page of several layers: that is a drawing, c0117's, which passes its own list through `run_kind(…, layers=…)`.

3. **DXF: one file per layer, in millimetres.** `dxf_layers(design)` is `Edge.Cuts`, then `F.Fab`, `B.Fab`, `F.CrtYd` and `B.CrtYd` where present: the outline and the bodies' footprints that an enclosure designer draws against. Coordinates are the board file's. Rejected: no mode flag (a notice on every 10.0.6 run that the behaviour will change). Rejected: `--use-drill-origin` (built boards set no drill origin, and nothing was measured with one) and `--use-contours` (a mechanical drawing wants centre lines).

4. **STEP: board body and component bodies, KiCad's origin.** No copper option is passed, and no origin option, so the STEP is placed in the board file's coordinates with y negated (measurement 5); `docs/exports.md` states it. `--subst-models` is always passed, because a `.wrl` path then gives its STEP sibling instead of failing the run (measurement 5). Rejected: `--user-origin` at the script's board origin: a board Fenolite did not build has no such origin, and one rule for every board is easier to hand to an enclosure designer. Rejected: tracks and zones in the STEP: an enclosure check needs bodies, and copper adds size and time.

5. **IPC-2581 and ODB++ as one file each.** ODB++ as a zip, because a fabricator receives one archive; IPC-2581 uncompressed. Rejected: `--compression none` (63 artefacts per four-layer board in the manifest). Rejected: IPC-2581 `--compress` (a zip under the `.xml` name unless renamed, and nothing gained in repeatability). No BOM column option is passed: which footprint field holds a part number is the user's to say, through a later preset.

6. **`--all` keeps the four kinds of c0024.** The document kinds are selected one by one. Rejected: `--all` selecting the ten kinds: every existing `--all` call, the agent guide and the oracle tests would gain a STEP of 7 to 17 s and need a schematic.

7. **Repeatability per kind, and what `content_sha256` means.** `Kind.repeat` is the weakest class measured over both majors (measurement 4): `bytes` (two runs are byte-equal: `pos`, `ipcd356`, `dxf`), `content` (they differ only in date-bearing lines, which `VOLATILE_PREFIXES` removes: `gerbers`, `drill`, `pdf`, `sch-pdf`), `none` (`ipc2581`, `odb`, `step`). The prefix of `pdf` and `sch-pdf` is `/CreationDate`. A `none` kind gets no prefix, so its `content_sha256` equals its `sha256`, and `docs/exports.md` says that neither hash of it tells whether the board changed. `result.repeat` gives the class of each selected kind; `Artifact.repeatable` stays "byte-equal", true exactly for `bytes`.
   - Rejected: a normal form for STEP (entity numbers shift), ODB++ (zip member times, and front layers vary on 10.0.6) or IPC-2581 (contour points vary on 10.0.6): it would claim an equality that the files do not have.
   - Rejected: a field per manifest entry: the class is a property of the kind, not of a file, so it is given in the result and the documentation, and "Artefact manifest" gains no field.

8. **Fenolite locates the models and gives them to the run.** For `step`, `models.board_models(text)` reads every `(model "<path>" …)` of every footprint with its reference; each distinct path is located once by `LibraryResolver.locate_model(path)`, which tries in order:
   - `project`: `<board folder>/3dmodels/<rel>` for `${KICAD<N>_3DMODEL_DIR}/<rel>` (the copies of Decision 10), or `<board folder>/<rel>` for `${KIPRJMOD}/<rel>`;
   - `env`, then `kicad-config`: the variable in the caller's environment, then in KiCad's `kicad_common.json` of major N, joined with `<rel>`;
   - `install`: the `3dmodels` folder of the KiCad install the resolver finds, for any N, as 10.0.6 itself does (measurement 5);
   - `cache`: `<cache>/<tag>/kicad-packages3D/<rel>` for the pinned tag of major N, when the file's SHA-256 equals its stamp entry (Decision 11).
   - Any other form (an absolute path, another variable) is left as written, reported with the source `in-place`, and read by `kicad-cli` where it is.

   `models.plan_models(refs, resolver)` puts each located file into the run as `3dmodels/<rel>` (or `<rel>` for `${KIPRJMOD}`), and sets `KICAD<N>_3DMODEL_DIR=3dmodels` for every N that a path names, also when none of its paths was located, so `kicad-cli` never falls back on its own install: the STEP holds exactly what the result reports. A `.wrl` path brings its `.step` and `.stp` siblings from the same source.
   - Why: the runner removes `KICAD*` variables and KiCad's configuration, so a model folder the user set never reaches `kicad-cli`; the 9.0.9 image has no model at all; and a missing model exits 0 (measurement 5).
   - Rejected: leaving resolution to `kicad-cli`: the STEP would depend on the machine, and a lost body would be silent. Rejected: passing the variables as absolute host paths: a Docker run cannot see them, while a value relative to the run folder works on both majors.
   - "Library sources" is not modified: `locate_model` defines no variable, so the rule that a cache source defines no `KICAD<M>_3DMODEL_DIR` still holds for library rows.

9. **A missing model is a warning; the STEP is still written.** Each path that is not located gives one `kicad.lib.missing-3d-model` (warning) naming the path and its references, the code that `missing_models` already uses. After the run, a `Could not add 3D model for <ref>.` line for a reference whose models were all located gives `export.model-unread` (warning): Fenolite gave the file and KiCad could not use it. `result.models` lists every path with `source`, `sha256`, `bytes` and `refs`. Rejected: an error: a library model that is absent on one machine is not a board defect, and the warning names the fix. Rejected: reading bodies out of the STEP: the output line already names the reference.

10. **Vendoring is a command, not a build step.** `fenolite models PATH` lists the models of a board, where each was found and its SHA-256, and runs no tool. With `--vendor` it plans one copy per located `${KICAD<N>_3DMODEL_DIR}/<rel>` whose source is not the project, at `<board folder>/3dmodels/<rel>`. Footprints and board keep their paths, so later exports take these copies first (Decision 8), on any machine and in any image. KiCad itself reads them only if the user points `KICAD<N>_3DMODEL_DIR` at the folder; `docs/exports.md` says so.
    - Rejected: vendoring in `build`: it would modify "Build command", "Built project files" and "Footprints of every row origin are vendored", and every build would copy megabytes nobody asked for. It would also ask what an Altium build does with a KiCad model folder; a command on a KiCad board asks nothing of the second backend.
    - Rejected: rewriting model paths to `${KIPRJMOD}/3dmodels/…`: KiCad reads such paths (measurement 5), but the vendored footprint would no longer equal its library byte for byte, which is the vendoring rule of the build.

11. **Fetch one file at a time.** `libraries.toml` gains one `[[models]]` pin per tag (`tag`, `major`, `project` `kicad/libraries/kicad-packages3D`, `commit` from the tags API). `tools/kicad_libs_fetch.py --models PATH…` reads the model paths that boards or footprint files name, asks GitLab's files API (`HEAD …/repository/files/<rel>?ref=<commit>`) for `X-Gitlab-Size` and `X-Gitlab-Content-Sha256`, as the corpus fetch already reads them for demo files (S-0024), downloads the raw file, checks both, writes it with `os.replace` and records it in `.fenolite-models.json`. Rejected: the whole repository archive: one install already holds 3.1 GB of models, beyond the tool's 1 GiB archive and 4 GiB tree limits. Rejected: pinning each model's digest in the repository: the set depends on the user's board. Rejected: a download by `fenolite` itself: c0078 owns user-facing downloads and their decision record. The tests never fetch: they use an authored model (task 1.2).

12. **Schematic PDF: the whole hierarchy or nothing.** The schematic is `<stem>.kicad_sch` beside the board, as `bom --source kicad` finds it; without it, `--sch-pdf` exits 3 before any run. The run gets the copy set of `project_set(board)`, whose "Schematic" clause already holds the root, the sheet files that `sch.sheet_files` lists inside the board's folder, the project file, the symbol table with its libraries and the schematic's drawing sheet; `documents.schematic_files` plans no second set and only reports the walk. A sheet reported missing, outside the folder or in a cycle, or skipped by the copy set as `too-large`, gives `export.sheet-missing` (error) and no run. Rejected: counting pages after the run: KiCad gives the page anyway (measurement 6). Rejected: a warning: the PDF would be handed over with an empty page.

13. **A board PDF that does not fit its page gives a warning.** `documents.page_check(design)` compares the outline's bounding box (`outline.board_outline`) with the page of `Board.sheet` (`PAPER_SIZES`, landscape unless portrait) and gives `export.page-too-small` (warning) naming both sizes; the files are written. Rejected: `--scale 0` (10.0 only). Rejected: choosing the paper here: the paper is the design's (`Design.sheet(paper=…)`, `dsl/design.py:364`).

14. **Help matrix rows.** `MATRIX` gains `pcb export step`, `pdf` and `dxf` and `sch export pdf`, recorded as `check-help-*` probes, so `doctor` says per major what `export` can run. Rejected: proving the commands only through the export probes: `doctor` would still not tell an agent what the installed major offers before an export fails.

15. **Evidence per kind.** `exports.DOCUMENTS_EVIDENCE` is `INFERRED` (`H-K-EXPORT-DOCS`, `H-K-EXPORT-DOCS-REPEAT`, `H-K-EXPORT-MODELS`, `H-K-EXPORT-SHEETS`) until the four hold on both majors. An export that selects a document kind carries `Evidence.combine` of the selected kinds' evidence, and each manifest entry the level of its kind; the clause of "Artefact manifest" that lowers a fabrication file's level under a preset stays, and no preset reaches a document kind. `models.EVIDENCE` is `INFERRED` (`H-K-EXPORT-MODELS`). Rejected: `exports.EVIDENCE` for every kind: it would label as `KICAD-VERIFIED` files no probe has seen yet.

16. **Other changes that hold the same requirements** (checked 2026-10-07 on `origin/dev` at `9aba2dff`, and against the review of the 26 proposals of v0.4).
    - "Export command" (`cli-contract`): the living text has `--preset` (c0074, archived); c0084, open on `dev` and part of `0.3.0`, holds a MODIFIED delta that adds `--altium-rul`. **c0084 lands first.** This change's delta is c0084's text with only the six flags, the "Schematic" clause, the document sentences of "Kinds", "Preset", "Tool" and "Source", the result keys `repeat` and `models`, the codes and five scenarios. If c0084's text changes before it is archived, task 0.1 regenerates the delta from the living text. c0117 adds a requirement beside this one ("Drawing options of the export command") and does not modify it. Order: c0084, c0116, c0117.
    - "Artefact states" (`manufacturing-exports`): four proposals of v0.4 add derived kinds to its list: this one (six kinds, and the design kind `3d-model`), c0117 (two), c0118 (`testpoints`) and c0105 (the impedance table). **Order: c0116, c0117, c0118, c0105.** Each delta is the living text of `9aba2dff` with only its own kinds; whoever lands later regenerates from the living text of that day. No open change on `dev` holds a delta of it.
    - "Manifest option of producing commands" (`cli-contract`): modified here (`layer` of `pdf` and `dxf` files, `from` of `sch-pdf`, the evidence per kind) and by c0118 (`testpoints --manifest`). This change first; c0118 regenerates. No open change on `dev` holds a delta of it.
    - "Artefact manifest" and "Project manifest" (`manufacturing-exports`): modified here only (the PDF prefix and the evidence of a document kind; the files below `3dmodels/`). No open change on `dev` and no other proposal of v0.4 holds a delta of either.
    - "Export kinds and their arguments", "Export evidence", "Missing 3D models are warnings" and "Subcommand matrix from help text": the living text is the text these deltas were written on, and no open change holds a delta of any.
    - c0084 also adds the artefact kind `altium-rul` (its own requirement "Altium rule file export"). It is neither a fabrication nor a document kind: `--all` selects neither, `result.repeat` does not list it, and this change leaves its manifest entry as c0084 defines it.
    - Archived since this proposal was written, so no longer "in flight": c0060 (`sch.sheet_files`), c0061 (built schematic), c0062 (copy set with the schematic), c0064, c0065 (manifest states), c0066 (paged results), c0074 (presets). Every "if archived" branch on them is gone from the tasks.
    - c0101 (stack-up): IPC-2581 states the stack-up's thickness; nothing here writes a stack-up. c0112 (via protection): its coating and hole-fill layers reach IPC-2581 through the `ipc2581` kind on 10.0.6; its drill side files come from the preset key `[drill] format = "gerber"`, and `--generate-tenting` (10.0 only) is offered by neither. c0105 writes the impedance table with its own `impedance --out` and adds its manifest kind after this change. c0117 builds drawings on `run_kind(…, layers=…)`. c0120 (staged plans): until `--confirm` writes the reviewed plan, the hashes of `none` kinds in a `--dry-run` differ from those written; c0141 (DRC report limits) does not touch `export`.

17. **The second backend.** `dev` writes Altium documents (c0084, c0085, c0086, c0088), so the question "what does an Altium project get" has an answer for every part of this change:
    - `export` and `models` take a KiCad board. `resolve_board` accepts a `.kicad_pcb`, a `.kicad_pro` or a folder holding them; a `.PcbDoc`, a `.PrjPcb` or a folder of an Altium build is refused with exit 2 (`FEN-2001`) before any tool is looked for, exactly as the four kinds are refused today. The six document kinds add no rule and no exception.
    - Why not convert: the six files are written by `kicad-cli` from a KiCad board. Lowering an Altium board to KiCad to export it is conversion (v0.5a), and its result would be labelled as a document of a board the user never saw.
    - What an Altium project has instead: the output job that `build --target altium` writes (c0087; c0138 completes its Gerber settings), which Altium runs.
    - `--altium-rul` (c0084) stays what it is, a rule file made from a KiCad project's rules with no tool; it is untouched by the six flags.
    - 3D models: an Altium build embeds no model file and writes extruded bodies on request (c0121). `fenolite models` lists the `(model …)` paths of a KiCad board and has nothing to list for a `.PcbDoc`.
    - No rule kind, selector or model field is added, so no row of the Altium rule table (c0084) and no lowering changes.

## Files and public API

| file | content |
|---|---|
| `src/fenolite/exports/plan.py` | six `Kind` rows; `Kind.repeat: Literal["bytes", "content", "none"]`, `Kind.source: Literal["board", "schematic"]`; `FAB_KINDS`, `DOCUMENT_KINDS`; `pdf_layers(design)`, `dxf_layers(design)`; `run_kind(…, layers=None, models=None)`; `KindResult.models`; `SHOWN_NAMES` gains the courtyard and adhesive names; `VOLATILE_PREFIXES` for `pdf` and `sch-pdf` |
| `src/fenolite/exports/documents.py` (new) | `schematic_files(board) -> SchematicFiles(root, files, issues)`; `page_check(design) -> Issue \| None` |
| `src/fenolite/exports/codes.py`, `__init__.py` | `export.sheet-missing`, `export.model-unread`, `export.page-too-small`; `DOCUMENTS_EVIDENCE` |
| `src/fenolite/exports/manifest.py`, `states.py` | the evidence level per kind in `entry()`; `design_kind` gives `3d-model` below `3dmodels/`; `states.DERIVED` gains the six kinds, and `3d-model` stops at `checked` |
| `src/fenolite/backends/kicad/models.py` (new) | `MODEL_FOLDER = "3dmodels"`; `ModelRef(ref, path)`; `board_models(text)`; `ModelUse(path, source, sha256, bytes, refs)`; `ModelPlan(files, env, uses, issues)`; `plan_models(refs, resolver)`; `unread_refs(stdout)`; `EVIDENCE` |
| `src/fenolite/backends/kicad/libs.py` | `ModelLocation(path, rel, file, source)`; `LibraryResolver.locate_model(path)`; `missing_models` through it |
| `src/fenolite/backends/kicad/libcache.py`, `data/libraries.toml` | `ModelPin(tag, major, project, commit)`; `load_model_pins(path=None)`; `MODEL_REPO`, `MODEL_STAMP`; `read_model_stamp(folder)`; two `[[models]]` pins |
| `tools/kicad_libs_fetch.py` | `--models PATH…`; `MAX_MODEL_BYTES`; `head(url)` and `download(url)` replaced by the unit tests |
| `src/fenolite/backends/kicad/helpmatrix.py` | the four rows |
| `src/fenolite/cli/cmd_export.py` | six flags, `result.repeat`, `result.models`, the schematic pre-check, combined evidence |
| `src/fenolite/cli/cmd_models.py` (new) | `COMMAND` (`models`, `mutates=True`, `paged="models"`) |
| `src/fenolite/cli/cmd_manifest.py` | `design_files` lists the files below `3dmodels/` |
| `src/fenolite/cli/data/explain.toml` | rows for the three new codes |
| `tests/data/models/` (new) | `Fenolite.3dshapes/Box_2x1.step`, written by `kicad-cli pcb export step --board-only` from the authored board beside it, and its `MANIFEST.toml` rows |
| `tests/unit/exports/test_plan_documents.py`, `test_documents.py`, `tests/unit/backends/kicad/test_models.py`, `test_locate_model.py`, `test_libcache_models.py`, `tests/unit/test_libs_fetch_models.py`, `tests/unit/cli/test_models_cmd.py` (new); `tests/unit/cli/test_export_cmd.py`, `tests/unit/exports/test_manifest.py`, `tests/unit/backends/kicad/test_helpmatrix.py` (extended) | hermetic |
| `tests/kicad/export/_doccases.py`, `test_document_probes.py` (new); `tests/kicad/_probes.py`; `tests/kicad/check/test_help_matrix.py` | the probes on both majors and the loop test |
| `docs/exports.md`, `docs/cli-contract.md`, `docs/formats/kicad/cli.md`, `docs/formats/kicad/libraries.md`, `docs/evidence/kicad-export.md` | the kinds, models and `models`; the fact rows with sources and labels |

## Sources registered by this change

| id | source | licence | used for |
|---|---|---|---|
| S-0700 | https://gitlab.com/kicad/libraries/kicad-packages3D (tags `10.0.6` and `9.0.9`; tags API `https://gitlab.com/api/v4/projects/kicad%2Flibraries%2Fkicad-packages3D/repository/tags/<tag>`) | CC-BY-SA-4.0 with the library exception (S-0048); files fetched into the cache, never committed | the commits of the model pins; the files of the fetch |
| S-0701 | https://docs.gitlab.com/api/repository_files/ | to be read from the page footer by task 1.1, as for S-0096 | `HEAD` of a file (`X-Gitlab-Size`, `X-Gitlab-Content-Sha256`) and the raw endpoint |

The `kicad-cli` facts rest on S-0020, S-0022, S-0029 and S-0037, the corpus demos on S-0058; task 1.1 widens their "used for" cells, and S-0024's (the files API on another project). The ids are from the block S-0700 to S-0719 that the coordinator gave this group on 2026-10-07, because the ids this proposal first reserved (S-0460 and S-0461) are c0084's on `dev`; no other change of the group registers a source, so S-0702 to S-0719 stay free.

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-K-EXPORT-DOCS | With the arguments of Decision 1, `kicad-cli` writes on 9.0.9 and 10.0.6: `ipc2581/<stem>.xml`; `odb/<stem>.zip`; `3d/<stem>.step`; one `pdf/<stem>-<name>.pdf` and one `dxf/<stem>-<name>.dxf` per listed layer, `<name>` being the name KiCad shows with dots as underscores; `schematic/<stem>.pdf`; and nothing else under those folders; 10.0 also writes `<stem>.kicad_prl`; `pdf --mode-multipage -o X` writes the file X on 10.0.6 and `X/<stem>.pdf` on 9.0.9 (S-0020, S-0022, S-0029, S-0037) | `tests/kicad/export/test_document_probes.py::test_files` | probes `export-files-<kind>` `equal` for the six kinds on both majors |
| H-K-EXPORT-DOCS-REPEAT | Two runs on one board: DXF byte-equal; board and schematic PDF differ only in the `/CreationDate` line; STEP differs beyond its `FILE_NAME` line; ODB++ as a zip never repeats; IPC-2581 differs beyond its `HistoryRecord` and `AvlHeader` lines on 10.0.6 and only in them on 9.0.9 (S-0020, S-0029) | `::test_repeat` (three runs) | `export-repeat-dxf`, `-pdf`, `-sch-pdf` `equal` under `content_sha256` and `export-repeat-step`, `-odb` `different` on both majors; `export-repeat-ipc2581` recorded per major |
| H-K-EXPORT-MODELS | `pcb export step` takes `${KICAD<N>_3DMODEL_DIR}/<rel>` from the folder that the variable names in its environment, absolute or relative to its working folder; 9.0.9 does not read a `KICAD9_` path through `KICAD10_3DMODEL_DIR`; without the variable 10.0.6 reads its install's `3dmodels` folder for N = 9 and 10; a model not found gives `Could not add 3D model for <ref>.` and `File not found: <path>` on standard output and exit 0; with `--subst-models` a `.wrl` path whose file is found gives its `.step` sibling, and without the `.wrl` file nothing is substituted (S-0020, S-0029) | `::test_models` | `export-models-var`, `export-models-missing` and `export-models-subst` `equal` on both majors; `export-models-install` recorded on 10.0.6 |
| H-K-EXPORT-SHEETS | `sch export pdf` plots one page per sheet instance, and a sheet whose file is missing still gives its page, with exit 0 and no message (S-0020, S-0029) | `::test_sheets` | `export-sheets-missing` `present` on both majors |
| H-K-EXPORT-PDF-PAGE | The page of `pcb export pdf` is the board's paper whatever the extent of the board (S-0020) | `::test_page` | `export-pdf-page` `equal` on 10.0.6, recorded on 9.0.9 |
| H-G-MODELS-FETCH | For a file of `kicad-packages3D` at a pinned commit, `HEAD …/repository/files/<path>?ref=<commit>` gives `X-Gitlab-Size` and `X-Gitlab-Content-Sha256`, and the raw file has that size and SHA-256 (S-0024, S-0700, S-0701) | task 6.3, with the maintainer's consent | the fetch of `examples/blink_official`'s models exits 0 with every file `fetched`, and the run is recorded in `docs/evidence/kicad-libs.md` |

The five `H-K-*` rows start `INFERRED` with the measurements of "Context" as their first record; `H-G-MODELS-FETCH` starts `INFERRED` with none. Cited without a change of level: `H-K-EXPORT-FILES`, `H-K-EXPORT-REPEAT`, `H-K-CLI-HELP`, `H-K-CHECK-COPYSET`, `H-K-PRO-PRL`, `H-K-LIB-COMMON`.

## Evidence level per behaviour (before merge)

| behaviour | level required | proof |
|---|---|---|
| file sets of the six kinds | KICAD-VERIFIED (9.0.x, 10.0.x) | `export-files-*` |
| repeat classes and the PDF prefix | KICAD-VERIFIED (9.0.x, 10.0.x) | `export-repeat-*` |
| models through the run's variables, the missing-model lines, substitution | KICAD-VERIFIED (9.0.x, 10.0.x) | `export-models-*` |
| a missing sheet gives a page and exit 0 | KICAD-VERIFIED (9.0.x, 10.0.x) | `export-sheets-missing` |
| page of a board PDF | KICAD-VERIFIED (10.0.x), 9.0.x recorded | `export-pdf-page` |
| help rows | KICAD-VERIFIED (9.0.x, 10.0.x) | `check-help-pcb-export-step`, `-pdf`, `-dxf`, `check-help-sch-export-pdf` |
| plan table, model location, `models`, sheet refusal, page check, manifest kinds | mechanical | the unit tests of "Files and public API" |
| the fetch | INFERRED until task 6.3 runs | `H-G-MODELS-FETCH` |

## Risks / Trade-offs

- **A STEP without bodies is handed over.** The warning names each path and part; `fenolite models` shows the sources tried; `docs/exports.md` puts the check of `result.models` in the loop.
- **Non-repeatable kinds read as changes.** `result.repeat` and the documentation say which hashes compare; the content hash of a `none` kind equals its byte hash, so it claims nothing more.
- **A model that Fenolite and KiCad find in different places.** Fenolite sets every model variable of the run, so KiCad sees only what Fenolite located; the result lists each file's SHA-256.
- **Copied models make runs larger.** 2.4 MB for 9 models here, one copy per distinct path and per run; the files are read, never changed.
- **A later 10.0.x changes a file name, a date line or the repeat class.** Every fact is a probe pinned per version; the test fails before the table drifts.
- **Shared requirements.** "Export command" is written on c0084's open delta, and "Artefact states" and "Manifest option of producing commands" are modified again by c0117, c0118 and c0105. The order is fixed in Decision 16, and task 0.1 regenerates every MODIFIED delta from the living text of the day.
- **The 9.0.9 image has no models.** Its oracle test takes the authored model; the official models need the fetch, which needs consent once.
- **Vendored models diverge from the install.** The copies are what the project exports with; `fenolite models` shows the source of each, and deleting `3dmodels/` returns to the install.

## Migration Plan

- Additive: six flags, three issue codes, a command, a tool option, two result keys of `export` (`repeat`, `models`), two pins in a new table of `libraries.toml`. `--all` and the four kinds write the same files.
- The manifest of an export with the new kinds holds entries of new kinds; a manifest without them reads as before.
- `missing_models` now also finds a model in the project's `3dmodels/` folder and in a fetched cache, so it can report fewer warnings than before.
- Rollback: remove the kinds and the command; vendored `3dmodels/` folders stay as plain files.

## Budget (6.25 days)

| part | days |
|---|---|
| 1. registers, authored model, probes on 10.0.6, the 9.0.9 run, fact rows | 1.0 |
| 2. kinds: plan table, layer lists, repeat classes, prefix, evidence, page check | 0.75 |
| 3. schematic PDF: sheet files and refusal | 0.5 |
| 4. 3D models: `locate_model`, `board_models`, run files and variables, cross-check | 1.0 |
| 5. `export` flags and result; `models` command with `--vendor` | 1.0 |
| 6. model pins and fetch | 0.75 |
| 7. help rows, manifest kinds | 0.5 |
| 8. loop test on both majors, documentation, closing | 0.75 |
| **total** | **6.25** |

Cut order: (1) the fetch (part 6): tests use the authored model, and users read models from their install or their own variable; (2) `--vendor` of `models` (keep the listing); (3) the page check; (4) the design kind `3d-model` of the project manifest (the derived kinds stay: without them a manifest could not hold the files). Never cut: the six kinds with their probes on both majors, model location for the STEP, the sheet refusal.

## Open Questions

- **Should a missing model fail the export?** Default: warning (Decision 9). A `--require-models` flag can follow if agents ignore the warning.
- **`from` of a schematic PDF names only the root sheet**, so an edit of a sub-sheet does not mark it stale. Default: the root, because "Artefact states" knows the sources `board` and `schematic` only; a digest over the hierarchy would change that requirement for every schematic-derived kind and is left to a change of its own.
- **ODB++ as a folder** would give 61 comparable files on 9.0.9. Default: zip, as fabricators receive it.
- **Layer lists of `pdf` and `dxf` as options before presets?** Default: no; c0117 passes its own through `layers=`.
- **Should `models --vendor` record hashes in `.fenolite/`?** Default: no; `fenolite manifest` lists the files with their hashes, as design files of kind `3d-model`.
- **Should built boards pass `--user-origin` at the script's origin?** Default: no (Decision 4).
