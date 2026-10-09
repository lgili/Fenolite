## ADDED Requirements

### Requirement: Differential pairs in design files
`backends.specctra.dsn.write_dsn` SHALL write no `pair` list: the two nets of a differential pair are written as two nets, as every other net. `docs/formats/specctra/dsn.md` SHALL record, in Fenolite's own words, that the reference describes a `pair` list in the network section naming two nets (S-0224), and that Freerouting 2.4.1 writes the same routes for a design file with such lists, with or without a rule inside them, as for the file without them (`H-G-DSN-PAIR`, labelled by the outcome `dsn-pair-ignored`).
- A later pin of Freerouting MUST run the probe again before the writer emits the list; the writer emits it only after a recorded outcome shows routes coupled at the pair's gap.

#### Scenario: No pair list
- **GIVEN** an authored design with the nets `USB_P` and `USB_N` in a class with pair values, both selected
- **WHEN** `uv run pytest tests/unit/backends/specctra/test_dsn.py -k pair` calls `write_dsn`
- **THEN** the parsed network section holds the two nets and no list whose head is `pair`

#### Scenario: Fact row
- **WHEN** `uv run pytest tests/unit/test_format_facts.py` runs
- **THEN** it passes with the row of the `pair` list in `docs/formats/specctra/dsn.md`, whose hypothesis is `H-G-DSN-PAIR`
