## ADDED Requirements

### Requirement: Differential pairs in an Altium build
`fenolite build --target altium` SHALL keep the pair content of a design in the model, write none of it into an Altium document, and name each part that is not written. No pair record, pair rule or pair value is written, because `docs/formats/altium/pcb-copper.md` records no fact about them.
- **Pair and length rules.** A rule of kind `diff_pair_gap`, `diff_pair_uncoupled`, `skew`, `diff_pair_skew` or `length` MUST give one `altium.not-lowered` warning with `where` = `design-rules/<kind>`, naming the rule, its selector and the reason `no-counterpart`, and one entry of `result.rules.not_lowered` (`altium-pcb-writer`, "Rule lowering table"; "Rules in an Altium build"). The build MUST NOT raise for a kind of `model.rules.RuleKind`.
- **Pair leaf.** A rule of an `exact` kind whose selector holds a `diff_pair` leaf (for example the `clearance` rule that `design.rules.pair(…, clearance=…)` records, with the pair on both sides) MUST give the reason `scope-unsupported` for that rule only, as every selector outside the written scope forms does ("Scoped rule records"); the other rules of the kind are written.
- **Class pair values.** When a net class of the design holds `diff_pair_width`, `diff_pair_gap` or `diff_pair_via_gap`, the build MUST give one `altium.not-lowered` info with `where` = `pair-values` that names those classes, sorted by name, and says that the values are kept in the model only. It MUST be given with and without a planned PCB document, and a design whose classes hold none of the three values MUST get no such info.
- **Pair interfaces.** A `diff_pair` or `usb2` interface stays named by the info of the kind `interfaces` ("Typed interfaces in an Altium build"), whether or not a rule selects it: the narrower condition of `build.interface-not-lowered` (`design-dsl`, "Interfaces in the DSL") is the KiCad build's, where the pair reaches the file through its net names and rules.
- Every planned file outside `.fenolite/` MUST equal, byte for byte, the file of the same design without its pair values, without its rules of the five kinds and without its rules that hold a `diff_pair` leaf. `.fenolite/circuit.json` and `.fenolite/rules.json` hold them.
- A script whose copper intents are resolved through the KiCad build in memory ("Script copper in an Altium build") is still judged by that build: `build.diff-pair-name` and `build.diff-pair-gap-shadowed` are reported as that build reports them.

#### Scenario: Pair rules in an Altium build
- **GIVEN** the blink script with `usb = USB2(usb_p, usb_n)` on `USB_P` and `USB_N`, both in the class `USB` (clearance 0.2 mm, `diff_pair_gap` 0.15 mm), and `d.rules.pair(usb, gap_min=mm(0.13), clearance=mm(0.15), uncoupled_max=mm(5), skew_max=mm(0.5), length_max=mm(60))`
- **WHEN** `uv run pytest tests/unit/lens/test_altium_rules.py -k pair` builds it with `--target altium`
- **THEN** the build does not fail; `issues` hold one `altium.not-lowered` warning at each of `design-rules/diff_pair_gap`, `design-rules/diff_pair_uncoupled`, `design-rules/diff_pair_skew` and `design-rules/length` with the reason `no-counterpart`, one at `design-rules/clearance` with the reason `scope-unsupported`, one info at `pair-values` naming `USB`, and the info of `interfaces` naming the pair

#### Scenario: Files equal without the pair content
- **GIVEN** the design of "Pair rules in an Altium build" and the same design without the `pair()` call and without the class pair gap
- **WHEN** both are built with `--target altium --dry-run --json`
- **THEN** every planned file outside `.fenolite/` is byte-equal between the two
