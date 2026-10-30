## ADDED Requirements

### Requirement: Enclosure templates command
`fenolite enclosure templates PATH --out DIR [--faces LIST] [--formats LIST] [--enclosure FILE] [--timestamp T]` SHALL plan `<face>.svg`, `<face>.pdf` and `<face>.dxf` per selected face through the mutation protocol, all or none, after running the enclosure judge on those faces. An `enclosure.aperture-off-face` error MUST plan no write and exit 5; a missing record MUST exit 3 with `FEN-3001`.

#### Scenario: An aperture off its face
- **GIVEN** the example with `J1`'s aperture raised so that it leaves the front's flat rectangle
- **WHEN** `uv run pytest tests/unit/cli/test_enclosure_templates.py -k off_face` runs `fenolite enclosure templates <dir> --out tpl --dry-run --json`
- **THEN** the exit code is 5, the issues hold `enclosure.aperture-off-face` naming `J1`, and `result.plan` is empty

#### Scenario: Faces and receipt
- **WHEN** the command runs on the example with `--faces front,back --confirm`
- **THEN** it writes six files, `back` gets `enclosure.template-empty`, and the receipt lists each file with its SHA-256
