# verification-evidence Specification

## Purpose
Keep the evidence behind Fenolite's claims machine-checked: one grammar for evidence labels, a strict reader of the hypothesis register (`docs/hypotheses.md`) and its reserved id families, a guard that every hypothesis id cited in live text is registered, the release rule (author reports and refuted rows never count as release support), and the change-id and ADR numbering rules. Package: `fenolite.verify`; guard: `tests/unit/test_hypotheses_register.py`.
## Requirements
### Requirement: Verification package
The package `fenolite.verify` SHALL provide the modules `verify/hypotheses.py` and `verify/evidence.py` and re-export their public names from `fenolite.verify`.
- The package MUST import only the standard library and `fenolite.core`.
- Importing it MUST NOT load `fenolite.model`, `fenolite.geometry` or `fenolite.backends`.

#### Scenario: Import stays light
- **WHEN** `uv run python -c "import sys, fenolite.verify; print(sorted(m for m in sys.modules if m.startswith(('fenolite.model', 'fenolite.geometry', 'fenolite.backends'))))"` runs
- **THEN** it prints `[]` and exits 0

#### Scenario: Only the standard library and core are imported
- **GIVEN** the modules of `src/fenolite/verify/`
- **WHEN** `uv run pytest tests/unit/verify/test_levels.py` runs its AST check over every `import` and `from … import` statement, at any depth, including those inside functions and `try` blocks
- **THEN** every statement names a module in `sys.stdlib_module_names`, `fenolite.core` or a module below it, or a module of `fenolite.verify` itself

#### Scenario: Layering holds
- **GIVEN** the modules of `src/fenolite/verify/`
- **WHEN** `uv run pytest tests/unit/test_import_graph.py` runs
- **THEN** it passes

### Requirement: Evidence label grammar
`fenolite.verify.parse_level(text)` SHALL return the `Level` that a label text denotes. The rules are these:
- Every `Level` value written exactly MUST parse to that level.
- A parenthesis attached to the name, with no space, MUST be accepted only after `ORACLE-VERIFIED`, where it names the tool, and after `ALTIUM-VERIFIED`, where it is required. Its content MUST be non-empty and hold no parenthesis.
- For `ALTIUM-VERIFIED`, the first `;`-separated field of that parenthesis, stripped, MUST be `kit` (giving `ALTIUM_VERIFIED_KIT`) or `author-report` (giving `ALTIUM_VERIFIED_AUTHOR_REPORT`).
- A scope MUST be one space followed by a parenthesis with non-empty content and no nested parenthesis, at the end of the text. It is allowed after any label.
- Any other text MUST raise `ValueError` whose message quotes the text.

#### Scenario: Scoped KiCad label
- **GIVEN** the `Level` enumeration of `fenolite.core.evidence`
- **WHEN** `parse_level("KICAD-VERIFIED (9.0.x, 10.0.x)")` is called
- **THEN** it returns `Level.KICAD_VERIFIED`

#### Scenario: Author-report sub-label
- **WHEN** `parse_level("ALTIUM-VERIFIED(author-report; AD 24.x; 2026-09; no artefact)")` is called
- **THEN** it returns `Level.ALTIUM_VERIFIED_AUTHOR_REPORT`

#### Scenario: Kit sub-label
- **WHEN** `parse_level("ALTIUM-VERIFIED(kit)")` is called
- **THEN** it returns `Level.ALTIUM_VERIFIED_KIT`

#### Scenario: Oracle with tool and scope
- **WHEN** `parse_level("ORACLE-VERIFIED(freerouting) (2.4.1)")` is called
- **THEN** it returns `Level.ORACLE_VERIFIED`

#### Scenario: Kit label with scope
- **WHEN** `parse_level("ALTIUM-VERIFIED(kit) (24.x)")` is called
- **THEN** it returns `Level.ALTIUM_VERIFIED_KIT`

#### Scenario: Every level value parses
- **WHEN** `parse_level(level.value)` is called for every `level` in `Level`
- **THEN** each call returns `level`

