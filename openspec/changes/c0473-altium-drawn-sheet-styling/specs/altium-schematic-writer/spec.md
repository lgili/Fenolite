# Delta for altium-schematic-writer

## MODIFIED Requirements

### Requirement: Drawn sheets in Altium
`fenolite.backends.altium.drawn.lower_drawn` SHALL write one sheet per drawn sheet instance: wires and buses as polylines, junctions, local labels as net labels, hierarchical labels as ports, references as sheet symbols with sheet entries, power symbols and global labels as power ports of their text, bus entries and no-connect directives. A repeated sheet MUST be written once per instance with `drawn.altium-repeat-flattened` (info). When a sheet carries `Fenolite.Altium.Sheet` records and fields (from an Altium conversion or import), `lower_drawn` SHALL restore the sheet's `RECORD=31` font table and background colour, `RECORD=39` template graphics, port dimensions and colours, net-label justifications and colours, sheet-symbol colours and non-overlapping `SheetName`/`SheetFileName` poses and fonts, and component body graphics and field font ids.

#### Scenario: Carried Altium styling restored without overlap
- **GIVEN** an Altium schematic with a multi-font `RECORD=31`, a `Template` (`RECORD=39`), a sized `Port` (`RECORD=18`), a right-justified `NetLabel` (`RECORD=25`), a `SheetSymbol` (`RECORD=15`) with separated `SheetName` (`RECORD=32`) and `SheetFileName` (`RECORD=33`), and coloured component body graphics
- **WHEN** it is imported to Python or converted to KiCad and built or converted back to Altium
- **THEN** the written `.SchDoc` preserves the `RECORD=31` fonts and `AREACOLOR`, the `Template` graphics, the port's `WIDTH` and colours, the net label's `JUSTIFICATION`, the separated `SheetName` and `SheetFileName` locations, and the component body graphics
