# Altium PCB writers: the maintainer's check

2026-10-13 (c0166): schematic-library fixtures and their current protocol hashes
were regenerated for the model/owner repair. PCB and PcbLib bytes are unchanged.
Previous native reports retain their historical scope; the new measured outcomes
are recorded in [the native campaign](altium-native-acceptance.md).

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
| `tests/data/altium/blink/blink.SchLib` | `4f427227183102b479836e66d54a7a3cc0bae5794befc4d8a5a7e15362609517` |

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
| `tests/data/altium/routed/routed.SchLib` | `792908e69ccf5d932b6b5ce93fb65e835bad3c82c21b7c228415ae53e8d79d25` |
| `p0/routed.PcbDoc` | `4082a630a46d1a5213c05bf699692c19b953eb6dfdb08ecce7d557683cf392c5` |

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
  `GND` via that cross it show no connection line. The variant holds four tracks (none on the plane), one
  polygon on Bottom Layer and, since change c0389 (task 2.7), one `Split Plane` polygon on Internal Plane 1
  (`GND`) and the rules `PlaneConnect` (pads Relief, vias Direct) and `PlaneClearance`. A design rule check
  reports no Starved Thermal and no Un-Routed Net between the `GND` via and `D1` pad 1 (the 2026-11-05
  run on the earlier bytes `8e0978ec…` reported both). Settles `H-A-PCB-CU-PLANE`.

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
| `tests/data/altium/board6/board6.PcbDoc` | `39fa67748befc67521ba04f8bf78aa2e66cf75105bfebd704e99ccc3e404f7ee` |
| `tests/data/altium/board6/board6.PcbLib` | `9d09f5126ba6aad6026f4c85fa2899c908eaa363aeaec1b58b59e64a11666e22` |
| `tests/data/altium/board6/board6.PrjPcb` | `75e7078fdb8fc79b606ad0c0a3acf30103faada43dc440a7fb01e5daad2f7219` |
| `tests/data/altium/board6/board6.SchDoc` | `36e9850be729dd5e91e14c9b0adab1fb9ac7ef036154839f94d279a12ffc2118` |
| `tests/data/altium/board6/board6.SchLib` | `66b31ae040cb6f0de2584efe732182a9a230e040c4459a1d3aa58f3e34698ae7` |

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
| plane (change c0389, task 2.7) | one `Split Plane` polygon on Internal Plane 1, net `GND`, over the outline; the rules `PlaneConnect` (pads Relief, vias Direct) and `PlaneClearance` (20 mil) |
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
   (`--altium-bodies extruded`), and **the option stays `off` until step X8 is reported** (it was reported on 2026-10-09, and the
   maintainer made `extruded` the default the same day: change c0155; `off` gives the earlier files). The step runs on
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
   | `tests/data/altium/body2/body2.SchLib` | `cc57098f268663005a1074c0c6fc2da1a3095c10d36cfbce087a68ba6e98274d` |
   | `short/body2.PcbDoc` | `6becb1923051aa3b312cc97eaf8230fab0a50b30d7187253c55411ebe3e8175f` |
   | `short/body2.PcbLib` | `9432b8ab5f7801c7c9399a9e943dd272d4b02d2fbfa0586cc34c53e3666b991d` |
   | `short/body2.PrjPcb` | `e0b2cca3f3635c5ec50edca85d6dbae0d527a03d3e94447945e874a607769591` |
   | `short/body2.SchDoc` | `f5598952ca794defc855b6e3cf6d75f0a6813d2b277016b305da595832996e48` |
   | `short/body2.SchLib` | `cc57098f268663005a1074c0c6fc2da1a3095c10d36cfbce087a68ba6e98274d` |

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

## Part S: slots and cut-outs

Change c0168; pending, no Altium verification is claimed. Fenolite writes a **drilled** slot (a hole with
a length, `design.hole(..., length=...)`) as a free pad with a slotted hole, and a **milled** slot or a
cut-out (`design.slot`, `design.cutout`) as a board cut-out region. KiCad's importer reads both
(`H-A-SLOT-PAD`, `H-A-CUTOUT-REGION`); this part asks what Altium Designer does with them
(`H-A-SLOT-KIT`). Releases write no cut-out region until S3, S4 and S5 pass (`pcbdoc.CUTOUT_REGIONS`).

**Files.** Built outside the repository by `FENOLITE_ALTIUM_PART_S=~/fenolite-altium-checks/session-4/S-slots
uv run pytest tests/unit/backends/altium/test_part_s.py` (needs `fenolite[geo]`): `regions/`, `clearance/`
and `gate-off/`, each an Altium project `slots.PrjPcb` with its `slots.PcbDoc`; `expected.md` (the place
and size of every slot, hole and cut-out, read back from the files); this text as `README.md`; and
`SHA256SUMS`. The board is 60 × 40 mm. Coordinates below are millimetres from its lower-left corner, which
is the document's origin.

| item | where | what it is |
|---|---|---|
| `D1` | (27, 7), turned 30° | drilled slot 12 × 2 mm, alone |
| `D2`, `D3` | (38, 13) and (43, 8), turned 90° | drilled slots 10 × 2 mm whose holes overlap in an L |
| `H1` | (52, 8) | round hole 3.2 mm |
| `S1` | (15, 30), turned 30° | milled slot 12 × 2 mm, alone |
| `S2` + `S3` | (40, 30) and (45, 25) | two milled slots 12 × 2 mm merged into one L-shaped cut-out |
| `cut-out 1` | 8 … 20 × 8 … 16 | rectangular cut-out with 1 mm round corners |
| `TP1`, `TP2` (only `clearance/`) | (38, 28.3) and (36, 14.7) | 1 mm round pads on net `GND`, 0.2 mm from `S2` and from `D2` |

`clearance/` also holds a `GND` polygon on the Top Layer over the whole board and two rules: Board Outline
Clearance 0.5 mm and Hole To Hole Clearance 0.25 mm.

Work on a copy of the folder. For each case report `as expected` or what differed, in one sentence.

1. **S1** Open `regions/slots.PrjPcb` and its PCB. Double-click `D1`. Expected: the document opens with no
   repair message; `D1` is a pad on Multi-Layer with no designator, Hole shape Slot, Hole Size 2 mm,
   Length 12 mm, not plated, and no copper ring around the hole. Note the solder mask and paste openings
   shown at `D1` (Fenolite leaves both "from the rules"). Then **File » Fabrication Outputs » NC Drill
   Files** (defaults) and **Drill Drawings**. Expected: `D1` is a slot in the non-plated drill file and in
   the drill drawing.
2. **S2** Open `clearance/slots.PcbDoc`, run **Tools » Design Rule Check** (Run Design Rule Check).
   Expected: Hole To Hole Clearance reports the pair `D2` – `D3` (their holes overlap).
3. **S3** In `regions/slots.PcbDoc` press `1` (Board Planning Mode) and `3` (3D Layout Mode), then `2` to
   return. Expected: the board shape has the openings of `S1` and of `cut-out 1` in 2D and in 3D. The NC
   drill files of S1 hold no hit for `S1`, `S2`, `S3` or `cut-out 1`.
4. **S4** In `regions/slots.PcbDoc` click the L-shaped opening of `S2` + `S3`. Expected: one Region whose
   Kind is Board Cutout (not two), with a round end at each of the three free ends.
5. **S5** In the DRC report of S2. Expected: Board Outline Clearance flags `TP1` (0.2 mm from the cut-out
   edge) and does not flag `TP2` (0.2 mm from the drilled slot `D2`, which is a hole, not an edge).
6. **S6** In `clearance/slots.PcbDoc` run **Tools » Polygon Pours » Repour All**. Expected: the polygon
   pours without a message and leaves no copper inside `S1`, the L of `S2` + `S3` or `cut-out 1`.
7. **S7** Save `regions/slots.PcbDoc` with **File » Save As** to `regions/slots-saved.PcbDoc`, then run
   `FENOLITE_ALTIUM_S7=<that file> uv run pytest tests/unit/backends/altium/test_part_s.py -k s7` in the
   repository. Expected: the test passes (the same four holes and three cut-outs within 1 µm).
8. **S8** Open `gate-off/slots.PcbDoc` and `gate-off/build-report.json`. Expected: the board has no
   cut-out region (only the four holes), and the report names each cut-out: `slot/S1`, `slot/S2+slot/S3`
   and `cutout/1`.

Send the Altium Designer version (`AD <major>.<minor>`), the date, the SHA-256 of `regions/slots.PcbDoc`
from `SHA256SUMS`, and one outcome per case, in the form of the native acceptance inventory (date, version,
case, file hash, step, expected and observed outcome). S1 to S8 settle `H-A-SLOT-KIT`; S3, S4 and S5 decide
the gate.

