# Authored schematic font style observations

S-1204 (public KiCad text-effects documentation) defines independent height/width, line thickness, bold and italic. It does not define Fenolite glyphs or a native weight formula.

ORACLE-VERIFIED(kicad-cli 10.0.6), S-1205: authored free text at size1.27mm has native SVG stroke0.1524mm; explicit thickness0.3mm gives0.3000mm; bold gives0.2540mm. Italic changes the path bounds. A coloured export changes blue #0000C2 to requested red #C20000 for `(color 194 0 0 1)`; colour is effective and cannot be silently discarded. These are measured controls, not a generalized native renderer formula, GUI save, or native glyph-raster equivalence claim. Raw SVG remains external; only aggregate observations and hashes enter core.

Fenolite’s existing authored single-stroke font remains its own geometry. Explicit thickness controls its stroke width, bold selects a heavier authored weight, and italic uses an authored rational shear. Style-sensitive glyph-box comparison remains an envelope comparison. Named faces and mirror continue to refuse. Native observations do not promote external project evidence or justify changing comparison thresholds.

S-1205 colour addendum, ORACLE-VERIFIED(kicad-cli10.0.6): coloured gray128/128/128
plots #808080; all-zero RGBA is byte-identical to the default native text group;
red with alpha0,0.5,1 has identical coloured text-group signatures and native
stroke-opacity1. These observations apply to authored free text on this version.
The view-only adapter validates all four channels and preserves the original
opaque font node; no typed colour carrier is inferred. Level8’s existing BW
geometric masks do not judge RGB equality. Native colour observations are not
a justification to omit effective RGB or promote general native glyph evidence.

S-1205 nonvisual hyperlink addendum, ORACLE-VERIFIED(kicad-cli10.0.6): authored
free-text effects with one string href have exactly the same BW/coloured text
group, ancestor styles and bounds as no href. The view adapter validates one
string and adapts only a clone; the complete original remains opaque and
strictly compared atS. It opens no URL and adds no clickable-link feature.
Typed effects and malformed/repeated href remain refused.
