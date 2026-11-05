# altium-pour Specification

## Purpose
TBD - created by archiving change c0215-altium-repour. Update Purpose after archive.
## Requirements
### Requirement: Pour inputs are recorded facts
`docs/formats/altium/pcb-pour.md` SHALL hold one fact row per input of a pour (inputs I1 to I21 of the design of change c0215), each with its source from `docs/evidence/sources.md` and its label, or with the registered `H-A-POUR-*` hypothesis that stands for it, in the fact-table form that `tests/unit/test_format_facts.py` checks. `fenolite.backends.altium.pour.INPUTS` SHALL name the row of each input, and the engine MUST NOT use an input that has no row.

#### Scenario: Every input has a row
- **WHEN** `uv run pytest tests/unit/backends/altium/test_pour_inputs.py -k rows` compares `pour.INPUTS` with the rows of `pcb-pour.md`
- **THEN** every input names a row, every row names an input, and every row has a registered source or a registered hypothesis

### Requirement: Pour engine
`fenolite.backends.altium.pour.pour_reading(reading, *, backend=None)` SHALL compute, for each polygon of a PCB document as Fenolite's reader reads it, the pieces of its poured copper from that reading only: its polygon records, its rules, its objects and its board shape.

#### Scenario: Detailed contract for pour engine
- **WHEN** this behavior is exercised
- **THEN** the following detailed conditions MUST hold:

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
A refused polygon SHALL retain only its outline, with a warning naming its reason. Refusal closure MUST be recomputed until no finding involves a pour; the detailed refusal conditions below apply.

#### Scenario: Detailed contract for refusal of a pour
- **WHEN** this behavior is exercised
- **THEN** the following detailed conditions MUST hold:

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

#### Scenario: Detailed contract for pour comparison
- **WHEN** this behavior is exercised
- **THEN** the following detailed conditions MUST hold:

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

### Requirement: Certified final neck cut
The final neck-removal difference SHALL use exact signed selection and one half-even projection per exact boundary node. It SHALL preserve the existing quantization bound, integer source nonzero vertices, whole-ring orientation and certified retained topology/cleanup. Earlier opening operations SHALL remain unchanged. No fixture, digest or platform condition SHALL select this behavior.

#### Scenario: Original corner retained
- **WHEN** a final neck cut has an original nonzero boundary vertex
- **THEN** the result retains its exact integer coordinate and a nonzero turn, or refuses before writing, unless the realized boundary passes straight through that coordinate within the existing half-nanometre bound

#### Scenario: Sub-nanometre source turn is flattened, not refused
- **GIVEN** a source vertex at (0, 0) whose exact neighbour on the cut boundary is (-1, 1/4)
- **WHEN** the neighbour takes its half-even point (-1, 0)
- **THEN** the boundary keeps (0, 0) on a straight integer edge, the cut counts the flattened corner and writes no other change

### Requirement: Integer realization by selective snap rounding
Every exact boundary node SHALL take its half-even integer point. An exact edge SHALL be drawn straight between the points of its ends unless the drawing has a proper crossing, an edge current other than -1, 0 or 1, or a face winding other than 0 or 1; such an edge and the exact edges around it SHALL then pass through the centre of every hot pixel they meet, in order. Every point of every drawing SHALL lie within half a nanometre per axis of its exact edge. A conflict that remains with every edge bent SHALL refuse. Polygons whose grown boxes meet no cut polygon SHALL pass through unchanged; an arrangement above half the source-edge ceiling MAY be cut in vertical strips at integer seams that no cut polygon reaches and no subject vertex has, and SHALL then give the same selection.

#### Scenario: A crossing straight drawing is bent
- **GIVEN** a node at (3/10, 3/5) below an exact edge from (-10, 2/5) to (10, 9/10)
- **WHEN** the straight drawings of the rounded nodes cross
- **THEN** the edge is bent through the hot pixel (0, 1) and the realized boundary has no crossing

#### Scenario: Strips equal one arrangement
- **WHEN** the same subject and cut polygons are cut whole and in strips
- **THEN** both give the same polygons

### Requirement: Existing debris order and certified refusal
The cut SHALL test piece net area before removing small holes. Every removed whole face SHALL have exact/integer eligibility and unique parent/child ownership; a collapsed loop SHALL have zero signed line currents. Uncertified topology, precision or resource limits SHALL refuse through existing GeometryError without an approximate fallback.

#### Scenario: Thin piece owns its hole
- **GIVEN** a simple area-9 outer square and an area-1 hole, with tolerance 3
- **WHEN** debris removal runs
- **THEN** the net area-8 piece disappears with its hole and cannot become a solid area-9 square

#### Scenario: Zero shoelace area is insufficient
- **WHEN** a projected bow tie has zero shoelace area and nonzero signed line currents
- **THEN** it is refused as an uncertified collapse

