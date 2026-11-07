## ADDED Requirements

### Requirement: Edit session on an Altium document
`fenolite.backends.altium.edit.open(path) -> Session` SHALL open an Altium PCB document, PCB library or schematic document for typed edits, and `Session.commit(out) -> Receipt` SHALL write the edited document under the mutation protocol. The operations MUST be `delete`, `move`, `rotate`, `flip`, `set_property`, `clone(item, **changes)`, `add_component(from_doc, ref)`, `remap_layer(old, new)` and `set_rule` for PCB documents, and `set_property`, `move` and `delete` for schematic documents.

#### Scenario: A move written and read back
- **GIVEN** the authored PCB document of the kit saved by the maintainer in case J1, and a session that moves the track at (10 mm, 5 mm)–(20 mm, 5 mm) on `GND` by 1 mm in Y, stating its old ends, with the gate of `move` on
- **WHEN** `uv run pytest tests/unit/backends/altium/edit/test_session.py -k move` commits it
- **THEN** the written document reads back with that track at (10 mm, 6 mm)–(20 mm, 6 mm) and every other record equal to the input

### Requirement: Asserted edits
Each operation MUST name its item by kind, geometry and net (or by designator for a component), MUST find exactly one item, and MUST state the old value of each field it changes. A missing item, a second match or a different old value MUST refuse the commit with `altium.edit.assertion` (exit 5) and write nothing.

#### Scenario: A move refused on a wrong old value
- **GIVEN** the authored PCB document saved by the maintainer's kit, and a session that moves the track at (10 mm, 5 mm)–(20 mm, 5 mm) on `GND` stating an old width of 0.3 mm where the document holds 0.25 mm
- **WHEN** `uv run pytest tests/unit/backends/altium/edit/test_session.py -k assertion` commits it
- **THEN** the exit code is 5, the issues hold one `altium.edit.assertion`, and nothing is written

### Requirement: Records cloned from the document
A new record MUST be cloned from a record of the same kind and layer that the document holds, with the stated changes, and MUST never be written in a shorter form beside records of the longer form. A document that holds no record to clone from MUST refuse the operation with `altium.edit.no-template`.

#### Scenario: No record to clone from
- **GIVEN** the authored PCB document, which holds no track on Mechanical 1, and a session that clones the track `probe` onto Mechanical 1
- **WHEN** it commits
- **THEN** the issues hold one `altium.edit.no-template` naming the kind and the layer, and nothing is written

### Requirement: Index upkeep
Every index the session touches (per-primitive identifiers, pad and via caches, unique-id tables, polygon indices, wide-string tables, parameter groups, model-store entries) MUST be updated in the same commit. New identifiers MUST come from a cryptographic random source and MUST be unique in the document.

#### Scenario: A deleted component leaves no index behind
- **GIVEN** the authored PCB document saved by the kit, and a session that deletes the component `R2` with the gate of `delete` on
- **WHEN** it commits
- **THEN** the unique-id table, the wide strings and the parameter groups of the written document hold no entry of `R2`, and `fenolite check out.PcbDoc --stages altium.integrity --json` reports no finding

### Requirement: Operations gated by their hypotheses
The facts that each operation relies on MUST be hypotheses of `docs/hypotheses.md` with sources or kit cases. An operation whose hypotheses are not confirmed MUST stay behind a gate that is off by default, as c0092's graduation rule requires, and MUST be refused while its gate is off, naming the gate and the unconfirmed hypotheses.

#### Scenario: An operation behind its gate
- **GIVEN** the gate of `flip` off, as released
- **WHEN** a session flips the component `D1` and commits
- **THEN** the commit is refused, the refusal names the gate of `flip` and `H-A-EDIT-FLIP`, and nothing is written

### Requirement: Commit gates
`Session.commit` SHALL re-read the written document strictly, compare its decoded content with the input, and refuse a change outside the operations of the session (`altium.edit.unexpected-change`, exit 5), a change of the board's connectivity or of a sheet's net signature that the session does not declare (`altium.edit.connectivity`, exit 5), and any error of "Integrity check".

#### Scenario: An undeclared connectivity change
- **GIVEN** a session that moves a track onto a pad of another net without declaring a connectivity change
- **WHEN** it commits
- **THEN** the exit code is 5, the issues hold one `altium.edit.connectivity` naming both nets, and nothing is written

### Requirement: Integrity check
`fenolite check DOC --stages altium.integrity` SHALL report, without writing, the faults of an Altium document that make the native tool refuse it or fail on save, each as a finding with its stream and record. Each rule MUST cite its hypothesis; a rule whose hypothesis is not confirmed MUST report `warning`, not `error`.

#### Scenario: A gap in polygon sub-indices
- **GIVEN** an authored PCB document, saved by the kit, and a copy in which one polygon's sub-indices run 0, 1, 3
- **WHEN** `fenolite check copy.PcbDoc --stages altium.integrity --json` runs
- **THEN** the issues hold one finding naming that polygon and its stream, and the original document gives none

### Requirement: Integrity rules of indices
The stage `altium.integrity` MUST report gaps in the sub-indices of a polygon, duplicate pour indices and duplicate identifiers, each finding naming the records that share or skip the value.

#### Scenario: Two pads with one unique id
- **GIVEN** a copy of the kit's saved PCB document in which two pads share one unique id
- **WHEN** `fenolite check copy.PcbDoc --stages altium.integrity --json` runs
- **THEN** the issues hold one finding naming both pads and `UniqueIDPrimitiveInformation`, with severity `warning` while `H-A-INTEG-ID` is not confirmed

### Requirement: Integrity rules of parameters, models and layers
The stage `altium.integrity` MUST report parameter groups whose count disagrees with their records, parameter records of a component the document no longer holds, model-store entries that no body uses and bodies without an entry, and primitives whose two layer fields disagree.

#### Scenario: Two layer fields that disagree
- **GIVEN** a copy of the kit's saved PCB document in which one region's layer byte names Mechanical 13 and its `V7_LAYER` names Mechanical 15
- **WHEN** `fenolite check copy.PcbDoc --stages altium.integrity --json` runs
- **THEN** the issues hold one finding naming that region and both layers

### Requirement: Kit cases for edit sessions
`docs/evidence/altium-edit.md` SHALL hold Part J: phase A cases J1 to J22 that the maintainer runs on documents authored for Fenolite, and phase B cases J23 to J33 on the documents the session writes and on planted faults. Each case MUST state its expected outcome, and each hypothesis `H-A-EDIT-*` and `H-A-INTEG-*` MUST be named by a case.

#### Scenario: Pages name the cases
- **GIVEN** the page and `docs/hypotheses.md`
- **WHEN** `uv run pytest tests/unit/test_altium_verification_docs.py -k part_j` runs
- **THEN** it passes: J1 to J33 in order, each with an expected outcome, and every row of both families named
