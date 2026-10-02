# Altium ASCII schematic (`.SchDoc`)

This page states, in Fenolite's own words, what the experimental writer `fenolite.backends.altium`
(change c0032) relies on to write a schematic in Altium Designer's ASCII form.

- The code is written from this page and from `project.md` only. No third-party code was copied,
  transcribed or followed; the GPL importer sources (S-0131, S-0132) were read for facts only.
- Sources are listed in `docs/evidence/sources.md`. Altium publishes no specification of the format:
  the facts come from the documentation of an open-source converter (S-0130), KiCad's developer
  documentation (S-0002), facts read in open-source readers and writers (S-0131, S-0142, S-0143,
  S-0144) and Altium's user documentation (S-0133 to S-0141).
- Every fact is `INFERRED` until the maintainer reports what Altium Designer does with the committed
  sample (`docs/evidence/altium-schematic.md`); a confirmed row then names the author report. An author
  report never promotes an operation.
- **No second reader.** `kicad-cli` picks its schematic reader from the file extension and never tries
  its Altium importer (S-0132). Authored `.SchDoc` files in CR LF, in LF and as plain text gave "Failed
  to load schematic" and exit 3 for every command tried (S-0020). So `kicad-cli` is no oracle for this
  page, and no row is `ORACLE-VERIFIED`.
- `tests/unit/test_format_facts.py` checks the tables.

## File form

| fact | source | label | hypothesis |
|---|---|---|---|
| Altium Designer saves a schematic document as "SCH ASCII Version 5.0", a text file that keeps the `.SchDoc` extension, besides the binary forms; third-party importers ask users to save it as "Advanced Schematic ascii (*.SchDoc)" | S-0133 | INFERRED | H-A-SCH-OPEN |
| An ASCII schematic starts with the text `\|HEADER=`; readers tell it from the binary form by that prefix, not by the extension | S-0002, S-0131, S-0133 | INFERRED | H-A-SCH-OPEN |
| The first line is the header record, which has no `RECORD` key: `HEADER=Protel for Windows - Schematic Capture Ascii File Version 5.0`, then `WEIGHT=<n>`, the number of records that follow it. A reader compares the header value with that text and refuses another version | S-0002, S-0130, S-0131 | INFERRED | H-A-SCH-OPEN |
| Each record is one line of fields. A field is `\|KEY=VALUE`, so a line starts with `\|`; the examples end a line with the last value, without a trailing `\|` | S-0002, S-0130, S-0131 | INFERRED | H-A-SCH-OPEN |
| A key ends at the first `=` of its field and the rest of the field is the value, so a value may hold `=`. Keys are upper-case words run together, with exceptions such as `DISPLAY_UNIT` and coordinate keys with a dot (`LOCATION.X`, `CORNER.Y`) | S-0130, S-0131 | INFERRED | H-A-SCH-OPEN |
| A boolean is written `T` when true; a false boolean is usually left out, and a missing integer reads as 0 | S-0130 | INFERRED | H-A-SCH-OPEN |
| No source documents an escape for `\|` or for a line end inside a value: a reader ends a value at the next `\|` and a record at the line end | S-0130, S-0131 | INFERRED | H-A-SCH-OPEN |
| A reader joins a line that ends with the two characters `\|>` to the next line (long records), and trims spaces around values | S-0131 | INFERRED | H-A-SCH-OPEN |
| Plain values are 8-bit text in a Windows code page. A value may be repeated in UTF-8 under the key prefixed with `%UTF8%`. Altium Designer 17 and later save ASCII schematics as UTF-8, older versions in the system code page, and non-Latin text has been reported garbled | S-0130, S-0131, S-0133 | INFERRED | H-A-SCH-OPEN |
| No source states the line end Altium writes in an ASCII schematic. Open-source readers accept CR LF and LF; an open-source project writer states that Altium writes its project files with CR LF | S-0131, S-0142, S-0143 | INFERRED | H-A-SCH-LINEEND |
| Records after the header are numbered from 0 in file order (the header is not counted), and record 0 is the sheet record `RECORD=31` | S-0130, S-0131 | INFERRED | H-A-SCH-OPEN |
| A child record names its owner by `OWNERINDEX`, the owner's record number; sheet-level records have no `OWNERINDEX`. Records are stored depth first, every owner before its children; a reader drops a child whose owner it has not read yet | S-0130, S-0131 | INFERRED | H-A-SCH-OPEN |
| `OWNERPARTID` is -1 for sheet-level records and for a component's designator and parameters, and the part number (1 for a single-part component, equal to its `CURRENTPARTID`) for the component's graphics and pins | S-0130, S-0131 | INFERRED | H-A-SCH-OPEN |
| Embedded files (images) follow their own header line in the ASCII form; a schematic without them has one header | S-0002, S-0131 | INFERRED | H-A-SCH-OPEN |

