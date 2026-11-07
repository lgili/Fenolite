## ADDED Requirements

### Requirement: Copper of a footprint with a net

The writer SHALL write a copper graphic of a footprint without net-tie groups whose `net_id` names a net of
the written board as records of its component on its signal layer, each with that net's index: a filled
rectangle or polygon as one region, a line, a drawn shape, a circle or an arc as tracks and arcs. A copper
graphic of such a footprint without a net, or on a plane, SHALL stay counted lost under `footprint-copper`.

#### Scenario: A component region comes back with its net

- **GIVEN** a board whose footprint holds a filled polygon on `F.Cu` with the net `5V`
- **WHEN** the board is written
- **THEN** the document holds one region of the component on the top layer with the index of `5V`
