# Altium sheet template (`.SchDot`)

This page states, in Fenolite's own words, what `fenolite.backends.altium.read.sheet` (change c0046)
relies on to import an Altium sheet template into the neutral drawing sheet. The container and the
records are those of `schematic-binary.md`, `schematic-ascii.md` and `schematic-records.md`; this page
adds only what a template needs. Sources are listed in `docs/evidence/sources.md`. The code is written
from this page; the GPL source (S-0131) was read for facts only, and nothing was transcribed or
followed. No template of any organisation is committed: the three public files of S-0264 and S-0265
are fetched to the corpus cache and measured there.

Every row is `INFERRED`. No `kicad-cli` path reads an Altium schematic, so the import has no oracle. The
results of the unit tests and of the corpus census (2026-10-05) are recorded per hypothesis in
`docs/hypotheses.md`; they are supporting data and raise no label. The written `.kicad_wks` of an imported
authored template is checked against `kicad-cli` 10.0.6 and 9.0.9 (`tests/kicad/sheets/test_sheet_import.py`,
`H-K-WKS-CORNER`), which verifies the writer and `layout`, not the reading. One observation of that oracle:
KiCad draws a text justified `top` one text height below its anchor.

## What a template is

| fact | source | label | hypothesis |
|---|---|---|---|
| A sheet template is drawn as a schematic document and saved under the file type "Advanced Schematic template (*.SchDot)". No source describes a container of its own, so a `.SchDot` is read as a binary or an ASCII schematic with another extension | S-0261 | INFERRED | H-A-RD-SHT-SAME |
| A template holds the sheet size, the border and zone settings, graphics such as a title block, and the list of sheet-level parameters | S-0261 | INFERRED | H-A-RD-SHT-SAME |
| A custom title block is drawn with drawing objects (lines, images) and text strings; the built-in title block can be switched on or off in the page options | S-0261, S-0262 | INFERRED | H-A-RD-SHT-SAME |
| Record 0, the first record after the header, is the sheet record (`RECORD=31`) | S-0130 | INFERRED | H-A-RD-SHT-SAME |
| In a saved template, the drawn records carry no `OWNERINDEX`: they are root records beside the sheet record | S-0264, S-0265 | INFERRED | H-A-RD-SHT-SAME |
| When a template is applied to a sheet, its texts and graphics cannot be selected or edited there | S-0261 | INFERRED | H-A-RD-SHT-OWNER |
| A template record (`RECORD=39`, with `FILENAME`) owns the custom title block's lines and labels of a document; the sheet record holds `SHOWTEMPLATEGRAPHICS` and `TEMPLATEFILENAME`. A second reader places the children of that record on the sheet | S-0130, S-0131 | INFERRED | H-A-RD-SHT-OWNER |

## Sheet record

| fact | source | label | hypothesis |
|---|---|---|---|
| `SHEETSTYLE` selects one of 18 predefined sizes. Each has a drawing area, in units of 10 mil, that tends to be slightly smaller than the paper of that name: 0 A4 1150 × 760; 1 A3 1550 × 1110; 2 A2 2230 × 1570; 3 A1 3150 × 2230; 4 A0 4460 × 3150; 5 A 950 × 750; 6 B 1500 × 950; 7 C 2000 × 1500; 8 D 3200 × 2000; 9 E 4200 × 3200; 10 Letter 1100 × 850; 11 Legal 1400 × 850; 12 Tabloid 1700 × 1100; 13 OrCAD A 990 × 790; 14 OrCAD B 1540 × 990; 15 OrCAD C 2060 × 1560; 16 OrCAD D 3260 × 2060; 17 OrCAD E 4280 × 3280. A missing key is style 0 | S-0130, S-0131 | INFERRED | H-A-RD-SHT-AREA |
| `USECUSTOMSHEET=T` selects the size `CUSTOMX` × `CUSTOMY`; without it these two keys may still be present and are ignored | S-0130 | INFERRED | H-A-RD-SHT-AREA |
| `WORKSPACEORIENTATION` 0 is landscape and 1 is portrait: it switches the orientation of the style. How it combines with a custom sheet is not stated | S-0130 | INFERRED | H-A-RD-SHT-AREA |
| `BORDERON`, `TITLEBLOCKON` and `REFERENCEZONESON` are Booleans: the border, the built-in title block and the reference zones | S-0130 | INFERRED | H-A-RD-SHT-BORDER |
| `CUSTOMXZONES`, `CUSTOMYZONES` and `CUSTOMMARGINWIDTH` hold the zone counts and the margin width of a custom sheet. The page options name the same settings: horizontal and vertical divisions, a margin width that is the distance from the page edge to the border lines, and the corner the zone labels start from | S-0130, S-0262 | INFERRED | H-A-RD-SHT-BORDER |
| No source gives the margin width or the zone counts of a standard style, nor the geometry of the built-in title block, nor the key of the zone origin | S-0130, S-0262 | INFERRED | H-A-RD-SHT-BORDER |
| The font table `FONTIDCOUNT`, `SIZE<n>`, `FONTNAME<n>`, `BOLD<n>`, `ITALIC<n>`, `UNDERLINE<n>` is referenced by `FONTID`; `SYSTEMFONT` is the default font, normally 1 | S-0130 | INFERRED | H-A-RD-SHT-TEXT |
| `SIZE<n>` is a line spacing in units of 10 mil: for the value 10 the spacing is 100 mil, which is 7.2 points, and the visible em size of one common font is about 0.875 of it | S-0130 | INFERRED | H-A-RD-SHT-TEXT |