## Part Q: panels and the Embedded Board Array

Change c0173; pending, no Altium verification is claimed. Fenolite makes panels of several copies of one
board (`fenolite panel`). No public page gives the records of Altium's Embedded Board Array, so phase A
measures them by observation: the maintainer makes panels of a board built by Fenolite in his licensed
Altium Designer 26.5 and saves one document per variant, each differing from the baseline by one
property; Fenolite reads the saved files with its own reader (`fenolite diff A B --view records`, and a
dump of the opaque `EmbeddedBoards6` stream). Phase B (after task 7.2) asks Altium to open what Fenolite
writes. Releases wrote no array until Q7, Q8 and Q9 passed (`pcbdoc.EMBEDDED_ARRAYS`, the maintainer's
decision of 2026-10-16). They passed in Altium Designer 24.5.2.23 on 2026-11-05 (S-1585, S-1593), and the
gate is on (change c0389, task 3.3): a panel of a `.PcbDoc` board with an unturned, unmirrored grid is
written as the array. **Limitation:** Altium rereads a changed board only after it is restarted;
reopening the panel in the same session keeps the old copies (Q8).

**Files of phase A.** Built outside the repository by `FENOLITE_ALTIUM_PART_Q=~/fenolite-altium-checks/session-6/Q-panels
uv run pytest tests/unit/backends/altium/test_part_q.py -k phase_a`: `board/`, the fixture
`tests/data/panels/board.py` built with `--target altium` (`board.PrjPcb`, `board.PcbDoc` and their
library, schematic and output job), a two-layer 40 × 30 mm rectangle authored for Fenolite; `README.md`,
these steps in Portuguese; `PART-Q.md`, this text; and `SHA256SUMS`. Coordinates are millimetres from the
document origin. **Files of phase B** (task 7.3): `written/`, `flat/` and `expected.md`.

Work on a copy of the folder. For each case report `as expected` or what differed, in one sentence.

*Phase A, observation:*

1. **Q1** Add a new PCB `panel-a.PcbDoc` to `board/board.PrjPcb` (same folder). **Place » Embedded Board
   Array/Panelize**, pick `board.PcbDoc`, place it; in Properties set X 5, Y 5, Rotation 0, Column Count 2,
   Row Count 2, Column Spacing 42, Row Spacing 32, Mirrored off, Link Location off; choose "Synchronize
   Manually Later" if asked and note the dialog. Save. Expected: four boards with 2 mm gaps.
2. **Q2** From `panel-a`, **File » Save As** once per change, each made alone on a fresh copy of `panel-a`:
   `panel-cols4` (Column Count 4), `panel-rows3` (Row Count 3), `panel-spacing` (Column Spacing 45, Row
   Spacing 35), `panel-margin` (Column Margin 3, Row Margin 3; note whether the spacing fields change),
   `panel-rot90` (Rotation 90), `panel-mirror` (Mirrored on), `panel-link` (Link Location on),
   `panel-move` (X 12, Y 7). Expected: each saves; note any field that changed besides the one set.
3. **Q3** On `panel-a`, add two mechanical layers in the View Configuration or the Layer Stack Manager, set
   one's Layer Type to V Cut and the other's to Route Tool Path, draw one track on each, save as
   `panel-layers`. Expected: it saves; note the layer numbers and names Altium gives.
4. **Q4** On `panel-a`, place a second array of the same board at X 100, Y 5 (1 × 1), save as `panel-two`.
   Expected: two arrays.
5. **Q5** On `panel-a`, **File » Fabrication Outputs » Gerber Files** and **NC Drill Files** with their
   defaults. Expected: four copies in the copper and drill outputs; send the list of files written (names
   only).
6. **Q6** Close Altium, zip the folder without the `History` and `Project Outputs` folders, and send it.
   Expected: Fenolite runs `fenolite kit verify`'s path scan before anything is read.

*Phase B, confirmation (files written by Fenolite after task 7.2; the gate forced on for the kit only):*

7. **Q7** Open `written/panel.PrjPcb` and `panel.PcbDoc`. Expected: no repair message; one array of
   `board.PcbDoc`, 2 × 2, with the properties of `expected.md`.
8. **Q8** Move one track of `board.PcbDoc`, save, return to `panel.PcbDoc` and refresh (or reopen).
   Expected: all four copies show the move. A restart of Altium counts as the reopen (coordinator's
   decision of 2026-11-05): Altium rereads a changed board only after it is restarted. Then select the two mechanical layers. Expected: types V Cut
   and Route Tool Path when task 7.2 writes them, otherwise unassigned with the names `V-Cut` and
   `Route Tool Path`.
9. **Q9** Gerber Files and NC Drill Files of `written/panel.PcbDoc`, with NC Drill Setup's "Generate
   separate NC Drill files for plated & non-plated holes" on and the `V-Cut` layer ticked in Gerber Setup.
   Expected: four copies; the mouse-bite and tooling holes in the non-plated drill file; the `V-Cut` layer
   in its own Gerber file. Note (2026-11-05): the coordinator's decision, by the maintainer's delegation,
   turns both options on, because neither is stored in the PCB document (S-1593); the first text asked for
   the defaults.
10. **Q10** **Tools » Design Rule Check** on `written/panel.PcbDoc`. Expected: report every message; none
    is expected to block the outputs.
11. **Q11** Open `flat/panel.PcbDoc` (the flattened panel), run Q9 and Q10 on it. Expected: it opens
    without repair; the same holes and layers; note any message about repeated designators.
12. **Q12** Save `written/panel.PcbDoc` as `panel-saved.PcbDoc` and run
    `FENOLITE_ALTIUM_Q12=<that file> uv run pytest tests/unit/backends/altium/test_part_q.py -k q12`.
    Expected: it passes (the same array read back).

Send the Altium Designer version (`AD <major>.<minor>`), the date, the SHA-256 of each file sent, and one
outcome per case, in the form of the native acceptance inventory (date, version, case, file hash, step,
expected and observed outcome). Q1 to Q4 settle the measurement of `H-A-PANEL-RECORD`, Q3 that of
`H-A-PANEL-LAYERKIND`; Q7 to Q12 settle `H-A-PANEL-KIT`, and Q7, Q8 and Q9 decide the gate
`EMBEDDED_ARRAYS`. Saved native files stay outside the repository; only measured facts, digests and sizes
are committed.

## Part H: a slot shorter than its hole (change c0416)

No native kit form is claimed. The agent run of 2026-11-05 is under "Reports" (S-1605). Altium's pad dialog says a slot's Length cannot be smaller than
its Hole Size (S-0770), but a record may hold a smaller one. KiCad 10.0.6 reads such a hole by its extents:
an oval whose long side lies across the record's slot rotation. Level 3 of `equivalent` compares slots that
way (change c0416, `pcb-records.md`). This part asks what Altium Designer makes of the record
(`H-A-SLOT-SHORT`).

**Files.** Built outside the repository by `FENOLITE_ALTIUM_PART_H=~/fenolite-altium-checks/H-short-slots
uv run pytest tests/unit/backends/altium/test_part_h.py`:

- `holes.PcbDoc`, a free PCB document;
- `slots.PcbLib`, a free PCB library;
- `expected.md`, the fields of every pad read back from the files, and the axis KiCad gives each slot;
- this text as `README.md`;
- `SHA256SUMS`.

The board is 60 × 40 mm. Its six free plated pads `P1` to `P6` lie at X 10, 18, 26, 34, 42 and 50 mm, Y
20 mm from its lower-left corner. They are 4 mm round on Multi-Layer, and each has a slotted hole whose two
numbers are 1 mm and 2.15 mm. The footprint `SL` of the library holds the same six pads, numbered `1` to
`6`.

| pad | Hole Size | Length | hole Rotation | pad Rotation | KiCad 10.0.6 axis |
|---|---|---|---|---|---|
| `P1` | 1 | 2.15 | 0° | 0° | 0° |
| `P2` | 2.15 | 1 | 0° | 0° | 90° |
| `P3` | 1 | 2.15 | 30° | 0° | lost |
| `P4` | 2.15 | 1 | 30° | 0° | lost |
| `P5` | 1 | 2.15 | 90° | 45° | 135° |
| `P6` | 2.15 | 1 | 0° | 30° | 120° |

`P1`, `P3` and `P5` are controls that Altium's dialog allows. `P2`, `P4` and `P6` hold the Length below the
Hole Size. The axis is the direction of the hole's long side, counter-clockwise from the board's X axis.

Work on a copy of the folder. For each case report `as expected` or what differed, in one sentence.

