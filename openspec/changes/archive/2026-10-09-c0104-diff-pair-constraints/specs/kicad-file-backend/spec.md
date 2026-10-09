## ADDED Requirements

### Requirement: Net class pair values in project files
The class keys `diff_pair_width`, `diff_pair_gap` and `diff_pair_via_gap` SHALL be lowered values of a model class, as `clearance`, `track_width`, `via_diameter` and `via_drill` are. This requirement takes those three keys out of the template-value rule and the keep rule of "Project files are synthesised and preserved", as that requirement allows, and extends "Project files are read into the model".
- **Synthesis.** Each model class MUST be written with its pair values by `lower_netclass` (`rules-model`, "Net classes lower to the project file"), a value that is `None` keeping the value of the `Default` entry. A model class named `Default` MUST update the seven lowered values of the first entry.
- **Update.** `update_project` MUST replace the seven lowered values of each class entry whose name matches a model class, keeping the original text of a value that is equal in nanometres, and MUST leave a pair key untouched when the model value is `None`.
- **Reading.** `ProjectClass` MUST hold `diff_pair_width`, `diff_pair_gap` and `diff_pair_via_gap` in nm, read as its four other values are (a value that is not a whole number of nm reads as `None` with the info `kicad.project.inexact-value`), and `apply_project` MUST copy them into each `NetClass`.
- The templates of both targets hold the three keys in every class entry, so both targets write them and no key path is added to the template's (`H-K-PRO-VERSION`).

#### Scenario: Synthesis writes pair values
- **GIVEN** a design with the class `USB` (`diff_pair_gap` 150 000 nm, `diff_pair_width` 300 000 nm) holding the nets `USB_P` and `USB_N`
- **WHEN** `synthesize_project(design, target=9, board_name="b")` is called
- **THEN** the `USB` entry has `diff_pair_gap == JsonNumber("0.15")`, `diff_pair_width == JsonNumber("0.3")` and the template's `diff_pair_via_gap`, and the `Default` entry keeps the template's three values

#### Scenario: Update keeps an equal spelling
- **GIVEN** a target-10 project text (`meta.version` 3, `net_settings.meta.version` 5) whose class `USB` has `diff_pair_gap` written `0.150` and `diff_pair_width` written `0.2`
- **WHEN** it is updated with `USB` at `diff_pair_gap=150_000` and `diff_pair_width=None`
- **THEN** `diff_pair_gap` is still `JsonNumber("0.150")` and `diff_pair_width` is still `JsonNumber("0.2")`

#### Scenario: Pair values read back
- **GIVEN** the project of "Synthesis writes pair values"
- **WHEN** it is read with `read_project` and applied with `apply_project`
- **THEN** the model class `USB` has `diff_pair_gap == 150_000`, `diff_pair_width == 300_000` and the template's `diff_pair_via_gap` in nm, and `Default` has the template's three values
