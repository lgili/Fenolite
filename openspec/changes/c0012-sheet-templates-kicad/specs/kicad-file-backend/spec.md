## MODIFIED Requirements

### Requirement: Board read issue codes
`read_board` SHALL report problems only with the codes of this closed table, plus the `kicad.version.*` codes of `kicad-version-gating`. `pcb.ISSUE_CODES` MUST map each code to its severity. On boards, the shared footprint mapping MUST report `kicad.board.kept-opaque` instead of `kicad.lib.kept-opaque`. The `ReadResult.issues` of a board also hold the `model.*` codes of `Design.validate()` (`backend-protocol` "Read results"); they are model findings, not reader codes, and are not in this table.

| code | severity | when |
|---|---|---|
| `kicad.board.inexact-length` | info | a length that is not a whole number of nm |
| `kicad.board.inexact-angle` | info | an angle that is not a whole number of µdeg |
| `kicad.board.zone-outline-opaque` | info | a zone or rule-area outline with `pts` arcs or several `polygon` children |
| `kicad.board.duplicate-uuid` | warning | a uuid already used by another item of the file |
| `kicad.board.unknown-net` | warning | a numbered net reference absent from the table |
| `kicad.board.kept-opaque` | info | a modelled or projected child that loses modelled meaning or fails the emitter check |
| `kicad.board.paper-unmodelled` | info | a `paper` child whose name or size the model does not name ("Paper and title block on boards") |

#### Scenario: Closed set enforced
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_pcb_numbers.py -k closed_set` collects every issue code that `read_board` produces in the board unit tests
- **THEN** each code other than `kicad.version.*` is a key of `ISSUE_CODES` with the severity of this table, and no `model.*` code comes from `read_board`

#### Scenario: Oval drill on a board pad
- **GIVEN** a board pad with `(drill oval 1.2 2.0)`
- **WHEN** the board is read with an `issues` list
- **THEN** the pad has `drill is None`, and `issues` holds one info `kicad.board.kept-opaque` and no `kicad.lib.*` code

#### Scenario: Unmodelled paper is an info
- **GIVEN** a board holding `(paper "USLetter")`
- **WHEN** it is read with an `issues` list
- **THEN** `issues` holds one info `kicad.board.paper-unmodelled`, and `ISSUE_CODES["kicad.board.paper-unmodelled"] == "info"`

### Requirement: Created board header
For a created design, `write_board` SHALL emit exactly the root head set of c0007's `tests/data/kicad/tokens/skeleton.kicad_pcb`, plus `title_block` when one of the seven fields of `Board.title_block` is non-empty:
- `version`, `generator` and `generator_version`;
- `(general (thickness T) (legacy_teardrops no))`, where T is the sum of the `Board.stackup` layer thicknesses, or 1.6 mm without a stack-up;
- `paper`, written by `pcb.paper_node(Board.sheet)`, which gives `(paper "A4")` when `Board.sheet` is `None` ("Paper and title block on boards");
- `title_block`, written by `pcb.title_block_node(Board.title_block)` right after `paper`, only when one of its seven fields is non-empty;
- `layers`, from `Board.layers` and each layer's `kicad` bag;
- `(setup (pad_to_mask_clearance 0))`;
- for target 9 only, the net table.

The content follows in `CANONICAL_ORDER`. `pcb.CREATED_ROOT_HEADS` MUST stay the head set of a created board without a title block; `pcb.CANONICAL_ORDER["kicad_pcb"]` MUST hold `title_block` right after `paper`, and `pcb.CANONICAL_ORDER["title_block"]` MUST be `("title", "date", "rev", "company", "comment")`. `fenolite.backends.kicad.layers.created_layers(copper)` MUST return the 2- and 4-copper-layer sets recorded in `docs/formats/kicad/board.md`, numbered in the 9.0 scheme (`F.Cu` 0, `B.Cu` 2, `In1.Cu` 4, `In2.Cu` 6, `Edge.Cuts` 25), with the KiCad number, type and user name in each layer's `kicad` bag. Any other `copper` value MUST raise `ValueError`. Every head and field name the writer can create MUST match a row of the token inventory, appear in c0007's skeleton, or be listed in `pcb.FLOOR_HEADS`: a closed tuple of names that the 8.0 board format already has, each recorded in `docs/formats/kicad/board.md` with its source and written by the created test board that the triad oracle loads on both majors. `FLOOR_HEADS` MUST include `title_block`, `title`, `date`, `rev`, `company` and `comment` (S-0001; S-0033 at tag 8.0.0), and `tests/_boards.py::created_board()` MUST set `SheetFrameRef("A4")` and a `TitleBlock` whose seven fields are non-empty, so the created test board writes them.

#### Scenario: Head set of a created 2-layer board
- **GIVEN** a created design whose board has `created_layers(2)` and no content
- **WHEN** it is written for target 9
- **THEN** the root's child heads are, in order, `version`, `generator`, `generator_version`, `general`, `paper`, `layers`, `setup`, `net`

#### Scenario: No net table for target 10
- **GIVEN** the same design
- **WHEN** it is written for target 10
- **THEN** the root's child heads are `version`, `generator`, `generator_version`, `general`, `paper`, `layers`, `setup`, and no child is headed `net`

#### Scenario: Four copper layers
- **WHEN** `created_layers(4)` is called
- **THEN** the copper layers are `F.Cu`, `In1.Cu`, `In2.Cu` and `B.Cu` with KiCad numbers 0, 4, 6 and 2

#### Scenario: Created tokens are known
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_pcb_write.py -k created_tokens` runs
- **THEN** every head and field in `CANONICAL_ORDER` and in the created header is found in the skeleton, is in `FLOOR_HEADS`, or matches an inventory row, and every name of `FLOOR_HEADS` occurs in the parsed text of the created test board written for target 9

