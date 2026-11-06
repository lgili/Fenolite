## MODIFIED Requirements

### Requirement: Connector and free pads
A pad of kind `connect` SHALL be written as a surface pad whose paste and solder-mask expansions remove both openings. A pad without a number inside a footprint SHALL be written as a pad of that footprint with an empty designator, in the PCB document and in the derived library, as documents saved by Altium hold component pads without a name (`pcb-records.md`, "Pad": census of S-0172, S-0200, S-0601). Each such pad MUST be its own record with its own net, so several pads without a number in one footprint stay distinct; a pad that a writer cannot hold MUST be counted `lost` under `pad` with its reason.

#### Scenario: Connector pad
- **GIVEN** a footprint with one `connect` pad
- **WHEN** the board is written and read back
- **THEN** the pad is a surface pad on its copper layer with no paste and no mask opening, and the report has no lost `pad`

#### Scenario: Two pads without a number
- **GIVEN** a KiCad footprint with pads `1` and `2`, a surface pad without a number on the net of pad `1` and a non-plated hole pad without a number
- **WHEN** it is converted to Altium with `allow_lossy=True` and the PCB document and the derived library are read back
- **THEN** the row `pad` has `written` equal to `source` and no `changed` or `lost` item, the footprint read back holds four pads, two of them without a number at their own places, the surface one on its net, the library footprint holds four pads, and the comparison of the conversion holds no `pad-missing` and no `ref-ambiguous`
