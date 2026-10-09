# Conversion ledger: the KiCad 10.0.6 demo boards converted to Altium

The record of `H-G-CONV-LEDGER` (change c0159, capability design-conversion): each KiCad 10.0.6 demo board
of the corpus (S-0058, the rows `kicad-demo-10-0-6-pcb-01` to `-18` of `tests/corpus/manifest.toml`) is
converted to Altium with `fenolite.api.convert(board, to="altium", allow_lossy=True)`, and the PCB
document it writes is read back with the Altium backend and compared with the design that was written, at
the highest level both hold, under the profile `kicad-to-altium` (`src/fenolite/convert/data/profiles.toml`:
relative frame, 3 nm, 20 ppm). The page holds counts and the writer's reasons only; no content of a board
is written here. The corpus holds the boards without their project files, so each is read alone.

`tests/corpus/test_convert_census.py` reads the two tables between the markers below and fails when a
conversion gives other rows, or any `convert.unexplained`. Regenerate them by running the census and
copying its rows; never edit a count by hand.

What the label means: `CORPUS-VERIFIED` here says that every difference between a board and the reading
of its conversion is excluded by the profile or explained by an item the report names as lost. It says
nothing about what Altium Designer does with the documents (the kit's and the author reports' question,
`docs/altium-kit.md`), and it does not raise the Altium writers' own level (`INFERRED`, experimental).

## The boards

Measured on 2026-10-09 on `dev` at `3cfb65b` with this change (local run, Linux, 4 CPUs).

| row | board | footprints | written | level | explained differences | seconds |
|---|---|---|---|---|---|---|
| `-01` | CM5_MINIMA_3 | 112 | PCB document only (the schematic writer refuses the circuit) | 5 | 23 | 5.9 |
| `-02` | complex_hierarchy | 68 | yes | 5 | 0 | 1.3 |
| `-03` | ecc83-pp | 15 | yes | 5 | 0 | 0.4 |
| `-04` | ecc83-pp_v2 | 15 | yes | 5 | 19 | 0.4 |
| `-05` | interf_u | 25 | yes | 5 | 124 | 1.5 |
| `-06` | jetson-agx-thor-baseboard | — | no: the document needs 119 FAT sectors (`TargetLimitError`) | — | — | — |
| `-07` | kit-dev-coldfire-xilinx_5213 | 160 | yes | 5 | 8 | 5.6 |
| `-08` | microwave | 4 | yes | 4 | 1 | 0.2 |
| `-09` | multichannel_mixer-unrouted | 114 | yes | 5 | 38 | 3.1 |
| `-10` | multichannel_mixer | 114 | yes | 5 | 38 | 3.5 |
| `-11` | One-Air-Max | 210 | yes | 5 | 49 | 5.2 |
| `-12` | pic_programmer | 63 | yes | 5 | 12 | 1.6 |
| `-13` | RoyalBlue54L-Feather | 71 | yes | 5 | 84 | 4.7 |
| `-14` | RoyalBlue54L-NFC-Antenna | 2 | yes | 5 | 0 | 0.6 |
| `-15` | sonde xilinx | 25 | yes | 5 | 0 | 0.6 |
| `-16` | tinytapeout-demo | 309 | PCB document only (the schematic writer refuses the circuit) | 5 | 44 | 7.1 |
| `-17` | video | 189 | yes | 5 | 248 | 12.2 |
| `-18` | vme-wren | — | no: the document needs 181 FAT sectors with its bodies (`TargetLimitError`) | — | — | — |

No board gives `convert.unexplained`. The seconds include the read-back and the comparison.

