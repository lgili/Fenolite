## MODIFIED Requirements

### Requirement: No shipped requirement values
Fenolite SHALL ship no requirement value for `analyze`: no voltage-to-distance table, pollution degree, material group or altitude factor, and no default temperature rise, copper, plating or board thickness, or current. `src/fenolite/analysis/` MUST hold no data file, and the fit's only constants MUST be those of "Capacity fit". Example requirement files MUST be authored with round illustrative numbers and say so. The role profile of `net-roles` is the one exception and never feeds `analyze`.

#### Scenario: No data files
- **WHEN** `uv run pytest tests/unit/analysis/test_facts_page.py -k no_data` lists `src/fenolite/analysis/`
- **THEN** it holds only `.py` files, and `load_requirements` has no default document

#### Scenario: Example is marked as authored
- **WHEN** the same test reads `tests/data/analysis/requirements_example.toml`
- **THEN** its first comment line holds the words `authored for Fenolite; illustrative values, not requirements`

#### Scenario: Analyze ignores the role profile
- **GIVEN** a board with a 0.3 mm track on a net and no requirements file
- **WHEN** `fenolite analyze <board> --kinds current --temp-rise 10 --copper-thickness 35um --json` runs
- **THEN** no issue is a finding against a width, and no `roles.*` code is reported
