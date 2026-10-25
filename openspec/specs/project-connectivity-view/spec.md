# project-connectivity-view Specification

## Purpose
A sheet of an Altium project shows its nets as the project compiles them across sheets, so a net selected on one sheet, on another or on the board is the same net (change c0185).

## Requirements

### Requirement: Project nets on sheets
For an Altium project the schematic scenes SHALL name each local net by its project net, compiled across the project's sheets by ports, sheet entries, power ports and net labels as the project's scope says.

#### Scenario: A net through a port
- **GIVEN** the hierarchical test project `tests/data/altium/hier` whose net crosses two sheets through a port
- **WHEN** `uv run pytest tests/unit/view/test_project_nets.py` builds both sheets
- **THEN** the net has the same project name on both sheets and lists the pins of both
