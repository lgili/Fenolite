## MODIFIED Requirements

### Requirement: Placement precedence
`lens.preserve.effective_placements(placements, match, *, design, board, source={}, resolver=None)` SHALL decide each part's placement with the fixed precedence, written in `docs/lens.md`, "Placement precedence": (1) a locked `place()`, absolute or relative; (2) the existing board; (3) the part's entry in the placements file (`source`, "Placements file"); (4) an unlocked `place()`, absolute or relative; (5) the strategy of the innermost enclosing frame that has one, a layout strategy or a block layout reuse (`placement-in-code`, `layout-reuse`); (6) the build's staging. `prepare` SHALL call it, and `cmd_build` SHALL pass the result to `build_design` as its `placements`.
- `placements` MUST be `dsl.placements(design)` (c0011): component path → an object with `at`, `rotation`, `side` and `locked`. "Locked" means `place(…, locked=True)` in the script.
- Relative requests (`dsl.relative_requests(design)`), block poses and strategies MUST be resolved by `resolver`, which `cmd_build` injects from `placement.relative` and `placement.strategies` (`lens` imports neither), in the order of `placement-in-code`, "Resolution order". Every placement made in a block frame MUST be composed with the poses of its blocks before it is compared or written. Without `resolver`, a design with a relative request, a pose or a strategy MUST raise `ValueError`.
- A relative request decides at the level of its lock (1 or 4); a part with an unlocked request MUST NOT be placed by a strategy. A part that no level 1 to 5 places is left unplaced and staged.
- `source` MUST map component paths to `SourcePlacement` entries. An entry that wins MUST be given as a `KeptPlacement` with the entry's position, rotation, side and lock, so the build writes the entry's lock; that lock gives the entry no precedence.
- For a matched part: a locked `place()` MUST win. Otherwise, when its footprint is off the board, the part's `source` entry MUST win, then its `place()`, then its frame's strategy, and without any of them the part MUST be left unplaced, so the build stages it again (`layout.unplaced`). Otherwise the footprint's own position, rotation, side and lock MUST be used, as a `KeptPlacement`, moved rigidly when its block's pose changed (`placement-in-code`, "Rigid block moves").
- A footprint is off the board when its position lies outside the closed box `outline.outline_box(design)` (`kicad-file-backend`, "Board outline as rings"), which holds the arcs of the outline as well as its points, and only when the board's edge content is absent or is exactly that outline ("Board content outside the design is kept"). Otherwise no footprint counts as off the board.
- For an unmatched part: a locked `place()`, then its `source` entry, then its `place()`, then its frame's strategy; otherwise it is left unplaced and staged by the build.
- Without an existing board, `prepare` MUST return what `effective_placements` gives with an empty match and `board=None`, which is `placements` unchanged when `source` is empty, and no match. With `board=None` no footprint is off the board, and a design without an outline has none either.
- An unlocked `place()`, absolute or relative, whose resolved position, rotation or side differs from a kept board placement MUST give `layout.place-overridden` (info), naming the part and both placements (and the request text of a relative one), with the hint "lock the placement in the script, move the footprint in KiCad, or re-run with --discard-layout". When it differs from a `source` entry that wins, the same code MUST be given with the hint "lock the placement in the script, or edit placements.toml".
- A `source` entry of a part that keeps a board placement different from the entry MUST give `layout.source-stale` (info) naming the part and both placements, with the hint "run fenolite sync --to-source". An entry that names no part of the design MUST give `layout.source-unknown` (warning).
- A locked `place()` that differs from the board's position, rotation, side or lock MUST give `layout.place-forced` (warning), because the footprint is then re-placed from its definition ("Kept and re-placed footprints").

#### Scenario: The board wins over place()
- **GIVEN** a confirmed target-10 blink build in `B` whose board was edited by `edit_blink`
- **WHEN** the build runs again with `--confirm`
- **THEN** `D1` stays 4 mm right of its `place()` position, `issues` holds one `layout.place-overridden` naming `D1`, and the exit code is 0

#### Scenario: A locked place() wins
- **GIVEN** a confirmed blink build whose `U1`, locked in `design.py`, was moved 2 mm down in its board by token edit
- **WHEN** the build runs again with `--confirm`
- **THEN** `U1` is back at its `place()` position and locked, and `issues` holds `layout.place-forced` naming `U1`

#### Scenario: A staged part placed by the script
- **GIVEN** a confirmed build of a blink variant whose `R1` has no `place()`, so it is staged beside the outline, after which `design.py` gains `r1.place(mm(20), mm(10))`
- **WHEN** the build runs again with `--confirm`
- **THEN** `R1` is at (120 mm, 110 mm) and `issues` holds no `layout.unplaced`

#### Scenario: A staged part stays staged
- **GIVEN** the same staged build and `design.py` unchanged
- **WHEN** the build runs again with `--confirm`
- **THEN** `R1` keeps its staged position, `issues` holds one `layout.unplaced` naming `R1`, and every file keeps its bytes

#### Scenario: The file places an unmatched part
- **GIVEN** an existing blink board without `R1`'s footprint, a design whose `R1` has an unlocked `place()`, and a `source` entry for `R1` at another position
- **WHEN** `effective_placements` runs
- **THEN** `R1` takes the entry's placement as a `KeptPlacement`, and the issues hold one `layout.place-overridden` with the hint that names `placements.toml`

#### Scenario: The board wins over a stale file
- **GIVEN** the board edited by `edit_blink` and a `source` entry for `D1` at its `place()` position
- **WHEN** `effective_placements` runs
- **THEN** `D1` keeps its board placement, and the issues hold one `layout.source-stale` naming `D1`

#### Scenario: A locked footprint in the file
- **GIVEN** no existing board and a `source` entry for `R1` with `locked = true`
- **WHEN** the blink is built
- **THEN** `R1` is written at the entry's position with `(locked yes)`, and a later edit of the board still wins over the entry

#### Scenario: A part on a round board
- **GIVEN** a confirmed build of a blink variant with `board(outline=shape.circle(mm(20), mm(20), mm(40)))` whose `R1` is placed at (20 mm, 5 mm), then rebuilt with `R1`'s `place()` removed
- **WHEN** the build runs again with `--confirm`
- **THEN** `R1` keeps its board position, which lies inside `outline_box` though outside the box of the outline's two vertices, and `issues` holds no `layout.unplaced`

#### Scenario: A relative request on a fresh build
- **GIVEN** no existing board, `u1.place(mm(14), mm(15))` and `c5.place(right_of=u1, gap=mm(1))` with an injected resolver
- **WHEN** `effective_placements` runs
- **THEN** `C5` is placed with its courtyard box 1 mm right of `U1`'s, and no issue is given

#### Scenario: The board wins over a relative request
- **GIVEN** a confirmed build of that design whose `C5` was moved in KiCad
- **WHEN** the build runs again with `--confirm`
- **THEN** `C5` keeps its board placement, and `issues` hold one `layout.place-overridden` naming `C5` and the request `right_of=U1 gap=1mm`

#### Scenario: A request wins over the strategy
- **GIVEN** a block with `b.layout(row())`, an unplaced part `R1` and a part `C1` with `c1.place(below=r1)`, and no existing board
- **WHEN** `effective_placements` runs
- **THEN** `R1` is placed by the row, `C1` below `R1` by its request, and the row holds only `R1`
