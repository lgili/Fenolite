# corpus-policy Specification

## Purpose
Describe the public test corpus with licences and hashes, fetch it reproducibly, and allow only public-domain or authored files to be committed.
## Requirements
### Requirement: Corpus manifest schema
`tests/corpus/manifest.toml` SHALL describe every external test file as a `[[file]]` table with the keys `id`, `url`, `ref`, `sha256`, `license` (SPDX identifier), `license_variant`, `embeddable` (boolean), `uses` (list of strings) and `notes`, and `tests/corpus/test_manifest.py` SHALL validate the schema.

#### Scenario: Missing sha256 rejected
- **GIVEN** a `[[file]]` entry without `sha256`
- **WHEN** `pytest tests/corpus/test_manifest.py` runs
- **THEN** the test fails naming the entry id

### Requirement: Fetch with verification
`tools/corpus_fetch.py` SHALL download every manifest item into `~/.cache/fenolite/corpus/<id>/`, verify the SHA-256, refuse to keep a file whose hash differs, and print a summary of fetched, cached and failed items.

#### Scenario: Hash mismatch
- **GIVEN** a manifest entry whose `sha256` does not match the downloaded bytes
- **WHEN** `uv run python tools/corpus_fetch.py` runs
- **THEN** the file is deleted from the cache and the exit code is non-zero

### Requirement: Embeddable rule
A file committed under `tests/data/` or `examples/` MUST either be authored for Fenolite (declared `origin = "authored"` in `tests/data/MANIFEST.toml`) or reference a manifest item with `embeddable = true`, and `embeddable = true` SHALL be allowed only when `license` is `CC0-1.0` or the item is dedicated to the public domain.

#### Scenario: Share-alike file committed
- **GIVEN** a file under `tests/data/` referencing a manifest item with `license = "CC-BY-SA-4.0"`
- **WHEN** `pytest tests/corpus/test_manifest.py` runs
- **THEN** the test fails stating the file is not embeddable

#### Scenario: Authored fixture accepted
- **GIVEN** `tests/data/blink.kicad_pcb` declared with `origin = "authored"`
- **WHEN** the test runs
- **THEN** the file is accepted

### Requirement: Skip markers
Tests marked `needs_corpus` SHALL be skipped with the message `run: uv run python tools/corpus_fetch.py` when the cache is absent, and tests marked `needs_libs` SHALL be skipped when no KiCad library source is configured.

A KiCad library source for `needs_libs` is one of:
- a folder named by a `KICAD9_*` or `KICAD10_*` footprint or symbol variable of the environment
- a local KiCad install at the per-OS default location, or at the path in `FENOLITE_KICAD_INSTALL_DIR` when that variable is set; a path that does not exist means that no install is available
- a verified library cache: a `kicad-footprints` or `kicad-symbols` folder under `<cache>/<tag>/` whose `.fenolite-verified` stamp equals its pin (`kicad-library-resolution`, "Library pins"), where `<cache>` is `FENOLITE_LIBS_CACHE` when set and `~/.cache/fenolite/libs` otherwise

The `needs_libs` skip message MUST name the three ways to provide a source: setting `KICAD10_FOOTPRINT_DIR` and `KICAD10_SYMBOL_DIR`, installing KiCad, or running `uv run python tools/kicad_libs_fetch.py`. The required-resource mode of `ci-baseline` applies to `needs_libs` with this message.

#### Scenario: Corpus absent
- **GIVEN** an empty `~/.cache/fenolite/corpus/`
- **WHEN** `pytest -m needs_corpus` runs
- **THEN** every such test is reported as skipped with that message and the run exits 0

#### Scenario: No library source
- **GIVEN** `FENOLITE_KICAD_INSTALL_DIR` set to a path that does not exist, `FENOLITE_LIBS_CACHE` naming an empty folder, and no `KICAD9_*` or `KICAD10_*` library variable
- **WHEN** `uv run pytest tests/unit/test_conftest_libs.py` runs a pytester session with one `needs_libs` test
- **THEN** that test is skipped with the message naming the variables, the install and `tools/kicad_libs_fetch.py`, and the inner session exits 0

