## MODIFIED Requirements

### Requirement: Stitching vias
`resolve_copper` SHALL turn each stitch intent (`key`, `net`, `pitch`, `along`, `region`, `origin`, `diameter`, `drill`, `clearance`, `margin`) into through vias of its net, along a polyline or on a grid inside a region, keeping clear of other copper.
- Exactly one of `along` (at least two points) and `region` (at least three points forming a simple ring) MUST be given, `pitch` MUST be positive and `margin` not negative; otherwise `kicad.copper.bad-intent`.
- **Along.** Each segment of the polyline MUST be divided into the fewest equal parts no longer than `pitch` (the smallest `n ≥ 1` with `n²·pitch²` at least the squared length). The candidates MUST be the division points, each vertex once, rounded half to even, numbered `k = 0, 1, …` from the first vertex.
- **Region.** The candidates MUST be the points `origin + (i·pitch, j·pitch)` for integers `i` and `j` that lie inside the region at a distance of at least `diameter / 2 + margin` from every edge, decided exactly, in order of `j` then `i`.
- **Clearance.** A candidate MUST be dropped when its via disc comes closer than `clearance` to a copper entry or hole of any pad (`board-frame`), or to a track, arc or via of another net or of no net, or when it touches a via of its own net. Existing items, the vias of earlier intents and the candidates already kept MUST count. Distances MUST be decided exactly with integers and `Fraction`, using c0005's predicates; an arc MUST count as its polyline of `Arc.polygonize(DEFAULT_TOL)` with its width grown by `2·DEFAULT_TOL + 2`. Zones MUST NOT count.
- **Keep-outs and the edge.** A candidate MUST also be dropped when its via disc meets the outline of a `Keepout` with `no_vias` on a copper layer (a through via crosses every copper layer), or comes closer than the edge clearance in force to a ring of `board_outline`: the `min` of the governing board-wide `edge_clearance` rule in `rulemap.rule_order`, else the project's `min_copper_edge_clearance` (`H-K-STITCH-AVOID`). Without a closed outline the edge MUST NOT be checked. These candidates are dropped candidates for the count below.
- `clearance` MUST be the intent's, else the clearance of the class of its net, else `kicad.copper.size-missing`.
- The dropped candidates of an intent MUST give one `kicad.copper.stitch-skipped` info with their count, and an intent that keeps no candidate one `kicad.copper.stitch-empty` warning.

#### Scenario: Along a line
- **GIVEN** a design without copper near the line (0, 0)–(10 mm, 0), and a stitch intent on `GND` along it with pitch 3 mm, diameter 0.6 mm, drill 0.3 mm and clearance 0.2 mm
- **WHEN** it is resolved
- **THEN** it creates five vias at x = 0, 2.5, 5, 7.5 and 10 mm, with the locators `via[0]` to `via[4]`

#### Scenario: Region with margin and a pad to avoid
- **GIVEN** `Mini_R_0603` placed at (5 mm, 5 mm), 0°, with both pads on `LED_DRV`, and a stitch intent on `GND` in the square (0, 0)–(10 mm, 10 mm) with pitch 2.5 mm, origin (0, 0), diameter 0.6 mm, drill 0.3 mm, margin 0.2 mm and clearance 0.2 mm
- **WHEN** it is resolved with `issues=found`
- **THEN** it creates the eight vias at (2.5·i, 2.5·j) mm for i and j in 1, 2, 3 except (5 mm, 5 mm), with the locators `via[i,j]`, and `found` holds one `kicad.copper.stitch-skipped` with the count 1

#### Scenario: Own-net via touched
- **GIVEN** the region of the previous scenario without the footprint and with an existing `GND` via of diameter 0.6 mm at (5 mm, 5 mm)
- **WHEN** the stitch is resolved
- **THEN** no new via is placed at (5 mm, 5 mm) and the other eight are created

#### Scenario: Fence across a keep-out
- **GIVEN** the line of "Along a line" crossing a `Keepout` with `no_vias` on both copper layers that covers x from 4 mm to 6 mm
- **WHEN** the stitch is resolved with `issues=found`
- **THEN** no via is created at x = 5 mm, the others are, and `found` holds one `kicad.copper.stitch-skipped` with the count 1

#### Scenario: Fence along the edge
- **GIVEN** a design with a closed outline whose left edge is the line x = 0, a board-wide `edge_clearance` rule of 0.5 mm, and a stitch intent along the line x = 0.4 mm with diameter 0.6 mm
- **WHEN** the stitch is resolved
- **THEN** no via is created, and one `kicad.copper.stitch-empty` warning is given
