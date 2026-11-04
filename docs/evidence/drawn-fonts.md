# Drawn font preservation

Change c0326 preserves typed schematic effects without granting a fidelity
acceptance. Reference, Value and Footprint text remains code-owned. Native
sheet-name/file text remains bound to its sheet reference and resolved filename.

## Authored controls and licensing

The temporary native projects in `tests/_drawn_fonts.py` are original Fenolite
controls dedicated to CC0-1.0. Their circuit, text, coordinates and copper derive
only from Fenolite's authored Mini libraries and drawn fixtures already declared
in `tests/data/MANIFEST.toml`. The generator and tests retain their Python
Apache-2.0 headers. Every new CAD file lives under the test's temporary directory;
this change adds no versioned CAD payload or third-party material requiring a new
manifest row. These controls are code-authored, not GUI saves.

`tests/fidelity/test_drawn_fonts.py` exercises both written target majors through
the actual strict import, explicit build and complete verify-source harness. The
positive project has hierarchy, local/global/hierarchical labels, sheet pins,
sheet-property poses, styled symbol/power fields and one actual routed track.
Every level 1–8 and S must be equal, accepted/differences empty, original source
bytes unchanged, and level 5 must match that track. The harness passes no loss,
acceptance, tolerance or level-selection flag.

A further control changes the free-text font and the pin name/number fonts of
one native embedded symbol. These stay in their existing native slots through
vendor emission and embedding; no second typed projection or opaque style
placeholder is introduced. The symbol is unique to the root sheet, so no
inconsistent duplicate definition is fabricated in its child.

Each planted writer defect first has a passing all-nine control. Font loss,
changed free text and a removed endpoint junction must then leave 1–7 equal and
make S and 8 differ with accepted empty. The explicit 2.54 mm endpoint marker is
electrically redundant and visually large enough for the unchanged mask
threshold. Only that marker is removed; every existing functional junction
remains. This tests the S guard after connectivity legitimately stays equal.

## Native observations

The registered source is S-0020, a KiCad CLI subprocess oracle. Original scratch
probes run on **9.0.2** on 2026-11-02: fifteen field-font variants, ten instance
default/inheritance controls and eighty-four label/pin/sheet-property controls.
Raw input/SVG bytes and exact command/version/hash receipts remain outside the
core repository. The original measurement receipts are historical and unchanged.
They establish the effective mappings described in
`docs/formats/kicad/schematic.md`, including asymmetric `(size HEIGHT WIDTH)`,
false/absent flags, zero/absent thickness, and missing/empty justification.

The versioned CLI oracle adds 27 cases with 94 exports on installed 9.0.2,
including all eight typed text surfaces and actual model-font lowering. Every
source project stays byte-identical. Isolated SVG controls author unique marker
texts in their original native inputs to identify the intended glyph; this is
not a production field-text override or an electrical-round-trip claim. The
model-lowering cases keep their code-owned values. All matching native glyph
groups, their styles and their multiplicity are retained, including repeated
plots of the same field. Axis-ratio checks allow only SVG coordinate precision;
they do not change fidelity tolerances.

Installed Inkscape 1.4 rasterises the actual wide/tall native SVG controls at
150 dpi: the images have 919 different RGBA pixels. SVG/PNG/pixel digests, exact
commands and versions are recorded outside the core; the source SVGs are
unchanged. Pillow is used only by that separate installed diagnostic environment,
with no core/test dependency added. This measures actual native glyph ink for
those inputs and does not establish general raster agreement with Fenolite.

These are CLI exports, not native GUI saves, exact-version CI or a claim that a
named font is installed on another machine. Required 9.0.9/10.0.6 jobs remain a
separate gate. Altium 22.2.1 is now installed on the maintainer host and the authored root
project has opened. Compiled-net export, save/reopen and all kit cases remain
unproved; `H-A-DRAWN-WRITE` stays INFERRED and unproved styles retain the
existing explicit loss policy.

## Comparison and renderer limits

Level S compares backend-extracted effective fonts attribute by attribute, plus
label/pin justification and sheet-property poses. Canonical/TOML presence remains
exact; the target-normalization boundary is separate. S changes use existing
difference fields and add no attributes when styles are absent.

The scene reader retains independent height/width and justification in its
existing primitives. Positive 1/499/500 nm sizes refuse explicitly instead of
rounding to zero and becoming 1.27 mm; a 1 µm axis stays small. Visible explicit
nonzero thickness, true bold/italic, face and mirror refuse unsupported rendering.
Hidden field styles retain native data without visible ink. Separate actual API
controls prove exactly native levels 1–7/S for these styles and require a full
proof to refuse; they do not call that refusal an all-nine pass.