#### Scenario: Required libraries missing
- **GIVEN** the same environment and `FENOLITE_REQUIRE=libs`
- **WHEN** the pytester session runs
- **THEN** the `needs_libs` test fails with the same message

#### Scenario: Variables select the source
- **GIVEN** `FENOLITE_KICAD_INSTALL_DIR` set to a path that does not exist, `FENOLITE_LIBS_CACHE` naming an empty folder, and `KICAD10_FOOTPRINT_DIR` naming an existing folder
- **WHEN** the pytester session runs
- **THEN** the `needs_libs` test runs

#### Scenario: Verified cache selects the source
- **GIVEN** `FENOLITE_KICAD_INSTALL_DIR` set to a path that does not exist, no library variable, and `FENOLITE_LIBS_CACHE` naming a folder whose `10.0.6/kicad-footprints/.fenolite-verified` equals the 10.0.6 footprint pin
- **WHEN** the pytester session runs
- **THEN** the `needs_libs` test runs

#### Scenario: Stale cache does not count
- **GIVEN** the same folder, whose stamp names another tree hash
- **WHEN** the pytester session runs
- **THEN** the `needs_libs` test is skipped with the message of "No library source"

### Requirement: Measurement versus embedding
Files from reciprocal or share-alike sources (`embeddable = false`) MAY be used to measure formats and to run tests after fetching, and MUST NOT be copied, in whole or in part, into the repository, into seeds or into generated fixtures.

#### Scenario: Derived seed from a non-embeddable donor
- **GIVEN** a seed file under `src/fenolite/` whose bytes contain a stream copied from a manifest item with `embeddable = false`
- **WHEN** `pytest tests/residue` runs with the corpus cache present
- **THEN** the test fails naming the seed and the donor id

### Requirement: KiCad demo and third-party board rows
`tests/corpus/manifest.toml` SHALL contain the following rows:
- one row per distinct `.kicad_pcb` under `demos/` of the KiCad source repository at tags 10.0.6 and 9.0.9.1. A file whose SHA-256 is identical at both tags is listed once, and `notes` names the other tag and the tag commit.
- one schematic, one symbol library, one footprint, one footprint-library table and one worksheet from the demos at 10.0.6
- the Apache-2.0 third-party boards registered as sources S-0027 and S-0028

Every row MUST set `license` from the repository-level statement. It MUST record any per-folder licence in `license_variant`, and it MUST set `embeddable = false`. A demo folder whose licence carries a non-commercial clause MUST NOT be listed. Every row MUST carry exactly one of `origin:kicad-demos` and `origin:third-party` in `uses`, and either `rt0` or, for a file that its source publishes malformed so that the parser rejects it as fetched, `malformed` (never both); a `malformed` row's `notes` MUST name the rule the parser reports. Board rows that carry `rt0` MUST also carry `oracle`, and files larger than 20 MB MUST also carry `heavy`.

#### Scenario: Non-commercial folder excluded
- **GIVEN** a manifest row whose `license_variant` mentions a non-commercial licence
- **WHEN** `uv run pytest tests/corpus/test_manifest.py` runs
- **THEN** the test fails naming the row id

#### Scenario: Missing origin
- **GIVEN** an `rt0` row whose `uses` has no `origin:` value
- **WHEN** the manifest test runs
- **THEN** it fails naming the row id

#### Scenario: Heavy file untagged
- **GIVEN** a row whose fetched file is larger than 20 MB and whose `uses` lacks `heavy`
- **WHEN** `uv run pytest tests/corpus/test_manifest.py -m needs_corpus` runs
- **THEN** the test fails naming the row id

#### Scenario: File published malformed
- **GIVEN** the demo board at tag 9.0.9.1 whose published bytes close the root list early (a spliced line), listed with `uses = ["malformed", "origin:kicad-demos"]`
- **WHEN** `uv run pytest tests/corpus/test_rt0.py::test_malformed_items_rejected` runs with the file cached
- **THEN** the parser raises `FormatError` with the rule named in the row's `notes` (`content after the root list`), and the RT0 tests do not include the row

#### Scenario: Share-alike demo is not embeddable (regression case)
- **GIVEN** a demo row with `license = "CC-BY-SA-4.0"` and `embeddable = true`
- **WHEN** the manifest test runs
- **THEN** the existing embeddable rule fails it, stating that only CC0 or public-domain items may be embeddable

