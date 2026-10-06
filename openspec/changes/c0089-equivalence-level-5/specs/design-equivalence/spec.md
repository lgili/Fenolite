## ADDED Requirements

### Requirement: Routed connectivity of a net
`fenolite.checks.equivalence.routing.pieces(design)` SHALL return, for each net of a design with a board, the connected pieces of its copper: tracks, arcs, vias, the filled polygons of zones and the pads of the net, joined when two of them touch on a shared copper layer by the exact touch test of the copper check.
- Each `Piece` MUST hold `pads` (the sorted `REF-PAD` elements it contains), `vias` (the count per pair of copper spans) and `lengths` (the routed length of its tracks and arcs per copper span, in nanometres; an arc counts its true length).
- An unfilled zone MUST NOT join anything, and the number of unfilled zones MUST be returned.
- The result MUST NOT depend on the order of the items, and splitting a track at a point of itself MUST NOT change it.
- The module MUST import only `core`, `model`, `geometry` and other `checks` modules.

#### Scenario: Two pads joined through a via
- **GIVEN** a net with a pad on the top layer, a track to a via, and a track on the bottom layer to a second pad
- **WHEN** `pieces` runs
- **THEN** the net has one piece with both pads, one via for the pair top–bottom, and a length on each of the two layers

#### Scenario: An open connection
- **GIVEN** the same net with the bottom track removed
- **WHEN** `pieces` runs
- **THEN** the net has two pieces, one with the first pad and the via, one with the second pad alone

#### Scenario: Re-segmented track
- **WHEN** `uv run pytest tests/unit/checks/equivalence/test_routing.py -k split_invariance` splits and joins the tracks of generated boards
- **THEN** the pieces of each board are unchanged

### Requirement: Level 5 compares routing per net
`level_routing(a, b, pairing, tolerances)` SHALL compare the pieces of the nets that level 2 pairs, and SHALL report each difference with one code, located by the net's name on side `a` and the pads involved.
- `equiv.route-missing` (error): one side has copper on the net and the other has none.
- `equiv.route-connectivity` (error): the multisets of the pad sets of the pieces differ; `where` names the first pad set on one side only.
- `equiv.route-vias` (error): for equal pad sets, the via counts per span pair differ.
- `equiv.route-length` (error): for equal pad sets, a length per copper span differs by more than `max(length_nm, length × length_ppm / 1_000_000)`.
- `equiv.route-stub` (warning): the pieces without a pad differ in number or in total length beyond the tolerance.
- `equiv.route-unjudged` (info): a net whose pads are joined only through an unfilled zone on either side; such a net gives no other difference.
- Copper spans MUST be compared as level 3 compares them. The level summary MUST hold the nets compared, the pieces, the vias, the total length per side and `zones_unfilled`.

#### Scenario: A faithful copy
- **GIVEN** the routed two-layer board and a copy written and re-read by the KiCad backend
- **WHEN** level 5 runs
- **THEN** it reports no difference

#### Scenario: Five planted edits
- **WHEN** `uv run pytest tests/unit/checks/equivalence/test_level5.py -k planted` removes a track, removes a via, moves a track to another layer, opens a connection and deletes a net's copper, one at a time
- **THEN** each run reports one difference, of the code `equiv.route-connectivity`, `equiv.route-vias`, `equiv.route-length`, `equiv.route-connectivity` and `equiv.route-missing` in that order, naming the net

### Requirement: Level 5 in the equivalent command
`fenolite equivalent` SHALL accept `--level 5`, and `max_level` SHALL be 5 when both sides hold at least one track, arc or via.
- `--tolerance-ppm N` (a non-negative integer, default 0) MUST set the relative length tolerance; a profile MAY supply it.
- `--level 5` when a side holds no copper MUST exit 2 with `FEN-2001` naming that side. A level above 5 MUST exit 2.
- `result.levels` MUST hold the object of level 5 with its counts and summary, and the differences of the level MUST follow the rules of the command for issues, exclusions and exit code.

#### Scenario: Routed board against itself
- **WHEN** `fenolite equivalent routed.kicad_pcb routed.kicad_pcb --json` runs on a routed board
- **THEN** the exit code is 0, `result.level` is 5, and `result.levels` holds five objects with `differences` 0

#### Scenario: Unrouted side
- **WHEN** `fenolite equivalent routed.kicad_pcb unrouted.kicad_pcb --level 5` runs
- **THEN** the exit code is 2 and the message names the second side

### Requirement: Level 5 over the triangle
The triangle oracle of c0045 SHALL run at level 5 on routed boards: the KiCad board, the Altium PCB document that Fenolite writes from it and KiCad's import of that document MUST be pairwise equal at level 5 within the tolerances of the triangle's profile, and `docs/evidence/equivalence-triangle.md` MUST hold the boards, the tolerances and every exclusion with its cause.

#### Scenario: Samples and corpus boards
- **WHEN** `uv run pytest tests/kicad/equivalence/test_triangle_level5.py -rA` runs with KiCad 10.0.6 and the corpus cached
- **THEN** every pair is equal at level 5, and the probe `equiv-l5-triangle` records `equal`
