# kicad-version-gating Specification

## Purpose
Detect the kind and format version of KiCad files, classify them as too old, supported or future, read files from KiCad 8.0 on, write for KiCad 9.0 or 10.0, and refuse unsafe edits or downgrades with registered CLI error codes. Facts and sources: `docs/formats/kicad/versions.md`.
## Requirements
### Requirement: Format version constants
`fenolite.backends.kicad.versions` SHALL define `FileKind` with the values `kicad_pcb`, `kicad_mod`, `kicad_sch`, `kicad_sym`, `kicad_wks` and `kicad_dru`, and SHALL expose `FORMAT_VERSIONS[kind][major]`:

| kind | 8 | 9 | 10 |
|---|---|---|---|
| `kicad_pcb` | 20240108 | 20241229 | 20260206 |
| `kicad_mod` | 20240108 | 20241229 | 20260206 |
| `kicad_sch` | 20231120 | 20250114 | 20260306 |
| `kicad_sym` | 20231120 | 20241209 | 20251024 |
| `kicad_wks` | 20231118 | 20231118 | 20231118 |
| `kicad_dru` | — | 1 | 1 |

It SHALL also expose `READ_MAJORS = (8, 9, 10)`, `TARGET_MAJORS = (9, 10)`, `DEFAULT_TARGET = 10`, and `READ_FLOOR`. `READ_FLOOR` is the 8.0 constant for board, footprint, schematic and symbol library; 0 for worksheets; and 1 for rules. Every constant MUST cite its source in `docs/formats/kicad/versions.md` and carry the evidence level it has reached.

#### Scenario: Board constant for 10.0
- **GIVEN** the packaged `versions` module
- **WHEN** `FORMAT_VERSIONS[FileKind.BOARD][10]` is read
- **THEN** it equals `20260206`

#### Scenario: Footprints share the board constant
- **GIVEN** the packaged `versions` module
- **WHEN** `FORMAT_VERSIONS[FileKind.FOOTPRINT]` is compared with `FORMAT_VERSIONS[FileKind.BOARD]`
- **THEN** the two mappings are equal

#### Scenario: Worksheet constant is frozen
- **GIVEN** the packaged `versions` module
- **WHEN** the worksheet constants of majors 8, 9 and 10 are read
- **THEN** all three equal `20231118`

### Requirement: File kind detection
`kind_of(node)` SHALL map the root head to a `FileKind`:
- `kicad_pcb` → board;
- `footprint` → footprint;
- `kicad_sch` → schematic;
- `kicad_symbol_lib` → symbol library;
- `kicad_wks`, `page_layout` or `drawing_sheet` → worksheet;
- the synthetic `kicad_dru` → rules.

It MUST raise `UnsupportedFormatError` for the pre-6 footprint root `module`, with a `hint` naming `kicad-cli fp upgrade`, and MUST raise `FormatError` naming the head for any other root. `kind_for_suffix(name)` SHALL map a file name suffix to a kind, or return `None`.

#### Scenario: Board root
- **GIVEN** a node parsed from `(kicad_pcb (version 20241229) (generator "fenolite"))`
- **WHEN** `kind_of(node)` is called
- **THEN** it returns `FileKind.BOARD`

#### Scenario: Legacy worksheet root
- **GIVEN** a node whose head is `page_layout`
- **WHEN** `kind_of(node)` is called
- **THEN** it returns `FileKind.WORKSHEET`

#### Scenario: Pre-6 footprint refused
- **GIVEN** a node whose head is `module`
- **WHEN** `kind_of(node)` is called
- **THEN** `UnsupportedFormatError` is raised, its `cli_code` is `FEN-3003` and its `hint` contains `kicad-cli fp upgrade`

#### Scenario: Unknown root rejected
- **GIVEN** a node whose head is `kicad_frobnicate`
- **WHEN** `kind_of(node, file="x.kicad_pcb")` is called
- **THEN** `FormatError` is raised whose message names `kicad_frobnicate` and whose `file` is `x.kicad_pcb`

