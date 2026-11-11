# Delta for altium-schematic-writer

## ADDED Requirements

### Requirement: Carried project settings
When the drawing of an Altium project is read for a conversion or an import, the settings of its `.PrjPcb`
(every section but `Document<n>` and `GeneratedDocument<n>`, and `[Design]` without `Version`) SHALL ride in
the root sheet's `Fenolite.Altium.Sheet` carrier, field `PRJPCB` of the key `project`, and the `.PrjPcb`
written from that drawing (`build --target altium`, `convert --to altium`) SHALL hold them:
`write_prjpcb(..., carried=...)` replaces a written `[Design]` key by the carried one of that name, writes
the other carried `[Design]` keys after it, puts the carried sections of a family the writer writes in place
of the written ones, and appends every other carried section in carried order. The `UniqueId` of each
`Variation<n>` of a carried `[ProjectVariant<n>]` SHALL name the written component of its `Designator`: the
unique ids of its sheet symbols from the top sheet and its own, each after a backslash. A project without
carried settings keeps its bytes.

#### Scenario: Net options survive a round trip
- **GIVEN** an Altium project whose `[Design]` holds `AllowSheetEntryNetNames=0` and which has an
  `[Electrical Rules Check]` section and a `[Parameter1]`
- **WHEN** it is imported to Python and built with `--target altium`, or converted to KiCad and back
- **THEN** the written `.PrjPcb` holds `AllowSheetEntryNetNames=0` in `[Design]`, the
  `[Electrical Rules Check]` section, and the source's `[Parameter1]` in place of a written one

#### Scenario: A net label of an Altium source comes back as a net label
- **GIVEN** an Altium sheet with a port `+5V` and a net label `+5V`, converted to KiCad
- **WHEN** the KiCad project is converted back with `convert --to altium`
- **THEN** the written sheet holds the port and the net label `+5V` (`RECORD=25`), and a local label of a
  KiCad source that shares its text with a hierarchical label is still written as a port

#### Scenario: A variant names the written component
- **GIVEN** carried settings with `[ProjectVariant1]` and `Variation1=Designator=R1|UniqueId=\SOURCEID|Kind=1`
- **WHEN** a drawn design with `R1` is built with `--target altium`
- **THEN** the written `Variation1` names `R1` by the `UNIQUEID` its written component record holds

#### Scenario: Merge
- **WHEN** `write_prjpcb(schematic="a.SchDoc", parameters=(("Title", "x"),), carried="[Design]\nHierarchyMode=0\n[Parameter1]\nName=Rev\nValue=A\n")` is called
- **THEN** `[Design]` holds `Version=1.0` then `HierarchyMode=0`, and the only parameter section is
  `[Parameter1]` with `Name=Rev` and `Value=A`
