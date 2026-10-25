## ADDED Requirements

### Requirement: Generated copper and keep-outs
`fenolite.dsl.design.Design` SHALL offer calls that generate zones and rule areas from geometry, recorded as ordinary zone and rule-area intents, so that a build, a check and a conversion need nothing new.
- **`band(net, spine, *, width, max_width=None, layers, clearance=None)`.** A zone along the path `spine`, `width` wide, each side widened on its own up to `max_width` in steps that keep `clearance` (else the clearance in force) from other nets' copper known at build time; steps MUST be 45° chamfers and outer corners bevels; a side MUST widen by at most one step on a straight run shorter than five widths. A spine that leaves the board MUST raise `DslError`.
- **`keepout_ring(target, *, setback, layers, forbid, sides=32)`.** A rule area around a hole, or around every hole of a part when `target` is a part, as a polygon of `sides` sides whose vertices lie at `r / cos(π/sides)`, so the polygon holds the true circle grown by `setback`.
- **`barrier(netclass, *, setback, layers, forbid, pieces=False)`.** A rule area around all copper of a net class on any layer, grown by `setback` and projected onto every listed layer. A band that comes out in several pieces or with holes MUST raise `DslError` unless `pieces=True`.
- **`body_keepout(part, *, setback, layers, forbid)`.** A rule area of the plan view of the part's body volume (`component-body-volumes`), grown by `setback`.
- **`fanout_zone(net, *, side, refs=None, via=...)`.** For each SMD pad of `net` on `side` (or of `refs`), a via and a short track to the zone of `net` on the other side, placed by the rules of plane fan-out; a via MUST NOT overlap any pad's copper or another drill.
- **`stitch_pieces(net, *, layers, min_vias=2, pitch=...)`.** Vias in each overlap of two pieces of `net`'s zones on the listed layers, at least `min_vias` per overlap.
- The generated items MUST carry the call's name in their ids, so that a rebuild replaces them and nothing else.

#### Scenario: A band keeps its clearance
- **GIVEN** a script with `design.band(bus, spine, width=mm(3), max_width=mm(6), layers=("B.Cu",), clearance=mm(1))` beside a pad of another net 2 mm from the spine
- **WHEN** `uv run pytest tests/unit/dsl/test_generate.py -k band` builds it and fills the zones with `kicad-cli`
- **THEN** the band widens away from the pad and stays 1 mm from it, every corner is 45° or a bevel, and DRC reports nothing

#### Scenario: A ring holds the circle
- **GIVEN** a 3 mm hole and `keepout_ring(hole, setback=mm(2), layers=("F.Cu","B.Cu"), forbid=("zones",), sides=16)`
- **WHEN** the script is built
- **THEN** every point of the circle of radius 3.5 mm lies inside the written polygon

#### Scenario: A barrier in pieces is refused
- **GIVEN** a class `LV` whose copper lies in two separate regions
- **WHEN** `design.barrier("LV", setback=mm(4), layers=("F.Cu",), forbid=("tracks",))` is called
- **THEN** it raises `DslError` naming `pieces`