#### Scenario: Created board with a Tabloid sheet
- **GIVEN** a created design whose board has `created_layers(2)`, `sheet = SheetFrameRef("Tabloid")` and `title_block = TitleBlock(title="Bench")`
- **WHEN** it is written for target 10
- **THEN** the root's child heads are `version`, `generator`, `generator_version`, `general`, `paper`, `title_block`, `layers`, `setup`, and the `paper` child is `(paper "User" 431.8 279.4)`

### Requirement: Projected fields on write
Before re-emitting an opaque fragment that a reader projected into a model field, `write_board` SHALL project the fragment again with the reader's function and compare the result with the model.
- When `Component.ref` or `Component.value` differs, the writer MUST rewrite only the value atom of the `(property "Reference" …)` or `(property "Value" …)` fragment; every other atom and child of that fragment MUST stay tree-equal.
- When a modelled field kept as an `Opaque` projected slot by the reader's reproducibility check differs, the writer MUST emit that field from the model if the fragment differs from the emitter's output for the old value only in spelling (same heads and atom count, numbers equal as decimals, strings equal as text, a zero angle written or omitted); otherwise it MUST give `kicad.board.projection-read-only`. An unchanged value MUST keep its fragment.
- When `Board.sheet` differs from `pcb.project_paper` of the root `paper` fragment, the writer MUST re-emit that fragment whole with `pcb.paper_node`. When `Board.title_block` differs from `pcb.project_title_block` of the root `title_block` fragment, the writer MUST rewrite that fragment in place, or insert it, as "Paper and title block on boards" states. Both projections are editable, and an unchanged value MUST keep its fragment.
- When any other projection differs (`Component.properties` other than Reference and Value, `Graphic.width` from a `stroke`, `Pad.padstack`), the writer MUST give `kicad.board.projection-read-only`, naming the field and the locator.

#### Scenario: Reference renamed
- **GIVEN** `two_layer.kicad_pcb` read with `read_board`, and its resistor component's `ref` changed to `R9`
- **WHEN** the design is written for target 9 and the text is parsed
- **THEN** that footprint's `property "Reference"` node has value `"R9"` and is otherwise tree-equal to the source node

#### Scenario: Spelling-only projection re-emitted
- **GIVEN** a copy of `two_layer.kicad_pcb`, built in the test, whose first `segment` holds `(width 0.250000)`, read with `read_board`, so the reader keeps that `width` as a projected slot, and the track's width then changed to 300 000 nm
- **WHEN** the design is written for target 9 and the text is parsed
- **THEN** that segment holds `(width 0.3)` at the position of the source `width`, and no issue is raised

#### Scenario: Read-only projection edited
- **GIVEN** the same board with the resistor's `properties["Datasheet"]` changed
- **WHEN** it is written
- **THEN** `LossyWriteError` is raised with an issue `kicad.board.projection-read-only` naming `properties` and the footprint's locator

#### Scenario: Paper edited on a read board
- **GIVEN** `two_layer.kicad_pcb` read with `read_board`, and its board's `sheet` changed to `SheetFrameRef("A3")`
- **WHEN** the design is written for target 9
- **THEN** no issue is raised, and the `paper` child is `(paper "A3")` at its source index

### Requirement: Project files are synthesised and preserved
`fenolite.backends.kicad.pro.synthesize_project(design, *, target=DEFAULT_TARGET, board_name, allow_lossy=False, issues=None)` SHALL return the text of a complete project file built from a fresh copy of the packaged template of `target` (`backends/kicad/data/project_template_<target>.json`). `update_project(existing_text, design, *, target=DEFAULT_TARGET, allow_lossy=False, issues=None)` SHALL return the existing file with only its managed keys changed.

Synthesis MUST set:
- `meta.filename` to `"<board_name>.kicad_pro"`;
- `net_settings.classes` to the template's `Default` entry followed by one lowered entry per model `NetClass` other than `Default`, sorted by name; a model class named `Default` MUST update the four lowered values of the first entry;
- `net_settings.netclass_patterns` to one entry `{"netclass": <class name>, "pattern": <net name>}` per net whose `netclass_id` names a class other than `Default`, sorted by net name.

