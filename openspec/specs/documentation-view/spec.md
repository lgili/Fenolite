# documentation-view Specification

## Purpose
The viewer opens the documentation of an Altium project: ActiveBOM documents as a BOM built from the project's parts, output jobs as the list of their outputs, and the side views and callouts of Draftsman drawings (change c0190).

## Requirements

### Requirement: Output jobs
An `.OutJob` SHALL open as the list of its outputs with their name, type, bound documents and output folder, and a bound document of the project SHALL open from it.

#### Scenario: Public output jobs
- **GIVEN** the `altium-third-party-outjob-*` rows of the corpus cache
- **WHEN** `uv run pytest tests/unit/view/test_documentation.py -k outjob` builds their scenes
- **THEN** each scene lists every output of its file with its name, type and output folder