1. **H1** Open `holes.PcbDoc` and double-click each pad `P1` to `P6`. Expected: the document opens with no
   repair message, and the Properties panel shows each pad's Hole Shape Slot, Hole Size, Length and both
   rotations as in the table. Report the four values Altium shows for `P2`, `P4` and `P6`, and any message.
2. **H2** In 2D and in 3D Layout Mode (`3`, then `2`), look at each hole. Expected: each hole's long side
   lies along the KiCad axis of the table, and `P3` along 30° and `P4` along 120°. Report the direction of
   each long side (horizontal, vertical or the angle) and its length. For one short slot, measure it with
   Reports » Measure Distance between the two ends of its hole.
3. **H3** Run **File » Fabrication Outputs » NC Drill Files** (defaults) and **Drill Drawings**. Expected:
   six slots in the plated drill file, each 2.15 mm long and 1 mm wide along its H2 axis. Send the drill
   file or files and note any message.
4. **H4** Save `holes.PcbDoc` with **File » Save As** to `holes-saved.PcbDoc`, then run
   `FENOLITE_ALTIUM_H4=<that file> uv run pytest tests/unit/backends/altium/test_part_h.py -k h4` in the
   repository. Expected: the test passes, so Altium kept each pad's four numbers. Otherwise the failure
   names each changed field.
5. **H5** Open `slots.PcbLib`, footprint `SL`, and double-click pads `1` to `6`. Expected: no repair
   message, and the values of H1. Then on a copy, set pad `1`'s Length to 0.9 mm. Report whether Altium
   accepts a Length below the Hole Size, and close without saving.
6. **H6** Save the unchanged `slots.PcbLib` with **File » Save As** to `slots-saved.PcbLib`, then run
   `FENOLITE_ALTIUM_H6=<that file> uv run pytest tests/unit/backends/altium/test_part_h.py -k h6`.
   Expected: the test passes.

Send the Altium Designer version (`AD <major>.<minor>`), the date, the SHA-256 of `holes.PcbDoc` and of
`slots.PcbLib` from `SHA256SUMS`, and one outcome per case, in the form of the native acceptance inventory
(date, version, case, file hash, step, expected and observed outcome).

- H2 and H3 settle `H-A-SLOT-SHORT`.
- H1, H4, H5 and H6 say whether Altium keeps, rewrites or refuses such a record.
- If Altium reads the short slots differently, the slot form of change c0416 and the Altium adapter are
  revisited.

## Part Z: component bodies (changes c0387 and c0175)

The cases measure the component-body records that the Altium import keeps with unknown heights
(`altium.import.body-unknown`, c0387) and how a document stores one 3D model placed at four rotations
(c0175, task 10.4). Altium writes each file; Fenolite only reads the saved files. Prepare with
`FENOLITE_ALTIUM_PART_Z=<outside folder> uv run pytest tests/unit/backends/altium/test_part_z.py -k kit`.
The kit holds `body2/` (the committed project of step X8, `tests/data/altium/body2/`, as it is),
`Box_2x1.step` (an authored CC0 box of 2 × 1 × 0.5 mm, `tests/data/models/Fenolite.3dshapes/`),
`expected.md` (the bodies of `body2.PcbDoc` as Fenolite reads them), `README.md` (these steps) and
`SHA256SUMS`. Work on a copy. Save each result with **File » Save As** in `body2/` under the name the case
gives, and report per case the date, the exact version, what the Properties panel shows and whether a
message appeared.

1. **Z1** A body on the other side. Open `body2/body2.PcbDoc`, select the extruded body of `U1` (a top
   part) and set its side in the Properties panel to the bottom side; save as `Z1.PcbDoc`. Expected:
   Altium accepts the setting; report what the 3D view shows (the body above or below the board).
2. **Z2** Each model type. Open `body2/body2.PcbDoc` and, on `R1`, place one 3D body of each type that
   **Place » 3D Body** offers: an extruded body, a generic model from `Box_2x1.step` (embedded), a
   cylinder and a sphere, with an overall height of 2 mm each; save as `Z2.PcbDoc`. Expected: one body per
   type; report the names of the types the dialog offers.
3. **Z3** Heights at the limits. Open `body2/body2.PcbDoc` and, on the extruded body of `R1`, try in turn:
   standoff −0.5 mm with overall 1 mm; overall 1 mm with standoff 2 mm; overall 0 mm; overall 100 mm.
   Report which values the panel accepts and which it changes or refuses. Save the last accepted state as
   `Z3.PcbDoc`. Expected: the values that the panel keeps are the values the saved file holds.
4. **Z4** One model at four rotations (c0175). Open `body2/body2.PcbDoc`, place on `U1` four generic model
   bodies from `Box_2x1.step` (embedded) with a rotation about Z of 0°, 90°, 180° and 270°; save as
   `Z4.PcbDoc`. Expected: four bodies; report whether Altium asks to embed the model once or four times.

Read the saved files with `FENOLITE_ALTIUM_PART_Z_SAVED=<folder of the saved files> uv run pytest
tests/unit/backends/altium/test_part_z.py -k saved -s`, which prints, per body, its component, projection,
model type, heights, model name and rotation, and per entry of the `Models` storage its keys, and refuses
a folder that fails the kit privacy scan. These cases settle `H-A-IMP-BODY` and `H-A-IMP-BODY-Z` for the
cases they measure (c0387, task 1.2) and the model store per rotation (c0175, task 10.4). The agent run of
2026-11-05 is under "Reports" (S-1604); an agent run moves no row.

## Reports

### 2026-11-05, actual `AD24.5.2.23`, Part H (source S-1605)

A Claude agent ran H1 to H6 on 2026-11-05 at the maintainer's request (delegation of 2026-11-04), in the
maintainer's Windows VM, under the approved 24.5 scope. This is not the maintainer's own review.
`Client.GetProductVersion` is 24.5.2.23 (Trial licence). The kit was built at `4ab835e1`
(`origin/cac/lote-22`) with `FENOLITE_ALTIUM_PART_H=<outside folder> uv run pytest
tests/unit/backends/altium/test_part_h.py` into `~/fenolite-altium-checks/claude-2026-11-05/c0416-H`:
`holes.PcbDoc` `e31205570a2a…` and `slots.PcbLib` `db575bcd1ff5…`. The run used a VM copy, and both
inputs still match `SHA256SUMS` after the run. Menu commands ran through UI Automation. The Properties
fields were read by their automation ids after an authored read-only DelphiScript selected each pad.

| date | version | case | file (SHA-256) | step | expected | observed |
|---|---|---|---|---|---|---|
| 2026-11-05 | AD 24.5 | H1 | `holes.PcbDoc` `e31205570a2a…` | open; Properties of `P1` to `P6` | no repair message; values as the table | as expected. No message on open. Hole Shape `Slot` for all six. `P2`, `P4` and `P6` show Hole Size 84.646 mil and Length 39.37 mil, hole rotation 0, 30 and 0, pad rotation 0, 0 and 30. `P1`, `P3` and `P5` show 39.37 and 84.646 mil, hole rotation 0, 30 and 90, pad rotation 0, 0 and 45 |
| 2026-11-05 | AD 24.5 | H2 | `holes.PcbDoc` `e31205570a2a…` | 2D and 3D Layout Mode, each hole; Reports » Measure Distance on one short slot | long sides along 0°, 90°, 30°, 120°, 135° and 120° | as expected. A fit of the hole pixels of each 2D view, scaled by the 4 mm pad, gives axes 0.0°, 90.0°, 30.1°, 119.9°, 134.9° and 119.9°, each 2.14 to 2.16 mm long and 0.99 to 1.00 mm wide. 3D Layout Mode shows the same directions. Measure Distance between the visible ends of `P2`'s hole reads Y 85 mil (2.16 mm, on a 5 mil snap) |
| 2026-11-05 | AD 24.5 | H3 | `holes-SlotHoles.TXT` `014b1f81…`, `holes.DRR` `c50e9f5a…`, `holes.LDP` `98599f2f…` | File » Fabrication Outputs » NC Drill Files (defaults), Drill Drawings | six plated slots, 2.15 × 1 mm, along the H2 axes | as expected. NC Drill writes no round-hole file, only `holes-SlotHoles.TXT`: `;TYPE=PLATED`, tool `T01` 1.0 mm, and six routed paths (`G00`, `M15`, `G01`, `M16`) of 1.15 mm between centres, at 0°, 90°, 30°, 120°, 135° and 120°. With the 1 mm tool, each slot is 2.15 × 1 mm. The report lists `T1` 1 mm, Slot, 6, PTH. An Import Mill/Route Data dialog followed and was cancelled, and the CAMtastic document that opened was closed unsaved. Drill Drawings opens a print preview with six drill symbols in a row and no drill table; nothing was printed |
| 2026-11-05 | AD 24.5 | H4 | `holes-saved.PcbDoc` `1de97471…` | File » Save As, then `FENOLITE_ALTIUM_H4=<file> … -k h4` | the test passes | as expected. No message on save. 1 passed, with or without a reviewed prefix. The kit privacy scan finds the file's own VM path in its header |
| 2026-11-05 | AD 24.5 | H5 | `slots.PcbLib` `db575bcd1ff5…` | footprint `SL`, pads `1` to `6`; then pad `1` Length 0.9 mm on an unsaved copy | no repair message; values of H1; report whether Length below Hole Size is accepted | no message on open, and the six pads show the values of H1. On the unsaved copy, Length 0.9 mm with Hole Size 1 mm is accepted with no message: the panel keeps Slot, 1 mm and 0.9 mm. The library was closed without saving |
| 2026-11-05 | AD 24.5 | H6 | `slots-saved.PcbLib` `f142d52c…` | File » Save As of the unchanged library, then `FENOLITE_ALTIUM_H6=<file> … -k h6` | the test passes | as expected. No message on save, and 1 passed |