### Requirement: Corpus rows carry no names outside URLs
Vendor, product and project names SHALL appear only inside the `url` field of manifest rows and in the URLs of `docs/evidence/sources.md`. The id of every row whose `uses` contains `rt0` MUST match `^(kicad-demo-\d+(-\d+){2,3}|third-party)-(pcb|sch|sym|mod|fplib|wks)-\d{2,3}$`. `notes`, `docs/formats/kicad/corpus.md` and test output MUST describe rows by id, tag, format version and licence only.

#### Scenario: Named id rejected
- **GIVEN** an `rt0` row whose id is built from its demo folder name
- **WHEN** `uv run pytest tests/corpus/test_manifest.py` runs
- **THEN** the test fails naming the row and the expected pattern

#### Scenario: Three-digit id accepted
- **GIVEN** an `rt0` row with the id `kicad-demo-10-0-6-sch-104`
- **WHEN** the manifest test runs
- **THEN** it reports no id problem for that row

### Requirement: Selective fetch by use
`tools/corpus_fetch.py` SHALL accept `--uses TAG` (repeatable; an item is kept if it has any of the tags) and `--exclude-uses TAG` (repeatable; an item with any of the tags is dropped). It SHALL store each file under `<cache>/<id>/<name>`, where `<name>` is the URL-decoded last path segment of the URL.

#### Scenario: Heavy files skipped
- **GIVEN** a manifest with one `rt0` item and one `rt0` + `heavy` item
- **WHEN** `uv run python tools/corpus_fetch.py --uses rt0 --exclude-uses heavy` runs
- **THEN** only the first item is fetched and the summary counts one item

#### Scenario: Encoded space in a URL
- **GIVEN** an item whose URL path ends in `demo%20board.kicad_pcb`
- **WHEN** it is fetched
- **THEN** the cached file is named `demo board.kicad_pcb`

### Requirement: Derived corpus files stay out of the repository
Files derived from non-embeddable corpus items, such as copies re-saved by `kicad-cli pcb upgrade`, re-dumped by Fenolite, or cut out of a corpus board, MUST be written only under pytest's temporary directory or the corpus cache. They MUST NOT be committed, and they MUST NOT be used as fixtures or seeds. A residue test SHALL flag every `.kicad_*` file under `tests/data/` or `examples/` that is tree-equal to a cached corpus item, or that shares at least three identifier values with one. Identifier values are the atoms of `uuid` and `tstamp` lists, compared after lowercasing and removing `-` and leading zeros, and counted only when at least 8 hex digits remain.

#### Scenario: Partial copy committed
- **GIVEN** a file planted in `tmp_path` that holds one footprint cut out of a cached corpus board, with its identifiers
- **WHEN** `uv run pytest tests/residue/test_derived_corpus.py` runs with the corpus cache present
- **THEN** the detector reports the file and the corpus id

#### Scenario: Upgraded copy committed
- **GIVEN** `kicad-cli` 10.0.x and a copy of a cached corpus board upgraded with `pcb upgrade --force` into `tmp_path`
- **WHEN** the same test runs
- **THEN** the detector reports the upgraded copy, although it is not tree-equal to the original

#### Scenario: Authored fixture passes
- **GIVEN** the authored CC0 fixtures under `tests/data/kicad/sexpr/`
- **WHEN** the same test runs
- **THEN** none of them is reported

### Requirement: Upgraded copies keep their origin
A copy of a manifest row that `kicad-cli` 10.0.6 makes with `pcb upgrade --force` SHALL count as that row's origin (`origin:kicad-demos` or `origin:third-party`) when an evidence rule needs files from two or more origins, such as `CORPUS-VERIFIED`.
- The copy MUST be made through the package runner (`KicadCli.upgrade_board`), from the cached file. It MUST be kept only in memory or under `tmp_path`, and it MUST NOT be committed (requirement "Derived corpus files stay out of the repository").
- A test that uses such copies MUST carry `needs_corpus` and `kicad_min_major(10)`.
- A hypothesis row that relies on such copies MUST say so in its result.
- If review rejects this rule, the fallback is a search of at most 0.5 day for native permissive boards in format 8.0 or newer. The fallback registers them as new rows with a new source id and `embeddable = false`.

