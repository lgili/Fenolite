# Altium PCB document (`.PcbDoc`)

This page states, in Fenolite's own words, what the experimental writer `fenolite.backends.altium.pcbdoc`
(change c0035) relies on to write an Altium PCB document in the binary form, and what the test decoder
`tests/_altium_pcb_read.py` checks. Records are in `pcb-records.md`, the container in `compound-file.md`.

- Sources: KiCad's developer page (S-0002), KiCad's importer read for facts only (S-0160, S-0161), an MIT
  binary PcbDoc writer and a project that reports its output checked in the Altium 365 Viewer (S-0143),
  Altium's documentation (S-0164, S-0165, S-0149) and `kicad-cli` (S-0020, S-0166).
- Four documents saved by Altium Designer and published under BSD-2-Clause, MIT and Apache-2.0 (S-0172,
  S-0174, S-0175, S-0176; saved between 2021 and 2025) were downloaded to a scratch folder on 2026-10-03,
  read with the test readers and compared with Fenolite's output. They are not in the repository and
  nothing of them is copied: the rows of "The document as Altium saves it" state the rules their streams
  follow. Nothing was decompiled.
- The maintainer's report of 2026-10-03 (Altium Designer 26.5, a trial licence): the document written
  from the MIT writer's storage set with a short `Board6` record fails with a "catastrophic" error, while
  the PCB library, whose board record has the form Altium saves, opens (`docs/evidence/altium-pcb.md`,
  "Reports"). Which difference Altium refuses is not known; the writer now follows the Altium-saved form
  wherever its rule is clear, and the rest is listed under "Not written". In that form the document opens
  in Altium Designer 26.5 (report of the same day): the rows of the form Fenolite writes carry
  `ALTIUM-VERIFIED(author-report)`.
- The other Altium rows of this page stay `INFERRED` until a report settles them (`docs/evidence/altium-pcb.md`, Parts P and D);
  `kicad-cli pcb import` settles only `H-A-PCB-KICAD-DOC`.
- Rows that only say what KiCad's importer reads carry `ORACLE-VERIFIED(kicad-cli)` since the round trips of 2026-10-03 passed on 10.0.6; that label says nothing about Altium.
- `tests/unit/test_format_facts.py` checks the tables.

## Storages

| fact | source | label | hypothesis |
|---|---|---|---|
| "PCB Binary Version 6.0" is Altium's recommended PCB save format; an ASCII form with the same extension exists | S-0165 | INFERRED | H-A-PCB-DOC-OPEN |
| A binary PCB document is a compound file: root streams for the header, then one storage per object kind, each holding `Header` (a 32-bit record count) and `Data` (the records). Unlike a library footprint, every kind has its own `Data`, and each record keeps its type byte | S-0002, S-0160, S-0161 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-03) | H-A-PCB-KICAD-DOC |
| Property-text kinds: `Board6`, `Nets6`, `Components6`, `Classes6`, `Rules6`, `Polygons6`, `Dimensions6`. Binary kinds: `Arcs6`, `Pads6`, `Vias6`, `Tracks6`, `Texts6`, `Fills6`, `Regions6`, `ShapeBasedRegions6`, `ComponentBodies6`, `ShapeBasedComponentBodies6` | S-0002, S-0161 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-03) | H-A-PCB-KICAD-DOC |
| KiCad needs `Board6/Data`; a missing storage of the other kinds it looks for is reported on its standard output as "File not found" but not in its JSON report. A storage with `Header` 0 and an empty `Data` silences it (local probe of the format research) | S-0161, S-0020 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-03) | H-A-PCB-KICAD-DOC |
| The MIT writer writes empty storages for the kinds it does not use, among them `Arcs6`, `Regions6`, `ComponentBodies6`, `Classes6`, `DifferentialPairs6` and `Connections6`, and a third party reports such a file opening in the Viewer | S-0143 | INFERRED | H-A-PCB-DOC-VIEWER |
| `FileHeader`: KiCad reads a 32-bit length and a short string and checks nothing. The MIT writer writes the 32-bit value 19, then the first ten characters of `PCB 5.0 Binary File` in UTF-16LE (20 bytes); an Altium-saved document of 2024 holds the same 24 bytes. A second root stream `FileHeaderSix` holds the 32-bit value 19, one length byte, `PCB 6.0 Binary File` and the double 5.01 (the MIT writer stops here), then, in the Altium-saved document, the 32-bit value 38, a length byte 38 and a GUID in braces and upper case: the form of a library's `FileHeader` (`pcb-library.md`), which Altium refuses without its id | S-0143, S-0161, S-0172, S-0173 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-PCB-DOC-OPEN |
| An Altium-saved document holds about 47 root storages and a `Board6` record of 2 300 to 2 500 keys with `VERSION=5.01`; "The document as Altium saves it" lists them. The first form Fenolite wrote (the MIT writer's storages, a record of `VERSION=5.00` with the numbered `LAYER<n>NAME` keys only) is refused by Altium Designer 26.5 with a "catastrophic" error (maintainer's report, 2026-10-03) | S-0172, S-0174, S-0175, S-0176 | INFERRED | H-A-PCB-DOC-OPEN |
| `WideStrings6/Data` is a table: per entry a 32-bit index, a 32-bit byte length that counts a 2-byte NUL, and the UTF-16LE text with that NUL | S-0002, S-0160 | INFERRED | H-A-PCB-DOC-VIEWER |
| Primitives of a placed component are stored at absolute board coordinates with the component's index; the document holds no footprint definitions. A component index past the component count stops KiCad's import | S-0161, S-0143 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-03) | H-A-PCB-KICAD-DOC |

