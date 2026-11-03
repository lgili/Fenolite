## Why
Public board replays currently refuse preserved thickness, bold and italic because scenes and masks do not implement them. Native KiCad 10.0.6 authored probes confirm all three affect output.

## What Changes
- Implement these three effects in Fenolite’s authored stroke font, scene envelopes and glyph-box masks.
- Display validated RGB in opaque free-text fonts, preserving original RGBA nodes and keeping typed fonts closed. Existing level8 masks remain BW geometric ink, without RGB equality claims.
- Preserve normal/default scene bytes and existing comparison thresholds.
- Keep named faces, mirroring and unrepresentable dimensions refused.
- Record actual native observations separately from Fenolite’s own glyph geometry.

## Impact
Internal schematic scene/rendering only; no new CLI, DSL or diagnostic code. c0326 codec preservation remains unchanged. Full validation remains CI.
