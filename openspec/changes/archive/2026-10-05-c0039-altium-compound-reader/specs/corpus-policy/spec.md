## ADDED Requirements

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
