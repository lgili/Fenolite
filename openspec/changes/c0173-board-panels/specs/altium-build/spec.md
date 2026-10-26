## ADDED Requirements

### Requirement: Panel project of an Altium board
`fenolite panel … --target altium` SHALL write `<name>.PcbDoc` and a project `<name>.PrjPcb` that lists the panel document alone; with an Embedded Board Array the board's document stays where `build --target altium` wrote it and is referenced, not copied. A source that is a `.kicad_pcb` MUST give the flattened form.

#### Scenario: Panel project files
- **GIVEN** the fixture built with `--target altium` into `B` and a copy `T.py` of `tests/data/panels/tabs.py` whose `board=` names `B/board.PcbDoc`
- **WHEN** `fenolite panel T.py --out P --target altium --confirm --plan <id>` runs
- **THEN** `P/tabs.PcbDoc` and `P/tabs.PrjPcb` are written, the project lists `[Document1]` `tabs.PcbDoc` and no other document, and `B/board.PcbDoc` keeps its bytes
