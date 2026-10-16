# Altium Draftsman document (`.PCBDwf`)

This page states, in Fenolite's own words, what the Draftsman reader and writer of change c0172 rely on.
Sources are listed in `docs/evidence/sources.md`. The rows of the first sections come from Altium's public
documentation (S-0772 to S-0781), read for facts with nothing copied, and from Microsoft's public pages on
data contracts (S-0782 to S-0784). The container rows come from the four public documents of S-0785 and
S-0786, which are fetched to the corpus cache and measured there; they are never committed. No fact comes
from Altium's program code: nothing was decompiled, no installed assembly was inspected, no schema was
exported from the program, and no third-party Draftsman or Altium parser was read.

Rows from the documentation are `INFERRED`: they say what Altium Designer does, and only the maintainer's
kit (Part F of `docs/evidence/altium-draftsman.md`) can confirm that a written document behaves so. Rows
measured on the public documents are `CORPUS-VERIFIED` when both repositories show them and `INFERRED`
when one does.

## Files and templates

| fact | source | label | hypothesis |
|---|---|---|---|
| Draftsman saves a drawing document as `*.PCBDwf`; a sheet template is a `*.DwsDot` and a document template a `*.DwfDot` | S-0772, S-0774 | INFERRED | H-A-DWF-KIT |
| Draftsman is an extension installed with Altium Designer and is "based on a dedicated file format"; no public page describes that format | S-0773 | INFERRED | H-A-DWF-CONTAINER |
| A document is created by File » New » Draftsman Document or by Add New to Project, from a template or from `[Default]`, which is a blank A4 document | S-0772 | INFERRED | H-A-DWF-MINIMAL |
| A document holds several sheets; sheets are added and removed in the document | S-0772 | INFERRED | H-A-DWF-KIT |
| A sheet template holds sheet-level properties: the size and the title block. A document template holds the content of a new document: several sheets with their views and tables | S-0774 | INFERRED | H-A-DWF-TEMPLATE |
| Saving a document template keeps the current PCB's data as a content "shell"; a new document made from the template gets the project's current PCB data loaded into that shell | S-0774 | INFERRED | H-A-DWF-TEMPLATE |

## Binding to a project and a PCB document

| fact | source | label | hypothesis |
|---|---|---|---|
| A document is created for a project and for one PCB source document of that project, from which it draws its data | S-0772 | INFERRED | H-A-DWF-IMPORT |
| Draftsman extracts design data directly from the PCB document; Tools » Import Changes From `<name>.PcbDoc` refreshes the document's data after the board changed | S-0772, S-0773 | INFERRED | H-A-DWF-IMPORT |
| The creation dialog offers check boxes of the PCB layers whose data the document takes | S-0772 | INFERRED | H-A-DWF-IMPORT |

## Objects

