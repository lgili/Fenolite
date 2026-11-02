# Import census: the KiCad 10.0.6 demo boards as code

The record of `H-G-IMPORT-CODE` on public boards (change c0275, task 4.3; capability board-to-code): each
KiCad 10.0.6 demo board of the corpus (S-0058, the rows `kicad-demo-10-0-6-pcb-01` to `-18` of
`tests/corpus/manifest.toml`, with their recorded licence variants) is imported with `fenolite import BOARD --to python
--out out --allow-lossy --dry-run` in a temporary folder. The import builds the emitted code and compares
the built board with the source at equivalence levels 1 to 5 and copper item by item, under the profile
`import` (absolute frame, no tolerance). Nothing converted is kept, and this page holds counts only: no
content of a board is written here (corpus-policy, "Converted code stays out of the tool repository"). The
corpus holds the boards without their project files, so each is read alone.

`tests/corpus/test_import_corpus.py` imports each board and fails when it does not come through equivalent
or when the kinds it leaves out differ from the current emission observations below. The historical
conversion table is retained unchanged; never replace its counts or timings with emission-only data.
The two heavy boards (rows 06 and 18) run full conversions only with `FENOLITE_HEAVY=1`; their historical
aggregate conversion measurements below come from CI. Current emission observations include both.

What the label means: `CORPUS-VERIFIED` here says that the code Fenolite writes for each board rebuilds a
board equal to the source at levels 1 to 5 and copper item by item, once the listed omitted kinds are
left out. It says nothing about the drawn schematic (c0276) or about what the levels do not compare
(field positions, zone fills, presentation).

