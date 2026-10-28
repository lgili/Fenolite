## ADDED Requirements

### Requirement: Prune dangling copper
`fenolite.tidy.prune(design, *, pads, nets=None, keep=()) -> TidyResult` SHALL remove, pass after pass until one removes nothing, each unlocked track or arc of the selected nets with a free end (the disc of its width at that end touches no other copper and no zone outline of its net on its layer) and each unlocked via joined on fewer than two copper layers. Items of `keep` MUST stay.

#### Scenario: A stub after routing
- **GIVEN** an authored board with a routed net, a 2 mm stub of it that ends in the air, and a lead to a via joined only on the top layer
- **WHEN** `uv run pytest tests/unit/tidy/test_prune.py -k stub` prunes the board
- **THEN** the stub, the via and then the lead are removed, and every net keeps its groups

### Requirement: Prune keeps the groups
A removal SHALL be kept only when the remaining copper of its net is grouped exactly as before (two items touch on one layer, as in "Open connections of a net"). A track or an arc with a free end whose removal would split its net MUST stay, with `tidy.kept` (info). A net with copper that could not be shaped MUST be left as it is, with `tidy.net-skipped` (warning).

#### Scenario: A bridge with a free end
- **GIVEN** an authored net whose only path between two pads is a track that runs on to a free end
- **WHEN** `uv run pytest tests/unit/tidy/test_prune.py -k bridge` prunes the board
- **THEN** nothing is removed and one `tidy.kept` names that track

### Requirement: Chamfer right-angle joints
`fenolite.tidy.chamfer(design, *, pads, check, nets=None, keep=(), leg=None) -> TidyResult` SHALL replace each point where exactly two unlocked horizontal or vertical tracks of one net, layer and width end at 90°, with nothing else of the net there, by a 45° track between the two ends moved back by the leg: `leg`, or twice the width, at most half of the shorter track. A track cut to nothing MUST be removed.

#### Scenario: A right angle
- **GIVEN** an L of two 0.3 mm tracks of one net
- **WHEN** `uv run pytest tests/unit/tidy/test_chamfer.py -k right_angle` chamfers the board
- **THEN** the joint is a 45° track with legs of 0.6 mm, and the net keeps its groups

### Requirement: Chamfers are checked
A chamfer SHALL be kept only when its net keeps its groups and `check`, a copper check of the whole design, finds nothing that the design before lacks (a new pair of items, or a smaller gap). A chamfer whose tracks a new finding names MUST be undone, and the check run again, until it finds nothing new; a new finding that names no chamfer MUST undo them all. Each undone chamfer gives `tidy.chamfer-undone` (info).

#### Scenario: A chamfer too close
- **GIVEN** an authored corner with a pad of another net inside it, clear of both tracks but not of their chamfer
- **WHEN** `uv run pytest tests/unit/tidy/test_chamfer.py -k too_close` chamfers the board with the copper check
- **THEN** the design is unchanged and one `tidy.chamfer-undone` names `copper.clearance`

### Requirement: Tidy command
`fenolite tidy PATH [--nets GLOB]... [--prune] [--chamfer] [--leg LENGTH] [-o FILE]` SHALL be a writing command under the mutation protocol (schema `fenolite.tidy.v0`) on a KiCad board that runs the selected steps in the order prune, chamfer, both when neither is given. Locked items and script copper MUST stay. `result` MUST list each edit with its step, reason, net, layer, point and the ids it removed, replaced and added.

#### Scenario: Dry run of the steps
- **WHEN** `uv run pytest tests/unit/cli/test_tidy_cmd.py -k dry_run` runs `fenolite tidy tidy.kicad_pcb --dry-run --json` on the authored bench
- **THEN** the exit code is 0, `result.plan` names the board, and `result.steps` is `prune`, `chamfer`

### Requirement: Tidy command checks the result
`fenolite tidy` SHALL judge each edit with the copper check and the rules of the project beside the board, and the tidied board once more: a finding it lacked before gives `tidy.check-failed` (error) and no write. With `--drc`, `kicad-cli` DRC MUST run on copies of both boards; a violation type that grows gives `tidy.drc-new` (error) and no write, else the evidence is `KICAD-VERIFIED`. Without it the evidence MUST stay `INFERRED` or lower.

#### Scenario: KiCad finds nothing new
- **GIVEN** the authored bench written for the running `kicad-cli` with a project that holds its clearance
- **WHEN** `uv run pytest tests/kicad/tidy -k no_drc` runs `fenolite tidy <board> --drc --confirm`
- **THEN** the exit code is 0, the evidence is `KICAD-VERIFIED`, and no DRC violation type has more entries than before

### Requirement: Tidy codes
The codes `tidy.check-failed`, `tidy.drc-new` (error), `tidy.net-skipped`, `tidy.project-unread` (warning), `tidy.chamfer-undone`, `tidy.fill-stale` and `tidy.kept` (info) SHALL be the table `fenolite.tidy.codes.ISSUE_CODES`, each explained by `fenolite explain` and listed under "tidy" in `docs/cli-contract.md`.

#### Scenario: Every code is explained
- **WHEN** `uv run pytest tests/unit/cli/test_explain_cmd.py` runs
- **THEN** every `tidy.*` code has an entry whose `see` is the heading `tidy`