| fact | source | label | hypothesis |
|---|---|---|---|
| The Draftsman objects are views (Board Assembly, Board Fabrication, Drill Drawing, Layer Stack Legend and eleven others), tables (Bill Of Materials, Drill Table, Table, Transmission Line Table and two harness tables), annotations (Note, Text, Callout and four others), six dimensions and six graphical tools | S-0781 | INFERRED | H-A-DWF-KIT |
| A Board Assembly View is an automated composite of the board outline, cut-outs, holes and component graphics. Its View Side is Top, Bottom or a side; captions show the designator or the BOM item position; it has a scale and a title; component graphics come from a 3D projection, the silkscreen, a bounding box or an assembly drawing | S-0775 | INFERRED | H-A-DWF-IMPORT |
| A Board Assembly View shows the not-fitted parts of a variant hidden, crossed or meshed | S-0775 | INFERRED | H-A-DWF-KIT |
| A Board Fabrication View is a composite of the bare board seen from the top or the bottom, drawn from one source layer; the layer value "All (for document template)" makes one page per selected layer when a document is created from the template | S-0776 | INFERRED | H-A-DWF-TEMPLATE |
| A Drill Drawing View draws the board outline and the drill holes with one symbol per hole type, seen from the top or the bottom, for one drill layer pair; its symbols are shared with the Drill Table | S-0777 | INFERRED | H-A-DWF-IMPORT |
| A Layer Stack Legend is a sectional view of the stack with a table whose default columns are Material, Layer, Thickness, Dielectric Material, Type and Gerber, read from the Layer Stack Manager, with an optional footer of the total thickness; an edited cell stops following the board on import | S-0777 | INFERRED | H-A-DWF-IMPORT |
| The Bill Of Materials table takes its rows from the project's ActiveBOM document, else from the source documents (data source Project or Board); it can be filtered to one assembly view and split over pages | S-0778 | INFERRED | H-A-DWF-KIT |
| The Drill Table has columns, a symbol dialog shared with the Drill Drawing View and a layer-pair choice | S-0778 | INFERRED | H-A-DWF-KIT |
| A generic Table holds rows and columns whose cells may hold parameters | S-0778 | INFERRED | H-A-DWF-KIT |
| A Note is a numbered list with a title, an order across the notes of a document, a width that wraps its text, and entries that may hold document parameters | S-0779 | INFERRED | H-A-DWF-KIT |
| A Text is a box with a position, a size, a rotation, a font, an alignment and an optional clip | S-0779 | INFERRED | H-A-DWF-MINIMAL |
| A Linear Dimension is placed between vertices or edges of Draftsman objects such as a view and follows them; it is greyed when its PCB object is deleted; it uses the document's units unless overridden, with symmetric, bilateral and limit tolerances | S-0780 | INFERRED | H-A-DWF-KIT |

## Parameters

| fact | source | label | hypothesis |
|---|---|---|---|
| A document's texts can show parameters of the project (with its variants), of the system (`ProjectName`, `DocumentName`, `SheetNumber`, `SheetTotal`, `CurrentDate`), of the PCB, and custom document parameters; a custom document parameter takes priority | S-0772 | INFERRED | H-A-DWF-PARAMS |
| A template uses the parameters `SheetNumber` and `SheetNumber_OneSheet` for the sheet numbers of its title block | S-0774 | INFERRED | H-A-DWF-PARAMS |
| A project file holds its project parameters as `[Parameter<n>]` sections | S-0187 | INFERRED | H-A-DWF-PARAMS |
| A document has units, dual units and a precision per unit type | S-0772 | INFERRED | H-A-DWF-KIT |

## Outputs

| fact | source | label | hypothesis |
|---|---|---|---|
| A document is output by printing, through an Output Job, by File » Export to PDF (one or several pages) and by File » Export to Dxf | S-0773 | INFERRED | H-A-DWF-OUTJOB |
| In the public output jobs, a drawing document is bound to an output of the type `PCBDrawing` and the category `Documentation` whose document path is the bare file name of the document | S-0786, S-0187 | INFERRED | H-A-DWF-OUTJOB |

## Container

Measured on 2026-10-16 by `tools/draftsman_census.py` on the four public documents of S-0785 (two files)
and S-0786 (two files); the counts per file are in `docs/evidence/altium-draftsman.md`, "Census". A row
that both repositories show is `CORPUS-VERIFIED`; a row that one file shows is `INFERRED`.

