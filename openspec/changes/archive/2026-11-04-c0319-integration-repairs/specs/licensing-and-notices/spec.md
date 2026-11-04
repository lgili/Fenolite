## ADDED Requirements

### Requirement: Python headers follow the licensed role
Every Python file MUST begin with SPDX and copyright lines. Core implementation
SHALL use Apache-2.0; explicitly authored CC0 fixture and usage data SHALL retain
CC0-1.0. Header checks MUST validate the licensed role without permitting an
arbitrary licence in core code or weakening fixture authorship requirements.

#### Scenario: Authored executable data
- **GIVEN** an explicitly CC0-authored fixture or shipped usage design
- **WHEN** the repository header proof runs
- **THEN** its SPDX/copyright header and authored-data role pass without changing its dedication

#### Scenario: Unexpected core licence
- **WHEN** implementation code declares a licence outside its permitted role
- **THEN** the header proof fails
