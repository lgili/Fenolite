## ADDED Requirements

### Requirement: Experimental notice per kind
`fenolite build --target altium` SHALL report `altium.experimental` (info) once, naming the kinds it wrote whose write is experimental in the evidence matrix, and SHALL NOT report it when no written kind is experimental.
- The envelope evidence MUST be the lowest level of the write cells of the kinds written, combined with the evidence of the inputs; it MUST NOT be fixed at `INFERRED`.

#### Scenario: All kinds graduated
- **GIVEN** a tree in which every Altium write kind graduated
- **WHEN** the blink is built for Altium
- **THEN** no `altium.experimental` is reported, and the envelope level is the lowest level of the kinds written

#### Scenario: One kind still experimental
- **GIVEN** a tree in which the harness kind is experimental
- **WHEN** a design with a typed interface is built with module sheets
- **THEN** `altium.experimental` names `altium_harness` only

### Requirement: Altium acceptance project
The repository SHALL hold an acceptance project for the second backend's write side and a script `tools/acceptance_v03.py` that builds it for KiCad and for Altium, runs `fenolite check` on both, compares the two at level 5 of `equivalent`, runs `fenolite roundtrip --level rta3` on the Altium project, and compares the KiCad board with KiCad's import of the Altium documents at level 5.

#### Scenario: Acceptance run
- **WHEN** `uv run pytest tests/kicad/acceptance/test_v03_acceptance.py -rA` runs with KiCad 10.0.6
- **THEN** every step of the script passes, and the probe `acceptance-v03` records `equal`

### Requirement: Scope of the acceptance project
The acceptance project SHALL use every item that the written scope lists: a stack of six copper layers, blind and buried vias, board texts, a keep-out, a non-plated hole, bodies, polygons, rules of every exact kind, a module tree two levels deep, a bus, an output job and a drawing sheet.

#### Scenario: Every written item is used
- **WHEN** the acceptance project is built for Altium
- **THEN** each item of the written scope appears in the written documents

### Requirement: Record of the acceptance runs
`docs/evidence/altium-acceptance.md` SHALL record each run of `tools/acceptance_v03.py` with the versions of Fenolite, KiCad and Altium, the result of each step, and the id of the kit run made on the same tree.

#### Scenario: A run is recorded
- **WHEN** the acceptance script has run on a tree
- **THEN** the page holds a row with the three versions, each step's result and the kit run id, or says that no kit run was made on that tree

## MODIFIED Requirements

### Requirement: Altium build evidence
The Altium `build` envelope SHALL combine the write evidence of the kinds actually written with input evidence, lowest wins.
- A kind remains experimental until "Graduation of a write kind" holds; an author report never promotes an operation.
- `fenolite capabilities` MUST compute graduated and experimental kinds from the matrix.

#### Scenario: Sample envelope
- **WHEN** the sample is built with `--target altium --dry-run --json`
- **THEN** the evidence is the lowest of the inputs and written kinds, and ungraduated kinds are named in `altium.experimental`
