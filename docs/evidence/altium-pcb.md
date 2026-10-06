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
| `tests/data/altium/blink/blink.SchDoc` | `4f72b375b0292cb1c4241898f6ba6241382266926bdc96788cc66ca065efcf12` |
| `tests/data/altium/blink/blink.SchLib` | `4f3accb1f9634c7cedd305240493e6d6e9a2cfde3d3e0ff0aee0a75e6387517e` |

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
| `tests/data/altium/routed/routed.SchDoc` | `7fe119a7d4aeaac4e839efb62edaedcea16f0122cebd65a6529761a719f474be` |
| `tests/data/altium/routed/routed.SchLib` | `d5c422088de0150389ebee25d625dbeeba298d7099973b8588bc70593680a0fe` |
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

Not yet reported. The sample is the project `board6` (`tests/_altium_board6.py`): the blink design on six
copper layers with one item of every kind that change c0085 writes. The five files are the committed
golden files; `FENOLITE_ALTIUM_BOARD6=<folder outside the repository> uv run pytest
tests/unit/lens/test_altium_pcb_complete.py -k golden` writes the same bytes into a folder to open in
Altium Designer. No file that Altium wrote is committed.

| file | SHA-256 |
|---|---|
| `tests/data/altium/board6/board6.PcbDoc` | `9da3b8c4bd6f1c832251bccfc3eb02e93e714cb179f55af16c08a0ec21b83e8a` |
| `tests/data/altium/board6/board6.PcbLib` | `9d09f5126ba6aad6026f4c85fa2899c908eaa363aeaec1b58b59e64a11666e22` |
| `tests/data/altium/board6/board6.PrjPcb` | `75e7078fdb8fc79b606ad0c0a3acf30103faada43dc440a7fb01e5daad2f7219` |
| `tests/data/altium/board6/board6.SchDoc` | `7b5a19f0decab17ec29c33b42c913201db35d399738af3c6fb0e92b3b3ccb0c2` |
| `tests/data/altium/board6/board6.SchLib` | `c88e8978ada89f2168ce32a551b852386d7cb6912ac2345694af479df6325cb0` |

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
8. **X8** Not run: component bodies were cut from change c0085 and are not written.
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

A step that fails refutes the row it names: the row keeps its id and gets a registered successor. An
author report never moves an operation out of `experimental`.

## Part U: rules (change c0084)

Change c0084 writes the rules of the design by kind and scope (`docs/altium.md`, "Rules";
`docs/formats/altium/pcb-copper.md`, "Rule kinds lowered"). No step of this part has been run: every row
it names is `INFERRED`, and nothing here is `ALTIUM-VERIFIED`.

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
| `rules/routed.SchDoc` | `7fe119a7d4aeaac4e839efb62edaedcea16f0122cebd65a6529761a719f474be` |
| `rules/routed.SchLib` | `d5c422088de0150389ebee25d625dbeeba298d7099973b8588bc70593680a0fe` |

The library, the project file and the schematic are the committed files of Part C; only the PCB document
differs, and only in `Rules6`.

**The rules written**, as Fenolite reads them back from `rules/routed.PcbDoc`. Every row but
`Clearance_PWR` is a rule of the design; `Clearance_PWR` is the rule of the net class, which the board-wide
rule `Clearance` now precedes. `routed.RUL` holds the ten records of the design's rules, not
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
