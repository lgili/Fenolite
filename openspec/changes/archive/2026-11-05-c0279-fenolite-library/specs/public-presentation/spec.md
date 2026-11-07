## ADDED Requirements

### Requirement: Third-party material in public assets
Fenolite's README, site and launch material SHALL show third-party boards and other third-party-derived items only as images of the `fenolite-library` gallery, each with its attribution line (title, authors, upstream link, SPDX id, "Not endorsed by the authors"). An item by an organisation MUST have `featured` permission recorded in its `PROVENANCE.json` before such use.

#### Scenario: Image without attribution
- **GIVEN** a public asset list that names a gallery image of a converted board without its attribution line
- **WHEN** `uv run pytest tests/unit/test_public_presentation.py -k library` runs
- **THEN** the test fails naming the image