#### Scenario: Malformed labels are rejected
- **WHEN** `parse_level` is called with each of `"ALTIUM-VERIFIED"`, `"ALTIUM-VERIFIED(report)"`, `"kicad-verified"`, `"INFERRED(x)"`, `"KICAD-VERIFIEDX"` and `""`
- **THEN** each call raises `ValueError`, and each message contains the text it was given

### Requirement: Hypothesis register table
`docs/hypotheses.md` SHALL hold exactly one table whose header is `| id | backend | statement | level | test or kit request | criterion | result | date |`. `fenolite.verify.load_register(path)` SHALL return its rows as `HypothesisRow` values, in file order.
- Cells MUST be split on unescaped pipes, and each row MUST have exactly 8 cells.
- The id MUST fully match `ID_PATTERN`, which is `\bH-[AGK]-[A-Z0-9]+(?:-[A-Z0-9]+)*`.
- The level cell MUST be accepted by `parse_level`. `level` holds the parsed `Level`, and `level_text` holds the cell as written.
- A malformed row MUST raise `ValueError` naming `<path>:<line>` and the reason. A file without the table, or with two such tables, MUST raise `ValueError` naming the path.
- `HypothesisRow.refuted` MUST be true exactly when the result starts with `refuted`. `HypothesisRow.successor` MUST be the first id after the words `superseded by`, or `None`.

#### Scenario: Live register loads
- **GIVEN** `docs/hypotheses.md`
- **WHEN** `load_register("docs/hypotheses.md")` is called
- **THEN** it returns as many rows as `grep -c '^| H-' docs/hypotheses.md` prints, and every `level` is a `Level`

#### Scenario: Level text is kept
- **GIVEN** a register file whose only row has the level cell `KICAD-VERIFIED (10.0.x)`
- **WHEN** it is loaded
- **THEN** the row has `level is Level.KICAD_VERIFIED` and `level_text == "KICAD-VERIFIED (10.0.x)"`

#### Scenario: Seven cells are rejected
- **GIVEN** a register file `reg.md` whose row on line 3 has seven cells
- **WHEN** it is loaded
- **THEN** a `ValueError` is raised whose message names `reg.md:3` and `8 cells`

#### Scenario: Unknown level is rejected
- **GIVEN** a register file whose row on line 3 has the level cell `MAYBE`
- **WHEN** it is loaded
- **THEN** a `ValueError` is raised whose message names line 3 and `MAYBE`

#### Scenario: Successor is parsed
- **GIVEN** the row `H-K-TOK-FUTURE` of `docs/hypotheses.md`
- **WHEN** the register is loaded
- **THEN** the row has `refuted is True` and `successor == "H-K-TOK-FUTURE-2"`

#### Scenario: Partial refutation is not a refutation
- **GIVEN** the row `H-K-FMT-MIXED`, whose result starts with `partly refuted`
- **WHEN** the register is loaded
- **THEN** the row has `refuted is False`

### Requirement: Reserved id families
`docs/hypotheses.md` SHALL state, above the register table, the following rules:
- ids keep the prefixes `H-A-` (second backend), `H-G-` (general) and `H-K-` (KiCad);
- rows about a tool acting on KiCad files use `H-K-`, and routing rows use the `H-K-KRT-` prefix;
- Specctra rows use `H-G-DSN-*`, with backend `specctra`.

It SHALL also hold a reserved-families table with the header `| family | backend | rows for | owner |`. `fenolite.verify.load_families(path)` SHALL return the families of that table as written.
- Family cells MUST be written in backticks. A family cell, stripped and with one pair of enclosing backticks removed, MUST fully match an id stem followed by `-*`. Otherwise `load_families` MUST raise `ValueError` naming `<path>:<line>`.
- A file without a reserved-families table MUST give the empty tuple. A file with two such tables MUST raise `ValueError` naming the path.
- The table MUST list `H-A-WRITE-*`, `H-A-PH-*` and `H-G-DSN-*`; families MUST be removed once their rows are registered.