### Requirement: Certified repair of projected self-crossings
A bounded repair MAY omit implicated noninteger intersection nodes while preserving integer nodes and nonzero source turns. Every retained node SHALL keep its one shared half-even projection. Each changed loop SHALL have a complete exact bidirectional continuous boundary certificate within sqrt(2)/2 nm, with unchanged orientation, contacts, parentage and debris eligibility. Missing intervals or resource exhaustion SHALL refuse; samples alone SHALL NOT establish a certificate.

#### Scenario: Endpoint-only evidence is insufficient
- **GIVEN** a candidate whose original vertices are close to the target but whose edge interior exceeds the bound
- **WHEN** its certificate is checked
- **THEN** it is refused for lack of complete continuous interval coverage

#### Scenario: Many independent hairlines
- **GIVEN** seventeen independent projected hairlines with eligible noninteger intersections
- **WHEN** the one bounded all-implicated proposal is certified
- **THEN** every integer corner, retained topology and complete continuous error bound is preserved without enumerating all subsets

#### Scenario: Proposal exceeds its node cap
- **WHEN** the implicated proposal exceeds its declared 256-node bound
- **THEN** it is refused before constructing a candidate; no certificate or write is claimed

#### Scenario: Subnanometre cleanup has a complete continuous certificate
- **GIVEN** a rational 0.6-nm hairline whose projected zero-current spike is cleaned
- **WHEN** every integer canonical node stays on the curve and both complete boundary directions satisfy the existing bound
- **THEN** the continuous certificate may succeed although the stronger projected point-set fast gate differs

#### Scenario: Cleanup exceeds the continuous bound
- **GIVEN** the corresponding 0.9-nm hairline
- **WHEN** its cleaned boundary exceeds the existing bound
- **THEN** it is refused; integer nodes and source corners cannot be waived

### Requirement: Explicit bounded source-input coverage

The private source-edge admission ceiling SHALL use the reviewed100,000edge structural envelope while retaining every other storage/work/coordinate/distance/deadline guard and the complete geometry certificate. This expands input coverage; it SHALL NOT imply a successful pour when another certificate or resource guard refuses.

#### Scenario: Sparse source above the former pilot ceiling
- **GIVEN**10,001independent authored source edges within every downstream limit
- **WHEN** the exact input is admitted
- **THEN** all source-edge provenance and signed multiplicity remain present; the former10,000pilot ceiling does not reject it

#### Scenario: Expanded input does not expand dense work
- **WHEN** an input exceeds100,000source edges or the unchanged candidate-pair ceiling
- **THEN** the operation refuses before intersection arithmetic and returns no partial graph

### Requirement: Exact boundary subdivision proposals

A bounded repair MAY subdivide an exact selected boundary edge at a rational interior point while retaining every original exact node and proving identical signed curve/current. Each new canonical node SHALL use the same shared prescribed half-even projection and existing coordinate/resource bounds. Endpoint or midpoint predicates SHALL be necessary pruning only; the unchanged complete GLOBAL continuous/source/topology/parentage/debris certificate SHALL judge every returned result. Rejected proposals SHALL NOT become unqualified fallbacks.

#### Scenario: Near-boundary authored notch
- **GIVEN** an original rational notch whose nearest projection is nonsimple and whose original omission exceeds the continuous bound
- **WHEN** an exact collinear subdivision permits a candidate with the same exact curve
- **THEN** the original global certificate protects every original integer corner and complete continuous bound, or the operation refuses

#### Scenario: Samples do not certify an edge interior
- **GIVEN** a proposed projection with plausible endpoint distances but an uncovered interior
- **WHEN** the builder presents it to the caller
- **THEN** the original full global verifier rejects it; necessary probes do not waive any interval

### Requirement: Complete bounded closed-box candidate enumeration

The exact arrangement index SHALL emit every unordered original source-ID pair whose CLOSED integer envelopes intersect exactly once, sorted by source IDs, including point/degenerate/endpoint contacts. Tree pruning SHALL use exact containing envelopes and SHALL NOT alter geometry, merge IDs or discard multiplicity. All node/leaf predicates within one index call SHALL share its existing comparison ceiling; query/component subdivisions SHALL NOT reset it. Storage, candidate-output, coordinate and shared deadline guards SHALL remain effective.

#### Scenario: False single-axis density is not an overlap
- **GIVEN** two independent authored box families which overlap separately inXandYbut have no2Doverlap
- **WHEN** hierarchical candidate enumeration completes within the same work cap
- **THEN** the complete candidate tuple is empty, with every source ID still represented

#### Scenario: Callback resource refusal remains a refusal
- **WHEN** a node/leaf/storage callback exhausts its work or memory bound
- **THEN** traversal propagates the refusal before returning any partial graph