| fact | source | label | hypothesis |
|---|---|---|---|
| A document is a run of chunks: the first chunk starts at offset 0 and the file ends where the last chunk ends. There is no file header, no trailer and no checksum of the whole | S-0785, S-0786 | CORPUS-VERIFIED | H-A-DWF-CONTAINER |
| A chunk with the flag byte 1 holds the decoded length and then the stored length, each in the 7-bit form of S-0810 (least significant group first, high bit set while more bytes follow), then one LZ4 block (S-0803) of the stored length | S-0785, S-0786, S-0803, S-0810 | CORPUS-VERIFIED | H-A-DWF-CONTAINER |
| A chunk with the flag byte 0 holds the decoded length in the 7-bit form and then that many bytes as they are. Two such chunks occur, both in one file, in a run of base64 text that the LZ4 blocks around them hardly shrink | S-0785, S-0810 | INFERRED | H-A-DWF-CONTAINER |
| No flag byte other than 0 and 1 occurs | S-0785, S-0786 | CORPUS-VERIFIED | H-A-DWF-CONTAINER |
| Every chunk but the last decodes to exactly 1048576 bytes (1 MiB); the last decodes to fewer | S-0785, S-0786 | CORPUS-VERIFIED | H-A-DWF-CONTAINER |
| Every LZ4 block decodes on its own: no offset reaches before the start of its own chunk's decoded bytes, and the largest offset is at most 65535 | S-0785, S-0786, S-0803 | CORPUS-VERIFIED | H-A-DWF-CONTAINER |
| The decoded chunks, joined in order, are one well-formed XML document in UTF-8 with no declaration and no byte-order mark: it starts with `<Document xmlns="http://schemas.datacontract.org/2004/07/Altium.Designer.PcbDrawing.DataSerialization.V1"` (S-0782) | S-0782, S-0785, S-0786 | CORPUS-VERIFIED | H-A-DWF-CONTAINER |
| The first four bytes `01 80 80 40` are the flag 1 and the decoded length 1048576 of the first chunk. The next four bytes, first read as a field of their own, are the first chunk's stored length (two or three bytes) followed by the first bytes of its LZ4 block, so they are explained by the chunk form | S-0785, S-0786, S-0810 | CORPUS-VERIFIED | H-A-DWF-FIELD |
| None of the other candidates of the design decodes the stream: raw deflate, zlib, gzip (S-0805 to S-0807), `.xz` and legacy LZMA (S-0809) and bzip2 decode no text at the offsets 0 to 8 and at any chunk start, and the leading bytes of an LZ4 frame, a Zstandard frame, an `.xz` stream, a gzip member and a framed Snappy stream (S-0804, S-0807 to S-0809, S-0811) occur at none of them | S-0785, S-0786 | CORPUS-VERIFIED | H-A-DWF-CONTAINER |
| Whether Altium Designer reads a document whose chunks hold less than 1 MiB, only stored chunks, or LZ4 blocks of literals only, is not shown by any public file; probe FP1 of Part F settles the container Fenolite writes | S-0803 | UNKNOWN | H-A-DWF-CONTAINER |

## Document tree

Measured on 2026-10-16 on the decoded text of the four public documents (task 2.1); names and counts only.
The reader `fenolite.backends.altium.read.draftsman` relies on these rows and on the container rows.

