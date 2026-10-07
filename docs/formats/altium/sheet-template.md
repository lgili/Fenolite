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

## Writing a template (change c0087)

`fenolite.backends.altium.schdot` writes a neutral drawing sheet as a template, and the schematic writers
draw the same records on a built sheet. It uses the rows above in the other direction; the rows below
state what the writer sets. Nothing here is confirmed by Altium until Part W of
`docs/evidence/altium-schematic.md` is reported.

| fact | source | label | hypothesis |
|---|---|---|---|
| A custom sheet is `USECUSTOMSHEET=T` with `CUSTOMX` and `CUSTOMY` in units of 10 mil, each with an optional `_FRAC` key in 1/100 000 of a unit; two saved templates hold the `_FRAC` keys | S-0130, S-0264 | INFERRED | H-A-SCHDOT-OPEN |
| `BORDERON`, `TITLEBLOCKON` and `REFERENCEZONESON` are Booleans written as `T`; a key that is absent reads as false, so a sheet record without them has no built-in border, title block or reference zones | S-0130 | INFERRED | H-A-SCHDOT-OPEN |
| The drawn lines of the three saved templates are polylines (`RECORD=6`) and their texts are labels (`RECORD=4`), all root records with `OWNERPARTID=-1` | S-0264, S-0265 | INFERRED | H-A-SCHDOT-OPEN |
| A record 41 without an owner is a parameter of the sheet, with `NAME` and `TEXT`, `ISHIDDEN=T`, `FONTID` and `COLOR`; three of the 28 sheet parameters of one saved template hold no `TEXT` key | S-0130, S-0265 | INFERRED | H-A-SCHDOT-STRINGS |
| A label whose text is `=<ParameterName>` shows the value of that parameter of the document; the predefined names of the table "Special strings" need no record in the template | S-0130, S-0261, S-0263 | INFERRED | H-A-SCHDOT-STRINGS |
| A length of whole micrometres is not a whole number of 1/100 000 unit (one step is 2.54 nm): written to the nearest step it is at most 1.27 nm off, and a reader that rounds to the micrometre gets it back | S-0130, S-0131 | INFERRED | H-A-SCHDOT-READBACK |
| A font table may hold two equal entries (the same name, size, bold and italic) and a reader takes each by its number. One sheet written with the entries 10, 10, 5 and 7 points was saved by Altium Designer 26 with three entries, its labels naming the renumbered ones (one file, 2026-10-07; minor version not stated). Whether equal entries are an error for Altium is not known | S-0130, S-0610 | INFERRED | H-A-SCHDOT-FONT-MERGE |
| A sheet record without `AREACOLOR` and records without `COLOR` were shown by Altium Designer 26 as a page that was all black (the first files of Part R, 2026-10-07). The believed cause is that an absent colour key reads as 0, black; it is not confirmed, and the files also had no bodies and pins of length 0 | S-0611, S-0130 | INFERRED | H-A-SCHDOT-AREACOLOR |

### The writer's choices

- **One page.** A template has one sheet size, so the writer takes the page (width and height) and draws
  the neutral sheet as `templates.layout` predicts it on the first page: repeats are written as copies and
  an item of the scope `not_first` is left out.
- **Custom sheet of the paper's size.** The sheet record is a custom sheet of exactly the page, without
  `SHEETSTYLE` and without `WORKSPACEORIENTATION`: the drawing area of a standard style is smaller than
  its paper and no source says where it lies, and how the orientation key combines with a custom sheet is
  not stated. The size is written as oriented.
- **No built-in border.** `BORDERON`, `TITLEBLOCKON` and `REFERENCEZONESON` are not written. The frame,
  the reference zones and the title block are drawn records, because the built-in border has equal
  divisions and a specification has a zone pitch. The margins of the neutral sheet become the positions
  of the records on the page.
- **Records.** A line is a polyline of two points and a rectangle a closed polyline of five, with
  `OWNERPARTID=-1`, `LINEWIDTH` (left out for the 4 mil width) and `LOCATIONCOUNT`, `X<n>`, `Y<n>` and
  their `_FRAC` keys. A text is a label with `LOCATION`, `TEXT`, `FONTID`, and `JUSTIFICATION` and
  `ORIENTATION` when they are not 0. No colour key is written, so every record is black, and no
  `UNIQUEID` or `INDEXINSHEET`.
- **Fonts.** Font 1 is the system font of the schematic writer (10 points, not bold, not italic). A text
  in that font names font 1; the other fonts of the texts follow it, one per distinct size, bold and
  italic, in order of first use, all with the writer's one font name, so the table holds each distinct
  font once (change c0146; before it a text of 10 points added a second entry equal to the first). A text of
  height `h` gets the size `round(h × 72 / 25.4 mm)` points, at least 1: the inverse of the import's rule.
- **Line widths.** The nearest of 4, 10, 20 and 40 mil; a width that is replaced is counted in the info
  `altium.sheet.rounded`, as is a text height that is not a whole number of points.
- **Special strings.** A text that is one token is written as `=<Name>` with the name of the import's
  table (`SPECIAL_STRINGS` is its inverse); one parameter token `{param:NAME}` as `=NAME`, with a sheet
  parameter record of that name and no `TEXT`, so that the name exists in a document made from the
  template. `{paper}` has no special string and is written as the paper's name. A text that mixes a token
  with other text is not written: no source gives a form for it.
- **Not written.** A bitmap (`altium.sheet.image-not-kept`): the embedded-file record is known, but the
  size an image gets is not kept by the import either, so the logo was cut from this change. A text
  outside printable 7-bit ASCII, or with a vertical bar: the writers of this package write no other text.
- **On a built sheet.** The same records follow every other record of the document, then the sheet
  parameters with their values. The sheet record keeps its grids and its first font and becomes the
  custom sheet of the page; the layout's origin stays the bottom-left corner.
