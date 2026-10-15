## ADDED Requirements

### Requirement: Footprint items in the model difference
`fenolite.checks.diff.diff_designs` SHALL compare the graphics and the texts of footprints as two content kinds, `footprint_graphic` and `footprint_text`, and the corner ratio as a field of the kind `pad`.
- An entity of either kind is the item's compared fields with `footprint`, the key of its footprint in the kind `footprint` (the reference of its component). Entities are matched by content, as the kinds `graphic` and `text` are, so the order of a footprint's items does not count.
- The entry of a footprint in the kind `footprint` MUST leave out `graphics` and `texts`, as it leaves out `pads`.
- With a `ModelScope`, the kinds and their fields are compared only when the scope names them, and `points`, `position`, `size`, `width` and `thickness` take the scope's tolerance ("Model difference scope").
- Two designs whose footprints hold no item and whose pads hold no ratio MUST give the report they gave before: no path, no count and no key of `summary` changes for them.
- No level of `equivalent` reads the three fields (`design-equivalence`): a footprint's drawing and the corner ratio are compared by the model difference and by the Altium round-trip levels only.

#### Scenario: A moved line of one footprint
- **GIVEN** two designs that are equal except that one silkscreen line of `R1` is moved by 1 mm
- **WHEN** `uv run pytest tests/unit/checks/test_diff.py -k footprint_items` runs `diff_designs(a, b)`
- **THEN** the changes are one `removed` and one `added` under `/footprint_graphic/`, each naming `R1`, and nothing under `/footprint/`

#### Scenario: Order does not count
- **GIVEN** design `b` equal to `a` with the graphics of each footprint in reverse order
- **WHEN** `diff_designs(a, b)` runs
- **THEN** `equal` is true

#### Scenario: Reports of designs without items
- **WHEN** `uv run pytest tests/unit/checks/test_diff.py` runs after this change, with no edit of its earlier tests
- **THEN** every earlier test passes