## Board, nets and components

| fact | source | label | hypothesis |
|---|---|---|---|
| `Board6/Data` is exactly one property record; KiCad refuses an empty one | S-0160, S-0161 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-03) | H-A-PCB-KICAD-DOC |
| `Board6` holds `ORIGINX` and `ORIGINY` (mil text) and the layer stack `LAYER<i>NAME`, `LAYER<i>PREV`, `LAYER<i>NEXT` (layer ids, 0 the end), and per layer `LAYER<i>MECHENABLED`; an Altium-saved record lists i = 1 … 82 (`pcb-library.md`, "The board record") | S-0002, S-0160 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-PCB-DOC-OPEN |
| **Mechanical layers in use.** In a saved document every mechanical layer 1 to 16 that a track, an arc, a fill, a region or a text lies on is enabled in the board record: `LAYER<56+n>MECHENABLED=TRUE` (43 of 43 such layers over the eight public documents; 16 more are enabled and hold no primitive), and the layer set `&Mechanical Layers` lists exactly the enabled mechanical layers 1 to 16 (8 of 8 records). A layer is therefore enabled where it is used. The writer keeps Mechanical 13 to 16 enabled in every document, as before, and enables each of Mechanical 1 to 12 that a primitive of the document lies on (`libboard.enabled_mechanical`), in the numbered layers and in the two layer sets that list the mechanical layers; it writes the `MECHENABLED` key of the same layer in the `V9` and `_V8` stack lists in step with them, as the library record does (`pcb-library.md`, "The board record"). A document that uses none of the twelve keeps its bytes | S-0580, S-0160 | CORPUS-VERIFIED (8 rows; 2026-10-08) | H-A-PCBX-MECH |
| A primitive on Mechanical `n`, 1 to 16, holds the layer id `56 + n` in its prefix (`pcb-records.md`, "Layer ids"); the import names the layer `Mech.<n>`. The write of a board that was read from an Altium document takes those names for the items of its footprints and for its free texts and graphics; a build has no such layer | S-0160, S-0002 | INFERRED | H-A-PCBX-MECH |
| KiCad builds the copper stack by following `NEXT` from layer 1 until 0. It reads the `LAYER<i>` keys from i = 1 until the first missing `NAME` and follows a link only to an id below the number of names read, so ids up to at least 33 must be listed for a two-layer board to reach 32 | S-0160, S-0161 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-03) | H-A-PCB-KICAD-DOC |
| The outline is the vertex list `VX<k>`, `VY<k>`, `KIND<k>` (0 a line; another value an arc with `CX<k>`, `CY<k>`, `R<k>`, `SA<k>`, `EA<k>`); KiCad turns it into `Edge.Cuts` segments. The MIT project closes the polygon by repeating the first vertex and writes `KIND=Protel_Advanced_PCB` and `VERSION=5.00`; KiCad reads the record of `VERSION=5.01` with the eight keys per vertex as well | S-0002, S-0160, S-0143 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-03) | H-A-PCB-KICAD-DOC |
| `Nets6/Data` holds one property record per net with `NAME`; a net's index is its position | S-0160, S-0143 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-PCB-DOC-NETS |
| `Components6/Data` holds one property record per component: `LAYER` (`TOP` or `BOTTOM`), `X`, `Y` (mil text), `ROTATION` (degrees), `LOCKED`, `NAMEON`, `COMMENTON`, `PATTERN` (the footprint name), `SOURCEDESIGNATOR`, `SOURCEUNIQUEID`, `SOURCEHIERARCHICALPATH`, `SOURCEFOOTPRINTLIBRARY`, `SOURCECOMPONENTLIBRARY` and `SOURCELIBREFERENCE` | S-0160, S-0143 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-PCB-DOC-OPEN |
| KiCad takes the reference from `SOURCEDESIGNATOR`, the footprint id from `SOURCEFOOTPRINTLIBRARY` without path and extension plus `PATTERN`, and the footprint path from `SOURCEHIERARCHICALPATH` and `SOURCEUNIQUEID` with one leading backslash removed | S-0161 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-03) | H-A-PCB-KICAD-DOC |
| A PCB component made from a part on a child sheet holds `SOURCEUNIQUEID=\<sheet symbol unique id>\<component unique id>`, one id per level of the hierarchy (a repeated sheet adds one more), and `SOURCEHIERARCHICALPATH=<top sheet stem>\<sheet symbol designator>`. The link of a part placed on the top sheet of a hierarchical project was not observed: the saved top sheets hold no part | S-0164, S-0188 | INFERRED | H-A-SCH-HIER-ECO |
| For a part two levels down, the link holds the unique ids of both sheet symbols, the upper one first (`connectivity.md`, "Component link": observed through two levels). What `SOURCEHIERARCHICALPATH` holds there was not read from a saved file: the writer of change c0086 extends the one-level form by one `\<sheet symbol designator>` per level, and the component class of such a sheet is named after its own sheet symbol | S-0164, S-0188 | INFERRED | H-A-SCHX-ECO |
| `CHANNELOFFSET` counts the components of one sheet: in the saved board of a hierarchical project the components of each hierarchical path hold 0, 1, 2, …, and every instance of a repeated sheet starts again at 0. It is not an index over the whole board. A few sheets that were edited later hold one value twice | S-0188 | INFERRED | H-A-SCH-HIER-ECO |
| With the two-id link written for parts on module sheets, the change order of Altium Designer 26.5 ("Design » Update PCB Document" on the board example of change c0037) lists no component change, no pin change and no net change: every part on a module sheet matches its board component and the nets match by name. It proposes the component classes, rooms and "Supply Nets" rules that Altium derives from the sheets, and the removal of a board net class that the schematic does not declare. The link of a part on the top sheet of a hierarchical project and a repeated sheet were not checked (maintainer's third report of Part H, 2026-10-03) | S-0164, S-0139 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-SCH-HIER-ECO |
| Altium links a schematic component and its PCB component by the schematic component's unique id, stored on the PCB side as the path `\<id>` (one sheet level); when ids do not match it offers to link by designator, comment and footprint | S-0164, S-0139 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-PCB-DOC-LINK |
| Net names equal to the schematic's keep the connectivity in the change order | S-0164, S-0141 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-PCB-DOC-NETS |
| The Altium 365 Viewer lists `*.PcbDoc` among its inputs and not `*.PcbLib` | S-0149 | INFERRED | H-A-PCB-DOC-VIEWER |
| `kicad-cli pcb import --format altium` reads a PCB document from 10.0; 9.0 has no `pcb import` | S-0166 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-03) | H-A-PCB-KICAD-DOC |
| `kicad-cli` 10.0.6 imports the PCB document Fenolite writes for the blink sample: exit 0, no error in the report or on stdout, three footprints with their references, pad nets and relative positions, the outline as four `Edge.Cuts` segments, the copper layers "Top Layer" and "Bottom Layer", `D1` on the bottom (`tests/kicad/altium/test_pcbdoc_oracle.py`, 2026-10-03) | S-0020, S-0166 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-03) | H-A-PCB-KICAD-DOC |
| The only warnings of that import, on stdout and not in the report, are "Layer 'Internal Plane n' could not be mapped and will be skipped" for n from 1 to 16; the mechanical layers 69 to 72 and the other names give none | S-0020 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-03) | H-A-PCB-KICAD-DOC |
| KiCad moves an imported board to the middle of its sheet, so an import keeps relative positions only; it warns about each `Board6` layer it cannot map (local probe of the format research) | S-0020 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-03) | H-A-PCB-KICAD-DOC |