## Graphics

| fact | source | label | hypothesis |
|---|---|---|---|
| A line is `RECORD=13` from `LOCATION` to `CORNER`; a rectangle is `RECORD=14` with `LOCATION` at the bottom left and `CORNER` at the top right, `ISSOLID` for a fill; a polyline is `RECORD=6` and a polygon `RECORD=7`, with `LOCATIONCOUNT` and `X<n>`, `Y<n>`; a label is `RECORD=4` at `LOCATION` with `TEXT`, `FONTID`, `ORIENTATION`, `JUSTIFICATION` and `ISMIRRORED` | S-0130, S-0131 | INFERRED | H-A-RD-SHT-SAME |
| `LINEWIDTH`: omitted is 4 mil, 1 is 10 mil, 2 is 20 mil and 3 is 40 mil | S-0130 | INFERRED | H-A-RD-SHT-WIDTH |
| `JUSTIFICATION`: 0 bottom left, 1 bottom centre, 2 bottom right, 3 centre left, 4 centre, 5 centre right, 6 top left, 7 top centre, 8 top right; a missing key is 0 | S-0130, S-0131 | INFERRED | H-A-RD-SHT-TEXT |
| `ORIENTATION` 0 to 3 counts quarter turns; the text turns about its anchor (with orientation 2, justification 8 fixes the bottom-left corner of the text) | S-0130, S-0131 | INFERRED | H-A-RD-SHT-TEXT |
| Other graphic records exist and have no neutral item: Bézier 5, ellipse 8, pie 9, rounded rectangle 10, elliptical arc 11, arc 12, text frame 28, note 209 | S-0130, S-0131 | INFERRED | H-A-RD-SHT-SAME |

## Special strings

| fact | source | label | hypothesis |
|---|---|---|---|
| A text that starts with `=` shows the value of the parameter named by the rest (`=<ParameterName>`), taken from the sheet, the project or the variant | S-0130, S-0261 | INFERRED | H-A-RD-SHT-STRINGS |
| A second reader matches the parameter name without regard to letter case | S-0131 | INFERRED | H-A-RD-SHT-STRINGS |
| A parameter name with a space is not resolved reliably: an apostrophe or `#NAME?` may be shown | S-0261 | INFERRED | H-A-RD-SHT-STRINGS |
| The predefined names include `Title`, `DocumentNumber`, `Revision`, `SheetNumber`, `SheetTotal`, `Date`, `Time`, `Organization`, `CompanyName`, `Author`, `Engineer`, `DrawnBy`, `CheckedBy`, `ApprovedBy`, `Address1` to `Address4`, `DocumentName`, `ProjectName`, `ImagePath` and `Rule` | S-0263 | INFERRED | H-A-RD-SHT-STRINGS |
| The tool computes the values of `CurrentDate`, `CurrentTime`, `ModifiedDate`, `DocumentFullPathAndName`, `Application_BuildNumber` and `VariantName`; they are not taken from a parameter record | S-0130, S-0263 | INFERRED | H-A-RD-SHT-STRINGS |

## Images

| fact | source | label | hypothesis |
|---|---|---|---|
| An image is `RECORD=30` with `LOCATION` (bottom left), `CORNER`, `EMBEDIMAGE`, `KEEPASPECT` and `FILENAME`, which is a bare file name or an absolute Windows path | S-0130 | INFERRED | H-A-RD-SHT-IMAGE |
| An embedded image's bytes are a file of the `Storage` stream, compressed, under the name the image's `FILENAME` gives | S-0130, S-0147 | INFERRED | H-A-RD-SHT-IMAGE |

