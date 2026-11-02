## ADDED Requirements

### Requirement: Drawn effects remain observable
Level S SHALL compare target-probed effective fonts and text effects as drawn content. Scene extraction MUST preserve supported effects or report unsupported rendering, including positive sub-µm sizes that round to zero. It MUST NOT substitute default size or relax thresholds, sheet matching, geometry, junction checks or losses.

#### Scenario: Planted font change
- **GIVEN** equal authored drawings
- **WHEN** one explicit font size changes
- **THEN** level S reports the changed effect and level 8 retains its unchanged comparison rules

#### Scenario: Redundant junction removed
- **GIVEN** an authored drawing with an electrically redundant junction at a wire endpoint
- **WHEN** that junction is removed
- **THEN** the connectivity guard can pass but level S still reports the missing junction

#### Scenario: Positive size below scene resolution
- **GIVEN** an exact positive size below one micrometre
- **WHEN** its scene is extracted
- **THEN** a supported exact representation or explicit unsupported-render finding replaces silent default-size substitution
