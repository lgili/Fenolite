## ADDED Requirements

### Requirement: DRC gate on writing commands
`fenolite route` and `fenolite tidy` SHALL take `--gate drc`: the command makes its edit, judges it through `fenolite.api.trial(..., gate=True)` (change c0209) and plans the write of the board without the items the trial dropped. Without a `kicad-cli` the command MUST exit 6 before it edits and write nothing. `tidy --drc --gate drc` MUST exit 2.

#### Scenario: A gated route
- **GIVEN** an authored board where the router lays one track 0.1 mm from another net's pad under a 0.2 mm rule
- **WHEN** `uv run pytest tests/kicad/check/test_gate_cli.py` runs `fenolite route` with `--gate drc --confirm`
- **THEN** the written board holds the other tracks only, and the reply names the dropped track with its DRC finding

#### Scenario: No tool
- **WHEN** `fenolite route PATH --router direct --gate drc --confirm` runs where no `kicad-cli` is found
- **THEN** it exits 6 with `FEN-6001` and the board is unchanged

### Requirement: DRC gate report
With `--gate drc`, `result.gate` SHALL hold `tool_version`, `runs`, `refilled`, `items`, `kept`, `dropped` (each id with its findings) and `findings` (new findings naming no item of the edit); without it, `null`. Each dropped item SHALL give `gate.dropped` and each finding left `gate.unnamed`, both warnings. The verdict, counts and edits of the reply MUST describe the kept board. With no finding left the evidence is the trial's.

#### Scenario: Verdict of a gated route
- **WHEN** the gated route of "A gated route" runs
- **THEN** the net of the dropped track is in `result.unrouted`, `result.tracks` counts the kept track only, and the evidence is `KICAD-VERIFIED`

### Requirement: DRC gate units
`fenolite.api.trial` SHALL take `together`, groups of the edit's ids that the gate drops as one, each with the finding that named one of them. `tidy --gate drc` MUST pass one group per edit (its removed, replaced and added ids), so that an edit is kept or undone whole.

#### Scenario: A chamfer undone whole
- **GIVEN** an edit of two added tracks in one group, a new finding naming one of them
- **WHEN** `trial` runs with `gate=True` and that group in `together`
- **THEN** both tracks are dropped, each with that finding
