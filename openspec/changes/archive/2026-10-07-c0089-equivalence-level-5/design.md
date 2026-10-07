## Context

- **Today.** `checks/equivalence/levels.py` holds `level_components`, `level_netlist`, `level_footprints`, `level_placement`, `max_level` (4 with footprints on both sides, else 2) and `compare_designs`. The spec says `--level N` is 1 to 4 and that `--level 5` exits 2. `docs/equivalence.md`: "Levels 5 to 8 of the roadmap (routing, rules, geometry, presentation) are not built."
- **Existing geometry.** `checks/copper.py` (c0029) already decides exactly whether two copper items of a board touch, for tracks, arcs, vias, pads and zone fills; it is what finds shorts. Connected pieces of one net are the same question asked inside a net.
- **Why not item equality.** Two tools split one route into different segments (KiCad's importer joins or splits collinear tracks; Altium's writer rounds to 2.54 nm). Item-by-item equality fails on boards that are the same board. Connectivity and length are what a conversion must keep.
- **Constraints.** Integer arithmetic; deterministic output; the level must run on a 3000-item board in seconds (the copper check's index is reused).

## Goals / Non-Goals

**Goals:**
- A board and its faithful copy in another format are equal at level 5; a board that lost a track, a via or a connection is not.
- Each difference names a net and what differs, so an agent can act on it.
- The level is checked against an independent reading (KiCad's importer) on public boards.

**Non-Goals:**
- Everything under "Non-goals" in the proposal.

## Decisions

1. **Pieces.** For each net, the copper items of the net (tracks, arcs, vias, filled zone polygons, and the pads of the net) form a graph: two items are joined when `checks.copper`'s touch test says so on a shared layer. A piece is a connected component. Its signature is the sorted set of pads (`REF-PAD`) it holds, the number of vias per layer pair, and the routed length per layer (tracks and arcs; zones add none).
2. **Comparison.** Nets are paired as level 2 pairs them (by their pad sets, whatever the names). For a paired net: the multisets of pad sets of the pieces must be equal (`equiv.route-connectivity`); then via counts per layer pair (`equiv.route-vias`); then length per layer within `max(length_nm, length_ppm × length)` (`equiv.route-length`). Pieces without a pad (stubs, stitching) are compared by count and total length (`equiv.route-stub`). A net with copper on one side only gives `equiv.route-missing`.
3. **Layers** are compared by copper span as level 3 does (top, inner by ordinal, bottom), so `F.Cu` and `Top Layer` are the same layer.
4. **Tolerances.** `--tolerance-nm` applies to lengths as an absolute floor; a new `--tolerance-ppm` (default 0) is relative to the length, because rounding accumulates per segment. Profiles of the exclusion file may set both.
5. **Unfilled zones** are left out and counted in the level summary (`zones_unfilled`); a net whose connectivity depends on one is reported `equiv.route-unjudged` (info) and not as a difference.
6. **`max_level`** is 5 when both sides have at least one track, arc or via, else as today. `--level 5` on a side without copper exits 2 naming the side.
7. **Cut order.** First stub comparison, then the ppm tolerance, never connectivity and via counts.

## Files and public API

- `src/fenolite/checks/equivalence/routing.py`: `Piece(pads, vias, lengths)`, `pieces(design) -> Mapping[net id, tuple[Piece, ...]]`, `level_routing(a, b, pairing, tolerances)`.
- `src/fenolite/checks/equivalence/codes.py`: `equiv.route-connectivity`, `equiv.route-vias`, `equiv.route-length`, `equiv.route-missing` (errors), `equiv.route-stub` (warning), `equiv.route-unjudged` (info).
- `src/fenolite/checks/equivalence/norm.py`: `Tolerances(length_nm, angle_udeg, length_ppm=0)`.
- Tests: `tests/unit/checks/equivalence/test_routing.py`, `test_level5.py`, `tests/unit/cli/test_equivalent_cmd.py` (extended), `tests/kicad/equivalence/test_triangle_level5.py`.

## Sources registered by this change

- None: no format fact. The triangle uses `kicad-cli` (S-0020, S-0029) as c0045 does.

Each new source gets the next free `S-` number in `docs/evidence/sources.md` when its task runs (numbers are not reserved here, because changes that run in parallel would collide), with its licence and what was read. Sources under a copyleft or an all-rights-reserved licence are read for facts only; nothing is transcribed.

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-G-EQ-L5 | For two designs that hold the same routed board, `level_routing` reports no difference, and for each of five planted edits (a track removed, a via removed, a track moved to another layer, a connection opened, a net's copper deleted) it reports the difference of its kind | `tests/unit/checks/equivalence/test_level5.py` | no difference on the copies; one located difference of the expected code per edit |
| H-G-EQ-L5-TRIANGLE | A routed KiCad board, the Altium PCB document written from it and KiCad's import of that document are pairwise equal at level 5 within the tolerances of the profile | `tests/kicad/equivalence/test_triangle_level5.py` | probe `equiv-l5-triangle` `equal` on the samples and on the corpus boards of the triangle list; exclusions are listed by rule with their cause |
| H-G-EQ-L5-SPLIT | Splitting or joining collinear segments, and rounding each coordinate by up to 2 nm, changes no level-5 result within a tolerance of 2 nm per segment end | `tests/unit/checks/equivalence/test_routing.py::test_split_invariance` (property test) | no difference for generated boards and their re-segmented copies |

All start `INFERRED`. No id above is in `docs/hypotheses.md` or in another active change (checked 2026-10-06).

## Size (design-days)

| group | dd |
|---|---|
| entry and registers | 0.25 |
| pieces of a net | 1.25 |
| level comparison and codes | 1 |
| command, default level, tolerances | 0.5 |
| triangle oracle and evidence | 0.75 |
| docs | 0.25 |
| closing | 0.25 |

Total: 4.25. This is a size, not a calendar estimate.

## Spec deltas and archive order

- `design-equivalence`, "Equivalent command": `--level` accepts 5, `--tolerance-ppm` is added, the scenario "Usage errors" uses `--level 6`, and the example arguments keep level 4; "Tolerances and normalisation" gains `length_ppm`; "Equivalence documentation" loses the sentence that level 5 is not built. Task 0.1 writes the three as MODIFIED from the living text.
- Archive order: before c0090 and c0092.

## Risks / Trade-offs

- [Boards with zones as the only connection of a net] → reported as unjudged when unfilled; with fills, the zone joins its pads as copper.
- [Default level rises to 5 and existing comparisons start to differ] → the changelog says so; `--level 4` gives the old result; the examples in the docs name the level.
- [Performance on large boards] → the touch index of the copper check is built once per side; a benchmark test bounds a 3000-item board.

## Migration Plan

- `equivalent` without `--level` compares routing when both sides have copper. Scripts that expect exit 0 from routed boards that differ only in routing must pass `--level 4`.
- Rollback: `max_level` returns 4.

## Open Questions

- **Should arcs count their true length or their chord?** Default: true length, from the three points, rounded to a nanometre.
- **Should a via that joins nothing (a stitching via in a zone) be a stub?** Default: yes, counted in `equiv.route-stub`.