#### Scenario: Families of the live register
- **WHEN** `load_families("docs/hypotheses.md")` is called
- **THEN** the result contains `"H-A-WRITE-*"`, `"H-A-PH-*"` and `"H-G-DSN-*"`, but not `"H-K-KRT-*"` after c0016 registers its rows

#### Scenario: Reserved family
- **GIVEN** a temporary register holding only `H-K-UNIT`, whose reserved-families table lists `H-A-WRITE-*`, and `docs/x.md` citing `H-A-WRITE-*`
- **WHEN** `citation_problems(tree)` is called
- **THEN** it returns no problem

### Requirement: Register integrity
`tests/unit/test_hypotheses_register.py` SHALL check the register with `register_problems(rows)`. That function SHALL return one message per problem, naming the row, for each of these rules:
- ids MUST be unique;
- a refuted row MUST name a successor that is registered and differs from the row's own id;
- a row of family `H-A-WRITE-*` or `H-A-PH-*` MUST follow "Author-report rows".

The live test MUST load `docs/hypotheses.md` with `load_register`, so a row with the wrong cell count or an unparsable level fails it. The live test MUST pass on the current register.

#### Scenario: Duplicate id
- **GIVEN** rows that contain two rows with id `H-K-UNIT`
- **WHEN** `register_problems(rows)` is called
- **THEN** it returns one problem naming `H-K-UNIT` and the word `duplicate`

#### Scenario: Refuted row without a registered successor
- **GIVEN** rows that hold `H-K-SEXPR-NUM-WRITE`, with result `refuted; superseded by H-K-SEXPR-NUM-WRITE-2`, and no row `H-K-SEXPR-NUM-WRITE-2`
- **WHEN** `register_problems(rows)` is called
- **THEN** it returns one problem naming both ids

#### Scenario: Refuted row with its successor
- **GIVEN** the same rows plus a row `H-K-SEXPR-NUM-WRITE-2`
- **WHEN** `register_problems(rows)` is called
- **THEN** it returns no problem

#### Scenario: Row superseded by itself
- **GIVEN** a row `H-K-TOK-FUTURE` with result `refuted; superseded by H-K-TOK-FUTURE`
- **WHEN** `register_problems(rows)` is called
- **THEN** it returns one problem naming `H-K-TOK-FUTURE` and stating that the row is superseded by itself

#### Scenario: Live register passes
- **WHEN** `uv run pytest tests/unit/test_hypotheses_register.py::test_register_loads tests/unit/test_hypotheses_register.py::test_register_integrity` runs
- **THEN** it passes

### Requirement: Refuted rows keep their id
A refuted row SHALL stay in the register under its id. Its result MUST start with `refuted; superseded by <successor id>`, followed by the observation. Its level MUST be the level of the run that refuted the claim. A result that starts with other text, such as `partly refuted`, is not a refutation and needs no successor.
- The level of a refuted row grades the refutation, not the claim. A refuted row MUST NOT count as release-verified support for an operation.
- `fenolite.verify.is_release_evidence(row)` SHALL return `True` exactly when `row.refuted` is false and `release_verified(row.level)` is true. Any reader that counts register rows as release support MUST use it.

#### Scenario: Number spelling row
- **GIVEN** `docs/hypotheses.md` with the two refuted rows relabelled
- **WHEN** `grep -E '^\| H-K-SEXPR-NUM-WRITE ' docs/hypotheses.md` runs
- **THEN** the row has level `KICAD-VERIFIED (10.0.x)`, and its result starts with `refuted; superseded by` followed by `H-K-SEXPR-NUM-WRITE-2`

#### Scenario: Future header row
- **WHEN** `grep -E '^\| H-K-TOK-FUTURE ' docs/hypotheses.md` runs
- **THEN** the row has level `KICAD-VERIFIED (9.0.x, 10.0.x)`, and its result starts with `refuted; superseded by` followed by `H-K-TOK-FUTURE-2`

#### Scenario: Both relabelled rows
- **WHEN** `grep -cE '^\| H-K-(SEXPR-NUM-WRITE|TOK-FUTURE) \|.*\| refuted; superseded by ' docs/hypotheses.md` runs
- **THEN** it prints `2`