Twenty-two complete default scene maps, 421,823 bytes, compare exactly between
the signed S checkpoint `3f6ed875` and scene checkpoint `263748db`. This does not
replace planned-map compatibility: the literal 75-row guard passes unchanged,
and complete API plans independently match the immutable entry `695dee0f` on the
same authored inputs, paths, seed and timestamp. All 1,172 planned files across
65 successful rows, both version-file kinds and ten existing strict refusals are
identical; the committed byte table is untouched. At that c0326 checkpoint, pixel thresholds, text
envelopes, sheet matching and junction geometry remain unchanged. Level 8 remains
INFERRED: a matching envelope is not native glyph-raster equivalence.

Run the focused controls with:

```sh
uv run pytest tests/fidelity/test_drawn_fonts.py tests/residue/test_library_items.py -q
uv run pytest tests/unit/model/test_drawn_font_compare.py tests/unit/view/test_schematic_fonts.py tests/unit/model/test_drawn_compare.py tests/unit/view/test_fidelity_masks.py -q
uv run pytest tests/kicad/schematic/test_drawn_fonts_oracle.py -q
```

Source PCB/schematic Footprint-display disagreements and filename identity
differences remain independent findings. c0326 adds no text override, comparator
normalization, acceptance or baseline update to conceal them. Full gates, exact
CI and the replacement final-model-0 capture close only with their own receipts.

## Maintainer-host continuation — 2026-11-02

Actual native KiCad 10.0.6 repeats the font-oracle selection: 28 cases pass
(45.71 s), including an independently planted failed-export/retry control.
Direct exports use byte-identical temporary project copies, preserving every
original input digest and recording native-created local settings separately.
This repairs test isolation; it does not change a native style expectation or
promote general glyph-raster, GUI-save, Altium or exact-head CI evidence.

The clean signed de6c6f2f model-0 measurement contains 174 dataclasses, 1244
fields, 40 fixed extension keys and all 20 active v0 schema digests. Actual
complete plans retain all 75 rows / 1172 files / ten strict refusals exactly
against the earlier captured model-0 baseline. The prepared model-1 inventory
must incorporate DrawnFont, custom sheet properties and their carriers before
activation; the replacement transition and its own proof remain open.

c0330 separately pairs only explicitly resolved project roots after safe
filename spelling changes. The older font integration witness now proves
that positive case through all nine levels, while its visible Footprint
negative and separate child-name/collision/loss controls remain strict. The
combined focused selection passes 25 cases. Clean de6c6f2f's actual Sonde
full proof passes all nine levels without acceptance. This resolves the
root-identity finding for that source, without accepting child-sheet or
visible Footprint differences. ECC83 and Coldfire retain their measured
presentation/style blockers. The completed fast gate before reconciling the
older witness reports two failures; the Mac Altium byte discrepancy remains.

## c0337 authored stroke styles, 2026-11-02

The earlier c0326 refusal above is a historical checkpoint. c0337 now implements
explicit thickness, bold weight and italic shear in the existing authored font,
scene envelopes and glyph-box masks. A fresh baseline from immutable e2658942
compares all22 complete maps byte-for-byte (420455 compact-JSON bytes); this is
a new capture, not a reassertion of the differently serialized historical map.
The driver and individual map hashes are recorded in
`drawn-font-styles-default-scenes.json`. Comparison pitch/tolerance remains
127000nm/1000ppm, including its existing one-pixel allowance. Small visible
weight changes can therefore have different exact boxes without exceeding that
allowance; levelS still compares the preserved effective attributes.

Authored stroke, precedence, rotation, narrow-axis and refusal controls pass.
Actual DrawnFont lowering for thickness/bold/italic/combined styles loads and
changes output under CLI10.0.6 with original inputs unchanged (four cases).
This does not claim native glyph equality, GUI save, public-board acceptance,
H-K promotion or required CI completion. S-1204/1205 and the aggregate native
probe record document the actual source and output observations.

The separately reviewed free-text colour adapter validates exactly four native
channels, integer RGB0..255 and alpha0..1, retaining original nodes in the opaque
slot. Two authored target9/10 strict all-nine controls preserve the complete
node, unchanged source and empty accepted/differences. Typed drawn font colour
continues to refuse. Actual coloured10.0.6 SVG establishes effective red/gray,
zero sentinel and alpha behaviour in the recorded controls. Level8 remains BW
geometric ink and makes no RGB equality claim. No colour evidence promotion or
source-byte/threshold concession follows.

## Public style-board replays, 2026-11-04

On clean 468d8a61 with kicad-cli 10.0.6, the styled public demos were imported and proved with
`verify-source` against untouched copies whose digests match the corpus rows. Tiny Tapeout (33 explicit
thicknesses, 33 bold, 2 italic, one href), interf_u, pic_programmer and Complex pass all nine levels with
empty differences and accepted lists; Royal keeps levels S and 8 equal and differs only at level 7
(derived padvia geometry). Coldfire does not reach the style levels: its import refuses because a KiCad 9
board arrives with a project holding KiCad-10-only keys, an importer finding kept as measured. Authored
native controls pass (40 cases). `drawn-font-styles-public-replays.json` holds the receipts. This claims
no native glyph equality, no KiCad 9 replay and no CI result.
