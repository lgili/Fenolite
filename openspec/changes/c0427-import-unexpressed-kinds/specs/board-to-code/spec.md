## MODIFIED Requirements

### Requirement: Copper on no net and arcs on one line
The Python import SHALL write a track, arc or via on no net as a row of the corresponding table that names no
net, and the build SHALL write that copper on no net. An arc whose start, mid and end lie on one line SHALL
be written as the straight track from its start to its end and reported once as `import.arc-as-track`
(info), which explains its level-5 difference; it SHALL NOT be counted as unexpressed. A via with an unresolved nonempty net id SHALL still be counted as unexpressed rather than
being written on no net.

#### Scenario: A board with net-less copper and an arc on one line
- **WHEN** a KiCad board holds a track and an arc on no net and an arc whose three points lie on one line
- **THEN** `fenolite import --to python` exits 0 without `copper-without-net`, `degenerate-arc` or `arc-as-track` unexpressed
- **AND** the built board holds the net-less track and arc, and a track where the arc on one line was

#### Scenario: A via with no net imports without a loss
- **GIVEN** an authored board with a through via on no net
- **WHEN** it is imported to Python and built
- **THEN** no `copper-without-net` is reported and the built via keeps its position, size, drill, span and no-net state

## ADDED Requirements

### Requirement: Import preserves zero-width user drawing arcs

The importer SHALL express a curved board arc of zero width on a user drawing layer as a drawing
with zero width. The generated board SHALL keep the source layer and three points. A zero-width
arc of another layer or with collinear points SHALL still be reported as unexpressed.

#### Scenario: A stored zero-width drawing arc is rebuilt

- **GIVEN** a KiCad board containing a curved `gr_arc` on `Dwgs.User` with `(width 0)`
- **WHEN** the board is imported to Python and rebuilt
- **THEN** the generated board preserves its arc geometry and literal width

### Requirement: Preserve missing and open board outlines

If no closed board outline can be derived, the importer SHALL declare `board(outline=())` and emit
supported root `Edge.Cuts` items as drawings with their own widths. It SHALL report unsupported
drawings through the existing loss ledger. It MUST NOT substitute a rectangle.

#### Scenario: Import a board with an unfinished outline

- **GIVEN** an authored KiCad board with no root edge or with two open edges of different widths
- **WHEN** imported to Python and rebuilt
- **THEN** the resulting board has the same root edges and no added outline

### Requirement: Preserve a net on an unnumbered copper pad

The importer SHALL express a source net on an unnumbered copper pad as an instance-level
physical pad assignment. It MUST keep the pad number empty and the schematic pins unchanged.

#### Scenario: Imported footprint with mixed unnumbered pads

- **GIVEN** a footprint with netless and netted unnumbered copper pads
- **WHEN** the board is imported to Python and rebuilt
- **THEN** each unnumbered pad keeps its geometry and net in the rebuilt board
