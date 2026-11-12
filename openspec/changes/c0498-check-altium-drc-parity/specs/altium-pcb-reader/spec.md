## ADDED Requirements

### Requirement: DRC violations stored in a PCB document
`fenolite.backends.altium.read.violations.stored_violations(path, design)` SHALL read the `T…Violation`
storages and the `WaivedViolations` storage of a PCB document with `read.cfb.read_compound`. It SHALL return
one `NativeFinding(kind, rule, primitives, at, message, waived, stale)` per stored violation, in storage
then record order (change c0498).
- `primitives` MUST be the sorted `where` texts that the copper check gives the named items: `REF-PIN` for a
  pad, the item's provenance locator otherwise. They MUST be resolved through the import's locators, never
  by position.
- `at` MUST be in the model's frame, in nanometres, converted with `adapter.units`. The unit of the stored
  location MUST be the one `docs/formats/altium/pcb-records.md`, "DRC violations", records with its source.
- A violation that names a primitive the document does not hold MUST have `stale` true. A violation that
  `WaivedViolations` names MUST have `waived` true.
- A storage whose records do not follow the recorded layout MUST give `altium.read.violations-unknown`
  (warning) and no rows for that storage. The reader MUST NOT guess fields.
- A document without such storages MUST give `()`.

#### Scenario: Violations of the kit board
- **GIVEN** the authored kit board of change c0498, saved by Altium after a DRC with one planted fault per
  judged rule kind
- **WHEN** `uv run pytest tests/unit/backends/altium/test_violations.py -k stored` reads it
- **THEN** there is one row per planted fault, each with its rule kind and the `where` texts of its two
  items, and none is stale

#### Scenario: A renumbered document
- **GIVEN** a copy of that board in which a track named by a violation was deleted
- **WHEN** the stored violations are read
- **THEN** that violation has `stale` true and the others are unchanged

### Requirement: Altium's DRC text report
`violations.report_violations(path, design)` SHALL read the `.drc` text report of Altium's DRC into the same
`NativeFinding` rows (change c0498).
- Each primitive description MUST be matched to one model item by kind, layer and the coordinates that the
  line states. A description that matches no item, or more than one, MUST leave `primitives` as `()` and
  keep the description in `message`.
- An HTML report MUST be refused with `FEN-2001` and a hint to pass the `.drc` text report.

#### Scenario: The kit's text report
- **WHEN** `uv run pytest tests/unit/backends/altium/test_violations.py -k report` reads the `.drc` of the kit
  board of change c0498
- **THEN** its rows equal those of `stored_violations` on the saved board, kind, rule and primitives alike
