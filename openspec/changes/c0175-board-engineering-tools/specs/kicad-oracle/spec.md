## ADDED Requirements

### Requirement: Trial edits gated by DRC
`fenolite.api.trial(board, edit, *, kicad_cli=None, refill=True) -> TrialResult` SHALL apply an edit to a copy of a KiCad board, refill its zones, run `kicad-cli` DRC on the copy and on the unedited copy, and return the findings that only the edited copy holds, each mapped to the ids of the edit's items that it names.
- An edit is a callable on the board model that returns the ids of the items it added, removed or changed.
- A writing command that takes `--gate drc` MUST apply its edit through `trial`, drop the items that bring new findings, run the trial again until no new finding remains or nothing is left to drop, and report each dropped item with its finding.
- Without `kicad-cli`, `--gate drc` MUST exit 6 and write nothing.

#### Scenario: One offending track dropped
- **GIVEN** an authored board and an edit that adds two tracks, one of them 0.1 mm from another net's pad under a 0.2 mm rule
- **WHEN** `uv run pytest tests/kicad/test_trial.py -k drop` runs the edit with the gate
- **THEN** the written board holds the first track only, and the result names the second track with its DRC finding

### Requirement: DRC exclusions written
`fenolite check BOARD --exclude TYPE:ITEM_A:ITEM_B --reason TEXT --confirm` SHALL store a DRC exclusion in the project file for the finding of `TYPE` between the two items, under the mutation protocol, written in both orders of the two items, with the reason as its comment.
- An exclusion that matches no current finding MUST be refused with `check.exclusion-unmatched` (exit 5, nothing written).
- The stored exclusions MUST then be judged by the existing check of stored exclusions (live or stale).

#### Scenario: An accepted unconnected item
- **GIVEN** an authored board with one unconnected item that the design accepts
- **WHEN** the exclusion is written and `fenolite check <board> --json` runs
- **THEN** the finding is excluded on both KiCad majors, and the reply lists the exclusion as live
