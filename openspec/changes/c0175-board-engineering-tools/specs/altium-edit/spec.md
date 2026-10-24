## ADDED Requirements

### Requirement: Edit session on an Altium document
`fenolite.backends.altium.edit.open(path) -> Session` SHALL open an Altium PCB document, PCB library or schematic document for typed edits, and `Session.commit(out) -> Receipt` SHALL write the edited document under the mutation protocol, keeping every index table of the document consistent with its primitive streams.
- The operations MUST include `delete`, `move`, `rotate`, `flip`, `set_property`, `clone(item, **changes)`, `add_component(from_doc, ref)`, `remap_layer(old, new)` and `set_rule` for PCB documents, and `set_property`, `move` and `delete` for schematic documents.
- Each operation MUST name its item by kind, geometry and net (or by designator for a component), MUST find exactly one item, and MUST state the old value of each field it changes; a missing item, a second match or a different old value MUST refuse the commit with `altium.edit.assertion` (exit 5) and write nothing.
- A new record MUST be cloned from a record of the same kind and layer that the document holds, with the stated changes, and never written in a shorter form beside records of the longer form; a document that holds no record to clone from MUST refuse the operation with `altium.edit.no-template`.
- Every index the session touches (per-primitive identifiers, pad and via caches, unique-id tables, polygon indices, wide-string tables, parameter groups, model-store entries) MUST be updated in the same commit; new identifiers MUST come from a cryptographic random source and MUST be unique in the document.
- The facts that each operation relies on MUST be hypotheses of `docs/hypotheses.md` with sources or kit cases; an operation whose hypotheses are not confirmed MUST stay behind a gate that is off by default, as c0092's graduation rule requires.

#### Scenario: A move refused on a wrong old value
- **GIVEN** an authored PCB document saved by the maintainer's kit, and a session that moves the track at (10 mm, 5 mm)–(20 mm, 5 mm) on `GND` stating an old width of 0.3 mm where the document holds 0.25 mm
- **WHEN** `uv run pytest tests/unit/backends/altium/edit/test_session.py -k assertion` commits it
- **THEN** the exit code is 5, the issues hold one `altium.edit.assertion`, and nothing is written

### Requirement: Commit gates
`Session.commit` SHALL re-read the written document strictly, compare its decoded content with the input, and refuse a change outside the operations of the session (`altium.edit.unexpected-change`, exit 5), a change of the board's connectivity or of a sheet's net signature that the session does not declare (`altium.edit.connectivity`, exit 5), and any fault of "Integrity check".

#### Scenario: An undeclared connectivity change
- **GIVEN** a session that moves a track onto a pad of another net without declaring a connectivity change
- **WHEN** it commits
- **THEN** the exit code is 5, the issues hold one `altium.edit.connectivity` naming both nets, and nothing is written

### Requirement: Integrity check
`fenolite check DOC --stages altium.integrity` SHALL report, without writing, the faults of an Altium document that make the native tool refuse it or fail on save, each as an error with its stream and record: gaps in the sub-indices of a polygon, duplicate pour indices, duplicate identifiers, parameter groups whose count disagrees with their records, parameter records of a component the document no longer holds, model-store entries that no body uses and bodies without an entry, and primitives whose two layer fields disagree.
- Each rule MUST cite its hypothesis; a rule whose hypothesis is not confirmed MUST report `warning`, not `error`.

#### Scenario: A gap in polygon sub-indices
- **GIVEN** an authored PCB document, saved by the kit, and a copy in which one polygon's sub-indices run 0, 1, 3
- **WHEN** `fenolite check copy.PcbDoc --stages altium.integrity --json` runs
- **THEN** the issues hold one finding naming that polygon and its stream, and the original document gives none