Altium reads each short slot as KiCad 10.0.6 does. The hole spans the two numbers' extents, and its long
side lies across the record's slot rotation (`P2` 90°, `P6` 120°). `P3` and `P4`, which KiCad loses, lie at
30° and 120°. Altium keeps the four numbers of every pad through Save As (H4, H6). Its panel accepts a
Length below the Hole Size (H5). `norm.slot_form` and the Altium adapter need no change. `H-A-SLOT-SHORT`
keeps its level, because this is an agent run, not a kit form.

### 2026-11-05, actual `AD24.5.2.23`, Part Z (source S-1604)

A Claude agent ran Z1 to Z4 on 2026-11-05 at the maintainer's request (delegation of 2026-11-04), in the
maintainer's Windows VM, under the approved 24.5 scope. This is not the maintainer's own review.
`Client.GetProductVersion` is 24.5.2.23 (Trial licence). The kit is
`~/fenolite-altium-checks/claude-2026-11-05/c0387-Z-bodies` (`SHA256SUMS` `95e3ff5b…`; `body2.PcbDoc`
`bee5811b…`, `Box_2x1.step` `d8d09829…`), and the run used a VM copy of it. Menu commands ran through UI
Automation, and Properties fields were set by their automation ids. Each body was selected with an
authored read-only DelphiScript. The saved files stay outside the repository in
`~/fenolite-altium-runs/2026-11-05-Z/`: `Z1.PcbDoc` `b86a88cf…`, `Z2.PcbDoc` `938bf7c6…`, `Z3.PcbDoc`
`31b36fc9…` and `Z4.PcbDoc` `ca7ab0b1…`. Each holds one absolute path, its own VM file name in the header
(offset 5241). The kit privacy scan reports it, so the reader ran with `FENOLITE_KIT_REVIEWED_PREFIX` set to
that VM folder: `FENOLITE_ALTIUM_PART_Z_SAVED=<folder> uv run pytest
tests/unit/backends/altium/test_part_z.py -k saved -s`, 1 passed.

| date | version | case | file (SHA-256) | step | expected | observed |
|---|---|---|---|---|---|---|
| 2026-11-05 | AD 24.5 | Z1 | `Z1.PcbDoc` `b86a88cf…` | U1's extruded body, Board Side set to Bottom in the Properties panel | Altium accepts; report the 3D view | accepted with no message. Board Side offers `Top` and `Bottom`, and the layer stays Mechanical 13. In 3D, U1's pads show bare from the top. With View » Flip Board, a grey block appears under U1, so the body is drawn below the board. Saved: U1 `BODYPROJECTION=1`, `V7_LAYER=MECHANICAL13`, standoff 0 mil, overall 98.4252 mil. How far the block reaches below the bottom face was not measured |
| 2026-11-05 | AD 24.5 | Z2 | `Z2.PcbDoc` `938bf7c6…` | one body of each type, 2 mm high | one body per type; names of the types | the Place menu offers `Extruded 3D Body` and `3D Body`. `3D Body` opens a file chooser, Choose Model, for a STEP file. Cylinder and sphere are not Place commands: the panel's Model Type offers `Generic`, `Extruded`, `Cylinder` and `Sphere`, so two placed extruded bodies were switched to `Cylinder` (height 2 mm, radius 0.5 mm) and `Sphere` (radius 1 mm). Placed bodies have no component, so none is on `R1`. A generic body has no height field. Saved: extruded `MODELTYPE=0`, overall 78.7402 mil; generic `MODELTYPE=1`, `Box_2x1.step`, `EMBED=TRUE`, overall 16.9291 mil; cylinder `MODELTYPE=2`, overall 78.7402 mil; sphere `MODELTYPE=3`, standoff −39.3701 mil and overall 39.3701 mil; one `Models` entry |
| 2026-11-05 | AD 24.5 | Z3 | `Z3.PcbDoc` `31b36fc9…` | R1's extruded body (standoff 19.685, overall 157.48 mil): (a) overall 1, standoff −0.5; (b) overall 1, standoff 2; (c) overall 0; (d) overall 100 mm | report what is kept; the file holds what the panel keeps | no message in any step. (a) both kept: overall 39.37, standoff −19.685 mil. (b) the panel swaps them: overall 78.74, standoff 39.37 mil. (c) swapped again: overall 39.37, standoff 0 mil. (d) kept: overall 3937.008 mil, standoff 0. Saved after (d): `STANDOFFHEIGHT=0mil`, `OVERALLHEIGHT=3937.0079mil`. The file holds what the panel kept |
| 2026-11-05 | AD 24.5 | Z4 | `Z4.PcbDoc` `ca7ab0b1…` | four generic bodies from `Box_2x1.step`, Rotation Z° 0, 90, 180 and 270 in the panel | four bodies; embed asked once or four times | Altium never asked to embed. Each Place » 3D Body read the file again. Saved: four bodies `MODELTYPE=1`, `EMBED=TRUE`, `MODEL.3D.ROTZ` 0, 90, 180 and 270, and four `Models` entries, one per body, each with its own `ID`. Each entry's `ROTZ` equals its body's (`ROTX`, `ROTY` and `DZ` are 0). Placed bodies have no component, so none is on `U1`. Every body was placed by its own Place command, so the run does not separate "rotation selects the entry" from "each placement adds an entry" |

`H-A-IMP-BODY` and `H-A-IMP-BODY-Z` keep their levels, because this is an agent run, not a kit form.
Fenolite's reader reads each saved field as the panel showed it. The facts are in `pcb-bodies.md`,
"Agent observations in AD 24.5 (S-1604)".

### 2026-11-04, actual `AD24.5.2.23`, Part Q

Source S-1576. A Claude agent ran phase A at the maintainer's request of 2026-11-04 in the maintainer's
Windows VM. This is not the maintainer's own review and not the author report the rows ask for.
`Client.GetProductVersion` is 24.5.2.23 (Trial licence). The kit was built at `7074a68e` into the agent's
folder `~/fenolite-altium-checks/claude-2026-11-04/c0173-Q` with `FENOLITE_ALTIUM_PART_Q=<that folder>
uv run pytest tests/unit/backends/altium/test_part_q.py -k phase_a` (2 passed). The agent worked on a copy
of `board/` in the VM. Menu commands ran through UI Automation, and the Properties fields were set by
their automation ids. After the run, every kit input still matches `SHA256SUMS`: `board.PcbDoc`
`fd478b3a…`, `board.PrjPcb` `0c74499f…`, `board.PcbLib` `2005c279…`, `board.SchDoc` `9d59eedd…`,
`board.SchLib` `799ee1d2…`, `board.OutJob` `adfeb5f1…`.

