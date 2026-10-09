## ADDED Requirements

### Requirement: Height limits judged
`fenolite.checks.placement.judge_heights(design, limits, heights, *, extents) -> RuleReport` SHALL judge the height limits of a design on the board of `design`, beside `judge` of "Placement rules judged", and SHALL return the same `RuleReport(issues, counts)` with the rule family `height`.
- **Inputs.** `design` is a board model of any backend. `limits` is `RuleSet.heights` of the model that carries the rules (`rules_of(model)` gives it beside the proximity rules). `extents` is the board's `BoardFrame.placed_extents`. `heights` is `heights_of(design, model)`: for each footprint id of `design`, `outward_height` (`design-model`, "Outward height of a part") of that footprint when it holds a body; else `outward_height` of the footprint with the same component path in `model`, the `.fenolite/` model of a built project, when there is one; else `None`. The bodies of the two footprints MUST NOT be mixed, and no height MUST come from anywhere else.
- **Areas.** For each `HeightLimit`, the areas are the board's `Keepout`s whose `name` equals `area`. A limit whose area no `Keepout` names MUST give one `placement.rule-unresolved` (error) naming the limit ("Placement stage issue codes").
- **Under an area.** A footprint is under an area when the area's layers hold `F.Cu` and the footprint is on the top side, or hold `B.Cu` and it is on the bottom side, and the interior of a ring of its own face (`PlacedExtent.own`) meets the interior of the area's outline (`placement.legality.interiors_intersect`, which lives in `fenolite.geometry.rings` so that `checks` may import it; rings that only touch do not meet). An area on inner layers only judges no footprint. This is the face rule of "Placement legality" for keep-outs (`H-K-PLACE-KEEPOUT`). A footprint off the board ("Placement rules judged") is not judged.
- **Who is judged.** A footprint with the attribute `dnp` MUST NOT be judged. One with `board_only`, or whose pads are all of kind `np_thru_hole`, MUST be judged only when its height is known.
- **Findings.** A height above `max` MUST give `placement.too-tall` with the limit's severity; a judged footprint without a known height MUST give `placement.height-unknown` (warning). Both have the part's reference as `where` and name the area and `max`; `placement.too-tall` also names the height. The message of a part judged on the hull of its pads (extent source `pads`) ends with "(approximate extent)". A height equal to `max` is not a finding. One footprint under two areas of one name gives one finding.
- **Counts.** `counts` MUST be `{"height": {"judged", "failed", "unknown"}}`, one count per limit and footprint under one of its areas.
- Issues MUST be sorted by code, then `where`, then message. The function MUST read no file and use no clock, and equal inputs MUST give equal outputs. It MUST NOT call the volume analysis: a limit compares one number with one bound.

#### Scenario: Height limit on one side
- **GIVEN** a rule area named `LID` on `F.Cu` over the top-side parts `U2` (height 3 mm), `J1` (height 9 mm) and `R1` (no body) and the bottom-side part `B1` (height 9 mm), a `dnp` part `R2` under it, and `HeightLimit("LID", 5_000_000)`
- **WHEN** `uv run pytest tests/unit/checks/test_height_limits.py -k one_side` runs `judge_heights`
- **THEN** it gives `placement.too-tall` (error) for `J1`, `placement.height-unknown` (warning) for `R1`, nothing for `U2`, `B1` and `R2`, and `counts == {"height": {"judged": 3, "failed": 1, "unknown": 1}}`

#### Scenario: Equal to the limit, and an inner area
- **GIVEN** the same board with `J1` of height 5 mm, and a second limit on an area `MID` that lies on `In1.Cu` only over `J1`
- **WHEN** `judge_heights` runs
- **THEN** it gives no finding for `J1`

#### Scenario: A limit without its area
- **GIVEN** `HeightLimit("FAN", 12_000_000)` on a board without a rule area named `FAN`
- **WHEN** `judge_heights` runs
- **THEN** it gives one `placement.rule-unresolved` error naming `FAN`

#### Scenario: Heights of the board first, of the stored model second
- **GIVEN** a board read from a KiCad file, whose footprints hold no body, and its `.fenolite/` model whose footprint of `J1` holds a body of 9 mm; and a board read from an Altium document whose footprint of `J1` holds a body with `z_max == 7_000_000`, with the same stored model
- **WHEN** `uv run pytest tests/unit/checks/test_height_limits.py -k heights_of` calls `heights_of` on each
- **THEN** the height of `J1` is `9_000_000` on the first and `7_000_000` on the second

#### Scenario: A part without a courtyard
- **GIVEN** a part of height 9 mm whose extent has the source `pads`, under the area `LID` with a limit of 5 mm
- **WHEN** `judge_heights` runs
- **THEN** its `placement.too-tall` ends with "(approximate extent)"
