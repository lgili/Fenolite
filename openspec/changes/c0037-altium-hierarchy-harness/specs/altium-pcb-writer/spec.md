## MODIFIED Requirements

### Requirement: PCB document links and nets
Each component record SHALL link to the schematic, and each pad SHALL carry its net (S-0161, S-0164, S-0139, S-0188).
- `SOURCEUNIQUEID` MUST be a backslash followed by the component's schematic `UNIQUEID` (`project.unique_id(<component id>)`); `SOURCEDESIGNATOR` its ref; `PATTERN` its footprint name; `SOURCEFOOTPRINTLIBRARY` the file name of the PCB library it comes from; `SOURCELIBREFERENCE` and `SOURCECOMPONENTLIBRARY` the schematic's `LIBREFERENCE` and `SOURCELIBRARYNAME` (`H-A-PCB-DOC-LINK`).
- For a component on a module sheet (`pcbdoc.PlacedComponent.sheet` is `(<sheet symbol UNIQUEID>, <module name>)`; `altium-schematic-writer`, "Sheets of a hierarchical project"), `SOURCEUNIQUEID` MUST instead be `\<sheet symbol UNIQUEID>\<component UNIQUEID>` and `SOURCEHIERARCHICALPATH` MUST be `<design name>\<module name>`, as Altium saves them (S-0188). For any other component `PlacedComponent.sheet` is `None`, `SOURCEUNIQUEID` keeps the one-id form and `SOURCEHIERARCHICALPATH` is empty, as c0035 writes them. That the change order matches both forms is `H-A-SCH-HIER-ECO`.
- A pad whose number equals a pin designator of its component on a net MUST carry that net's index; any other pad MUST carry `0xFFFF`. Every primitive MUST carry its component's index.

#### Scenario: Unique ids match the schematic
- **WHEN** the sample's schematic and PCB document are read
- **THEN** for every component, `SOURCEUNIQUEID` equals `\` followed by the `UNIQUEID` of the schematic component with the same designator

#### Scenario: Pad nets
- **WHEN** the pads of the sample's `R1` are read
- **THEN** pad `1` carries the index of `LED_DRV` and pad `2` the index of `LED_A`

#### Scenario: Link of a part on a module sheet
- **WHEN** `examples/altium_hier_board/design.py` is built with `sheets="modules"` and its PCB document and sheets are read
- **THEN** the component `D1` holds `SOURCEUNIQUEID` equal to `\`, the `UNIQUEID` of the sheet symbol `led`, `\` and the `UNIQUEID` of the schematic component `D1`, and `SOURCEHIERARCHICALPATH=altium_hier_board\led`

#### Scenario: Flat links are unchanged
- **WHEN** the same example is built with `sheets="flat"`
- **THEN** every component holds `SOURCEUNIQUEID` equal to `\` and its schematic `UNIQUEID`, and an empty `SOURCEHIERARCHICALPATH`