### Requirement: Version detection
`detect_version(node)` SHALL return the integer of the root's first-level `(version N)` child. It MUST return `LEGACY_WORKSHEET_VERSION` (0) for a legacy worksheet root without a version. It MUST raise `FormatError` with the node's offset when the version is missing under any other root, or when the version is not an integer.

#### Scenario: Version read
- **GIVEN** a board node with `(version 20250513)`
- **WHEN** `detect_version(node)` is called
- **THEN** it returns `20250513`

#### Scenario: Missing version rejected
- **GIVEN** a board node without a `version` child
- **WHEN** `detect_version(node)` is called
- **THEN** `FormatError` is raised stating that the format version is missing

#### Scenario: Non-integer version rejected
- **GIVEN** a board node with `(version "abc")`
- **WHEN** `detect_version(node)` is called
- **THEN** `FormatError` is raised

#### Scenario: Legacy worksheet without version
- **GIVEN** a `page_layout` root without a `version` child
- **WHEN** `detect_version(node)` is called
- **THEN** it returns `0`

### Requirement: Mapping versions to majors
`major_for(kind, version)` SHALL return `None` when `version < READ_FLOOR[kind]`. Otherwise it SHALL return the oldest major in `READ_MAJORS` whose constant is greater than or equal to `version`, or `None` when `version` is greater than every known constant of that kind. Development versions MUST therefore map to the release that reads them.

#### Scenario: 10.0 development version
- **GIVEN** the board constants of the packaged module
- **WHEN** `major_for(FileKind.BOARD, 20250513)` is called
- **THEN** it returns `10`

#### Scenario: 9.0 development version
- **WHEN** `major_for(FileKind.BOARD, 20241030)` is called
- **THEN** it returns `9`

#### Scenario: Future version
- **WHEN** `major_for(FileKind.BOARD, 20260207)` is called
- **THEN** it returns `None`

#### Scenario: Version below the read floor
- **GIVEN** a KiCad 7 board version `20221018`, below the board read floor `20240108`
- **WHEN** `major_for(FileKind.BOARD, 20221018)` is called
- **THEN** it returns `None`

#### Scenario: Rules version
- **WHEN** `major_for(FileKind.RULES, 1)` is called
- **THEN** it returns `9`

### Requirement: Classification and read policy
`classify(kind, version)` SHALL return `TOO_OLD` when `version < READ_FLOOR[kind]`, `FUTURE` when `version` is greater than every known constant of the kind, and `SUPPORTED` otherwise. `inspect(node)` SHALL return a `FormatInfo` with kind, version, major, status, `generator` and `generator_version`.

`require_readable(info)` MUST raise `UnsupportedFormatError` (`cli_code` `FEN-3003`) for `TOO_OLD`, with a `hint` naming the upgrade command of the kind (`kicad-cli pcb upgrade`, `fp upgrade`, `sch upgrade` or `sym upgrade`; for `pcb` and `sch` the hint states that KiCad 10.0 is needed). `require_editable(info)` MUST additionally raise `FutureFormatError` (`cli_code` `FEN-3002`) for `FUTURE`.

`version_issues(info)` SHALL return:
- a `kicad.version.future` warning stating that the file is read-only, for `FUTURE`;
- a `kicad.version.dev` info issue only when the status is `SUPPORTED`, the version is greater than the lowest released constant of the kind, and it equals none of `FORMAT_VERSIONS[kind].values()`.

This policy is intentionally stricter than KiCad, which loads future-version boards whose tokens it knows and accepts a rules file with `(version 2)`; `docs/formats/kicad/versions.md` MUST state this.

#### Scenario: KiCad 7 board refused
- **GIVEN** a board with `(version 20221018)`
- **WHEN** `require_readable(inspect(node))` is called
- **THEN** `UnsupportedFormatError` is raised naming the version and the 8.0 floor, with a `hint` containing `kicad-cli pcb upgrade`

#### Scenario: Future board readable but not editable
- **GIVEN** a board with `(version 20990101)`
- **WHEN** `require_readable` and then `require_editable` are called on its `FormatInfo`
- **THEN** `require_readable` returns without error, `version_issues` contains `kicad.version.future` and no `kicad.version.dev`, and `require_editable` raises `FutureFormatError`

