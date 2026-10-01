## ADDED Requirements

### Requirement: Footprint files are written
`fenolite.backends.kicad.mod.write_footprint(defn, *, target=DEFAULT_TARGET, allow_lossy=False, issues=None)` SHALL return the text of one `.kicad_mod` file for KiCad `target` (9 or 10), and `write_pretty(defs, *, target=DEFAULT_TARGET, allow_lossy=False, issues=None)` SHALL return a mapping from `"<name>.kicad_mod"` to that text for each definition, sorted by name.
- The writer MUST call `require_editable` on the definition, as c0017's `place_footprint` does. A definition read from a future file MUST raise `FutureFormatError` (`FEN-3002`).
- A definition without a slot list in `ext["kicad"]` MUST raise `ValueError`. Footprint generation from scratch is out of scope.
- The root MUST be `(footprint "<name>" …)` with `(version V)`, `(generator "fenolite")` and `(generator_version "<target>.0")`, where `V = FORMAT_VERSIONS[FileKind.FOOTPRINT][target]`. These replace the source's `version`, `generator` and `generator_version` slots in place; missing ones MUST be inserted after the name, in that order.
- Every other child MUST follow the definition's slot list. Modelled children MUST come from c0017's footprint emitter, `_fpmap.emit_footprint(defn, root_chain=("footprint",))`. Opaque children MUST be re-emitted verbatim.
- Before a projected fragment is re-emitted, the writer MUST project it again with `mod`'s reader function and compare the result with the definition. An edited `properties["Reference"]` or `properties["Value"]` MUST rewrite only that property's value atom. Any other difference (other `properties`, `keywords`, `models`, `Graphic.width`, `Pad.padstack`) MUST raise `LossyWriteError` with the error `kicad.footprint.projection-read-only` naming the field and the locator.
- `mod.WRITE_ISSUE_CODES` SHALL be the closed table of the footprint writer's codes: `kicad.footprint.dropped-too-new` (warning) and `kicad.footprint.projection-read-only` (error). Every `kicad.footprint.` code MUST be one of its keys.
- The writer MUST NOT sort pads or graphics. Equality is judged on the model and on load, never on bytes.
- The emitted node MUST pass `check_emittable(node, FileKind.FOOTPRINT, target)`. A `kicad.token.too-new` error MUST raise `LossyWriteError` (`FEN-7001`). With `allow_lossy=True`, the smallest opaque slot holding the token MUST be dropped instead, with a warning `kicad.footprint.dropped-too-new` naming the token, appended to `issues`. Any other error MUST abort.
- A definition read from a 10.0 file MUST be accepted for target 9 when every fragment passes this check; there is no whole-file downgrade refusal for definitions.
- `write_pretty` MUST raise `ValueError` for a repeated name or for a name containing `/`, `\` or `:`.
- The KiCad backend's capability report MUST list `kicad_mod` in `write_kinds`.

#### Scenario: Mini resistor written for KiCad 10
- **GIVEN** `read_footprint(Path("tests/data/libs/Mini.pretty/Mini_R_0603.kicad_mod"))`
- **WHEN** `write_footprint(defn, target=10)` is called
- **THEN** the text starts with `(footprint "Mini_R_0603"`, holds `(version 20260206)`, `(generator "fenolite")` and `(generator_version "10.0")`, and its pads, graphics and properties appear in the order of the source file

#### Scenario: Mini resistor written for KiCad 9
- **GIVEN** the definition of `tests/data/libs/Mini_v9.pretty/Mini_R_0603.kicad_mod`
- **WHEN** `write_footprint(defn, target=9)` is called
- **THEN** the text holds `(version 20241229)` and `(generator_version "9.0")`, and `check_emittable` of its parsed node for target 9 returns no error

#### Scenario: 10.0-only fragment refused for target 9
- **GIVEN** a definition read from a `20260206` footprint holding `(duplicate_pad_numbers_are_jumpers no)`
- **WHEN** `write_footprint(defn, target=9)` is called
- **THEN** `LossyWriteError` is raised, and with `allow_lossy=True` the text lacks that child and `issues` holds one `kicad.footprint.dropped-too-new` warning

#### Scenario: Value edited
- **GIVEN** the definition of `tests/data/libs/Mini.pretty/Mini_R_0603.kicad_mod` with `properties["Value"]` changed to `"10k"`
- **WHEN** it is written for target 10 and the text is parsed
- **THEN** the `property "Value"` node has the value `"10k"` and is otherwise tree-equal to the source node

#### Scenario: Read-only projection edited
- **GIVEN** the same definition with `properties["Datasheet"]` changed
- **WHEN** it is written for target 10
- **THEN** `LossyWriteError` is raised with `droppable is False` and one `kicad.footprint.projection-read-only` naming `properties` and the property's locator

#### Scenario: Footprint write codes are closed
- **GIVEN** the issues produced by the footprint writer's unit tests and the `kicad.footprint.` literals in `src/fenolite/backends/kicad/*.py`
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_mod_write.py -k codes` runs
- **THEN** every produced code and every literal is a key of `mod.WRITE_ISSUE_CODES`, with the severity of the table

#### Scenario: Future definition refused
- **GIVEN** a definition read from a footprint with `(version 20991231)`
- **WHEN** `write_footprint(defn, target=10)` is called
- **THEN** `FutureFormatError` is raised

#### Scenario: Definition without slots
- **GIVEN** `FootprintDef(id=..., name="X")`
- **WHEN** `write_footprint` is called on it
- **THEN** a `ValueError` saying that footprint generation is not supported is raised

#### Scenario: Library folder mapping
- **GIVEN** the four definitions of `tests/data/libs/Mini.pretty`
- **WHEN** `write_pretty(defs, target=10)` is called
- **THEN** the keys are the four file names `<name>.kicad_mod` in sorted order, and two definitions with the same name raise `ValueError`

### Requirement: Custom rules files are read and written
`fenolite.backends.kicad.dru` SHALL read and write custom rules files in the full dialect. `parse_rules(text, *, file="")` SHALL return a `RulesDocument` whose ordered items are the version list, the rule lists and the comment lines of the file.
- A line whose first non-blank character is `#` MUST become a `CommentItem` with its exact text and line number, wherever it is. A comment line inside a top-level list MUST stay inside that item's text and mark it `has_comment`.
- A symbol atom containing `'` outside a double-quoted string, such as a single-quoted rule name, MUST raise `FormatError` with `locator == "line N"` and a message naming line N, because KiCad drops the whole file. A `'…'` literal inside a double-quoted condition MUST be accepted.
- A top-level atom, a second `version` list, or a missing version MUST raise `FormatError`. The version MUST follow `kicad-version-gating`: below 1 is too old, above 1 is future and read-only.
- `RulesDocument.node` MUST be the synthetic `kicad_dru` node of the version and rule lists, without comments.

`read_rules(text, *, file="", issues=None)` SHALL return a `RuleSet`:
- A rule list MUST be lifted into a `Rule` only when every child belongs to the closed grammar of `rules-model`: a name, one constraint of a mapped kind with allowed limits and values in `mm`, `mil` or `in` (parsed exactly with `core.units.parse_length`), at most one condition in the closed selector grammar (up to whitespace and redundant parentheses), at most one layer clause with one layer name, and at most one severity among `error`, `warning` and `ignore`. A `hole_size` rule whose condition starts with the conjunct `A.Type == 'Via'` MUST lift as `hole_size` with an `item_kind via` selector.
- Any other rule list, every comment line, and every rule with a comment inside MUST be kept as an `Opaque` slot of `RuleSet.ext["kicad"]` with its exact source text, in file order, and every unlifted rule MUST add the info `rules.kept-opaque` naming the reason.
- A lifted rule MUST get the priority "number of rule items after it, plus 1", the id `derived_id("rul", "kicad", "rule:<name>")` (with `:<k>` for the k-th repetition of a name), its clause order as slots in its own `ext["kicad"]`, and provenance with locator `/kicad_dru/rule[i]` and `dru.EVIDENCE`. A missing severity MUST lift as `"error"`.
- In a future file, every item MUST be kept opaque with the file version as minimum version.

`write_rules(ruleset, *, target=DEFAULT_TARGET, allow_lossy=False, issues=None)` SHALL return the file text:
- It MUST write `(version 1)` first, then follow the file slots: comments and opaque rules verbatim in place, the k-th `rules` slot as `ruleset.rules[k]`, rules beyond the slots after the last `rules` slot, and rules of a rule set without slots in tuple order. Rule names and clause order MUST be kept. A clause the model now needs and the slots lack MUST be inserted in the order `layer`, `condition`, `constraint`, `severity`. A rule without clause slots MUST always carry `(severity …)`.
- Modelled rules MUST be written through `rulemap` (the `rules-model` grammar). A rule set read from a future file MUST raise `FutureFormatError`.
- Every opaque rule and every unknown top-level list MUST pass `check_emittable` on a synthetic `kicad_dru` node holding `(version 1)` and that item. An item whose text does not parse there MUST raise `RulesSelfCheckError` with step `parse`, before any gating issue. For target 9, a `kicad.token.too-new` or `kicad.token.uninventoried` issue MUST refuse the item: `RulesLossError` (`FEN-7001`, `droppable` true) is raised, or with `allow_lossy=True` the item is dropped with the warning `rules.dropped-for-target` naming the rule and the token. For target 10, a `kicad.token.uninventoried` item MUST be kept and its warning appended to `issues`.
- Before returning, the writer MUST pass the self-check of `rules-model` ("Lowered text is self-checked"), and every comment and opaque rule MUST come back as the same opaque slot in the same order. A failure MUST raise `RulesSelfCheckError` (`FEN-1001`).
- `versions.wrap_rules` and `versions.rules_text` MUST keep their common-subset behaviour.
- The KiCad backend's capability report MUST list `kicad_dru` in `write_kinds`. `read_kinds` MUST stay unchanged, because `Backend.read` returns a `Design` or a `Library` and `read_rules` returns a `RuleSet`.

#### Scenario: Comments stay in place
- **GIVEN** `tests/data/kicad/rules/comments.kicad_dru`, with a comment line before the first rule, one between two rules and one inside a rule
- **WHEN** `write_rules(read_rules(text), target=10)` is called and the result is read again
- **THEN** the three comment lines appear at the same positions relative to the rules, the rule holding a comment is kept verbatim, and the two rule sets are equal ignoring provenance

#### Scenario: Units read exactly
- **GIVEN** `tests/data/kicad/rules/units.kicad_dru` with the values `0.2mm`, `8mil` and `0.01in`
- **WHEN** it is read
- **THEN** the lifted `min` values are `200000`, `203200` and `254000`, and writing gives `0.2mm`, `0.2032mm` and `0.254mm`

#### Scenario: Single-quoted rule name
- **GIVEN** `tests/data/kicad/rules/broken.kicad_dru`, whose third line opens `(rule 'big one'`
- **WHEN** `read_rules(text, file="broken.kicad_dru")` is called
- **THEN** `FormatError` is raised with `file == "broken.kicad_dru"` and `locator == "line 3"`

#### Scenario: Unrepresentable rule kept opaque
- **GIVEN** a rule `(rule ring (constraint annular_width (min 0.1mm)))` between two lifted rules
- **WHEN** it is read with an `issues` list and written for target 9
- **THEN** it is an `Opaque` slot between the two `rules` slots, `issues` holds one `rules.kept-opaque`, and the written text holds it verbatim at the same position

#### Scenario: 10.0-only rule refused for target 9
- **GIVEN** `tests/data/kicad/rules/ten_only.kicad_dru`, which holds the canary and a rule `(constraint bridged_mask)`
- **WHEN** `write_rules(read_rules(text), target=9)` is called
- **THEN** `RulesLossError` is raised with `droppable is True` and one `kicad.token.too-new` issue naming the `bridged_mask` row

#### Scenario: 10.0-only rule dropped with allow_lossy
- **GIVEN** the same rule set
- **WHEN** `write_rules(ruleset, target=9, allow_lossy=True, issues=found)` is called
- **THEN** the text holds the canary and no `bridged_mask`, and `found` holds one `rules.dropped-for-target` warning

#### Scenario: Unknown construct kept for 10 and refused for 9
- **GIVEN** a preserved rule containing the uninventoried head `(frobnicate 1)`
- **WHEN** it is written for target 10 and for target 9
- **THEN** target 10 keeps it and reports one `kicad.token.uninventoried` warning, and target 9 raises `RulesLossError`

#### Scenario: Future rules file
- **GIVEN** a rules text whose first list is `(version 2)`
- **WHEN** it is read and written for target 10
- **THEN** reading gives the warning `kicad.version.future` and only opaque slots, and writing raises `FutureFormatError`

#### Scenario: Opaque text that does not parse
- **GIVEN** a `RuleSet` whose opaque slot holds `(rule broken (constraint clearance`
- **WHEN** `write_rules` is called
- **THEN** `RulesSelfCheckError` is raised naming the parse step, and no text is returned

#### Scenario: Written kinds in capabilities
- **WHEN** `fenolite capabilities --json` runs
- **THEN** the `write_kinds` of the `kicad` entry of `result.backends` contain `kicad_mod` and `kicad_dru`, and its `read_kinds` do not contain `kicad_dru`

#### Scenario: Dialect fixtures load in KiCad
- **GIVEN** the comments, units and selectors fixtures, each on a bench with the canary
- **WHEN** `uv run pytest tests/kicad/rules/test_rule_dialect.py` runs on 9.0.9 and on 10.0.6
- **THEN** the canary violation is present for each fixture, and the `mil` and `in` rules each give their violation
