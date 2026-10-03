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
