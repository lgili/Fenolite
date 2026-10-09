## ADDED Requirements

### Requirement: Board outline arcs
`Outline` SHALL hold `arcs: tuple[OutlineArc, ...]`, empty by default, and `fenolite.model.board.OutlineArc` SHALL be a frozen value with `ring: int`, `edge: int` and `mid: Point`.
- Ring 0 is `Outline.points` and ring k ≥ 1 is `Outline.cutouts[k − 1]`. Edge i of a ring of n vertices joins vertex i to vertex (i + 1) mod n. An `OutlineArc` makes that edge the circular arc from its first vertex through `mid` to its second vertex; every other edge is straight. `points` and `cutouts` keep their meaning: the vertices of each ring, in order.
- `arcs` MUST be sorted by `(ring, edge)` and MUST hold at most one entry per edge; `ring` and `edge` MUST name an edge of the outline; `mid` MUST differ from the edge's two vertices and MUST NOT lie on the line through them. A ring MUST hold three vertices or more, or two when one of its two edges is an arc. An outline that breaks one of these rules is refused by the build (`kicad-file-backend`, "Outline shape checks").
- The canonical writer omits `arcs` when it is empty, so a `board.json` written before this requirement loads unchanged and an outline without arcs keeps its bytes. `tools/gen_schemas.py` MUST regenerate `schemas/fenolite.model.v0/board.json` with `arcs`.
- The other direction does not hold, and MUST be said: release 0.2.x cannot read a model document that carries the key `arcs`, because its reader refuses an unknown key. `docs/design-model.md` and the changelog MUST hold that sentence. The `board.json` that release 0.2.0 wrote, `tests/data/model/v0.2.0/blink_2layer.board.json` ("Graphics and texts of a footprint instance"), MUST still load unchanged and serialise again to its own bytes.

#### Scenario: An outline with an arc round-trips
- **GIVEN** an `Outline` whose `points` are (0, 0), (10 mm, 0), (10 mm, 10 mm) and (0, 10 mm), whose one cut-out has the two vertices (6 mm, 5 mm) and (4 mm, 5 mm), and whose `arcs` are `OutlineArc(0, 1, Point(11_000_000, 5_000_000))`, `OutlineArc(1, 0, Point(5_000_000, 4_000_000))` and `OutlineArc(1, 1, Point(5_000_000, 6_000_000))`
- **WHEN** the design is written with `canonical.dump_dir` and loaded again with `canonical.load_dir`
- **THEN** the loaded outline equals the original, and `board.json` holds the three entries under `arcs` in that order

#### Scenario: Documents without arcs keep their bytes
- **GIVEN** the `.fenolite/board.json` of a blink build made before this change
- **WHEN** it is loaded with `canonical.loads` and dumped again
- **THEN** `board.outline.arcs == ()` and the dumped text equals the loaded one byte for byte

#### Scenario: A document of 0.2.0 still loads
- **GIVEN** `tests/data/model/v0.2.0/blink_2layer.board.json`, whose outline holds no `arcs`
- **WHEN** `uv run pytest tests/unit/model/test_outline_arcs.py -k v020` loads it with `canonical.loads` and dumps it again
- **THEN** the dumped text equals the file byte for byte, and `docs/design-model.md` and `CHANGELOG.md` each hold the sentence that release 0.2.x cannot read a model document that carries `arcs`

#### Scenario: Schemas regenerated
- **WHEN** `uv run python tools/gen_schemas.py --check` runs after this change
- **THEN** it exits 0, and `board.json` defines `arcs` with the integer fields `ring` and `edge` and the point `mid`