#### Scenario: Third-party origin through upgraded copies
- **GIVEN** the cached rows `third-party-pcb-01`, `-02` and `-03`, below the read floor, and `kicad-cli` 10.0.6
- **WHEN** `uv run pytest tests/kicad/board/test_board_upgraded.py -q` runs with `FENOLITE_REQUIRE=kicad,corpus`
- **THEN** each upgraded copy is read and checked as origin `third-party`, and `git status --porcelain` is unchanged afterwards

#### Scenario: Skipped on KiCad 9
- **GIVEN** the `kicad-9` job with `kicad-cli` 9.0.9 and `FENOLITE_REQUIRE=kicad`
- **WHEN** `uv run pytest tests/kicad/board/test_board_upgraded.py` runs
- **THEN** every test is skipped and none fails

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

### Requirement: RT2 rows for KiCad 9.0
`tests/corpus/manifest.toml` SHALL tag with the use `rt2-9` exactly the rows whose `ref` is `9.0.9.1`, whose URL names a `.kicad_pcb` file, and whose `uses` hold `rt0` and not `heavy`. Today these are `kicad-demo-9-0-9-1-pcb-01`, `-02`, `-03`, `-05` and `-06`; the malformed `-04` is not one of them.
- `tests/corpus/test_manifest.py` MUST fail, naming the row, when a row carries `rt2-9` without meeting this rule, or meets the rule without `rt2-9`.
- `rt2-9` rows MUST keep every other rule of the manifest (licence, `embeddable = false`, exactly one origin), and their files MUST stay out of the repository like every corpus file.
- `uv run python tools/corpus_fetch.py --uses rt2-9` MUST fetch exactly these rows. The `kicad-9` job fetches them together with the schematic rows of the 9.0.9.1 tree, in its only corpus fetch, `--uses rt2-9 --uses sch-9` (`ci-baseline`, "KiCad 9.0 oracle job"); a row MUST NOT carry `rt2-9` because it carries `sch-9`.

#### Scenario: Five rows tagged
- **WHEN** `uv run pytest tests/corpus/test_manifest.py` runs on the committed manifest
- **THEN** it passes, and exactly the five readable non-heavy 9.0.9.1 board rows carry `rt2-9`

#### Scenario: Wrong row tagged
- **GIVEN** a manifest in which `kicad-demo-10-0-6-pcb-01` also carries `rt2-9`
- **WHEN** the manifest test checks it
- **THEN** it fails naming `kicad-demo-10-0-6-pcb-01` and the use `rt2-9`

#### Scenario: Tag missing
- **GIVEN** a manifest in which `kicad-demo-9-0-9-1-pcb-03` lacks `rt2-9`
- **WHEN** the manifest test checks it
- **THEN** it fails naming `kicad-demo-9-0-9-1-pcb-03`

#### Scenario: Fetch by use
- **GIVEN** a temporary manifest with one `rt0` row and one `rt0` and `rt2-9` row
- **WHEN** `uv run python tools/corpus_fetch.py --manifest <it> --cache <tmp> --uses rt2-9` runs
- **THEN** only the second row is fetched, and the summary counts one item