## The document as Altium saves it

The four Altium-saved documents (S-0172, S-0174, S-0175, S-0176) agree on every rule below unless a row
says otherwise. `tests/unit/backends/altium/test_docboard.py` and `test_pcbdoc.py` check Fenolite's output
against each rule.

### Storages

| fact | source | label | hypothesis |
|---|---|---|---|
| Besides the storages of the first table, every document holds `FromTos6`, `Textures`, `Embeddeds6`, `Coordinates6`, `ModelsNoEmbed`, `EmbeddedBoards6`, `PinPairsSection`, `PadViaLibraryLinks` and `ExtendedPrimitiveInformation` with `Header` 0 and an empty `Data`; `WaivedViolations`, `PrimitiveParameters`, `SmartUnions`, `Fills6` and `Dimensions6` have that same empty form in a document without such objects | S-0172, S-0174, S-0175, S-0176 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-PCB-DOC-OPEN |
| `Advanced Placer Options6`, `Pin Swap Options6` and `Design Rule Checker Options6` (the names hold spaces) each have `Header` 1 and one property block that starts with `RECORD=AdvancedPlacerOptions`, `RECORD=PinSwapOptions` or `RECORD=DesignRuleCheckerOptions`. The first two blocks are equal in the four documents: placer clearances `PLACELARGECLEAR=50mil` and `PLACESMALLCLEAR=20mil`, four switches and two empty net names; the pin-swap block has `QUIET=FALSE`, `APPROXIMATEPINPOSITIONS=FALSE`, `ALLOWPARTIALLYROUTEDCONNECTIONS=TRUE`, `VIAPENALTYSTATE=TRUE`, `CROSSOVERRATIO=50`, `VIAPENALTYVALUE=0` and seven empty lists. The rule-checker block has 20 keys after `RECORD`: report switches, an empty `REPORTFILENAME` unless a report was made, `MAXVIOLATIONCOUNT=500`, the lists `RULESETTOCHECK` and `ONLINERULESETTOCHECK` of rule-kind numbers, and the plane, dead-copper and starved-thermal switches | S-0172, S-0174, S-0175, S-0176 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-PCB-DOC-OPEN |
| `PadViaLibrary` and `PadViaLibraryCache` each have `Header` 0 and one property block `PADVIALIBRARY.LIBRARYID` (a GUID, different in the two), `PADVIALIBRARY.LIBRARYNAME=<Local>` and `PADVIALIBRARY.DISPLAYUNITS=1`: the block of a library's `PadViaLibrary` (`pcb-library.md`) | S-0172, S-0174, S-0175, S-0176 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-PCB-DOC-OPEN |
| `LayerKindMapping` has `Header` 1; its `Data` is a wide string `1.0` (a 32-bit byte length that counts the 2-byte NUL, then UTF-16LE), a 32-bit value and a 32-bit count of 8-byte entries. Two documents hold the 20-byte form with value 0 and count 0 | S-0172, S-0174, S-0175, S-0176 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-PCB-DOC-OPEN |
| `ConstraintManager` has `Header` 1 and one wide string in that same form. In three documents it is the 12 characters of the base64 text of a zlib stream that holds no data | S-0174, S-0175, S-0176 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-PCB-DOC-OPEN |
| `SignalClasses` has `Header` 1 and one property block: the seven common keys of the next table with `LAYER=MULTILAYER`, then `NAME=All xSignals`, `KIND=10`, `SUPERCLASS=TRUE`, `SELECTED=FALSE`, `SCHAUTOGENERATEDCLUSTER=FALSE` and `UNIQUEID` | S-0172, S-0174, S-0175, S-0176 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-PCB-DOC-OPEN |
| `UniqueIDPrimitiveInformation` has one property block per pad, `PRIMITIVEINDEX` (the pad's position in `Pads6`), `PRIMITIVEOBJECTID=Pad` and `UNIQUEID` (eight upper-case letters); its `Header` is the pad count. No other primitive kind is listed | S-0172, S-0174, S-0175, S-0176 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-PCB-DOC-OPEN |
| Every document also holds storages this page does not describe further: `FileVersionInfo` (one block of version messages, as in a library), `Texts` (three texts that tell older software the file is of version 6), `EmbeddedFonts6` (font data), `Models` (one stream per 3D model), `BoardRegions` (one region record of the board shape with its layer-stack id), `UnionNames`, `Rules6` (39 to 41 design rules, each block after a 2-byte lead) and `Classes6` (15 to 20 classes); two documents hold `PrimitiveGuids` | S-0172, S-0174, S-0175, S-0176 | INFERRED | H-A-PCB-DOC-OPEN |

### The `Board6` record

The record is the board record of a library (`pcb-library.md`, "The board record of `Library/Data`") with
one line before it and keys added to its lines. It is 27 lines joined by one CR, each after the first
starting with `\|RECORD=Board`.

| fact | source | label | hypothesis |
|---|---|---|---|
| Line 1 starts with seven keys that open most property records of a document: `SELECTION=FALSE`, `LAYER` (`UNKNOWN` here), `LOCKED=FALSE`, `POLYGONOUTLINE=FALSE`, `USERROUTED=TRUE`, `KEEPOUT=FALSE` and `UNIONINDEX=0`. Then `FILENAME` (the path the document was saved to), `KIND=Protel_Advanced_PCB`, `VERSION=5.01`, `DATE`, `TIME`, `ORIGINX`, `ORIGINY`, `BIGVISIBLEGRIDSIZE=0.000`, `VISIBLEGRIDSIZE=0.000`, `ELECTRICALGRIDRANGE`, `ELECTRICALGRIDENABLED`, `SNAPGRIDSIZE`, `SNAPGRIDSIZEX`, `SNAPGRIDSIZEY`, `TRACKGRIDSIZE=200000.000000`, `VIAGRIDSIZE=200000.000000`, `COMPONENTGRIDSIZE`, `COMPONENTGRIDSIZEX`, `COMPONENTGRIDSIZEY` (binary units with six decimals), `DOTGRID=TRUE`, `DISPLAYUNIT` (1 with a grid in mils, 0 with a metric one) and `DESIGNATORDISPLAYMODE=0` | S-0172, S-0174, S-0175, S-0176 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-PCB-DOC-OPEN |
| The outline follows as a polygon: the seven common keys again with `LAYER=TOP`, `PRIMITIVELOCK=TRUE`, `POLYGONTYPE=Polygon`, `POUROVER=FALSE`, `REMOVEDEAD=FALSE`, `GRIDSIZE=10mil`, `TRACKWIDTH=10mil`, `HATCHSTYLE=None`, `USEOCTAGONS=FALSE`, `MINPRIMLENGTH=3mil`, then per vertex k from 0 the eight keys `KIND<k>`, `VX<k>`, `VY<k>`, `CX<k>`, `CY<k>`, `SA<k>`, `EA<k>`, `R<k>` (a line vertex has `KIND` 0, centre and radius `0mil` and both angles zero), the first vertex repeated last. Then `SHELVED=FALSE`, `RESTORELAYER=UNKNOWN`, `RESTORENET` (empty), `REMOVEISLANDSBYAREA=TRUE`, `REMOVENECKS=TRUE`, `AREATHRESHOLD=250000000000.000000`, `ARCRESOLUTION=0.5mil`, `NECKWIDTHTHRESHOLD=5mil`, `POUROVERSTYLE=2`, `NAME` (empty), `POURINDEX=-1`, `IGNOREVIOLATIONS=FALSE` and `SPLITLINECOUNT=0` | S-0172, S-0174, S-0175, S-0176 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-PCB-DOC-OPEN |
| An angle is written in scientific form with a leading space, one digit, 14 decimals and a signed four-digit exponent, such as ` 0.00000000000000E+0000` and ` 2.70000000000000E+0002`; `ROTATION` of a component has the same form | S-0172, S-0174, S-0175, S-0176 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-PCB-DOC-OPEN |
| Line 1 ends with the sheet, `SHEETX=1000mil`, `SHEETY=1000mil`, `SHEETWIDTH=10000mil`, `SHEETHEIGHT=8000mil`, `SHOWSHEET=FALSE`, `LOCKSHEET=TRUE`, and `PLANE<n>NETNAME` for n = 1 … 16, `(No Net)` for a plane without a net | S-0172, S-0174, S-0175, S-0176 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-PCB-DOC-OPEN |
| Line 2 is the first line of a library's record without its five file keys, with a sub-stack: after the six `V9_MASTERSTACK_` keys come `V9_SUBSTACK0_ID` (a GUID), `_NAME=Board Layer Stack`, `_SHOWTOPDIELECTRIC=FALSE`, `_SHOWBOTTOMDIELECTRIC=FALSE`, `_ISFLEX=FALSE`, `_SERVICE=FALSE`, `_USEDBYPRIMS` and `_TYPE=1`; the same eight keys follow the `LAYERMASTERSTACK_V8` keys as `LAYERSUBSTACK_V8_0<KEY>` | S-0172, S-0174, S-0175, S-0176 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-PCB-DOC-OPEN |
| Each of the nine layers of the physical stack has, before its `ID`, the two keys `<prefix>_<sub-stack GUID>CONTEXT=0` and `<prefix>_<sub-stack GUID>USEDBYPRIMS=FALSE`, where `<prefix>` is `V9_STACK_LAYER<i>`, `V9_CACHE_LAYER<i>` or `LAYER_V8_<i>`; the other layers of the cache and `_V8` lists have none. Three documents add `V9_STACKCUSTOMDATA` (a compressed text) after the cache list; S-0172 has none | S-0172, S-0174, S-0175, S-0176 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-PCB-DOC-OPEN |
| The numbered layers and the `LAYERV7_` layers are those of a library. The line of layers 81 and 82 then ends with the drill pair `LAYERPAIR0LOW=TOP`, `LAYERPAIR0HIGH=BOTTOM`, `LAYERPAIR0DRILLGUIDE=FALSE`, `LAYERPAIR0DRILLDRAWING=FALSE` and `LAYERPAIR0SUBSTACK_0` (the sub-stack GUID); documents with paired mechanical layers add `MECHPAIR<i>L1`/`L2` and `MECHKIND` keys | S-0172, S-0174, S-0175, S-0176 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-PCB-DOC-OPEN |
| The next line holds `TOGGLELAYERS` (82 digits), `PLACEMARKERX<i>` and `PLACEMARKERY<i>` for i = 1 … 10 (`-0.0001mil` when unset), `SELECTIONMEMORYLOCK<i>=FALSE` for i = 1 … 8, the four impedance formulas of the next row, `ELECTRICALGRIDSNAPTOBO=FALSE`, `ELECTRICALGRIDUSEALLLAYERS=FALSE`, the routing directions `ROUTINGDIRECTIONTOP LAYER`, `ROUTINGDIRECTIONMID LAYER <i>` for i = 1 … 30 and `ROUTINGDIRECTIONBOTTOM LAYER` (the keys hold spaces; `Automatic`), the last routing widths `TOPLAYER_MRLASTWIDTH`, `MIDLAYER<i>_MRLASTWIDTH` and `BOTTOMLAYER_MRLASTWIDTH`, `MRLASTVIASIZE`, `MRLASTVIAHOLE`, `LASTTARGETLENGTH=99999mil`, `SHOWDEFAULTSETS=TRUE`, the five layer sets of a library and `BOARDINSIGHTVIEWCONFIGURATIONNAME` (empty) | S-0172, S-0174, S-0175, S-0176 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-PCB-DOC-OPEN |
| The four formulas are the same text in the four documents: `SURFACEMICROSTRIP_I=(60/SQRT(Er*(1-EXP(-1.55*(0.00002+TraceToPlaneDistance)/TraceToPlaneDistance))))*LN(5.98*TraceToPlaneDistance/(0.8*TraceWidth+TraceHeight))`, `SURFACEMICROSTRIP_W=((5.98*TraceToPlaneDistance)/EXP(CharacteristicImpedance/(60/SQRT(Er*(1-EXP(-1.55*(0.00002+TraceToPlaneDistance)/TraceToPlaneDistance)))))-TraceHeight)/0.8`, `SYMMETRICSTRIPLINE_I=(80/SQRT(Er))*LN((1.9*(2*TraceToPlaneDistance+TraceHeight)/(0.8*TraceWidth+TraceHeight)))*(1-(TraceToPlaneDistance/(4*(PlaneToPlaneDistance-TraceHeight-TraceToPlaneDistance))))` and `SYMMETRICSTRIPLINE_W=((1.9*(2*TraceToPlaneDistance+TraceHeight))/(EXP((CharacteristicImpedance/(80/SQRT(Er)))/(1-(TraceToPlaneDistance/(4*(PlaneToPlaneDistance-TraceHeight-TraceToPlaneDistance))))))-TraceHeight)/0.8` | S-0172, S-0174, S-0175, S-0176 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-PCB-DOC-OPEN |
| Then one line `VISIBLEGRIDMULTFACTOR=1.000`, `BIGVISIBLEGRIDMULTFACTOR=5.000`, `ELECTRICALGRIDMULTFACT=0.000`, `OUTLINEMODELCRC=0`, `OUTLINEMODELNAME` (empty), and the six view lines of a library: `CURRENT2D3DVIEWSTATE`, the window `VP.LX`, `VP.HX`, `VP.LY`, `VP.HY` in binary units, and the 2D and 3D configurations with their file names. The view configurations of the documents of 2021 to 2025 hold more `CFGALL.`, `CFG2D.` and `CFG3D.` keys than those of the libraries of 2016 and 2019; the document groups are not written after the layer sets, only inside `2DCONFIGURATION` and `3DCONFIGURATION` | S-0172, S-0174, S-0175, S-0176 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-PCB-DOC-OPEN |
| The last line holds the camera keys of a library (`LOOKAT.X/Y/Z`, `EYEROTATION.X/Y/Z`, `ZOOMMULT`, `VIEWSIZE.X/Y`; the view size is the window's size and `ZOOMMULT` times the width is about 1 190), the snap grid `GR0_TYPE=CartesianGrid`, `GR0_NAME=Global Board Snap Grid`, `GR0_COLOR=6049101`, `GR0_COLORLGE=9473425`, `GR0_PRIO=50`, `GR0_OX`, `GR0_OY` (the origin), `GR0_DRAWMODE=1`, `GR0_DRAWMODELARGE=1`, `GR0_ENABLED=TRUE`, `GR0_MULT=1`, `GR0_MULTLARGE=5`, `GR0_DISPLAYUNIT`, `GR0_COMP=TRUE`, `GR0_GSX`, `GR0_GSY` (the snap grid), `GR0_QSX=99999mil`, `GR0_QSY=99999mil`, `GR0_ROT=0.000000`, `GR0_FLAGS=15`, then the snap options of a library with `EGSNAPTOARCCENTERS=TRUE`, `OGSNAPENABLED=TRUE`, `NEAROBJECTSET=011110100011000000000000001` and `NEARDISTANCE` | S-0172, S-0174, S-0175, S-0176 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-PCB-DOC-OPEN |
| The record ends with `DRILLSYMBOLASENUM=0`, `DRILLSYMBOLSIZE=200000`, `HOLESHAPEHASHSIZE` (the number of `HASHKEY#<i>`/`HASHVALUE#<i>` pairs that follow, one per kind of hole on the board), `VIEWPORTSAREVISIBLE=TRUE`, `UNIQUEID` (eight upper-case letters), `PINPAIRCOUNT=0`, eight teardrop percentages (`TEARDROPPARAM_PERCENTFORVIAS_LENGTH=30.000000`, `…VIAS_WIDTH=70.000000`, `…PADS_LENGTH=100.000000`, `…PADS_WIDTH=200.000000`, `…TRACKS_LENGTH=100.000000`, `…TRACKS_WIDTH=-1.000000`, `…TJUNCTIONS_LENGTH=100.000000`, `…TJUNCTIONS_WIDTH=300.000000`), `TEARDROPPARAM_FLAGSEX` and `SPLITLINECOUNT=0`. Three documents add tuning keys (`SHOWSIGNALLAYERSONLY`, `LAYERCOUNT`, `VALUECOUNT` and `FN#<i>`/`FV#<i>` pairs) before the teardrop keys; S-0172 has none. The closing keys of a library (`BOARDVERSION` and the four GUID keys) are absent | S-0172, S-0174, S-0175, S-0176 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-PCB-DOC-OPEN |

### Records and primitives

| fact | source | label | hypothesis |
|---|---|---|---|
| A `Nets6` record holds, in this order, the seven common keys with `LAYER=TOP`, `PRIMITIVELOCK=FALSE`, `NAME`, `VISIBLE`, `COLOR`, `LOOPREMOVAL=TRUE`, `OVERRIDECOLORFORDRAW=FALSE`, `UNIQUEID` and `JUMPERSVISIBLE=TRUE`; some records add routing widths per layer between the colour switch and the id | S-0172, S-0174, S-0175, S-0176 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-PCB-DOC-NETS |
| A `Components6` record holds, in this order, `SELECTION=FALSE`, `LAYER`, `LOCKED`, `POLYGONOUTLINE=FALSE`, `USERROUTED=TRUE`, `KEEPOUT=FALSE`, `PRIMITIVELOCK=TRUE`, `X`, `Y`, `PATTERN`, `NAMEON`, `COMMENTON`, `GROUPNUM=0`, `COUNT=0`, `ROTATION` (in the angle form above), `UNIONINDEX=0`, `CHANNELOFFSET`, `SOURCEDESIGNATOR`, `SOURCEUNIQUEID`, `SOURCEHIERARCHICALPATH`, `SOURCEFOOTPRINTLIBRARY`, `SOURCECOMPONENTLIBRARY`, `SOURCELIBREFERENCE`, `UNIQUEID` and `JUMPERSVISIBLE=TRUE`; optional keys (a height, text positions, descriptions, library identifiers) stand between them | S-0172, S-0174, S-0175, S-0176 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-PCB-DOC-OPEN |
| The primitives are longer than those Fenolite writes: a track of 49 bytes, an arc of 60, pad subrecord 5 of 185 or 194 and subrecord 6 of 651, a text of 252. The first 119 bytes of a text follow the long form of `pcb-records.md` (the comment and designator flags at 40 and 41, the font name at 46, the wide-string index at 115), and the wide-string index of a text is its position in `Texts6`. Altium Designer 26.5 accepts the short pad, track and arc records in a library and in a document, and the 137-byte text in a document (maintainer's reports, 2026-10-03) | S-0172, S-0174, S-0175, S-0176 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-PCB-DOC-OPEN |

## Fenolite's choices

- `docboard.py` writes the `Board6` record from the rules above and reuses the library's stack, layer and
  view rules (`libboard.py`); `pcbdoc.py` writes the storages. Every value is fixed or derived from the
  design, so equal designs give equal bytes.
- The root holds `FileHeader` in the MIT writer's form and `FileHeaderSix` with its id (the GUID of
  `libboard.guid("pcbdoc:<the components' unique ids joined by commas>")`), then the storages `Board6`,
  `Nets6`, `Components6`, `Pads6`, `Tracks6`, `Arcs6`, `Texts6`, `WideStrings6` and
  `UniqueIDPrimitiveInformation` (one block per pad), the option storages `Advanced Placer Options6`,
  `Pin Swap Options6`, `Design Rule Checker Options6`, `PadViaLibrary`, `PadViaLibraryCache`,
  `LayerKindMapping` (the 20-byte form), `ConstraintManager` (the empty form) and `SignalClasses`, and the
  copper storages `Vias6`, `Polygons6`, `Classes6` and `Rules6` (`pcb-copper.md`; `Header` the record
  count, an empty `Data` without such objects), and the empty storages (`Header` 0, empty `Data`)
  `Fills6`, `Regions6`, `ShapeBasedRegions6`, `Dimensions6`, `ComponentBodies6`, `ShapeBasedComponentBodies6`,
  `DifferentialPairs6`, `Connections6`, `FromTos6`, `Textures`, `Embeddeds6`, `Coordinates6`, `Models`,
  `ModelsNoEmbed`, `EmbeddedBoards6`, `PinPairsSection`, `PadViaLibraryLinks`,
  `ExtendedPrimitiveInformation`, `WaivedViolations`, `PrimitiveParameters` and `SmartUnions`.
- Not written (`H-A-PCB-DOC-OPEN`): `FileVersionInfo` (a library opens without it), `Texts`,
  `EmbeddedFonts6`, `BoardRegions`, `UnionNames`, `PrimitiveGuids`, the super classes and every rule kind but three
  (`pcb-copper.md`), `V9_STACKCUSTOMDATA`, the tuning keys, the mechanical pairs and the hole-shape
  pairs (`HOLESHAPEHASHSIZE=0`). An empty `Models` storage follows the empty form of `ModelsNoEmbed`; no
  Altium-saved document without a 3D model was read.
- `Board6`: `FILENAME` is the file name without a folder, `DATE=2000-01-01`, `TIME=00:00:00`; the snap and
  component grids are 5 mil with `DISPLAYUNIT=1`; `ELECTRICALGRIDRANGE=8mil` and
  `ELECTRICALGRIDENABLED=TRUE`; every plane `(No Net)`; the stack is the two-layer stack of the library
  with Mechanical 13 to 16 enabled; `USEDBYPRIMS` is `TRUE` for the layers that primitives lie on and
  `FALSE` for the sub-stack; `TOGGLELAYERS` is 82 ones; every last routing width is `10mil`, the via
  `50mil` with a `28mil` hole; `NEAROBJECTSENABLED=FALSE`, `NEARDISTANCE=200mil`,
  `TEARDROPPARAM_FLAGSEX=1002`. The view is 2D with the library's view configurations; the window is the
  outline's box widened by 100 mil on every side, `LOOKAT.X/Y` its middle, `VIEWSIZE.X/Y` its size and
  `ZOOMMULT` 1 190 divided by its width, rounded to six decimals. The GUIDs are
  `libboard.guid` of `masterstack`, `substack`, `layer:<long id>`, `pcbdoc:<file name>:padvia` and
  `…:padviacache`; the eight-letter ids are `project.unique_id` of `pcbdoc:<file name>:board`,
  `…:signals`, `…:net:<name>`, `…:component:<schematic id>` and `…:pad:<index>`.
- The outline is written as line vertices (`KIND<k>=0`), the first repeated last, with the eight keys per
  vertex.
- Frame: a point is placed as KiCad places it (`Transform.placement(at, θ, mirror=bottom)`), then Y is
  negated and the result shifted so that the outline's lowest X and highest Y (in KiCad's Y-down frame)
  land on (1000 mil, 1000 mil), which is also `ORIGINX`/`ORIGINY` and `GR0_OX`/`GR0_OY`. On the bottom
  side every layer takes its flip partner.
- Nets are written in name order with the 15 keys of the table (`VISIBLE=TRUE`, `COLOR=7709086`);
  components in component-path order with the 25 keys of the table. `SOURCEUNIQUEID` is `\` followed by
  the schematic `UNIQUEID`, `SOURCEHIERARCHICALPATH` is empty, `NAMEON=TRUE`, `COMMENTON=FALSE`,
  `CHANNELOFFSET` is the component's index among the components of its sheet, which in a `flat` build
  is its index in the document; `ROTATION` is in the angle form.
- A pad whose number is a pin of its component on a net carries that net's index; other pads `0xFFFF`.
- Each component gets a designator text 0.5 mm above the middle of the top edge of the box of its pads and
  graphics, 1 mm high with a 0.15 mm stroke on the overlay of its side, and a comment text 1.5 mm below
  the middle of the bottom edge, hidden by `COMMENTON=FALSE`; both texts are also in `WideStrings6`, the
  wide-string index being the text's position in `Texts6`.
- Pads, tracks, arcs and texts keep the short forms of `pcb-records.md`; Altium Designer 26.5 opens them
  (report of 2026-10-03).
- Routing, vias, polygons, classes and rules are on `pcb-copper.md` (change c0038).
- Change c0037: for a component on a module sheet (`--altium-sheets modules`) `SOURCEUNIQUEID` is
  `\<sheet symbol UNIQUEID>\<component UNIQUEID>` and `SOURCEHIERARCHICALPATH` is
  `<design name>\<module name>`, the sheet symbol's designator being the module name. A component on
  the top sheet, and every component of a `flat` build, keeps the one-id form and the empty path
  (`H-A-SCH-HIER-ECO`). `CHANNELOFFSET` starts at 0 on every module sheet and on the top sheet, in
  component-path order. The first build of c0037 wrote the index over the whole document instead; the
  maintainer's check of step H7 (`docs/evidence/altium-schematic.md`, report of 2026-10-03) found that
  difference from the saved files while looking for another fault, and it was corrected. On the
  rebuilt example the change order of Altium Designer 26.5 lists no component, pin or net change
  (third report of Part H, 2026-10-03).

### A model that was read (change c0090)

`fenolite.backends.altium.lower` writes a model that holds a board without a script. It adds no record
and no field: every byte is one of the records above and of `pcb-records.md`. What differs from a build
is which values the records get.

- **Frame.** A board that was read from a PCB document is written in the document's own frame: the
  import maps a point (x, y) of the document to (x, −y) of the model, and the write maps it back, so
  every coordinate keeps its units. `ORIGINX` and `ORIGINY` get the values that the import kept. Any
  other board is written like a build, with the outline's lower-left corner at (1000 mil, 1000 mil).
- **Components.** A footprint of the model is one component record with its own pads; the model holds
  no graphics of a footprint, so none is written. `UNIQUEID` is the unique id that the import kept for
  the footprint, and `SOURCEUNIQUEID` the one it kept for the component, when one component alone
  holds it. A component without a designator or without a comment gets no text record for it.
- **Arcs** (change c0127). An arc that was read from an arc record is written with the centre, the
  radius and the two angles of that record, which the import keeps in the pair `arc` of the entity's
  bag (`import.md`, "Extension-bag keys"), when they still give the entity's three points within
  2 nm. The record is the one of "Tracks and arcs" in `pcb-copper.md`; only its values differ from
  the ones a build derives from three points. An arc without the pair, and an arc that was moved in
  the model, is derived from its points.
- **Vias with a hole equal to the diameter** (change c0128). A saved document can hold a via whose
  hole equals its diameter (`pcb-copper.md`, "Via"). When the write is the rewrite of a document that
  was read (`rewrite=True`), such a via is written as the via record of any other via with the two
  equal values. In every other write, and in a build, it is refused.
- **Free pads.** A pad that belongs to no component is a pad record whose component index is the
  "none" value, like the pad that a hole is written as ("Free pads as holes"), here with its name, its
  copper and its net.
- **Texts outside 7-bit ASCII.** A designator or a comment that the 8-bit string cannot hold is written
  as a free text is: the 8-bit string with `?` for each character outside ISO-8859-1, and the text
  itself as the wide string.
