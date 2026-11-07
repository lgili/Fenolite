## ADDED Requirements

### Requirement: Altium native rounds follow-up keeps unmet criteria open
The Altium native rounds follow-up SHALL keep a moved task open until a recorded Altium run meets that task's
proof criteria as written. An agent run counts only under the maintainer's delegation of 2026-11-04 and only
when its criteria pass. A failed case SHALL stay recorded as a result, and no level SHALL rise from a failed or
unrun step.

#### Scenario: A moved task whose run failed a criterion
- **GIVEN** a moved task whose recorded run failed one of its criteria
- **WHEN** the task is reviewed
- **THEN** its box stays open, its blocker names the failed criterion, and no level changes

#### Scenario: A moved task whose run meets its proof
- **GIVEN** a moved task whose recorded run meets every criterion of its proof as written
- **WHEN** the task is reviewed
- **THEN** its box is ticked, and the tick names who ran it and on whose delegation

### Requirement: Kit script creates its log
The kit script SHALL create `results/script.log` when the file is missing and SHALL add to it otherwise, and
it SHALL tell the two cases apart before it opens the file: `FileExists` on the log's path selects `Rewrite`
(missing) or `Append` (present). The choice MUST NOT rest on an exception, because Altium Designer 24.5.2.23
stopped the script on the `EInOutError` of `Append` on the missing log even inside `Try`-`Except` (run
`2026-11-05-e28d0bb1`, S-1590). `FileExists` MUST be listed in `SCRIPT_CALLS` with its public source.

#### Scenario: The log is created by the first scripted step
- **WHEN** `uv run pytest tests/unit/verify/kit/test_script.py -k creates_its_log` reads the script's `LogLine`
- **THEN** `FileExists` on `results\script.log` selects `Rewrite` when it is false and `Append` when it is true, and neither call is inside a `Try` block
