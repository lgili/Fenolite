## ADDED Requirements

### Requirement: KiCad to Altium closes the measured losses
`fenolite convert --to altium` SHALL write every KiCad 10.0.6 demo board of the corpus, and its report SHALL lose no pad for a per-layer stack of plain shapes, a connector pad or a pad without a number, and no drawing or text on a layer of `lower.KICAD_MECHANICAL` or on a copper layer. `docs/evidence/conversion.md` MUST hold, per board, the counts per kind and reason before and after this change.

#### Scenario: Census after the change
- **WHEN** `uv run pytest tests/corpus/test_convert_census.py -rA` runs with the corpus cached
- **THEN** all 18 demo boards are written, no board gives `convert.unexplained`, and the lost `pad` rows hold only custom shapes

#### Scenario: Part T recorded
- **GIVEN** the maintainer's author report of Part T in `docs/evidence/altium-pcb.md`
- **WHEN** `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_provenance.py` runs
- **THEN** the rows of this change name the report with the tool, the date and no artefact, and no write kind is marked out of `experimental`