| date | version | case | file (SHA-256) | step | expected | observed |
|---|---|---|---|---|---|---|
| 2026-11-04 | AD 24.5 | Q1 | `panel-a.PcbDoc` `83999080…` | new PCB, Place » Embedded Board Array/Panelize, `board.PcbDoc` through the PCB Document "…" button, X 5, Y 5, 2 × 2, spacing 42/32 | four boards with 2 mm gaps; note any synchronize dialog | four boards with gaps; the margin fields show 2 mm. No synchronize dialog appeared, and the save showed no message. The project file was not saved: `board.PrjPcb` is unchanged, and the output reports name the panel a free document |
| 2026-11-04 | AD 24.5 | Q2 | `panel-cols4` `a89373ac…`, `panel-rows3` `01cda5ef…`, `panel-spacing` `02f131b0…`, `panel-margin` `cc7e29c6…`, `panel-rot90` `f4f78485…`, `panel-mirror` `0c9b26b8…`, `panel-link` `c23a57e9…`, `panel-move` `32910ced…` | one change on a reopened `panel-a`, then Save As | each saves; note other fields that change | each saves with no message. Spacing 45/35 sets the margins to 5 mm. Margin 3 sets the spacings to 43/33 mm. No other field changed |
| 2026-11-04 | AD 24.5 | Q3 | none | mechanical layers V Cut and Route Tool Path | `panel-layers` saves; note the layer numbers | not run. View » Panels » View Configuration opened as a floating panel over the Projects panel, and a right-click reached another project's document. The agent dismissed that menu with Esc, chose nothing, and stopped the case |
| 2026-11-04 | AD 24.5 | Q4 | `panel-two.PcbDoc` `1552077e…` | second array at X 100, Y 5, 1 × 1 | two arrays | two arrays: 2 × 2 at (5, 5) and 1 × 1 at (100, 5). The new array starts with spacings 1500/2500 mil |
| 2026-11-04 | AD 24.5 | Q5 | `panel-a.GTL` `cf0afc72…`, `panel-a.GBL` `1a5504c0…`, `panel-a.TXT` `476dcc4b…` | File » Fabrication Outputs » Gerber Files (Apply) and NC Drill Files (OK), defaults | four copies in copper and drill; list of files | four copies. The top copper has 28 flashes and the bottom copper 12, which is 7 and 3 per copy. The drill file has 4 holes of 0.3 mm (vias) and 8 of 0.9 mm (LED pads). The outline file `GM` holds one rectangle. Gerber opened a CAM document. For NC Drill, Import Drill Data was cancelled, and an `Error` box with OK followed (its text was not read). Neither CAM document was saved. Files: `panel-a.GTL`, `.GBL`, `.GTO`, `.GBO`, `.GTP`, `.GBP`, `.GTS`, `.GBS`, `.GM`, `.apr`, `panel-a-macro.APR_LIB`, `.EXTREP`, `.REP`, `.TXT`, `.LDP`, `.DRR`, `Status Report.Txt`. They were written in `board/`, not under `Project Outputs`. The drill status report advises a separate BOM per embedded board |
| 2026-11-04 | AD 24.5 | Q6 | the ten saved panels above | copy without `History` and outputs; path scan before reading | the scan runs before anything is read | `fenolite kit verify` refuses the folder with `FEN-3001` (no `kit.json`). The kit privacy scan `privacy_scan`, called directly, finds two strings in each of the ten panels. One is a VM home folder in the Board record's `2DCONFIGFULLFILENAME`, the path of Altium's 2D view configuration. The other is the document's own VM path in its `FILENAME` header. Of the outputs, only `panel-a.LDP` holds a VM path. The folder cannot be published as it is. Only digests and the facts below were read from it |

In each saved panel, one text record per array holds `DOCUMENTPATH=board.PcbDoc` (relative), `X`, `Y`,
`COLCOUNT`, `ROWCOUNT`, `COLSPACING`, `ROWSPACING`, `MIRROR`, `ORIGINMODE` (1, and 0 with Link Location on),
`TCOLOR` and `VISIBLELAYERS`. Between `panel-a` and each variant, that record changes only in the field the
variant set, plus the spacings in `panel-margin`. No margin field is stored. `panel-rot90` has the same
record as `panel-a`, so its rotation is stored elsewhere. Its file hash differs. The opaque
`EmbeddedBoards6` stream was not read. The saved files stay in `c0173-Q/saved/board/` and the outputs in
`c0173-Q/outputs/`, both outside the repository.

`H-A-PANEL-RECORD` stays `UNKNOWN`: its row names 26.5, and these are agent observations under the
approved 24.5 scope. `H-A-PANEL-LAYERKIND` stays `UNKNOWN` (Q3 not run). Task 2.4 stays open.

**Evening retry of Q3, and Q5 (source S-1580).** At the maintainer's second request of 2026-11-04 the
agent tried Q3 again on the same VM copy of `panel-a.PcbDoc` (`83999080…`, unchanged) in Altium 24.5.2.23.
View » Panels » View Configuration again opened as a floating panel over the Projects panel. A right-click
on its "Mechanical Layers (M)" row opened the Projects panel's document menu (Open, Remove from
Project…, and so on). The agent closed it with Esc and chose nothing. A read-only DelphiScript read the
`Kind` of mechanical layer 20 as 0. The agent did not set any kind by script, because no source here
maps kind numbers to V Cut or Route Tool Path, and Q3 asks for the panel's own fields. Q3 stays not run,
and nothing was saved.

The four copies of Q5 are the expected outcome, not a defect. Q1 set Column Count 2 and Row Count 2, so
the array holds four boards. The outputs repeat each board's 7 top and 3 bottom flashes four times.

### 2026-11-04 evening, actual `AD24.5.2.23`, Part Q phase B (source S-1585)

Run by a Claude agent at the maintainer's request of 2026-11-04/05 in the maintainer's Windows VM. It is
not the maintainer's own review. The kit was built from the Part Q phase B builder at `aa49b069`
(`origin/cac/lote-14`). This branch lacks the array writer of task 7.2, so the kit came from that commit.
Its digests are `written/panel.PcbDoc` `75bb8545…`, `board/board.PcbDoc` `fd478b3a…` and
`flat/panel.PcbDoc` `ab1e0159…`. The run used a VM copy of the kit. Q8 saved only that copy of
`board.PcbDoc`. `written/panel.PcbDoc` and `flat/panel.PcbDoc` are unchanged after the run.

| case | expected | observed | result |
|---|---|---|---|
| Q7 | opens with no repair message; one 2 × 2 array of `board.PcbDoc` as `expected.md` | no new message; one array, `..\board\board.PcbDoc` with its child loaded, 2 × 2, spacing 42 / 32 mm, at (0, 5) mm, 82 × 62 mm, rotation 0, not mirrored, `OriginMode` 1; Mechanical 1 `Route Tool Path`, Mechanical 2 `V-Cut`; 40 × 0.6 mm and 4 × 3 mm non-plated free pads; 3 free 1 mm Top pads | pass |
| Q8 | after a saved move in `board.PcbDoc`, all four copies show it | the agent moved one free Top track by +2 mm in X (to 12.8, 10 – 20, 10 mm) and saved (`51361162…`, read back at the new place). The four copies still show the old place after closing and reopening both documents. The array's in-memory child board, path `written\../board/board.PcbDoc`, still lists the old track. Altium was not restarted | fail |
| Q8 (layers) | unassigned, named `V-Cut` and `Route Tool Path` | `Kind` 0 for both, the same value as the unnamed mechanical layers; the names match | pass |
| Q9 | four copies; mouse-bite and tooling holes in the non-plated drill file; `V-Cut` in its own Gerber | Gerber Files with defaults writes 11 Gerber files. Every mechanical layer is unticked by default, so no `V-Cut` file is written. The board profile is 82 × 72 mm. NC Drill with defaults writes one file, `panel.TXT`. Under `;TYPE=PLATED` it holds 4 × 0.3 mm and 8 × 0.9 mm: one via and two holes per copy. Under `;TYPE=NON_PLATED` it holds 40 × 0.6 mm and 4 × 3 mm. After Cancel in Import Drill Data, an "Error" dialog without readable text came up, and a CAMtastic document opened | partial: copies and holes pass; no separate non-plated file and no `V-Cut` Gerber by default |
| Q10 | every message; none blocks the outputs | 36 violations, all on free pads: 32 MinimumSolderMaskSliver (7.748 mil between neighbouring mouse-bite holes) and 4 HoleSize (3 mm > 100 mil). The copies' own content is not reported. The outputs of Q9 were written | pass |
| Q11 | the flat panel opens without repair; the same holes and layers; note repeated-designator messages | no new message on open; no repeated-designator message. 71 pads, the same drill table as Q9 and the same Gerber file set. DRC gives 88 violations: the same 36, plus 48 SilkToSolderMaskClearance and 4 NetAntennae from the copies' content | pass |
| Q12 | Save As `panel-saved.PcbDoc` reads back the same array | File » Save As wrote `panel-saved.PcbDoc` (`c312d8e9…`, 762368 bytes) with no message; `FENOLITE_ALTIUM_Q12=<that file> uv run pytest tests/unit/backends/altium/test_part_q.py -k q12`, run at `aa49b069`: 1 passed | pass |

`H-A-PANEL-RECORD`, `H-A-PANEL-LAYERKIND` and `H-A-PANEL-KIT` keep their levels, because this was an
agent run. `EMBEDDED_ARRAYS` stays `False`: Q8 did not pass and Q9 passed only in part. The saved files
and outputs stay in `c0173-QB2-native/`, outside the repository.

