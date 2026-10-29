# Import census: the KiCad 10.0.6 demo boards as code

The record of `H-G-IMPORT-CODE` on public boards (change c0275, task 4.3; capability board-to-code): each
KiCad 10.0.6 demo board of the corpus (S-0058, the rows `kicad-demo-10-0-6-pcb-01` to `-18` of
`tests/corpus/manifest.toml`, all `CC-BY-SA-4.0`) is imported with `fenolite import BOARD --to python
--out out --allow-lossy --dry-run` in a temporary folder. The import builds the emitted code and compares
the built board with the source at equivalence levels 1 to 5 and copper item by item, under the profile
`import` (absolute frame, no tolerance). Nothing converted is kept, and this page holds counts only: no
content of a board is written here (corpus-policy, "Converted code stays out of the tool repository"). The
corpus holds the boards without their project files, so each is read alone.

`tests/corpus/test_import_corpus.py` imports each board and fails when it does not come through equivalent
or when the kinds it leaves out differ from its row below. Regenerate the table by running the census and
copying its rows; never edit a count by hand. The two heavy boards (rows 06 and 18) run only with
`FENOLITE_HEAVY=1` and are not measured here.

What the label means: `CORPUS-VERIFIED` here says that the code Fenolite writes for each board rebuilds a
board equal to the source at levels 1 to 5 and copper item by item, once the kinds of the last column are
left out. It says nothing about the drawn schematic (c0276) or about what the levels do not compare
(field positions, zone fills, presentation).

Measured on 2026-10-29 on `cac/c0275-board-to-code` (local run, Linux, 4 CPUs shared).

<!-- import-corpus:begin -->
| row | board | left out (kind count) | parts | tracks | arcs | vias | zones | equivalent | seconds |
|---|---|---|---|---|---|---|---|---|---|
| 01 | `CM5_MINIMA_3.kicad_pcb` | dnp 2, drawing 7, drawing-layer 4, footprint-ref 1, generated 15, group 4, pad-net-conflict 2, text 18, zone-setting 4 | 111 | 1884 | 200 | 444 | 13 | yes | 34 |
| 02 | `complex_hierarchy.kicad_pcb` | teardrop 165, text-layer 2 | 68 | 364 | 0 | 0 | 1 | yes | 10 |
| 03 | `ecc83-pp.kicad_pcb` | none | 15 | 59 | 0 | 0 | 1 | yes | 2 |
| 04 | `ecc83-pp_v2.kicad_pcb` | none | 15 | 53 | 0 | 0 | 1 | yes | 2 |
| 05 | `interf_u.kicad_pcb` | dimension 2, text 2, text-layer 6 | 25 | 731 | 0 | 84 | 1 | yes | 6 |
| 07 | `kit-dev-coldfire-xilinx_5213.kicad_pcb` | stackup-field 2, text-layer 5 | 160 | 2935 | 0 | 253 | 3 | yes | 42 |
| 08 | `microwave.kicad_pcb` | duplicate-ref 3 | 1 | 0 | 0 | 0 | 0 | yes | 0 |
| 09 | `multichannel_mixer-unrouted.kicad_pcb` | group 4, rule-area-name 4, text 2 | 114 | 140 | 0 | 19 | 1 | yes | 21 |
| 10 | `multichannel_mixer.kicad_pcb` | group 4, rule-area-name 4, text 1 | 114 | 576 | 0 | 29 | 2 | yes | 22 |
| 11 | `One-Air-Max.kicad_pcb` | copper-drawing 2, dnp 11, drawing 16, footprint-ref 6, generated 2, group 1, net-tie 2, text 1 | 204 | 1638 | 16 | 410 | 34 | yes | 53 |
| 12 | `pic_programmer.kicad_pcb` | text-layer 19 | 63 | 370 | 0 | 6 | 1 | yes | 7 |
| 13 | `RoyalBlue54L-Feather.kicad_pcb` | dnp 22, footprint 1, net-tie 1, teardrop 263, text 71, via-span 183, zone-outline 2 | 70 | 943 | 0 | 0 | 2 | yes | 24 |
| 14 | `RoyalBlue54L-NFC-Antenna.kicad_pcb` | copper-drawing 4, footprint-ref 1, outline 1 | 1 | 112 | 48 | 2 | 0 | yes | 1 |
| 15 | `sonde xilinx.kicad_pcb` | dimension 1, text-layer 8 | 25 | 208 | 0 | 3 | 1 | yes | 3 |
| 16 | `tinytapeout-demo.kicad_pcb` | dimension 6, dnp 11, duplicate-ref 131, footprint-ref 7, group 3, net-tie 9, outline 1, text 167, text-layer 1 | 171 | 2143 | 0 | 405 | 2 | yes | 59 |
| 17 | `video.kicad_pcb` | dimension 2, text-layer 1 | 189 | 7932 | 0 | 808 | 2 | yes | 63 |
<!-- import-corpus:end -->

Reading the table: every board comes through equivalent. What is left out is what the DSL cannot say yet
(`docs/import.md`, "What the DSL cannot say"): KiCad's groups, generated items and teardrops, components
not fitted, net ties and dimensions (c0277), texts the DSL's `text()` refuses or on layers it does not take,
and a few items of exotic demos (blind vias spanning the whole board, footprints without a reference).
