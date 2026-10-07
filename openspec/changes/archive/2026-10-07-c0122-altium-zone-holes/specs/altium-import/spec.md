## MODIFIED Requirements

### Requirement: Zones from polygons
`import_board` SHALL map each record of `Polygons6` whose `polygon_type` is `Polygon` and whose layer is a copper layer of the chain to one `Zone`.
- `outline` MUST be the vertices in order, converted, without the repeated last vertex. A record with an arc vertex MUST give `outline == ()`, which the model defines as "kept by the backend", and one `altium.import.zone-arc` info per import with the count.
- `layers` is the one layer; `net_id` the net of the record's net index; `name` the record's name.
- `priority` MUST be `max(pour_index) − pour_index` over the mapped zones, so the zone poured first has the highest priority, the inverse of what c0038 writes. The original goes to `pour_index`.
- `fills` MUST hold one `ZoneFill(layer, polygon)` per region of `PcbDocument.regions_of(index)` on a copper layer, in stream order. Tracks and arcs of a hatched pour are counted as `pour-primitives`, not mapped.
- `polygon` MUST be `keyhole_ring(outline, holes).ring` ("Keyhole ring of a polygon with holes" of `geometry-kernel`), `outline` and each hole being the region's vertices rounded by "Units and frame", without a repeated last vertex and without repeated neighbours. The copper of a fill is therefore the region's outline without its holes: a point inside a hole is outside the polygon under the non-zero and the even-odd rule, and a region without a hole gives its outline unchanged.
- A hole that the ring does not hold is not in the model and MUST be counted as `region-holes`: one with fewer than three distinct points or without area, and one that lies outside its outline. The holes outside their outline MUST also give one `altium.import.zone-hole-outside` warning per import, located at `Regions6/Data`, whose message holds the count of such holes and the count of regions that hold them.
- A polygon of another type (a split plane, a cutout), or on a layer outside the chain, is unmapped.

#### Scenario: Unpoured zones of the routed sample
- **GIVEN** the PCB document of `tests/data/altium/routed/`, whose two zones are written without poured copper
- **WHEN** it is imported
- **THEN** the board holds the zones with the model's nets, layers and outlines within 2 nm, each on one layer, with `fills == ()`, and the zone that the model gives the highest priority has the highest priority

#### Scenario: Outline with an arc
- **GIVEN** a polygon whose second vertex has `KIND1=1`
- **WHEN** it is imported
- **THEN** the zone has `outline == ()`, its net and layer are set, and `altium.import.zone-arc` reports one zone

#### Scenario: Pour with a hole and an island
- **GIVEN** a document with one polygon on layer 1 and two regions of it: a square with one square hole, and a smaller square that lies inside that hole
- **WHEN** it is imported
- **THEN** the zone has two fills, the first polygon holds the four points of the outline followed by the anchor, the hole and the anchor again, a point inside the hole and outside the island is `OUTSIDE` of the first polygon, the copper check's touch test finds the two fills apart, the copper check reports no short with a track of another net that lies in the hole, the net of the polygon has two pieces of copper, and no `region-holes` is counted

#### Scenario: Hole outside its outline
- **GIVEN** a polygon with three regions: one with a hole that lies wholly outside its outline, one with such a hole and a hole inside its outline, and one with a hole of three equal points
- **WHEN** it is imported
- **THEN** the first and the third fill are their region's outline, the second holds its inner hole, one `altium.import.zone-hole-outside` warning located at `Regions6/Data` reports 2 holes of 2 regions, and `region-holes` counts 3

### Requirement: Import issue codes
Every issue of the adapter SHALL carry a code of the closed table `adapter.IMPORT_ISSUE_CODES`, which maps each code to its one severity, and `docs/cli-contract.md` SHALL list the table.
- Errors: `altium.import.bad-stack`, `altium.import.sheet-loop`.
- Warnings: `altium.import.bad-length`, `altium.import.bad-geometry`, `altium.import.layer-outside-stack`, `altium.import.duplicate-net`, `altium.import.unknown-member`, `altium.import.padstack-unknown`, `altium.import.via-span`, `altium.import.no-designator`, `altium.import.sheet-missing`, `altium.import.repeated-sheet`, `altium.import.scope-unknown`, `altium.import.duplicate-net-name`, `altium.import.duplicate-sheet-name`, `altium.import.bus-width`, `altium.import.harness-nested`, `altium.import.pcb-only-component`, `altium.import.document-skipped`, `altium.import.zone-hole-outside`.
- Infos: `altium.import.inexact`, `altium.import.multi-class`, `altium.import.zone-arc`, `altium.import.copper-shape`, `altium.import.scope`, `altium.import.option-ignored`, `altium.import.bus-member`, `altium.import.harness-entry`, `altium.import.extra-board`, `altium.import.linked-by-designator`, `altium.import.pcb-only-net`, `altium.import.rule-unmapped`, `altium.import.unmapped`.
- An issue's `where` MUST be a locator of "Identifiers and provenance", a reference, a `REF-PIN` or a net name; a counting issue's message MUST hold its counts.
- An error issue never stops the import: the adapter raises only for a programming error and for a project with nothing to read.
- No code of this table MUST equal a code of `fenolite.lens.altium.ALTIUM_ISSUE_CODES` or of the readers' tables.

#### Scenario: Closed table
- **WHEN** `uv run pytest tests/unit/backends/altium/adapter/test_codes.py` collects the codes that the adapter's source can give and those the tests have seen
- **THEN** both sets are within `IMPORT_ISSUE_CODES`, every code of the table has one severity, every code is a row of `docs/cli-contract.md`, and none is a code of the build or of a reader
