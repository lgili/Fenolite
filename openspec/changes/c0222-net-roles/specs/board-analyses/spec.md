## MODIFIED Requirements

### Requirement: No shipped requirement values
Fenolite SHALL ship no requirement value: no table from voltage to distance, no pollution degree, material group or altitude factor, no default temperature rise, copper thickness, plating thickness or board thickness, and no default current. `src/fenolite/analysis/` MUST hold no data file, and the only numeric constants of the capacity fit MUST be those of the table "Capacity fit". Example requirement files in tests and docs MUST be authored for Fenolite with round illustrative numbers, and MUST say so in a comment. The one exception is the role profile of `net-roles` (`fenolite.roles.profile`), which lives outside `src/fenolite/analysis/`, serves only `fenolite roles --check` and the stage `roles.rules`, and is never read by `fenolite analyze`; a row that `fenolite.roles` derives from it and passes to an analysis function MUST NOT give an `analysis.*` finding.

#### Scenario: No data files
- **WHEN** `uv run pytest tests/unit/analysis/test_facts_page.py -k no_data` lists `src/fenolite/analysis/`
- **THEN** it holds only `.py` files, and `load_requirements` has no default document

#### Scenario: Example is marked as authored
- **WHEN** the same test reads `tests/data/analysis/requirements_example.toml`
- **THEN** its first comment line holds the words `authored for Fenolite; illustrative values, not requirements`

#### Scenario: Analyze ignores the role profile
- **GIVEN** a board with a 0.3 mm track on a net confirmed as a 2 A `power` role, and no requirements file
- **WHEN** `uv run pytest tests/unit/analysis/test_facts_page.py -k role_profile` runs `fenolite analyze <board> --kinds current,power,necks --temp-rise 10 --copper-thickness 35um --json`
- **THEN** no issue is a finding against a width, a section or a neck, no `roles.*` code is reported, and no module of `src/fenolite/analysis/` imports `fenolite.roles`