### 2026-11-05, actual `AD24.5.2.23`, Part Q

Source S-1593. A Claude agent ran this round at the maintainer's request of 2026-11-05, under the maintainer's
delegation of 2026-11-04, in the maintainer's Windows VM. It is not the maintainer's own review.
`Client.GetProductVersion` gives 24.5.2.23 (Trial licence). The agent worked on a fresh VM copy of the
S-1576 saved folder (`panel-a.PcbDoc` `83999080…`, `board.PcbDoc` `fd478b3a…`). Phase B used the kit
built at `1169f10d`. Its bytes match the S-1585 kit (`written/panel.PcbDoc` `75bb8545…`,
`flat/panel.PcbDoc` `ab1e0159…`). The View Configuration panel was floating over the Projects panel, so
the agent moved it into the document area by its window handle before clicking. During the first try
of Q3, Altium showed two "Runtime error 216" boxes and an access violation, then exited. The agent
restarted Altium (no licence prompt or other prompt) and redid Q3 from the unchanged copy; nothing of
the first try was saved.

| date | version | case | file (SHA-256) | step | expected | observed |
|---|---|---|---|---|---|---|
| 2026-11-05 | AD 24.5 | Q3 | `panel-layers.PcbDoc` `d875c453…` (162304 bytes) | View Configuration, right-click a mechanical layer, Add Mechanical Layer twice; Layer Type V Cut, then Route Tool Path; Place » Line on each; Save As | it saves; note the layer numbers and names Altium gives | as expected. Each Add Mechanical Layer opens "Edit Layer" with the next free number and a Layer Type list: N/A, Assembly Notes, Board, Dimensions, Fab Notes, V Cut, Route Tool Path, Sheet, Board Shape. Picking a type replaces the name. Mechanical 2 became `V Cut` (layer 58, `Kind` 25) and Mechanical 3 became `Route Tool Path` (layer 59, `Kind` 28). A third Add Mechanical Layer no longer offers V Cut or Route Tool Path (cancelled). One line on each layer; the save showed no message |
| 2026-11-05 | AD 24.5 | Q6 | the eleven saved panels of S-1576 and Q3, with the kit's `board/` files | copy of the folder without `History` and `Project Outputs`, zip; the kit privacy scan before anything else reads it | the scan runs before anything is read | as expected. The phase A folder has no `kit.json`, so `fenolite kit verify` refuses it (`FEN-3001`, S-1576). The agent ran the scan that `kit verify` runs (`privacy_scan`) on the zip's 18 members first. It finds 22 strings, a VM home folder and an absolute path in each panel, and none in the kit's own files. The folder stays outside the repository. Only digests and the facts in this section were read from it |

In `panel-layers.PcbDoc` the type is stored twice:

- `Board6` holds `LAYER58MECHKIND=VCut` and `LAYER59MECHKIND=RouteToolPath`, the same in the key families
  `LAYER_V8_12…`/`LAYER_V8_13…` and `V9_CACHE_LAYER70…`/`V9_CACHE_LAYER71…`, beside the new names and
  `MECHENABLED=TRUE`. `ROUTETOOLPATHLAYER=MECHANICAL3` is added, and no V Cut counterpart key is.
- `LayerKindMapping/Data` grows from the 20-byte form (value 0, count 0) to 36 bytes: the `1.0` string, the
  32-bit value `0x7984CB1F` and two 8-byte entries, (58, 25) and (59, 28). Each entry is a layer number
  and its `Kind`.

**Q8 again, and the Q9 options.** On the phase B kit the agent moved the same free Top track of
`board/board.PcbDoc` by +2 mm in X (10.8 → 12.8 mm) and saved it (`d89bdeb0…`).

- Back in `panel.PcbDoc`, the array's child board still lists the old place, as in S-1585. No menu item of
  Edit, View, Design, Tools or Place refreshes an array.
- The agent closed Altium with File » Exit (no prompt) and started it again. Opening `panel.PcbDoc` alone
  then shows the move: the child board lists the track at 12.8–20 mm, and a capture of the document
  area showed all four copies with the moved track (capture deleted after viewing).
- So the copies follow a saved change only after Altium restarts. Reopening the panel within one session
  is not enough. The child board's path reads `written\../board/board.PcbDoc`.

For Q9 the agent turned on NC Drill Setup's "Generate separate NC Drill files for plated & non-plated
holes". NC Drill then writes `panel-Plated.TXT` and `panel-NonPlated.TXT`. With `V-Cut` ticked in Gerber
Setup, Gerber writes it as `panel.GM2`. Saved as `panel-q9opts.PcbDoc` (`6bfa6477…`), the document has no
changed `Board6` key for either option; Altium's resave adds only its usual records. So these choices
are not stored in the PCB document, and a written panel cannot make them its defaults. Q9 as written
(defaults) stays partial.

