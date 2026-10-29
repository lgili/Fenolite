## ADDED Requirements

### Requirement: Pour inputs are recorded facts
`docs/formats/altium/pcb-pour.md` SHALL hold one fact row per input of a pour (inputs I1 to I21 of the design of change c0215), each with its source from `docs/evidence/sources.md` and its label, or with the registered `H-A-POUR-*` hypothesis that stands for it, in the fact-table form that `tests/unit/test_format_facts.py` checks. `fenolite.backends.altium.pour.INPUTS` SHALL name the row of each input, and the engine MUST NOT use an input that has no row.

#### Scenario: Every input has a row
- **WHEN** `uv run pytest tests/unit/backends/altium/test_pour_inputs.py -k rows` compares `pour.INPUTS` with the rows of `pcb-pour.md`
- **THEN** every input names a row, every row names an input, and every row has a registered source or a registered hypothesis

### Requirement: Pour engine
`fenolite.backends.altium.pour.pour_reading(reading, *, backend=None)` SHALL compute, for each polygon of a PCB document as Fenolite's reader reads it, the pieces of its poured copper from that reading only: its polygon records, its rules, its objects and its board shape.
- The area of a polygon MUST be its outline within the board shape (I17), less the governing clearance (I2) around each object of another net (I18, I19), less each keep-out with the copper restriction on its layer or on the Keep-Out layer (I16), less the copper of the earlier polygons of other nets on its layer grown by their clearance, polygons being poured in rising `POURINDEX` (I9).
- Objects of the polygon's net MUST be treated by `POUROVERSTYLE` (I8), and its pads and vias by the governing Polygon Connect Style (I5 to I7).
- The steps MUST run in the order of I11: the area and its voids; necks removed by an opening of `NECKWIDTHTHRESHOLD` when `REMOVENECKS` is true (I10); conductors and direct joins; the pieces; pieces below `AREATHRESHOLD` removed when `REMOVEISLANDSBYAREA` is true (I12); dead copper removed when `REMOVEDEAD` is true (I13).
- Each curve MUST become chords within the polygon's `ARCRESOLUTION`, with voids outside the true curve and copper corners inside it, so that no copper of the pour lies nearer to an object than its governing clearance (I14).
- The same reading MUST give the same pieces in the same order. The engine MUST use the `clipper` backend of the `geo` extra and MUST import it only when called.
- Each `PolygonPour` MUST name the hypotheses its inputs used.

#### Scenario: Clearance around a pad of another net
- **GIVEN** an authored two-layer reading with a `GND` polygon on the top layer, a round `VIN` pad of 1 mm inside it and one `All` Clearance rule of 0.3 mm
- **WHEN** `uv run pytest tests/unit/backends/altium/test_pour_engine.py -k clearance` pours it
- **THEN** the pour is one piece with one hole around the pad, and every point of the piece lies at least 0.3 mm and the hole's edge at most 0.3 mm plus `ARCRESOLUTION` from the pad's edge

#### Scenario: Relief of a pad of the polygon's net
- **GIVEN** a `GND` through-hole pad inside the `GND` polygon and one Polygon Connect Style rule: relief, 4 conductors at 90°, conductor width 0.25 mm, air gap 0.25 mm
- **WHEN** the reading is poured
- **THEN** the piece has a void of the pad grown by 0.25 mm crossed by four conductors 0.25 mm wide at 0°, 90°, 180° and 270°, and the pad touches the piece through them

#### Scenario: Necks below and above the width
- **GIVEN** `VIN` pads that leave two `GND` necks, one 4.5 mil and one 5.5 mil wide, with `NECKWIDTHTHRESHOLD=5mil`
- **WHEN** the reading is poured
- **THEN** no copper lies at the narrowest point of the first neck and copper lies at the narrowest point of the second

#### Scenario: Dead copper
- **GIVEN** an area of the `GND` polygon enclosed by `VIN` tracks, above the island area and without a `GND` object
- **WHEN** the reading is poured with `REMOVEDEAD=TRUE`
- **THEN** no piece covers that area

#### Scenario: Repeatable
- **WHEN** the same reading is poured twice
- **THEN** both results are equal, piece for piece and vertex for vertex

