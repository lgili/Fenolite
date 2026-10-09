# `fenolite export` and `render` on kicad-cli 9.0.9 and 10.0.6

Counts and outcomes only (change c0024, task 2.2). Measured on 2026-10-03 by
`tests/kicad/export/test_export_probes.py` with kicad-cli 10.0.6 (macOS) and 9.0.9 (the pinned image, no
display), on `tests/data/kicad/board/two_layer.kicad_pcb` and on the authored project of the running major.
Every run happened on a copy in a temporary folder; no exported file is kept.

| probe | 9.0.9 | 10.0.6 |
|---|---|---|
| `export-files-gerbers` | `equal` | `equal` |
| `export-files-drill` | `equal` | `equal` |
| `export-files-pos` | `equal` | `equal` |
| `export-files-ipcd356` | `equal` | `equal` |
| `export-repeat-gerbers` | `equal` | `equal` |
| `export-repeat-drill` | `equal` | `equal` |
| `export-repeat-pos` | `equal` | `equal` |
| `export-repeat-ipcd356` | `equal` | `equal` |
| `export-render-svg` | `present` | `present` |
| `export-render-png` | `present` | `present` |

**Files.** For the two-copper fixture: nine Gerber files (`F_Cu`, `B_Cu`, `F_Mask`, `B_Mask`, `F_Paste`,
`B_Paste`, `F_Silkscreen`, `B_Silkscreen`, `Edge_Cuts`) and the job file; two drill files; one position
file; one netlist. The names are the same on both majors. 10.0.6 also writes `<stem>.kicad_prl` next to
the board copy; 9.0.9 does not. Both majors create a missing output folder.

**Byte equality of two runs, per kind.**

| kind | byte-equal | lines that differ |
|---|---|---|
| `gerbers` | no | `%TF.CreationDate`, `G04 Created by KiCad`; in the job file, `"CreationDate":` |
| `drill` | no | `; DRILL file`, `; #@! TF.CreationDate` |
| `pos` | yes | none |
| `ipcd356` | yes | none |

No other line differed on either major, so the date-stripped hash (`content_sha256`) is equal for every
file of two exports.

**Renders.** `pcb render --width 400 --height 300` wrote a PNG of 368 × 280 on both majors, and was
byte-equal across two runs on 10.0.6. The SVG of 9.0.9 carries a date in its `<title>`; a view is not a
manifest artefact, and the `render` stage of `check` hashes an SVG without that line, so that two checks
of one project give the same output (found by `test_deterministic` on 9.0.9).

**Differences from the proposal-time observation.** The Gerber job file was not listed; it is an
artefact of kind `gerbers` with no layer. KiCad names a Gerber after the layer name it shows
(`F_Silkscreen`), not the canonical one (`F.SilkS`). A rendered PNG is at most the requested size, not
exactly it. The design and the specs of c0024 were corrected before the code relied on them.

## Document kinds (change c0116)

Counts and outcomes only. Measured on 2026-10-07 by `tests/kicad/export/test_document_probes.py` with the
local kicad-cli 10.0.6 (macOS), on the four-copper created board, the authored project of the running
major, the authored two-sheet hierarchy, a two-copper bench whose two footprints name the authored model
`tests/data/models/Fenolite.3dshapes/Box_2x1.step`, and a bench whose outline leaves its A4 paper. Every
run happened on a copy in a temporary folder; no exported file is kept. **9.0.9: not run** (no container
run on 2026-10-07); the column waits for the pinned image, and until then the rows of `docs/hypotheses.md`
stay `INFERRED`. The measurements of 2026-10-05 on both majors (larger boards of official footprints,
none committed) are in the design of the change and in the hypothesis rows.

| probe | 9.0.9 | 10.0.6 |
|---|---|---|
| `export-files-ipc2581` | not run | `equal` |
| `export-files-odb` | not run | `equal` |
| `export-files-step` | not run | `equal` |
| `export-files-pdf` | not run | `equal` |
| `export-files-dxf` | not run | `equal` |
| `export-files-sch-pdf` | not run | `equal` |
| `export-repeat-ipc2581` | not run | `different` |
| `export-repeat-odb` | not run | `different` |
| `export-repeat-step` | not run | `different` |
| `export-repeat-pdf` | not run | `equal` |
| `export-repeat-dxf` | not run | `equal` |
| `export-repeat-sch-pdf` | not run | `equal` |
| `export-models-var` | not run | `equal` |
| `export-models-missing` | not run | `equal` |
| `export-models-subst` | not run | `equal` |
| `export-sheets-missing` | not run | `present` |
| `export-pdf-page` | not run | `equal` |

**Files (10.0.6).** For the four-copper created board: one IPC-2581 file (26 901 bytes), one ODB++ zip
(19 997 bytes), one STEP (8 836 bytes, the board alone), 13 PDF files (four copper layers, both masks,
pastes and silkscreens, `F_Fab`, `B_Fab`, `Edge_Cuts`) and 5 DXF files (`Edge_Cuts`, `F_Fab`, `B_Fab`,
`F_Courtyard`, `B_Courtyard`). For the hierarchy: one schematic PDF of 2 pages. Every run also wrote
`<stem>.kicad_prl` next to the copy.

**Byte equality of three runs, more than a second apart (10.0.6).**

| kind | byte-equal | `content_sha256` equal | `Kind.repeat` |
|---|---|---|---|
| `ipc2581` | no | no | `none` |
| `odb` | no | no | `none` |
| `step` | no | no | `none` |
| `pdf` | no | yes: only `/CreationDate` differs | `content` |
| `dxf` | yes | yes | `bytes` |
| `sch-pdf` | no | yes: only `/CreationDate` differs | `content` |

`Kind.repeat` is the weakest class over both majors. It rests on this table for 10.0.6 and, for 9.0.9, on
the measurements of 2026-10-05, in which no kind was in a stronger class on 9.0.9 than on 10.0.6 except
IPC-2581 without its date lines, which Fenolite does not use.

**Models (10.0.6).** With `KICAD10_3DMODEL_DIR=3dmodels` and the authored box in the run: a STEP of
19 822 bytes with one assembly occurrence for each of the two footprints. With a folder that lacks the
model: exit 0, two lines per footprint (`Could not add 3D model for <ref>.`, `File not found: <path>`) and
a STEP of 8 821 bytes. A `.wrl` path with its `.step` sibling present: both bodies; with the sibling alone:
no body and the same two lines. With no model variable, on a macOS install, a footprint naming an official
model got its body for a `KICAD9_` and a `KICAD10_` path (`test_models_install`, which skips on a machine
without an install and is not a pinned probe).

**Sheets and page (10.0.6).** The two-sheet hierarchy gives a PDF of 2 pages with its child sheet (41 321
bytes) and without it (37 676 bytes), exit 0, and only `Plotted to '…'` and `Done.` printed. An outline of
158 × 179 mm from (100, 100) mm on A4 gives `/MediaBox [0 0 841.896 595.296]`.

**Loops (10.0.6).** `fenolite export --ipc2581 --odb --step --pdf --dxf --sch-pdf --manifest --confirm` on
the authored project with the hierarchy and the model wrote every file of the manifest and left the
project folder unchanged; the built blink gave its board PDFs and its schematic PDF; and the STEP of
`examples/blink_official` took its official models from the local install.