## Census of the public templates

Measured on 2026-10-05 by `tests/corpus/test_schdot_corpus.py` on the three fetched rows
(`altium-third-party-schdot-01` and `-02` of S-0264, `-03` of S-0265) and, for record 39, on the thirteen
schematic rows of change c0040. Counts per record kind and per key name only: no text, name, coordinate
or image of a row is recorded. The rows come from two repositories, so these counts are supporting data
and no row of this page is `CORPUS-VERIFIED`.

All three templates are binary compound files that `read_schematic` reads without a warning. Record 0 is
the sheet record, there is no `Additional` record and no record 39, and no record carries an owner.

| record kind | row 01 | row 02 | row 03 | imported as |
|---|---|---|---|---|
| 4 label | 9 | 9 | 31 | texts (9, 9, 31) |
| 6 polyline | 7 | 7 | 17 | lines (7, 7, 17 records) |
| 28 text frame | 6 | 6 | 0 | reported, `altium.sheet.not-representable` |
| 30 image | 0 | 0 | 1 | reported, `altium.sheet.image-not-kept` (`not-png`) |
| 41 sheet-level parameter | 32 | 27 | 28 | names kept in `parameters` |

Key names per record kind, with the number of records that hold each key in rows 01 / 02 / 03 (an indexed
key such as `X1` is counted under its name without the number):

- **31 sheet** (1 / 1 / 1): `AREACOLOR`, `BORDERON`, `CUSTOMX`, `CUSTOMY`, `DISPLAY_UNIT`, `FONTIDCOUNT`,
  `HOTSPOTGRIDON`, `HOTSPOTGRIDSIZE`, `ISBOC`, `SHEETNUMBERSPACESIZE`, `SNAPGRIDON`, `SNAPGRIDSIZE`,
  `SYSTEMFONT`, `USEMBCS`, `VISIBLEGRIDON`, `VISIBLEGRIDSIZE` in every row; `CUSTOMMARGINWIDTH`,
  `CUSTOMMARGINWIDTH_FRAC`, `CUSTOMXZONES`, `CUSTOMYZONES`, `CUSTOMX_FRAC`, `CUSTOMY_FRAC`,
  `FILEVERSIONINFO`, `REFERENCEZONESTYLE` 1 / 1 / 0; `SHEETSTYLE` and `WORKSPACEORIENTATION` 0 / 1 / 0;
  font keys `SIZE` 7 / 7 / 8, `FONTNAME` 7 / 7 / 8, `BOLD` 2 / 2 / 3, `ITALIC` 0 / 0 / 2, `UNDERLINE` 0 / 0 / 1.
- **4 label**: `FONTID`, `INDEXINSHEET`, `LOCATION.X`, `LOCATION.Y`, `OWNERPARTID`, `UNIQUEID` 9 / 9 / 31;
  `TEXT` 9 / 9 / 30; `JUSTIFICATION` 7 / 7 / 18; `LOCATION.X_FRAC` 1 / 1 / 0; `COLOR` 0 / 0 / 2.
- **6 polyline**: `INDEXINSHEET`, `LOCATIONCOUNT`, `OWNERPARTID`, `UNIQUEID` 7 / 7 / 17; `LINEWIDTH` 7 / 7 / 4;
  `X` and `Y` 14 / 14 / 35 each.
- **28 text frame** (6 / 6 / 0): `AREACOLOR`, `CLIPTORECT`, `CORNER.X`, `CORNER.Y`, `FONTID`, `INDEXINSHEET`,
  `LOCATION.X`, `LOCATION.Y`, `OWNERPARTID`, `TEXT`, `TEXTMARGIN_FRAC`, `UNIQUEID`, `WORDWRAP`; `TEXTCOLOR` 1 / 1 / 0.
- **30 image** (0 / 0 / 1): `CORNER.X`, `CORNER.X_FRAC`, `CORNER.Y`, `CORNER.Y_FRAC`, `EMBEDIMAGE`, `FILENAME`,
  `INDEXINSHEET`, `KEEPASPECT`, `LOCATION.X`, `LOCATION.Y`, `OWNERPARTID`, `UNIQUEID`.
