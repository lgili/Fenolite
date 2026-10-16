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