| fact | source | label | hypothesis |
|---|---|---|---|
| The root `Document` declares the prefix `i` for `http://www.w3.org/2001/XMLSchema-instance`, which marks an empty member with `i:nil="true"` and a derived object with `i:type` | S-0782, S-0785, S-0786 | CORPUS-VERIFIED | H-A-DWF-CONTAINER |
| The root's members are `Id` and then the others in ordinal alphabetical order; a sheet's members are `Id` and then the others in that order; an item's members are `Id`, `Anchor`, `OriginatedFromTemplate` and then at most three runs, each in alphabetical order, as the data-contract rule of a derived type gives (base type first, S-0783) | S-0783, S-0785, S-0786 | CORPUS-VERIFIED | H-A-DWF-MINIMAL |
| The root's member `FormatVersion` is 22 in the two files of S-0785 and 21 in the two of S-0786, and `FormatAppVersion` holds `_Major`, `_Minor`, `_Build` and `_Revision` in the namespace `http://schemas.datacontract.org/2004/07/System` (22, 8 and 21, 3); which values Altium Designer 26.5 writes is shown by round F0 | S-0785, S-0786 | CORPUS-VERIFIED | H-A-DWF-MINIMAL |
| `Pages` holds one `Page` per sheet. A `Page` holds `Id`, `HorizontalZoneCount`, `Items`, `Margin` (`Bottom`, `Left`, `Right`, `Top`), `SheetSizingMode` (`StandardSize` or `FromTemplate`), `ShowZones`, `Size` (`Height`, `Width`), `StandardSizeName`, `TemplateFileName` and `VerticalZoneCount` | S-0785, S-0786 | CORPUS-VERIFIED | H-A-DWF-MINIMAL |
| Sheet lengths are in units of 1/96 inch: the A4 sheets of S-0785 are 1122.5196850393702 × 793.70078740157487 (297 × 210 mm) with margins of 24; the sheets of S-0786, sized `FromTemplate`, are 1056 × 816 (11 × 8.5 in) with margins of 19.2 while `StandardSizeName` still reads `A4`, so the size members, not the name, give the sheet | S-0785, S-0786 | CORPUS-VERIFIED | H-A-DWF-MINIMAL |
| Each object of a sheet is an `Item` of `Items`, and its `i:type` names its kind. Both repositories show `BoardAssemblyViewData`, `BoardFabricationViewData`, `LayerStackLegendView`, `DrillTableBoardView`, `Text`, `Line` and `Picture` | S-0785, S-0786 | CORPUS-VERIFIED | H-A-DWF-CONTAINER |
| One repository shows the kinds `DrillViewView`, `BillOfMaterialsView`, `Note`, `LinearDimension`, `Callout` and `Rectangle` (S-0786) and `TransmissionLineTableData` (S-0785) | S-0785, S-0786 | INFERRED | H-A-DWF-CONTAINER |
| By their members and the object list of S-0781, `BoardAssemblyViewData` is the Board Assembly View, `BoardFabricationViewData` the Board Fabrication View, `DrillViewView` the Drill Drawing View, `LayerStackLegendView` the Layer Stack Legend, `DrillTableBoardView` the Drill Table, `BillOfMaterialsView` the Bill Of Materials table and `TransmissionLineTableData` the Transmission Line Table; rounds F0.5 to F0.9 of Part F confirm each | S-0781, S-0785, S-0786 | INFERRED | H-A-DWF-KIT |
| Page and item ids are decimal integers, and no two are equal within a document | S-0785, S-0786 | CORPUS-VERIFIED | H-A-DWF-MINIMAL |
| `OriginatedFromTemplate` is `true` on the items of the S-0786 sheets that come from their sheet template (36 per document) and `false` on every other item | S-0786 | INFERRED | H-A-DWF-TEMPLATE |
| A Board Assembly, Board Fabrication or Drill Drawing View holds `Location` (`X`, `Y`), `Scale` (`Denominator`, then `Numenator`, spelled so), `Title` and `ViewSide`; `ViewSide` is `Top` or `Bottom`, and `Right` and `Front` also occur | S-0785, S-0786 | CORPUS-VERIFIED | H-A-DWF-IMPORT |
| A `Text` item holds its string in `Text`; 55 of the 117 texts of the four documents start with `=`, as the title-block texts of a template that show a parameter (S-0772) do | S-0772, S-0785, S-0786 | CORPUS-VERIFIED | H-A-DWF-PARAMS |
| A `Note` holds a `Title` and `Elements` of `NoteElement`, each with `BorderStyle`, `BorderStyleV2`, `FirstLineIndent`, `Id`, `Postfix` and `Text` | S-0779, S-0786 | INFERRED | H-A-DWF-KIT |
| `Parameters` holds the document's parameters as `DrawingDocumentParameterData` (`Name`, `Value`, `Version`); `ParametersData` holds `LastUpdate`, `PCBParameters`, `PCBParametersV2` and `ProjectParameters` of the same form | S-0785, S-0786 | CORPUS-VERIFIED | H-A-DWF-PARAMS |
