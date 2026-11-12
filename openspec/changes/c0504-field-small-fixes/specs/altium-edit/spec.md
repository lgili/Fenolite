## ADDED Requirements

### Requirement: A polygon's pour dropped
`Session.unpour(Polygon(name))` SHALL remove every poured primitive of the polygon from every storage that holds one,
keeping the polygon record, its index and every other polygon. A polygon without a poured primitive MUST be refused
with `altium.edit.assertion`. It MUST be gated by `unpour` (`H-A-EDIT-SHAPE`, `H-A-EDIT-KIT`), off as released
(change c0504).

#### Scenario: The ground pour dropped after a move
- **GIVEN** the Part J kit board with planted pour pieces for `GND` and `VIN` (`faults.py`), and a session that moves a track inside it and
  unpours `GND`
- **WHEN** `uv run pytest tests/unit/backends/altium/edit/test_unpour_c0504.py -k dropped` commits it
- **THEN** `GND` holds no poured primitive, `VIN` keeps its pour, the polygon records equal the source's, and
  the receipt holds no `altium.edit.pour-stale`

### Requirement: A stale pour reported
`Session.commit` SHALL give `altium.edit.pour-stale` (warning) for each polygon that still holds a pour and whose
outline box meets the box of a copper item the session added, removed or changed on its layer. The hint MUST name
`Session.unpour` for that polygon (change c0504).

#### Scenario: A move through a poured polygon
- **GIVEN** the same board and a session that moves a track inside the poured polygon `GND` and nothing else
- **WHEN** it commits
- **THEN** it writes, and the issues hold one `altium.edit.pour-stale` naming `GND`

### Requirement: Inherited integrity findings
`Session.commit` SHALL compare the integrity findings of the source and of the result by a key that names the
records by identity (a polygon's name and pour index, an id, a designator, a model id) and not by position. A finding
whose key the source holds MUST NOT give `altium.edit.integrity`. The inherited findings MUST be counted in one
`altium.edit.integrity-inherited` (info) (change c0504).

#### Scenario: A source gap after a region delete
- **GIVEN** the planted fault document whose polygon has the sub-indices 0, 1 and 3, with a free region stored
  before its pieces
- **WHEN** `uv run pytest tests/unit/backends/altium/edit/test_commit.py -k inherited` deletes that free region
  and commits
- **THEN** the commit writes, the issues hold no `altium.edit.integrity` and one
  `altium.edit.integrity-inherited` that counts one `altium.integrity.subpoly-gap`

### Requirement: Values outside the code page in an edit
An edit session SHALL write a property value through the fold of "Compatibility characters folded" (capability
altium-schematic-writer). A value that does not fit Windows-1252 after the fold MUST refuse the commit with
`altium.edit.assertion` naming the character, and MUST NOT raise out of `Session.apply` (change c0504).

#### Scenario: A degree Celsius sign
- **GIVEN** the Part J kit board and a session that sets a component's key to `-40 ℃` and another to `1 kΩ`
- **WHEN** each commits
- **THEN** the first writes `-40 °C` with `altium.text-folded`, and the second is refused with
  `altium.edit.assertion` naming U+03A9, and exit code 5
