## ADDED Requirements

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
