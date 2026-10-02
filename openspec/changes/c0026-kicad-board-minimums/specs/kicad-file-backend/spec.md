## ADDED Requirements

### Requirement: Project files carry the board-setup minimums
`fenolite.backends.kicad.pro.synthesize_project` and `pro.update_project` SHALL write the minimums that `lowering.lower_minimums(design.rules, target=target, current=…, issues=…)` returns into `board.design_settings.rules` (`pro.MINIMUM_POINTER`) of the project text they return, so that `triad.write_triad` and `KicadBackend.lower` ship them. For the keys of `lowering.MINIMUM_KEYS`, this requirement takes precedence over the template-value rule and the keep rule of "Project files are synthesised and preserved". The five codes below extend the closed table of "Project issue codes".
- The minimums MUST be written before the net classes are lowered, so that the floors that `lower_netclass` receives are the written values and `kicad.project.below-floor` compares with them.
- After the net classes are lowered, both functions MUST call `lowering.class_conflicts(design.rules, target=target, clearances=…, model_names=…, issues=…)` with the clearance of every class entry of the project they return and the names of `design.circuit.netclasses`.
- `current` MUST be the value of each key in the project being written (`pro.project_minimums`), and the value of the target's template (`pro.template(target)`) for a key that the project lacks.
- A key whose existing value is a JSON number equal in nanometres to the written value MUST keep its text. Any other value MUST be replaced by the exact millimetre text of the nanometres as a `JsonNumber` (`lowering.millimetres`), and the writer MUST NOT produce a float.
- A key that an existing project lacks MUST be appended after the members of `board.design_settings.rules`, in the order of the table. A missing `board`, `design_settings` or `rules` object MUST be appended to its parent. When a key must be written and one of these members is not an object, `FormatError` MUST be raised with its JSON pointer.
- An update MUST add the info `kicad.project.minimum-replaced` for each written key whose existing value is absent, is not a JSON number, or differs in nanometres, naming the key, the old text (or `absent`), the new value and the governing rule. Synthesis adds no such info.
- Every other key, its position and its number spelling MUST stay as read, or as in the template for synthesis. When `lower_minimums` returns no key, the text MUST be the text returned for the same design with `rules=None`, byte for byte.
- `pro.project_minimums(data, *, issues=None)` SHALL return the nanometre value of each key of `lowering.MINIMUM_KEYS` that `board.design_settings.rules` holds as a JSON number. A value that is not a whole number of nm MUST read as absent with the info `kicad.project.inexact-value`.
- Minimums MUST NOT be lifted into rules: `read_project` and `apply_project` MUST leave `Design.rules` as it is, so that a design written by `write_triad` and read back holds the rules of its `.kicad_dru` and nothing more, and writing it again gives the same minimums.

| code | severity | when |
|---|---|---|
| `kicad.project.minimum-replaced` | info | an update writes a minimum that is absent from the file, is not a number there, or differs in nanometres |
| `kicad.project.minimum-kept` | info | the governing board-wide rule has a severity other than `error` or no `min`, so the minimum is kept |
| `kicad.project.rule-below-minimum` | warning | a rule asks for less than a minimum that Fenolite does not write, on a target where the minimum governs custom rules |
| `kicad.project.class-shadowed` | warning | a board-wide clearance rule overrides a larger class clearance, on a target where custom rules govern class items |
| `kicad.project.default-over-rule` | warning | the `Default` class, which the model does not set, keeps unclassed nets above a board-wide clearance rule, on a target where class clearances govern above custom rules |

#### Scenario: Synthesis writes the fab minimums
- **GIVEN** a design whose rules are the five board-wide rules of the scenario "Fab rule set" of `rules-model`
- **WHEN** `synthesize_project(design, target=10, board_name="b")` is called
- **THEN** `board.design_settings.rules` holds `min_clearance == JsonNumber("0.1")`, `min_track_width == JsonNumber("0.127")`, `min_via_diameter == JsonNumber("0.45")`, `min_through_hole_diameter == JsonNumber("0.2")` and `min_copper_edge_clearance == JsonNumber("0.3")`, every other member equals the template's with the same number text, and the members keep the template's order

#### Scenario: Classes compare with the written minimums
- **GIVEN** a board-wide `clearance` rule with `min=300_000` and a class HV with `clearance=200_000`
- **WHEN** the design is synthesised for target 10 with an `issues` list
- **THEN** `issues` holds the warning `kicad.project.below-floor` naming HV, `0.2`, `min_clearance` and `0.3`, although the template's `min_clearance` is 0

#### Scenario: Class conflicts use the written classes
- **GIVEN** a board-wide `clearance` rule with `min=100_000` and a model class HV with `clearance=2_000_000`, and no model class `Default`
- **WHEN** the design is synthesised for target 10 with an `issues` list, once with `RULES_OVER_CLASSES == frozenset({9, 10})` and once with it empty
- **THEN** the first `issues` holds `kicad.project.class-shadowed` naming HV and no `kicad.project.default-over-rule`; the second holds `kicad.project.default-over-rule` naming the template's `Default` clearance `0.2` and no `kicad.project.class-shadowed`