#### Scenario: Refuted row gives no release support
- **GIVEN** the row `H-K-TOK-FUTURE` of `docs/hypotheses.md`, refuted and labelled `KICAD-VERIFIED (9.0.x, 10.0.x)`
- **WHEN** `is_release_evidence(row)` is called
- **THEN** it returns `False`, although `release_verified(row.level)` returns `True`

#### Scenario: Successor gives release support
- **GIVEN** the row `H-K-TOK-FUTURE-2` of `docs/hypotheses.md`, not refuted and labelled `KICAD-VERIFIED (9.0.x, 10.0.x)`
- **WHEN** `is_release_evidence(row)` is called
- **THEN** it returns `True`

#### Scenario: No refuted row counts
- **GIVEN** the rows of `docs/hypotheses.md` whose `refuted` is `True`
- **WHEN** `is_release_evidence(row)` is called for each of them
- **THEN** every call returns `False`

### Requirement: Cited ids are registered
The guard SHALL scan with `fenolite.verify.cited_ids` every UTF-8 file under `docs/`, `openspec/specs/`, `openspec/changes/`, `src/`, `tests/` and `tools/`, and every `*.md` file at the repository root, such as `CHANGELOG.md`. It MUST fail when a cited id is not registered, naming the file and the id.
- The scan MUST exclude `openspec/changes/archive/`, `tests/corpus/cache/`, every file or folder whose name starts with `.`, and every `__pycache__` folder.
- A root that is a file MUST be scanned itself.
- A citation is a match of `ID_PATTERN`. The exceptions are the family references, the proposed ids and the synthetic literals, each defined by its own requirement.
- `cited_ids(roots, *, base, exclude=())` MUST return a mapping from each cited id or family to the sorted POSIX paths, relative to `base`, of the files that cite it.

#### Scenario: Unregistered id in a document
- **GIVEN** a temporary tree whose `docs/hypotheses.md` registers only `H-K-UNIT` and whose `docs/x.md` cites `H-K-02`
- **WHEN** `citation_problems(tree)` is called
- **THEN** it returns exactly one problem, naming `docs/x.md` and `H-K-02`

#### Scenario: Registered id passes
- **GIVEN** the same tree, where `docs/x.md` cites only `H-K-UNIT`
- **WHEN** `citation_problems(tree)` is called
- **THEN** it returns no problem

#### Scenario: Unregistered id in the changelog
- **GIVEN** a temporary tree whose `docs/hypotheses.md` registers only `H-K-UNIT` and whose top-level `CHANGELOG.md` cites `H-K-02`
- **WHEN** `citation_problems(tree)` is called
- **THEN** it returns exactly one problem, naming `CHANGELOG.md` and `H-K-02`

#### Scenario: Dot files are skipped
- **GIVEN** the same register, and `H-K-02` cited only in `openspec/changes/c0099-x/.openspec.yaml`
- **WHEN** `citation_problems(tree)` is called
- **THEN** it returns no problem

#### Scenario: Archived changes are history
- **GIVEN** the same register, and `H-K-02` cited only in `openspec/changes/archive/2026-01-01-c0001-x/design.md`
- **WHEN** `citation_problems(tree)` is called
- **THEN** it returns no problem

#### Scenario: Live tree passes
- **WHEN** `uv run pytest tests/unit/test_hypotheses_register.py::test_cited_ids_registered` runs
- **THEN** it passes

### Requirement: Family references
A match of `ID_PATTERN` followed by `-`, `*` or `…` SHALL be read as the family reference `<stem>-*`. A following `-` cannot continue the id, because the pattern is greedy, so this case covers both `-*` and a prefix written with a trailing hyphen, as in a `grep` pattern. A family reference SHALL pass in any of these cases:
- a registered id starts with `<stem>-`;
- `<stem>` is itself registered;
- `<stem>-*` is a reserved family.

Otherwise the guard MUST fail, naming the file and the family.

