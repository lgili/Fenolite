# Preserve custom footprint property poses through board import

Public TinyTapeout and Multichannel proofs expose hundreds of custom footprint
properties whose local rotation becomes zero after import/build. The vendor
correctly removes instance-specific property values from shared definitions,
but the generated code currently preserves only their values, losing their
placement and style. Preserve representable poses through explicit existing
field requests, keeping the full level7 and rendering checks unchanged.