### Requirement: Refusal of a pour
A polygon SHALL keep its outline only, as an unpoured polygon, when one of its inputs refuses it (a reason of `pour.REASONS`), when Fenolite's copper check of the poured reading reports a short or a clearance finding that involves its copper, or when it is a later polygon of the same layer whose outline, grown by the largest clearance of that layer, meets a refused polygon. The closure MUST be computed again after each refusal until no finding involves a pour. Each refused polygon MUST give one `altium.zone-unpoured` (warning) with `where` `zone/<id>` and its reason.

#### Scenario: A rule scope the reader does not parse
- **GIVEN** a reading with a Clearance rule scoped `InPolygon('GND_L01_P000')`, the polygon `GND_L01_P000`, a later `VIN` polygon on the same layer that overlaps it, and a polygon on the bottom layer
- **WHEN** `uv run pytest tests/unit/backends/altium/test_pour_refusal.py -k scope` pours it
- **THEN** `GND_L01_P000` is refused with the reason `rule-scope`, the `VIN` polygon with `depends-on-refused`, the bottom polygon is poured, and two `altium.zone-unpoured` are given

#### Scenario: The self-check refuses a bad pour
- **GIVEN** a test engine that pours `GND` 0.1 mm from a `VIN` track under a Clearance rule of 0.2 mm
- **WHEN** the document is written with `pour="computed"`
- **THEN** the polygon is written with its outline only, its reason is `copper-check`, and the written document holds no region of it

### Requirement: Pour comparison
`fenolite.backends.altium.pourcompare.compare_pours(candidate, reference, *, points=())` SHALL compare the pours of two readings of one board, polygon by polygon, matched by layer, name and `POURINDEX`, and SHALL write nothing. With `d` the polygon's `ARCRESOLUTION`, a polygon passes when:
- **M1** the area of the XOR of the two pours is at most `d` times the boundary length of the reference pour;
- **M2** no part of the XOR still has area after an inward offset by `d`;
- **M3** the pieces match one to one, each overlapping exactly one piece of the other side by more than half the smaller area, with the same number of holes;
- **M4** each matched piece touches the same objects, and each net's objects form the same connected groups through copper, the pours included;
- **M5** both sides agree at every declared point of `points`; a point where both sides contradict its declaration is reported as a fault of the probe.
The verdict MUST name each failed criterion with the polygon and, for M2, the centre, the area and the side that holds the copper.

#### Scenario: A pour against itself
- **WHEN** `uv run pytest tests/unit/backends/altium/test_pour_compare.py -k self` compares a reading's pour with itself
- **THEN** every polygon passes M1 to M5

#### Scenario: A neck kept on one side
- **GIVEN** a candidate that keeps a 0.2 mm neck that the reference removed, joining two of its pieces
- **WHEN** the pours are compared
- **THEN** the polygon fails M2 at the neck's place with the copper on the candidate's side, and fails M3

#### Scenario: Two approximations of one curve
- **GIVEN** a void around a round pad drawn with 64 chords in the candidate and 32 in the reference, both within `ARCRESOLUTION`
- **WHEN** the pours are compared
- **THEN** M1 and M2 pass

#### Scenario: A missing conductor
- **GIVEN** a candidate whose relief has three of the reference's four conductors
- **WHEN** the pours are compared
- **THEN** M2 fails at the missing conductor and M4 passes

### Requirement: Computed pours are experimental
Every computed pour SHALL carry the evidence level `INFERRED` and the hypotheses it used until a K6 round of the kit on Altium Designer passes every step of the samples `pour` and `pour4`. `altium.zones-poured` (info) MUST name the count, say that the pour is computed by Fenolite and experimental, and name "Tools » Polygon Pours » Repour All" as the way to Altium's own copper.

#### Scenario: Routed built with a computed pour
- **WHEN** the routed sample's model (one `GND` zone on `In1.Cu` and `B.Cu`) is built for Altium with the pour mode `computed`
- **THEN** `result.pcb.pour.mode` is `computed`, `result.pcb.pour.evidence` is `INFERRED`, its `hypotheses` hold `H-A-POUR-OPEN`, and one `altium.zones-poured` names 2 polygons and "Repour All"
