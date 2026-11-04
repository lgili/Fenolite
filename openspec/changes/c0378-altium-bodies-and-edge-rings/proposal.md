# Convert Altium bodies and keep micro edges of the board outline

## Why

Two conversion gaps remain. Component bodies with an unproved projection side, an unsupported model type
or an invalid height are kept but not converted (`backends/altium/adapter/bodies.py:35`,
`altium.import.body-unknown`). And two boards report an unexplained `edge-ring` difference. Diagnosis (2026-11-04): the source has
no micro edge. `backends/altium/adapter/copper.py:1070` (`outline`) computes the ends of an outline arc
from its centre, radius and angles (`units.arc_points`), not from the vertices `a` and `b` of the `Board6`
vertex list it joins; on large radii the computed end lies about 6 µm from the vertex. The Altium ring
(`backends/altium/frame.py:board_edges`) joins ends closer than `EDGE_JOIN_NM` (1 µm), so it keeps both
points; the KiCad read-back joins ends closer than `CHAIN_GAP` (10 µm, measured on KiCad), so it keeps
one. Fenolite writes the edges exactly as read.

## What Changes

- Record, with public or maintainer-measured evidence (kit case), that an arc vertex of the `Board6`
  outline runs from its vertex to the next one, then take the arc's ends from the vertices (its middle
  from the centre and angles) when the computed ends lie within a stated distance; an authored outline
  with a large-radius arc reproduces the ring difference first. No comparison tolerance is added.
- Measure the body records that are refused today on maintainer-saved Altium documents and convert the
  proved cases.

## Impact

KiCad board writer/reader edges, Altium body adapter, docs/formats with evidence labels.
