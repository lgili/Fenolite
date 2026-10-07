## ADDED Requirements

### Requirement: Impedance targets in an Altium build
An Altium build SHALL keep the impedance targets of a design ("Impedance targets in the rules model") in the model and in `.fenolite/` only, and SHALL report them in one `altium.not-lowered` info whose `where` is `impedance`, naming the targets sorted by name and the number of rules derived from them. No Altium document holds a target: `docs/formats/altium/` records no fact about the record of an impedance profile.
- **Derived rules.** The rules that `to_model` derives from a target are rules of the design, and "Rules in an Altium build" (c0084) applies to them as to any rule: each `track_width_<target>_<layer>` rule carries a layer and MUST be reported with the reason `scope-unsupported` ("Scoped rule records"), and each `diff_pair_gap_<target>_<layer>` rule MUST be reported with the reason `no-counterpart` (`altium-pcb-writer`, "Rule lowering table", as c0104 leaves it). Each gives one `altium.not-lowered` warning at `design-rules/<kind>` and one entry of `result.rules.not_lowered`; none is written, and none is left out of that account.
- **Files.** Every planned file outside `.fenolite/` MUST equal, byte for byte, the file of the same design without the targets, which is also the design without their derived rules. `.fenolite/rules.json` holds the targets and the derived rules.
- **Checks.** `build.impedance-layer` MUST be reported as in a KiCad build, and refuses the build. The other five codes of "Impedance targets in a build" (`design-dsl`) are about what KiCad's DRC and KiCad's project do; an Altium build gives them only where the script is judged through the KiCad build in memory ("Script copper in an Altium build"), as that build reports them.
- **Reading.** No Altium document reads into an `ImpedanceTarget`: `RuleSet.impedance` of an imported Altium design is empty.
- A design without targets MUST give no info at `impedance`.

#### Scenario: Target in an Altium build
- **GIVEN** `examples/altium_sample/design.py` and a variant that puts two of its signal nets in a class `SE50` with a target `SE50` whose traces are on `F.Cu` and `B.Cu`
- **WHEN** `uv run pytest tests/unit/lens/test_altium_rules.py -k impedance` builds both with `--target altium --dry-run --json`
- **THEN** the variant's planned files outside `.fenolite/` equal the example's built with the same class and no target; its `issues` hold one `altium.not-lowered` info at `impedance` naming `SE50` and two derived rules, and two `altium.not-lowered` warnings at `design-rules/track_width` naming `track_width_SE50_F.Cu` and `track_width_SE50_B.Cu` with the reason `scope-unsupported`; `result.rules.not_lowered` holds both

#### Scenario: Pair target in an Altium build
- **GIVEN** a variant with a `USB2` pair of the class `USB90` and a differential target on `F.Cu`
- **WHEN** it is built with `--target altium --dry-run --json`
- **THEN** the build does not fail, and `issues` hold one warning at `design-rules/track_width` (`scope-unsupported`) and one at `design-rules/diff_pair_gap` (`no-counterpart`) beside the info at `impedance`
