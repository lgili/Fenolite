# Preserve custom footprint property poses through board import

Public TinyTapeout and Multichannel proofs expose hundreds of custom footprint
properties whose local rotation becomes zero after import/build. The vendor
correctly removes instance-specific property values from shared definitions,
but the generated code currently preserves only their values, losing their
placement and style. Preserve representable poses through explicit existing
field requests, keeping the full level7 and rendering checks unchanged.

## Proposed mirror-ownership addendum, 2026-11-03

Investigate exact native ownership for an otherwise valid user-property pose whose mirror differs from the footprint side. Public Part.properties/Part.field behavior and the model remain unchanged. Preserve a valid native mirror through existing typed footprint fields/library slots instead of forcing a side-derived mirror. Runtime remains on hold until the authored RED and transform proof are reviewed. The existing source-mirror refusal is explicitly proposed to become a native-preservation positive; all other unsupported-pose/text/font/name refusals remain.
