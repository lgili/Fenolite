## ADDED Requirements

### Requirement: Library items in the corpus
A test that needs a `fenolite-library` item SHALL fetch it through a `tests/corpus/manifest.toml` row whose `url` is the release asset, `ref` the release tag, `sha256` the archive digest, `license` the item's SPDX id, and `uses` holds `origin:third-party` and `library:<kind>/<id>@<version>`. Such a row MUST be `embeddable = false` unless the id is `CC0-1.0`, and no item, item `PROVENANCE.json` or vendored `fenolite_library/` folder MAY be committed.

#### Scenario: Share-alike library row marked embeddable
- **GIVEN** a manifest row with `uses = ["origin:third-party", "library:footprint/Demo:SA_PAD@1.0.0"]`, `license = "CC-BY-SA-4.0"` and `embeddable = true`
- **WHEN** `uv run pytest tests/corpus/test_manifest.py` runs
- **THEN** the test fails naming the row id

#### Scenario: Vendored item committed
- **GIVEN** a file `examples/x/fenolite_library/devices/Demo/EXB/PROVENANCE.json` of schema `fenolite.provenance.v0` with `origin = "converted"`
- **WHEN** `uv run pytest tests/residue` runs
- **THEN** the test fails naming the file
