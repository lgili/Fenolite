## MODIFIED Requirements

### Requirement: Polygon pour records
`pcbdoc.write_pcbdoc` SHALL write each `model.board.Zone` of `PcbDocSpec.zones` as one `Polygons6` property record per zone layer, with or without poured copper by its pour mode ("Polygon pour modes"; S-0160, S-0172, S-0174, S-0175, S-0176, S-0195, S-0196, S-0833; `H-A-PCB-CU-REPOUR`).
- A record MUST hold, in this order: the seven common keys with `LAYER` = the layer text; `PRIMITIVELOCK=TRUE`, `POLYGONTYPE=Polygon`, `POUROVER=TRUE`, `REMOVEDEAD=TRUE` (`FALSE` for a zone whose islands are never removed, change c0085), `GRIDSIZE=20mil`, `TRACKWIDTH=8mil`, `HATCHSTYLE=Solid`, `USEOCTAGONS=FALSE`, `MINPRIMLENGTH=3mil`; per vertex `KIND<k>=0`, `VX<k>`, `VY<k>`, `CX<k>`, `CY<k>`, `SA<k>`, `EA<k>`, `R<k>` as the board outline writes them, the first vertex repeated last; `SHELVED=FALSE`, `RESTORELAYER=UNKNOWN`, `RESTORENET` (empty), `REMOVEISLANDSBYAREA=TRUE`, `REMOVENECKS=TRUE`, `AREATHRESHOLD=250000000000.000000`, `ARCRESOLUTION=0.5mil`, `NECKWIDTHTHRESHOLD=5mil`, `POUROVERSTYLE=1`, `NAME`, `POURINDEX`, `IGNOREVIOLATIONS=FALSE`, `AUTONAME` (only when the name is generated), `OPTIMALVOIDROTATION` (`TRUE` with the pour mode `outline`, `FALSE` with `computed`, change c0215), and `NET` (the net's index; left out without a net).
- `NAME` MUST be the character codes of the name in decimal, joined by commas. The name is `Zone.name`, or `<net name>_L<layer position, two digits from 01>_P<pour index, three digits>` when it is empty (`NONET` stands for a missing net), in upper case, with `AUTONAME=TRUE`.
- `POURINDEX` MUST number the records from 0 in the order of falling `Zone.priority`, then net name, first outline point, zone id and stack position, so a zone of higher priority is poured first. `POURINDEX` MUST equal the record's position in `Polygons6`.
- With the pour mode `outline`, `Regions6` and `ShapeBasedRegions6` MUST hold no region of a polygon (they hold the filled graphics, keep-outs and cut-outs only, and stay empty without them). `Zone.fills` MUST NOT be written in either mode: a computed pour comes from the document ("Poured regions"), never from the model.
- A zone with fewer than three outline points, a zone layer outside the copper layers or on a plane, or a name that fails `text_problem` MUST raise `ValueError` naming the zone's id.

#### Scenario: Ground zone on two layers
- **GIVEN** a zone on `In1.Cu` and `B.Cu` with the net `GND`, four outline points and priority 0, and a second zone on `F.Cu` with priority 2
- **WHEN** `Polygons6` is read after a write with the pour mode `outline`
- **THEN** it holds three records; the `F.Cu` record has `POURINDEX=0`; the two `GND` records have `LAYER=MID1` and `LAYER=BOTTOM`, five vertices, `NET` equal to the index of `GND`, and names that decode to `GND_L02_P001` and `GND_L04_P002`; `Regions6` is empty

#### Scenario: Zone without an outline refused
- **WHEN** a spec holds a zone whose `outline` is empty
- **THEN** `write_pcbdoc` raises `ValueError` naming the zone's id

#### Scenario: Zone fills of the model are not written
- **GIVEN** a zone whose `fills` hold a ring that differs from what the engine pours
- **WHEN** the document is written with the pour mode `computed`
- **THEN** the regions of the polygon are the engine's pieces, and no region holds the model's ring

## REMOVED Requirements

### Requirement: Unpoured polygons are a contract
**Reason**: the maintainer's decision of 2026-10-26 (roadmap, "Open decisions", row 48) supersedes row 23 of c0085: Fenolite computes the pour of the polygons it writes ("Polygon pour modes", "Poured regions"; capability `altium-pour`).
**Migration**: `--altium-pour outline` (library: `pour="outline"`) writes every polygon unpoured, as this requirement did, with the same `altium.zones-unpoured` info.

## ADDED Requirements

### Requirement: Polygon pour modes
`pcbdoc.write_pcbdoc(spec, *, pour="outline")` SHALL take the pour mode `outline` or `computed`.
- With `outline`, every polygon MUST be written unpoured with its net, layer, outline, priority (as the pour index) and island removal, the document's bytes MUST be those the writer gave for the same spec before change c0215, and the build MUST report `altium.zones-unpoured` (info) once, with the count.
- With `computed`, the writer MUST write the document without pour regions, read it back with Fenolite's reader, pour that reading with `pour.pour_reading` (capability `altium-pour`), and write the document again with the regions of every polygon that is not refused ("Refusal of a pour"). It MUST also write `OPTIMALVOIDROTATION=FALSE` in every polygon record and the Polygon Connect Style rules of "Polygon Connect Style records".
- `computed` without the `geo` extra MUST raise `BackendUnavailable` with a hint naming `fenolite[geo]`; a command maps it to exit 6.
- `pour_regions=False` (internal; for the kit's reference input and tests only) MUST give the bytes of the `computed` document without the regions of the polygons.

#### Scenario: Outline mode keeps the bytes
- **WHEN** `uv run pytest tests/unit/backends/altium/test_pour_modes.py -k outline` writes every committed Altium sample with `pour="outline"`
- **THEN** each document equals its committed bytes

#### Scenario: Computed and reference inputs differ in the pour only
- **WHEN** the kit sample `pour` is written with `pour="computed"` and with `pour="computed", pour_regions=False`
- **THEN** the two documents differ only in `Regions6` and `ShapeBasedRegions6`, and in their headers' record counts

### Requirement: Poured regions
With the pour mode `computed`, `pcbdoc.write_pcbdoc` SHALL write each piece of a poured polygon as one region in `Regions6` and its twin at the same position in `ShapeBasedRegions6`, in the form of the fact rows of `docs/formats/altium/pcb-pour.md`, "Written form" (`H-A-POUR-REGION`).
- The prefix MUST hold the polygon's layer, no net (`0xFFFF`: the net is the polygon's), the polygon's index (its position in `Polygons6`) and no component, with the flags `0C 00`.
- The keys and their order MUST be those of the census of poured regions in the public corpus (task 1.3 of change c0215). The plain form MUST hold the holes of the piece; the shape-based form MUST hold them in the form the census found, every vertex straight.
- The regions of the polygons MUST come together, in polygon order and then by the lowest point of each piece, at the place in the storage that the census found. Vertices MUST be whole units, each ring without a slit, at least three vertices.
- Fenolite's reader MUST read the written document back to zones whose fills equal the written pieces within one unit; KiCad's importer MUST read them as the zone's fills (`H-A-POUR-KICAD`).

#### Scenario: A piece with a hole read back
- **GIVEN** the poured `GND` polygon of the scenario "Clearance around a pad of another net" of `altium-pour`
- **WHEN** `uv run pytest tests/unit/backends/altium/test_pour_regions.py` writes it and reads it back
- **THEN** `Regions6` and `ShapeBasedRegions6` hold one region each, with the polygon's index and no net, and the read zone has one fill whose outer ring and hole equal the engine's within one unit

#### Scenario: KiCad imports the pour
- **WHEN** `uv run pytest tests/kicad/altium/test_pour_import.py -rA` imports the computed kit sample `pour` with `kicad-cli pcb import` (10.0.6)
- **THEN** each imported zone holds fills equal to the written pieces within 10 nm, and the zones of refused polygons hold none

### Requirement: Polygon Connect Style records
With the pour mode `computed` and at least one polygon, `pcbdoc.write_pcbdoc` SHALL write Polygon Connect Style rules (kind number 20) in `Rules6` after the kinds of "Design rule records", in the Advanced form of the fact rows of `docs/formats/altium/pcb-pour.md`, "Polygon Connect Style" (`H-A-POUR-CONNECT`), lowered from the zones (the maintainer's decision of 2026-10-26):
- One rule scoped `InNet('<net>')` per net whose zones agree on `ZoneSettings.connection`, `thermal_gap`, `thermal_spoke_width` and `clearance` (through `effective()`): `thermal` is Relief Connect for through-hole and SMD pads; `thru_hole_only` is Relief Connect for through-hole pads and Direct Connect for SMD pads; `solid` is Direct Connect for both; `none` is No Connect for both with `clearance` as the air gap. A relief MUST have 4 conductors at 90°, the conductor width `thermal_spoke_width` and the air gap `thermal_gap`. Vias MUST be Direct Connect in every rule.
- One `All` rule from `ZoneSettings()`, with the last priority; priorities count from 1 within the kind, the net rules in net-name order.
- A net whose zones disagree MUST get the rule of its zone of highest priority (then the lowest zone id); each other zone of the net, and each pad with its own `zone_connection`, MUST give one `altium.not-lowered` with `where` `zone/<id>` or `pad/<id>`.
- In a rewrite of a read document, Polygon Connect Style records that map exactly (`connectstyle.read_connect_styles`) MUST be written back as they were read, and the lowering above applies only when one does not map; each record that does not map MUST be reported.
- Fenolite's reader MUST map the written records back to the same `connectstyle.ConnectStyle` values.

#### Scenario: One rule per net and a default
- **GIVEN** the kit sample `pour`, whose four probe nets of P2 hold zones with the connections `thermal`, `thru_hole_only`, `solid` and `none`
- **WHEN** it is written with `pour="computed"` and its rules are read back
- **THEN** `Rules6` holds the records of kind 20 of those four nets scoped `InNet`, the other probe nets' rules, and one `All` rule with the last priority; each maps back to the style of its net, and every via setting is Direct Connect

#### Scenario: Zones of one net disagree
- **GIVEN** two `GND` zones, the first of priority 1 with `thermal` and the second of priority 0 with `solid`
- **WHEN** the document is written with `pour="computed"`
- **THEN** the `GND` rule is Relief Connect, and one `altium.not-lowered` names the second zone