#### Scenario: Stem extended by a row
- **GIVEN** a temporary register holding `H-K-FMT-INDENT`, and a document that cites `H-K-FMT-*`
- **WHEN** `citation_problems(tree)` is called
- **THEN** it returns no problem

#### Scenario: Stem with no row
- **GIVEN** a temporary register holding only `H-K-UNIT`, and `docs/x.md` citing `H-K-TOK-*`
- **WHEN** `citation_problems(tree)` is called
- **THEN** it returns one problem naming `docs/x.md` and `H-K-TOK-*`

#### Scenario: Reserved family
- **GIVEN** a temporary register holding only `H-K-UNIT`, whose reserved-families table lists `H-K-KRT-*`, and `docs/x.md` citing `H-K-KRT-*`
- **WHEN** `citation_problems(tree)` is called
- **THEN** it returns no problem

#### Scenario: Prefix in a grep pattern
- **GIVEN** a temporary register holding `H-K-FMT-INDENT`, and `docs/x.md` containing `grep -c '^| H-K-FMT-' docs/hypotheses.md`
- **WHEN** `citation_problems(tree)` is called
- **THEN** it returns no problem

#### Scenario: Range notation
- **GIVEN** a temporary register holding `H-K-00` and `H-K-03`, and `docs/x.md` citing `H-K-00…H-K-03`
- **WHEN** `citation_problems(tree)` is called
- **THEN** it returns no problem

### Requirement: Ids proposed by active changes
`fenolite.verify.proposed_ids(changes_dir)` SHALL return the ids that start the first column of every table under the heading `## Hypotheses registered by this change`, up to the next `## ` heading, in the `design.md` of every change folder directly under `changes_dir` except `archive`.
- A first cell MUST contribute the id it starts with, after stripping and removing one pair of enclosing backticks. A first cell that does not start with an id MUST be ignored.
- Inside `openspec/changes/<active change>/`, the guard MUST treat a proposed id as registered, for plain ids and for family references.
- Everywhere else, proposed ids MUST NOT count.

#### Scenario: Proposed id cited by an active change
- **GIVEN** a temporary tree whose register holds only `H-K-UNIT`, whose `openspec/changes/c0099-x/design.md` lists `H-K-SEXPR-STRICT` in its hypotheses table, and whose `openspec/changes/c0098-y/tasks.md` cites `H-K-SEXPR-STRICT`
- **WHEN** `citation_problems(tree)` is called
- **THEN** it returns no problem

#### Scenario: Proposed id cited outside the changes
- **GIVEN** the same tree, where `src/fenolite/x.py` also cites `H-K-SEXPR-STRICT`
- **WHEN** `citation_problems(tree)` is called
- **THEN** it returns one problem naming `src/fenolite/x.py`

#### Scenario: Archived designs propose nothing
- **GIVEN** a temporary tree whose register holds only `H-K-UNIT`, where only `openspec/changes/archive/2026-01-01-c0097-z/design.md` lists `H-K-SEXPR-STRICT` in its hypotheses table, and `openspec/changes/c0098-y/tasks.md` cites it
- **WHEN** `citation_problems(tree)` is called
- **THEN** it returns one problem naming `openspec/changes/c0098-y/tasks.md`

#### Scenario: Second table and qualified cell
- **GIVEN** a temporary `openspec/changes/c0099-x/design.md` whose section "Hypotheses registered by this change" holds two tables, the second with the first cell `H-K-SEXPR-STRICT (c0006)`, followed by a `## Evidence level per behaviour (before merge)` section whose table starts with `H-K-SEXPR-ESCAPES`
- **WHEN** `proposed_ids(tree / "openspec/changes")` is called
- **THEN** the result contains `H-K-SEXPR-STRICT` and does not contain `H-K-SEXPR-ESCAPES`

### Requirement: Synthetic test literals
The guard SHALL hold an explicit allowlist `SYNTHETIC`, which maps a repository path to the unregistered ids allowed in that file.
- It MUST name only two paths: `tests/unit/core/test_evidence.py`, with the two synthetic ids of `test_combine`, and the guard file itself, with the same two ids.
- The same ids cited in any other file MUST fail.

