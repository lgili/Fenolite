## ADDED Requirements

### Requirement: Project and rules corpus rows
`tests/corpus/manifest.toml` SHALL contain one row per distinct `.kicad_pro` and per distinct `.kicad_dru` file under `demos/` of the KiCad source repository at tags 10.0.6 and 9.0.9.1, found through S-0024. A file whose SHA-256 is identical at both tags is listed once, and `notes` names the other tag.
- Every such row MUST have `uses` containing `project` and `origin:kicad-demos`, and MUST NOT contain `rt0`, `oracle` or `malformed`.
- Its id MUST match `^kicad-demo-\d+(-\d+){2,3}-(pro|dru)-\d{2}$`.
- `license`, `license_variant` and `embeddable = false` MUST be set as in "KiCad demo and third-party board rows", and a folder whose licence has a non-commercial clause MUST NOT be listed. The `rt0`-or-`malformed` rule of that requirement covers the rows it lists; project rows carry `project` instead.
- The rows SHALL be used only for a key-name census and for round-trip tests. Test output and `docs/evidence/kicad-project.md` MUST report key names, ids, version numbers and counts only, never other values.
- `tests/corpus/test_manifest.py` SHALL enforce the id pattern and the forbidden uses for every row whose `uses` contains `project`.

#### Scenario: Project row with a named id
- **GIVEN** a row with `uses = ["project", "origin:kicad-demos"]` whose id is built from its demo folder name
- **WHEN** `uv run pytest tests/corpus/test_manifest.py` runs
- **THEN** the test fails naming the row and the expected pattern

#### Scenario: Project row tagged for RT0
- **GIVEN** a row `kicad-demo-10-0-6-pro-01` with `uses = ["project", "rt0", "origin:kicad-demos"]`
- **WHEN** the manifest test runs
- **THEN** it fails stating that project rows never carry `rt0`

#### Scenario: Fetch by use
- **GIVEN** the manifest with `project` rows
- **WHEN** `uv run python tools/corpus_fetch.py --uses project` runs
- **THEN** only rows whose `uses` contains `project` are fetched, and the summary counts them

### Requirement: Project fixtures saved by the KiCad GUI
Every file under `tests/data/kicad/project/` SHALL be declared in `tests/data/MANIFEST.toml` with `origin = "authored"` and `notes` that state the KiCad version, the operating system, the save date and the SHA-256 of the file as saved by the KiCad GUI.
- `tests/corpus/test_manifest.py` MUST check that the notes name a version matching `(9|10)\.\d+\.\d+` and a 64-hex SHA-256 equal to the SHA-256 of the committed file, so that a fixture edited after the save is detected.
- The files MUST contain no absolute path and no user or host name. `tests/corpus/test_manifest.py` MUST fail when a JSON string of such a file starts with `/`, `~/`, or a drive letter followed by `:\` or `:/`; KiCad's default `~A` and `~V` values do not match. No pattern knows a user or host name, so the maintainer inspects each save for them (task 3.1), and the residue scan's user-path patterns run on the files.
- The only residue waiver for `tests/data/kicad/project/*.kicad_pro` MUST be for the pattern `numeric-code`, with the reason that KiCad stores the `Default` class `priority` as 2147483647.

#### Scenario: Absolute path in a fixture
- **GIVEN** `tests/data/kicad/project/empty_10.kicad_pro` whose `schematic.plot_directory` holds `/tmp/out/`, with notes whose SHA-256 matches the file
- **WHEN** `uv run pytest tests/corpus/test_manifest.py` runs
- **THEN** the test fails naming the file and the pointer `/schematic/plot_directory`

#### Scenario: Fixture edited after the save
- **GIVEN** `tests/data/kicad/project/empty_10.kicad_pro` with one value changed after the save, and its manifest notes unchanged
- **WHEN** `uv run pytest tests/corpus/test_manifest.py` runs
- **THEN** the test fails naming the file and both hashes

#### Scenario: Notes without a version
- **GIVEN** a manifest row for `tests/data/kicad/project/empty_9.kicad_pro` whose notes name no KiCad version
- **WHEN** the manifest test runs
- **THEN** it fails naming the row
