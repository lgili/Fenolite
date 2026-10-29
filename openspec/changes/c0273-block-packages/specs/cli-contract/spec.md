## ADDED Requirements

### Requirement: Blocks index command
`fenolite blocks index PACKAGE_DIR --out FILE` SHALL import the package in `PACKAGE_DIR`, describe every block in its modules' `__all__`, and plan one file of kind `block-index` holding `fenolite.block-index.v0`, written only under `--confirm` with a receipt. With `--check` it SHALL compare with `FILE` and write nothing.

#### Scenario: Index check fails on a stale file
- **GIVEN** the test distribution with a committed index older than its code
- **WHEN** `fenolite blocks index tests/data/blocks/pkg/acme_blocks --out tests/data/blocks/pkg/acme_blocks/fenolite-blocks-index.json --check --json` runs
- **THEN** it exits 5 with `blocks.index-stale` and nothing is written

### Requirement: Blocks upgrade command
`fenolite blocks upgrade SCRIPT [--block ID]... [--package NAME]... [--out DIR] [--allow-major]` SHALL run the script as a build does without planning outputs, and SHALL plan only the lock: the `[blocks]` entries whose locked version differs (or the selected ones) set to the used versions, and the selected `[block-packages]` entries set to the installed packages. It MUST write only under `--confirm`, and MUST refuse `--frozen` (exit 2).

#### Scenario: Planned upgrade
- **GIVEN** a lock with `"led1" = "Acme:led@1.0.0"` and `acme-blocks` installed with `Acme:led` 1.1.0
- **WHEN** `fenolite blocks upgrade design.py --dry-run --json` runs
- **THEN** the exit code is 0, `result.plan` holds the lock of kind `lock`, `result.upgrades` holds `led1` from `1.0.0` to `1.1.0` with `step` `minor`, and the lock file is unchanged

#### Scenario: Build after the upgrade
- **WHEN** the same command runs with `--confirm` and then `fenolite build design.py --dry-run --json` runs
- **THEN** the build reports no `lock.block-version`

### Requirement: Upgrade review content
Each row of `result.upgrades` SHALL hold `path`, `id`, `before`, `after`, `step` (`patch`, `minor`, `major` or `downgrade`), the installed record, `deprecated`, and the build issues naming the instance; with `--out DIR` it SHALL also hold `circuit`, the parts of the instance added, removed or changed against `DIR/.fenolite/circuit.json`. A `major` row MUST be refused with `blocks.upgrade-major` (exit 5) unless `--allow-major` is given.

#### Scenario: Circuit difference shown
- **GIVEN** a confirmed build in `B` with `Acme:led` 1.0.0, whose 1.1.0 changes the resistor value
- **WHEN** `fenolite blocks upgrade design.py --out B --dry-run --json` runs
- **THEN** the row of `led1` holds in `circuit` the part `led1/R` with its value before and after

### Requirement: Block package error code
`FEN-6006` SHALL mean that a block package pinned by the design lock is not installed: exit 6, `retryable` false, registered in `cli/errors.py` and `explain.toml`, with a hint naming the install command of the pinned version. The number SHALL be the next free `FEN-6` code when this change is implemented.

#### Scenario: Code registered
- **WHEN** `fenolite explain FEN-6006 --json` runs
- **THEN** it gives exit code 6, `retryable` false and a hint that names installing the pinned version

### Requirement: Block packages in capabilities and doctor
`fenolite capabilities --json` SHALL hold `block_packages`, one row per discovered package with `distribution`, `version`, `namespace`, `blocks` and `index`, sorted by distribution, and `doctor` SHALL list them and warn on broken, conflicting or reserved packages. Neither MUST import a package.

#### Scenario: Installed package reported
- **GIVEN** the test distribution `acme-blocks` 0.3.0 installed into a temporary environment
- **WHEN** `fenolite capabilities --json` runs there
- **THEN** `result.block_packages` holds `acme-blocks`, `0.3.0`, `Acme` and `2`
