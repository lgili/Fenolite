## ADDED Requirements

### Requirement: Project JSON is preserved exactly
`fenolite.backends.kicad.pro.read_project_text(text, *, file="")` SHALL parse a `.kicad_pro` file into a `JsonObject` that keeps the key order of every object and keeps every number as a `JsonNumber` holding its original text, and `write_project_text(data)` SHALL print it back. No float MUST exist at any step.
- Reading MUST raise `FormatError` with `file`: with `offset`, the UTF-8 byte offset of the error, for a syntax error; and with a JSON-pointer `locator` for a duplicate key inside one object (the key's pointer), `NaN`, `Infinity` or `-Infinity` (the value's pointer), and a root that is not an object (`""`).
- `JsonNumber` MUST reject text that does not match the JSON number grammar.
- The printer MUST use two-space indentation, one member or element per line, `"key": value`, `{}` and `[]` for empty containers, strings escaped as JSON with non-ASCII characters kept as UTF-8, and a final newline.
- `read_project_text(write_project_text(d))` MUST be structurally equal to `d`, with numbers compared as text. Byte identity with KiCad's printer is not required.

#### Scenario: Order and spellings survive a round trip
- **GIVEN** the text `{"b": 1.50, "a": {"x": 1e-3, "y": -0}, "z": [1, "s", true, null]}`
- **WHEN** it is read with `read_project_text`, printed with `write_project_text` and read again
- **THEN** the keys are in the order `b`, `a`, `z`, and the numbers are `JsonNumber("1.50")`, `JsonNumber("1e-3")`, `JsonNumber("-0")` and `JsonNumber("1")`

#### Scenario: Printer layout
- **WHEN** `write_project_text({"a": [JsonNumber("1")], "b": {}})` is called
- **THEN** it returns `'{\n  "a": [\n    1\n  ],\n  "b": {}\n}\n'`

#### Scenario: Duplicate key refused
- **WHEN** `read_project_text('{"meta": {"version": 3, "version": 4}}', file="p.kicad_pro")` is called
- **THEN** `FormatError` is raised with `file == "p.kicad_pro"`, `locator == "/meta/version"` and a message naming the key `version`

#### Scenario: Not a number refused
- **WHEN** `read_project_text('{"a": NaN}')` is called
- **THEN** `FormatError` is raised with `locator == "/a"`, and no float is created

#### Scenario: Syntax error located by offset
- **WHEN** `read_project_text('{"a": }')` is called
- **THEN** `FormatError` is raised with `offset == 6` and an empty `locator`

