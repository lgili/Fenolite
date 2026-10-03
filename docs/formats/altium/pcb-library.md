# Altium PCB library (`.PcbLib`)

This page states, in Fenolite's own words, what `fenolite.backends.altium.pcblib` (change c0035) relies on to
write an Altium PCB library, and what the test decoder `tests/_altium_pcb_read.py` checks. The records of
a footprint are in `pcb-records.md`; the container is in `compound-file.md`.

- Sources: KiCad's developer page (S-0002), KiCad's importer read for facts only (S-0160, S-0162),
  AltiumSharp **version 1 only** (S-0150 at commit `afe796434b6d2110c745c90abe44a6ddf64f5bca`), the
  compound-file specification (S-0145), the oracle observations of `kicad-cli` (S-0020, S-0166), four
  libraries saved by Altium Designer and published under MIT and GPL-2.0 (S-0170, S-0171), and the public
  reports of a GPL writer whose libraries are checked in Altium Designer (S-0173, facts only).
- The Altium-saved libraries were downloaded to a scratch folder on 2026-10-03, read with the test readers
  and compared with Fenolite's output; they are not in the repository and nothing of them is copied: the
  rows below state the rules their streams follow. Nothing was decompiled.
- The maintainer's report of 2026-10-03 (an Altium Designer trial): the library written from AltiumSharp
  version 1's stream set alone, even with no footprint, fails with a "catastrophic" error. S-0173 reports
  the same message for a short `Library/Data` block. The same day, with Altium Designer 26.5 under a
  trial licence on the maintainer's own PC, eight library variants in the form of this page opened and
  looked correct (`docs/evidence/altium-pcb.md`, "Reports"): the rows of the form Fenolite writes carry
  `ALTIUM-VERIFIED(author-report)`. Which keys Altium needs at least stays unknown, and the other Altium
  rows stay `INFERRED` until a report settles them; a report counts only when made with a licence the
  maintainer may use for Fenolite (`LEGAL.md` P4). The Altium 365 Viewer does not open libraries (S-0149).
- Rows that only say what KiCad's importer reads carry `ORACLE-VERIFIED(kicad-cli)` since the round trips of 2026-10-03 passed on 10.0.6; that label says nothing about Altium.
- `tests/unit/test_format_facts.py` checks the tables.

## Container

