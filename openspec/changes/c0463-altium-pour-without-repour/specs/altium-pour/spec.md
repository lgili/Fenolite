## MODIFIED Requirements

### Requirement: Computed pours are experimental
A computed pour SHALL carry the evidence level `INFERRED`, together with the hypotheses it used, until change c0463's graduation holds:

- a K6 round of the kit on Altium Designer passes every step of the samples `pour`, `pour4` and `pour-hatched`;
- the Repour oracle (`tests/corpus/test_altium_pour_repour_c0463.py`) passes M1 to M4 on every polygon of the public rows of the pour census.

From graduation on, a computed pour MUST carry `ALTIUM-VERIFIED(kit)`.

`altium.zones-poured` (info) MUST name the count and say that Fenolite computed the pour. Before graduation it MUST also say the pour is experimental and name "Tools » Polygon Pours » Repour All" as the way to Altium's own copper. After graduation it MUST NOT name Repour All. Each `altium.zone-unpoured` MUST name it.

#### Scenario: Routed built with a computed pour
- **WHEN** the routed sample's model (one `GND` zone on `In1.Cu` and `B.Cu`) is built for Altium with the pour mode `computed`
- **THEN** `result.pcb.pour.mode` is `computed`, `result.pcb.pour.evidence` is the level the graduation gives, and one `altium.zones-poured` names 2 polygons

## ADDED Requirements

### Requirement: Outline arcs poured
A polygon whose outline holds arc vertices SHALL be poured, with each arc turned into chords by its `ARCRESOLUTION`. The rule is the largest step whose sagitta is at most `d`. The written polygon MUST keep its arc vertices. `outline-arc` MUST remain only for an arc the reader cannot place.

#### Scenario: A rounded outline
- **GIVEN** an authored polygon whose outline has two corners rounded by arcs of 2 mm radius, and an `ARCRESOLUTION` of 0.0254 mm
- **WHEN** `uv run pytest tests/unit/backends/altium/test_pour_outline_c0463.py -k arc -q -n 0` pours it
- **THEN** the polygon is poured, and its pour lies within 0.0254 mm of the exact rounded area

### Requirement: Outlines made simple by Altium's rule
An outline that repeats a vertex SHALL keep the vertex once. An outline that touches itself at a vertex SHALL be split there into simple rings, when the corpus record S-2222 shows Altium fills each ring. An outline that crosses itself MUST still refuse `outline`, unless a recorded source shows Altium's fill.

#### Scenario: A ring touching itself
- **GIVEN** an authored outline of two squares that share one vertex
- **WHEN** the same file, `-k touch`, pours it
- **THEN** both squares are poured as two pieces

### Requirement: Hatched polygons poured
A polygon with a `HATCHSTYLE` other than solid SHALL be poured as tracks of `TRACKWIDTH` at `GRIDSIZE` in the style's directions, clipped to its solid pour, with the grid alignment that the kit sample `pour-hatched` records (S-2223). Until that record exists, `hatched` MUST stay a refusal.

#### Scenario: The hatched sample
- **WHEN** `uv run pytest tests/corpus/test_altium_pour_hatched_c0463.py -q -n 0` pours the kit sample `pour-hatched`
- **THEN** each polygon passes M1 to M4 against the regions and tracks Altium saved

### Requirement: Census of the public rows poured without Repour
Every polygon of the 8 public rows of the pour census SHALL be poured, or SHALL be exact as not poured (`shelved`, `plane-layer`, counted under `exact`). Each poured polygon MUST pass M1 to M4 against Altium's Repour record (S-2224). Each poured polygon MUST also pass against the regions the source saves, or be named stale where the two oracles disagree.

#### Scenario: No refusal on the public rows
- **WHEN** `FENOLITE_HEAVY=1 uv run pytest tests/corpus/test_altium_pour_census.py tests/corpus/test_altium_pour_repour_c0463.py -q -n 2` runs
- **THEN** no polygon is refused, and every poured polygon passes M1 to M4 against the Repour record