Where the copies lie (change c0386, tasks 1.1 to 1.3, S-1592). Saved panels and Altium outputs per
variant: `panel-a` has its saved file and the default Gerber and NC Drill outputs of the S-1576 run;
`panel-rot90`, `panel-mirror` and `panel-link` have their saved files (S-1422) and an NC Drill output made
this day with the separate plated file still on (`panel-<variant>-Plated.TXT`, the board having plated holes
only); `panel-cols4`, `panel-rows3`, `panel-spacing`, `panel-margin`, `panel-move` and `panel-two` have
saved files and no output. `tests/unit/backends/altium/test_panel_placement.py` reads each drill file and
places the board's 3 drilled holes (the via and the 2 through-hole pads) by the array record. All 12 hits of
each of the 4 variants lie within 0.001 mm of (`X`, `Y`) + (c · `COLSPACING`, r · `ROWSPACING`) +
(p − the board's origin). `ROTATION` 90 turns the whole array about (`X`, `Y`), and `MIRROR` mirrors its X
about `X`. `panel-link` gives the same hits as `panel-a`, because the fixture board's origin is its shape's
bottom-left corner. Copper and silkscreen start more than 5 mm inside that corner, so the reference is not
the bottom-left of those objects.

Judged by the coordinator's decision of 2026-11-05, given by the maintainer's delegation: a restart
counts as Q8's reopen, and Q9 is judged with the separate drill files and the `V-Cut` Gerber on, because
those options are not stored in the PCB document. Both observations of each case stay recorded.

| case | expected | observed | result |
|---|---|---|---|
| Q7 | opens with no repair message; one 2 × 2 array of `board.PcbDoc` as `expected.md` | as S-1585: no message, one 2 × 2 array of `../board/board.PcbDoc` with the properties of `expected.md` | as expected |
| Q8 | after a saved move in `board.PcbDoc` and a reopen (a restart counts), all four copies show it | within one session, closing and reopening the panel keeps the old track; after Altium is restarted, all four copies show the move | as expected |
| Q9 | with the separate drill files and `V-Cut` on: four copies; the mouse-bite and tooling holes in the non-plated drill file; `V-Cut` in its own Gerber | with defaults, one drill file `panel.TXT` and no `V-Cut` Gerber (partial, as S-1585); with the options on, `panel-Plated.TXT` holds 4 × 0.3 mm and 8 × 0.9 mm, `panel-NonPlated.TXT` holds 40 × 0.6 mm and 4 × 3.0 mm, and `panel.GM2` holds the 2 rail score lines | as expected |

With Q7, Q8 and Q9 as expected, `EMBEDDED_ARRAYS` is set to `True` (change c0389, task 3.3). Limitation:
Altium rereads a changed board only after it is restarted. `H-A-PANEL-RECORD`, `H-A-PANEL-LAYERKIND` and
`H-A-PANEL-KIT` keep their levels, because this was an agent run. The saved files and outputs stay in the
agent's folder `claude-2026-11-05/rounds/`, outside the repository.

### 2026-11-05, actual `AD24.5.2.23`, Parts D and C, step X8.6 and the long via (source S-1601)

Run by a Claude agent at the maintainer's request (delegation of 2026-11-04) in the maintainer's Windows VM,
Altium Designer 24.5.2.23 (Trial). It is not the maintainer's own review (c0389 task 2.4). Inputs:
- copies of the committed `blink`, `routed` and `body2` files, each SHA-256 checked against the tables
  above;
- the plane variant `p0`, rebuilt by `-k variants` with digest `8e0978ec…`.

The documents were read through public menus and dialogs and through authored read-only DelphiScript.
Altium's saves were read with Fenolite's reader. No capture was kept, and every file Altium saved stays
outside the repository.

| step | observed |
|---|---|
| D1 | `blink.PrjPcb` opens and lists `blink.SchDoc`, `blink.PcbDoc`, `blink.PcbLib` and `blink.SchLib`. `blink.PcbLib` opens with no message and holds `Mini_R_0603`, `Mini_LED_THT_3mm` and `Mini_QFP-32_7x7mm_P0.8mm`. Each pad equals the pad table in shape, size and hole. Altium reports the "rounded" pads as rounded rectangles with a 50 % corner. `Mini_LED_THT_3mm` pad 1 is a rectangle and pad 2 a round pad, both 708661 with a 354331 hole on Multi-Layer. Lines and arcs lie on Top Overlay, Mechanical 13 and Mechanical 15 |
| D2 | A new PCB document added to a copy of the project, then "Update PCB Document" from `blink.SchDoc`. The change order adds 3 components, 4 nets, the component class `blink`, the net class `PWR` and 2 Supply Nets rules. Validation finds every footprint in `blink.PcbLib` and marks nothing invalid. Executed, the board holds `D1`, `R1` and `U1` with their nets |
| D3 | `blink.PcbDoc` opens with no message. Two copper layers. `D1` lies on Bottom Layer at rotation 0, its pads on Multi-Layer with `GND` and `LED_A`. The source unique ids match the schematic's. "Update PCB Document" adds no component and changes no net; it proposes only the two Supply Nets rules, which the document does not hold, and they validate |
| C6 | `p0` opens with no message. The stack is Top Layer, Internal Plane 1 (`GND`), Mid-Layer 2 and Bottom Layer. The document holds 4 tracks (none on the plane), 3 vias and one `GND` polygon on Bottom Layer. A design rule check reports "Starved Thermal" on the `GND` via (13 % of the copper connected to the hole) and on `D1` pad 1 (10 %), and an "Un-Routed Net" violation between them. These come from Altium's own Plane Connect and Un-Routed Net rules: the document writes only the 5 rules of the table. **Not as expected**: Altium does not join the `GND` via and the `GND` pad of `D1` through the plane. Connection lines were not read |
| X8.6 | `body2.PcbDoc` saved under another name. `-k saved_report` prints 3 bodies in `ComponentBodies6` and 3 in `ShapeBasedComponentBodies6`; none keeps the `MODELID` that was written, 3 hold a `MODEL.CHECKSUM` other than 0, and each body has 35 keys. These are the counts of the 2026-10-13 native run (`docs/evidence/altium-native-acceptance.md`) |
| long via | A copy of `routed.PcbDoc` (Top, Mid-Layer 1, Mid-Layer 2 and Bottom, ids 1, 2, 3 and 32; three through vias of 0.6 mm), read after each of three saves. First Altium's save as is (`s0`). Then "Tools » Remove Unused Pad Shapes" on vias with "Preserve pads on start and end layers" on (`s1`). Then the same with that option off (`s2`). `s0` writes each via in 321 bytes with the table at 209 all zero. In `s1` each via has 330 bytes: the table marks Mid-Layer 1 and 2 for the `GND` via, Mid-Layer 1 for `LED_A` and Mid-Layer 2 for `VIN` (each keeps the inner layer that its track uses). A 32-bit 1 is at 246 and a 32-bit 9 at 250, and nine bytes are inserted at 254: `04 00 80 01`, then 236220 as a 32-bit integer at 258 (the via diameter, 0.6 mm), then `00`. Nothing else differs. `s2` differs from `s1` only at 240, set for the `GND` and `LED_A` vias, whose bottom pad nothing touches. Byte 240 is 208 + 32, the id of Bottom Layer, while Bottom Layer is fourth in the stack |

Not run: C5 (the Viewer upload). The C6 failure leaves `H-A-PCB-CU-PLANE` pending. No level changes.

### 2026-11-05, actual `AD24.5.2.23`, C6 rerun after c0389 task 2.7 (source S-1607)

Run by a Claude agent at the maintainer's request (delegation of 2026-11-04), relayed by the coordinator. It
used Altium Designer 24.5.2.23 (Trial) in the maintainer's Windows VM. It is not the maintainer's own review.
The input is the plane variant `p0`, rebuilt at `cdf2f84c` by `-k variants`, with digest `4082a630…`, the
digest the table above names. It was opened from a VM copy, read with authored read-only DelphiScript and
checked with Tools » Design Rule Check » Run Design Rule Check, in the same way as the run of S-1601. The
document was closed without saving and its digest is unchanged.

| step | observed |
|---|---|
| C6 | `p0` opens with no message. The stack is Top Layer, Internal Plane 1 (net `GND`), Mid-Layer 2 and Bottom Layer. The board holds 4 tracks (none on the plane), 3 vias, one `GND` polygon on Bottom Layer and one split plane on Internal Plane 1 with net `GND`; no connection line is listed. The rules include `PlaneConnect` ("Relief Connect", expansion 20 mil, conductor 10 mil, air gap 10 mil, 4 entries, `All`) and `PlaneClearance` (20 mil, `All`) besides the five written rules and Altium's defaults. The design rule check reports 42 violations: 1 Net Antennae (the `VIN` track on Bottom Layer), 10 Silk To Solder Mask Clearance and 31 Minimum Solder Mask Sliver. **No Starved Thermal and no Un-Routed Net**: the S-1601 violations on the `GND` via, on `D1` pad 1 and between them are gone. The rule descriptor does not show the via connect style, so "vias Direct" was not read |

The 42 remaining violations concern silk, solder mask and one antenna; the S-1601 report names only the plane
and routing violations, so they are not compared here. `H-A-PCB-CU-PLANE` keeps its level, because this
was an agent run. The decision is left to the coordinator.

### 2026-11-04, actual `AD24.5.2.23`, Part T

Source S-1571: [T1–T6 report](altium-part-t-convert-2026-11-04.md) and
[measured recap](altium-part-t-convert-24-native.json). Run by a Claude agent at the maintainer's
request of 2026-11-04 in the maintainer's Windows VM, not the maintainer's own review. At source
`d155b258` only PADSTACK converts: SCHEMATIC is refused with `FEN-3005` and DIFAT fails with `FEN-1001`.
These two cases were observed on the 2026-10-12 bundle (`complex_hierarchy.PcbDoc` `23a77447…`,
`vme-wren.PcbDoc` `62d026e1…`). Inputs are unchanged after the run, and nothing was saved.

| case | T1–T2 | T3–T4 | T5 | T6 |
|---|---|---|---|---|
| PADSTACK (current) | opens and compiles with no error; 1 component, 1 net | no polygon; 0 violations | no differences | PCB pad, PcbLib pad and the pad of the placed copy are equal: Full Stack, In1 1.2 × 1.2 mm shape 1, In2 1.4 × 1.1 mm shape 2 |
| SCHEMATIC (2026-10-12) | opens; three sheets, 68 components, 56 nets; 3 errors and 20 warnings | the one polygon pours; 217 violations, 194 of them silk | 2 of 68 components unmatched by unique id; ECO removes 2 net classes, no footprint change | not run |
| DIFAT (2026-10-12) | opens; 1508 components, 1847 nets; at least 976 messages (469 one-pin-net errors) | 92 of 134 polygons pour; DRC stops at 500 | parameter changes and 2 pins added to nets on `L1`; no footprint change | not run |

Connector masks are not exercised: no source has a `connect` pad. The four `H-A-CONV-*` rows stay
`INFERRED`, and c0160 5.3 and c0166 2.1 stay open.

### 2026-11-04, actual `AD24.5.2.23`, Part S

Source S-1570: [S1/S2/S8 report](altium-part-s-slots-2026-11-04.md) and
[measured recap](altium-slots-s1-s2-s8-24-native.json). Run by a Claude agent at the maintainer's
request of 2026-11-04 in the maintainer's Windows VM, not the maintainer's own review. It uses the same
input digests as S-1297: regions `be65d4b9…`, clearance `822d31cf…`, gate-off `c798ec46…`. All inputs
are unchanged after the run, and nothing was saved.

| Case | Measured observation | Result |
|---|---|---|
| S1 | Opens with no message. `D1` is a free Multi Layer pad with no designator, a 2 × 12 mm unplated slot, no ring and mask/paste mode 1 (rule values 4 mil/0). NC Drill defaults put it in the NON_PLATED slot file at 30° about (27, 7). Drill Drawings show only the T1 slot symbol, with no slot outline and no legend | as expected for the pad and NC Drill; drill drawing by symbol only |
| S2 | DRC (existing options) reports Hole To Hole `Pad/Via Touching Holes` for `D2`–`D3`, with the same 7 findings as S5 | as expected |
| S8 | Four holes and no cut-out region; the report names `cutout/1`, `slot/S1`, `slot/S2+slot/S3` | as expected |

Every case S1–S8 now has a current24 observation on these digests, but from separate operator
sessions and with no formal record. `H-A-SLOT-KIT` stays `INFERRED`, and task 5.2 stays open.

### 2026-11-03, actual `AD24.5.2.23`, Part S

Source S-1297: [current native report](altium-part-s-slots-2026-11-03.md) and
[measured recap](altium-slots-24-native.json). S3/S4 and the S5 literal result subtest pass on current24; historical26.5
observations are unchanged. All three native input hashes remain exact. No global settings changed.

| Case | Measured observation | Result |
|---|---|---|
| S3 | Planning/2D/actual3D openings plus native NC3drilled slots/1round NPTH, no milled/cut-out hit | as expected |
| S4 | One selected L Region, Kind Board Cutout, authored rounded extremities | as expected |
| S5 | Complete stable7-row native DRC result: TP1 pad Board Outline Clearance7.874mil<19.685mil; no TP2 in that category. All Rules, Normal mode,0waived, cap500 not reached; all other findings retained. No independent native TP2 object census. | as expected |
| S6 | Later actual Repour All once on scratch822, AD24.5.2.23; Top Layer copper remains outside S1, the merged L and cut-out1; no observed message. Scratch dirty, no save/reopen, new DRC or SDK. | as expected |
| S7 | Actual24.5.2.23 Save As of original regionsbe65d4 to new saved34baa3; existing S7readback exits0,1pass/1deselected, same4holes/3cutouts within1µm. Original/staged/saved bytes unchanged; no added reopen/DRC/SDK. | as expected |

At capture time, S1/S2/S6/S7/S8 current24 outcomes remained open, CUTOUT_REGIONS was false and
H-A-SLOT-KIT was INFERRED. Those observation records and their input hashes are unchanged.

Functional continuation, 2026-11-03: retained current24 S3/S4/S5 satisfy only the functional
cut-out gate. Task5.1a enables CUTOUT_REGIONS and the default three written cut-outs, while
preserving the explicit gate-off regression. S6 and aggregate5.2 remain open in this continuation;
H-A-SLOT-KIT remains INFERRED. This does not declare a clean DRC, complete current24 kit, formal
kit record, writer graduation or release approval.

Later literal S6, observed at native VM UTC2026-11-04T00:10:20Z and reviewed at
host UTC2026-11-04T00:11:02Z: [separate measured record](altium-slots-s6-24-native.json).
The root operator invoked public Repour All once on a fresh scratch copy of
input822d31cf. Actual red Top Layer copper remains and is absent inside S1,
the merged L S2+S3 and the rounded cut-out1; no message was observed and the
main returned enabled/foreground with only the scratch dirty. A previous
attempt refused before expanding the menu or invoking repour. No Save, reopen,
new DRC or SDK was requested; this does not alter the earlier seven findings
or prove a saved fill. Only the S6 literal outcome is now as expected.
Aggregate5.2 and H-A-SLOT-KIT remain open/INFERRED; no full kit, Part T,
graduation, CI, archive or release result follows. VM/host clocks were not
calibrated; their timestamps are retained separately.

Later literal S7: [source-bound Save As/readback](altium-slots-s7-24-native.json)
records actual24.5.2.23 output34baa3 from original regionsbe65d4 and the
existing readback1pass onad8cbf2e. Only S7 is completed; raw receipts have no
operation timestamp and no clock equivalence is inferred. S1/S8 remain
pending; task5.2, formal bools/record, H-A-SLOT-KIT and writer graduation
are unchanged. Native-saved bytes stay outside the repository.

### 2026-10-17, `AD 26.5`, Part S

Native run on Windows of the kit built from `670f02d`, recorded in full in
`docs/evidence/altium-part-s-slots-2026-10-17.md` (S-0812). S1, S2, S4, S5, S6, S7 and S8 as expected. S1:
the slot pad is a free Multi-Layer pad with no ring and a 2 × 12 mm non-plated slot, and its solder mask
and paste expansions come from the rules, as Fenolite writes them. S3 is incomplete: Board Planning Mode
shows the three openings and the NC output holds no hit for a milled form, but the 3D Layout Mode viewport
stayed blank (a black view with no board), so the board shape in 3D was not observed. `H-A-SLOT-KIT` stays
`INFERRED` and `pcbdoc.CUTOUT_REGIONS` stays false until S3 is repeated. No native file is committed.

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

## Part T — converted projects (c0160)


Pending maintainer report; no Altium verification is claimed. The runtime bundle contains three
KiCad cases: two registered public projects (large DIFAT document and a source schematic with repeated
child sheets) and an authored four-layer Full Stack case with different inner-layer shapes/sizes.
It includes conversion reports, a README and SHA-256 hashes. Work on scratch copies.

| step | action | report |
|---|---|---|
| T1 | Open all three project, PCB, schematic and library documents | load outcome and any errors |
| T2 | Compile each project; inspect sheet instances and connectivity | compile outcome |
| T3 | Repour polygons in each PCB | repour outcome |
| T4 | Run DRC on each converted board | counts by rule category; losses are listed in the conversion report |
| T5 | Update PCB from schematic and inspect the ECO | unexpected footprint changes, without executing them on the only copy |
| T6 | Place a PcbLib footprint in a scratch board; inspect its padstack and connector masks | placement and pad/mask outcome |

Send the Altium Designer major/minor version, date and one generic result for each step. No source
project, screenshots or employer details are needed. T1/T3 settle `H-A-CONV-DIFAT`, T4/T6 settle
`H-A-CONV-PADSTACK`, T5/T6 settle `H-A-CONV-LIBRARY`, and T1/T2 settle `H-A-CONV-SCHEMATIC`.
These four hypotheses remain open until the corresponding actual report is recorded.

## Clearance checks of 2026-10-14

At the maintainer's request, both optional checks of c0125/c0130 ran through guarded
scripts and owned dialog messages in native Altium Designer Professional 26.5.0.
The two scratch boards are authored for Fenolite; no private or vendor board is used.
S-0744 and `altium-clearance-2026-10-14.json` retain fingerprints and constraint lines.
Raw reports and native saved boards remain ignored because they contain local paths.

| case | authored constraints and planted copper | actual native result |
|---|---|---|
| M1-M3, layer scopes | Two copper layers; inner `OnMid` 7 mil, outer `ExistsOnLayer` 5 mil, parent matrix 10 mil. Separate track-track on top, via-track on bottom and via-via pairs, each with a 4-mil edge gap | Three violations, each explicitly `4mil < 5mil`; none uses 7 or 10 mil. Native save keeps all three tracks and three vias and both scope expressions |
| C1-C2, matrix cell | Generic 4 mil with `ClearanceObj_Via-ClearanceObj_Via:35000` (3.5 mil). Separate via-via and via-track pairs, both at 3.7 mil | One violation, via-track, explicitly `3.7mil < 4mil`. The via-via pair passes. Native save keeps all three vias, the track and the cell text |

The original M report executed no Clearance check and is retained as an invalid attempt,
not as a zero-violation pass. The retry selects rule kind 0 and proves that Clearance ran.
The C dialog's first launch timed out while open and was cancelled; its retry completed.
Native report headings group the M violations under the 10-mil parent matrix, while each
constraint line gives the actual 5-mil limit. On save, Altium renames its child rules to
`Fallback_1` (inner) and `Fallback_2` (outer). A parent heading alone cannot identify the
governing child; this differs from the original protocol's expectation of a named child
in the summary and changes no imported scope or clearance.

Native saved readback agrees with Fenolite's copper check: three findings in M, one in C.
Input hashes remain unchanged. The verifier asserts report counts, pair kinds, exact
thresholds, native saved scopes/cell values and matching Fenolite counts.
These outcomes complete the two requested experiments. The wider hypothesis rows
`H-A-RULE-CLEARANCE-FORMS` and `H-A-RULE-CLEARANCE-CELLS` remain `INFERRED`: no human
author report or published kit archive is claimed, and this experiment does not test
four-layer scoping, all matrix object kinds or cross-rule priority.

## Approved pending-native scope — 2026-11-03

The maintainer explicitly authorized the pending Altium validations on the
available Altium Designer 24.5.2.23: "tenho so o24.5, mas eu autorizo as
validacoes serem no24, nao precisa ser na26". This replaces the version
prerequisite of pending runs only. Record the actual tool/build, input hashes
and each observed outcome. It does not complete a case, open a write gate,
raise evidence, prove26.5 equivalence or replace any historical26.5 report.
Do not combine different versions/input digests into one fictional kit run.
All existing acceptance criteria, facts-before-code rules and final CI remain.
The kit form keeps its existing AD major.minor dialect: use AD 24.5; keep full
build 24.5.2.23 in the separate native observation report, not a new form key.
