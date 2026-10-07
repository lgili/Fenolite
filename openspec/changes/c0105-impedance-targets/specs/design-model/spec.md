## ADDED Requirements

### Requirement: Impedance targets in the rules model
`fenolite.model.rules` SHALL define `ImpedanceKind = Literal["single", "differential"]`, the value object `TraceGeometry(layer, references, width, gap=None)` and the entity `ImpedanceTarget(name, kind, netclass_ids, ohms, tolerance_percent="", layers=())`, and `RuleSet` SHALL gain the field `impedance: tuple[ImpedanceTarget, ...]`, empty by default and stored in `rules.json`. This is an addition to the `rules` layer of "Model layers for v0.1".
- `TraceGeometry.layer` MUST be a copper layer name; `references` MUST hold one or two layer names in stack order, none equal to `layer`; `width` MUST be an `Nm` above 0; `gap` MUST be an `Nm` above 0 for a `differential` target and `None` for a `single` one.
- `ImpedanceTarget.netclass_ids` MUST name the classes the target governs, in order; `ohms` and `tolerance_percent` MUST be decimal texts of positive numbers (`"90"`, `"42.5"`) or `""`, never produced from a `float`. `ohms` is `""` only for a target read from a file that gives none. `layers` MUST be in stack order.
- `Design.validate()` MUST report the error `model.impedance-invalid`, naming the target, for: a class id that names no class, a class named by two targets, two targets of one name, one layer twice in a target, a `gap` that does not fit the kind, a width or gap of 0 or less, a reference count other than one or two or a reference equal to the layer, and an `ohms` or tolerance text that is not a positive decimal, or a tolerance of 100 or more.
- `schemas/fenolite.model.v0/rules.json` MUST be regenerated, and a `rules.json` without the key `impedance` MUST load with an empty tuple.

#### Scenario: Target round trip
- **GIVEN** a design whose `RuleSet.impedance` holds `ImpedanceTarget(name="USB90", kind="differential", netclass_ids=(<id of USB90>,), ohms="90", tolerance_percent="10", layers=(TraceGeometry("F.Cu", ("In1.Cu",), 200_000, 150_000),))`
- **WHEN** it is written with `canonical.dump_dir` and loaded with `canonical.load_dir`
- **THEN** the loaded target equals the original, and `rules.json` holds it under the key `impedance`

#### Scenario: Rules file of an older build
- **GIVEN** a `rules.json` written before this change, without the key `impedance`
- **WHEN** it is loaded and validated against the regenerated schema
- **THEN** loading succeeds, validation passes and `RuleSet.impedance == ()`

#### Scenario: One class, two targets
- **GIVEN** two targets `A` and `B` that both name the class `USB90`
- **WHEN** `design.validate()` runs
- **THEN** it reports one `model.impedance-invalid` error naming `A`, `B` and `USB90`