### Requirement: Demo library corpus rows
`tests/corpus/manifest.toml` SHALL list, at tags 10.0.6 and 9.0.9.1, the `fp-lib-table` of every demo folder whose boards place a footprint through a `${KIPRJMOD}` row of that table, and every `.kicad_mod` file that such a board places through such a row. The files are found through S-0024.
- Every such row MUST carry `libs`, `rt0` and `origin:kicad-demos` in `uses`. It MUST set `license`, `license_variant` and `embeddable = false` as "KiCad demo and third-party board rows" requires, and its id MUST use the kind `fplib` or `mod` of "Corpus rows carry no names outside URLs". The existing rows `kicad-demo-10-0-6-fplib-01` and `kicad-demo-10-0-6-mod-01` gain `libs` when they qualify.
- A file identical at both tags MUST be listed once, under its 10.0.6 URL, with `notes` ending in `identical at tag 9.0.9.1 (commit <short id>).`, as the board rows do.
- A file that the parser rejects as fetched MUST NOT be listed. When more files qualify than two-digit ids allow (99 per kind and tag), demo folders MUST be taken in name order up to the limit, and `docs/formats/kicad/corpus.md` MUST record the cut.
- `tests/corpus/test_manifest.py` SHALL check that every row whose `uses` contains `libs` also contains `rt0` and `origin:kicad-demos`.
- `tests/corpus/test_demo_libs.py` (`needs_corpus`) SHALL rebuild each listed demo folder of each tag T in `tmp_path`. The rebuild places, at the path that the row's URL gives inside the demo folder, every `libs` row and every non-heavy `rt0` board row of that folder whose URL is at T or whose `notes` name T as identical. The test SHALL read each rebuilt board with c0009's board reader and resolve every footprint whose `lib_ref` nickname is a row of the rebuilt `fp-lib-table`. It SHALL resolve through a `LibraryResolver` whose `project_dir` is the rebuilt folder, whose `config_home` is an empty folder, whose `env` is empty and whose `install_dir` does not exist. Any failure MUST fail the test. Footprints of other nicknames MUST be counted by issue code, and the counts written only to the report file named by `FENOLITE_CENSUS_OUT`.

#### Scenario: Library row without rt0
- **GIVEN** a row `kicad-demo-10-0-6-mod-02` with `uses = ["libs", "origin:kicad-demos"]`
- **WHEN** `uv run pytest tests/corpus/test_manifest.py` runs
- **THEN** the test fails naming the row and `rt0`

#### Scenario: Demo projects resolve their own footprints
- **GIVEN** the cached `libs` rows and board rows, with `FENOLITE_REQUIRE=corpus`
- **WHEN** `uv run pytest tests/corpus/test_demo_libs.py` runs
- **THEN** every footprint of a rebuilt board whose nickname is a row of its project table resolves at both tags, and `git status --porcelain` is unchanged afterwards

#### Scenario: Other nicknames are counted
- **GIVEN** a rebuilt demo board that also places footprints of an official library, and `FENOLITE_CENSUS_OUT` naming a file under a temporary folder
- **WHEN** the same test runs
- **THEN** those footprints are counted under `kicad.lib.unknown-nickname` in that file, and the test passes

#### Scenario: Rows fetched by use
- **GIVEN** the manifest with `libs` rows
- **WHEN** `uv run python tools/corpus_fetch.py --uses libs` runs
- **THEN** only rows whose `uses` contains `libs` are fetched, and the summary counts them

### Requirement: Second-backend corpus rows
`tests/corpus/manifest.toml` SHALL list the public files written by the second backend's own tool that Fenolite's readers are measured on. The files are fetched by `tools/corpus_fetch.py` and never committed.
- **Ids.** A row's id MUST match `^altium-third-party-(schdoc|schlib|pcbdoc|pcblib|prjpcb|outjob|harness|rules|stackup|schdot)-\d{2}$`. This is the only id form for a file written by the second backend's tool. A later change MUST take the next free number of the kind, MUST NOT renumber a row, and MUST NOT list a URL twice: it adds its use to the row that holds the URL. As "Corpus rows carry no names outside URLs" requires, `notes` MUST describe a row by its source id (`S-NNNN`), the kind, the size in bytes and the year it was saved, and by nothing else.
- **Pinned.** `ref` MUST be a 40-digit commit, and `url` MUST contain that commit. A file kept in Git LFS MUST use the host's media URL for that commit, so the fetched bytes are the file and not a pointer.
- **Licence.** `license` MUST be the SPDX identifier of the licence file of the repository at that commit, which MUST permit the use and MUST be registered with the row's source id in `docs/evidence/sources.md`. A repository without a licence file, or with a non-commercial clause, MUST NOT be listed. `embeddable` MUST be `false`.
- **Uses.** `uses` MUST hold `altium` and `origin:third-party`, and MUST NOT hold `rt0`, `malformed` or `project`. A row read by the compound-file census also holds `cfb`; only the rows that this requirement counts hold it. Later changes add their own tags. A file larger than 20 MB MUST also hold `heavy`.
- **Origins.** Every such row has the origin `third-party`. An evidence rule that needs two or more origins MUST, for these rows, count distinct repositories and need at least three.
- **Counts only.** Test output and pages MUST report ids, counts, key names and sizes, never a part name, a net name or another value of a file.
- `tests/corpus/test_manifest.py` SHALL enforce the id pattern, the pinned `ref` and `url`, `embeddable = false` and the required and forbidden uses for every row whose `uses` holds `altium`.
- Change c0039 lists ten rows with `uses` `altium`, `cfb`: four PCB documents, two PCB libraries and four schematic documents, from five repositories (S-0170, S-0172, S-0176, S-0187, S-0188, S-0199). One of them, `altium-third-party-pcbdoc-01`, uses DIFAT sectors.

