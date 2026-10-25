# Altium ActiveBOM document (`.BomDoc`)

This page states, in Fenolite's own words, what the reader `fenolite.backends.altium.read.bomdoc` (change
c0190) relies on. The source is one public ActiveBOM document saved by Altium Designer (S-0815, in the
repository of S-0174 and S-0786), downloaded to a scratch folder and never committed; only record kinds, key
names, counts and value forms were read. No parser code of another project was read. The viewer shows the
document; supplier data (prices, stock) is not read.

## Facts

| fact | source | label | hypothesis |
|---|---|---|---|
| The file is text, one record per line, each a run of `\|KEY=VALUE` pairs whose first key is `RECORD`; the first record is `RECORD=BOM` with `VERSION`, `KIND` (`ALTIUM_DESIGNER_LIVEBOM`), a date and a time, a currency and a production quantity (301 records) | S-0815 | INFERRED | H-A-PRJ-BOMDOC |
| The settings are one record each: `GeneralOptions`, `SortOrderOptions` (`SORTORDER`, `Column=Up!Column=Up`), `GroupOrderOptions`, `VisibleOrderOptions` (`VISIBLEORDER`, `Column=width!…`), `VisibleOrderOptions2` (`BASEVIEW`, `FLATVIEW`, `CONSOLIDATEDVIEW`, in the same form), `CustomColumns`, `ColumnsAliases` (`Column=Alias!…`), `FilterOptions`, `CheckGroupCompParamsOptions` (`Comment=1,Description=0,Value=0,Footprint=1`: the parameters parts are grouped by have 1), `ManufacturerLinkOptions`, `FavoriteSuppliers`, `CheckOptions`, `LineNumberingOptions` (`STARTVALUE`, `INCREMENT`) and `Catalog` | S-0815 | INFERRED | H-A-PRJ-BOMDOC |
| Visible columns include supplier columns named with an index (`Supplier 1`, `Supplier Part Number 1`, `Supplier Unit Price 1`, `Supplier Subtotal 1`) and per-quantity columns named with `@` (`Quantity@Default`, `Price@Default`); `Line #` has the width −1 | S-0815 | INFERRED | H-A-PRJ-BOMDOC |
| The catalog is one `CatalogItem` per part type (25), each followed by its `PartChoice` records (supplier offers), one `Solution` (`MANUFACTURER`, `MANUFACTURERPARTNO`, `RANK`) and one `PartChoiceGroups`, sometimes after a `ManufacturerLink` | S-0815 | INFERRED | H-A-PRJ-BOMDOC |
| A `CatalogItem` has `ITEMTYPE`, `UNIQUEID`, `DESIGNITEMID`, `ITEMSOURCE`, `DESCRIPTION`, `LINENUMBER` (empty in the file read) and `COMPONENTPARAMETERS`. `Automatic-NonVault` (13) is a part type of the design: `UNIQUEID` is `<library>\<design item id>` and `DESIGNITEMID` the library reference of its parts. `Manual-Custom` (12) is a line the user added, with a UUID as `UNIQUEID` and a `DESIGNITEMID` such as `Custom row 1` | S-0815 | INFERRED | H-A-PRJ-BOMDOC |
| The file ends with one `Item` per manual line (12): `ITEMTYPE` `Manual-Custom`, the `UNIQUEID` of its catalog item, an empty `DESIGNATOR` and `QUANTITY`. No record lists the parts of the design: the BOM's lines are built from the project's parts | S-0815 | INFERRED | H-A-PRJ-BOMDOC |
