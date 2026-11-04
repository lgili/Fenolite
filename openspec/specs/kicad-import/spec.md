# kicad-import Specification

## Purpose
TBD - created by archiving change c0342-source-footprint-alias. Update Purpose after archive.
## Requirements
### Requirement: Native source footprint aliases retain exact physical binding
Import SHALL preserve a nonempty original schematic Footprint alias using exact
source file/symbol UUID/use-path/ref identity when its basename agrees with the
physical board footprint. The local vendored alias SHALL resolve to the exact
board-derived geometry. No comparator or arbitrary text override may hide a
change of pads, names, source binding or physical definition.

#### Scenario: Visible namespace-only alias
- **WHEN** an authored symbol declares Original:Mini_R and its physical board uses Board:Mini_R
- **THEN** imported code and visible schematic text retain Original:Mini_R
- **AND** local resolution uses the original board-exact geometry with unchanged pads, refs and paths
- **AND** levels3/S/8 and native connectivity agree

#### Scenario: Ambiguous or incompatible alias
- **WHEN** one exact definition lookup binds incompatible physical bytes or inconsistent unit declarations
- **THEN** import refuses before staging writes
- **WHEN** physical and declared basenames genuinely differ
- **THEN** no normalization makes level3 falsely equal

#### Scenario: Edited instances behind one logical alias
- **WHEN** two board instances have exact source-derived variants behind the same logical schematic alias
- **THEN** footprint preserves that alias and footprint_definition selects each distinct local variant
- **AND** original pad edits, field poses and native ordering remain unchanged
- **AND** a true collision on one exact definition lookup still refuses before staging

#### Scenario: Inconsistent visible physical identity is refused early
- **WHEN** a visible source Footprint declaration names a genuinely different basename from the physical board
- **THEN** FEN-3004 locates the component/Footprint contradiction before any plan or target write
- **AND** source bytes are unchanged; no arbitrary text override or level8 ignore makes it pass

