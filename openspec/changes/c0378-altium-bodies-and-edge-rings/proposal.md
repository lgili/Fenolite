# Convert Altium bodies and keep micro edges of the board outline

## Why

Two conversion gaps remain. Component bodies with an unproved projection side, an unsupported model type
or an invalid height are kept but not converted (`backends/altium/adapter/bodies.py:35`,
`altium.import.body-unknown`). And two boards report an unexplained `edge-ring` difference: the
written outline read back by KiCad lacks vertices of 1 to 6 µm edges and moves one vertex by about
6 µm, compared with the source's edges (`api/conversion.py:144`); no cut-out is merged. The likely
cause is a tiny outline arc that degenerates on writing or reading.

## What Changes

- Reproduce the outline difference with an authored outline holding a micro arc and fix the writer or
  reader so the ring is kept exactly (no added tolerance).
- Measure the body records that are refused today on maintainer-saved Altium documents and convert the
  proved cases.

## Impact

KiCad board writer/reader edges, Altium body adapter, docs/formats with evidence labels.
