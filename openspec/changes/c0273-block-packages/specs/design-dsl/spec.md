## ADDED Requirements

### Requirement: Block packages in the design lock
c0249's lock SHALL hold `[block-packages."<distribution>"]` with `version`, `namespace` and `index` (the index's SHA-256) for each distribution whose blocks an instance of the build uses, registered as a `LockSection`. A changed version or index whose used blocks keep their `[blocks]` versions MUST move the entry with `lock.block-package-moved` (info), and an unused entry MUST be dropped with `lock.block-package-released` (info).

#### Scenario: First use pins the package
- **GIVEN** a design using `Acme:led` 1.0.0 from `acme-blocks` 0.3.0 and no lock
- **WHEN** `fenolite build design.py --dry-run --json` runs
- **THEN** the planned lock holds `[blocks]` with the instance and `[block-packages."acme-blocks"]` with version `0.3.0`, namespace `Acme` and the index digest

#### Scenario: Package release with unchanged blocks
- **GIVEN** that lock and `acme-blocks` 0.4.0 installed, in which `Acme:led` is still 1.0.0
- **WHEN** the design is built
- **THEN** the build succeeds, the lock's entry moves to `0.4.0`, and `issues` hold `lock.block-package-moved`; with `--frozen` it exits 7 with `FEN-7004` instead

#### Scenario: Starter blocks are not pinned as a package
- **WHEN** a design that uses only `Fenolite:` blocks is built
- **THEN** its lock holds `[blocks]` entries and no `[block-packages]` section

### Requirement: Missing pinned block package
When a design script raises `ModuleNotFoundError` for a package that a `[block-packages]` entry pins, the build SHALL exit 6 with `FEN-6006`, naming the distribution and version, with a hint naming the install command of that exact version, and MUST write nothing. Any other `ModuleNotFoundError` MUST keep the script-error behaviour.

#### Scenario: Package not installed
- **GIVEN** a lock pinning `acme-blocks` 0.3.0 and an environment without it
- **WHEN** `fenolite build design.py --json` runs
- **THEN** it exits 6, stderr holds `FEN-6006` whose hint names `acme-blocks==0.3.0`, and no file is written
