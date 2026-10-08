## ADDED Requirements

### Requirement: Kit command
`fenolite kit` SHALL be registered by `src/fenolite/cli/cmd_kit.py` with four subcommands.
- `kit build --out DIR [--seed N] [--timestamp T]` MUST write the kit under the rules of "Writing files" (dry run, confirm, receipt). It runs no external tool.
- `kit verify DIR` MUST be read-only, MUST print the verdict per step and per hypothesis and the privacy list in `result`, MUST exit 5 when a step fails and 0 otherwise, and MUST exit 3 with `FEN-3001` for a folder without `kit.json`.
- `kit record DIR --out REPO` MUST be a mutating command: it writes `results.zip` beside `DIR` and the run record under `REPO/docs/evidence/altium-kit/`, refuses a verdict with a failed machine check on the kit's own files, refuses a synthetic run, and prints in `result.rows` the register rows whose label may change, with the label text.
- `kit status` MUST be read-only and MUST list the committed runs and the stale rows.
- The envelope evidence of `kit verify` MUST be `ALTIUM-VERIFIED(kit)` only when every step passed and the run is not synthetic; otherwise the lowest level of what was checked.

#### Scenario: Help and example
- **WHEN** `fenolite kit status --json` runs in a tree without a run record
- **THEN** the exit code is 0 and `result.runs` is empty

#### Scenario: Verify refuses a folder that is no kit
- **WHEN** `fenolite kit verify <empty folder>` runs
- **THEN** the exit code is 3 and stderr holds `FEN-3001`
