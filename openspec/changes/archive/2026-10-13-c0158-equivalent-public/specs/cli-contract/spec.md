## ADDED Requirements

### Requirement: Levels and sides of equivalent in capabilities
The `equivalent` entry of `result.commands` of `fenolite capabilities` SHALL hold, besides the keys of every entry, `levels` (the list `LEVELS` of `fenolite.checks.equivalence`) and `sides` (the side kinds the command reads, sorted: `altium_pcbdoc`, `altium_prjpcb`, `altium_schdoc`, `fenolite_model`, `kicad_pcb`, `kicad_pro`, `kicad_sch`). No other entry gains these keys.

#### Scenario: Levels and sides listed
- **WHEN** `uv run fenolite capabilities --json --no-tools` runs
- **THEN** the entry named `equivalent` has `levels` `[1, 2, 3, 4, 5]` and `sides` holding `kicad_sch`
