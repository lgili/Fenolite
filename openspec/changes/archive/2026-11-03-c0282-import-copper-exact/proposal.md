## Why

The copper check widens polygonised arcs by 1,001 nm. This exceeds KiCad's 500 nm
clearance tolerance and reports valid imported copper near the limit. Bottom-side
placement also refuses chamfered pads although their corner names have a defined mirror.

## What Changes

- Decide distances involving circular arc cores with exact rational and radical arithmetic.
- Use those decisions for copper pairs, rule areas and curved board edges; preserve strict
  direct calls and the existing injected clearance tolerance.
- Mirror authored pad chamfer corners with the existing local-Y footprint mirror.
- Add authored boundary, reversal, rotation, reflection and KiCad canary tests.

## Impact

- Affected specs: geometry-kernel, copper-check, kicad-file-backend.
- No model units, dependencies, commands, DSL names or diagnostic codes change.
- Existing band-induced false findings disappear; evidence stays INFERRED until oracle CI.