| fact | source | label | hypothesis |
|---|---|---|---|
| A PCB library is a compound file; KiCad accepts a `.PcbLib` for its Altium footprint plugin when the file has the compound-file signature | S-0002, S-0162 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-03) | H-A-PCB-KICAD-LIB |
| The root holds the stream `FileHeader` of 53 bytes: the text `PCB 6.0 Binary Library File` as a string block (a 32-bit length, one length byte, the text; here both lengths carry the text length 27, unlike the string blocks of `pcb-records.md`), then the double 5.01 with no length before it, then eight upper-case letters as a string block of the same form (a unique id of the library). Altium refuses a library whose header lacks the double or the id. KiCad does not read the stream | S-0170, S-0171, S-0173 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-PCB-LIB-OPEN |
| The root holds the storage `Library` with the streams `Header` (32-bit 1), `Data` and `EmbeddedFonts` (32-bit 0 without fonts) and the storages `Models`, `ModelsNoEmbed` and `Textures` (each `Header` 32-bit 0 and an empty `Data` without 3D models), `ComponentParamsTOC` and `PadViaLibrary`. Libraries saved in 2022 add `LayerKindMapping`; those of 2016 and 2019 do not have it. KiCad reads `Library/Models/Data` only when present; the developer page puts `Models` at the root, the files hold it under `Library` | S-0002, S-0162, S-0170, S-0171, S-0173 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-PCB-LIB-OPEN |
| `Library/Data` is one property block (the board record, see below), then a 32-bit footprint count, then each footprint name as a string block. The block is longer than 65 535 bytes; its 32-bit word carries the length in the low 24 bits. Altium-saved libraries hold no `HEADER` or `WEIGHT` key there (the writer of S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) writes only those two, and Altium refuses that block). KiCad needs the stream, refuses an empty property block and reads the whole stream | S-0162, S-0170, S-0171, S-0173 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-03) | H-A-PCB-KICAD-LIB |
| Each footprint is a root storage holding `Header` (32-bit primitive count), `Parameters`, `WideStrings`, `Data` and the storage `UniqueIDPrimitiveInformation` (Altium writes `ID` in capitals; storage names compare without case, `compound-file.md`) with `Header` and `Data` | S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca), S-0170, S-0171 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-PCB-LIB-OPEN |
| KiCad finds a footprint only through a root storage that holds `Parameters` with `PATTERN`: a footprint without `Parameters` is not converted, and `kicad-cli fp upgrade` still exits 0 (local probe of the format research). Each name of `Library/Data` must be found that way | S-0162, S-0020 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-03) | H-A-PCB-KICAD-LIB |
| `Parameters` is one property block with, in this order, `PATTERN` (the footprint name), `HEIGHT` (a length in mil text), `DESCRIPTION` (empty when there is none), `ITEMGUID` and `REVISIONGUID` (both empty for a footprint that no server manages); KiCad reads `PATTERN` and `DESCRIPTION` | S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca), S-0162, S-0170, S-0171 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-03) | H-A-PCB-KICAD-LIB |
| A footprint's `Data` is its name as a string block, then its primitive records of mixed types one after another, until fewer than 4 bytes remain; `Header`'s count is not compared with it by KiCad | S-0160, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-03) | H-A-PCB-KICAD-LIB |
| `WideStrings` of a footprint is one property block of `ENCODEDTEXT<i>` entries, one per text; KiCad's library path does not read it | S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca), S-0160 | INFERRED | H-A-PCB-LIB-OPEN |
| `UniqueIDPrimitiveInformation/Data` holds one property block per listed primitive with `PRIMITIVEINDEX` (the zero-based position in `Data`, over all kinds), `PRIMITIVEOBJECTID` (such as `Pad`, `Track`, `Arc`) and an eight-letter `UNIQUEID`; `Header` holds the count of blocks. The Altium-saved libraries list their pads and not every track. KiCad does not read it | S-0002, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca), S-0170, S-0171, S-0173 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-PCB-LIB-OPEN |
| `Library/ComponentParamsTOC/Header` is 32-bit 1 whatever the number of footprints. `Data` is one block: a 32-bit length, then per footprint the line `Name=<name>\|Pad Count=<pads>\|Height=<mils>\|Description=<text>` ended by CR LF (no leading `\|`; the height is a number of mils without unit, `0` for none), then one NUL that the length counts | S-0170, S-0171 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-PCB-LIB-OPEN |
| `Library/PadViaLibrary/Header` is 32-bit 0 and `Data` one property block with `PADVIALIBRARY.LIBRARYID` (a GUID in braces), `PADVIALIBRARY.LIBRARYNAME=<Local>` and `PADVIALIBRARY.DISPLAYUNITS=1` | S-0170, S-0171 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-PCB-LIB-OPEN |
| Altium-saved libraries also hold the root storage `FileVersionInfo` (`Header` 32-bit 1, `Data` one property block of `COUNT`, `VER<i>`, `FWDMSG<i>` and `BKMSG<i>`: version names and compatibility messages as decimal character codes). A writer whose libraries Altium opens is not reported to need it | S-0170, S-0171, S-0173 | INFERRED | H-A-PCB-LIB-OPEN |
| Altium reports "catastrophic failure whilst loading section Library" for a library whose `Library/Data` block holds a short layer stack of about 90 keys, and opens the library once the block holds the whole board record of an Altium-saved library (about 2 000 keys); which keys are the needed ones is not known | S-0173 | INFERRED | H-A-PCB-LIB-OPEN |
| Altium Designer does not open compound files of major version 4 (4096-byte sectors) as libraries; version 3 is needed | S-0173 | INFERRED | H-A-PCB-LIB-OPEN |
| A storage name holds at most 31 characters and none of `/ \ : !` | S-0145 | INFERRED | H-A-PCB-LIB-NAME |
| Version 1 stores a footprint whose name is not a valid storage name under its name cut to 31 characters with `/` replaced by `_`, and writes the root stream `SectionKeys` only then: a 32-bit count, then per keyed footprint its full name (a 32-bit length and the NUL-terminated text, the length counting the NUL) and its storage name (a string block) | S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | INFERRED | H-A-PCB-LIB-NAME |
| `kicad-cli fp upgrade <lib>.PcbLib -o <dir>.pretty` converts a non-KiCad library through the plugin its path selects, on 10.0 and 9.0; the message on failure is only "Unable to convert library" | S-0166, S-0020 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-03) | H-A-PCB-KICAD-LIB |
| `kicad-cli` 10.0.6 converts the PCB library Fenolite writes for the blink sample: three `.kicad_mod` files whose pads, holes, corner ratios, lines, rectangles, arcs and circle equal the source within 10 nm; without `Parameters` a footprint gives no file and exit 0 (`tests/kicad/altium/test_pcblib_oracle.py`, 2026-10-03) | S-0020, S-0166 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-03) | H-A-PCB-KICAD-LIB |
| `kicad-cli` 9.0.9 (pinned image, local run; again in the `kicad-9` job of run https://github.com/lgili/Fenolite/actions/runs/37117800828) converts the same library with the same pads and geometry; it puts Mechanical 13 on `B.Fab` and Mechanical 15 on `Eco2.User`, and exits 2 when a footprint has no `Parameters` | S-0020, S-0166 | INFERRED | H-A-PCB-KICAD-LIB |

## The board record of `Library/Data`

The property block of `Library/Data` is the record of a board without objects. The four Altium-saved
libraries (S-0170, S-0171; saved in 2016, 2019 and 2022) hold the same keys in the same order, apart from
the view keys of the last table; `tests/unit/backends/altium/test_libboard.py` checks each rule.

| fact | source | label | hypothesis |
|---|---|---|---|
| The record starts with `FILENAME` (the path the library was saved to), `KIND=Protel_Advanced_PCB_Library`, `VERSION=3.00`, `DATE` and `TIME` (in the saving machine's locale form) | S-0170, S-0171, S-0173 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-PCB-LIB-OPEN |
| The master stack follows as `V9_MASTERSTACK_STYLE=0`, `_ID` (a GUID in braces), `_NAME=Master layer stack`, `_SHOWTOPDIELECTRIC=FALSE`, `_SHOWBOTTOMDIELECTRIC=FALSE` and `_ISFLEX=FALSE`; S-0173 reports that `VERSION=3.00` needs the `V9_MASTERSTACK` and `V9_STACK_LAYER` keys in the same block | S-0170, S-0171, S-0173 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-PCB-LIB-OPEN |
| The physical stack is `V9_STACK_LAYER<i>_…` for i = 0 … 8, top to bottom: Top Paste, Top Overlay, Top Solder, Top Layer, Dielectric 1, Bottom Layer, Bottom Solder, Bottom Overlay, Bottom Paste. Each layer has `ID` (a GUID), `NAME`, `LAYERID` (its long id) and `USEDBYPRIMS` (`TRUE` when a primitive lies on it) | S-0170, S-0171 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-PCB-LIB-OPEN |
| After those four keys a copper layer adds `COPTHICK=1.4mil` and `COMPONENTPLACEMENT` (1 top, 2 bottom, 0 a mid layer); an internal plane `COPTHICK=1.4mil` and `PULLBACKDISTANCE=20mil`; a dielectric `DIELTYPE=0`, `DIELCONST=4.800`, `DIELHEIGHT=12.6mil` and `DIELMATERIAL=FR-4`; a solder mask `DIELTYPE=3`, `DIELCONST=3.500`, `DIELHEIGHT=0.4mil`, `DIELMATERIAL=Solder Resist` and `COVERLAY_EXPANSION=0mil`; a mechanical layer `MECHENABLED`; any other layer nothing | S-0170, S-0171 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-PCB-LIB-OPEN |
| `V9_CACHE_LAYER<i>_…` for i = 0 … 101 lists every layer with the same keys: Multi-Layer, Connections, Background, DRC Error Markers, DRC Detail Markers, Selections, Visible Grid 1, Visible Grid 2, Pad Holes, Via Holes, Top Pad Master, Bottom Pad Master, the nine layers of the physical stack, Mid-Layer 1 … 30, Internal Plane 1 … 16, Drill Guide, Keep-Out Layer, Mechanical 1 … 16, Drill Drawing, Mechanical 17 … 32. A layer has one GUID in every list | S-0170, S-0171 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-PCB-LIB-OPEN |
| The same master-stack keys repeat as `LAYERMASTERSTACK_V8<KEY>`, and `LAYER_V8_<i><KEY>` for i = 0 … 55 lists (keys joined without `_`) the physical stack, Drill Guide, Keep-Out Layer, Mechanical 1 … 16, Drill Drawing, Multi-Layer, Connections, Background, DRC Error Markers, Selections, Visible Grid 1, Visible Grid 2, Pad Holes, Via Holes, Top Pad Master, Bottom Pad Master, DRC Detail Markers and Mechanical 17 … 32 | S-0170, S-0171 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-PCB-LIB-OPEN |
| Then `TOPTYPE=3`, `TOPCONST=3.500`, `TOPHEIGHT=0.4mil`, `TOPMATERIAL=Solder Resist`, the same four keys for `BOTTOM`, `LAYERSTACKSTYLE=0`, `SHOWTOPDIELECTRIC=FALSE` and `SHOWBOTTOMDIELECTRIC=FALSE` | S-0170, S-0171 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-PCB-LIB-OPEN |
| Then the numbered layers `LAYER<n>…` for n = 1 … 82 (ids 1 to 74 of `pcb-records.md`, then 75 Connections, 76 Background, 77 DRC Error Markers, 78 Selections, 79 Visible Grid 1, 80 Visible Grid 2, 81 Pad Holes, 82 Via Holes), each with `NAME`, `PREV`, `NEXT`, `MECHENABLED`, `COPTHICK=1.4mil`, `DIELTYPE=0`, `DIELCONST=4.800`, `DIELHEIGHT=12.6mil` and `DIELMATERIAL=FR-4`. `PREV`/`NEXT` are 0/32 for layer 1, 1/0 for layer 32, 0/1 for 33, 35 and 37, 32/0 for 34, 36 and 38, and 0/0 otherwise. The layers come five at a time, and a field `RECORD=Board` stands before every group but the first. One CR (byte 0x0D, no LF) stands before each of these `RECORD=Board` fields and before every later one, except the one that opens the view keys after the layer sets: the record is 25 lines, each after the first starting with `\|RECORD=Board`; no other byte of the block lies outside printable 7-bit ASCII in a library saved to an ASCII path | S-0170, S-0171 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-PCB-LIB-OPEN |
| Then `LAYERV7_<i>…` for i = 0 … 15 (Mechanical 17 … 32): `LAYERID` (the long id), `NAME`, `PREV=16973824`, `NEXT=16973824`, `MECHENABLED` and the same five thickness and dielectric keys | S-0170, S-0171 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-PCB-LIB-OPEN |
| Then `RECORD=Board` and the grid: `BIGVISIBLEGRIDSIZE=0.000`, `VISIBLEGRIDSIZE=0.000`, `SNAPGRIDSIZE`, `SNAPGRIDSIZEX`, `SNAPGRIDSIZEY` (binary units with six decimals), `ELECTRICALGRIDRANGE=8mil`, `ELECTRICALGRIDENABLED`, `DOTGRID`, `DOTGRIDLARGE`, `DISPLAYUNIT=0`, `TOGGLELAYERS` (82 digits, 1 for a shown layer) and `SHOWDEFAULTSETS=TRUE` | S-0170, S-0171 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-PCB-LIB-OPEN |
| Then `LAYERSETSCOUNT=5` and, for n = 1 … 5, `LAYERSET<n>NAME`, `LAYERS` (names without spaces, comma separated), `ACTIVELAYER.7`, `ISCURRENT=FALSE`, `ISLOCKED=TRUE` and `FLIPBOARD=FALSE`. The sets are `&All Layers` (Multi-Layer, top paste, overlay and solder, both copper layers, bottom solder, overlay and paste, Drill Guide, Keep-Out, the enabled mechanical layers, Drill Drawing; active `TOP`), `&Signal Layers` (Multi-Layer and both copper layers; `TOP`), `&Plane Layers` (none; `UNKNOWN`), `&NonSignal Layers` (the first set without copper and mechanical layers; `MULTILAYER`) and `&Mechanical Layers` (the enabled mechanical layers; the first of them) | S-0170, S-0171 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-PCB-LIB-OPEN |
| The record ends with the view keys of the next table, each group opened by `RECORD=Board`, then `BOARDVERSION=5.01` and four empty keys `VAULTGUID`, `FOLDERGUID`, `LIFECYCLEDEFINITIONGUID` and `REVISIONNAMINGSCHEMEGUID` | S-0170, S-0171 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-PCB-LIB-OPEN |

### Long layer ids

| fact | source | label | hypothesis |
|---|---|---|---|
| A long layer id is a 32-bit number written in decimal: `0x01000000 + n` for copper layer n (1 the top, 2 … 31 the mid layers) and `0x0100FFFF` for the bottom; `0x01010000 + n` for internal plane n; `0x01020000 + n` for mechanical layer n (1 … 32); `0x01040000 + n` for dielectric n | S-0170, S-0171 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-PCB-LIB-OPEN |
| The other layers are `0x01030000 + k`: 6 Top Overlay, 7 Bottom Overlay, 8 Top Paste, 9 Bottom Paste, 10 Top Solder, 11 Bottom Solder, 12 Drill Guide, 13 Keep-Out Layer, 14 Drill Drawing, 15 Multi-Layer, 16 Connections, 17 Background, 18 DRC Error Markers, 19 Selections, 20 Visible Grid 1, 21 Visible Grid 2, 22 Pad Holes, 23 Via Holes, 24 Top Pad Master, 25 Bottom Pad Master, 26 DRC Detail Markers; `0x01030000` itself stands for no layer | S-0170, S-0171 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-PCB-LIB-OPEN |

### View keys

A library saved in the 2D view holds the keys below; one saved in the 3D view holds `CFG3D.` keys in place
of the `CFG2D.` ones. They are editor state, not design data.

| fact | source | label | hypothesis |
|---|---|---|---|
| After the layer sets: `RECORD=Board`, `CFGALL.CONFIGURATIONKIND=1`, `CFGALL.CONFIGURATIONDESC=Altium%20Standard%202D`, `CFG2D.PRIMDRAWMODE` (23 zeros), then `CFG2D.LAYEROPACITY.<LAYER>` for the 82 numbered layers (`TOPLAYER`, `MIDLAYER1` … `30`, `BOTTOMLAYER`, `TOPOVERLAY`, `BOTTOMOVERLAY`, `TOPPASTE`, `BOTTOMPASTE`, `TOPSOLDER`, `BOTTOMSOLDER`, `INTERNALPLANE1` … `16`, `DRILLGUIDE`, `KEEPOUTLAYER`, `MECHANICAL1` … `16`, `DRILLDRAWING`, `MULTILAYER`, `CONNECTLAYER`, `BACKGROUNDLAYER`, `DRCERRORLAYER`, `HIGHLIGHTLAYER`, `GRIDCOLOR1`, `GRIDCOLOR10`, `PADHOLELAYER`, `VIAHOLELAYER`), each 23 values ended by `;`: sixteen `1.00`, one `0.40`, six `1.00` | S-0170 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-PCB-LIB-OPEN |
| Then `CFG2D.TOGGLELAYERS` (82 ones) and `CFG2D.TOGGLELAYERS.SET`: for the groups `Signal` (copper 1 … 31 and bottom), `Mechanical` (1 … 16), `Internal` (planes 1 … 16) and `Standard` (`0x01030000 + 26`, then `+ 6` … `+ 23`), the text `<Group>.All~0_<Group>.Include~SerializeLayerHash.Version=2,ClassName=TLayerHash,` and `<long id>=1` per layer, comma separated; the groups joined by `_`, ended by `_Dielectric.All~0` | S-0170 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-PCB-LIB-OPEN |
| Then `CFG2D.WORKSPACECOLALPHA<i>=1.0` for i = 0 … 11, 13 and 14 (the library of 2019; that of 2016 stops at 6), `CFG2D.MECHLAYERINSINGLELAYERMODE` and `CFG2D.MECHLAYERLINKEDTOSHEET` (16 zeros each, each followed by its `.SET` key `SerializeLayerHash.Version~2,ClassName~TLayerToBoolean,25165826~0`), `CFG2D.CURRENTLAYER` and 23 display switches and colours with fixed default values | S-0170 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-PCB-LIB-OPEN |
| Then `BOARDINSIGHTVIEWCONFIGURATIONNAME` (empty), `VISIBLEGRIDMULTFACTOR=1.000`, `BIGVISIBLEGRIDMULTFACTOR=5.000`, and one group each for `CURRENT2D3DVIEWSTATE` (`2D` or `3D`); the window `VP.LX`, `VP.HX`, `VP.LY`, `VP.HY` (binary units; the library origin lies at 50 000 mil in both axes); `2DCONFIGTYPE=.config_2dsimple` and `2DCONFIGURATION`; `2DCONFIGFULLFILENAME`; `3DCONFIGTYPE=.config_3d` and `3DCONFIGURATION`; `3DCONFIGFULLFILENAME` (`(Not Saved)` for none) | S-0170, S-0171 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-PCB-LIB-OPEN |
| `2DCONFIGURATION` and `3DCONFIGURATION` hold a view configuration as one value: `RECORD=Board` and the `CFGALL.` and `CFG2D.` (or `CFG3D.`) fields, each opened by a backtick in place of `\|`, every `;` written `?`. `2DCONFIGURATION` holds exactly the `RECORD=Board` group of view keys written after the layer sets. `3DCONFIGURATION` holds `CFGALL.CONFIGURATIONKIND=3`, a default description and 37 `CFG3D.` switches, colours and opacities | S-0170 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-PCB-LIB-OPEN |
| The last group holds the 3D camera (`LOOKAT.X/Y/Z`, `EYEROTATION.X/Y/Z`, `ZOOMMULT`, `VIEWSIZE.X/Y`), the snap options (`EGRANGE=8mil`, `EGMULT`, `EGENABLED`, `EGSNAPTOBOARDOUTLINE`, `EGSNAPTOARCCENTERS`, `EGUSEALLLAYERS`, `OGSNAPENABLED`, `MGSNAPENABLED`, `POINTGUIDEENABLED`, `GRIDSNAPENABLED`, `NEAROBJECTSENABLED`, `FAROBJECTSENABLED`, `NEAROBJECTSET` and `FAROBJECTSET` of 27 digits, `NEARDISTANCE`) and the closing keys of the record | S-0170, S-0171 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-PCB-LIB-OPEN |

## Version 2 not used

AltiumSharp version 2 (2026) cites a decompilation folder that is not public, so no fact found only in
version 2 is used (`LEGAL.md` P1). The streams once listed here as known from version 2 alone
(`FileVersionInfo`, `Library/LayerKindMapping`, `Library/PadViaLibrary`, `Library/ComponentParamsTOC`,
`Library/Textures`, `ModelsNoEmbed`, the longer `FileHeader`) are now stated above from Altium-saved
libraries under MIT and GPL-2.0 (S-0170, S-0171) and from S-0173; version 2 is still not a source.

The PcbDoc `FileHeader` form also appears in version 2, but Fenolite takes it from the MIT writer S-0143,
an independent source (`pcb-document.md`).

## Fenolite's choices

- One `<design>.PcbLib` holds every KiCad footprint of the design (`project.pcblib_name`), beside c0034's
  `<design>.SchLib`; Altium footprint links (`<X>.PcbLib:<name>`) get no footprint.
- The root holds `FileHeader`, `SectionKeys` only when a storage name differs from its footprint name,
  `Library`, then one storage per footprint in the MS-CFB order of storage names. `Library` holds `Header`,
  `Data`, `EmbeddedFonts`, `Models`, `ModelsNoEmbed`, `Textures`, `ComponentParamsTOC` and `PadViaLibrary`.
  `FileVersionInfo` and `LayerKindMapping` are not written (`H-A-PCB-LIB-OPEN`).
- The id of `FileHeader` is `project.unique_id("pcblib:<file name>")`; the GUIDs of the board record and of
  `PadViaLibrary` are the first 16 bytes of the SHA-256 of `fenolite.altium.guid:<key>` (`layer:<long id>`,
  `masterstack`, `padvia:<file name>`), so equal inputs give equal bytes.
- The board record is written whole by `libboard.board_text`: `FILENAME` is the library's file name
  without a folder, `DATE=2000-01-01` and `TIME=00:00:00` are fixed, Mechanical 13 to 16 (Fenolite's
  layer map) are the enabled mechanical layers, `USEDBYPRIMS` is `TRUE` for the layers the written
  primitives lie on, the snap grid is 5 mil, the view is the 2D one with the window ± 100 mil around the
  origin, and both configuration file names are `(Not Saved)`.
- `ComponentParamsTOC/Data` of a library without footprints is the block of the NUL alone.
- Storage names come from c0034's `project.storage_name`; two footprints with one storage name are
  refused.
- `Parameters` holds `PATTERN`, `HEIGHT=0mil`, `DESCRIPTION` (empty when there is none or when it is not
  printable 7-bit ASCII), `ITEMGUID` and `REVISIONGUID` (empty); `WideStrings` is an empty property block (only the NUL); `Data` holds the pads in definition
  order, then the tracks and arcs in graphic order; `UNIQUEID` is `project.unique_id("pcblib:<name>:<i>")`
  with `i` the zero-based primitive index.
