# Altium PCB writers: the maintainer's check

This page is the protocol by which the maintainer checks the PCB files that `fenolite build --target
altium` writes for `examples/blink_2layer/design.py` (change c0035, capability altium-build, "PCB author
reports"). The files are committed under `tests/data/altium/blink/`; they are built from the authored CC0
mini library (`tests/data/libs/Mini_v9.*`), so they may be uploaded and shared.
Since change c0061 the example marks its 29 unused pins with `no_connect`; the committed files are those
of the example without that call (`tests/_altium.py`), so their bytes and the SHA-256 values below are
unchanged. A build of the example as it is adds one No ERC directive per marked pin to `blink.SchDoc`.

- Results are recorded in `docs/hypotheses.md` as `ALTIUM-VERIFIED(author-report; <tool>; <YYYY-MM-DD>;
  no artefact)`, the tool being `A365 Viewer` or `AD <major>.<minor or x>`, with one generic outcome per
  step. No file made in Altium enters the repository.
- **Licence rule.** Part P uses the free Altium 365 Viewer (S-0149), which needs no licence. Part D needs
  Altium Designer under a licence the maintainer may use for Fenolite (`LEGAL.md`, block A, P3 and P4). A
  result obtained with an employer's licence, or any licence the maintainer may not use for this purpose,
  is **not recorded**: the rows it would settle stay `INFERRED` with a result that starts with
  `pending (author report)`.
- The KiCad oracles (`tests/kicad/altium/test_pcblib_oracle.py`, `test_pcbdoc_oracle.py`) check only what
  KiCad's importer reads; they never settle an Altium row.

## The committed files

`tests/unit/lens/test_altium_pcb_golden.py` checks that fresh builds give these bytes and that this table
names them.

| file | SHA-256 |
|---|---|
| `tests/data/altium/blink/blink.PcbDoc` | `642ce93cdfd14136c421406e3ba261aab055fcdb437dff9cfc9fefebdd3e0a32` |
| `tests/data/altium/blink/blink.PcbLib` | `8fca33bda63bc3846e99478aa76f20e248026aefa0addd6e6e4ce9e9314c0082` |
| `tests/data/altium/blink/blink.PrjPcb` | `91a938db221c185bd611c2d6f0698677e8a16c616ffec75ab53b20aca1a2931c` |
| `tests/data/altium/blink/blink.SchDoc` | `c34bde2f95810e5f41647b6fe393b596c998c217074092fb121087a5dfdd6284` |
| `tests/data/altium/blink/blink.SchLib` | `1c97388753b0826ae3029506aad502cc0c63b65a6a72f0d0ac3cb374a347c48d` |

Since change c0086 (2026-10-06) `blink.SchDoc` and `blink.SchLib`, here and in the routed sample of Part C,
are the default build with the symbols' own graphics. The reports of this page were made on the rectangle
form of those two files, which is kept byte for byte under `tests/data/altium/generic/blink/` and
`tests/data/altium/generic/routed/` and is still built with `--altium-symbols generic`
(`tests/unit/lens/test_altium_schematic_complete.py -k generic`). The graphics form has not been opened in
Altium (Part Y of `docs/evidence/altium-schematic.md`, step Y9); the PCB library, the PCB document and the
project file did not change.

### Report of 2026-10-03 and the files since

The maintainer opened the first `blink.PcbLib` (SHA-256 `dbe1aef8…025a`, the stream set of AltiumSharp
version 1 alone) in an Altium Designer trial: a "catastrophic" error, and the same for a library without
footprints. The library is since written in the form Altium saves (`docs/formats/altium/pcb-library.md`:
the 53-byte `FileHeader`, the whole board record in `Library/Data`, the `Library` side streams), and
`blink.PcbDoc` carries the id block of `FileHeaderSix`. In that form the library opens ("Reports" below).
`blink.PcbDoc`, then still a short `Board6` record with 20 storages, failed with the same "catastrophic"
error; it is since written in the form Altium saves (`docs/formats/altium/pcb-document.md`, "The document
as Altium saves it"), and the digests above are the new files. The new document opens ("Reports" below).
Since a refusal names no cause, the maintainer also gets six documents outside the repository, each with
one thing more than the one before: the outline alone; one net; one component without pads; its pads; its
designator and comment texts; the full sample. The first that fails names what to study next. Texts, pads,
tracks and arcs keep the short forms of `pcb-records.md`.

Change c0038 rebuilt `blink.PcbDoc`: it now holds the net class `PWR` in `Classes6` and five rules in
`Rules6` (`Clearance_PWR`, `Clearance`, `Width_PWR`, `Width`, `RoutingVias`)
(`docs/formats/altium/pcb-copper.md`). The document that the report of 2026-10-03 opened had the SHA-256
`5e084d85…894f` and neither class nor rule; that report stays valid for the facts it settled, and Part C names the new
bytes.

Change c0048 rebuilt the schematics, the project files and the documents of the blink and routed samples:
each schematic holds the net class directives, each project file the class keys and `[PrjClassGen]`, and
each document the component class of its sheet (`blink` and `routed`). The Viewer report of 2026-10-03
names the document it uploaded, `f0940168…3c01`; the copper report of Part C was made on
`aee17146…0fef`. Both stay valid for the facts they settled: the new records are one class more in
`Classes6`.

### Pads of the library

Sizes and holes in binary units (1 unit = 2.54 nm; 708661 units = 1.8 mm, 354331 = 0.9 mm). "rounded" is a
round pad with alternate shape 9 and corner percentage 50 (KiCad ratio 0.25). Through-hole pads lie on
Multi-Layer, surface pads on the Top Layer.

| footprint | pad | shape | size | hole |
|---|---|---|---|---|
| `Mini_LED_THT_3mm` | 1 | rectangle | 708661 × 708661 | 354331 |
| `Mini_LED_THT_3mm` | 2 | round | 708661 × 708661 | 354331 |
| `Mini_QFP-32_7x7mm_P0.8mm` | 1…32 | rounded | 590551 × 216535 | 0 |
| `Mini_R_0603` | 1…2 | rounded | 354331 × 374016 | 0 |

Graphics: silkscreen lines and two arcs on Top Overlay; the fabrication outline (rectangle or circle) on
Mechanical 13; the courtyard on Mechanical 15. The filled pin-1 triangle of the QFP is not written
(`altium.primitive-dropped`); texts, properties and 3D model links are not written.

### The document

`blink.PcbDoc` is experimental: a 50 × 30 mm two-layer board whose lower-left corner lies at (1000 mil,
1000 mil), the three components at their script placements, their pads, silkscreen, fabrication and
courtyard graphics, the designators (comments hidden) and the nets on the pads; no routing.

| component | layer | rotation | footprint |
|---|---|---|---|
| `D1` | BOTTOM | 0 | `Mini_LED_THT_3mm` |
| `R1` | TOP | 0 | `Mini_R_0603` |
| `U1` | TOP | 0 | `Mini_QFP-32_7x7mm_P0.8mm` |

Pad nets (every other pad has no net):

| ref | pad | net |
|---|---|---|
| D1 | 1 | GND |
| D1 | 2 | LED_A |
| R1 | 1 | LED_DRV |
| R1 | 2 | LED_A |
| U1 | 1 | LED_DRV |
| U1 | 9 | VIN |
| U1 | 10 | GND |

## Part P: the Altium 365 Viewer

No licence is needed. Upload only the files named here.

- **P1** (`blink.PcbDoc`, SHA-256 above): upload the document alone. Expected: the board outline, three
  components with their pads and designators, the silkscreen arcs and lines, and `D1` on the bottom side
  (its graphics on Bottom Overlay, Mechanical 14 and 16). Settles `H-A-PCB-DOC-VIEWER`, and supports
  `H-A-PCB-PAD`, `H-A-PCB-GRAPHICS` and `H-A-PCB-DOC-BOTTOM` for what the Viewer shows.
- **P2** (a Zip of `blink.PrjPcb`, `blink.SchDoc`, `blink.SchLib`, `blink.PcbLib` and `blink.PcbDoc`): upload
  the Zip as one project. Note whether the Viewer lists the project, the library and the document;
  supports `H-A-PCB-DOC-VIEWER` (the Viewer does not list `.PcbLib` among its inputs, S-0149).

## Part D: Altium Designer

Each step needs a licence the maintainer may use for Fenolite (licence rule above). Work on copies.

- **D1** (`blink.PrjPcb`, `blink.SchDoc`, `blink.SchLib`, `blink.PcbLib`, SHA-256 above): open the project.
  Check that the project lists the PCB library, then open `blink.PcbLib`: the PCB Library panel lists the
  three footprints with no repair prompt; each footprint's pads, holes and shapes equal the pad table;
  the silkscreen, fabrication and courtyard graphics are visible on Top Overlay, Mechanical 13 and
  Mechanical 15. Settles `H-A-PCB-LIB-OPEN`, `H-A-PCB-PAD`, `H-A-PCB-GRAPHICS` and `H-A-PCB-PRJ`. When a
  footprint with a name longer than 31 characters is added to a test build, its full name is shown
  (`H-A-PCB-LIB-NAME`).
- **D2** (same files): add a new blank PCB document to the project and run "Design » Update PCB Document"
  from `blink.SchDoc`. Expected: every footprint is found in `blink.PcbLib`; no "footprint not found".
  Settles `H-A-PCB-ECO`.

- **D3** (`blink.PcbDoc` with the project, SHA-256 above, on a copy): open the document. Expected: no repair
  prompt, two copper layers, the board at the offset frame. Then run "Design » Update PCB Document" from
  `blink.SchDoc`: no component is added or removed (the unique ids match), no net changes, and `D1` stays
  on the bottom as in its KiCad build. Settles `H-A-PCB-DOC-OPEN`, `H-A-PCB-DOC-LINK`, `H-A-PCB-DOC-NETS`
  and `H-A-PCB-DOC-BOTTOM`.

Report per step: the tool and version, the date, and one generic outcome (as expected, or the first
message shown). Do not describe Altium's internals beyond what the step asks.

## Part C: copper (change c0038)

The routed sample is the blink design named `routed` on four copper layers, with copper authored for
Fenolite (`tests/_altium_copper.py`). `tests/unit/lens/test_altium_copper_golden.py` checks that a fresh
build gives these bytes, that this table names them, and that the copper table below equals the sample.
The plane variant `p0` is not committed; the test rebuilds it and checks its digest.

| file | SHA-256 |
|---|---|
| `tests/data/altium/routed/routed.PcbDoc` | `158cc00bc5d78a82f5c5a2a99fab5b839b3da3d5c279b641105aba5c8815931f` |
| `tests/data/altium/routed/routed.PcbLib` | `693d03ad18bc987664a681933fab96e3a01aa2477a8e9181cb1f6fd0e2355738` |
| `tests/data/altium/routed/routed.PrjPcb` | `9c35d817e1d0ab294f8ad72674d2e2c4f470d449b71b998eba0886b78b7b62f0` |
| `tests/data/altium/routed/routed.SchDoc` | `01ab1936ab50c1d506c0891f471b4a01177489f14ae76d943538ca91022fabf5` |
| `tests/data/altium/routed/routed.SchLib` | `2c4b57784793fa177849de22ebb00ff760cf60a57174102405260ff47d4480c5` |
| `p0/routed.PcbDoc` | `8e0978ec8ee6c22e3a8a3a76b4e14f17be811b9604f463207f3d6eae2f84dbb1` |

Expected copper, in millimetres from the outline's top-left corner (Y down); the last column is the width
of a track or arc, or the diameter and hole of a via:

| kind | layer | net | geometry (mm) | size (mm) |
|---|---|---|---|---|
| track | F.Cu | LED_DRV | (9.85, 12.2) → (9.85, 10) | 0.25 |
| track | F.Cu | LED_DRV | (10.85, 9) → (31.2, 9) | 0.25 |
| track | B.Cu | VIN | (11.2, 18.75) → (5, 18.75) | 0.5 |
| track | In1.Cu | VIN | (11.2, 18.75) → (11.2, 26) | 0.5 |
| track | In2.Cu | LED_A | (32.8, 9) → (40.54, 20) | 0.25 |
| arc | F.Cu | LED_DRV | (9.85, 10) → (10.142893, 9.292893) → (10.85, 9) | 0.25 |
| via | F.Cu–B.Cu | LED_A | (32.8, 9) | 0.6 / 0.3 |
| via | F.Cu–B.Cu | VIN | (11.2, 18.75) | 0.6 / 0.3 |
| via | F.Cu–B.Cu | GND | (12, 19.55) | 0.6 / 0.3 |
| polygon | In1.Cu | GND | (1, 1), (49, 1), (49, 29), (1, 29) | unpoured |
| polygon | B.Cu | GND | (1, 1), (49, 1), (49, 29), (1, 29) | unpoured |

Each step needs a licence the maintainer may use for Fenolite (licence rule above), but for C5. Work on
copies.

- **C1** (`routed.PcbDoc`, SHA-256 above): open the document in Altium Designer. Expected: no repair
  prompt; the five tracks, the arc and the three vias of the table show on their layers with their nets
  and sizes; `LED_DRV` and `LED_A` are routed and show no connection line. Settles `H-A-PCB-CU-TRACK` and
  `H-A-PCB-CU-VIA`.
- **C2** (same file): open "Design » Layer Stack Manager". Expected: Top Layer, Mid-Layer 1, Mid-Layer 2
  and Bottom Layer as signal layers with three dielectrics between them (prepreg 0.2 mm, core 1.0 mm,
  prepreg 0.2 mm), and no repair. Settles `H-A-PCB-CU-STACK`.
- **C3** (same file): the two `GND` polygons (Mid-Layer 1 and Bottom Layer) show as outlines without
  copper. Run "Tools » Polygon Pours » Repour All": both fill, and the `GND` pads and the `GND` via connect
  to them. Settles `H-A-PCB-CU-REPOUR`.
- **C4** (same file): the PCB panel in "Nets" mode, or "Design » Classes", lists the net class `PWR` with
  `GND` and `VIN`; the rules editor ("Design » Rules") shows five rules, `Clearance_PWR`, `Clearance`, `Width_PWR`, `Width`
  and `RoutingVias`, and the design rule check runs. Settles `H-A-PCB-CU-CLASS` and `H-A-PCB-CU-RULES`.
- **C5** (`routed.PcbDoc`, no licence needed): upload the document to the Altium 365 Viewer. Expected: the
  tracks, the vias and four copper layers are visible. Settles `H-A-PCB-CU-VIEWER`.
- **C6** (`p0/routed.PcbDoc`, SHA-256 above): open the plane variant. Expected: the Layer Stack Manager
  lists Internal Plane 1 between Top Layer and Mid-Layer 2; the plane is on `GND`; the `GND` pads and the
  `GND` via that cross it show no connection line. The variant holds four tracks (none on the plane) and
  one polygon on Bottom Layer. Settles `H-A-PCB-CU-PLANE`.

- **C7** (script copper, change c0053; `blink_routed.PcbDoc`, SHA-256
  `6691042bc82ef6250d4944f6b08ab8be16b8aeb83d39f0c6975d42cfc332333a`): the copper comes from the design
  script, not from a routed board. Build it outside the repository with
  `fenolite build examples/blink_routed/design.py --out <folder> --target altium --confirm` and open the
  document in Altium Designer. Expected: no repair prompt; 11 tracks and 7 through vias on Top Layer and
  Bottom Layer, on the nets `LED_DRV`, `LED_A` and `GND` (five of the vias are the `GND` stitching row
  along the bottom track); those three nets show no connection line. The step registers no new row: it
  repeats `H-A-PCB-CU-TRACK` and `H-A-PCB-CU-VIA` on a document whose copper a script declared, and it
  stays pending until reported. `tests/unit/cli/test_build_altium_script_copper.py -k protocol` checks the
  digest. The bisection variants below do not apply to this step.

- **C8** (via tenting, change c0112; `~/fenolite-altium-checks/session-2/ViaTenting/blink.PcbDoc`, SHA-256
  `eca2619850f48f745d66d6d8714c7af4ada6b290d816c9f55cc5a1cb57d2a02e`): the blink with four through vias of
  0.8 mm (hole 0.4 mm) on `GND`, 4 mm above the bottom edge, at 10, 15, 20 and 25 mm from the left edge,
  whose first flags byte is `0C`, `2C`, `4C` and `6C`. The sample was built outside the repository on
  2026-10-07 with `fenolite build <copy of examples/blink_2layer>/design.py --out <folder> --target altium
  --confirm --timestamp 2026-10-07T00:00:00Z --seed 112`, the script extended by the four lines
  `design.via("v1", mm(10), mm(26), net=gnd, diameter=mm(0.8), drill=mm(0.4), protection=protect(tenting=False))`,
  `v2` at `mm(15)` with `protect(tenting="front")`, `v3` at `mm(20)` with `protect(tenting="back")` and `v4`
  at `mm(25)` with `protect(tenting=True)`; its folder holds a `README.md` with the steps. Open the
  document in Altium Designer 26 (a menu path or a dialog name may read differently there), select each of
  the four vias and read the "Tented" check boxes of its solder mask settings in the Properties panel.
  Expected: no message on opening; via 1 tented on neither side, via 2 on the top only, via 3 on the bottom
  only, via 4 on both; the Top Solder and Bottom Solder layers show an opening exactly where a via is not
  tented. Question for the report: which sides does Altium Designer 26 show as tented for each via, and
  does the document open without a message? Also report the solder mask expansion the panel shows: the
  written record holds 4 mil on both sides whatever the flags. Settles `H-A-PCB-CU-VIATENT`, which stays
  `INFERRED` until the report is recorded here. The bisection variants below do not apply to this step.

When a step fails, open the variants in order and report the first that fails. They are written outside
the repository with `FENOLITE_ALTIUM_VARIANTS=<folder> uv run pytest
tests/unit/lens/test_altium_copper_golden.py -k variants`: `c0` two layers with tracks and an arc; `c1` adds
the vias; `c2` the stack of four signal layers with the inner tracks; `c3` adds the polygons; `c4` the net
class; `c5` adds the rules (the committed sample); `p0` is the plane variant of C6.

The KiCad oracles (`tests/kicad/altium/test_pcbdoc_copper_oracle.py`, `test_copper_from_oracle.py`,
`test_script_copper_oracle.py`) check only what KiCad's importer reads; they settle no row of this part.

## Part E: the change order (change c0048)

After the maintainer's report of 2026-10-03, "Design » Update PCB Document" on the board example still
proposed to remove the net class `PWR` and to add two component classes, two rooms and two "Supply Nets"
rules. Change c0048 declares the net classes in the schematic, turns the rooms off in the project file and
writes the component class of every sheet into the PCB document
(`docs/formats/altium/schematic-ascii.md`, "Net class directive"; `project.md`, "Class generation";
`pcb-copper.md`, "Classes and rules of the change order").

Two samples, each built into an empty folder outside the repository:

- the board example, `fenolite build examples/altium_hier_board/design.py --out <folder> --target altium
  --altium-sheets modules --confirm`: a top sheet, the module sheets `driver` and `led`, the PCB document;
- the routed sample of Part C (`tests/data/altium/routed/`, SHA-256 in the table of Part C): a single sheet.

Each step needs a licence the maintainer may use for Fenolite (licence rule above). Work on a fresh copy
of each folder: a project file that Altium saved earlier holds its own class options, and Fenolite keeps
an existing project file.

- **E1** (board example): open `altium_hier_board.PrjPcb` and run "Project » Validate PCB Project", without
  opening any dialog first. Expected: both module sheets are under the top sheet in the Projects panel, as
  before the class keys were added, and no message names a directive or a parameter. Settles
  `H-A-ECO-PRJ-KEYS` and repeats `H-A-SCH-HIER-ORDER`.
- **E2** (same project): open "Project » Project Options", tab "Class Generation". Expected: under
  "User-Defined Classes", "Generate Net Classes" is ticked; each of the three sheets has "Component Classes"
  ticked, "Generate Rooms" unticked and the net class scope "None". On the sheets `driver` and `led`, a red
  directive sits on one stub of `GND` (and of `VIN` on `driver`); its hidden parameter `ClassName` is `PWR`.
  Settles `H-A-ECO-PRJ-KEYS`.
- **E3** (same project): from the top sheet run "Design » Update PCB Document altium_hier_board.PcbDoc".
  Expected: no "Remove Net Classes", no change of the members of `PWR`, no "Add Component Classes", no
  change of the members of `driver` and `led`, and no "Add Rooms". Note every group the change order still
  lists, with its entries. The only group expected is "Add Rules" with "Supply Nets" entries, one per net
  with a power port (`GND` and `VIN`); it is absent when Altium's advanced setting
  `Schematic.AutoGenerateSupplyNetsRule` is off. Settles `H-A-ECO-NETCLASS`, `H-A-ECO-COMPCLASS`,
  `H-A-ECO-ROOMS` and `H-A-ECO-SUPPLY`.
- **E4** (routed sample): open `routed.PrjPcb`, validate the project, check "Generate Net Classes" as in
  E2 and that the one sheet has "Generate Rooms" unticked, and run "Design » Update PCB Document
  routed.PcbDoc". Expected: no net class change, no "Add Component Classes" (the document holds the class
  `routed` with `D1`, `R1` and `U1`), no "Add Rooms"; at most the "Supply Nets" rules. Settles
  `H-A-ECO-SHEETCLASS`, and `H-A-ECO-NETCLASS` for a single sheet. If a room is still listed, tick nothing
  and report whether "Generate Rooms" showed ticked: that separates the key from the class.

When E1 fails (a module sheet outside the hierarchy), remove the three `ClassGen…` lines from every
`[Document<n>]` section of a fresh copy and repeat E1: that tells whether the class keys are the cause.
When E3 still lists rooms, note whether "Generate Rooms" was unticked in E2.

Fenolite writes no room and no "Supply Nets" rule: no permitted source holds their records
(`pcb-copper.md`, "Not written"). They are additions; executing them removes nothing.

## Part X: complete board (change c0085)

Every step is reported (2026-10-09, "Reports" below): step X8 in the first report of that day, steps X1 to X7
and X9 to X12 in the second. The sample is the project `board6` (`tests/_altium_board6.py`): the blink design on six
copper layers with one item of every kind that change c0085 writes. The five files are the committed
golden files; `FENOLITE_ALTIUM_BOARD6=<folder outside the repository> uv run pytest
tests/unit/lens/test_altium_pcb_complete.py -k golden` writes the same bytes into a folder to open in
Altium Designer. No file that Altium wrote is committed.

| file | SHA-256 |
|---|---|
| `tests/data/altium/board6/board6.PcbDoc` | `9da3b8c4bd6f1c832251bccfc3eb02e93e714cb179f55af16c08a0ec21b83e8a` |
| `tests/data/altium/board6/board6.PcbLib` | `9d09f5126ba6aad6026f4c85fa2899c908eaa363aeaec1b58b59e64a11666e22` |
| `tests/data/altium/board6/board6.PrjPcb` | `75e7078fdb8fc79b606ad0c0a3acf30103faada43dc440a7fb01e5daad2f7219` |
| `tests/data/altium/board6/board6.SchDoc` | `36e9850be729dd5e91e14c9b0adab1fb9ac7ef036154839f94d279a12ffc2118` |
| `tests/data/altium/board6/board6.SchLib` | `6111fd9db8fda9f778cd3dcfc61d89d2bd37a8bfc91edd5f072c38e7d3da03ac` |

`board6.SchDoc` and `board6.SchLib` are the default build of change c0086, with the symbols' own graphics
(they were committed by c0085 with rectangle bodies, `7b5a19f0…` and `c88e8978…`, and never reported on);
`--altium-symbols generic` gives that form. The PCB document, the PCB library and the project file did not
change.

Values to compare (millimetres from the outline's upper-left corner, Y down, as the sample states them):

| item | value |
|---|---|
| copper layers, top to bottom | Top Layer (signal), Mid-Layer 1 (signal), Internal Plane 1 (plane, net `GND`), Mid-Layer 3 (signal), Mid-Layer 4 (signal), Bottom Layer (signal) |
| copper thickness | 0.035 mm outer, 0.0175 mm inner |
| dielectrics, top to bottom | 0.11 mm `FR-4 prepreg` 4.2; 0.2 mm `FR-4 core` 4.5; 0.8 mm `FR-4 prepreg` 4.2; 0.2 mm `FR-4 core` 4.5; 0.11 mm `FR-4 prepreg` 4.2 |
| via 1 | (11.2, 18.75), net `VIN`, Top Layer to Bottom Layer, 0.6 mm with a 0.3 mm hole |
| via 2 | (32.8, 9), net `LED_A`, Top Layer to Mid-Layer 1 (blind) |
| via 3 | (20, 24), net `GND`, Mid-Layer 1 to Internal Plane 1 (buried) |
| text 1 | `Tensão 5 V`, Top Overlay, at (22, 4), height 1 mm, stroke 0.15 mm, 0 degrees |
| text 2 | `BOARD6 REV A`, Bottom Overlay, at (30, 27), height 1.2 mm, stroke 0.18 mm, mirrored |
| text 3 | `ASSEMBLY TOP`, Mechanical 13, at (3, 28), height 0.8 mm, stroke 0.12 mm |
| text 4 | `BOTTOM`, Mechanical 14, at (47, 12), height 1 mm, 90 degrees, mirrored |
| keep-out | rectangle (22, 12) to (30, 17) on the Keep-Out layer; restrictions: vias and tracks (value 3, in the keys `KEEPOUTRESTRICTIONS` and `KEEPOUTRESTRIC`) |
| hole | (4, 25), 3.2 mm, not plated, no copper |
| polygons | `GND` on Top Layer and `GND` on Bottom Layer, each 1 mm inside the outline, unpoured |
| graphics | a line on Mechanical 13, an arc, a circle and a filled triangle on Top Overlay, a rectangle on Mechanical 14 |

Steps; report one generic outcome per step (`as expected`, or what differed in one sentence), the tool as
`AD <major>.<minor>` and the date.

1. **X1** Open `board6.PrjPcb` and `board6.PcbDoc`. Expected: no repair prompt and no message in the
   Messages panel (`H-A-PCB-DOC-OPEN`).
2. **X2** Open Design » Layer Stack Manager. Expected: six copper layers in the order and with the kinds of
   the table (`H-A-PCBX-STACK`).
3. **X3** Read the thickness and the material of each dielectric. Expected: the table's values
   (`H-A-PCBX-STACK`).
4. **X4** Select each of the three vias and read its start and end layer; open the drill pairs of the
   stack. Expected: through, blind (top to mid 1), buried (mid 1 to the plane), and three drill pairs
   (`H-A-PCBX-VIASPAN`).
5. **X5** Read the four texts, their layers, heights and rotations, and where each stands relative to the
   table's position (the table gives the record's position; say which corner of the text lies there).
   Expected: the table (`H-A-PCBX-TEXT`).
6. **X6** Select the keep-out and read its restrictions. Expected: vias and tracks on, the three others off
   (`H-A-PCBX-KEEPOUT`).
7. **X7** Select the hole; read plated and the hole size. Expected: not plated, 3.2 mm (`H-A-PCBX-HOLE`).
   The sample holds no slot: the model's board hole is round.
8. **X8** Component bodies (change c0121; added on 2026-10-07; reported on 2026-10-09). This step belongs to **session 2**
   of the maintainer's Altium work, with Altium Designer 26: session 1 is the folder he already has, and
   nothing is added to it. Change c0085 cut bodies; change c0121 writes the extruded ones on request
   (`--altium-bodies extruded`), and **the option stays `off` until step X8 is reported** (it was reported on 2026-10-09; the default is still
   `off`, and making `extruded` the default is the maintainer's decision, not taken). The step runs on
   a sample of its own, `body2` (`tests/_altium_body2.py`), so that a body that Altium refused cannot hide
   the answers of the other steps on `board6`.

   What is known and what is not: the keys of a body were measured on 1272 saved extruded bodies of five
   public documents of three repositories, 1265 of them from one repository
   (`docs/formats/altium/pcb-bodies.md`, "Written form of an extruded body"); nothing that Fenolite writes
   for a body was opened in Altium. Two keys have no rule, `MODELID` and `MODEL.CHECKSUM`: the file set
   `saved` holds stand-ins for them (a GUID derived by Fenolite, and `0`), and the file set `short` holds
   no model key at all (21 keys instead of 35; the form that a third-party writer reports of its own
   bodies, S-0571). One session settles both. The steps were written from Altium's documentation (S-0303,
   S-0570); a menu path or a dialog name may read differently in Altium Designer 26.

   Files: `FENOLITE_ALTIUM_BODY2=<folder outside the repository> uv run pytest
   tests/unit/lens/test_altium_bodies.py -k golden` writes both sets and a `README.md`. On the
   maintainer's machine they lie in `~/fenolite-altium-checks/session-2/X8-bodies/` (`saved/`, `short/`).
   The set `saved` is the committed sample; the set `short` is built for this step and is not committed.
   It differs from `saved` in `body2.PcbDoc` only.
   Change c0148 (2026-10-08) added bit 0x20 to every pin's `PINCONGLOMERATE`: both schematic files of both
   sets were written again, and the folder of session 2 still holds the earlier ones (`body2.SchDoc`
   `cfea41d6…`, `body2.SchLib` `53cc1b8f…`), which differ in that bit alone.

   | file | SHA-256 |
   |---|---|
   | `tests/data/altium/body2/body2.PcbDoc` | `bee5811bc7a1b43c589722a5b95d1bf1a784aa78f38a5abad8e035156fded2f2` |
   | `tests/data/altium/body2/body2.PcbLib` | `9432b8ab5f7801c7c9399a9e943dd272d4b02d2fbfa0586cc34c53e3666b991d` |
   | `tests/data/altium/body2/body2.PrjPcb` | `e0b2cca3f3635c5ec50edca85d6dbae0d527a03d3e94447945e874a607769591` |
   | `tests/data/altium/body2/body2.SchDoc` | `f5598952ca794defc855b6e3cf6d75f0a6813d2b277016b305da595832996e48` |
   | `tests/data/altium/body2/body2.SchLib` | `a8c584c2a9997ec642b5fd5a1e2cc0fff62ddbe9c5334804b69dce5c5758363e` |
   | `short/body2.PcbDoc` | `6becb1923051aa3b312cc97eaf8230fab0a50b30d7187253c55411ebe3e8175f` |
   | `short/body2.PcbLib` | `9432b8ab5f7801c7c9399a9e943dd272d4b02d2fbfa0586cc34c53e3666b991d` |
   | `short/body2.PrjPcb` | `e0b2cca3f3635c5ec50edca85d6dbae0d527a03d3e94447945e874a607769591` |
   | `short/body2.SchDoc` | `f5598952ca794defc855b6e3cf6d75f0a6813d2b277016b305da595832996e48` |
   | `short/body2.SchLib` | `a8c584c2a9997ec642b5fd5a1e2cc0fff62ddbe9c5334804b69dce5c5758363e` |

   Values to compare. The model holds a fourth body, which names a 3D model: it is reported by the build
   and not written, so the document holds three.

   | body | footprint | board side | layer | overall height | standoff height | outline | identifier |
   |---|---|---|---|---|---|---|---|
   | 1 | `U1` | Top | Mechanical 13 | 2.5 mm | 0 mm | a rectangle 7 mm by 7 mm | empty |
   | 2 | `D1` | Bottom | Mechanical 14 | 1 mm | 0 mm | a rectangle 4 mm by 3 mm | `LED` |
   | 3 | `R1` | Top | Mechanical 13 | 4 mm | 0.5 mm | six points, an L | `STANDOFF` |

   - **X8.1** Open `saved/body2.PrjPcb` and `body2.PcbDoc`. Expected: no repair prompt and no message in
     the Messages panel (`H-A-PCBX-BODY-OPEN`).
   - **X8.2** Open the PCB panel in the mode "3D Models" (or select each body in 2D). Expected: three
     bodies, each owned by the footprint of the table.
   - **X8.3** Read in the properties of each body: identifier, board side, layer, overall height, standoff
     height. Expected: the table.
   - **X8.4** Switch to the 3D view. Expected: three solids at the heights of the table, body 2 below the
     board.
   - **X8.5** Repeat X8.1 to X8.4 with the folder `short/` (`H-A-PCBX-BODY-SHORT`).
   - **X8.6** Save `saved/body2.PcbDoc` under another name outside the repository and run
     `FENOLITE_ALTIUM_BODY2_SAVED=<that file> uv run pytest tests/unit/lens/test_altium_bodies.py -k
     saved_report -s`. It prints counts only: the bodies per storage, how many keep the `MODELID` that was
     written, how many hold a `MODEL.CHECKSUM` other than 0, and the number of keys per body
     (`H-A-PCBX-BODY-ID`; a measurement, not a pass or fail).
   - **X8.7** Open `saved/body2.PcbLib`, select the footprint of `U1` and read the heights of its body.
     Expected: one body, 2.5 mm overall, 0 mm standoff (`H-A-PCBX-BODY-LIB`).

   Report one generic outcome per step, as for every step of this part. No file that Altium wrote is
   committed. What the report decides: with X8.1 to X8.4 as expected, `saved` stays the form and the
   default of the option may become `extruded` (a one-line change with its changelog line, outside change
   c0121); with only X8.5 as expected, the form becomes `short`; with neither, the option stays off and
   the report's sentence is the next fact row. An author report never moves an operation out of
   `experimental`.
9. **X9** Open Tools » Polygon Pours » Polygon Manager; note the state of the two polygons; run Repour All;
   note the state and any message. Expected: unpoured, then poured, no message (`H-A-PCBX-REPOUR`).
10. **X10** Save the document under another name and report only its size and whether Altium asked
    anything on save.
11. **X11** (added on 2026-10-06 with the second keep-out key) The keep-out's record holds two keys with
    the restrictions: `KEEPOUTRESTRICTIONS`, which Altium saves, and `KEEPOUTRESTRIC`, which is written for
    KiCad's importer and which Altium does not write itself. Confirm that the board loaded without a
    message about the keep-out (step X1) and that its restrictions are vias and tracks only (step X6)
    although the record holds the second key; then save the document, reopen it and read the restrictions
    again. Expected: no message, the same two restrictions before and after the save
    (`H-A-PCBX-KEEPOUT`).
12. **X12** Copper locks (change c0108; added on 2026-10-07; reported on 2026-10-09). Build a document whose model holds
    one locked track, one locked arc and one locked via beside unlocked ones: the routed sample with those
    three items set `locked=True` (`tests/unit/backends/altium/test_pcbdoc_copper.py -k locked` builds it
    in memory; write it to a folder outside the repository). Open it in Altium Designer 26, select each of
    the three items and read the property "Locked"; select one unlocked track, arc and via too. Expected:
    the three items locked, the others not, and no message on load (`H-A-PCB-CU-LOCK`). Then try to drag
    the locked track: Altium should ask before it moves a locked primitive. Report one generic outcome per
    item kind. Before this step was reported, the lock bit rested on a public reader's statement and on
    Fenolite's own reader, and the row was `INFERRED`.

A step that fails refutes the row it names: the row keeps its id and gets a registered successor. An
author report never moves an operation out of `experimental`.

## Part U: rules (change c0084)

Change c0084 writes the rules of the design by kind and scope (`docs/altium.md`, "Rules";
`docs/formats/altium/pcb-copper.md`, "Rule kinds lowered"). Steps U1 to U6 were reported on 2026-10-09
("Reports" below): the four rows they settle are author reports.

**Files.** The routed sample of Part C with one rule of every `exact` kind, the class `PWR` (`GND`,
`VIN`) and two planted violations, plus the same rules as a rule file. They are built outside the
repository and none is committed. On the maintainer's machine they lie in
`~/fenolite-altium-checks/c0084-part-u/` (the folder `rules` and the script `build_part_u.py`); build
them again with `uv run python ~/fenolite-altium-checks/c0084-part-u/build_part_u.py <folder>`, run from
the repository, which uses `tests/_altium_copper.py` and `rulemap.write_rule_file`. Built on 2026-10-06:

| file | SHA-256 |
|---|---|
| `rules/routed.PcbDoc` | `abe6d0b13c6f336577f5ead4e7054d513793c3eee8c37bbb3901c38d5b6d51a7` |
| `rules/routed.PcbLib` | `693d03ad18bc987664a681933fab96e3a01aa2477a8e9181cb1f6fd0e2355738` |
| `rules/routed.PrjPcb` | `9c35d817e1d0ab294f8ad72674d2e2c4f470d449b71b998eba0886b78b7b62f0` |
| `rules/routed.RUL` | `aac210fee08abeaafd56351109bba5116f4bc09b0c20d672a5c9ad6baae7d4d5` |
| `rules/routed.SchDoc` | `5c7ce5f3352ce91e6970dd49753f03d9f0b39c539f56b8a79b59d5c5679e7557` |
| `rules/routed.SchLib` | `db7d0c5b55210c9f7a113120595fa48427c43263cff13c76452ed44312dd0e07` |

The library, the project file and the schematic are the committed files of Part C; only the PCB document
differs, and only in `Rules6`.

**The rules written**, as Fenolite reads them back from `rules/routed.PcbDoc`. Every row but
`Clearance_PWR` is a rule of the design; `Clearance_PWR` is the rule of the net class, which the board-wide
rule `Clearance` now precedes. `routed.RUL` holds the nine records of the design's rules, not
`Clearance_PWR`.

| Altium rule kind | name | priority | first scope | second scope | values |
|---|---|---|---|---|---|
| Clearance | `Clearance_net_LED_DRV_to_net_LED_A` | 1 | `InNet('LED_DRV')` | `InNet('LED_A')` | 59.0551 mil (1.5 mm) |
| Clearance | `Clearance` | 2 | `All` | `All` | 5.9055 mil (0.15 mm) |
| Clearance | `Clearance_PWR` | 3 | `InNetClass('PWR')` | `All` | 7.874 mil (0.2 mm) |
| Width | `Width_PWR` | 1 | `InNetClass('PWR')` | `All` | minimum and preferred 23.622 mil (0.6 mm), maximum 78.7402 mil (2 mm) |
| Width | `Width` | 2 | `All` | `All` | minimum 5.9055 mil (0.15 mm), preferred 9.8425 mil (0.25 mm), maximum 78.7402 mil (2 mm) |
| Routing Via Style | `RoutingVias` | 1 | `All` | `All` | diameter 19.685 / 23.622 / 31.4961 mil (0.5 / 0.6 / 0.8 mm); hole 9.8425 / 11.811 / 15.748 mil (0.25 / 0.3 / 0.4 mm) |
| Hole Size | `HoleSize` | 1 | `All` | `All` | minimum 11.811 mil (0.3 mm), maximum 236.2205 mil (6 mm), absolute |
| Board Outline Clearance | `BoardOutlineClearance` | 1 | `All` | `All` | 19.685 mil (0.5 mm) |
| Hole To Hole Clearance | `HoleToHoleClearance` | 1 | `All` | `All` | 9.8425 mil (0.25 mm), stacked microvias not allowed |
| Minimum Annular Ring | `MinimumAnnularRing` | 1 | `All` | `All` | 4.9213 mil (0.125 mm) |

**Planted violations.** (1) The two `VIN` tracks are 0.5 mm wide, below the 0.6 mm minimum of `Width_PWR`.
(2) The two pads of `R1` carry `LED_DRV` and `LED_A` and lie closer than the 1.5 mm of
`Clearance_net_LED_DRV_to_net_LED_A`; the end of the `LED_DRV` track and the `LED_A` via at those pads are
inside that distance too, so the rule can be named by more than one violation. How many violations Altium
counts for each is not known: the steps ask which rules are named.

Each step needs a licence the maintainer may use for Fenolite (licence rule above). Work on copies.

- **U1** (`rules/routed.PrjPcb`, `rules/routed.PcbDoc`): open the project and the PCB document; open
  "Design » Rules". Expected: no repair prompt; one entry per row of the table above, under the kind of its
  row. Settles `H-A-RULE-KINDS` with U2 and U3.
- **U2** (same file): for each entry, compare the values with the table. Expected: equal.
- **U3** (same file): confirm that no kind of the table shows only Altium's default rule in place of
  the written one, and that Altium added no second rule of a written kind.
- **U4** (same file): read each entry's scope text. Run "Tools » Polygon Pours » Repour All", then "Tools »
  Design Rule Check" with the default report. Expected: the scopes of the table as written; among the
  kinds of the table, only `Width_PWR` and `Clearance_net_LED_DRV_to_net_LED_A` are named by violations.
  Report the number of violations per rule, and any other rule of the table that is named. Settles
  `H-A-RULE-SCOPE`.
- **U5** (same file): select one of the two `VIN` tracks and read which Width rule its violation names.
  Expected: `Width_PWR`, not `Width`. Settles `H-A-RULE-PRIORITY`.
- **U6** (a copy of `rules/routed.PcbDoc`, and `rules/routed.RUL`): in the rules editor delete the rules
  of one kind (for example Width), import `routed.RUL` (right-click in the rules tree, "Import Rules…",
  choose that kind), and compare the list with U1. Expected: the import gives no message and the rules of
  the kind are those of U1. Settles `H-A-RULE-FILE`.

The maintainer reports one generic outcome per step (`as expected`, or what differed in one sentence), the
tool as `AD <major>.<minor>` and the date. No file that Altium wrote is committed. A step that fails
refutes the row it names: the row keeps its id and gets a registered successor.

### Rules against KiCad's importer

`tests/kicad/altium/test_rules_oracle.py` builds the routed sample with one rule of every `exact` kind and
imports its PCB document with `kicad-cli pcb import --format altium` (10.0.6, macOS, 2026-10-06, 3 passed).
`pcb import` writes the board file only, and KiCad keeps design-rule minimums and net classes in the
project file, so the oracle is narrow:

| Altium rule kind | what the import shows |
|---|---|
| Clearance | read: each zone of the imported board gets the clearance of the first Clearance rule (0.17 mm with the design's rule, Fenolite's 0.2 mm default without it) |
| Width, Routing Via Style, Hole Size, Board Outline Clearance, Hole To Hole Clearance, Minimum Annular Ring | loaded without an error or a warning; no value of them is in the imported board, so the import says nothing about them |

A pass shows that KiCad's importer accepts the records; it settles no Altium row and raises no level.

## Part G: footprint items of a rewrite (change c0126)

Reported on 2026-10-09 ("Reports" below). Change c0126 puts the graphics and free texts of a footprint and the corner ratio of a pad
into the model; a PCB document that Fenolite reads and writes again keeps the lines, arcs, fills, regions,
designator and comment of its components on the overlays and on Mechanical 1 to 16. This part asks whether
Altium Designer shows the written primitives as parts of their component. The row it settles,
`H-A-PCBX-FPGFX-AD`, is an author report since the report of 2026-10-09. The steps are written for Altium Designer 26 from Altium's public documentation; a menu path or a
panel name may read differently in the version that is run.

**Files.** Built outside the repository and never committed:
`FENOLITE_ALTIUM_PART_G=~/fenolite-altium-checks/c0126-part-g uv run pytest
tests/unit/backends/altium/test_part_g.py` (run from the repository; the test refuses a folder inside it)
writes four things there:

- `original/`: the committed project `board6` (`tests/data/altium/board6/`, Part X), as it is.
- `rewrite/`: the import of `original/board6.PrjPcb` written again by `AltiumBackend().write` (the write of
  a model, with `rewrite=True` as RT-A3 writes it). The schematic is generated from the circuit, and no PCB
  library is written: a rewrite derives no library from an imported model (design of c0126, decision 7).
- `rewrite-mech/`: the same model with two lines added to `R1`, one on Mechanical 1 and one on Mechanical 5
  (2 mm long, 0.1 mm wide, 2 mm above and below the footprint's origin), written the same way.
- `expected.md`: the values the steps compare, read back from the written files with Fenolite's own reader
  (the tracks and arcs of each component per layer, the corner radius of four rounded pads, the place,
  layer, height and visibility of each designator and comment) and the SHA-256 of every file.

Built on 2026-10-08 on the tree of change c0126; the values of `expected.md` of that build:

| component | layer | primitives in `rewrite/` |
|---|---|---|
| D1 (bottom side) | Bottom Overlay | 2 arcs |
| D1 | Mechanical 14 | 1 arc |
| D1 | Mechanical 16 | 4 tracks |
| R1 | Top Overlay | 2 tracks |
| R1 | Mechanical 13, Mechanical 15 | 4 tracks each |
| U1 | Top Overlay | 2 tracks |
| U1 | Mechanical 13, Mechanical 15 | 4 tracks each |

`rewrite-mech/` holds the same and one track of `R1` on each of Mechanical 1 and Mechanical 5. The four
rounded pads `R1-1`, `R1-2`, `U1-1` and `U1-10` have a corner radius of 50 %. The designators of the three
components are shown and their comments hidden, as in the original. `fenolite check` exits 0 on each of the
three folders with the same stages; the generated schematic of a rewrite gives no
`erc.lite.power-undriven`, which the original's schematic gives.

Steps; report one generic outcome per step (`as expected`, or what differed in one sentence), the tool as
`AD <major>.<minor>` and the date.

1. **G1** Open `original/board6.PrjPcb` and `rewrite/board6.PrjPcb`, each with its PCB document, side by
   side. Expected: no repair prompt, and each component shows the same silkscreen outline in both
   (`H-A-PCBX-FPGFX-AD`).
2. **G2** In `rewrite/board6.PcbDoc`, open the PCB List panel (or PCB Filter) and list the tracks and arcs
   whose component is `U1`, then `R1` and `D1`. Expected: the counts and layers of the table above.
3. **G3** Drag `R1` by about 5 mm. Expected: its overlay and mechanical lines move with it. Undo.
4. **G4** Drag `R1` again and press `L` to flip it to the other side. Expected: its Top Overlay lines go to
   the Bottom Overlay and its Mechanical 13 and 15 lines to their layer pairs, if the pairs are set. Undo.
5. **G5** Select the pads `R1-1`, `R1-2`, `U1-1` and `U1-10` and read the corner radius of each in the
   Properties panel. Expected: 50 %.
6. **G6** Compare the place and the visibility of the designator and the comment of each component with the
   original. Expected: equal (the table "Designators and comments" of `expected.md` gives the text records'
   positions).
7. **G7** Open `rewrite-mech/board6.PcbDoc`, open the View Configuration panel and list the mechanical
   layers. Expected: Mechanical 1 and Mechanical 5 are listed and shown, and the two lines of `R1` lie on
   them.

## Reports

### 2026-10-03, `AD 26.5`, Part D

- Tool: Altium Designer 26.5.0 under a trial licence on the maintainer's own PC, a licence the maintainer
  may use for Fenolite (`LEGAL.md`, block A). Label: `ALTIUM-VERIFIED(author-report; AD 26.5; 2026-10-03;
  no artefact)`.
- Files: Fenolite's authored samples only, from local copies; no file opened or saved in the session
  enters the repository.

Outcome per step:

- **D1, library.** The first `blink.PcbLib` failed with a "catastrophic" error, and so did a library
  without footprints. After the library fix, eight variants in the form Altium saves opened and looked
  correct: an empty library, a footprint without primitives, one line, one rounded surface pad, one
  rectangular surface pad, one through-hole pad, one arc, one full footprint and the three footprints of
  the blink library. Confirms `H-A-PCB-LIB-OPEN` and `H-A-PCB-GRAPHICS`. Sizes and holes were not compared
  with the pad table, so `H-A-PCB-PAD` stays pending with this observation. Whether the project lists the
  library (`H-A-PCB-PRJ`) and the long name (`H-A-PCB-LIB-NAME`) are not reported.
- **D1, project.** The blink project compiles. Its ERC messages follow from the example circuit: `VIN` has
  one pin, and inputs are unconnected, `U1` pins 11 and 12 among them. Recorded as data for
  `H-A-SCHLIB-SCHDOC`; no net row is confirmed by it.
- **D2.** Not run: the change order into a new blank PCB document (`H-A-PCB-ECO` and `H-A-SCH-ECO` stay
  pending, with the observation of D3).
- **D3, first form.** `blink.PcbDoc` in its first form (SHA-256 `2b8b3379…b256`) failed with a
  "catastrophic" error.
- **D3, the form Altium saves.** After the document fix the six bisection documents open with no error:
  the outline alone, one net, one component without pads, with its pads, with its designator and comment
  texts, and the full sample. The blink project opens with its `blink.PcbDoc` (SHA-256 `5e084d85…894f`).
  The 137-byte text records are accepted. Confirms `H-A-PCB-DOC-OPEN`.
- **D3, change order.** "Design » Update PCB Document" ran without error on the blink project against
  Fenolite's own `blink.PcbDoc`: Altium matched every component and reported no difference, and "Validate
  Changes" passed. The schematic's unique ids agree with the board's `SOURCEUNIQUEID`, and the footprints
  and nets of the schematic agree with the document. Confirms `H-A-PCB-DOC-LINK` and `H-A-PCB-DOC-NETS`.
  The side, rotation and pads of `D1` were not reported, so `H-A-PCB-DOC-BOTTOM` stays pending; whether
  the project lists the PCB library is not reported (`H-A-PCB-PRJ`).

### 2026-10-03, `AD 26.5`, Part C

- Tool: Altium Designer 26.5 under a trial licence on the maintainer's own PC, a licence the maintainer
  may use for Fenolite (`LEGAL.md`, block A). Label: `ALTIUM-VERIFIED(author-report; AD 26.5; 2026-10-03; no artefact)`.
- Files: the bisection variants `c0` to `c5` and `p0` of the routed sample, written outside the repository;
  no file opened or saved in the session enters the repository. `c5` is the committed `routed.PcbDoc`.

Outcome per step:

- **C1, tracks, arc and vias.** `c0` (two layers, tracks and an arc), `c1` (with the vias) and `c2` (four
  layers, tracks on both mid layers) open and look correct. The nets of the tracks, the sizes of the vias
  and the connection lines were not reported, so `H-A-PCB-CU-TRACK` and `H-A-PCB-CU-VIA` stay pending with
  this observation.
- **C2, stack.** `c2` opens with its four signal layers and looks correct. The Layer Stack Manager was not
  reported, so `H-A-PCB-CU-STACK` stays pending with this observation.
- **C3, polygons.** `c3` opens and looks correct with its two unpoured `GND` polygons, and "Tools » Polygon
  Pours » Repour All" filled both. Confirms `H-A-PCB-CU-REPOUR`.
- **C4, class and rules.** In `c4` the net class `PWR` shows with its member nets. In `c5` the Clearance,
  Width and Routing Via Style rules show correctly in the rules editor, and the design rule check ran to
  the end with them. Confirms `H-A-PCB-CU-CLASS` and `H-A-PCB-CU-RULES`.
- **C5, Viewer.** Not reported (`H-A-PCB-CU-VIEWER` stays pending).
- **C6, plane.** `p0` opens, and the internal plane appears to carry `GND`. The maintainer saw `GND` on the
  plane but did not find the plane's net in the Layer Stack Manager and did not open the split-plane
  dialog; the connection lines were not reported. `H-A-PCB-CU-PLANE` stays pending with this observation.

No step named a fault, so no fact of `docs/formats/altium/pcb-copper.md` changed.

The schematic steps of the same session are recorded in `docs/evidence/altium-schematic.md`, "Reports".

### 2026-10-03, `A365 Viewer`, Part P

- Tool: the free Altium 365 Viewer (web), `A365 Viewer`; it shows no version and needs no licence. Label:
  `ALTIUM-VERIFIED(author-report; A365 Viewer; 2026-10-03; no artefact)`.
- File: `blink.PcbDoc`, uploaded alone from a local copy that the maintainer built from the committed
  sample after the document fix (the form Altium saves). The committed bytes are those of the table above:
  the SHA-256 on this page, `f0940168…3c01`, equals the golden file's. The digest of the uploaded copy was
  not reported. Only Fenolite's authored sample was uploaded.

Outcome per step:

- **P1.** The document opened in the Viewer and was rendered, with no refusal. Confirms
  `H-A-PCB-DOC-VIEWER`. The report lists no object: the pad shapes, the graphics per layer and the side of
  `D1` were not reported, so it adds nothing to `H-A-PCB-PAD` or `H-A-PCB-DOC-BOTTOM`, which stay pending.
- **P2.** Not reported: the Zip of the project.

The report names no fault, so no fact and no golden file changed. Step C5 (the routed sample in the
Viewer, `H-A-PCB-CU-VIEWER`) is not part of this report.

### 2026-10-04, `AD 26.5`, Part E

- Tool: Altium Designer 26.5.0 under a trial licence on the maintainer's own PC, a licence the maintainer
  may use for Fenolite (`LEGAL.md`, block A). Label: `ALTIUM-VERIFIED(author-report; AD 26.5; 2026-10-04; no artefact)`.
- Files: the two samples of Part E as first built for it, outside the repository: the board example with
  module sheets, and the routed sample as it was then (schematic `7fe119a7…74be`, project file
  `8bcaa84d…2f04`, document `aee17146…0fef`): with the net class directives and `[PrjClassGen]`, without a
  class key in the project file and without a component class in the document. No file opened or saved in
  the session enters the repository.

Outcome per step:

- **E1, hierarchy.** The project of the board example opens and "everything is right": every component of
  both module sheets matches its board component in the change order. The Projects panel was not
  described. Confirms `H-A-ECO-PRJ-KEYS` by its effect and repeats `H-A-SCH-HIER-ORDER`.
- **E2, options.** Not reported: the ticks of the tab "Class Generation" were not read.
- **E3, change order of the board example.** It lists only "Add Rules (2): Supply Nets", each with a
  voltage of 0 and a net scope. No net class removal, no component class, no room. Confirms
  `H-A-ECO-NETCLASS`, `H-A-ECO-COMPCLASS`, `H-A-ECO-ROOMS` and `H-A-ECO-SUPPLY`.
- **E4, change order of the flat routed sample.** It lists "Add Component Classes (1): `routed`", "Add
  Rooms (1): Room `routed`", scoped by that component class, and "Add Rules (2): Supply Nets". No net class
  removal: confirms `H-A-ECO-NETCLASS` for a single sheet.

Reading of E4, and what changed:

- In a flat project Altium derives one component class named after the single sheet, with every
  component, and a room for it. The two samples differ in two ways for rooms: the board example's project
  file held `ClassGenCCAutoRoomEnabled=0` in each schematic section and its document held the classes of
  its sheets; the routed sample had neither. Altium's documentation ties the room to the option "Generate
  Rooms" of the sheet and scopes it by the sheet's component class (S-0310), so the key is the likelier
  cause and the missing class the lesser one; the report does not separate them.
- Fenolite now writes both for every build with a PCB document: one component class per sheet that holds
  a component (named after the module, or after the sheet for the top or single sheet), and the three
  class keys in every schematic section (`H-A-ECO-SHEETCLASS`, pending until the repeat below). The routed and blink golden files
  are rebuilt, and step E4 is to be repeated on the rebuilt routed sample.
- The "Supply Nets" rules stay the one accepted difference: no permitted source holds their record.

### 2026-10-04, `AD 26.5`, Part E, repeat

- Tool: Altium Designer 26.5.0 under a trial licence on the maintainer's own PC, a licence the maintainer
  may use for Fenolite (`LEGAL.md`, block A). Label: `ALTIUM-VERIFIED(author-report; AD 26.5; 2026-10-04; no artefact)`.
- Files: the two samples of Part E, built again outside the repository after the report above: the board
  example with module sheets, and the flat routed sample. Each holds a component class for every sheet
  that holds a component, and the three class keys in every schematic section. The routed sample is the
  build of the committed golden files (table of Part C: schematic `7fe119a7…74be`, project file
  `9c35d817…62f0`, document `158cc00b…931f`); the digests of the opened copies were not reported. No file
  opened or saved in the session enters the repository.

Outcome per step:

- **E1, hierarchy.** Not reported apart: both projects opened, and each change order was run.
- **E2, options.** Not reported: the ticks of the tab "Class Generation" were not read.
- **E3, change order of the board example.** It lists only "Add Rules (2): Supply Nets". No net class
  removal, no component class to add, no room. Repeats `H-A-ECO-NETCLASS`, `H-A-ECO-COMPCLASS`,
  `H-A-ECO-ROOMS` and `H-A-ECO-SUPPLY` on the build with a class for every sheet.
- **E4, change order of the flat routed sample.** It lists only "Add Rules (2): Supply Nets". No net class
  removal, no component class to add, no room. Confirms `H-A-ECO-SHEETCLASS`, and `H-A-ECO-ROOMS` and
  `H-A-ECO-NETCLASS` for a single sheet.

Reading of the repeat:

- The component class and the room that the first flat build was offered are gone once the document holds
  the class of the sheet and the sheet's section holds `ClassGenCCAutoRoomEnabled=0`. The two were written
  together, so the report still does not separate the key from the class; `H-A-ECO-SHEETCLASS` and
  `H-A-ECO-ROOMS` claim the pair, not either alone.
- `H-A-ECO-PRJ-KEYS` stays confirmed by its effect only: step E2 was reported in neither session.
- `H-A-ECO-SUPPLY` keeps its scope, builds with module sheets; that the flat build lists the same two
  rules and nothing else is recorded as an observation.
- No step named a fault, so no fact and no golden file changed. The SHA-256 values that this page names
  for committed files were compared with the golden files on the day of this record and are equal.

### 2026-10-09, `AD 26.5`, Parts U, X (step X8), G and V

- Tool: Altium Designer 26.5, the installation of session 2 on the maintainer's own PC, a licence he may use
  for Fenolite (`LEGAL.md`, block A). Reported by the maintainer on 2026-10-09 for his sessions of
  2026-10-07 and 2026-10-08 (S-0724). Label: `ALTIUM-VERIFIED(author-report; AD 26.5; 2026-10-09; no
  artefact)`.
- Files: Fenolite's own files of the tables of Parts U, X (step X8) and G, from his session folders, and for
  Part V a board of his own drawing. No file opened or saved in the sessions enters the repository; the
  digests of the opened copies were not reported.

Outcome per step:

- **U1 to U6, rules (change c0084).** Each as expected: the rules editor lists the written rules under
  their kinds with the values of the table, no kind holds only Altium's default rule, the scopes read as
  written and the rule check names only `Width_PWR` and `Clearance_net_LED_DRV_to_net_LED_A` among the
  written kinds, the planted `VIN` track is judged by `Width_PWR`, and the rule file imports without a
  message. Confirms `H-A-RULE-KINDS`, `H-A-RULE-SCOPE`, `H-A-RULE-PRIORITY` and `H-A-RULE-FILE`. The number
  of violations per rule was not given.
- **X8.1 to X8.4, bodies, set `saved` (change c0121).** As expected. Confirms `H-A-PCBX-BODY-OPEN`.
- **X8.5, set `short`.** As expected. Confirms `H-A-PCBX-BODY-SHORT`.
- **X8.6, the saved file.** Done; the counts that `-k saved_report` prints were not given, so
  `H-A-PCBX-BODY-ID`, a measurement, stays pending with this observation.
- **X8.7, the library body.** As expected. Confirms `H-A-PCBX-BODY-LIB`.
- **G1 to G7, footprint items of a rewrite (change c0126).** Each as expected. Confirms `H-A-PCBX-FPGFX-AD`.
- **Part V, vias without inner pads (change c0132, task 4.3).** A four-layer board of the maintainer's own
  drawing whose inner layers have the ids 3 and 5, one via used on the outer layers only, "Remove Unused
  Pad Shapes" run for vias, saved; its via record read with `fenolite`. As expected: the table at 209 holds
  1 at 211 and at 213 and 0 elsewhere, an index by layer id. Confirms `H-A-IMP-VIA-PADLESS`. The second
  question of the task, the nine further bytes of the long record, was not reported.

Reading of the report:

- No step named a fault, so no fact of the format pages and no golden file changed, and no row is refuted.
- Step X8 decides, by its own rule (Part X above): with X8.1 to X8.4 as expected, the file set `saved`
  stays the written form. The default of `--altium-bodies` may become `extruded` by a one-line change with
  its changelog line, outside change c0121; it is not made here and the option stays `off`.
- An author report moves no write kind out of `experimental`: every Altium write stays experimental.

### 2026-10-09, `AD 26.5`, Part D, steps D4 to D6 (confirmation)

The maintainer confirmed on 2026-10-09 (S-0724) his answer of 2026-10-08 to steps D4 to D6 of
`openspec/changes/c0088-altium-light-drc/design.md` ("Session 2 of 2026-10-08" below, S-0616) as his
report of those steps: done as expected for what they ask, the count N reported (N = 0 on `-03`) and the
pad size read. The follow-up that the answer called for is change c0152, opened and closed since (Altium's
own comparison passes the pairs; `docs/evidence/altium-roundtrip.md`). Steps D1 to D3 (optional) were not
run, so `H-A-DRC-ALTIUM` stays open.

### 2026-10-09, `AD 26.5`, Part X, steps X1 to X7 and X9 to X12

- Tool: Altium Designer 26.5. Reported by the maintainer on 2026-10-09 in his own chat, a second report of
  that day (S-0726). Label: `ALTIUM-VERIFIED(author-report; AD 26.5; 2026-10-09; no artefact)`.
- Files: Fenolite's own files of Part X (`board6`) and, for step X12, the document with locked copper built
  from the routed sample. No file opened or saved in the session enters the repository; the digests of the
  opened copies were not reported.

Outcome per step, each as expected:

- **X1, opening.** No repair prompt and no message in the Messages panel. Adds the Messages panel to
  `H-A-PCB-DOC-OPEN`, which is an author report since 2026-10-03.
- **X2 and X3, the layer stack.** Confirms `H-A-PCBX-STACK`.
- **X4, via spans and drill pairs.** Confirms `H-A-PCBX-VIASPAN`.
- **X5, the four texts.** Confirms `H-A-PCBX-TEXT`. Which corner of each text lies at the record's position
  was not named.
- **X6 and X11, the keep-out.** Confirms `H-A-PCBX-KEEPOUT`: no message on load, the same two restrictions
  before and after a save, with both keys in the record.
- **X7, the hole.** Confirms `H-A-PCBX-HOLE`.
- **X9, repour.** Confirms `H-A-PCBX-REPOUR`.
- **X10, save.** Done; the size of the saved file was not given. It settles no row.
- **X12, copper locks (change c0108).** As expected for each item kind. Confirms `H-A-PCB-CU-LOCK`.

Reading of the report:

- No step named a fault, so no fact of the format pages and no golden file changed, and no row is refuted.
- Not given, and still owed: the counts of step X8.6 (`H-A-PCBX-BODY-ID` stays pending) and the list of
  Gerber extensions of step O3 (`H-A-OUTJOB-GERBER-LAYERS` stays pending); the maintainer will send both
  later. Steps D1 to D3 of Part D were not run: `H-A-DRC-ALTIUM` stays pending.
- An author report moves no write kind out of `experimental`: every Altium write stays experimental.

## Author report of 2026-10-07 (opening only)

On 2026-10-07 the author reported, for the files he was given: every project opened in Altium Designer 26
(minor version not stated) with no problem, and what he sees looks right to him; on some small components
the names of pins overlap, and he does not know whether that is intended.

- **What he was given.** The session folder built from commit `bc306deb` (Parts Y, W, O, U and X, 63 files
  with their SHA-256) and the kit built from `5adad054`. The three files of Part R were in the same pack; he
  did not say that he opened them.
- **What the report is.** An author report of opening and looking, on files that Fenolite wrote, with a
  licence the author may use for Fenolite.
- **What it is not.** It is not the numbered steps of the Parts. No value was read back (rules and scopes, the
  layer stack, via spans, text positions, keep-out restrictions, title-block fields, outputs and containers),
  and no compile, change order, rule check, repour or output-job run was reported. When this was written no
  file that Altium saved had been received; the folders came back later the same day (next section).
- **A second answer, the same day.** Asked whether any repair, upgrade or conversion prompt appeared
  when he opened the kit's files, and for his minor version, the author answered: "nenhum erro ou pedido
  de restaurar foi feito, tudo abriu como projeto Altium. E meu Altium é o 26" (no error and no request
  to restore was made, everything opened as an Altium project; my Altium is 26). The answer does not use
  the word upgrade and gives no minor version.
- **What it moves.** No level. The two rows whose criterion is opening alone, `H-A-PH-CHECKSUM` and
  `H-A-PH-LAYOUT`, are stated for the author's earlier writer with a value as reported, and the second
  for another version of the tool; this report is about files that Fenolite's writers wrote and names no
  value. Change c0092 restates that family for Fenolite's writers, and the answer above is then the
  author report for the restated rows. The rows whose first step is opening carry a dated partial note in
  `docs/hypotheses.md` (`H-A-SCHX-GRAPHICS`, `H-A-SCHDOT-OPEN`, `H-A-OUTJOB-OPEN`, `H-A-RULE-KINDS`,
  `H-A-PH-CHECKSUM`, `H-A-PH-LAYOUT`), and `H-A-PCB-DOC-OPEN`, which was settled on 2026-10-03, names the
  further documents. Every row that needs a value, one of Altium's engines or the recorded kit run is where
  it was.
- **Observation: names of pins that overlap.** The author named the symbols the same day: `BJT_NPN`,
  `Comparator`, `Operational_Amplifier`, `CONN2` and `Linear_Regulator`, and asked for a correction. A scan of the
  session's schematic libraries with Fenolite's own reader shows where a shown name can collide: a small
  transistor body with three shown names, the triangle of a comparator or an operational amplifier with
  names on four of five pins, and a two-pin connector whose name and number are the same text. The Altium
  writer honours a symbol's hidden pin names, so the likely cause is in the symbol definitions, which leave
  names visible on small discrete symbols; KiCad would then show the same. Change c0134 corrects the
  definitions; the samples it regenerates are new files that this report does not cover.
- The steps of the Parts were written from Altium's documentation; a menu path or a dialog name may read
  differently in version 26.

## Returned folders of 2026-10-07

Later on 2026-10-07 the author returned the two folders he had been given, after working in them by hand in
Altium Designer 26 (minor version not stated). He said of the session that all went right, that he saved
some files of the kit, and that the sheet of Part R showed as a page that was all black. Nothing that Altium
wrote is in this repository; the folders were read outside it, on 2026-10-07, with Fenolite's own readers and
`fenolite kit verify` at commit `6f6227eb`.

**What came back.**

- The session folder: its 64 files unchanged, and 21 new ones. A project structure file stands beside nine of
  the ten projects, the mark that Altium compiled them; the project of Part U has none. Under the project of
  Part O are the files that the written output job produced. The reply form of the session's guide was not
  filled, and no note came with the folder.
- The kit: the project file of the sample `flat` rewritten in place by Altium, and saved documents of three
  samples: a schematic document, a PCB document and the project file of `flat`; a schematic library and a
  schematic document of `libs`; a schematic document of `board6`. The kit's form is as built: every value empty.

**What the files show.**

- **Every saved document reads back to the model that was written.** Fenolite's import of each of the five
  saved compound documents equals its import of the file it wrote. The one model difference is on the PCB
  document: a rule `HoleSize` that Altium adds by default. Altium's save adds its own bookkeeping (identifiers
  on records, default parameters of the sheet, default classes and rules around the written ones, further
  storages) and keeps what was written: the nets, the components, the five written rules in keys, values and
  order, the two written classes, the six title-block values, the class settings of the project file.