Every other key, `boards`, `netclass_assignments`, `text_variables` and `pcbnew.page_layout_descr_file` included, MUST keep its template value; `write_triad` then sets `text_variables` and `pcbnew.page_layout_descr_file` from the design with `pro.apply_sheet_keys` ("Projects carry the drawing sheet and text variables"), which leaves the text unchanged when the design sets neither. Synthesis MUST add no key path absent from the template other than those of `pro.PATTERN_ENTRY_PATHS`: `/net_settings/netclass_patterns/*`, `/net_settings/netclass_patterns/*/netclass` and `/net_settings/netclass_patterns/*/pattern`. A `netclass_id` that names no class MUST raise `ConsistencyError` naming `model.unknown-netclass`; callers run `Design.validate()` first, which reports that error as a finding, so the CLI's `FEN-1001` for the exception marks a caller bug.

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

### Requirement: Project files are read into the model
`fenolite.backends.kicad.pro.read_project(source, *, file="", issues=None)` SHALL accept an `os.PathLike` (a `.kicad_pro` file) or a `str` (file text) and return a `ProjectInfo` with the parsed tree, the version pair, the status, the major, the classes (four values in nm), the patterns, the assignments, the floors, the drawing sheet named by `pcbnew.page_layout_descr_file` and the text variables ("Projects carry the drawing sheet and text variables"). `apply_project(design, info, *, issues=None)` SHALL return a new `Design`:
- `Circuit.netclasses` MUST be one `NetClass` per `classes` entry, in file order, with id `derived_id("cls", "kicad", "netclass:<name>")` and provenance naming the file and the entry's JSON pointer; a value that is not a whole number of nm MUST read as `None` with the info `kicad.project.inexact-value`.
- A net's candidate classes are those of its `netclass_assignments` entry (a string or a list of strings) and of every pattern entry that `pattern_matches` its name. Its `netclass_id` MUST be the candidate of highest priority: the lowest `priority` value, ties in `classes` order. A net with no candidate MUST keep `netclass_id = None`, which means `Default`.
- `pattern_matches(pattern, name)` MUST follow the reading of S-0046: it MUST return true when the pattern matches the whole name as a wildcard (`*` any run, `?` one character, every other character itself, case-sensitive), or when the pattern compiles as a Python regular expression whose `re.fullmatch` matches the name. The flavour and the whole-name matching are `INFERRED` (`H-K-PRO-PATTERNS`).
- Several distinct candidates for one net MUST give the warning `kicad.project.multiple-classes` naming them all, because KiCad forms an aggregate class while the model keeps one; a pattern or assignment naming an absent class MUST give `kicad.project.unknown-class`; an entry of another shape MUST give the info `kicad.project.unread-entry`. Each such entry is skipped.
- A `FUTURE` project MUST be read with the warning `kicad.version.future`.
- `apply_project` MUST also copy the drawing sheet into `Board.sheet.drawing_sheet` and the text variables into `Board.title_block.params`, as "Projects carry the drawing sheet and text variables" states.

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
| `kicad.project.reserved-variable` | error |
| `kicad.project.dropped-variable` | warning |
| `kicad.project.unread-variable` | info |

Every issue the project functions append MUST use a code from this table or a `kicad.version.*` code of `kicad-version-gating`, and every code MUST match `ISSUE_CODE`.