#### Scenario: The evidence test passes
- **WHEN** the guard runs on the live tree
- **THEN** no problem names `tests/unit/core/test_evidence.py`

#### Scenario: A synthetic id elsewhere fails
- **GIVEN** a temporary tree whose `tests/unit/test_other.py` contains one of the ids that `SYNTHETIC` allows in `tests/unit/core/test_evidence.py`
- **WHEN** `citation_problems(tree)` is called
- **THEN** it returns one problem naming `tests/unit/test_other.py`

#### Scenario: The allowlist is closed
- **WHEN** `SYNTHETIC` is inspected
- **THEN** its keys are exactly `tests/unit/core/test_evidence.py` and `tests/unit/test_hypotheses_register.py`

### Requirement: Ids cited only in archived changes are registered
`docs/hypotheses.md` SHALL register `H-K-LIB-DRC` and `H-G-SHAPELY-GC`. Until their owning changes settle them, both MUST have level `INFERRED` and result `pending`.
- The test column of `H-K-LIB-DRC` MUST name `tests/kicad/board/test_flip_oracle.py::test_lib_drc` and the board writer change (c0017).
- The test column of `H-G-SHAPELY-GC` MUST name `tests/unit/geometry/test_boolean_shapely.py::test_line_parts_dropped` and the boolean-backends change (v0.3).

#### Scenario: Both rows exist
- **GIVEN** `docs/hypotheses.md` with the two pending rows registered
- **WHEN** `grep -cE '^\| (H-K-LIB-DRC|H-G-SHAPELY-GC) ' docs/hypotheses.md` runs
- **THEN** it prints `2`

#### Scenario: Settling tests are named
- **WHEN** `load_register("docs/hypotheses.md")` is called
- **THEN** the test column of `H-K-LIB-DRC` contains `test_flip_oracle.py::test_lib_drc` and `c0017`, and the test column of `H-G-SHAPELY-GC` contains `test_boolean_shapely.py::test_line_parts_dropped` and `v0.3`

### Requirement: Release-verified levels
`fenolite.verify.release_verified(level)` SHALL return `True` exactly for the levels in the explicit set `RELEASE_VERIFIED`: `ALTIUM_VERIFIED_KIT`, `KICAD_VERIFIED`, `ORACLE_VERIFIED` and `CORPUS_VERIFIED`. For every other `Level` it MUST return `False`.

#### Scenario: Author report is not release-verified
- **WHEN** `release_verified(Level.ALTIUM_VERIFIED_AUTHOR_REPORT)` is called
- **THEN** it returns `False`

#### Scenario: KiCad verification is release-verified
- **WHEN** `release_verified(Level.KICAD_VERIFIED)` is called
- **THEN** it returns `True`

#### Scenario: Whole level table
- **GIVEN** the `Level` enumeration of `fenolite.core.evidence`
- **WHEN** `release_verified` is called for every `Level`
- **THEN** it returns `True` for `ALTIUM_VERIFIED_KIT`, `KICAD_VERIFIED`, `ORACLE_VERIFIED` and `CORPUS_VERIFIED`, and `False` for `ALTIUM_VERIFIED_AUTHOR_REPORT`, `INFERRED`, `UNKNOWN` and `UNVERIFIED`

### Requirement: Author reports never promote an operation
A result whose evidence depends on an author report SHALL NOT be release-verified, whatever its other parts are.
- `Evidence.combine` of an `ALTIUM_VERIFIED_AUTHOR_REPORT` item with any stronger items MUST give the level `ALTIUM_VERIFIED_AUTHOR_REPORT`, and `release_verified` of that level MUST be `False`.
- No register row whose level is `ALTIUM_VERIFIED_AUTHOR_REPORT` counts as release-verified.

#### Scenario: Combined with a KiCad result
- **WHEN** `Evidence.combine(Evidence(Level.ALTIUM_VERIFIED_AUTHOR_REPORT), Evidence(Level.KICAD_VERIFIED, "kicad-cli 10.0.6"))` is called
- **THEN** the result has level `Level.ALTIUM_VERIFIED_AUTHOR_REPORT`, and `release_verified` of that level is `False`

