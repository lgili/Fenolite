## ADDED Requirements

### Requirement: RT2 rows for KiCad 9.0
`tests/corpus/manifest.toml` SHALL tag with the use `rt2-9` exactly the rows whose `ref` is `9.0.9.1`, whose URL names a `.kicad_pcb` file, and whose `uses` hold `rt0` and not `heavy`. Today these are `kicad-demo-9-0-9-1-pcb-01`, `-02`, `-03`, `-05` and `-06`; the malformed `-04` is not one of them.
- `tests/corpus/test_manifest.py` MUST fail, naming the row, when a row carries `rt2-9` without meeting this rule, or meets the rule without `rt2-9`.
- `rt2-9` rows MUST keep every other rule of the manifest (licence, `embeddable = false`, exactly one origin), and their files MUST stay out of the repository like every corpus file.
- `uv run python tools/corpus_fetch.py --uses rt2-9` MUST fetch exactly these rows. It is the only corpus fetch of the `kicad-9` job (`ci-baseline`, "KiCad 9.0 oracle job").

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