#### Scenario: Future rules file
- **GIVEN** a synthetic rules node with `(version 2)`
- **WHEN** `classify(FileKind.RULES, 2)` is called
- **THEN** it returns `FUTURE`

#### Scenario: Legacy worksheet supported without a dev issue
- **GIVEN** a `page_layout` worksheet without a version
- **WHEN** `classify(FileKind.WORKSHEET, 0)` and `version_issues(inspect(node))` are called
- **THEN** the status is `SUPPORTED` and no `kicad.version.dev` issue is returned

#### Scenario: Development version reported
- **GIVEN** a board with `(version 20250907)`
- **WHEN** `version_issues(inspect(node))` is called
- **THEN** it contains one `kicad.version.dev` issue of severity `info` and no error

### Requirement: Targets and downgrade refusal
`check_target(info, target_major)` SHALL return `FORMAT_VERSIONS[info.kind][target_major]` when `target_major` is in `TARGET_MAJORS`, the input is `SUPPORTED`, and the target is not older than `major_for(info.kind, info.version)`. It MUST raise:
- `ValueError` for a target outside `TARGET_MAJORS`;
- `UnsupportedFormatError` (`FEN-3003`) when the input is `TOO_OLD`;
- `FutureFormatError` (`FEN-3002`) when the input is `FUTURE`;
- `DowngradeRefusedError` (`cli_code` `FEN-7002`, carrying `source_major`, `target_major` and a `hint` naming the lowest allowed target) when the target is older than the input's major.

#### Scenario: Same-major target
- **GIVEN** a board read at `20241229`
- **WHEN** `check_target(info, 9)` is called
- **THEN** it returns `20241229`

#### Scenario: Upgrade target allowed
- **GIVEN** a board read at `20241229`
- **WHEN** `check_target(info, 10)` is called
- **THEN** it returns `20260206`

#### Scenario: Downgrade refused
- **GIVEN** a board read at `20250513` (major 10)
- **WHEN** `check_target(info, 9)` is called
- **THEN** `DowngradeRefusedError` is raised with `source_major == 10`, `target_major == 9` and `cli_code == "FEN-7002"`

#### Scenario: Too-old input refused
- **GIVEN** a board read at `20221018`
- **WHEN** `check_target(info, 10)` is called
- **THEN** `UnsupportedFormatError` is raised and no header version is returned

#### Scenario: Unsupported target
- **GIVEN** a board read at `20241229`
- **WHEN** `check_target(info, 8)` is called
- **THEN** `ValueError` is raised listing the supported targets

### Requirement: Rules text and the synthetic node
`wrap_rules(text, *, file="")` SHALL return a node with head `kicad_dru` whose children are the top-level lists of `text`, in order. It MUST raise `FormatError`, naming the file and the line or offset, when a line's first non-blank character is `#` or when any symbol atom contains `'`; the message SHALL say that this part of the rules dialect needs the rules reader. `rules_text(node)` SHALL return the children of the synthetic root printed one after another at top level with c0006's `dumps`, ending with a newline, and MUST NOT contain the `kicad_dru` head.

#### Scenario: Several top-level lists
- **GIVEN** the text `(version 1)` followed by `(rule a (constraint clearance (min 3mm)))`
- **WHEN** `wrap_rules(text)` is called
- **THEN** the node has head `kicad_dru` and two children, `version` and `rule`

#### Scenario: Comment line refused
- **GIVEN** a rules text whose second line is `# keep HV apart`
- **WHEN** `wrap_rules(text, file="b.kicad_dru")` is called
- **THEN** `FormatError` is raised naming `b.kicad_dru` and line 2

#### Scenario: Single-quoted name refused
- **GIVEN** a rules text containing `(rule 'big one' (constraint clearance (min 1mm)))`
- **WHEN** `wrap_rules(text)` is called
- **THEN** `FormatError` is raised; a condition string `"A.NetName == 'X'"` inside double quotes is accepted

#### Scenario: Canary rules round trip
- **GIVEN** the committed canary rules file `tests/data/kicad/tokens/canary/canary.kicad_dru`
- **WHEN** `rules_text(wrap_rules(text))` is parsed again with `wrap_rules`
- **THEN** the two nodes are equal under `tree_equal` and the printed text does not contain `kicad_dru`

