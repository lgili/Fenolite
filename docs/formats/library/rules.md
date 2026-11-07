# Library rules: Fenolite conventions

Change c0262. All constants and checks on this page are Fenolite-authored, `INFERRED`.
They do not assert compliance with an industry library standard.

| rule | convention and reason |
|---|---|
| Land tolerance | `T = 50_000 nm` (0.05 mm). Imported pads differing by more than T in position or size warn; generated manufacturer lands must agree exactly. |
| Pin 1 | In the zero-orientation footprint frame (X right, Y down), pad 1 or A1 is above-left of the numbered-pad centroid: both inequalities non-strict, at least one strict. Non-polarized two-terminal parts are exempt. |
| Pin order | Perimeter leads are numbered counter-clockwise in the top view (X right, Y down), the JEDEC/IPC convention for DIP, SO, SOT, QFP, QFN and DFN outlines (change c0385). Only pads numbered `1`, `2`, ... count, and the smallest pad of each number is its lead; a pad over `TAB_AREA_RATIO = 2` times the median numbered-pad area is a tab or exposed pad and no lead. Leads on one line are judged only against one tab beside the middle of that line (SOT-89, SOT-223, TO-252): the leads run strictly one way, the tab projects inside the row and stands off it by more than twice any lead. Leads on one line without such a tab (headers, terminal blocks, JST, USB, TO-220) give no order. Otherwise the leads must outline the land: three leads in the SOT-23 shape (a pair on one side, the lone lead within their span across), four leads in pairs 1-2 and 3-4 on opposite sides, or five and more on the sides of their bounding box with each side one run of the numbering. Around the centre of the pads' extent every turn from one lead to the next must then have one sign; a zig-zag (two-row headers), a grid, a lead on the centre or a turn of the other sign gives no order and no finding. Severity is error for a catalog or library record, warning for a plain library item that has no record to carry a waiver. |
| Marker | A silk/fab graphic's bounding-box centre is strictly closer to pad 1 than every other pad. This is a heuristic; unusual connectors may waive it with a reason. |
| Grid | Symbol connection points and lengths use 254_000 nm (10 mil); 2_540_000 nm (100 mil) is the preferred grid. Off the first is an error; off only the second is a warning. |
| Clearance | Copper pads with different numbers must have a positive gap on every common copper layer. Geometry uses integer nanometres. |
| Body/span | Leads outside a body require its maximum width below the minimum span. Lead length uses `2Lmin < span.max − width.min + 2T`. |
| Grid arrays | Rows use `ABCDEFGHJKLMNPRTUVWY`, then AA, AB, etc.; columns start at 1. Depopulated locations are unique grid positions and have no copper pad. |

Public source S-0988 (TI ZXH0080A outline) supports A–J omitting I. As already recorded in
[naming.md](naming.md), the other omitted letters and the multi-letter continuation are Fenolite
conventions (`INFERRED`); this change makes no unsupported JEDEC claim. The checked rules are stated
here from first principles rather than copied from another library's rules.

Review digests exclude top-level evidence and review metadata, normalize generated evidence-only
descriptions, and include referenced records and generated definitions. The accepted HTML contains an
immutable review-content section; live reviewer/date/state is reported by the command. This prevents
accepting the sheet from immediately making that same sheet stale.

## Pin order of the catalog lands (c0385)

The facts behind the "Pin order" row and the 55 catalog lands that change c0385 mirrored about the X axis.
The lowest label applies to each land: none is higher than `INFERRED`, since no land was placed on a board
and checked against a fitted part.

| fact | source | label |
|---|---|---|
| A package top view numbers the leads counter-clockwise from pin 1 (DIP, SOIC, TSSOP, MSOP, SSOP, SOT-23, SC-70, SOT-563, QFP, QFN, DFN, SOT-89, SOT-223, TO-252, TO-263, SOT-143): the JEDEC/IPC outline convention. The records cite their outline drawings (each record's own `sources`, for example S-0322, S-0323, S-0327, S-0338, S-0355, S-0369, S-0372); c0385 did not fetch them again, and no cited part is recorded as numbered clockwise | each record's `sources` | `INFERRED` |
| The register already records two top views that the old lands contradicted: S-0416 (ABM8: pin 1 bottom left, 2 bottom right, 3 top right, 4 top left) and S-0422 (WS2812B-V6: 1 upper left, 2 lower left, 3 lower right, 4 upper right, corner at pin 3). The old records held pin 1 of the WS2812B at y +1.65 mm, the lower left in the Y-down frame; the mirrored records match both top views | S-0416, S-0422 | `INFERRED` |
| The cited land drawings give pad centres with Y up: S-0372 lists the SOT223-3 lead pads at y −3.10 mm and the tab at y +3.10 mm, the tab above the leads as drawn. The catalog had copied such numbers into its Y-down frame, so every land with a chirality was the mirror image of its part | S-0372 | `INFERRED` |
| The stock KiCad footprints of the same outlines number counter-clockwise in the Y-down frame (SOT-23 pad 1 at the upper left, pad 2 below it; SOT-89, SOT-223 and TO-252 with pin 1 at the top of a left lead column; the WS2812B PLCC-4 and the 3225 crystal; JST XH with pin 1 opposite the wide housing side as drawn by S-0410; the Würth micro-B with its pins behind the opening). Read on an installed copy as a cross-check only; nothing was copied | S-0018 | `INFERRED` |
| S-0410 page 2 draws the JST XH PCB-top view with pin 1 at the right; S-0411 page 1 draws the micro-B contacts 1 to 5 behind the shell's front anchors | S-0410, S-0411 | `INFERRED` |
| `tools/catalog/render_footprints.py` drew the review gallery with Y up until c0385, so the mirrored lands looked like their datasheets in every review sheet | this repository | `INFERRED` |

Lands whose chirality comes from the body and not from the pads (one row of pins: `JST_XH_B2B_XH_A`,
`JST_XH_B4B_XH_A`, `MicroUSB_B_Wurth_629105150521`, `TO220_3_Diodes_Vertical`) were mirrored with the rest;
`library.pin-order` cannot see them. Lands without chirality kept their drawing: the two-pad parts, the
single-row headers (a row read backwards is the same row turned), the 2-row headers (a mirrored zig-zag
is the same zig-zag from the adjacent corner) and the two tact switches (each pair of common terminals
stays a pair).
