## MODIFIED Requirements

### Requirement: PCB document links and nets
Each component record SHALL link to the schematic, and each pad SHALL carry its net (S-0161, S-0164, S-0139, S-0188).
- `SOURCEUNIQUEID` MUST be a backslash followed by the component's schematic `UNIQUEID` (`project.unique_id(<component id>)`); `SOURCEDESIGNATOR` its ref; `PATTERN` its footprint name; `SOURCEFOOTPRINTLIBRARY` the file name of the PCB library it comes from; `SOURCELIBREFERENCE` and `SOURCECOMPONENTLIBRARY` the schematic's `LIBREFERENCE` and `SOURCELIBRARYNAME` (`H-A-PCB-DOC-LINK`).
- For a component on a module sheet (`pcbdoc.PlacedComponent.sheet` is `(<sheet symbol UNIQUEID>, <module name>)`; `altium-schematic-writer`, "Sheets of a hierarchical project"), `SOURCEUNIQUEID` MUST instead be `\<sheet symbol UNIQUEID>\<component UNIQUEID>` and `SOURCEHIERARCHICALPATH` MUST be `<design name>\<module name>`, as Altium saves them (S-0188). For any other component `PlacedComponent.sheet` is `None`, `SOURCEUNIQUEID` keeps the one-id form and `SOURCEHIERARCHICALPATH` is empty, as c0035 writes them. That the change order matches both forms is `H-A-SCH-HIER-ECO`.
- `CHANNELOFFSET` MUST be the component's index among the components of its own sheet, in component-path order, starting at 0 on every module sheet and on the top sheet, as a saved board of a hierarchical project holds it (S-0188; `pcbdoc.channel_offsets`). In a `flat` build this is the component's index in the document, so the bytes of c0035 do not change.
- The test suite MUST read a built project back as a second program finds it (`tests/_altium_read.py`, `component_links` and `board_link_problems`): the sheets are the `.SchDoc` documents the project file lists; a sheet symbol's file-name record names its child by the exact name of a listed document; every module sheet MUST be reachable from the top sheet; and every board component's `SOURCEUNIQUEID`, designator and `SOURCEHIERARCHICALPATH` MUST be those of one schematic component. A module MUST get its sheet symbol even when no net crosses it. This readback raises no evidence label.
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

#### Scenario: Every board link resolves
- **WHEN** `examples/altium_hier_board/design.py` is built with `sheets="modules"` and `component_links` and `board_link_problems` read its project file, sheets and PCB document
- **THEN** there is no problem: the links of `R1` and `U1` resolve through the sheet symbol `driver` and that of `D1` through the sheet symbol `led`, both module sheets are listed in the project file and reachable from the top sheet, and `CHANNELOFFSET` is `0` and `1` on `driver` and `0` on `led`

#### Scenario: A sheet outside the hierarchy is caught
- **GIVEN** that build with the section of `altium_hier_board_led.SchDoc` removed from the project file, or with the top sheet replaced by one without sheet symbols
- **WHEN** `component_links` runs
- **THEN** it fails, naming the sheet

#### Scenario: Module without a crossing
- **GIVEN** a design of two modules whose only nets are the two nets of a `power` interface
- **WHEN** it is built with `sheets="modules"`
- **THEN** the top sheet holds one sheet symbol per module, each with its name and file name and no sheet entry, and both module sheets are reachable from the top sheet

#### Scenario: Flat links are unchanged
- **WHEN** the same example is built with `sheets="flat"`
- **THEN** every component holds `SOURCEUNIQUEID` equal to `\` and its schematic `UNIQUEID`, and an empty `SOURCEHIERARCHICALPATH`