#### Scenario: Combined with a kit result
- **WHEN** `Evidence.combine(Evidence(Level.ALTIUM_VERIFIED_KIT), Evidence(Level.ALTIUM_VERIFIED_AUTHOR_REPORT))` is called
- **THEN** the result has level `Level.ALTIUM_VERIFIED_AUTHOR_REPORT`

#### Scenario: Register rows
- **GIVEN** the rows of `docs/hypotheses.md` whose level is `Level.ALTIUM_VERIFIED_AUTHOR_REPORT`
- **WHEN** `release_verified(row.level)` is called for each of them
- **THEN** every call returns `False`

### Requirement: Author-report rows
`docs/hypotheses.md` SHALL hold one `H-A-WRITE-*` row per second-backend file type that the author reports as validated, and one `H-A-PH-*` row per placeholder or omission choice that the author reports. Each row MUST meet these rules:
- backend `altium`;
- statements in generic format terms;
- no artefact, path, screenshot, design name or identifier from any organisation;
- registered only for a validation on files the author created or may use for this purpose, opened with a licence the author may use for it (`LEGAL.md`, block A and its prohibitions P3 and P4). A file type validated only on other files gets no row;
- each concrete value in an `H-A-PH-*` row is a choice made by the author's own writer, never a constant measured on or copied from non-public files (`LEGAL.md`, block B). When the provenance of a value is not clear, the row names the kind of choice and leaves the value out;
- level `ALTIUM-VERIFIED(author-report; AD <major>.<minor or x>; <YYYY-MM-DD or YYYY-MM>; no artefact)`. While the author's values are missing, the level is `INFERRED` instead, with a result that starts with `pending (author report)`;
- a test column that starts with `kit request`.

`register_problems` MUST report a row of either family that has any other level. The check is exact: the level cell is `ALTIUM-VERIFIED(` followed by four `;`-separated fields and `)`, with no scope; stripped, field 1 is `author-report`, field 2 fully matches `AD \d+\.(\d+|x)`, field 3 fully matches `\d{4}-\d{2}(-\d{2})?`, and field 4 equals `no artefact`.

#### Scenario: Rows exist for both families
- **WHEN** `grep -c '^| H-A-WRITE-' docs/hypotheses.md` and `grep -c '^| H-A-PH-' docs/hypotheses.md` run
- **THEN** each prints at least `1`

#### Scenario: Bare author-report label is refused
- **GIVEN** rows with one row of family `H-A-WRITE-*` whose level cell is the bare `ALTIUM-VERIFIED(author-report)`
- **WHEN** `register_problems(rows)` is called
- **THEN** it returns one problem naming that row and the expected form

#### Scenario: Malformed version and date fields are refused
- **GIVEN** rows with one row of family `H-A-WRITE-*` whose level cell is `ALTIUM-VERIFIED(author-report; 24; soon; no artefact)`
- **WHEN** `register_problems(rows)` is called
- **THEN** it returns one problem naming that row and the expected form

#### Scenario: Well-formed author-report row is accepted
- **GIVEN** rows with one row of family `H-A-WRITE-*` whose level cell is `ALTIUM-VERIFIED(author-report; AD 24.x; 2026-09; no artefact)` and whose test column starts with `kit request`
- **WHEN** `register_problems(rows)` is called
- **THEN** it returns no problem

#### Scenario: Pending rows are accepted
- **GIVEN** rows with one row of family `H-A-PH-*` whose level is `INFERRED` and whose result starts with `pending (author report)`
- **WHEN** `register_problems(rows)` is called
- **THEN** it returns no problem

#### Scenario: Validation on files the author may not use gets no row
- **GIVEN** an author report for a file type that was validated only on files the author may not use for this purpose, or only with a licence the author may not use for it
- **WHEN** the author-report rows are registered
- **THEN** no `H-A-WRITE-*` row is registered for that file type, and the design table "Hypotheses registered by this change" is amended to match

