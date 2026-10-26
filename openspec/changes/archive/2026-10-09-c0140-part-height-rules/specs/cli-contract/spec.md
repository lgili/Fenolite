## ADDED Requirements

### Requirement: Height limits in place
`fenolite place` SHALL also judge the height limits of a built project after its moves, in addition to the rules of "Place command".
- When the `.fenolite/` model that the command loads holds a height limit, `checks.placement.judge_heights` (`placement`, "Height limits judged") MUST run on the layout after the moves, with `heights_of(<the board>, <that model>)` and the extents the command already has. Each `placement.too-tall` and `placement.height-unknown` MUST be reported with a severity no higher than `warning` and MUST NOT refuse the write.
- `result.rules` MUST gain the family `height` with the counts of `judge_heights`; without a limit the family is absent and the reply is that of "Place command".
- The grid does not read heights: a part that the grid puts under an area too low for it is reported, not moved.
- The envelope's evidence MUST also combine `checks.placement.EVIDENCE` when a limit was judged. No subprocess MUST run, and two runs on equal boards MUST return equal results.

#### Scenario: A move under a low area
- **GIVEN** the blink built with `R1` created with `height=mm(9)`, a rule area `LID` on `F.Cu` over the 8 mm square at the top-left corner of the board (the courtyard of `U1` at (14, 15) mm reaches into a 10 mm square), and `design.height_limit("LID", max=mm(5))`, with `R1` placed outside the area
- **WHEN** `uv run pytest tests/unit/cli/test_place_cmd.py -k height` runs `fenolite place <dir> --move R1=4mm,4mm --dry-run --json`
- **THEN** the exit code is 0, `issues` hold one `placement.too-tall` warning naming `R1`, and `result.rules.height` is `{"judged": 1, "failed": 1, "unknown": 0}`

#### Scenario: No limit, same reply
- **GIVEN** the built blink without a height limit
- **WHEN** `fenolite place <dir> --move R1=12mm,8mm --dry-run --json` runs
- **THEN** `result.rules` holds no `height`