### Requirement: Minimum version queries
`min_version(kind, token_path, *, value=None)` SHALL return the matched row's `since_version`. When the row has no dated version, it SHALL return `FORMAT_VERSIONS[kind][since_major]`, or `READ_FLOOR[kind]` when that major has no constant for the kind. It SHALL return `None` when no inventory row matches. `min_major` SHALL return the matched row's `since_major`, or `None`. `token_path` is the head chain from the root, separated by `/`.

#### Scenario: Dated row
- **GIVEN** the packaged inventory with row `pad-padstack` (`since_version = 20240929`)
- **WHEN** `min_version(FileKind.FOOTPRINT, "footprint/pad/padstack")` is called
- **THEN** it returns `20240929`

#### Scenario: Rules row gated by major
- **GIVEN** the packaged inventory with the rules row for `bridged_mask`
- **WHEN** `min_major(FileKind.RULES, "kicad_dru/rule/constraint", value="bridged_mask")` is called
- **THEN** it returns `10`

#### Scenario: Unknown path
- **WHEN** `min_version(FileKind.BOARD, "kicad_pcb/fenolite_nothing")` is called
- **THEN** it returns `None`

### Requirement: Emit check
`check_emittable(node, kind, target_major)` SHALL walk the tree once and return, in document order, issues whose `where` is exactly the locator c0006's `walk` yields for the node, with no prefix:
- `kicad.version.header-missing` (error) when the root has no version;
- `kicad.version.header-too-new` (error) when the header version exceeds the target constant;
- `kicad.token.too-new` (error) for every node or symbol value whose matched row has `since_major > target_major`, with a `hint` naming the row id and its sources;
- `kicad.token.obsolete` (warning) for every match whose row has an `until_major` older than the target;
- `kicad.token.uninventoried` (warning), for worksheet and rules kinds only, for every head or constraint value outside the inventory.

It MUST NOT report unmatched board or footprint paths. It MUST raise `ValueError` for a target outside `TARGET_MAJORS`. It MUST NOT modify the node.

#### Scenario: Padstack allowed for 9.0
- **GIVEN** a board with header `20241229` whose pad contains `(padstack (mode front_inner_back) …)`
- **WHEN** `check_emittable(node, FileKind.BOARD, 9)` is called
- **THEN** no issue of severity `error` is returned

#### Scenario: 10.0 via protection refused for 9.0
- **GIVEN** a board with header `20241229` whose `setup` contains `(tenting (front yes) (back yes))`
- **WHEN** `check_emittable(node, FileKind.BOARD, 9)` is called
- **THEN** the result contains `kicad.token.too-new` issues, one of whose `where` is `/kicad_pcb/setup[0]/tenting[0]/front[0]`

#### Scenario: Header newer than target
- **GIVEN** a board with header `20260206` and only floor tokens
- **WHEN** `check_emittable(node, FileKind.BOARD, 9)` is called
- **THEN** the result contains exactly one issue, `kicad.version.header-too-new`

#### Scenario: Obsolete token for 10.0
- **GIVEN** a board with header `20260206` whose plot parameters contain `(plotinvisibletext no)`
- **WHEN** `check_emittable(node, FileKind.BOARD, 10)` is called
- **THEN** the result contains a `kicad.token.obsolete` warning and no error

#### Scenario: 10.0 rules constraint refused for 9.0
- **GIVEN** a synthetic rules node with a rule `(constraint bridged_mask)`
- **WHEN** `check_emittable(node, FileKind.RULES, 9)` is called
- **THEN** the result contains one `kicad.token.too-new` error naming the row for `bridged_mask`

#### Scenario: Unknown worksheet token
- **GIVEN** a worksheet node containing `(frobnicate 1)`
- **WHEN** `check_emittable(node, FileKind.WORKSHEET, 10)` is called
- **THEN** the result contains one `kicad.token.uninventoried` warning

#### Scenario: Unmatched board path not reported
- **GIVEN** a board with header `20241229` and a `(gr_line …)` child that matches no row
- **WHEN** `check_emittable(node, FileKind.BOARD, 9)` is called
- **THEN** the result is empty