#### Scenario: Value of unclear provenance is left out
- **GIVEN** a placeholder choice whose value the author cannot trace to a choice of the author's own writer
- **WHEN** its `H-A-PH-*` row is registered
- **THEN** the statement names the kind of choice and gives no value

#### Scenario: Rows pass the residue scan with the private gate on
- **GIVEN** the author-report rows in `docs/hypotheses.md`, and the maintainer's private token and blob lists present under `private/`
- **WHEN** `make residue` runs, which runs `tools/residue/scan.py` with those lists exported
- **THEN** it exits 0, and its summary line ends with `private gate: on`; a run that prints `private gate: skipped` does not satisfy this scenario

### Requirement: Second-backend source licence
The licence cell of S-0002 in `docs/evidence/sources.md` SHALL state the licence that the page declares, or `not stated on the page (checked <YYYY-MM-DD>)`. It MUST NOT say `to verify`.

#### Scenario: Licence cell settled
- **GIVEN** `docs/evidence/sources.md` after the page of S-0002 was checked
- **WHEN** `grep '^| S-0002 ' docs/evidence/sources.md | grep -c 'to verify'` runs
- **THEN** it prints `0`

### Requirement: Change id allocation
`openspec/README.md` SHALL hold a "Change ids" table that maps every id from c0009 to c0025 to its slug, roadmap item and parent.
- c0009 to c0016 MUST keep the numbers of roadmap items 0009 to 0016.
- Split-offs and follow-ups MUST take c0017 and later numbers in implementation order, with their parent named. A new split-off MUST take the next free number.
- Ids MUST have the form `cNNNN-<slug>`. Lettered ids such as `c0009a` MUST NOT be used.
- The README MUST state that `tokens.yaml` in older planning text means `src/fenolite/backends/kicad/data/tokens.toml`.

#### Scenario: Table is complete
- **GIVEN** `openspec/README.md` with its section "Change ids"
- **WHEN** `grep -cE '^\| c00(09|1[0-9]|2[0-5]) ' openspec/README.md` runs
- **THEN** it prints `17`

#### Scenario: Split-offs name their parent
- **WHEN** the rows `c0017` and `c0021` of the table are read
- **THEN** `c0017` names `kicad-board-writer` with parent `0009`, and `c0021` names `kicad-libs-cache` with parent `c0008`

#### Scenario: Token file note
- **WHEN** `grep -n 'tokens.yaml' openspec/README.md` runs
- **THEN** the line it prints also names `tokens.toml`

### Requirement: ADR numbering
`docs/adr/README.md` SHALL state these numbering rules:
- ADRs are numbered in order of allocation and never renumbered. The README MUST NOT keep the older wording "numbered in order of creation".
- The next free number is one above the highest number written or allocated. A new ADR takes it when its change is proposed, and numbers are never reserved.
- ADR-0002 is the only number written out of order: c0001 allocated it before 0003 and 0004 were written, and c0009 writes it.
- ADR numbers are not tied to planning decision numbers.

Informative example: with 0001 to 0004 written, the next ADR is 0005.

The ADR files MUST keep passing `tests/unit/test_adrs.py`.

#### Scenario: Note present
- **GIVEN** `docs/adr/README.md` with the numbering note
- **WHEN** `grep -n 'ADR-0002' docs/adr/README.md` runs
- **THEN** it prints the numbering note

#### Scenario: ADR checks pass
- **WHEN** `uv run pytest tests/unit/test_adrs.py` runs
- **THEN** it passes

#### Scenario: Next free number rule
- **GIVEN** `docs/adr/README.md` with the numbering note
- **WHEN** `grep -n 'next free number' docs/adr/README.md` runs
- **THEN** the line it prints says that the next free number is one above the highest number written or allocated, and that numbers are never reserved

#### Scenario: Older wording removed
- **GIVEN** `docs/adr/README.md` with the numbering note
- **WHEN** `grep -c 'numbered in order of creation' docs/adr/README.md` runs
- **THEN** it prints `0`

