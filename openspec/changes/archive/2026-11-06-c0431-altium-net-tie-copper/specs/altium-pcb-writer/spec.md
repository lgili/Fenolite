## ADDED Requirements

### Requirement: Copper of a net-tie footprint

The Altium writer SHALL write each copper graphic of a footprint instance with net-tie groups as a primitive
of its component on the graphic's signal layer, without a net: a line as a track, an arc or a circle as an
arc, a filled rectangle or polygon as a region, a rectangle or polygon outline as tracks. It SHALL count each
under `footprint-copper` as written. A copper graphic of a footprint without net-tie groups, one on an
internal plane, and one that `pcbdoc.graphic_problem` refuses SHALL stay a `footprint-copper` loss.

#### Scenario: A net tie keeps its copper

- **GIVEN** the authored board `net_tie_copper.kicad_pcb`, whose net tie `NT1` holds an F.Cu line from pad 1
  (net `A`) to pad 2 (net `B`)
- **WHEN** it is converted to Altium without `--allow-lossy`
- **THEN** the conversion succeeds with no `footprint-copper` loss and nothing unexplained
- **AND** the PcbDoc holds one track on the top layer with the component's index and no net, and the
  component record holds `COMPONENTKIND=4`

#### Scenario: Copper no record holds stays refused

- **GIVEN** the same board with a filled circle on F.Cu in place of the line
- **WHEN** it is converted to Altium
- **THEN** the conversion is refused for a `footprint-copper` loss, and with `--allow-lossy` the
  `net-tie-copper` difference it causes is explained by that row
