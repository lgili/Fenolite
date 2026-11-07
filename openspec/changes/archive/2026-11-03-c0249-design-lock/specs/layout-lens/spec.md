## ADDED Requirements

### Requirement: Changed references keep the layout
A rebuild whose only change to a part is its reference designator, assigned or renumbered through the design lock, SHALL keep that part's footprint with its position, rotation, side and copper, because footprints are matched by uuid and by the `fenolite.path` property and never by reference ("Footprint matching"). The written footprint MUST carry the new reference.

#### Scenario: Lock edit renumbers without moving
- **GIVEN** a confirmed target-10 build of `examples/lock/design.py` whose board was edited to move `buck/U` 3 mm to the right, and a lock then edited by hand from `"buck/U" = "U1"` to `"buck/U" = "U9"`
- **WHEN** the build runs again with `--confirm --json`
- **THEN** `result.preserved.kept` lists `buck/U`, its footprint keeps the moved position and carries the reference `U9`, and `issues` holds no `layout.unplaced` for it
