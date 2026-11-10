# Delta for altium-schematic-writer

## MODIFIED Requirements

### Requirement: Designator, comment and links
Each component SHALL carry its designator, its comment, its library link and, when it has one, its footprint link.
- Designator record: `RECORD=34`, `OWNERINDEX`, `OWNERPARTID=-1`, `NAME=Designator`, `TEXT=<ref>`, `LOCATION.X`, `LOCATION.Y` (100 mil above the body's top-left corner), `FONTID=1`, `COLOR=8388608` (S-0130, S-0131).
- Comment record: `RECORD=41` with the same keys, `NAME=Comment` and `TEXT=<value>`, 200 mil below the body's bottom-left corner. An empty value MUST give the symbol name as the comment (S-0130, S-0137).
- Library link: `lib_id` `<library>:<name>` MUST give `LIBREFERENCE=<name>`, `DESIGNITEMID=<name>` and `SOURCELIBRARYNAME=<project.schlib_name(lib_id, design=<design name>)>`: the library itself for an Altium link, and `<design name>.SchLib` for a KiCad lib id, the library file that the build writes (S-0002, S-0130, S-0137; "Library and storage names"). That "Tools » Update From Libraries" follows these keys is `H-A-SCH-UPDATE`.
- Footprint link: the component's footprint link `<library>:<name>` (its `footprint`, or the symbol's `Footprint` property, `altium-build` "Altium symbol sources") MUST give, after the component's other children, `RECORD=44` (`OWNERINDEX` = the component), then `RECORD=45` (`OWNERINDEX` = the record 44, `MODELNAME=<name>`, `MODELTYPE=PCBLIB`, `DATAFILECOUNT=1`, `MODELDATAFILEENTITY0=<name>`, `MODELDATAFILEKIND0=PCBLIB`, `MODELDATAFILE0=<project.pcblib_name(link, design=<design name>)>`, `ISCURRENT=T`), then `RECORD=46` and `RECORD=48`, each with `OWNERINDEX` = the record 45 (S-0130, S-0131, S-0135, S-0144, S-0150). That Altium reads `MODELDATAFILE0` as the "Library name" mode is `H-A-SCH-LINK`.
- Every owner index of the chain SHALL name the record as written, also when the component's carried body graphics replace its template's own body records with a different number of records (change c0473): the writer SHALL resolve each template owner through the records it actually wrote, and SHALL fail (`FormatError`) when a template owner names a record it did not write.
- `MODELDATAFILE0` MUST follow the link's form, not the build's outcome: the library itself for an Altium link (`.PcbLib` in any letter case), and `<design name>.PcbLib` for a KiCad footprint link, whether or not that footprint is written (`altium-pcb-writer`, "PCB library name"). The schematic bytes therefore never depend on the content of a footprint library.
- A component without footprint MUST have no record 44, 45, 46 or 48.

#### Scenario: Links of the sample's J1
- **WHEN** the records of the sample's `J1` are read
- **THEN** its component record holds `LIBREFERENCE=HDR2`, `DESIGNITEMID=HDR2` and `SOURCELIBRARYNAME=FenoliteSample.SchLib`, and its record 45 holds `MODELNAME=HDR1X2`, `MODELTYPE=PCBLIB`, `DATAFILECOUNT=1`, `MODELDATAFILEENTITY0=HDR1X2`, `MODELDATAFILEKIND0=PCBLIB`, `MODELDATAFILE0=FenoliteSample.PcbLib` and `ISCURRENT=T`

#### Scenario: Ownership chain
- **WHEN** the owners of the sample's records 44, 45, 46 and 48 are followed
- **THEN** every record 44 is owned by a component, every record 45 by the record 44 just before it, and every record 46 and 48 by that record 45

#### Scenario: Owners behind a carried body
- **GIVEN** a part whose carried body graphics (`comp_gfx`) differ in count from the template's own body (including a `RECORD=4` label and a `RECORD=6` polyline) and whose footprint link is set
- **WHEN** the project is built with `build --target altium`
- **THEN** the part's record 45 names the record 44 just before it, its records 46 and 48 name that record 45, and no owner of the chain names a parameter or pin record

#### Scenario: Empty value and no footprint
- **GIVEN** a part `X1` with `lib_id="L.SchLib:SYM"`, no value and no footprint
- **WHEN** it is written
- **THEN** its comment record holds `TEXT=SYM`, and no record 44 is owned by it

#### Scenario: Links of a KiCad lib id
- **GIVEN** a part with `lib_id="Device:R"` in a design named `board`
- **WHEN** it is written
- **THEN** its component record holds `LIBREFERENCE=R`, `DESIGNITEMID=R` and `SOURCELIBRARYNAME=board.SchLib`

#### Scenario: Links of a KiCad footprint
- **GIVEN** the part `R1` of `examples/blink_2layer/design.py`, with `footprint="Mini:Mini_R_0603"`, in the design `blink`
- **WHEN** it is written
- **THEN** its record 45 holds `MODELNAME=Mini_R_0603`, `MODELDATAFILEENTITY0=Mini_R_0603` and `MODELDATAFILE0=blink.PcbLib`

#### Scenario: Unresolved KiCad footprint keeps its link
- **GIVEN** a part with `footprint="Nowhere:X"` in a design named `board`, whose library does not resolve
- **WHEN** it is written
- **THEN** its record 45 holds `MODELNAME=X` and `MODELDATAFILE0=board.PcbLib`
