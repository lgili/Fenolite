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
The repository SHALL hold an acceptance project for the second backend's write side and a script `tools/acceptance_v03.py` that: builds it for KiCad and for Altium; runs `fenolite check` on both; compares the two at level 5 of `equivalent`; runs `fenolite roundtrip --level rta3` on the Altium project; and compares the KiCad board with KiCad's import of the Altium documents at level 5.
- The project MUST use every item that the written scope lists: a stack of six copper layers, blind and buried vias, board texts, a keep-out, a non-plated hole, bodies, polygons, rules of every exact kind, a module tree two levels deep, a bus, an output job and a drawing sheet.
- `docs/evidence/altium-acceptance.md` MUST record each run of the script with the versions of Fenolite, KiCad and Altium, the result of each step, and the id of the kit run made on the same tree.

#### Scenario: Acceptance run
- **WHEN** `uv run pytest tests/kicad/acceptance/test_v03_acceptance.py -rA` runs with KiCad 10.0.6
- **THEN** every step of the script passes, and the probe `acceptance-v03` records `equal`
