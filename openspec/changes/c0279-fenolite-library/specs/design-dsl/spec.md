## ADDED Requirements

### Requirement: Library section of the design lock
c0249's lock SHALL hold `[library.items."<kind>/<id>"]` with `version`, `release`, `index`, `tree`, `spdx` and `path` (relative to the script folder) for each item that `fenolite get` vendored, registered as a `LockSection`. Only `get` SHALL change the section; a build MUST read it without changing it, so `--frozen` is unaffected.

#### Scenario: Pin written by get
- **GIVEN** a project with `design.py` and no lock, and the release fixture
- **WHEN** `fenolite get device Demo:EXB --from <release> --confirm --json` runs
- **THEN** `design.lock` holds `[library.items."device/Demo:EXB"]` with the item version, release `1.0.0`, the index digest, the tree digest, `CC0-1.0` and `fenolite_library/devices/Demo/EXB`

#### Scenario: Build leaves the section alone
- **GIVEN** that project
- **WHEN** `fenolite build design.py --frozen --json` runs
- **THEN** it reports no `lock.changed` for the section `library`

### Requirement: Missing vendored item
When a `[library.items]` entry's folder does not exist, the build SHALL report `library.item-missing` (error) naming the entry and exit 6 with `FEN-6004`, whose hint is `fenolite get --locked <script> --dry-run`, and MUST write nothing.

#### Scenario: Fresh clone without library folder
- **GIVEN** a lock pinning `device/Demo:EXB` and no `fenolite_library/` folder
- **WHEN** `fenolite build design.py --json` runs
- **THEN** it exits 6, stderr holds `FEN-6004` whose hint names `fenolite get --locked design.py --dry-run`, and no file is written