#### Scenario: Named id rejected
- **GIVEN** a row with `uses = ["altium", "cfb", "origin:third-party"]` whose id is built from its repository name
- **WHEN** `uv run pytest tests/corpus/test_manifest.py` runs
- **THEN** the test fails naming the row and the expected pattern

#### Scenario: Branch reference rejected
- **GIVEN** an `altium` row whose `ref` is `master`
- **WHEN** the manifest test runs
- **THEN** it fails stating that the row needs a 40-digit commit that its `url` contains

#### Scenario: Round-trip tag refused
- **GIVEN** an `altium` row whose `uses` also holds `rt0`
- **WHEN** the manifest test runs
- **THEN** it fails naming the row and the forbidden use

#### Scenario: Fetch by use
- **GIVEN** the manifest with the ten rows of change c0039
- **WHEN** `uv run python tools/corpus_fetch.py --uses cfb` runs
- **THEN** only those rows are fetched, each file's SHA-256 is verified, and the summary counts ten items

#### Scenario: Rows of the compound-file census
- **WHEN** `uv run pytest tests/corpus/test_manifest.py -k altium` runs on the committed manifest
- **THEN** it finds ten rows with `altium` and `cfb`, from at least three repositories, all with `embeddable = false`

### Requirement: Altium schematic corpus rows
`tests/corpus/manifest.toml` SHALL contain rows for public schematic documents and schematic libraries that Altium Designer saved, for the schematic reader (`altium-schematic-reader`). Every such row follows "Second-backend corpus rows" (change c0039): its id pattern, the pinned commit in `ref` and `url`, the licence rule, `embeddable = false`, the uses `altium` and `origin:third-party`, and notes without names.
- A schematic document row MUST also carry the use `altium-sch`, and a schematic library row the use `altium-schlib`. A row MUST NOT carry both.
- The four schematic rows that change c0039 lists (`altium-third-party-schdoc-01` to `-04`) MUST gain `altium-sch`; no second row is added for a URL that a row already lists.
- A later change MAY add rows with these tags (c0046 adds three `schdot` rows with `altium-sch`); the counts of this requirement are those of changes c0039 and c0040.
- This change adds nine schematic rows, `altium-third-party-schdoc-05` to `-13`: the other four sheets of the design of S-0188, the other four of S-0187, and one sheet of S-0279. It adds nine library rows, `altium-third-party-schlib-01` to `-09`: six of S-0277, two of S-0278 and one of S-0279.
- The rows with `altium-sch` MUST come from at least three repositories, and so MUST the rows with `altium-schlib`.
- `tests/corpus/test_manifest.py` SHALL check, for every row with `altium-sch` or `altium-schlib`, that it holds `altium`, that its id kind is `schdoc` or `schdot` for `altium-sch` and `schlib` for `altium-schlib`, and that each tag covers three repositories, counted by the host and the first two path segments of `url`.
- The files are measurement material: "Measurement versus embedding" and "Derived corpus files stay out of the repository" apply to them and to every file derived from them, such as the KiCad libraries that `kicad-cli sym upgrade` writes and the ASCII files rewritten from their records.

#### Scenario: Tag on the wrong kind
- **GIVEN** a row `altium-third-party-pcblib-01` whose `uses` holds `altium-schlib`
- **WHEN** `uv run pytest tests/corpus/test_manifest.py` runs
- **THEN** the test fails naming the row and the kinds the tag allows

#### Scenario: Tag without the family use
- **GIVEN** a row with `uses = ["altium-sch", "origin:third-party"]`
- **WHEN** the manifest test runs
- **THEN** it fails stating that the row needs `altium`