#### Scenario: No board-wide rule, no change
- **GIVEN** `bench_design(target=10)` of `tests/_netclass_bench.py`, whose only rule is the canary on `net CANARY_A`, and a target-10 project text (`meta.version` 3, `net_settings.meta.version` 5) whose `min_track_width` is written `0.25`
- **WHEN** it is synthesised for target 10, and the project text is updated with it
- **THEN** the synthesised `board.design_settings.rules` equals the template's member for member, and the updated text keeps `min_track_width == JsonNumber("0.25")` and adds no `kicad.project.minimum-replaced`

#### Scenario: Update keeps spelling, replaces and appends
- **GIVEN** a target-10 project text (`meta.version` 3, `net_settings.meta.version` 5) whose rules object holds `min_track_width` written `0.127000`, `min_through_hole_diameter` written `0.3` and no `min_copper_edge_clearance`, and a design with board-wide `track_width` (`min=127_000`), `hole_size` (`min=250_000`) and `edge_clearance` (`min=300_000`) rules
- **WHEN** `update_project(text, design, target=10, issues=found)` is called
- **THEN** `min_track_width` keeps `JsonNumber("0.127000")`, `min_through_hole_diameter == JsonNumber("0.25")`, `min_copper_edge_clearance == JsonNumber("0.3")` is the last member, every other member is unchanged, and `found` holds `kicad.project.minimum-replaced` for `min_through_hole_diameter` and `min_copper_edge_clearance` only

#### Scenario: Rules member that is not an object
- **GIVEN** a target-10 project text whose `board.design_settings.rules` is `[]`, and a design with one board-wide `track_width` rule
- **WHEN** `update_project` is called
- **THEN** `FormatError` is raised with `locator == "/board/design_settings/rules"`

#### Scenario: Minimums stay out of the model's rules
- **GIVEN** the design of "Synthesis writes the fab minimums" written by `write_triad(design, name="b", target=10)`
- **WHEN** `b.kicad_pro` is read with `read_project` and applied with `apply_project` to a design read from `b.kicad_pcb`
- **THEN** the applied design's `rules` is the read design's `rules`, `project_minimums(info.data)` returns the five written values, and `write_triad` of the original design with `existing_project` set to the text of `b.kicad_pro` keeps the five number texts and adds no `kicad.project.minimum-replaced`

## MODIFIED Requirements

### Requirement: Project files are synthesised and preserved
`fenolite.backends.kicad.pro.synthesize_project(design, *, target=DEFAULT_TARGET, board_name, allow_lossy=False, issues=None)` SHALL return the text of a complete project file built from a fresh copy of the packaged template of `target` (`backends/kicad/data/project_template_<target>.json`). `update_project(existing_text, design, *, target=DEFAULT_TARGET, allow_lossy=False, issues=None)` SHALL return the existing file with only its managed keys changed.

Synthesis MUST set:
- `meta.filename` to `"<board_name>.kicad_pro"`;
- `net_settings.classes` to the template's `Default` entry followed by one lowered entry per model `NetClass` other than `Default`, sorted by name; a model class named `Default` MUST update the four lowered values of the first entry;
- `net_settings.netclass_patterns` to one entry `{"netclass": <class name>, "pattern": <net name>}` per net whose `netclass_id` names a class other than `Default`, sorted by net name.

Every other key, `boards`, `netclass_assignments`, `text_variables` and `pcbnew.page_layout_descr_file` included, MUST keep its template value. Synthesis MUST add no key path absent from the template other than those of `pro.PATTERN_ENTRY_PATHS`: `/net_settings/netclass_patterns/*`, `/net_settings/netclass_patterns/*/netclass` and `/net_settings/netclass_patterns/*/pattern`. A `netclass_id` that names no class MUST raise `ConsistencyError` naming `model.unknown-netclass`; callers run `Design.validate()` first, which reports that error as a finding, so the CLI's `FEN-1001` for the exception marks a caller bug.

An update MUST:
- replace the four lowered values of each class entry whose name matches a model class, keeping the original text of a value that is equal in nanometres;
- append the model classes absent from the file, lowered from the file's `Default` entry and sorted by name, and never delete a class entry;
- regenerate the exact-name pattern entries whose pattern equals a model net name and place them first, keeping every other pattern entry verbatim and in order after them;
- add the warning `kicad.project.pattern-conflict` when a kept pattern entry or assignment matches, by `pattern_matches`, a model net that has another class;
- keep every other key, its position, its value and its number spellings, `meta.filename`, `boards` and the version pair included, except where "Project files are gated by target" removes keys.

A classed net whose name contains a character of `pro.UNSAFE_PATTERN_CHARS` (`*` and `?`), or whose exact-name pattern matches, by `pattern_matches`, another net of the design that is not in the same class, MUST raise `LossyWriteError` (`FEN-7001`, `droppable=True`) with the error `kicad.project.pattern-unsafe` naming the net and the other nets. With `allow_lossy=True` the net MUST get no pattern, and `issues` MUST hold the warning `kicad.project.dropped-pattern` instead.