#### Scenario: GUI fixtures round-trip
- **GIVEN** `tests/data/kicad/project/empty_10.kicad_pro` and, when it exists, `empty_9.kicad_pro`
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_pro.py -k fixture` runs
- **THEN** each file read, printed and read again is structurally equal to the first read, with identical key order and number texts

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

### Requirement: Project files are gated by target
`synthesize_project` and `update_project` MUST NOT emit, for target 9, a key path of `pro.TEN_ONLY_PATHS`: the key paths present in `project_template_10.json` and absent from `project_template_9.json`, with list items written `*`. `update_project(…, target=9)` on a project whose pair is (3, 5) or that holds such a path SHALL:
- raise `DowngradeRefusedError(FileKind.BOARD, 10, 9)` (`FEN-7002`) when the design's board has source major 10, because the board's source major drives the refusal;
- otherwise raise `LossyWriteError` (`FEN-7001`, `droppable=True`) with one `kicad.project.too-new-key` error per path and, for the pair (3, 5), one more whose `where` is `/net_settings/meta/version`; with `allow_lossy=True`, remove each path and write `net_settings.meta.version` 4, with one warning `kicad.project.dropped-too-new` per error that the call would have raised.

For target 10, every key MUST be kept.

#### Scenario: 10.0 project for a 9.0 board
- **GIVEN** a project text with pair (3, 5) and a top-level `tuning_profiles` key, and a design whose board was read from a 9.0 file
- **WHEN** `update_project(text, design, target=9)` is called
- **THEN** `LossyWriteError` is raised whose issues include `kicad.project.too-new-key` with `where == "/tuning_profiles"`

#### Scenario: Lossy update for target 9
- **GIVEN** the same inputs
- **WHEN** `update_project(text, design, target=9, allow_lossy=True, issues=found)` is called
- **THEN** the result has no `tuning_profiles` key and no class `tuning_profile` key, `net_settings.meta.version == JsonNumber("4")`, and `found` holds `kicad.project.dropped-too-new` warnings

#### Scenario: Version alone is too new
- **GIVEN** a project text with pair (3, 5) and no key of `TEN_ONLY_PATHS`, and a design whose board was read from a 9.0 file
- **WHEN** `update_project(text, design, target=9)` is called, then again with `allow_lossy=True, issues=found`
- **THEN** the first call raises `LossyWriteError` whose only issue is `kicad.project.too-new-key` with `where == "/net_settings/meta/version"`, and the second returns a text with `net_settings.meta.version == JsonNumber("4")` and `found` holds one `kicad.project.dropped-too-new` warning with that `where`

#### Scenario: Downgrade refused
- **GIVEN** the same project and a design whose board was read from a 10.0 file
- **WHEN** `update_project(text, design, target=9, allow_lossy=True)` is called
- **THEN** `DowngradeRefusedError` is raised with `cli_code == "FEN-7002"`, `kind == FileKind.BOARD`, `source_major == 10` and `target_major == 9`

### Requirement: Project files are read into the model
`fenolite.backends.kicad.pro.read_project(source, *, file="", issues=None)` SHALL accept an `os.PathLike` (a `.kicad_pro` file) or a `str` (file text) and return a `ProjectInfo` with the parsed tree, the version pair, the status, the major, the classes (four values in nm), the patterns, the assignments and the floors. `apply_project(design, info, *, issues=None)` SHALL return a new `Design`:
- `Circuit.netclasses` MUST be one `NetClass` per `classes` entry, in file order, with id `derived_id("cls", "kicad", "netclass:<name>")` and provenance naming the file and the entry's JSON pointer; a value that is not a whole number of nm MUST read as `None` with the info `kicad.project.inexact-value`.
- A net's candidate classes are those of its `netclass_assignments` entry (a string or a list of strings) and of every pattern entry that `pattern_matches` its name. Its `netclass_id` MUST be the candidate of highest priority: the lowest `priority` value, ties in `classes` order. A net with no candidate MUST keep `netclass_id = None`, which means `Default`.
- `pattern_matches(pattern, name)` MUST follow the reading of S-0046: it MUST return true when the pattern matches the whole name as a wildcard (`*` any run, `?` one character, every other character itself, case-sensitive), or when the pattern compiles as a Python regular expression whose `re.fullmatch` matches the name. The flavour and the whole-name matching are `INFERRED` (`H-K-PRO-PATTERNS`).
- Several distinct candidates for one net MUST give the warning `kicad.project.multiple-classes` naming them all, because KiCad forms an aggregate class while the model keeps one; a pattern or assignment naming an absent class MUST give `kicad.project.unknown-class`; an entry of another shape MUST give the info `kicad.project.unread-entry`. Each such entry is skipped.
- A `FUTURE` project MUST be read with the warning `kicad.version.future`.

#### Scenario: Bench project read back
- **GIVEN** the bench of `tests/_netclass_bench.py` written by `write_triad` for target 10, then read with `read_board` and `read_project`
- **WHEN** `apply_project(design, info)` is called
- **THEN** `Circuit.netclasses` holds `Default` and `HV`, the nets `+3V3` and `SIG1` have the HV id, and `SIG10`, `Net-(R1-Pad1)`, `Net-R1-Pad1`, `D[0]`, `D0` and `GND` have `netclass_id is None`

#### Scenario: Wildcard pattern
- **GIVEN** a project whose only pattern is `{"netclass": "HV", "pattern": "SW?_*"}` and a design with nets `SW1_A` and `SW10`
- **WHEN** the project is applied
- **THEN** `SW1_A` is in HV and `SW10` is not

#### Scenario: Patterns read as wildcards and regular expressions
- **GIVEN** the documented reading of S-0046
- **WHEN** `pattern_matches` is called with (`D[0]`, `D0`), (`D[0]`, `D[0]`), (`net*`, `ne`), (`+3V3`, `+3V3`) and (`SIG1`, `SIG10`)
- **THEN** it returns `True`, `True`, `True`, `True` and `False`

#### Scenario: Two classes for one net
- **GIVEN** a target-10 project (`meta.version` 3, `net_settings.meta.version` 5) whose classes HV and PWR have `priority` 0 and 1, and whose patterns give `+3V3` both HV (`+3V3`) and PWR (`+*`)
- **WHEN** it is applied with an `issues` list
- **THEN** `+3V3` is in HV and `issues` holds one warning `kicad.project.multiple-classes` naming HV and PWR; with the two priorities swapped, `+3V3` is in PWR

#### Scenario: Minimal canary project
- **GIVEN** the text `{}`
- **WHEN** `read_project("{}")` is called
- **THEN** the status is `SUPPORTED`, both versions are `None`, `major is None` and there are no classes

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

Every issue the project functions append MUST use a code from this table or a `kicad.version.*` code of `kicad-version-gating`, and every code MUST match `ISSUE_CODE`.

#### Scenario: Closed table
- **GIVEN** the issues appended by the project unit tests of task groups 2 to 5
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_pro_read.py -k codes` runs
- **THEN** it passes only if every code appended during the project unit tests is a key of `ISSUE_CODES` or starts with `kicad.version.`