- **The output job runs, except for its Gerber output.** NC drill, pick and place, the bill of materials and a
  schematic and PCB print of two pages were produced, each into the container of its kind. The drill files
  hold 7 holes of 0.3 mm and 2 of 0.9 mm, which are the seven vias and the two pads of the through-hole part of
  the written board; the three placement rows hold the three components on their sides at the positions of the
  model (Altium reports the centre of a part's pads, not its reference point). **No Gerber layer file was
  produced**: the report of that output names no layer, and its aperture files are empty, with no error
  message. The written job holds no settings record for the Gerber output (a decision of change c0087: the
  job holds outputs, sources and containers and no setting), and for this one output Altium's default
  plots nothing. That is a defect of the written job. Change c0138 writes the settings record of the Gerber
  output, with the plotted layers taken from the board.
- **The kit.** `fenolite kit verify` on the folder as returned fails every step of the sample `flat` for one
  reason: step K1.5 (save the project under another name) made Altium rewrite the kit's own project file,
  which then differs from its digest. With that file restored from the history copy that Altium left beside
  it, steps K1.1, K1.2, K1.3, K1.5 and K9.1 pass (the saved schematic document, PCB document, schematic
  library and project file are read and are equal to the samples at the levels the steps name), and no step
  fails on a difference. The other steps have no file or no form value. This is not a recorded kit run:
  `fenolite kit record` refuses a folder whose kit files changed and whose form is empty. The defects this
  showed in the kit itself (the step that rewrites a kit file, wrong expected values printed for integer
  steps, a path that the kit's privacy check does not list, a step that cannot tell an update from a save) are
  change c0139.
- **Part R, the black page.** The two sheets of Part R were authored record by record, outside the schematic
  writer, and their sheet record holds no area colour and their objects no colour; every sheet that the
  schematic writer writes, and every sheet Altium saved, holds an area colour. An absent colour most likely
  reads as black. The files of Part R are to be authored again with the writer's colours; until then Part R
  has no outcome. 2026-10-08, change c0146: they are authored again, through the schematic writer itself
  (`docs/evidence/altium-schematic.md`, Part R, which also records what the saved schematic of the kit showed
  of two equal fonts); nobody has opened them.

**What it moves.** No level. The reply form was not filled, so no row that needs a value read from a dialog or
a message panel has its value; the kit rows need a recorded run. Recorded in `docs/hypotheses.md` as
observations, with the rows left where they were: `H-A-OUTJOB-RUN` (five kinds generated, the Gerber kind
not) and `H-A-OUTJOB-OPTIONS` (the default of the Gerber output plots no layer), both waiting for the author
to state the outcome and his minor version; `H-A-KIT-SCRIPT` (the author reports that the first call of the
script probe, `Client.GetServerRecordCount`, is not known to Altium Designer 26; he did not go on with the
script). The structure files of Part Y list the sheet tree of step Y4, and five of the six outputs of Part O
exist: both support their rows and settle neither, because the step's own report is missing.

What the saved files show of the formats (keys that Altium adds, drops or reorders on a save) is input for
the format pages and is recorded there in a change of its own.

## Session 2 of 2026-10-08

The maintainer's second session of Altium work, in Altium Designer 26.5.0 on his own PC, a licence he may
use for Fenolite (`LEGAL.md`, block A), on the session pack built from commit `695574ba` (S-0615), and on
one public document opened read-only (S-0616). Nothing that Altium wrote is in the repository.

- **Part K, the kit.** No kit run was recorded. The maintainer decided on 2026-10-08 that the kit did not
  change since his run of 2026-10-07 and is accepted as validated by that run for the release 0.3.0; the
  decision, what it does not do and the revalidation it asks for are in
  `docs/evidence/altium-kit/README.md`. No `H-A-KIT-*` row moves and no `ALTIUM-VERIFIED(kit)` label exists.
- **The LED `D1` on the board** (changes c0144 and c0147): pad 1 on `GND`, pad 2 on `LED_A`, as the model
  says (the cathode on pad 1 of the cathode-first land). Whether the schematic of `flat` shows `GND` on pin
  2 (`K`) of `D1` was not stated.
- **Part D on a public document** (change c0131, steps D4 to D6 of
  `openspec/changes/c0088-altium-light-drc/design.md`; S-0616): on `altium-third-party-pcbdoc-03`, not
  repoured and not saved, Altium's rule check with the Clearance rules only.
  - **D4.** Done, with the Clearance rules alone.
  - **D5.** Altium shows **0** violations of `Clearance_2` between pad `J2-1` and the track of `Net*_4`.
    Fenolite reports 7 there, all 8 to 9 nm short of the rule's 127 000 nm (gaps of 126 991 and 126 992
    nm). Fenolite's check is stricter than Altium's by that rounding: the pairs are no finding for Altium.
  - **D6.** The properties panel shows pad `J2-1` as 63.78 mil by 63.78 mil, with two decimals. That agrees
    with Fenolite's reading of 63.7795 mil and cannot tell it from a pad of 63.78 mil.
  - **What follows.** By the design of c0088 (N = 0), the seven findings of `-03` are not findings of the
    board for Altium; the 18 others of their class (2 on `-01`, 16 on `-08`) were not checked in Altium.
    D6 does not show the pad-size fact that Fenolite reads otherwise.
  - **The fix landed (change c0152, 2026-10-08).** The cause is Altium's own tolerance, not Fenolite's
    reading: the document's integers put the straight track segment 49 996.5 units from the edge of the
    637 795-unit pad, 3.5 units (8.89 nm) inside the 50 000-unit rule, and Fenolite reads that gap as
    126 991 nm against an exact 126 991.11; no rounding of coordinates, track ends or polygons takes
    part, and a pad of 63.78 mil would be nearer still. Altium passes it, so its check allows at least 3.5
    units. The copper check on Altium input now lowers each clearance rule by 9 nm (that tolerance in
    whole nanometres; `docs/formats/altium/import.md`, "Clearance of the copper check",
    `ALTIUM-VERIFIED(author-report)`): `-03` has no clearance finding, and of the 18 others the 9 that are 8
    or 9 nm short go and the 9 that are 10 to 20 nm short stay errors (1 on `-01`, 8 on `-08`). D5 above stays the evidence of what Altium shows.
- **Parts X8 (c0121), V (c0132) and G (c0126).** Not done: owed. `--altium-bodies extruded` stays off by
  default, and the rows of the three parts are where they were.
  The report of 2026-10-09 below covers them.

## Report of 2026-10-09

On 2026-10-09 the maintainer reported, for his sessions of 2026-10-07 and 2026-10-08 in Altium Designer
26.5, the parts that were owed (S-0724), one generic outcome per step: Part U (c0084), step X8 of Part X
(c0121), Part G (c0126), Part V (c0132), all as expected, and his answer to D4 to D6 confirmed. The outcomes
and the rows they move are under "Reports", "2026-10-09". A second report of the same day (S-0726) covers
steps X1 to X7 and X9 to X12 of Part X, all as expected (under "Reports" too). Still owed on this page: the
counts of step X8.6, and steps D1 to D3 of Part D (optional; not done, so `H-A-DRC-ALTIUM` stays pending). The kit run (`fenolite kit
verify` and `fenolite kit record`, change c0091) is not part of this report. The schematic side of the same
report is in `docs/evidence/altium-schematic.md`, "Report of 2026-10-09".