Another requirement of this capability MAY take named keys out of the template-value rule, the added-path rule and the keep rule above, as "Project files carry the board-setup minimums" does for the keys of `lowering.MINIMUM_KEYS`. It names this requirement and the keys, and those keys follow it.

#### Scenario: Synthesis for target 10
- **GIVEN** a design with class HV (clearance `2_000_000` nm), nets `+3V3` and `Net-(R1-Pad1)` in HV, and `GND` with `netclass_id = None`
- **WHEN** `synthesize_project(design, target=10, board_name="bench")` is called
- **THEN** the result has `meta.filename == "bench.kicad_pro"`, class names `["Default", "HV"]`, HV `clearance == JsonNumber("2")`, and exactly the patterns `+3V3` and `Net-(R1-Pad1)` for HV, in that order

#### Scenario: No key outside the template
- **GIVEN** the same design
- **WHEN** it is synthesised for target 9 and for target 10
- **THEN** every key path of each result is a key path of `project_template_9.json` or `project_template_10.json` respectively, with list items written `*`, or one of `pro.PATTERN_ENTRY_PATHS`; the template's `netclass_patterns` is `[]`, so it has no path below `/net_settings/netclass_patterns/*`

#### Scenario: Unknown keys and tuning profiles kept on update
- **GIVEN** a target-10 project text (`meta.version` 3, `net_settings.meta.version` 5) holding a top-level key `x_unknown` with value `{"k": 1.000}`, a `tuning_profiles` value and class HV with clearance `2`
- **WHEN** `update_project(text, design, target=10)` runs with HV at clearance `3_000_000` nm
- **THEN** `x_unknown` and `tuning_profiles` are structurally equal to the input with `JsonNumber("1.000")` kept, and the only changed value is the HV clearance, now `JsonNumber("3")`

#### Scenario: Equal value keeps its spelling
- **GIVEN** a target-10 project text (`meta.version` 3, `net_settings.meta.version` 5) whose HV clearance is written `2.000`
- **WHEN** it is updated with HV at `2_000_000` nm
- **THEN** the HV clearance is still `JsonNumber("2.000")`

#### Scenario: Unsafe net name refused
- **GIVEN** a design whose net `CLK*` is in class HV
- **WHEN** `synthesize_project(design, target=10, board_name="b")` is called
- **THEN** `LossyWriteError` is raised naming `CLK*`; with `allow_lossy=True` the text is returned, `issues` holds the warning `kicad.project.dropped-pattern`, and no pattern names `CLK*`

#### Scenario: Over-matching name refused
- **GIVEN** a design whose net `D[0]` is in class HV and whose net `D0` has `netclass_id = None`
- **WHEN** `synthesize_project(design, target=10, board_name="b")` is called
- **THEN** `LossyWriteError` is raised with `droppable == True` and the error `kicad.project.pattern-unsafe` naming `D[0]` and `D0`; when `D0` is also in HV, the pattern `D[0]` is written and no issue is added

#### Scenario: Wildcard pattern conflicts with the model
- **GIVEN** a target-10 project text (`meta.version` 3, `net_settings.meta.version` 5) with classes HV and LV and the wildcard entry `{"netclass": "LV", "pattern": "+3*"}`, and a design where `+3V3` is in HV
- **WHEN** `update_project` runs with an `issues` list
- **THEN** the wildcard entry is kept after the exact-name entries and `issues` holds one warning `kicad.project.pattern-conflict` naming `+3V3`, HV and LV

### Requirement: Project issue codes
`fenolite.backends.kicad.proerrors.ISSUE_CODES`, re-exported as `pro.ISSUE_CODES`, SHALL be the closed table of project issue codes and severities. `proerrors` MUST import only `core`, so that `lowering` and `pro` can both use it:

| code | severity |
|---|---|
| `kicad.project.below-floor` | warning |
| `kicad.project.pattern-unsafe` | error |
| `kicad.project.dropped-pattern` | warning |
| `kicad.project.too-new-key` | error |
| `kicad.project.dropped-too-new` | warning |
| `kicad.project.multiple-classes` | warning |
| `kicad.project.unknown-class` | warning |
| `kicad.project.pattern-conflict` | warning |
| `kicad.project.inexact-value` | info |
| `kicad.project.unlowered-field` | info |
| `kicad.project.unread-entry` | info |

Every issue the project functions append MUST use a code from this table or a `kicad.version.*` code of `kicad-version-gating`, and every code MUST match `ISSUE_CODE`. Another requirement of this capability MAY add rows to the table, as "Project files carry the board-setup minimums" does; it names this requirement, and its rows belong to the closed table `ISSUE_CODES`.

#### Scenario: Closed table
- **GIVEN** the issues appended by the project unit tests of task groups 2 to 5
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_pro_read.py -k codes` runs
- **THEN** it passes only if every code appended during the project unit tests is a key of `ISSUE_CODES` or starts with `kicad.version.`