#### Scenario: Two repositories only
- **GIVEN** a manifest whose `altium-schlib` rows come from two repositories
- **WHEN** the manifest test runs
- **THEN** it fails stating that library rows need three repositories

#### Scenario: Fetch by use
- **GIVEN** the manifest with the rows of changes c0039 and c0040
- **WHEN** `uv run python tools/corpus_fetch.py --uses altium-sch --uses altium-schlib` runs
- **THEN** 13 schematic rows and 9 library rows are fetched and verified by SHA-256, and the summary counts 22 items

### Requirement: Altium project sets
`tests/corpus/manifest.toml` SHALL mark the rows of one public Altium project as a set, so that the import of change c0043 can read a project's sheets and its PCB document together. This requirement extends "Second-backend corpus rows" (c0039), whose rules hold for every row of a set.
- A set is the rows that carry the use `altium-set:<nn>`, `<nn>` two digits. A set MUST hold exactly one project file row (`altium-third-party-prjpcb-NN`), exactly one PCB document row, and every schematic sheet that the project file lists. All rows of a set MUST come from one repository at one commit and MUST carry one licence.
- Every row of a set MUST also carry the use `altium-import`. The use `altium-import:known-diff` MAY be added to the project file row of a set whose sheets and PCB document disagree; its `notes` MUST then add, after the usual four fields, a sentence `Known difference: …` that gives the cause in lower-case words, row ids and counts only; the use and that sentence go together.
- Change c0043 adds no file of a new kind: it tags rows that c0039 to c0042 list and adds the sheets, project files and PCB documents that those changes do not list for the chosen projects. Each added row follows the id pattern, the pinned commit and the licence rule of c0039, with its source id registered, takes the next free number of its kind, and carries only `altium`, `origin:third-party` and the set uses: it carries none of `cfb`, `altium-sch`, `altium-pcbdoc` and `altium-text`, so the row counts that c0039 to c0042 state still hold.
- The sets MUST come from at least three repositories when they support a `CORPUS-VERIFIED` label; with fewer, the label is not given. The manifest holds five sets from five repositories (S-0187, S-0188, S-0174, S-0176, S-0175); S-0305 stays unused.
- `tools/corpus_fetch.py --uses altium-import` MUST fetch exactly the rows of the sets.
- `tests/corpus/test_manifest.py` SHALL check, for every `altium-set` use: one project file row and one PCB document row, one repository, one commit and one licence over the set, and `altium-import` on every row.
- Nothing read from a set, and nothing derived from it, is committed.

#### Scenario: Set without a PCB document
- **GIVEN** rows that carry `altium-set:01`, among them a project file and four sheets but no PCB document
- **WHEN** `uv run pytest tests/corpus/test_manifest.py -k altium_set` runs
- **THEN** it fails naming the set and the missing kind

#### Scenario: Set from two commits
- **GIVEN** a set whose sheets are pinned to one commit and whose PCB document to another
- **WHEN** the manifest test runs
- **THEN** it fails naming the set and the two commits

#### Scenario: Fetch of the sets
- **WHEN** `uv run python tools/corpus_fetch.py --uses altium-import` runs
- **THEN** only rows with an `altium-set` use are fetched, and each file's SHA-256 is verified

### Requirement: Schematic corpus rows
`tests/corpus/manifest.toml` SHALL contain one row per distinct `.kicad_sch` under `demos/` of the KiCad source repository at tags 10.0.6 and 9.0.9.1, and one row for each of the two S-expression schematics that the third-party repositories of S-0027 and S-0028 hold at their pinned commits. A file whose SHA-256 is identical at both tags is listed once, and `notes` names the other tag and the tag commit.
- **Ids.** New demo rows MUST have ids `kicad-demo-<tag>-sch-NNN` with three digits, and the third-party rows `third-party-sch-01` and `third-party-sch-02`. The row `kicad-demo-10-0-6-sch-01` keeps its id.
- **Uses.** Every row MUST carry `rt0`, `sch` and exactly one origin, and these content tags, computed from the file and its project:
  - `sch-root`: a project file of the same stem exists beside it at the same tag;
  - `sch-bus`: the file holds a `bus`, `bus_entry` or `bus_alias` child, or a label whose text is a bus (a vector `NAME[m..n]` or a group in braces);
  - `sch-multi`: the file holds a symbol with more than one use under one project, or more than one sheet reference of its project names it;
  - `sch-old`: its format version is below `READ_FLOOR[FileKind.SCHEMATIC]`;
  - `sch-9`: the file is in the demos at tag 9.0.9.1 (every row of that tag, and every row of tag 10.0.6 that is identical there). This tag is not recomputed from the file: it follows from the two tree listings (S-0024).