## Units, axes and colours

| fact | source | label | hypothesis |
|---|---|---|---|
| A length is an integer number of units of 10 mil (1/100 inch, 0.254 mm). An optional `<key>_FRAC` integer adds 1/100 000 of a unit | S-0130, S-0131 | INFERRED | H-A-SCH-OPEN |
| The same unit holds for locations, `CORNER`, `PINLENGTH`, the wire points `X1`, `Y1`, … and `CUSTOMX`, `CUSTOMY` | S-0130, S-0131 | INFERRED | H-A-SCH-OPEN |
| KiCad's developer page calls the base value "mils", but its own sheet table (A4 drawing area 1150 × 760) fits only 10-mil units; the 10-mil reading is used | S-0002, S-0130 | INFERRED | H-A-SCH-OPEN |
| The origin is the sheet's bottom-left corner; X grows rightwards and Y upwards | S-0002, S-0130 | INFERRED | H-A-SCH-OPEN |
| A component's children (body graphics, pins, designator, parameters) carry absolute sheet coordinates, already rotated and mirrored with the component | S-0131 | INFERRED | H-A-SCH-OPEN |
| A colour is an integer with red in bits 0 to 7, green in bits 8 to 15 and blue in bits 16 to 23. Values seen in files: `128` (dark red) for component outlines, `11599871` (pale yellow) for component fills, `8388608` (dark blue) for designators, `16317695` (off-white) for the sheet. A wire takes any colour; the writer uses the same dark blue for wires, labels and ports | S-0130 | INFERRED | H-A-SCH-OPEN |
| The sheet record holds a font table: `FONTIDCOUNT=<n>`, then for each font `SIZE<i>` and `FONTNAME<i>` (optionally `ITALIC<i>`, `BOLD<i>`, …); text records name a font by its 1-based `FONTID`, and `SYSTEMFONT` names the default font | S-0130, S-0131 | INFERRED | H-A-SCH-OPEN |

## Sheet record

| fact | source | label | hypothesis |
|---|---|---|---|
| The sheet record is `RECORD=31`. Keys seen with these values: `SYSTEMFONT=1`, `BORDERON=T`, `SNAPGRIDON=T`, `SNAPGRIDSIZE=10`, `VISIBLEGRIDON=T`, `VISIBLEGRIDSIZE=10`, `HOTSPOTGRIDON=T`, `HOTSPOTGRIDSIZE=4`, `DISPLAY_UNIT=4` (1/100 inch) and `AREACOLOR=16317695`. Which keys Altium requires is not documented | S-0130 | INFERRED | H-A-SCH-OPEN |
| `SHEETSTYLE` selects the paper. Styles 0 to 4 are the ISO sizes A4, A3, A2, A1 and A0, landscape, with drawing areas of 1150 × 760, 1550 × 1110, 2230 × 1570, 3150 × 2230 and 4460 × 3150 units; the drawing area is slightly smaller than the paper | S-0002, S-0130, S-0131 | INFERRED | H-A-SCH-OPEN |
| `USECUSTOMSHEET=T` with `CUSTOMX` and `CUSTOMY` (units) gives a custom sheet size; `CUSTOMX` and `CUSTOMY` are ignored without `USECUSTOMSHEET=T` | S-0130, S-0131 | INFERRED | H-A-SCH-OPEN |
| `WORKSPACEORIENTATION` is 0 for landscape and 1 for portrait, so a sheet record without it is landscape | S-0130, S-0131 | INFERRED | H-A-SCH-OPEN |
| `TITLEBLOCKON=T` shows the title block; a sheet record without it has none | S-0130 | INFERRED | H-A-SCH-OPEN |