#### Scenario: Closed table
- **GIVEN** the issues appended by the project unit tests of task groups 2 to 5
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_pro_read.py -k codes` runs
- **THEN** it passes only if every code appended during the project unit tests is a key of `ISSUE_CODES` or starts with `kicad.version.`

### Requirement: Generated projects are coherent
`fenolite.backends.kicad.triad.write_triad(design, *, name, target=DEFAULT_TARGET, existing_project=None, allow_lossy=False, issues=None)` SHALL return exactly the three files `<name>.kicad_pcb`, `<name>.kicad_pro` and `<name>.kicad_dru`:
- the board from c0017's `write_board`;
- the rules from c0018's `lower_rules`, from an empty `RuleSet` when `design.rules is None`;
- the project from `update_project(existing_project, …)` when one is given, else from `synthesize_project(…, board_name=name)`, followed in both cases by `pro.apply_sheet_keys(…, allow_lossy=allow_lossy, issues=issues)` ("Projects carry the drawing sheet and text variables").

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

## ADDED Requirements

### Requirement: Drawing sheet files are read
`fenolite.backends.kicad.wks.read_drawing_sheet(source, *, file="", name=None, issues=None)` SHALL accept an `os.PathLike` (a `.kicad_wks` file), a `str` (file text) or a parsed `Node`, and return a `DrawingSheet`.
- The roots `kicad_wks`, `page_layout` and `drawing_sheet` MUST be read; a legacy root (c0007's `LEGACY_WORKSHEET_ROOTS`) MUST add the info `kicad.wks.legacy-root`. The version MUST be checked as boards check it: `info = versions.inspect(root, file=file)`, then `versions.require_readable(info, file=file)`, with `versions.version_issues(info)` added to `issues`.
- `setup` MUST map to `SheetSetup` (`textsize`, `linewidth`, `textlinewidth`, `left_margin`, `right_margin`, `top_margin`, `bottom_margin`). `line` and `rect` MUST map to `SheetShape` with `kind` `line` and `rect`, and `tbtext` and `bitmap` to `SheetText` and `SheetBitmap`, with `name`, `comment`, the points and their corner atom (none means `rb`), `linewidth`, `repeat`, `incrx`, `incry`, `incrlabel` (absent means `label_step = 1`, KiCad's default; `H-K-WKS-REPEAT`), `option`, `font` (`size`, `bold`, `italic`), `justify`, `rotate` (degrees, stored in µdeg), `maxlen`, `maxheight`, `scale` (stored in parts per million) and `pngdata` (stored as base64 text).
- `polygon` items and items with an unknown head MUST be opaque items at their position. Unmodelled children of a modelled item (`face`, `color`, unknown heads) MUST be opaque slots under nested relative locators (`tbtext[3]/font[0]`).
- Each modelled child MUST be re-emitted with the writer's emitter and compared with the original. A child that is not reproduced tree-equal (an explicit `rbcorner`, `(pos 10.000 10)`) MUST become an opaque slot whose value stays projected into the model, with the info `kicad.wks.kept-opaque`. On write, such a slot MUST be re-emitted verbatim while its projection equals the model, and from the model otherwise.
- An item MUST stay opaque, with the info `kicad.wks.kept-opaque` naming the reason, when one of its lengths is not a whole number of micrometres, an angle is not a whole number of µdeg, its scale is not a whole number of parts per million, one of its children holds a value atom outside `wks.VALUE_ATOMS`, its text holds a variable that the token map cannot read, or its text holds a `%` followed by an ASCII letter. KiCad still resolves these legacy text codes (`%T` draws the title) in `page_layout` and in `kicad_wks` 20231118 files alike (observed on 10.0.6 on 2026-10-01; `H-K-WKS-PCT`), so such a text is neither a literal nor a neutral token.
- Texts MUST be read through the inverse of `wks.KICAD_TOKENS`: each mapped variable reads as its neutral token, any other `${X}` with X matching `[A-Za-z_][A-Za-z0-9_]*` and not in `wks.RESERVED_VARIABLES` reads as `{param:X}`, and literal braces read as `{{` and `}}`. A KiCad-only variable (`${SHEETNAME}`, `${SHEETPATH}`, `${LAYER}`, `${KICAD_VERSION}`, `${KIPRJMOD}`, `${COMMENT4}` … `${COMMENT9}`) or a malformed `${` keeps the item opaque.
- `rebuild_drawing_sheet(sheet)` SHALL return the source tree of a read sheet, with the source root and header, modelled items emitted from the model and opaque items and slots verbatim at their positions. For every authored fixture under `tests/data/kicad/sheets/` and `tests/data/kicad/tokens/` and the corpus row `kicad-demo-10-0-6-wks-01`, with `t` its text, `tree_equal(rebuild_drawing_sheet(read_drawing_sheet(t)), parse(t))` MUST hold, and `wks.opaque_count` MUST count its opaque items and slots.
- Reading third-party worksheets is `INFERRED` (one corpus origin plus authored fixtures).

#### Scenario: Every modelled kind read
- **GIVEN** the authored fixture `tests/data/kicad/sheets/all_items.kicad_wks`
- **WHEN** it is read
- **THEN** its items include a `SheetShape` of each kind (`line`, `rect`), a `SheetText` and a `SheetBitmap`, every corner and scope value occurs, and a `tbtext` without corner atom has `pos.corner == "rb"`

#### Scenario: Tokens read back as neutral text
- **GIVEN** a sheet holding `(tbtext "${TITLE} / ${COMMENT1} / ${LOT_NO} / {x}" (pos 10 10))`
- **WHEN** it is read
- **THEN** the item is a `SheetText` with `text == "{title} / {doc_id} / {param:LOT_NO} / {{x}}"`

#### Scenario: Explicit default corner kept
- **GIVEN** a sheet holding `(tbtext "A" (pos 10 10 rbcorner))`
- **WHEN** it is read with an `issues` list and rebuilt with `rebuild_drawing_sheet`
- **THEN** the item is a `SheetText` with `pos == SheetPoint("rb", 10_000_000, 10_000_000)`, its `pos` child is an opaque slot, `issues` holds one info `kicad.wks.kept-opaque`, and the rebuilt tree is tree-equal to the source

#### Scenario: KiCad-only variable keeps the item opaque
- **GIVEN** a sheet holding `(tbtext "${SHEETNAME}" (pos 10 10))`
- **WHEN** it is read with an `issues` list
- **THEN** the item is opaque and `issues` holds one info `kicad.wks.kept-opaque`

#### Scenario: Sub-micrometre length on a modelled item
- **GIVEN** the authored fixture `tests/data/kicad/sheets/sub_um.kicad_wks`, holding `(line (start 50.0006 30 ltcorner) (end 60 30 ltcorner))` and one `tbtext` with whole-micrometre values
- **WHEN** it is read with an `issues` list and rebuilt
- **THEN** the `line` is an opaque item, `issues` holds one info `kicad.wks.kept-opaque` naming the length, the `tbtext` is a `SheetText`, and the rebuilt tree is tree-equal to the source

#### Scenario: Legacy percent code keeps the item opaque
- **GIVEN** a sheet holding `(tbtext "Title: %T" (pos 10 10))`
- **WHEN** it is read with an `issues` list
- **THEN** the item is opaque and `issues` holds one info `kicad.wks.kept-opaque`

#### Scenario: Demo worksheet read
- **GIVEN** the fetched corpus row `kicad-demo-10-0-6-wks-01`, a `page_layout` root whose lengths that are not whole micrometres all sit in its single `polygon` item and whose texts use `%` codes
- **WHEN** `uv run pytest tests/corpus/test_wks_corpus.py` runs (`needs_corpus`)
- **THEN** the `polygon` and every text with a `%` code are opaque and counted by `opaque_count`, and the RT1 condition holds

#### Scenario: Legacy root
- **GIVEN** c0007's fixture `tests/data/kicad/tokens/page_layout.kicad_wks`
- **WHEN** it is read with an `issues` list
- **THEN** `issues` holds the info `kicad.wks.legacy-root`, and `rebuild_drawing_sheet` returns a tree whose root is `page_layout`

### Requirement: Drawing sheet files are written
`fenolite.backends.kicad.wks.write_drawing_sheet(sheet, *, target=DEFAULT_TARGET, allow_lossy=False)` SHALL return a `WriteResult` whose text is one `.kicad_wks` file that both majors load.
- The root MUST be `kicad_wks`, followed by `(version 20231118)` (S-0032) and `(generator "fenolite")`, with no `generator_version`; a legacy root is re-rooted. For a read sheet, the writer MUST first call `versions.require_editable(versions.inspect(<source root>))`, as boards do: a sheet read from a `FUTURE` file MUST raise `FutureFormatError` (`FEN-3002`) and is never re-headed to 20231118, because future files are read-only (`kicad-version-gating`). The output MUST NOT depend on `target`: the text for target 9 and target 10 MUST be byte-identical, and `target` selects only the emit check.
- Children MUST follow `wks.CANONICAL_ORDER` (header, `setup`, then the items in `items` order, opaque items of a read sheet at their positions). The text MUST be printed with `dumps(style="kicad")`.
- Lengths MUST be written in millimetres with `Atom.from_nm`, rotations as the shortest exact decimal of degrees. The corner atoms MUST be `ltcorner`, `lbcorner` and `rtcorner`, and `rb` MUST be written without a corner atom. Scopes MUST be written `(option page1only)` and `(option notonpage1)`. `repeat`, `incrx` and `incry` MUST be written only when they differ from 1, 0 and 0, and `incrlabel` only when `label_step` is not 1, because KiCad steps labels by 1 when `incrlabel` is absent (`H-K-WKS-REPEAT`). A bitmap MUST be written as `pngdata` with at most 32 space-separated hex bytes per `data` row (S-0035).
- Texts MUST be written through `wks.KICAD_TOKENS`: `{title}` → `${TITLE}`, `{doc_id}` → `${COMMENT1}`, `{revision}` → `${REVISION}`, `{sheet}` → `${#}`, `{sheets}` → `${##}`, `{date}` → `${ISSUE_DATE}`, `{organization}` → `${COMPANY}`, `{responsible}` → `${COMMENT2}`, `{approver}` → `${COMMENT3}`, `{filename}` → `${FILENAME}`, `{paper}` → `${PAPER}`, `{param:X}` → `${X}`, and `{{`/`}}` → literal braces.
- The writer MUST refuse, with `LossyWriteError` (`FEN-7001`, `droppable=False`), a modelled length that is not a multiple of 1 000 nm (`kicad.wks.below-resolution`), a `{param:X}` with X in `wks.RESERVED_VARIABLES` (`kicad.wks.param-reserved`), and a neutral text whose KiCad form holds a `${`, or a `%` followed by an ASCII letter, that no token produced (`kicad.wks.literal-variable`; KiCad would resolve either, `H-K-WKS-PCT`).
- `versions.check_emittable(root, FileKind.WORKSHEET, target)` MUST run on the final tree. Each `kicad.token.uninventoried` warning MUST become the error `kicad.wks.uninventoried`, and each value atom outside `wks.VALUE_ATOMS` (corners, options, justify values, font flags) the error `kicad.wks.unknown-value`. Both MUST raise `LossyWriteError` (`FEN-7001`, `droppable=True`) with a hint naming `--allow-lossy`; with `allow_lossy=True`, the opaque item holding them MUST be dropped with the warning `kicad.wks.dropped-item` naming its locator. Modelled items MUST produce only inventoried names and listed values. The requirements of `kicad-version-gating` are unchanged.
- `KicadBackend.write_sheet(sheet, *, target=None, allow_lossy=False)` MUST return `write_drawing_sheet` for the same arguments, `target=None` meaning `default_target`. The capability report MUST list `kicad_wks` in `write_kinds` and MUST NOT list it in `read_kinds`, because `Backend.read` returns a `Design` or a `Library`.
- The evidence of a write is `INFERRED` (`wks.WRITE_EVIDENCE`, `H-K-WKS-CORNER`): a write runs no `kicad-cli`, and the oracle of `kicad-oracle` verifies the constructs, not each written file.

#### Scenario: Header and target independence
- **GIVEN** the sheet built from `iso5457_generic`
- **WHEN** it is written for target 9 and for target 10
- **THEN** both texts are byte-identical and start with `(kicad_wks (version 20231118) (generator "fenolite")`, and `check_emittable` on the parsed text gives no issue for either target

#### Scenario: Unknown head refused, then dropped
- **GIVEN** a sheet read from a text holding `(frobnicate 1)` as an item
- **WHEN** it is written, then written again with `allow_lossy=True`
- **THEN** the first call raises `LossyWriteError` with `droppable == True` and an issue `kicad.wks.uninventoried`; the second returns a text without `frobnicate` and a warning `kicad.wks.dropped-item`

#### Scenario: Unknown value atom refused
- **GIVEN** a sheet read from a text holding an opaque item with `(option bogus)`
- **WHEN** it is written
- **THEN** `LossyWriteError` is raised with an issue `kicad.wks.unknown-value`

#### Scenario: Sub-micrometre length refused
- **GIVEN** a built sheet with a `SheetShape` of kind `line` ending at `SheetPoint("lt", 500, 0)`
- **WHEN** it is written with `allow_lossy=True`
- **THEN** `LossyWriteError` is raised with `droppable == False` and an issue `kicad.wks.below-resolution`

#### Scenario: Reserved parameter refused
- **GIVEN** a built sheet with a `SheetText` `"{param:TITLE}"`, a second with the text `"${{x}}"` and a third with the text `"Title: %T"`
- **WHEN** each is written
- **THEN** the first raises `LossyWriteError` with `kicad.wks.param-reserved`, and the second and third with `kicad.wks.literal-variable`

#### Scenario: Label step written only when not 1
- **GIVEN** a built sheet with two repeated `SheetText` items `"A"`, one with `SheetRepeat(count=3, step_y=5_000_000)` and one with `SheetRepeat(count=3, step_y=5_000_000, label_step=0)`
- **WHEN** it is written and read back
- **THEN** the first `tbtext` has no `incrlabel` child, the second has `(incrlabel 0)`, and the read items equal the built ones

#### Scenario: Future worksheet not rewritten
- **GIVEN** a sheet read from a `kicad_wks` text whose `version` is newer than every supported version
- **WHEN** it is read with an `issues` list and then written
- **THEN** `issues` holds the warning `kicad.version.future`, and the write raises `FutureFormatError` (`FEN-3002`)

#### Scenario: Capability report
- **WHEN** `uv run fenolite capabilities --json --no-tools` runs
- **THEN** the `kicad` entry has `kicad_wks` in `write_kinds` and not in `read_kinds`

### Requirement: Drawing sheet issue codes
`fenolite.backends.kicad.wks.ISSUE_CODES` SHALL be the closed table of drawing-sheet issue codes, and every issue that `read_drawing_sheet` and `write_drawing_sheet` add MUST use one of its codes or a `kicad.version.*` code of `kicad-version-gating`:

| code | severity | when |
|---|---|---|
| `kicad.wks.kept-opaque` | info | an item or child kept opaque on read, with the reason |
| `kicad.wks.legacy-root` | info | a `page_layout` or `drawing_sheet` root on read |
| `kicad.wks.uninventoried` | error | a name with no inventory row on write |
| `kicad.wks.unknown-value` | error | a value atom outside `VALUE_ATOMS` on write |
| `kicad.wks.below-resolution` | error | a modelled length that is not a whole micrometre on write |
| `kicad.wks.param-reserved` | error | a `{param:X}` with X a reserved KiCad variable |
| `kicad.wks.literal-variable` | error | a `${`, or a `%` followed by an ASCII letter, in the written text that no token produced |
| `kicad.wks.dropped-item` | warning | an opaque item dropped under `allow_lossy` |

#### Scenario: Closed table
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_wks_write.py -k codes` collects every code that the drawing-sheet unit tests produce
- **THEN** each is a key of `ISSUE_CODES` with the severity of this table or starts with `kicad.version.`

### Requirement: Paper and title block on boards
`fenolite.backends.kicad.pcb` SHALL project the root children `paper` and `title_block` into `Board.sheet` and `Board.title_block` on read, and SHALL write them from those fields, as the MODIFIED "Created board header" and "Projected fields on write" require. Both MUST stay opaque root slots, so the closed list of "Modelled board content", every `opaque_count` and RT1 are unchanged.
- `project_paper(node, *, issues=None)` MUST return `SheetFrameRef(<name>, portrait=<portrait atom present>)` for `(paper "A0")` … `(paper "A5")`. For `(paper "User" W H)` it MUST return `Letter`, `Legal` or `Tabloid` when W x H equals that size of `PAPER_SIZES` in either orientation (portrait when W < H), and otherwise `SheetFrameRef("custom", width=W, height=H)`. Any other name (`USLetter`, `A` … `E`, …), and a size that is not a whole number of nm, MUST give `None` and add the info `kicad.board.paper-unmodelled` to `issues`; `read_board` passes its own `issues` list. A board without `paper` has `Board.sheet = None`.
- `project_title_block(node)` MUST map `title`, `date`, `rev`, `company`, `comment 1`, `comment 2` and `comment 3` through `pcb.TITLE_BLOCK_FIELDS` to `title`, `date`, `revision`, `organization`, `doc_id`, `responsible` and `approver`. `comment 4` … `comment 9` and unknown children MUST stay in the fragment unmapped. A board without `title_block` has `Board.title_block = None`. `Board.sheet.drawing_sheet` and `TitleBlock.params` come from the project ("Projects carry the drawing sheet and text variables").
- `paper_node(sheet)` MUST write `(paper "A3")` with a `portrait` atom when portrait, `(paper "A4")` for `None`, and `(paper "User" W H)` in millimetres for `Letter`, `Legal`, `Tabloid` and `custom`, with W > H for a US size unless it is portrait. KiCad's own names `USLetter`, `USLegal` and `USLedger` MUST NOT be written (`H-K-PCB-PAPER`).
- `title_block_node(block)` MUST write the non-empty fields among the seven, in the order `title`, `date`, `rev`, `company`, `comment 1`, `comment 2`, `comment 3`.
- On a read board, the writer MUST project the fragment again and compare it with the model. An unchanged value MUST keep its fragment. A changed `paper` MUST be re-emitted whole with `paper_node`. A changed `title_block` MUST be rewritten in place: the value atom of a changed mapped child replaced, a newly set field inserted at the place its order gives among the mapped children, an emptied field removed, and every other child kept tree-equal at its position; `None` counts as `TitleBlock()`, and a board read without `title_block` gains `title_block_node(block)` right after `paper`. These are projections re-emitted from changed model values in the sense of "Slots for lossless round-trip".

#### Scenario: Named paper read
- **GIVEN** the authored board with its `paper` child replaced by `(paper "A3" portrait)`
- **WHEN** it is read
- **THEN** `board.sheet == SheetFrameRef("A3", portrait=True)` and the `paper` child is an `Opaque` slot

#### Scenario: User paper equal to Letter
- **GIVEN** a board holding `(paper "User" 215.9 279.4)`
- **WHEN** it is read
- **THEN** `board.sheet == SheetFrameRef("Letter", portrait=True)`

#### Scenario: Unmodelled paper kept
- **GIVEN** a board holding `(paper "USLetter")`
- **WHEN** it is read with an `issues` list and written again for its own target
- **THEN** `board.sheet is None`, `issues` holds the info `kicad.board.paper-unmodelled`, and the written `paper` child is tree-equal to the source

#### Scenario: Title block projected and edited in place
- **GIVEN** a board whose `title_block` holds `(title "A")`, `(rev "1")` and `(comment 4 "keep")`
- **WHEN** it is read, `title_block.title` is changed to `"B"` and `title_block.organization` set to `"Lab"`, and the design is written
- **THEN** the written `title_block` holds `(title "B")`, `(rev "1")`, `(company "Lab")` after `rev`, and `(comment 4 "keep")` unchanged, and no other root child changed

#### Scenario: Corpus boards unchanged
- **WHEN** `uv run pytest tests/corpus/test_board_rt1.py` runs (`needs_corpus`)
- **THEN** it passes, and every corpus board's `opaque_count` equals the value before this change

### Requirement: Projects carry the drawing sheet and text variables
`fenolite.backends.kicad.pro.apply_sheet_keys(project_text, design, *, allow_lossy=False, issues=None)` SHALL return the project text with `pcbnew.page_layout_descr_file` (`pro.PAGE_LAYOUT_POINTER`) and `text_variables` set from the design, and `triad.write_triad` SHALL run it on the project text after `synthesize_project` or `update_project`. The three codes below are rows of the closed table of "Project issue codes".
- When `Board.sheet.drawing_sheet` is not `None`, `pcbnew.page_layout_descr_file` MUST be set to it verbatim; otherwise the existing value MUST be kept. `schematic.page_layout_descr_file` MUST NOT be touched.
- Each key of `TitleBlock.params` MUST add or replace one member of `text_variables`. New members MUST be appended after the existing ones, sorted by name, and no member MUST be deleted. The key paths `pro.SHEET_KEY_PATHS` (`/text_variables/*`) MUST be the only paths that `write_triad` adds beyond the template's and `pro.PATTERN_ENTRY_PATHS`.
- A name in `wks.RESERVED_VARIABLES` MUST give the error `kicad.project.reserved-variable` and raise `LossyWriteError` (`FEN-7001`, `droppable=True`); with `allow_lossy=True` the variable MUST be left out with the warning `kicad.project.dropped-variable`.
- When the design sets neither key (no `Board.sheet.drawing_sheet` and no parameter), the text MUST come back unchanged, so every c0010 scenario holds byte for byte.
- `read_project` MUST fill `ProjectInfo.drawing_sheet` (`None` for an absent or empty value) and `ProjectInfo.text_variables` (name and value pairs in file order; a member whose value is not a string gives the info `kicad.project.unread-variable` and is skipped, so c0010's `kicad.project.unread-entry` keeps its meaning). `apply_project` MUST copy the first into `Board.sheet.drawing_sheet` when `Board.sheet` is not `None`, and the second into `TitleBlock.params`, creating `TitleBlock(params=…)` when `Board.title_block` is `None` and there are variables.
- A triad written by `write_triad` without `existing_project` MUST read back with `sheet` and `title_block` equal to the design's in normal form (`H-K-PRO-WKS`): `Board.sheet = None` reads back as `SheetFrameRef("A4")`, the `(paper "A4")` of a created board, and a `TitleBlock` whose seven fields are empty and which has no parameter reads back as `None`, because no `title_block` is written for it.

| code | severity |
|---|---|
| `kicad.project.reserved-variable` | error |
| `kicad.project.dropped-variable` | warning |
| `kicad.project.unread-variable` | info |

#### Scenario: Nothing to set
- **GIVEN** a design whose board has no `sheet` and no `title_block`
- **WHEN** `write_triad(design, name="b", target=10)` is called
- **THEN** `b.kicad_pro` equals `synthesize_project(design, target=10, board_name="b")` byte for byte

#### Scenario: Both keys written and read back
- **GIVEN** a design whose board has `sheet = SheetFrameRef("A3", drawing_sheet="frame.kicad_wks")` and `title_block = TitleBlock(title="Bench", params={"LOT": "7"})`
- **WHEN** the triad is written for target 10, then read with `read_board`, `read_project` and `apply_project`
- **THEN** the project has `pcbnew.page_layout_descr_file == "frame.kicad_wks"` and `text_variables == {"LOT": "7"}`, and the read board's `sheet` and `title_block` equal the design's

#### Scenario: Default presentation reads back in normal form
- **GIVEN** a design whose board has no `sheet` and `title_block = TitleBlock()`
- **WHEN** the triad is written for target 10, then read with `read_board`, `read_project` and `apply_project`
- **THEN** the read board has `sheet == SheetFrameRef("A4")` and `title_block is None`

#### Scenario: Existing variables kept
- **GIVEN** an existing project text whose `text_variables` is `{"ZZ": "1", "LOT": "6"}`, and a design with params `{"LOT": "7", "AA": "2"}`
- **WHEN** `write_triad(design, name="b", target=10, existing_project=text)` is called
- **THEN** `text_variables` is `{"ZZ": "1", "LOT": "7", "AA": "2"}`, in that order

#### Scenario: Reserved variable refused
- **GIVEN** a design with params `{"TITLE": "x"}`
- **WHEN** `write_triad(design, name="b", target=10)` is called, then again with `allow_lossy=True` and an `issues` list
- **THEN** the first call raises `LossyWriteError` with `kicad.project.reserved-variable`; the second writes no `TITLE` member and `issues` holds `kicad.project.dropped-variable`

### Requirement: Drawing sheet format facts are documented
`docs/formats/kicad/worksheet.md` SHALL hold the worksheet facts in a table with the header `| fact | source | label | hypothesis |`: the roots and header constant, the setup and item heads, corner atoms and the default corner, repeat and its clipping, label increment, page-1 options, value atoms, text variables and their resolution on a board, the legacy `%` text codes that KiCad still resolves, the stated 1 µm resolution and what KiCad draws for finer lengths, `pngdata` rows, the silent fallback for missing files, and the SVG form used by the oracle. Every row MUST cite a source id, and every row below `KICAD-VERIFIED` or `CORPUS-VERIFIED` MUST name a hypothesis.
- `docs/formats/kicad/board.md` MUST gain rows for the `paper` forms and the `title_block` children and their order.
- `docs/formats/sheets.md` MUST state, in Fenolite's words and with a registered source id per row, the paper sizes (S-0077, S-0079) and the frame, zone and title-block figures used by the examples (S-0077, S-0078). No ISO text or figure is reproduced.
- `tests/unit/test_format_facts.py` MUST check `worksheet.md` with the rules above and `sheets.md` for a registered source id per row.

#### Scenario: Fact tables checked
- **WHEN** `uv run pytest tests/unit/test_format_facts.py` runs
- **THEN** it passes and its collected pages include `docs/formats/kicad/worksheet.md` and `docs/formats/sheets.md`

#### Scenario: Unsourced row refused
- **GIVEN** a row of `worksheet.md` with label `INFERRED` and no hypothesis
- **WHEN** `uv run pytest tests/unit/test_format_facts.py` runs
- **THEN** it fails naming the row
