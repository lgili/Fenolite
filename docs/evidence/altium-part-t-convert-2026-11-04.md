# Part T: actual Altium 24.5.2.23 T1 to T6

Source S-1571, 2026-11-04. A Claude agent ran these steps at the maintainer's request of 2026-11-04,
operating the Altium Designer installed in the maintainer's Parallels Windows VM. This is not the
maintainer's own review. The tool reports `Client.GetProductVersion` 24.5.2.23, and `X2.exe` has
FileVersion 24.5.2.23 (Trial licence, not signed in). [The measured recap](altium-part-t-convert-24-native.json)
keeps the input digests, the conversion outcomes and the hashes of the read-only scripts.

**Method.** The agent ran public menu commands through Windows UI Automation in the VM's interactive
session. Native properties were read by authored read-only DelphiScript procedures, started with
File » Run Script. The procedures use the public workspace and PCB interfaces: they open and compile a
project, list its messages, iterate polygons, pads and violation objects, and in T6 load one footprint
from the PcbLib into a scratch board. Nothing was saved. Every staged input still matches its digest
after the run.

## Inputs

The kit was rebuilt at source `d155b258` with `fenolite convert … --to altium --allow-lossy --seed 1
--timestamp 2026-11-04T00:00:00Z`, `--dry-run` then `--confirm --plan`:

| case | source | conversion at `d155b258` |
|---|---|---|
| PADSTACK | authored four-layer Full Stack fixture | written; `full-stack.PcbDoc` `cecd53b1…`, `full-stack.PcbLib` `c9255baa…` |
| SCHEMATIC | registered public `complex_hierarchy` | refused, exit 3, `FEN-3005` `geometry.degenerate`: the exact-geometry enumeration-node budget was exceeded |
| DIFAT | registered public `vme-wren` | failed, exit 1, `FEN-1001`: a symbol pin length of 1905000 nm (inductor `IND_10UH_20%_TDK_VLCF5020-1`, pin 1) is not a multiple of 10 mil |

The two failures are recorded as results; no code was changed. For SCHEMATIC and DIFAT the agent used
the historical Part T bundle of 2026-10-12 instead (its own `SHA256SUMS`: `vme-wren.PcbDoc` `62d026e1…`,
`complex_hierarchy.PcbDoc` `23a77447…`). Those observations are on these older bytes, not on the current
source.

## Results

| step | PADSTACK (current) | SCHEMATIC (2026-10-12 bytes) | DIFAT (2026-10-12 bytes) |
|---|---|---|---|
| T1 open | the schematic, PCB, PcbLib, SchLib and ActiveBOM open; no message | all six documents (three sheets, PCB, PcbLib, SchLib) open; no message | the schematic, PCB, PcbLib and SchLib open; no message |
| T2 compile | `Compile successful, no errors found.`; 1 component, 1 net | three physical sheets (10, 29 and 29 components), flattened 68 components and 56 nets; 23 messages: 3 errors (two one-pin nets at `U102`, one floating input) and 20 warnings (four duplicate pins in `U201`/`U301`, 16 nets without a driving source) | one physical sheet, 1508 components and 1847 nets; the Messages panel reached 1000 entries, 976 of them from this compile: 469 errors `has only one pin`, 395 warnings `Off sheet`, 112 warnings `Off grid` (a lower bound) |
| T3 repour | the board holds no polygon; Repour All has nothing to pour | one polygon `GND_L02_P000` (Bottom, `GND`): 0 regions before, 1 after | 134 polygons with 0 regions before; afterwards 92 hold copper (112 regions) and 42 hold none (28 Top, 14 Bottom, all `GND`) |
| T4 DRC | 0 violations | 217 violations: Clearance 17, Clearance_power 6, SilkToSilkClearance 60, SilkToSolderMaskClearance 134 | stopped at the limit of 500: Clearance 157, HoleSize 7, UnRoutedNet 336 (a lower bound) |
| T5 ECO | Comparator Results: `No Differences Detected`; no ECO | `Failed to match 2 of 68 Components using Unique identifiers`; after Automatically Create Component Links (68 links modified, in memory only), the ECO lists only Remove Net Classes (2), `Default` and `power`, from the PCB; no footprint change; closed without executing | no link dialog; the ECO lists Change Component Parameters (1495…, the count is truncated on screen) and Add Pins To Nets (2): `L1-1` to `Net-(IC32-SW)` and `L1-2` to `5VREG`; no footprint change; closed without executing |
| T6 padstack | see below | not run | not run |

