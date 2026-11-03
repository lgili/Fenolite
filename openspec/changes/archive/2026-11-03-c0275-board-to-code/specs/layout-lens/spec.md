## ADDED Requirements

### Requirement: Adopted boards
`fenolite import --adopt` SHALL also write `adopted/<name>.kicad_pcb` and its project file: the source board rewritten by token edits only, where each footprint takes the uuid `footprint_uuid(path)`, a `fenolite.path` property and the pad uuids a build derives, and each keyed item (track, arc, via, zone, rule area, drawing) takes the uuid its key derives. "Footprint matching" applies unchanged.

#### Scenario: Build over an adopted board changes nothing
- **GIVEN** a confirmed `--adopt` import of the authored two-sheet project into `out`
- **WHEN** `fenolite build out/design.py --out out/adopted --confirm` runs, and then again
- **THEN** every component is matched with key `uuid`, `orphans` and `board_only` are empty, no `kicad.copper.regenerated` or `kicad.copper.stale` is reported, and the second build writes the same bytes as the first

#### Scenario: Only identities change
- **GIVEN** the same adopted board and the source board, both read with `read_board`
- **WHEN** they are compared with `equivalent` at levels 1 to 5
- **THEN** no difference is reported, and the two texts differ only in `uuid` atoms and the added `fenolite.path` properties

#### Scenario: KiCad loads the adopted board
- **GIVEN** `kicad-cli` 9.0.9 or 10.0.6 and the adopted board of the authored project
- **WHEN** `pcb drc --format json` runs on it and on the source
- **THEN** both reports parse and hold the same violations and unconnected items