### Requirement: Project file versions
`fenolite.backends.kicad.pro` SHALL expose `PROJECT_VERSIONS = {9: (3, 4), 10: (3, 5)}`, the pairs (`meta.version`, `net_settings.meta.version`) that Fenolite writes for each target in `TARGET_MAJORS`, together with `classify_project(meta_version, net_settings_version)` and `project_major(meta_version, net_settings_version)`. The project file is JSON and MUST stay outside `FileKind`: `FileKind` keeps exactly its six values, `FORMAT_VERSIONS` is unchanged, and `kind_for_suffix` returns `None` for a `.kicad_pro` name.
- `classify_project` MUST return `FUTURE` when `meta.version` is greater than 3 or `net_settings.meta.version` is greater than 5, and `SUPPORTED` otherwise, absent versions included, because KiCad reads a `{}` project (`H-K-TOK-RULES-SILENT`).
- `project_major` MUST return the target whose pair equals the given pair, and `None` for any other pair.
- A `FUTURE` project MUST be readable, with the warning `kicad.version.future`, and MUST NOT be edited: `update_project` MUST raise `FutureFormatError` (`FEN-3002`).
- `update_project` MUST raise `UnsupportedFormatError` (`FEN-3003`) for a `SUPPORTED` project whose pair is not in `PROJECT_VERSIONS`, `{}` and versions 1 and 2 included, with a `hint` saying to re-save the project in KiCad 9 or 10 or to synthesise a new one.
- An update MUST keep the existing pair, except the lossy target-9 path of "Project files are gated by target" in `kicad-file-backend`.
- Every pair MUST cite its source in `docs/formats/kicad/project.md` and carry the evidence level it has reached (`H-K-PRO-VERSION`).

#### Scenario: Pairs per target
- **GIVEN** the packaged `pro` module
- **WHEN** `PROJECT_VERSIONS[9]` and `PROJECT_VERSIONS[10]` are read
- **THEN** they equal `(3, 4)` and `(3, 5)`

#### Scenario: Synthesised versions follow the target
- **GIVEN** any design
- **WHEN** it is synthesised with `board_name="b"` for target 9 and for target 10
- **THEN** the target-9 text has `meta.version` 3 and `net_settings.meta.version` 4, and the target-10 text has 3 and 5

#### Scenario: Future project is read-only
- **GIVEN** a project text with `"meta": {"version": 4}`
- **WHEN** `read_project(text)` and then `update_project(text, design, target=10)` are called
- **THEN** the status is `FUTURE`, the issues hold `kicad.version.future`, and the update raises `FutureFormatError` with `cli_code == "FEN-3002"`

#### Scenario: Older project readable, not editable
- **GIVEN** a project text with `meta.version` 2
- **WHEN** it is read and then updated for target 10
- **THEN** the read succeeds with status `SUPPORTED` and `major is None`, and the update raises `UnsupportedFormatError` whose `hint` names KiCad 9 or 10

#### Scenario: Project stays outside FileKind
- **WHEN** `kind_for_suffix("bench.kicad_pro")` is called and the members of `FileKind` are listed
- **THEN** the call returns `None` and `FileKind` has exactly the six members `kicad_pcb`, `kicad_mod`, `kicad_sch`, `kicad_sym`, `kicad_wks` and `kicad_dru`

### Requirement: Isolated worksheet version oracle

The worksheet version boundary oracle SHALL run every version probe on fresh input copies with a private KiCad configuration directory and the C locale, without inheriting KICAD settings. Every probe SHALL also receive private home, cache, data and temporary directories, including its instance-lock location. Each probe SHALL finish successfully and produce an SVG. The next-version probe SHALL require both the drawing-sheet loading error and the more-recent-version diagnostic, without retrying or skipping failures.

#### Scenario: Accepted worksheet version

- **WHEN** the worksheet uses the recorded version constant for the installed KiCad major
- **THEN** an isolated export produces an SVG without a drawing-sheet loading error

#### Scenario: Future worksheet version

- **WHEN** the worksheet version is one greater than the recorded constant
- **THEN** a separate isolated export reports both `Error loading drawing sheet` and `more recent version`, and produces the fallback SVG