### Requirement: Generated projects are coherent
`fenolite.backends.kicad.triad.write_triad(design, *, name, target=DEFAULT_TARGET, existing_project=None, allow_lossy=False, issues=None)` SHALL return exactly the three files `<name>.kicad_pcb`, `<name>.kicad_pro` and `<name>.kicad_dru`:
- the board from c0017's `write_board`;
- the rules from c0018's `lower_rules`, from an empty `RuleSet` when `design.rules is None`;
- the project from `update_project(existing_project, …)` when one is given, else from `synthesize_project(…, board_name=name)`.

An error of any of the three writers MUST abort the whole set. Functions of `fenolite` MUST NOT read or write a `.kicad_prl` file. Every `kicad-cli` run on a generated set MUST go through c0009's `KicadCli`, which works on a temporary copy. The KiCad backend's capability report MUST list `kicad_pro` in `write_kinds` and `lower` in `operations`, and MUST NOT list `kicad_pro` in `read_kinds`, because `Backend.read` returns a `Design` or a `Library` and `read_project` returns a `ProjectInfo`. `KicadBackend.lower(design, *, name, target=None, existing_project=None, allow_lossy=False, issues=None)` MUST return the files of `write_triad` for the same arguments, appending the same issues, `target=None` meaning `default_target`.

#### Scenario: Three files, always
- **GIVEN** a design with no rules
- **WHEN** `write_triad(design, name="blink", target=10)` is called
- **THEN** the keys are exactly `blink.kicad_pcb`, `blink.kicad_pro` and `blink.kicad_dru`, and the rules text is `(version 1)` followed by a newline

#### Scenario: Existing project is updated, not replaced
- **GIVEN** a target-10 project text (`meta.version` 3, `net_settings.meta.version` 5) holding the key `x_unknown`
- **WHEN** `write_triad(design, name="b", target=10, existing_project=text)` is called
- **THEN** `b.kicad_pro` still holds `x_unknown` with its original value

#### Scenario: One failing writer aborts the set
- **GIVEN** a design whose classed net is named `CLK*`
- **WHEN** `write_triad(design, name="b", target=10)` is called
- **THEN** `LossyWriteError` is raised and no text is returned

#### Scenario: Capability report
- **GIVEN** the KiCad backend with this change applied
- **WHEN** `uv run fenolite capabilities --json` runs
- **THEN** the `kicad` entry of `result.backends` has `kicad_pro` in `write_kinds`, not in `read_kinds`, and `lower` in `operations`

#### Scenario: Backend lowering returns the triad
- **GIVEN** a design with no rules
- **WHEN** `KicadBackend().lower(design, name="blink")` is called
- **THEN** it returns exactly `blink.kicad_pcb`, `blink.kicad_pro` and `blink.kicad_dru`, equal to `write_triad(design, name="blink", target=10)`

#### Scenario: Backend lowering keeps the issues
- **GIVEN** `bench_design(target=10, hv_clearance=500_000)` and `text`, a target-10 project from `pro.template(10)` whose `board.design_settings.rules.min_clearance` is 1.5
- **WHEN** `KicadBackend().lower(design, name="b", existing_project=text, issues=issues)` is called with an empty list
- **THEN** `issues` is not empty, holds the warning `kicad.project.below-floor` naming `HV`, and equals what `write_triad(design, name="b", target=10, existing_project=text, issues=other)` puts in `other`

### Requirement: Project format facts are documented
`docs/formats/kicad/project.md` SHALL record, in Fenolite's own words and in fact tables with the header `| fact | source | label | hypothesis |`:
- the roles of `.kicad_pro` and `.kicad_prl`, and the absence of a public specification;
- the key diff of the two GUI-saved fixtures and the version pair of each;
- the class keys, the pattern entry keys and the floor keys Fenolite reads or writes;
- the managed keys and the update rules;
- the census counts and the answer on tuning profiles.

Every row MUST cite an id of `docs/evidence/sources.md`, and every row below `KICAD-VERIFIED` and `CORPUS-VERIFIED` MUST name an `H-K-PRO-*` hypothesis or `H-K-TOK-RULES-SILENT`. The page MUST state that the templates come only from the GUI saves and that the demos and S-0066 are used for key names and counts only.

#### Scenario: Fact tables checked
- **GIVEN** `docs/formats/kicad/project.md` written by task 1.3, and a `project.md` entry in `HYPOTHESIS_IDS` of `tests/unit/test_format_facts.py` that accepts only `H-K-PRO-*` and `H-K-TOK-RULES-SILENT`
- **WHEN** `uv run pytest tests/unit/test_format_facts.py tests/unit/test_provenance.py` runs
- **THEN** both pass, and a `project.md` row below the verified levels that names another hypothesis fails the first
