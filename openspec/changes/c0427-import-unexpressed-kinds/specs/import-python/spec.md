## ADDED Requirements

### Requirement: Rules the DSL cannot say are kept as written
`import --to python` SHALL NOT emit a `design.rules` call that the DSL refuses. When a rule of the source's
rules file has no `design.rules` call (an undeclared net class, a selector or limit the DSL cannot write)
and the source holds the text of every rule of that constraint kind, every rule of that kind SHALL be
emitted as `design.verbatim("rule/<n>", <text>, target="kicad_dru")` in file order, and SHALL NOT be counted
as `custom-rule`; the rules of the other kinds SHALL stay `design.rules` calls (change c0427).

#### Scenario: An undeclared class
- **WHEN** `uv run pytest tests/unit/importer/test_unexpressed_kinds.py -k cannot_say -q` imports the committed `two_sheet` project with clearance rules `ghost` (class `Ghost`, not declared) and `wide`, and a track width rule
- **THEN** both clearance rules are verbatim items in their file order, the track width is `design.rules.minimum`, the script builds, and the built rules file holds the clearance rules `ghost` then `wide`

### Requirement: Nets that only copper graphics name
A net that a copper graphic of the source names SHALL be declared with `Net(...)` and passed as the graphic's
`net=`, whether or not a pad, track, zone or sheet names it (change c0427).

#### Scenario: A board-only net
- **WHEN** `uv run pytest tests/unit/importer/test_unexpressed_kinds.py -k only_a_copper_graphic -q` imports `two_sheet` with a filled `F.Cu` polygon on net `ISLAND`
- **THEN** nothing is unexpressed, the result is equivalent, the script declares `Net("ISLAND")`, and the built board holds the polygon on `ISLAND`

### Requirement: Paste-layer drawings
A drawing on `F.Paste` or `B.Paste` SHALL be emitted as a DSL drawing call (change c0427).

#### Scenario: A paste polygon
- **WHEN** `uv run pytest tests/unit/importer/test_unexpressed_kinds.py -k paste -q` imports `two_sheet` with a filled polygon on `B.Paste`
- **THEN** nothing is unexpressed and the built board holds the polygon on `B.Paste`

### Requirement: A straight arc is the line it draws
`import --to python` SHALL emit a drawing arc whose three points lie on one line, with the middle point
between the ends and a width above 0, as `design.line()` from its start to its end, on its layer and of its
width. An arc of
one point, or whose middle point lies beyond an end, SHALL stay counted as `drawing` (change c0427).

#### Scenario: Straight arcs on Dwgs.User
- **WHEN** `uv run pytest tests/unit/importer/test_unexpressed_kinds.py -k straight_arc -q` imports `two_sheet` with three `Dwgs.User` arcs of width 0.2 mm: one with its middle point between its ends, one of one point, one whose middle point lies beyond its end
- **THEN** the first is `design.line()`, the other two are counted as `drawing`, the script builds, and the built board holds one `Dwgs.User` line from (10, 10) to (12, 10) mm, 0.2 mm wide

### Requirement: Public Altium rows are pinned
The import result of every public Altium PCB document of the corpus manifest SHALL be pinned: exit code,
codes of its error findings, and no unexpressed item (change c0427).

#### Scenario: The public rows
- **WHEN** `uv run pytest tests/corpus/test_altium_import_python.py -q` runs with the corpus cached (row 08 with `FENOLITE_HEAVY=1`)
- **THEN** rows 03 to 07 exit 0 and are equivalent, rows 01, 02 and 08 exit 5 with `import.unequal` only, and no row leaves an item out