In T6, three pads were read: pad `1` of the generated PCB, pad `1` of the PcbLib footprint `Mini_Padstack`, and the pad of that footprint after it was loaded into a scratch copy of the four-layer board. The script loaded it with `PCBServer.LoadCompFromLibrary` and `AddPCBObject`, not with the PCB Library panel's Place button. All three pads have the same values: mode 2 (Full Stack); Top shape 1 at 1.7 × 1.7 mm; Mid-Layer 1 shape 1 at 1.2 × 1.2 mm; Mid-Layer 2 shape 2 at 1.4 × 1.1 mm; Bottom shape 2 at 1.5 × 1.5 mm; a plated round hole of 1.0 mm; solder mask mode 1 at 4 mil; paste mode 1 at 0. These values equal the authored sizes and the 2026-10-13 native inspection. They are read as round and rectangle only by that comparison, because the tool's own name for a shape code was not displayed. The report line after the placement stopped on `Undeclared identifier: Pattern`. The agent acknowledged that error and then read the placed pad from the scratch board.

**Connector masks** were not exercised. None of the three sources has a KiCad `connect` pad: the boards
hold 6353 `smd`, 688 `thru_hole` and 8 `np_thru_hole` pads.

## What this does not settle

The four `H-A-CONV-*` rows stay `INFERRED`, and c0160 task 5.3 and c0166 task 2.1 stay open:

- The current source does not convert two of the three projects.
- SCHEMATIC and DIFAT were observed on older bytes.
- T6 used a scripted placement, and connector masks are not exercised.
- This is an agent observation, not the author report the rows ask for.

No native file, screenshot or saved document enters the repository. They stay in the agent's kit folder
outside it, and nothing was saved in Altium.

## Rerun on the current source, 2026-11-04 evening (source S-1578)

The same agent reran Part T at the maintainer's request (via the coordinating session) after the branch
was rebased on `cac/lote-13` (`3479f126`), where the exact cut of c0332 is switched off. The Altium
Designer in the VM is still 24.5.2.23 (Trial); no Altium Designer 26 is installed there. The inputs were
converted with the same command at `0207378b`:

| case | conversion | files |
|---|---|---|
| SCHEMATIC | written, exit 0 (the `FEN-3005` refusal is gone with the exact cut) | `complex_hierarchy.PcbDoc` `6f794440…`, `.SchDoc` `1c8fc161…`, `_ampli_ht_horizontal.SchDoc` `3047fd9c…`, `_ampli_ht_vertical.SchDoc` `3e8c3420…`, `.SchLib` `5e841237…`, `.PcbLib` `7d012756…`, `.PrjPcb` `9dceff67…` |
| PADSTACK | written, exit 0 | the same bytes as at `d155b258` (`cecd53b1…`, `c9255baa…`), so the T1 to T6 results above stand for the current source |
| DIFAT | refused | at `0207378b` still `FEN-1001`; at `8bbba776` exit 7, `FEN-7001`, naming the 75-mil pin of `IND_10UH_20%_TDK_VLCF5020-1` |

**Cause of `FEN-1001`.** `convert/schematic.py` called `altsym.from_symbol_def` without handling its
`ValueError` for a pin off Altium's 10-mil grid; `lens/altium.py` already reports the same case as
`altium.symbol-off-grid`. Commit `8bbba776` turns it into a target-limit refusal (`FEN-7001`) with a
regression test. It reproduces with `fenolite convert vme-wren.kicad_pro --to altium --allow-lossy --dry-run`
on the registered public project. DIFAT therefore has no current bytes, and its T1 to T5 were not rerun.

SCHEMATIC on the current bytes:

| step | observation |
|---|---|
| T1 open | the project opens its three sheets, PCB, PcbLib and SchLib; no message |
| T2 compile | three physical sheets (10, 29 and 29 components), flattened 68 components and 56 nets; `Compile successful, no errors found.` with 18 warnings: four duplicate pins in `U201`/`U301` and 14 nets without a driving source. The 2026-10-12 bytes gave 3 errors |
| T3 repour | `GND_L02_P000` (Bottom, `GND`) already holds 1 region as written; after Repour All it holds 1 |
| T4 DRC | 221 violations: SilkToSilkClearance 60, SilkToSolderMaskClearance 152, MinimumSolderMaskSliver 9; no clearance violation (the older bytes had Clearance 17 and Clearance_power 6) |
| T5 ECO | no component-link dialog; the ECO lists Remove Nets (2), `unconnected-(U102-LV-Pad6)` and `unconnected-(U102-OSC-Pad7)`, and Remove Net Classes (2), `Default` and `power`, from the PCB; no footprint change; closed without executing |
| T6 | not part of SCHEMATIC |

The rows stay `INFERRED` and task 5.3 stays open: this is an agent run on 24.5, DIFAT has no current
bytes, T6 used a scripted placement and connector masks are not exercised. Nothing was saved in Altium.
