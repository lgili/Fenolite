## ADDED Requirements

### Requirement: Round-trip use on Altium rows
`tests/corpus/manifest.toml` SHALL tag with the use `rta` exactly the rows whose URL path ends, in any letter case, in `.SchDoc`, `.SchLib`, `.PcbDoc`, `.PcbLib` or `.PrjPcb`, and whose `uses` do not hold `malformed`. These are rows that c0039 to c0043 add; this change adds no row of its own unless "Altium project sets" (`corpus-policy`, c0043; the use `altium-set:<nn>`) holds fewer than three sets, in which case task 1.3 adds the project file, the schematic documents and the PCB document of the missing sets from the sources S-0245 to S-0247. A file that a row already lists MUST be reused by adding the set uses to that row; a new row takes the next free number of its kind ("Second-backend corpus rows") and carries only `altium`, `origin:third-party`, the set uses and `rta`.
- `tests/corpus/test_manifest.py` MUST fail, naming the row, when a row carries `rta` without meeting this rule, or meets the rule without `rta`.
- `rta` rows MUST keep every other rule of the manifest and of the requirement that added them (licence, pinned commit, `embeddable = false`, names only in the URL), and their files MUST stay out of the repository like every corpus file.
- Test output and `docs/evidence/altium-roundtrip.md` MUST name rows by id, kind, size and licence only, and MUST report counts, stream names and record numbers, never a value of a record.
- `uv run python tools/corpus_fetch.py --uses rta` MUST fetch exactly these rows. A row that also holds `heavy` is fetched and run only when `--exclude-uses heavy` is not given.

#### Scenario: Every Altium row tagged
- **WHEN** `uv run pytest tests/corpus/test_manifest.py -k rta` runs on the committed manifest
- **THEN** it passes, and every row whose URL ends in one of the five suffixes carries `rta`

#### Scenario: Tag on a KiCad row
- **GIVEN** a manifest in which `kicad-demo-10-0-6-pcb-01` also carries `rta`
- **WHEN** the manifest test checks it
- **THEN** it fails naming `kicad-demo-10-0-6-pcb-01` and the use `rta`

#### Scenario: Tag missing
- **GIVEN** a manifest in which one row whose URL ends in `.PcbDoc` lacks `rta`
- **WHEN** the manifest test checks it
- **THEN** it fails naming that row

#### Scenario: Fetch by use
- **GIVEN** a temporary manifest with one `rt0` row and one `rta` row
- **WHEN** `uv run python tools/corpus_fetch.py --manifest <it> --cache <tmp> --uses rta` runs
- **THEN** only the `rta` row is fetched, and the summary counts one item