- **Licence.** Every row MUST set `license`, `license_variant` and `embeddable = false` as "KiCad demo and third-party board rows" requires, and a demo folder whose licence carries a non-commercial clause MUST NOT be listed.
- **Census.** `tests/corpus/test_schematic_census.py` (marker `needs_corpus`) MUST recompute the four content tags of every `sch` row from the cached files and MUST fail naming the row id when a tag is missing or wrong. It MUST write, through `tests/_boards.py::census`, the number of rows per tag, per format version and per origin, the root heads with their counts, and the number of rows that carry none of `sch-bus`, `sch-multi` and `sch-old`; the numbers are copied into `docs/evidence/kicad-schematic.md`.
- **Acceptance list.** The rows that carry `sch` and none of `sch-bus`, `sch-multi` and `sch-old` are the "schematics without bus and without multi-instance" of the project plan's v0.2a acceptance; no second list is kept.
- **Round trips.** `tests/corpus/test_schematic_rt.py` (marker `needs_corpus`) MUST run RT0 (`tree_equal(parse(dumps(parse(t))), parse(t))`) and RT1 (`sch.roundtrip_schematic`) on every demo row without `sch-old`, bus or not, and MUST record `opaque_count` per row. A row with `sch-old` MUST be counted as not read, with its format version.
- **Fetch.** The `kicad-10` job fetches the `sch` rows through its existing `--uses rt0` selection. The `kicad-9` job fetches the rows of the 9.0.9.1 tree with `--uses sch-9`, beside its `rt2-9` rows (`ci-baseline`, "KiCad 9.0 oracle job").

#### Scenario: Tags recomputed
- **GIVEN** the `sch` rows cached, and a manifest in which one row with bus entries lacks `sch-bus`
- **WHEN** `uv run pytest tests/corpus/test_schematic_census.py` runs
- **THEN** it fails naming that row id and `sch-bus`

#### Scenario: Round trips over the demo rows
- **GIVEN** the `sch` rows cached
- **WHEN** `uv run pytest tests/corpus/test_schematic_rt.py -rA` runs with `FENOLITE_CENSUS_OUT` set
- **THEN** every demo row without `sch-old` passes RT0 and RT1, rows with `sch-old` are counted with their format version, and the census file holds one `opaque_count` per row read

#### Scenario: Acceptance list is a query
- **WHEN** the manifest rows with `sch` and without `sch-bus`, `sch-multi` and `sch-old` are selected
- **THEN** the selection is not empty, and each selected row passed RT0 and RT1 in the census

#### Scenario: Nothing derived is committed
- **WHEN** the two corpus tests have run
- **THEN** `git status --porcelain` and the SHA-256 of every cached file are unchanged

### Requirement: Upgraded schematic copies keep their origin
A copy of a `sch` row that `kicad-cli` 10.0.6 makes with `sch upgrade --force` SHALL count as that row's origin when an evidence rule needs files from two or more origins, under the conditions of "Upgraded copies keep their origin": made through the package runner (`KicadCli.upgrade_schematic`) from the cached file, kept only in memory or under `tmp_path`, never committed, used only by tests that carry `needs_corpus` and `kicad_min_major(10)`, and named as such in the result of the hypothesis row that relies on it.

#### Scenario: Third-party origin through upgraded copies
- **GIVEN** the cached rows `third-party-sch-01` and `-02`, below the read floor, and `kicad-cli` 10.0.6
- **WHEN** `uv run pytest tests/kicad/schematic/test_schematic_upgraded.py -q` runs with `FENOLITE_REQUIRE=kicad,corpus`
- **THEN** each upgraded copy is read and checked as origin `third-party`, and `git status --porcelain` is unchanged afterwards

