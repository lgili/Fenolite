# Viewer against Altium on a public project, 2026-11-04 (source S-1587)

This comparison was run by a Claude agent on a public project at the maintainer's request of 2026-11-04/05.
It is not the maintainer's own project and not the maintainer's review. The agent compared Fenolite's viewer
with Altium Designer 24.5.2.23 (Trial), as reported by `Client.GetProductVersion`. Altium ran in the
maintainer's Parallels Windows VM. The comparison stands beside tasks c0177 2.4, c0186 2.2 and c0180 2.4. It
does not close them, because each of those tasks asks for the maintainer's own project, and it raises no
level.

## Inputs

The project is `sstallion/PCB-PiDP11IOExpander` at `d97b8164` (BSD-2-Clause). It is in the corpus manifest
as `altium-third-party-prjpcb-04`, `-schdoc-34`, `-pcbdoc-05`, `-pcbdwf-03` and `-pcbdwf-04`. The agent
copied these five files unchanged into a VM folder:

| file | SHA-256 |
|---|---|
| `PCB-PiDP11IOExpander.PrjPcb` | `ede24d715cf83b91bb0d0e86a0f747d315de0f036bb9309a6e7e29c451e6a359` |
| `PiDP11IOExpander.SchDoc` | `8555c4ece52cebd911b6152bd211d4e8b7dc59f003fc5a031e1c7d525ff4325d` |
| `PiDP11IOExpander.PcbDoc` | `1ff7234670ec5e20092d23ecf0cd5e7380e842ef7efff2b5cb992f53f84c9c69` |
| `PiDP11IOExpander_Assembly.PCBDwf` | `4def7c99163b06d43f66af0395adab2e2220245b9b7959b206eca032d9bab1de` |
| `PiDP11IOExpander_Fabrication.PCBDwf` | `973fe49867cb7fa4ade210609e5533910c2db6732a5009ba868031b6a53e3b04` |

The Fenolite side used source `698f7608`. The page was written by
`fenolite view PCB-PiDP11IOExpander.PrjPcb --export view.html --seed 1 --timestamp 2026-11-04T00:00:00Z`,
first with `--dry-run` and then with `--confirm --plan`. The export is `23df6d1b…`. A second export used
`--variant Default`. Both pages were read in a browser on 127.0.0.1.

In Altium the project opens with nine messages, each naming a project file the corpus does not hold (the
BomDoc, three OutJobs and five text or image files). The compile flattens 23 components and 31 nets. Altium
also marks both drawings as modified after opening. Nothing was saved. Window captures covered the document
area only and were deleted after viewing.

## Schematic sheet (beside c0177 2.4)

| criterion | Altium | Fenolite page |
|---|---|---|
| layout, parts, wires | one Letter sheet, 23 parts, three coloured note regions, title block | the same parts, wires, regions and border; 23 parts, 31 nets |
| text size and font | serif designators, values and net labels; sans-serif region titles | the same faces at about the same size |
| power ports | bar ports (`VCC_3V3`, `VCC_5V`) and ground ports | the same shapes and names |
| ports, sheet entries | none: the project has one sheet | not exercised |
| title block | special strings resolved: `PiDP-11 I/O Expander`, `Revision A` | unresolved: `=ProjectTitle`, `=ProjectRev`, and `*` for date, time and file |
| text note | a yellow note ("Single board operation is assumed by default…") at the lower right | missing |
| pin names | `INT` drawn with a bar | drawn as `\INT` |
| pin electrical-type marks | arrows beside the `GP` pins of U2 | none drawn |

## Variant (beside c0186 2.2)

The PrjPcb holds one variant, `Default`, with six variations. Altium's Variant Management lists A0, A1, A2, J2,
R2 and R3 as Not Fitted, and every other part with no variation. With `Default` chosen, the Fenolite page
crosses out the same six parts on the sheet, and no other part. The agent could not switch Altium's sheet to
the variant through UI Automation: a double-click on the `Default` node left the sheet without not-fitted
marks. So the drawn marks themselves are not compared; only the not-fitted set is.

## Draftsman drawings (beside c0180 2.4, round F0.5)

| item | Altium | Fenolite page |
|---|---|---|
| assembly: views | Top, Bottom, Front and Right views, BOM, title block | the same views and table, the same title block (`Assembly Drawing`, `Revision A`); view titles below the views, not above |
| assembly: top view | silkscreen, pads and pins, not-fitted parts hatched | component outlines with designators only; no silkscreen and no hatching |
| assembly: bottom view | mounting holes and the board text | empty board outline |
| assembly: dimensions | `[2.350in±0.008] 59.69mm±0.20`, `21.59mm±0.20`, height `11.43mm±0.20` | `59.69mm`, `21.59mm`, height `43.2` |
| assembly: BOM | six columns (quantity, designator, description, manufacturer, MPN, footprint); variant applied, so A0–A2, J2, R2 and R3 are absent | three columns (comment, designator, quantity); no variant applied, so A0–A2 and J2 are grouped with J3, and R2 and R3 with R10 |
| fabrication: layout | stack legend with colour swatches, board shape with dimensions, drill view, drill table, twelve notes, title block | the same items and note text; the stack legend has three columns and no swatches |
| fabrication: drill table | 59 × 0.30 mm plated, 32 × 1.10 mm plated, 4 × 1.57 mm non-plated; 95 total; more columns | the same three rows and counts; four columns, no total |

## Result

These are generic agent observations on one public project. They raise no level: `H-G-VIEW-SCENE` and the
viewer rows stay `INFERRED`. The tasks that ask for the maintainer's own project stay open.
