## ADDED Requirements

### Requirement: Net classes lower to the project file
`fenolite.backends.kicad.lowering.lower_netclass(cls, *, base, floors, issues=None)` SHALL return a new `net_settings.classes` entry for the model `NetClass` `cls`: a copy of `base`, the `Default` entry of the project being written, with `name` set to `cls.name` and the four modelled values written.
- `clearance`, `track_width`, `via_diameter` and `via_drill` MUST map to the class keys of the same names. Each MUST be written as a `JsonNumber` holding the exact millimetre text of the nanometre value (`format_length(nm, "mm")` without the unit), and MUST keep the base value when the model field is `None`. No float MUST be produced.
- Every other key of `base` (microvia, differential pair, colours, `priority`, line style, and `tuning_profile` when present) MUST be copied unchanged.
- A non-empty `description` MUST add the info `kicad.project.unlowered-field`, because no project key holds it.
- `floors` maps model fields to the nanometre values of `board.design_settings.rules` (`min_clearance`, `min_track_width`, `min_via_diameter`, `min_through_hole_diameter`). A written value below its floor MUST add the warning `kicad.project.below-floor` naming the class, the field, the value and the floor, and the value MUST still be written, because the floor governs and the class value is not enforced (`H-K-PRO-FLOOR`).
- Every issue `lower_netclass` appends MUST use a code of the project table `proerrors.ISSUE_CODES` (re-exported as `pro.ISSUE_CODES`), with the severity the table gives. `lowering` imports that leaf module and never imports `pro`. The requirement "Rule issue codes" governs the rule issues of `lower_rules`, `read_rules` and `write_rules`, not these.
- Fenolite MUST lower net classes only to the project file and only from the user's `Circuit.netclasses`; it ships no class values of its own.

#### Scenario: HV class lowered
- **GIVEN** `NetClass(name="HV", clearance=2_000_000, track_width=500_000)` and a `Default` base whose `via_diameter` is `JsonNumber("0.6")`
- **WHEN** `lower_netclass(cls, base=base, floors={})` is called
- **THEN** the entry has `name == "HV"`, `clearance == JsonNumber("2")`, `track_width == JsonNumber("0.5")`, `via_diameter == JsonNumber("0.6")`, and every other key equal to the base

#### Scenario: Value below the floor
- **GIVEN** `NetClass(name="HV", clearance=500_000)` and `floors == {"clearance": 1_500_000}`
- **WHEN** it is lowered with an `issues` list
- **THEN** the entry has `clearance == JsonNumber("0.5")` and `issues` holds one warning `kicad.project.below-floor` naming `HV`, `clearance`, `0.5` and `min_clearance`

#### Scenario: Description has no project key
- **GIVEN** `NetClass(name="HV", description="mains side")`
- **WHEN** it is lowered with an `issues` list
- **THEN** the entry has no description key and `issues` holds one info `kicad.project.unlowered-field`
