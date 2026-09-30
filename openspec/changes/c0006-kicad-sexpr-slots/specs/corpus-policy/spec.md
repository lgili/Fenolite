## ADDED Requirements

### Requirement: KiCad demo and third-party board rows
`tests/corpus/manifest.toml` SHALL contain the following rows:
- one row per distinct `.kicad_pcb` under `demos/` of the KiCad source repository at tags 10.0.6 and 9.0.9.1. A file whose SHA-256 is identical at both tags is listed once, and `notes` names the other tag and the tag commit.
- one schematic, one symbol library, one footprint, one footprint-library table and one worksheet from the demos at 10.0.6
- the Apache-2.0 third-party boards registered as sources S-0027 and S-0028

Every row MUST set `license` from the repository-level statement. It MUST record any per-folder licence in `license_variant`, and it MUST set `embeddable = false`. A demo folder whose licence carries a non-commercial clause MUST NOT be listed. Every row MUST carry `rt0` and exactly one of `origin:kicad-demos` and `origin:third-party` in `uses`. Board rows MUST also carry `oracle`, and files larger than 20 MB MUST also carry `heavy`.

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

#### Scenario: Share-alike demo is not embeddable (regression case)
- **GIVEN** a demo row with `license = "CC-BY-SA-4.0"` and `embeddable = true`
- **WHEN** the manifest test runs
- **THEN** the existing embeddable rule fails it, stating that only CC0 or public-domain items may be embeddable

### Requirement: Corpus rows carry no names outside URLs
Vendor, product and project names SHALL appear only inside the `url` field of manifest rows and in the URLs of `docs/evidence/sources.md`. The id of every row whose `uses` contains `rt0` MUST match `^(kicad-demo-\d+(-\d+){2,3}|third-party)-(pcb|sch|sym|mod|fplib|wks)-\d{2}$`. `notes`, `docs/formats/kicad/corpus.md` and test output MUST describe rows by id, tag, format version and licence only.

#### Scenario: Named id rejected
- **GIVEN** an `rt0` row whose id is built from its demo folder name
- **WHEN** `uv run pytest tests/corpus/test_manifest.py` runs
- **THEN** the test fails naming the row and the expected pattern

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