## Components, bodies and pins

| fact | source | label | hypothesis |
|---|---|---|---|
| A placed component is `RECORD=1`, at sheet level (`OWNERPARTID=-1`), before all its children. Keys: `LIBREFERENCE` (the symbol name in its library), `SOURCELIBRARYNAME` (the file name of the source library), `DESIGNITEMID`, `PARTCOUNT`, `DISPLAYMODECOUNT`, `CURRENTPARTID`, `LOCATION.X`, `LOCATION.Y` (its reference point), `UNIQUEID`, `COLOR`, `AREACOLOR`; optional `ORIENTATION` (0 to 3 quarter turns counter-clockwise) and `ISMIRRORED` | S-0002, S-0130, S-0131 | INFERRED | H-A-SCH-OPEN |
| `PARTCOUNT` is one more than the number of parts, so 2 for a single-part component; `CURRENTPARTID` is the part shown (1) and `DISPLAYMODECOUNT` the number of alternative graphics (1) | S-0130, S-0131 | INFERRED | H-A-SCH-OPEN |
| A placed component is cached in the schematic, so the document opens and shows it without its source library | S-0137 | INFERRED | H-A-SCH-OPEN |
| A rectangle is `RECORD=14`: `LOCATION` is its bottom-left corner and `CORNER` its top-right corner; `LINEWIDTH` (1 is the small width), `COLOR` (outline), `AREACOLOR` (fill) and `ISSOLID=T` (filled) | S-0130, S-0131 | INFERRED | H-A-SCH-OPEN |
| A pin is `RECORD=2` with `OWNERINDEX` (the component), `OWNERPARTID` (its part), `FORMALTYPE=1` (the only value seen), `ELECTRICAL`, `PINCONGLOMERATE`, `PINLENGTH`, `LOCATION.X`, `LOCATION.Y`, `NAME` (the pin's function, drawn inside the body) and `DESIGNATOR` (the pin number, drawn outside) | S-0130, S-0131 | INFERRED | H-A-SCH-OPEN |
| `ELECTRICAL` is 0 input (the default), 1 input/output, 2 output, 3 open collector, 4 passive, 5 high impedance, 6 open emitter or 7 power; Altium lists the same eight pin types | S-0130, S-0131, S-0140 | INFERRED | H-A-SCH-OPEN |
| `PINCONGLOMERATE` is a bit field: bits 0 and 1 give the direction (0 rightwards, 1 upwards, 2 leftwards, 3 downwards), 0x04 hides the pin, 0x08 shows its name, 0x10 shows its number, 0x40 locks it. A left-edge pin that shows only its number is 2 + 0x10 = 18 | S-0130, S-0131 | INFERRED | H-A-SCH-OPEN |
| A pin's `LOCATION` is its body end, where the pin line leaves the body. Its electrical end lies `PINLENGTH` further in its direction (rightwards +X, upwards +Y, leftwards −X, downwards −Y), and only that end, away from the body, is electrical | S-0130, S-0131, S-0140 | INFERRED | H-A-SCH-NETS |

## Designator and comment

| fact | source | label | hypothesis |
|---|---|---|---|
| The designator is `RECORD=34` owned by the component, with `OWNERPARTID=-1`, `NAME=Designator`, `TEXT=<designator>`, `LOCATION.X`, `LOCATION.Y`, `FONTID` and `COLOR` (`8388608` seen) | S-0130, S-0131 | INFERRED | H-A-SCH-OPEN |
| A component parameter is `RECORD=41` owned by the component with `OWNERPARTID=-1`, `NAME`, `TEXT`, `LOCATION.X`, `LOCATION.Y`, `FONTID` and `COLOR`; the parameter named `Comment` holds the part's comment, which readers take as its value | S-0130, S-0137, S-0144 | INFERRED | H-A-SCH-OPEN |
| A parameter `TEXT` that starts with `=` names another parameter of the same owner, and Altium shows that parameter's text instead | S-0130 | INFERRED | H-A-SCH-OPEN |

## Library and footprint links

| fact | source | label | hypothesis |
|---|---|---|---|
| A placed part shows its "Design Item ID" and "Source" (the source library); the source library name and the model names are stored in the placed component, and models are linked by name, never copied | S-0137 | INFERRED | H-A-SCH-LINK |
| "Design Item ID" is the component's `DESIGNITEMID` (equal to the symbol name `LIBREFERENCE` for a part from a file-based library) and "Source" its `SOURCELIBRARYNAME`; the mapping is read from the key names | S-0002, S-0130, S-0137 | INFERRED | H-A-SCH-LINK |
| "Tools » Update From Libraries" takes each component's source from its library link and lists a part whose library is not available as `<Not Found>`. It offers a full replacement of the symbol or "Replace selected attributes", with separate switches for graphical attributes, parameters and models | S-0136 | INFERRED | H-A-SCH-UPDATE |
| A footprint link is a chain owned by the component: `RECORD=44` (the implementation list), then `RECORD=45` (one implementation) owned by the 44, then `RECORD=46` (its map definer list) and `RECORD=48` (its parameters), both owned by the 45. Record 47 (a pin-to-pad map) is a child of 46 and is needed only for an explicit map | S-0130, S-0131, S-0142, S-0144 | INFERRED | H-A-SCH-LINK |
| An implementation record holds `MODELNAME` (the footprint name), `MODELTYPE=PCBLIB`, `DATAFILECOUNT=1`, `MODELDATAFILEENTITY0` (the footprint name), `MODELDATAFILEKIND0=PCBLIB`, `MODELDATAFILE0` (the footprint library file the model comes from, such as `X.PcbLib`) and `ISCURRENT=T` for the current footprint | S-0130, S-0131, S-0144 | INFERRED | H-A-SCH-LINK |
| Model type `PCBLIB` is a footprint, and data-file kind `PCBLIB` is a footprint library (`*.PcbLib`) | S-0135 | INFERRED | H-A-SCH-LINK |
| The PCB model of a part has a footprint name and a "PCB Library" mode: any library, a library name, a library path, or the component's own library. Which keys give which mode is not documented; a bare file name in `MODELDATAFILE0` is read as the "Library name" mode | S-0135, S-0144 | INFERRED | H-A-SCH-LINK |
| Without a pin-to-pad map, pins are matched to pads by equal designators | S-0130, S-0135 | INFERRED | H-A-SCH-ECO |
| The engineering change order looks a footprint up in the project's libraries, then the installed libraries, then the project's search paths; the project folder is the default search path and is searched first | S-0138 | INFERRED | H-A-SCH-ECO |

## Wires, net labels and power ports

| fact | source | label | hypothesis |
|---|---|---|---|
| A wire is `RECORD=27` at sheet level (`OWNERPARTID=-1`): `LINEWIDTH` (1 is the small width), `COLOR`, `LOCATIONCOUNT=<n>`, then the points `X1`, `Y1`, …, `X<n>`, `Y<n>` | S-0130, S-0131 | INFERRED | H-A-SCH-NETS |
| A wire connects to a pin at the pin's electrical end | S-0140 | INFERRED | H-A-SCH-NETS |
| A net label is `RECORD=25` at sheet level: `LOCATION.X`, `LOCATION.Y`, `TEXT` (the net name), `FONTID`, `COLOR`, optional `ORIENTATION` | S-0130, S-0131 | INFERRED | H-A-SCH-NETS |
| A net label's electrical hotspot is its lower-left corner, its `LOCATION`, which must touch a wire, a bus or a pin; labels may sit on pins, wires and buses; same-named labels connect within one sheet | S-0140 | INFERRED | H-A-SCH-NETS |
| A power port is `RECORD=17` at sheet level: `LOCATION.X`, `LOCATION.Y` (its connection point), `STYLE`, `ORIENTATION` (the direction its symbol points: 0 right, 1 up, 2 left, 3 down), `SHOWNETNAME=T`, `TEXT` (the net name), `FONTID`, `COLOR` | S-0130, S-0131 | INFERRED | H-A-SCH-NETS |
| Power-port `STYLE` values: 0 circle, 1 arrow, 2 bar, 3 wave, 4 power ground, 5 signal ground, 6 earth, 7 to 10 GOST variants | S-0131, S-0140 | INFERRED | H-A-SCH-OPEN |
| A power port's style does not choose its net, its name does; same-named power ports connect across the whole design | S-0140 | INFERRED | H-A-SCH-NETS |
| A junction is `RECORD=29`. Altium adds junctions at T joints itself, and wires that never meet need none | S-0130, S-0140 | INFERRED | H-A-SCH-NETS |

## Unique ids

| fact | source | label | hypothesis |
|---|---|---|---|
| A `UNIQUEID` value is eight upper-case letters from `A` to `Y` (25 letters) | S-0130 | INFERRED | H-A-SCH-UID |
| A component's unique id links the schematic component to its PCB component; when the ids do not match, Altium falls back on designators | S-0139 | INFERRED | H-A-SCH-RELINK |
| Duplicate unique ids of objects other than components are corrected when the document is loaded; duplicate component ids are not repaired, and the compiler reports them | S-0139 | INFERRED | H-A-SCH-UID |
| No source says whether Altium creates a component unique id that a file leaves out | S-0130, S-0139 | INFERRED | H-A-SCH-UID |

## Fenolite's choices

These are decisions of the writer, not format facts (design of change c0032, capability
`altium-schematic-writer`):

- Bytes are printable 7-bit ASCII (0x20 to 0x7E) and every line ends with CR LF, the last one included.
  `ascii.text_problem` refuses `|`, any other character, an empty text, a leading or trailing space,
  and a comment that starts with `=`; nothing is escaped or replaced.
- Every written length is a multiple of 100 mil (10 units), so no `_FRAC` key is written, and every
  point lies inside the sheet, so every coordinate is positive.
- Keys are written in the fixed order of `altium-schematic-writer`; record 0 is the sheet; component
  blocks come in component-path order, then the sheet-level wires, labels and ports.
- The sheet has one font, `Times New Roman` at size 10, used by every text record (`FONTID=1`).
- Generic bodies, stubs, label and port positions, the layout and the unique-id derivation are choices
  of the `altium-schematic-writer` capability (change c0032).
- Stub lengths: a label stub is `max(300, 100 · ⌈(70 · L + 150) / 100⌉)` mil for a label of `L`
  characters. A port stub is 200 mil, except for the second, fourth, … port of a run of ports on
  adjacent pins of one edge: its stub is `200 + 100 · ⌈(100 + 70 · M + 100) / 100⌉` mil, `M` being the
  longest net name of the ports one row above and one row below it, so that port sits at least 100 mil
  past both neighbours and their texts (100 mil for the symbol and 70 mil per character are Fenolite
  estimates). Ports of adjacent pins thus alternate between short and long stubs. With 200-mil stubs on
  pins 100 mil apart, the ports of the sample's `U1` and `U2` pins 1 and 2 overlapped in KiCad 10.0.6's
  import of the sample (2026-10-02; supporting data, `docs/evidence/altium-schematic.md`).