- **41 parameter**: `COLOR`, `FONTID`, `ISHIDDEN`, `NAME`, `OWNERPARTID`, `UNIQUEID` 32 / 27 / 28;
  `INDEXINSHEET` 31 / 26 / 27; `TEXT` 32 / 27 / 25; `READONLYSTATE` 4 / 4 / 4; `LOCATION.X` 1 / 0 / 1;
  `LOCATION.Y` 5 / 0 / 1.

What the census shows, stated as observations of these rows:

| fact | source | label | hypothesis |
|---|---|---|---|
| The three saved templates are compound files with the binary schematic header; record 0 is the sheet record and every drawn record is a root | S-0264, S-0265 | INFERRED | H-A-RD-SHT-SAME |
| No row holds `USECUSTOMSHEET`, yet every row holds `CUSTOMX` and `CUSTOMY`; two rows hold no `SHEETSTYLE` key, which reads as style 0. Every style found (0, 0 and 1) is in the table | S-0264, S-0265 | INFERRED | H-A-RD-SHT-AREA |
| Every row has `BORDERON=T` on a standard style; none holds `TITLEBLOCKON` or `REFERENCEZONESON`. Two rows hold the key `REFERENCEZONESTYLE`, which no source describes | S-0264, S-0265 | INFERRED | H-A-RD-SHT-BORDER |
| The line widths found are a missing key (13 polylines) and 1 (18 polylines); the justifications found are a missing key, 1, 3 and 5; no label holds `ORIENTATION` | S-0264, S-0265 | INFERRED | H-A-RD-SHT-WIDTH |
| 21 of the 49 labels start with `=`: 7 map to a token, 7 to a parameter, 6 name a string the tool computes, and 1 holds no parameter name and is reported | S-0264, S-0265 | INFERRED | H-A-RD-SHT-STRINGS |
| The one image is embedded and `image_data` finds its file under the image's `FILENAME`. Its bytes start with the two letters of a bitmap file although the name ends in `.png`, so it is reported as `not-png` | S-0265 | INFERRED | H-A-RD-SHT-IMAGE |
| Seven of the thirteen schematic documents of change c0040 hold one record 39 each; its children are of the kinds 4, 6, 13, 28 and 30 only (kind 4: 204, kind 6: 99, kind 13: 39, kind 30: 7, kind 28: 1). Every embedded image of the sixteen rows (8) has its file in `Storage` | S-0187, S-0279 | INFERRED | H-A-RD-SHT-OWNER |
| In one of those documents the sheet record has no `SHOWTEMPLATEGRAPHICS` key and the children of record 39 reach past the document's drawing area: they keep the coordinates of the template's own sheet. The importer reports such records as `altium.sheet.outside` | S-0279 | INFERRED | H-A-RD-SHT-OWNER |

## Fenolite's choices

These are rules of the importer, not format facts.

- **Centring.** The drawing area of a style is smaller than its paper, and no source says where it
  sits on the paper. The importer centres it: the left and right margins are half the width difference
  and the top and bottom margins half the height difference. A style without a neutral paper name, a
  custom sheet, and a paper whose difference is negative or not a whole number of micrometres per side
  give the paper `custom` with four zero margins.
- **Anchoring.** Each item is anchored to one corner of the drawing area, the nearest to the centre of
  the bounding box of its points. Only the two rectangles of a drawn border span two corners.
- **Text size.** A text of font size `s` gets the width and the height `s × 25.4 mm / 72`, rounded to
  the micrometre: the size is treated as points. The source's note above says the visible glyphs are
  somewhat smaller; neither model has a width metric.
- **Line widths.** The four widths are rounded to the micrometre: 102 000, 254 000, 508 000 and
  1 016 000 nm.
- **Border rule.** The border and zones are drawn only for a custom sheet with a margin width above 0:
  two rectangles one margin width apart, ticks at equal divisions, numbers along the top and bottom
  and letters from the top along the left and right, starting at the top-left corner. For a standard
  style the importer warns and draws nothing. The built-in title block is never drawn.
- **Rounding.** Lengths are converted exactly and then rounded to the nearest micrometre, half to
  even, because the `.kicad_wks` writer holds micrometres. A whole unit of 10 mil is 254 µm, so only
  fractional coordinates round; their count is reported.
- **Special strings.** Ten names map to neutral tokens (`docs/sheet-templates.md`); every other
  parameter name becomes `{param:NAME}`. A string whose value a tool computes is kept as a parameter
  and reported.
- **Images.** Only an embedded PNG is kept. Nothing is converted and no linked path is opened.
