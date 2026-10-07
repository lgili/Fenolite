## ADDED Requirements

### Requirement: Meanders from intents
`fenolite.backends.kicad.meander.resolve_meanders(design, meanders, *, major, issues=None) -> Design` SHALL replace, for each meander intent (`key`, `track`, `segment`, `amplitude`, `pitch`, `target`, `match`, `side`, `margin`), the track with the uuid `copper_uuid(track, f"seg[{segment}]")` that `resolve_copper` created by a square-wave meander that gives the track intent its target length. The module MUST import only the standard library, `core`, `model`, `geometry`, `backends.base` and modules of `backends.kicad`, never `fenolite.dsl`; it MUST read intents by attribute through the protocol `MeanderIntentLike`, and the function MUST be pure.
- **Length of an intent.** The length of a track intent MUST be the sum of the `segment_length` of its tracks, the `arc_length` of its arcs, the heights of its vias as major `major` counts a via that only the two segments of its via step join (`board-frame`, "KiCad net lengths"), and the die lengths of the pads its ends chose. The target MUST be `target`, or the length of the intent `match` after its own meander, when it has one.
- **Shape.** Let `P` and `Q` be the start and end of the replaced track, `u` the unit vector from `P` to `Q`, `n` the unit normal on `side` (`left` is the side where `orient2d(P, Q, X) < 0`), `m` the margin (`pitch` when `None`), `E` the target less the intent's length, `N = ⌈E / (2·amplitude)⌉` and `h = E / (2N)`. The points MUST be `P`; then, for each bump `i` from 0 to `N − 1`, `P + (m + 2i·pitch)·u`, the same point plus `h·n`, `P + (m + (2i + 1)·pitch)·u + h·n` and `P + (m + (2i + 1)·pitch)·u`; then `Q`. Each point MUST be computed with at least 64 fractional bits and rounded half to even per axis. One track MUST join each two consecutive points, with the width, layer and net of the replaced track and the uuid `copper_uuid(key, f"m[{k}]")`, `k` counting in path order, and the new tracks MUST take the place of the replaced one in `Board.tracks`.
- **Correction.** The intent's length MUST be measured on the built shape; while it differs from the target by more than `LENGTH_TOLERANCE_NM = 10`, half of the difference MUST be added to the height of the last bump and the shape built again, at most twice. No bump MUST be higher than `amplitude` plus 10 nm.
- **Refusals.** `0 ≤ E ≤ LENGTH_TOLERANCE_NM` MUST change nothing and give `kicad.meander.not-needed`, because the intent already lies within the tolerance of its target; `E < 0` `kicad.meander.too-long`; a `pitch` not above the replaced track's width `kicad.meander.bad-shape`; `(2N − 1)·pitch + 2m` above the length of `P`–`Q` `kicad.meander.no-room`, whose message gives `E` and the most the run can add; a track intent without the segment, because it had an error or ended at a staged part, `kicad.meander.no-segment`; a `match` whose intent created nothing, or matches that form a cycle, `kicad.meander.bad-match`; a length still more than 10 nm from the target `kicad.meander.inexact`; a key, side, size or segment that is malformed `kicad.meander.bad-intent`. A refused meander MUST change nothing, and the other meanders are still resolved.
- **Order.** Meanders MUST be resolved in key order, except that a meander whose `match` intent has a meander comes after that one.
- The same design and intents MUST give the same tracks, uuids and issues in every process, whatever `PYTHONHASHSEED`. The tracks carry copper uuids, so `merge_copper` and `merge_layout` keep, regenerate and drop them as script copper.
- `MEANDER_ISSUE_CODES` MUST be the closed table of these codes; as `kicad.*` codes they pass through the closed tables of the build and of the lens unchanged. `meander.EVIDENCE` MUST be `Evidence(Level.INFERRED, hypotheses=("H-K-NETLEN-MEANDER",))`.

| code | severity | when |
|---|---|---|
| `kicad.meander.bad-intent` | error | a key, side, size or segment index is malformed, or the segment is an arc |
| `kicad.meander.bad-shape` | error | the pitch is not above the track's width |
| `kicad.meander.too-long` | error | the intent is already longer than the target |
| `kicad.meander.no-room` | error | the segment cannot add the needed length with the amplitude, pitch and margin |
| `kicad.meander.bad-match` | error | `match` names an intent without copper, or matches form a cycle |
| `kicad.meander.inexact` | error | after two corrections the length differs from the target by more than 10 nm |
| `kicad.meander.no-segment` | warning | the track intent created no segment of that index; the meander creates nothing |
| `kicad.meander.not-needed` | info | the intent already has the target length, within 10 nm |

#### Scenario: A run along an axis
- **GIVEN** a design with the track intent `t` of net `N` from (0, 0) to (20 mm, 0) on `F.Cu`, width 0.2 mm, resolved by `resolve_copper`, and the meander `m` on segment 0 with `target=23 mm`, `amplitude=1 mm`, `pitch=1 mm` and side `left`
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_meander.py -k axis` calls `resolve_meanders(design, [m], major=10)`
- **THEN** the track `seg[0]` of `t` is gone, nine tracks with the uuids `copper_uuid("m", "m[0]")` to `m[8]` join (0, 0), (1 mm, 0), (1 mm, −0.75 mm), (2 mm, −0.75 mm), (2 mm, 0), (3 mm, 0), (3 mm, −0.75 mm), (4 mm, −0.75 mm), (4 mm, 0) and (20 mm, 0), and their lengths sum to 23 000 000

#### Scenario: A run at 30 degrees
- **GIVEN** the same intent from (0, 0) to (17.320508 mm, 10 mm) and a meander with `target=23 mm`
- **WHEN** it is resolved
- **THEN** the intent's length differs from 23 mm by at most 10 nm, and every point lies within `amplitude` plus 10 nm of the run on its left

#### Scenario: Matching another intent
- **GIVEN** the track intents `p` of 20 mm and `n` of 18.8 mm, and a meander on `n` with `match="p"`
- **WHEN** it is resolved
- **THEN** the length of `n` differs from that of `p` by at most 10 nm, and `p` is unchanged

#### Scenario: Refusals change nothing
- **GIVEN** the intent of "A run along an axis"
- **WHEN** meanders with `target=60 mm`, with `target=15 mm` and with `pitch=0.2 mm` are resolved, one at a time
- **THEN** each design is unchanged, and the issues hold `kicad.meander.no-room` (naming 40 mm needed and at most 18 mm possible), `kicad.meander.too-long` and `kicad.meander.bad-shape`
