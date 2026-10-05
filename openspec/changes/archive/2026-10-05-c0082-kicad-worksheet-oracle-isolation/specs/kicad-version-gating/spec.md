## ADDED Requirements

### Requirement: Isolated worksheet version oracle

The worksheet version boundary oracle SHALL run every version probe on fresh input copies with a private KiCad configuration directory and the C locale, without inheriting KICAD settings. Every probe SHALL also receive private home, cache, data and temporary directories, including its instance-lock location. Each probe SHALL finish successfully and produce an SVG. The next-version probe SHALL require both the drawing-sheet loading error and the more-recent-version diagnostic, without retrying or skipping failures.

#### Scenario: Accepted worksheet version

- **WHEN** the worksheet uses the recorded version constant for the installed KiCad major
- **THEN** an isolated export produces an SVG without a drawing-sheet loading error

#### Scenario: Future worksheet version

- **WHEN** the worksheet version is one greater than the recorded constant
- **THEN** a separate isolated export reports both `Error loading drawing sheet` and `more recent version`, and produces the fallback SVG