The 16 non-heavy rows were refreshed on 2026-10-31 on the batch-6 integration with the c0274 prefix
correction. Those local imports returned exit 0 and equivalent=true. Rows 06 and 18 were measured on
2026-11-01 in [CI run 41305101514, job 124843785751](https://github.com/lgili/Fenolite/actions/runs/41305101514/job/124843785751),
with Fenolite commit `b8b24842c1b792a0fcb37a6a7e5ca0270b90efd6` and `kicad-cli` 10.0.6, in
`kicad/kicad:10.0.6@sha256:18693567392b80da435f9fa952ce3a3e534c66eb5a6033f5b9c80aa3b19dd3ec`.
Their `IMPORT_CENSUS` records each report exit 0 and equivalent=true; both tests then failed only because
the table lacked their rows. The job finished with 2 failed, 3584 passed, 118 skipped and 3 xfailed.
These are observed aggregate measurements, not a green job or a new exact-commit CI result.

Both heavy inputs are pinned by S-0058 and the manifest to upstream tag 10.0.6 (commit `caf7377e9cb6`).
The manifest records row 06's Apache-2.0 licence variant. Source SHA-256s:

| row | source SHA-256 |
|---|---|
| 06 | `e61179b68ac151376f5552f91a8acc2aed46f0cc4cd9c771049490735cdbf3f8` |
| 18 | `1c76ac238b04babc238d2d50585858988fb3f6c4f8d0fbacc738cfe4862fff5b` |

The table rows are copied from emitted aggregate records; no source board or converted code is kept.

<!-- import-corpus:begin -->
| row | board | left out (kind count) | parts | tracks | arcs | vias | zones | equivalent | seconds |
|---|---|---|---|---|---|---|---|---|---|
| 01 | `CM5_MINIMA_3.kicad_pcb` | dnp 2, drawing 7, drawing-layer 4, footprint-ref 1, generated 15, group 4, layer-table 9, outline-width 30, pad-net-conflict 2, text 18, zone-setting 4 | 111 | 1884 | 200 | 444 | 13 | yes | 17 |
| 02 | `complex_hierarchy.kicad_pcb` | outline-width 4, teardrop 165, text-layer 2 | 68 | 364 | 0 | 0 | 1 | yes | 5 |
| 03 | `ecc83-pp.kicad_pcb` | outline-width 4 | 15 | 59 | 0 | 0 | 1 | yes | 1 |
| 04 | `ecc83-pp_v2.kicad_pcb` | none | 15 | 53 | 0 | 0 | 1 | yes | 1 |
| 05 | `interf_u.kicad_pcb` | dimension 2, outline-width 9, text 2, text-layer 6 | 25 | 731 | 0 | 84 | 1 | yes | 3 |
| 06 | `jetson-agx-thor-baseboard.kicad_pcb` | copper-count 1, copper-layer 4030, dimension 24, dnp 113, footprint-ref 2, generated 167, layer-table 9, net-tie 6, pad-net-conflict 12, rule-area-layer 10, stackup 1, text 4, zone-layer 1 | 1123 | 16457 | 1664 | 3235 | 96 | yes | 5654 |
| 07 | `kit-dev-coldfire-xilinx_5213.kicad_pcb` | layer-table 2, outline-width 4, stackup-field 2, text-layer 5 | 160 | 2935 | 0 | 253 | 3 | yes | 18 |
| 08 | `microwave.kicad_pcb` | duplicate-ref 3, outline-width 4 | 1 | 0 | 0 | 0 | 0 | yes | 0 |
| 09 | `multichannel_mixer-unrouted.kicad_pcb` | group 4, layer-table 9, outline-width 4, rule-area-name 4, text 2 | 114 | 140 | 0 | 19 | 1 | yes | 14 |
| 10 | `multichannel_mixer.kicad_pcb` | group 4, layer-table 9, outline-width 4, rule-area-name 4, text 1 | 114 | 576 | 0 | 29 | 2 | yes | 13 |
| 11 | `One-Air-Max.kicad_pcb` | copper-drawing 2, dnp 11, drawing 16, footprint-ref 6, generated 2, group 1, layer-table 9, net-tie 2, text 1 | 204 | 1638 | 16 | 410 | 34 | yes | 27 |
| 12 | `pic_programmer.kicad_pcb` | text-layer 19 | 63 | 370 | 0 | 6 | 1 | yes | 5 |
| 13 | `RoyalBlue54L-Feather.kicad_pcb` | dnp 22, footprint 1, layer-table 9, net-tie 1, teardrop 263, text 71, via-span 183, zone-outline 2 | 70 | 943 | 0 | 0 | 2 | yes | 19 |
| 14 | `RoyalBlue54L-NFC-Antenna.kicad_pcb` | copper-drawing 4, footprint-ref 1, layer-table 45, outline 1, outline-width 17 | 1 | 112 | 48 | 2 | 0 | yes | 1 |
| 15 | `sonde xilinx.kicad_pcb` | dimension 1, outline-width 4, text-layer 8 | 25 | 208 | 0 | 3 | 1 | yes | 2 |
| 16 | `tinytapeout-demo.kicad_pcb` | dimension 6, dnp 11, duplicate-ref 131, footprint-ref 7, group 3, layer-table 9, net-tie 9, outline 1, text 167, text-layer 1 | 171 | 2143 | 0 | 405 | 2 | yes | 36 |
| 17 | `video.kicad_pcb` | dimension 2, outline-width 22, text-layer 1 | 189 | 7932 | 0 | 808 | 2 | yes | 35 |
| 18 | `vme-wren.kicad_pcb` | copper-count 1, copper-layer 4527, dimension 2, dnp 3, drawing-layer 839, generated 89, group 3, layer-table 9, outline-width 29, property 37, rule-area-layer 3, stackup 1, text 68, text-layer 34, zero-length-track 5, zone-layer 13, zone-name 5, zone-setting 1 | 1508 | 21126 | 992 | 4374 | 110 | yes | 469 |
<!-- import-corpus:end -->

Reading the historical table: every measured board came through equivalent at that revision. What was
left out was what the DSL could not say then
(`docs/import.md`, "What the DSL cannot say"): KiCad's groups, generated items and teardrops, components
not fitted, net ties and dimensions (c0277), texts the DSL's `text()` refuses or on layers it does not take,
and a few items of exotic demos (blind vias spanning the whole board, footprints without a reference).

## Current source-emission observations

Measured on 2026-11-02 with `tools/measure_import_coverage.py` against emitter commit
`fbec5cd9e711cc9b50f9b8d393ab8bb1cda48556` (`0.7.0.dev0`, explicit standard technical layer tables).
[import-coverage.json](import-coverage.json) binds each declared input SHA-256, its complete emission
counts and omitted kinds, the measurement tool SHA-256, and each observation's SHA-256. The collection
measurement SHA-256 is `c40ba136c8ee4da2d3c3a0fe25cbc1e4d43f857f19860329fcf89db5330c41fd`.

These are **emission-only observations**, including rows 06 and 18. They do not claim a completed
conversion, equivalence, native output bytes, or elapsed conversion time. The helper uses the production
reader and complete emitter, including footprint derivation; two authored fixtures and public rows 03 and 07
prove that its counts and omitted kinds match the complete CLI import. The corpus test independently
builds every selected row and still requires exit 0 and equivalent=true before comparing these current
expectations. No converted content is retained here.

<!-- import-coverage:begin -->
| row | input SHA-256 | current emission left out (kind count) |
|---|---|---|
| 01 | `123e209e6245cbcc344c1c70b425dcb44a12cd0a2d05f00a39d3f2e7ff307ffa` | none |
| 02 | `d5f4162d4c766448832723d139f9e0fcb88a17c82340f10f6f6dc6c2042f0d69` | none |
| 03 | `0ab45f4f8c90ac877e3313a1888d875107f2be3fc2b2f40cfb7927873b35260c` | none |
| 04 | `9be2caf4c257a93fc2b3904add1061a4d2e23cde502a7846513ae7db6b214c30` | none |
| 05 | `a740ce7fde77ab6af191e23ece21e57d36bb3c29325879248520dcd9ab47b57e` | none |
| 06 | `e61179b68ac151376f5552f91a8acc2aed46f0cc4cd9c771049490735cdbf3f8` | dimension-style 24, drawing 6, rule-area-placement 2 |
| 07 | `392cf6bf4b9b62beb435f965ccd7671a46decb17f947b74bfde482acd2132a5e` | none |
| 08 | `7f17191488b51f8782efc0a3b9ce7b5748a4e771ff0babb34ec0369ffcf43be5` | none |
| 09 | `149b2dce16e0f59adb78f87068f4137b7dafca0e991a0b21fdd967c873fd5ee9` | none |
| 10 | `44b7c119a0d05c98e9f294659879184038a5f6c30073c04d9536990429ca413e` | none |
| 11 | `a577ba5e2b337c9b827f3c30256161a1893da8303d278fb7db10dba4f02ea810` | none |
| 12 | `1ca70b620506818eb0227e2863bbd573d1fec1672072dc43d0dbe8475e69c8fb` | none |
| 13 | `535dbe212f43a8bab12b23277e176a94ac9694177258af2981c0e7b08e4b7252` | none |
| 14 | `cd87e6d1b20fe0d129d9a9c807af3118c67749eff44b1f032d85c047a814c6dc` | none |
| 15 | `d0dee876715fcdd3f656dd6a77cc1141c39bec4d6f8492a3784d38edd6b9a998` | none |
| 16 | `0d26bf9b6d561e32cf610d428541d6433e60b45e1838f34f73467e25b9144814` | none |
| 17 | `f620675158ddd5c61e5ce9e15f4c92b230ae1df1cbcec6c502b8ce266e4007ea` | none |
| 18 | `1c76ac238b04babc238d2d50585858988fb3f6c4f8d0fbacc738cfe4862fff5b` | text 10, zero-length-track 5, zone-name 6, zone-setting 1 |
<!-- import-coverage:end -->