- **Before this change** (the design's measurement, `lens.altium.write_model` and `compare_designs`), the
  `dnp` differences of four boards (2, 11, 22 and 11 components) had no declared cause, and `pad-shape`
  differences of equal-sized ovals were reported on eight boards; c0158 made those ovals circles, and the
  write now counts each do-not-populate component under `dnp`.
- **Largest per-coordinate difference** without tolerance: 2 nm (a placement after the frame's
  translation, a pad position, a pad size or a drill), which sets `tolerance_nm` 3 of the profile
  (`tests/corpus/test_convert_census.py::test_differences_per_kind`).
- **A reference that several components share** in the board (`microwave` 1, `One-Air-Max` 1,
  `tinytapeout-demo` 4) gives a `ref-ambiguous` difference that the board compared with itself gives
  too; it is explained as the source's own (`source`).

## Changed and lost, per kind and reason

One row per kind and reason of the report, per board (`outcome` `changed`: written in another form that
compares equal; `lost`: not written).

<!-- ledger:begin -->
| board | kind | outcome | count | reason |
|---|---|---|---|---|
| CM5_MINIMA_3 | dnp | lost | 2 | the Altium documents hold no fitted flag outside variants |
| CM5_MINIMA_3 | pad | lost | 16 | the pad number '' is empty |
| CM5_MINIMA_3 | pad | lost | 12 | the pad has a per-layer padstack |
| CM5_MINIMA_3 | pad | lost | 2 | the pad is a connector pad (kind connect) |
| CM5_MINIMA_3 | footprint-graphic | lost | 16 | the layer Cmts.User has no layer in the document for a graphic |
| CM5_MINIMA_3 | footprint-graphic | lost | 6 | the layer Eco2.User has no layer in the document for a graphic |
| CM5_MINIMA_3 | footprint-graphic | lost | 5 | the layer Eco1.User has no layer in the document for a graphic |
| CM5_MINIMA_3 | footprint-graphic | lost | 3 | a filled circle has no record: a region holds straight edges only |
| CM5_MINIMA_3 | footprint-graphic | lost | 2 | the layer Dwgs.User has no layer in the document for a graphic |
| CM5_MINIMA_3 | footprint-graphic | lost | 1 | the layer User.2 has no layer in the document for a graphic |
| CM5_MINIMA_3 | zone-fill | changed | 13 | a polygon is written unpoured; Altium fills it on a repour |
| CM5_MINIMA_3 | outline | lost | 1 | the board holds no closed outline; the box of its items is written |
| CM5_MINIMA_3 | stackup | lost | 1 | the document has no key for the solder mask thickness, the colours, the finish, the impedance-control flag; the copper and dielectric values are written |
| CM5_MINIMA_3 | text | lost | 149 | the layer Dwgs.User has no layer in the document for a text |
| CM5_MINIMA_3 | graphic | lost | 27 | the layer Dwgs.User has no layer in the document for a graphic |
| CM5_MINIMA_3 | graphic | lost | 4 | the layer User.4 has no layer in the document for a graphic |
| CM5_MINIMA_3 | schematic | lost | 1 | the schematic writer refuses the circuit: no schematic and no project file are written |
| complex_hierarchy | zone-fill | changed | 1 | a polygon is written unpoured; Altium fills it on a repour |
| complex_hierarchy | stackup | lost | 1 | the document has no key for the solder mask thickness, the colours; the copper and dielectric values are written |
| complex_hierarchy | text | lost | 1 | the layer B.Cu has no layer in the document for a text |
| complex_hierarchy | text | lost | 1 | the layer F.Cu has no layer in the document for a text |
| complex_hierarchy | schematic | changed | 1 | the schematic is generated from the circuit on one sheet with generic symbols |
| ecc83-pp | footprint-graphic | lost | 4 | the layer Cmts.User has no layer in the document for a graphic |
| ecc83-pp | zone-fill | changed | 1 | a polygon is written unpoured; Altium fills it on a repour |
| ecc83-pp | stackup | lost | 1 | the document has no key for the solder mask thickness, the colours; the copper and dielectric values are written |
| ecc83-pp | schematic | changed | 1 | the schematic is generated from the circuit on one sheet with generic symbols |
| ecc83-pp_v2 | pad | lost | 9 | the pad has a per-layer padstack |
| ecc83-pp_v2 | pad | lost | 1 | the pad number '' is empty |
| ecc83-pp_v2 | footprint-graphic | lost | 4 | the layer Cmts.User has no layer in the document for a graphic |
| ecc83-pp_v2 | zone-fill | changed | 1 | a polygon is written unpoured; Altium fills it on a repour |
| ecc83-pp_v2 | stackup | lost | 1 | the document has no key for the solder mask thickness, the colours; the copper and dielectric values are written |
| ecc83-pp_v2 | schematic | changed | 1 | the schematic is generated from the circuit on one sheet with generic symbols |
| interf_u | pad | lost | 62 | the pad is a connector pad (kind connect) |
| interf_u | zone-fill | changed | 1 | a polygon is written unpoured; Altium fills it on a repour |
| interf_u | stackup | lost | 1 | the document has no key for the solder mask thickness, the colours; the copper and dielectric values are written |
| interf_u | text | lost | 3 | the layer B.Cu has no layer in the document for a text |
| interf_u | text | lost | 3 | the layer F.Cu has no layer in the document for a text |
| interf_u | dimension | lost | 2 | the document has no dimension record |
| interf_u | schematic | changed | 1 | the schematic is generated from the circuit on one sheet with generic symbols |
| kit-dev-coldfire-xilinx_5213 | pad | lost | 3 | the pad has a per-layer padstack |
| kit-dev-coldfire-xilinx_5213 | pad | lost | 2 | the pad number '' is empty |
| kit-dev-coldfire-xilinx_5213 | zone-fill | changed | 3 | a polygon is written unpoured; Altium fills it on a repour |
| kit-dev-coldfire-xilinx_5213 | stackup | lost | 1 | the document has no key for the solder mask thickness, the colours, the finish; the copper and dielectric values are written |
| kit-dev-coldfire-xilinx_5213 | text | lost | 4 | the layer F.Cu has no layer in the document for a text |
| kit-dev-coldfire-xilinx_5213 | text | lost | 1 | the layer B.Cu has no layer in the document for a text |
| kit-dev-coldfire-xilinx_5213 | schematic | changed | 1 | the schematic is generated from the circuit on one sheet with generic symbols |
| microwave | footprint-copper | lost | 4 | a graphic of a footprint on a copper layer has no record written: it would be copper |
| microwave | graphic | lost | 3 | the layer Dwgs.User has no layer in the document for a graphic |
| microwave | schematic | changed | 1 | the schematic is generated from the circuit on one sheet with generic symbols |
| multichannel_mixer-unrouted | pad | lost | 35 | the pad has a per-layer padstack |
| multichannel_mixer-unrouted | footprint-graphic | lost | 32 | the layer Cmts.User has no layer in the document for a graphic |
| multichannel_mixer-unrouted | zone-fill | changed | 1 | a polygon is written unpoured; Altium fills it on a repour |
| multichannel_mixer-unrouted | keep-out | lost | 4 | the keep-out sets no restriction that the record carries (tracks, vias, pads, copper) |
| multichannel_mixer-unrouted | text | lost | 1 | the layer Eco1.User has no layer in the document for a text |
| multichannel_mixer-unrouted | text | lost | 1 | the text holds a control character or a line break |
| multichannel_mixer-unrouted | schematic | changed | 1 | the schematic is generated from the circuit on one sheet with generic symbols |
| multichannel_mixer | pad | lost | 35 | the pad has a per-layer padstack |
| multichannel_mixer | footprint-graphic | lost | 32 | the layer Cmts.User has no layer in the document for a graphic |
| multichannel_mixer | zone-fill | changed | 2 | a polygon is written unpoured; Altium fills it on a repour |
| multichannel_mixer | keep-out | lost | 4 | the keep-out sets no restriction that the record carries (tracks, vias, pads, copper) |
| multichannel_mixer | text | lost | 1 | the layer Eco1.User has no layer in the document for a text |
| multichannel_mixer | text | lost | 1 | the text holds a control character or a line break |
| multichannel_mixer | schematic | changed | 1 | the schematic is generated from the circuit on one sheet with generic symbols |
| One-Air-Max | dnp | lost | 11 | the Altium documents hold no fitted flag outside variants |
| One-Air-Max | pad | lost | 12 | the pad has the shape custom, which has no exact Altium form |
| One-Air-Max | pad | lost | 6 | the pad has a per-layer padstack |
| One-Air-Max | pad | lost | 5 | the pad number '' is empty |
| One-Air-Max | footprint-copper | lost | 3 | a graphic of a footprint on a copper layer has no record written: it would be copper |
| One-Air-Max | footprint-graphic | lost | 28 | the layer Cmts.User has no layer in the document for a graphic |
| One-Air-Max | footprint-graphic | lost | 1 | degenerate arc on F.SilkS is not written |
| One-Air-Max | net-tie | lost | 2 | the pads are written, without a mark that ties them: a net-tie group is KiCad data |
| One-Air-Max | copper-shape | lost | 2 | a shape on a copper layer has no record written |
| One-Air-Max | zone-fill | changed | 34 | a polygon is written unpoured; Altium fills it on a repour |
| One-Air-Max | outline | lost | 20 | an arc of the outline is written as two straight edges |
| One-Air-Max | stackup | lost | 1 | the document has no key for the solder mask thickness, the finish; the copper and dielectric values are written |
| One-Air-Max | text | lost | 24 | the text record has no key for a justification other than centred |
| One-Air-Max | text | lost | 1 | the text holds a control character or a line break |
| One-Air-Max | graphic | lost | 2 | the layer Dwgs.User has no layer in the document for a graphic |
| One-Air-Max | schematic | changed | 1 | the schematic is generated from the circuit on one sheet with generic symbols |
| pic_programmer | pad | lost | 9 | the pad number '' is empty |
| pic_programmer | pad | lost | 2 | the pad has the shape custom, which has no exact Altium form |
| pic_programmer | footprint-graphic | lost | 6 | the layer Cmts.User has no layer in the document for a graphic |
| pic_programmer | zone-fill | changed | 1 | a polygon is written unpoured; Altium fills it on a repour |
| pic_programmer | stackup | lost | 1 | the document has no key for the solder mask thickness, the colours; the copper and dielectric values are written |
| pic_programmer | text | lost | 17 | the layer F.Cu has no layer in the document for a text |
| pic_programmer | text | lost | 2 | the layer B.Cu has no layer in the document for a text |
| pic_programmer | schematic | changed | 1 | the schematic is generated from the circuit on one sheet with generic symbols |
| RoyalBlue54L-Feather | dnp | lost | 22 | the Altium documents hold no fitted flag outside variants |
| RoyalBlue54L-Feather | pad | lost | 39 | the pad number '' is empty |
| RoyalBlue54L-Feather | pad | lost | 18 | the pad has the shape custom, which has no exact Altium form |
| RoyalBlue54L-Feather | pad | lost | 6 | the pad is a connector pad (kind connect) |
| RoyalBlue54L-Feather | pad | lost | 4 | the pad has a per-layer padstack |
| RoyalBlue54L-Feather | footprint-copper | lost | 1 | a graphic of a footprint on a copper layer has no record written: it would be copper |
| RoyalBlue54L-Feather | footprint-graphic | lost | 4 | the layer Cmts.User has no layer in the document for a graphic |
| RoyalBlue54L-Feather | footprint-text | lost | 2 | a text of a footprint: the layer Cmts.User has no layer in the document for a text |
| RoyalBlue54L-Feather | net-tie | lost | 1 | the pads are written, without a mark that ties them: a net-tie group is KiCad data |
| RoyalBlue54L-Feather | zone | lost | 2 | the model holds no outline of the zone (an outline with an arc is kept by the reader) |
| RoyalBlue54L-Feather | zone-fill | changed | 2 | a polygon is written unpoured; Altium fills it on a repour |
| RoyalBlue54L-Feather | outline | lost | 4 | an arc of the outline is written as two straight edges |
| RoyalBlue54L-Feather | stackup | lost | 1 | the document has no key for the solder mask thickness, the colours, the finish; the copper and dielectric values are written |
| RoyalBlue54L-Feather | text | lost | 1 | the text holds a control character or a line break |
| RoyalBlue54L-Feather | schematic | changed | 1 | the schematic is generated from the circuit on one sheet with generic symbols |
| RoyalBlue54L-NFC-Antenna | footprint-graphic | lost | 6 | the layer Cmts.User has no layer in the document for a graphic |
| RoyalBlue54L-NFC-Antenna | footprint-graphic | lost | 5 | the layer Edge.Cuts has no layer in the document for a graphic |
| RoyalBlue54L-NFC-Antenna | copper-shape | lost | 4 | a shape on a copper layer has no record written |
| RoyalBlue54L-NFC-Antenna | outline | lost | 1 | the board holds no closed outline; the box of its items is written |
| RoyalBlue54L-NFC-Antenna | schematic | changed | 1 | the schematic is generated from the circuit on one sheet with generic symbols |
| sonde xilinx | footprint-graphic | lost | 2 | the layer Dwgs.User has no layer in the document for a graphic |
| sonde xilinx | footprint-text | lost | 2 | a text of a footprint: the layer Dwgs.User has no layer in the document for a text |
| sonde xilinx | zone-fill | changed | 1 | a polygon is written unpoured; Altium fills it on a repour |
| sonde xilinx | stackup | lost | 1 | the document has no key for the solder mask thickness, the colours, the finish; the copper and dielectric values are written |
| sonde xilinx | text | lost | 7 | the layer F.Cu has no layer in the document for a text |
| sonde xilinx | text | lost | 1 | the layer B.Cu has no layer in the document for a text |
| sonde xilinx | dimension | lost | 1 | the document has no dimension record |
| sonde xilinx | schematic | changed | 1 | the schematic is generated from the circuit on one sheet with generic symbols |
| tinytapeout-demo | dnp | lost | 11 | the Altium documents hold no fitted flag outside variants |
| tinytapeout-demo | pad | lost | 16 | the pad has the shape custom, which has no exact Altium form |
| tinytapeout-demo | pad | lost | 7 | the pad number '' is empty |
| tinytapeout-demo | pad | lost | 4 | the pad has a per-layer padstack |
| tinytapeout-demo | footprint-copper | lost | 25 | a graphic of a footprint on a copper layer has no record written: it would be copper |
| tinytapeout-demo | footprint-graphic | lost | 9 | the layer Edge.Cuts has no layer in the document for a graphic |
| tinytapeout-demo | footprint-graphic | lost | 6 | a filled circle has no record: a region holds straight edges only |
| tinytapeout-demo | footprint-graphic | lost | 4 | the layer Cmts.User has no layer in the document for a graphic |
| tinytapeout-demo | footprint-text | lost | 1 | a text of a footprint: the layer User.4 has no layer in the document for a text |
| tinytapeout-demo | net-tie | lost | 9 | the pads are written, without a mark that ties them: a net-tie group is KiCad data |
| tinytapeout-demo | zone-fill | changed | 2 | a polygon is written unpoured; Altium fills it on a repour |
| tinytapeout-demo | outline | lost | 1 | the board holds no closed outline; the box of its items is written |
| tinytapeout-demo | stackup | lost | 1 | the stack-up holds several dielectric sheets between F.Cu and In1.Cu (2 dielectric entries) and the document holds one dielectric per gap; the default stack values are written |
| tinytapeout-demo | text | lost | 215 | the text record has no key for a justification other than centred |
| tinytapeout-demo | text | lost | 8 | the text holds a control character or a line break |
| tinytapeout-demo | text | lost | 1 | the layer User.1 has no layer in the document for a text |
| tinytapeout-demo | graphic | lost | 2 | a filled circle has no record: a region holds straight edges only |
| tinytapeout-demo | dimension | lost | 6 | the document has no dimension record |
| tinytapeout-demo | schematic | lost | 1 | the schematic writer refuses the circuit: no schematic and no project file are written |
| video | pad | lost | 120 | the pad is a connector pad (kind connect) |
| video | pad | lost | 24 | the pad number '' is empty |
| video | zone-fill | changed | 2 | a polygon is written unpoured; Altium fills it on a repour |
| video | stackup | lost | 1 | the document has no key for the solder mask thickness, the colours, the finish; the copper and dielectric values are written |
| video | text | lost | 1 | the layer B.Cu has no layer in the document for a text |
| video | graphic | lost | 14 | the layer Dwgs.User has no layer in the document for a graphic |
| video | dimension | lost | 2 | the document has no dimension record |
| video | schematic | changed | 1 | the schematic is generated from the circuit on one sheet with generic symbols |
<!-- ledger:end -->

## Differences explained

Each difference of the read-back, per board, with the kind of the lost item that explains it.

<!-- explained:begin -->
| board | difference | explained by | count |
|---|---|---|---|
| CM5_MINIMA_3 | dnp | dnp | 2 |
| CM5_MINIMA_3 | pad-missing | pad | 15 |
| CM5_MINIMA_3 | pin-missing | pad | 6 |
| ecc83-pp_v2 | pad-missing | pad | 10 |
| ecc83-pp_v2 | pin-missing | pad | 9 |
| interf_u | pad-missing | pad | 62 |
| interf_u | pin-missing | pad | 62 |
| kit-dev-coldfire-xilinx_5213 | pad-missing | pad | 5 |
| kit-dev-coldfire-xilinx_5213 | pin-missing | pad | 3 |
| microwave | ref-ambiguous | source | 1 |
| multichannel_mixer-unrouted | pad-missing | pad | 19 |
| multichannel_mixer-unrouted | pin-missing | pad | 19 |
| multichannel_mixer | pad-missing | pad | 19 |
| multichannel_mixer | pin-missing | pad | 19 |
| One-Air-Max | dnp | dnp | 11 |
| One-Air-Max | pad-missing | pad | 20 |
| One-Air-Max | pin-missing | pad | 17 |
| One-Air-Max | ref-ambiguous | source | 1 |
| pic_programmer | pad-missing | pad | 10 |
| pic_programmer | pin-missing | pad | 2 |
| RoyalBlue54L-Feather | dnp | dnp | 22 |
| RoyalBlue54L-Feather | pad-missing | pad | 35 |
| RoyalBlue54L-Feather | pin-missing | pad | 25 |
| RoyalBlue54L-Feather | route-connectivity | zone | 2 |
| tinytapeout-demo | dnp | dnp | 11 |
| tinytapeout-demo | pad-missing | pad | 24 |
| tinytapeout-demo | pin-missing | pad | 4 |
| tinytapeout-demo | ref-ambiguous | source | 4 |
| tinytapeout-demo | route-connectivity | pad | 1 |
| video | pad-missing | pad | 128 |
| video | pin-missing | pad | 120 |
<!-- explained:end -->

## What the ledger asks of the writers

The losses of `refuse` kinds that the census measures are the work of change c0160 (closing the losses of
KiCad to Altium); none of them is a fault of the conversion, which reports each one and explains every
difference it causes:

- `pad`: connector pads (`kind connect`, 190 pads on four boards), per-layer padstacks (108 on eight boards),
  pads without a number (103 on eight boards) and custom shapes (48 on four boards);
- `dnp`: 46 components on four boards, which Altium holds in variants only (after 1.0);
- `zone` (2 zones whose outline holds an arc, `RoyalBlue54L-Feather`), `footprint-copper` (33 graphics on
  four boards) and `copper-shape` (6 shapes on two boards);
- the schematic writer refuses the circuits of `CM5_MINIMA_3` (one pin on two nets) and `tinytapeout-demo`
  (two symbols with one storage name), so their conversions hold the PCB document alone;
- `jetson-agx-thor-baseboard` and `vme-wren` are not written at all: their documents need DIFAT sectors.
