## ADDED Requirements

### Requirement: Blocks index command
`fenolite blocks index ITEM_DIR --out FILE` SHALL import the item package in `ITEM_DIR` under a private module name, describe the one block in its `__all__`, and plan one file of kind `block-index` holding `fenolite.block-item.v0`, written only under `--confirm` with a receipt. Zero or several blocks MUST give `FEN-3004`. With `--check` it SHALL compare with `FILE` and write nothing.

#### Scenario: Index check fails on a stale file
- **GIVEN** the test block item with a committed `block.json` older than its code
- **WHEN** `fenolite blocks index tests/data/library/demo/blocks/apache/Demo/led --out tests/data/library/demo/blocks/apache/Demo/led/block.json --check --json` runs
- **THEN** it exits 5 with `blocks.index-stale` and nothing is written

### Requirement: Blocks upgrade command
`fenolite blocks upgrade SCRIPT [--block ID]... [--out DIR] [--allow-major]` SHALL run the script as a build does without planning outputs, and SHALL plan only the lock: the `[blocks]` entries whose locked version differs from the used one (or the selected ones) set to the used versions. It MUST write only under `--confirm`, never edit the script or vendored files, and refuse `--frozen` (exit 2).

#### Scenario: Planned upgrade
- **GIVEN** a lock with `"led1" = "Demo:led@1.0.0"` and `Demo:led` 1.1.0 vendored by `fenolite get block Demo:led --version 1.1.0`
- **WHEN** `fenolite blocks upgrade design.py --dry-run --json` runs
- **THEN** the exit code is 0, `result.plan` holds the lock of kind `lock`, `result.upgrades` holds `led1` from `1.0.0` to `1.1.0` with `step` `minor`, and the lock file is unchanged

#### Scenario: Build after the upgrade
- **WHEN** the same command runs with `--confirm` and then `fenolite build design.py --dry-run --json` runs
- **THEN** the build reports no `lock.block-version`

### Requirement: Upgrade review content
Each row of `result.upgrades` SHALL hold `path`, `id`, `before`, `after`, `step` (`patch`, `minor`, `major` or `downgrade`), the used record, `deprecated`, and the build issues naming the instance; with `--out DIR` it SHALL also hold `circuit`, the parts of the instance added, removed or changed against `DIR/.fenolite/circuit.json`. A `major` row MUST be refused with `blocks.upgrade-major` (exit 5) unless `--allow-major` is given.

#### Scenario: Circuit difference shown
- **GIVEN** a confirmed build in `B` with `Demo:led` 1.0.0, whose 1.1.0 changes the resistor value
- **WHEN** `fenolite blocks upgrade design.py --out B --dry-run --json` runs
- **THEN** the row of `led1` holds in `circuit` the part `led1/R` with its value before and after
