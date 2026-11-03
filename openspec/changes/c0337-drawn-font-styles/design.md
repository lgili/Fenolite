## Reviewed boundary
2026-11-02 coordinator approved this new c0337 scope before code: effective thickness/bold/italic in the authored font plus masks/envelopes, defaults/22 scenes preserved, located comparisons, no native glyph raster equality or H-K promotion claim. Face, mirror and sub-micrometre dimensions remain refusals. Colour is outside this initial scope pending separate review of measured coloured SVG.

## Design
Use existing text primitive thickness for explicit width. Bold uses authored heavier width and italic shears the existing authored glyphs by a rational one-fifth of cap height; neither imports native glyphs. Styled fonts register variants in scene fonts, leaving default index zero and default bytes unchanged. Envelopes and glyph-box masks account for the same weight/shear while legacy defaults follow their original path. Explicit widths use the existing half-even scene grid; positive sub-micrometre widths refuse rather than becoming zero. Positive explicit thickness takes precedence over derived bold width. Native evidence does not assert identical glyph geometry: these are Fenolite authored text envelopes, as the existing mask contract states.

## Probes
Actual KiCad 10.0.6 free-text controls exported without drawing sheets, both black-and-white and coloured. Size1.27 default stroke0.1524mm; explicit thickness0.3 produces0.3000mm; bold produces0.2540mm; italic changes path bounds. Full source/SVG hashes and commands remain external; no glyph data enters core. Official text-effects documentation provides syntax only, not renderer constants.

## Validation
One style/proof iteration, focused Python and TypeScript renderer controls, default byte census, authored native roundtrip and actual public-board replay. Complete CI required before archive. No acceptance, threshold or source-input edits.

## Reviewed free-text colour addendum, before code
2026-11-02 coordinator approved a view-only adapter for colour in opaque free
text after actual coloured CLI10 probes. Preserve the original node/opaque
slot and effective RGB display; typed DrawnFont stays closed and refuses colour.
Validate exactly four numeric channels, integer RGB0..255 and alpha0..1;
duplicates, malformed, nested and out-of-range inputs refuse with locators.
Native10 authored red alpha0/0.5/1 coloured SVG signatures are identical with
stroke-opacity1; the all-zero sentinel retains legacy palette behaviour.
This scoped native observation does not discard RGB. Existing level8 remains
a documented BW geometric ink comparison and does not judge RGB equality;
no extra RGB findings, carriers, thresholds or colour layers are introduced.
The actual opaque comparison/preservation remains in existing S semantics.
No independent check-fast runs concurrently with the coordinator’s batch.
