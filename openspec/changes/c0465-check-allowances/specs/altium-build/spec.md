## MODIFIED Requirements

### Requirement: Scope of the acceptance project
The acceptance project SHALL use every item that the written scope lists: a stack of six copper layers, blind and buried vias, board texts, a keep-out, a non-plated hole, bodies, polygons, rules of every exact kind of the v0.3 written scope, a module tree two levels deep, a bus, an output job and a drawing sheet. The kinds `short` and `antenna`, exact since change c0465, are outside that scope: the project of v0.3 authors neither, and its bytes stay those of v0.3.

#### Scenario: Every written item is used
- **WHEN** the acceptance project is built for Altium
- **THEN** each item of the written scope appears in the written documents

#### Scenario: The kinds of change c0465 are outside the acceptance scope
- **WHEN** `tools/acceptance_v03.py` lists the exact rule kinds the project must use
- **THEN** the list holds every exact kind of `rulemap.TABLE` but `short` and `antenna`
