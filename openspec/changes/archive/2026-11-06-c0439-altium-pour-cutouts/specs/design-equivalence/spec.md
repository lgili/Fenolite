## ADDED Requirements

### Requirement: Copper without a net

Level 5 SHALL compare the copper without a net of both sides: tracks, arcs and graphics on copper layers
(a footprint's own graphics and zone fills left out; a KiCad graphic's net read from its KiCad slot). Each
piece that one side holds and no piece of the other matches within the length tolerance SHALL be one
difference of kind `copper-no-net` (field `copper`) at `(no net):<span>`.

| level | kind | field | when |
|---|---|---|---|
| 5 | `copper-no-net` | `copper` | a piece of copper without a net is on one side only |

#### Scenario: A cut-out written as copper

- **GIVEN** the reading of the converted `polygon_cutouts.kicad_pcb`, and the same reading with one F.Cu
  cut-out replaced by a filled polygon of no net
- **WHEN** the two are compared at level 5
- **THEN** they are not equivalent, with one `copper-no-net` difference at `(no net):top`
