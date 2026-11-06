## ADDED Requirements

### Requirement: Copper of a net-tie footprint

Level 3 SHALL compare the copper of each footprint pair where a side has net-tie groups: the graphics on the
board's copper layers, in the footprint's frame, as segments, regions and arcs, the layer named by its role
(`top`, `inner<k>`, `bottom`). Each piece that no piece of the other side matches within the length tolerance
SHALL be one difference of kind `net-tie-copper` (field `copper`) at the reference, with the piece's text on
its side and `""` on the other. A footprint that is a net tie on neither side SHALL compare no copper.

| level | kind | field | when |
|---|---|---|---|
| 3 | `net-tie-copper` | `copper` | a piece of copper of a net-tie footprint is on one side only |

#### Scenario: An open net tie is a difference

- **GIVEN** the conversion of `net_tie_copper.kicad_pcb` and its reading with the tie's line removed
- **WHEN** the two are compared at level 3
- **THEN** there is exactly one `net-tie-copper` difference, at `NT1`, whose side `a` names a `top segment`
  of width 300000 nm and whose side `b` is empty

#### Scenario: A moved tie line

- **GIVEN** the reading with the tie's line moved by 0.1 mm
- **WHEN** it is compared with the conversion at level 3
- **THEN** there are two `net-tie-copper` differences, one per side, and none when neither footprint is a
  net tie
