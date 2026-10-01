## Context

- **Register.** `docs/hypotheses.md` holds one table with eight columns, `| id | backend | statement | level | test or kit request | criterion | result | date |`, fixed by c0001 Decision 9. At commit 351a7a8 (2026-10-01) it has 47 rows: 37 `H-K-*`, 9 `H-G-*` and 1 `H-A-*` (`H-A-UNIT`). Every row has 8 cells.
  - Level cells use four forms: `INFERRED`, `KICAD-VERIFIED (9.0.x, 10.0.x)`, `KICAD-VERIFIED (10.0.x)` and `KICAD-VERIFIED (9.0.x)`.
  - Only one test reads the register: `tests/unit/backends/kicad/test_inventory.py` collects its ids with the pattern `^\| (H-[A-Z0-9-]+) ` and fails when a `tokens.toml` row names an unregistered hypothesis (`test_provenance_sources_and_hypotheses_registered`). Nothing checks the register's integrity or the ids cited in text; only review does. That pattern keeps working after this change, because the reserved-family rows of Decision 7 start with a backtick and do not match it.
- **Refuted rows.** Three results contain the word "refuted":
  - `H-K-SEXPR-NUM-WRITE`: refuted with `kicad-cli` 10.0.6. The successor `H-K-SEXPR-NUM-WRITE-2` is `KICAD-VERIFIED (10.0.x)`, but the row's level is still `INFERRED`.
  - `H-K-TOK-FUTURE`: refuted with 9.0.9 and 10.0.6. The successor `H-K-TOK-FUTURE-2` is `KICAD-VERIFIED (9.0.x, 10.0.x)`, but the row's level is still `INFERRED`.
  - `H-K-FMT-MIXED`: "partly refuted on 9.0 writes", with 10.0 pending. This row is still open.
- **Cited ids.** A scan of the live text on 2026-10-01 with the pattern of Decision 6 finds the following (not normative):
  - outside active changes, every cited id is registered, except the two synthetic ids of `tests/unit/core/test_evidence.py::test_combine` (a KiCad id numbered 1 and a general id numbered 2). Inside active changes, the other unregistered ids are all proposed by an active change (Decision 8);
  - the family references `H-K-FMT-*`, `H-K-LIB-*`, `H-K-SEXPR-*` and `H-K-TOK-*` each extend registered rows;
  - `H-K-LIB-DRC` (c0008 Decision 18) and `H-G-SHAPELY-GC` (c0005, section "Hand-over") are cited only in archived designs, so a scan of live text cannot catch them.
- **Labels.** `fenolite.core.evidence.Level` orders eight levels, strongest first. `ALTIUM_VERIFIED_AUTHOR_REPORT` sits between `CORPUS_VERIFIED` and `INFERRED` (`core-primitives`, "Evidence labels", which also fixes `min_level`). `Evidence.combine` returns the lowest level; it is defined only in `src/fenolite/core/evidence.py` and tested by `tests/unit/core/test_evidence.py::test_combine`. The scenarios of this change's requirement "Author reports never promote an operation" are the first spec text to pin `combine`.
  - The module docstring says an author report never promotes an operation in the release matrix. No function says which levels count as verified for a release.
  - `tests/unit/test_format_facts.py::_label` parses labels with an optional scope, for the format pages only.
- **Sources.** `docs/evidence/sources.md` has 42 rows at the same commit. Four licence cells still say "to verify": S-0002, S-0013, S-0015 and S-0017.
  - S-0002 is the dev-docs import page that gives the second backend's length unit (registered by c0004).
  - S-0001 and S-0040 are on the same site, and their cells read "not stated on the page (checked 2026-10-01)".
- **Second backend.** `H-A-UNIT` is the only `H-A-*` row. Before Fenolite, the author wrote second-backend files with an earlier writer and opened them in the native tool. The project plan asks to record this as author reports. The scope is still to be confirmed (Open Questions).
- **Numbering.**
  - c0001 Decision 8 allocated ADR-0002 (KiCad backend) to c0006, which did not write it. ADR-0001, 0003 and 0004 exist (`docs/adr/README.md`), and `tests/unit/test_adrs.py` requires those three files.
  - This batch keeps plan items as c0009–c0016 and numbers split-offs from c0017 on.
  - The token inventory is `src/fenolite/backends/kicad/data/tokens.toml` (c0007). Older planning text calls it `tokens.yaml`.
- **Batch load.** The hypothesis tables of the batch drafts on 2026-10-01 propose 20 new rows: 5 in c0009, 3 in c0017, 5 in c0018 and 7 in c0010. c0017 also names the settling tests of 3 existing `H-G-*` rows, of `H-K-LIB-DRC` and of c0009's `H-K-UUID-KEEP`. This change adds 10 rows (table "Hypotheses registered by this change").
  - **Correction of the brief.** The brief says the four later changes add "about 35 rows". Their drafts add 20, plus any `-2` successor that a refutation creates. The proposal uses the measured count.
  - A dry run of Decisions 6 to 9 over the current drafts (2026-10-01, after review) finds no problem: every cited id is registered, proposed by an active change, a family stem or one of the two synthetic literals. An earlier draft of c0010's proposal spelt a c0020 id; it was reworded before implementation. Task 3.2 stays as a re-check for drafts edited later.
- **Upstream changes.** None are needed. `core.evidence` (c0004) provides `Level`, `strength`, `min_level` and `Evidence`. The `package-layering` table already lists `verify → model, geometry, backends`, and `tests/unit/test_import_graph.py` has the `verify` row.
- **Constraints.**
  - Stdlib only.
  - Unit tests only, because no format behaviour changes. The `kicad-9` and `kicad-10` jobs run unchanged.
  - 3 working days.

## Goals / Non-Goals

**Goals:**
- Make the register machine-checked before c0009, c0017, c0018 and c0010 add their 20 new rows.
- One label grammar for the register, the format pages and the v0.2a matrix.
- A written rule, a function and a test saying that an author report never promotes an operation.
- Record the author's earlier write validation as author-report rows.
- Write down the change-id and ADR numbering rules that v0.1 uses.

**Non-Goals:**
- Everything listed under Non-goals in the proposal.
- Replacing `tests/unit/test_format_facts.py::_label` with `parse_level` (v0.2a matrix change; Open Questions).
- The licence cells of S-0013, S-0015 and S-0017 (boolean-backends change, v0.3).
- The licence check of the public third-party second-backend library that the project plan's 0014 work also lists. It is not part of `H-K-00` to `H-K-03`, so c0007 did not settle it, and the brief keeps only the S-0002 check. Owner: the second-backend change (v0.3+), which registers the library as a source by its URL and records its LICENSE file under the same "stated or not stated" rule as Decision 13.
- The placeholder tests of `H-K-LIB-RELPATH`, `-FALLBACK`, `-NESTED` and `-CONFIGHOME` (c0021).
- A guard for source ids (`S-NNNN`) (Open Questions).

## Decisions

1. **The scope is only what c0007 did not settle.** The environment checks `H-K-00` to `H-K-03` are not repeated, and the matrix generator stays in v0.2a.
   - Rejected: re-running the environment checks. c0007 verified all four on both majors, in CI as well (run https://github.com/lgili/Fenolite/actions/runs/36837554710).
   - Rejected: generating `docs/evidence/matrix.md` now. No module carries `# evidence:` markers yet, and nothing reads a matrix before v0.2a.

2. **A `verify` package in `src`, stdlib only, importing only `core`.**
   - `verify/hypotheses.py` reads the register and scans text.
   - `verify/evidence.py` holds the release rule.
   - The v0.2a matrix generator and `capabilities` will reuse both.
   - Importing `fenolite.verify` must not load `fenolite.model`, `fenolite.geometry` or `fenolite.backends`, although the layering table allows them. Reading Markdown needs none of them.
   - `tests/unit/test_import_graph.py` allows `verify` to import `model`, `geometry` and `backends*`, and its stdlib-only set does not include `verify`. So it cannot enforce the narrower rule, and the fresh-interpreter check sees only imports made at import time. `tests/unit/verify/test_levels.py` therefore adds an AST check: every import statement in `src/fenolite/verify/`, at any depth, names a standard-library module, `fenolite.core` or `fenolite.verify` itself.
   - Rejected: keeping the parsers inside the guard test. The matrix generator in `src` would need a second copy.
   - Rejected: putting them in `core`. Every package imports `core`, which holds primitives; reading repository registers does not belong there.

3. **Label grammar.** `parse_level(text) -> Level` accepts every `Level` value written exactly, plus these qualified forms:

   | written form | `Level` |
   |---|---|
   | `ALTIUM-VERIFIED(kit)`, `ALTIUM-VERIFIED(kit; <fields>)`, either one optionally followed by ` (<scope>)` | `ALTIUM_VERIFIED_KIT` |
   | `KICAD-VERIFIED`, `KICAD-VERIFIED (<scope>)` | `KICAD_VERIFIED` |
   | `ORACLE-VERIFIED`, `ORACLE-VERIFIED(<tool>)`, either one followed by ` (<scope>)` | `ORACLE_VERIFIED` |
   | `CORPUS-VERIFIED`, `CORPUS-VERIFIED (<scope>)` | `CORPUS_VERIFIED` |
   | `ALTIUM-VERIFIED(author-report)`, `ALTIUM-VERIFIED(author-report; <fields>)`, either one optionally followed by ` (<scope>)` | `ALTIUM_VERIFIED_AUTHOR_REPORT` |
   | `INFERRED`, `UNKNOWN`, `UNVERIFIED`, each optionally followed by ` (<scope>)` | the same level |

   - **Attached qualifier.** A parenthesis directly after the name, with no space, is allowed only after `ORACLE-VERIFIED`, where it names the tool, and after `ALTIUM-VERIFIED`, where it is required. Its content is non-empty and holds no parenthesis. For `ALTIUM-VERIFIED`, the first `;`-separated field, stripped, must be `kit` or `author-report`.
   - **Scope.** One space, then a parenthesis with non-empty content and no nested parenthesis, at the end of the text. It is allowed after every label, as the table shows, so `ALTIUM-VERIFIED(kit) (24.x)` parses. The spec states the same rule ("Evidence label grammar").
   - **Rejected input.** Anything else raises `ValueError` quoting the text: a bare `ALTIUM-VERIFIED`, an unknown sub-label, lower case, an attached qualifier after `INFERRED`, and an empty string.
   - The grammar covers every level cell of the register today and the sub-labels of the release policy: `ALTIUM-VERIFIED(kit; <sha256>)` and `ALTIUM-VERIFIED(author-report; AD 24.x; <date>; no artefact)`.
   - Rejected: a new `Level` member per sub-label. It would change the total order that `core-primitives` fixes.
   - Rejected: matching by prefix. `KICAD-VERIFIEDX` would pass.

4. **Strict register reading.** `load_register(path)` works as follows:
   - It finds the one table whose header row is exactly `REGISTER_HEADER`. No such table, or two of them, raises `ValueError`.
   - It splits rows on unescaped pipes (`\|` is a literal pipe) and strips the cells.
   - Every row must have exactly 8 cells, an id that fully matches `ID_PATTERN`, and a level that `parse_level` accepts. Otherwise it raises `ValueError` with `<path>:<line>` and the reason.
   - It keeps `level_text` as written and `date` as text, and returns the rows in file order.

   `HypothesisRow.refuted` is true when the result starts with `refuted` (case-sensitive). `HypothesisRow.successor` is the first id after the words `superseded by`, or `None`.
   - Rejected: skipping malformed rows. A broken row would silently drop out of the guard.

5. **Refuted rows keep their id.**
   - The result starts with `refuted; superseded by <id>`. The observation, run links and date follow.
   - The level is the level of the run that refuted the claim, because the label grades what the result column says.
   - The successor must be registered and must differ from the row's own id.
   - A result that starts with anything else is not a refutation and needs no successor. This includes `partly refuted …` (`H-K-FMT-MIXED`), whose row stays open.

   The two rows change as follows:

   | row | level after | result starts with |
   |---|---|---|
   | `H-K-SEXPR-NUM-WRITE` | `KICAD-VERIFIED (10.0.x)` | `refuted; superseded by H-K-SEXPR-NUM-WRITE-2` |
   | `H-K-TOK-FUTURE` | `KICAD-VERIFIED (9.0.x, 10.0.x)` | `refuted; superseded by H-K-TOK-FUTURE-2` |

   - A refuted row never counts as release support, although its level may be release-verified: `is_release_evidence(row)` (Decision 11) is false for it.
   - Rejected: deleting refuted rows. Ids are never reused, and the history of the claim would be lost.
   - Rejected: keeping `INFERRED`. It reads as "unsettled", but the claim is settled as false.

6. **Cited-id scan.** `cited_ids(roots, *, base, exclude=())` works as follows:
   - It walks every regular file under the roots; a root that is a file is scanned itself. Below a root, it skips every file or folder whose name starts with `.`, every folder named `__pycache__`, the `exclude` paths, and files that are not valid UTF-8. The spec uses the same wording.
   - It matches `ID_PATTERN` = `\bH-[AGK]-[A-Z0-9]+(?:-[A-Z0-9]+)*`.
   - A match followed by `-`, `*` or `…` is a family reference. It is keyed `<match>-*`.
     - Because the pattern is greedy, a following `-` can never continue the id. The case covers `-*`, and also a prefix written with a trailing hyphen, as in the proof `grep -c '^| H-K-LIB-' docs/hypotheses.md` of c0008 task 1.1.
     - **Correction of the brief.** The brief lists only `-*`, `*` and `…`. With that list, every task proof that greps for a row prefix would cite a bare stem as if it were an id, and the guard would fail on it.
   - It returns `{id or family: sorted paths}`, with paths in POSIX form relative to `base`.

   The guard calls it with these settings:
   - roots `docs/`, `openspec/specs/`, `openspec/changes/`, `src/`, `tests/` and `tools/`, plus every `*.md` file at the repository root (`CHANGELOG.md`, `README.md`, `AGENTS.md`, `CONTRIBUTING.md`, `LEGAL.md`, `LEGAL-ANNEX.md`, `CLAUDE.md`);
   - excluded `openspec/changes/archive/`, and `tests/corpus/cache/`, which is where the residue scope expects a corpus cache inside the tree.

   Archived changes are history and may cite ideas that were later dropped. A plain id passes when it is registered; Decisions 7 to 9 add the other cases.
   - **Correction of the brief.** The brief's root list leaves out the top-level files, although its own rule is "every id cited in live text". `CHANGELOG.md` is live text: it cites 9 ids today, all registered, and every change of this batch adds a line to it (task 6.3 adds `H-K-LIB-DRC` and `H-G-SHAPELY-GC`). The other top-level files cite none today. Ids are never deleted (Decision 5), so release notes stay valid.
   - Rejected: scanning the archive. It would force rows for dropped ideas.
   - Rejected: a hand-kept list of cited ids, which would drift.
   - Rejected: leaving the top-level files out. A misspelt id in `CHANGELOG.md` would pass.

7. **Family references and reserved families.** A family reference `<stem>-*` passes in any of these cases:
   - a registered id starts with `<stem>-`;
   - `<stem>` is itself registered, which covers a range written with `…`;
   - the family is reserved in the register header.

   Reserved families are a second table in `docs/hypotheses.md`, with the header `| family | backend | rows for | owner |` (`FAMILIES_HEADER`). `load_families(path)` returns the families as written, for example `H-K-KRT-*`. Family cells are written in backticks, so that Markdown does not read `*` as emphasis. A family cell, stripped and with one pair of enclosing backticks removed, must fully match `ID_PATTERN` followed by `-*`; otherwise it raises `ValueError` with `<path>:<line>`. A file without the table gives `()`, so the guard's temporary registers need no families table unless a case tests one; two such tables raise `ValueError` naming the path, as `load_register` does. Because the cells start with a backtick, the rows never match `^| H-`, so the row counts of the register table are unchanged. The table starts with four rows:

   | family | backend | rows for | owner |
   |---|---|---|---|
   | `H-A-WRITE-*` | altium | author-report write validation, one row per file type | c0014 |
   | `H-A-PH-*` | altium | placeholder and omission choices of the author's earlier writer | c0014 |
   | `H-K-KRT-*` | kicad | routing tools run on KiCad files | routing change (c0016) |
   | `H-G-DSN-*` | specctra | Specctra DSN/SES and the Freerouting plugin | Specctra change (c0023) |

   - **Correction of the brief.** The brief puts the routing and Specctra naming note into the register header, which the scan reads. No row extends those stems until c0016 and c0023, so without reserved families the guard would fail on its own header.
   - Rejected: writing the note without ids, which makes it unreadable.
   - Rejected: allowlisting `docs/hypotheses.md`, which would hide typos in the register itself.

8. **Ids proposed by active changes.** An active change declares the ids it will register in the table "Hypotheses registered by this change" of its `design.md`.
   - `proposed_ids(changes_dir)` returns the ids in the first column of every table in that section, up to the next `## ` heading, across all active changes (`archive/` excluded). A section may hold more than one table: c0017 has a second table for existing rows it settles.
   - A first cell contributes the id it starts with, after stripping and removing one pair of enclosing backticks. A cell such as `H-K-LIB-DRC (c0014)` contributes `H-K-LIB-DRC`. A first cell that does not start with an id is ignored.
   - Inside `openspec/changes/<active>/`, an id or family passes when it is registered or proposed.
   - Everywhere else it must be registered. This works because each change registers its rows in its first task, before any code, test or doc cites them.
   - **Correction of the brief.** The batch drafts of c0009, c0017, c0018 and c0010 cite 20 new ids that only their own first tasks register (count of their hypothesis tables on 2026-10-01). They will be active when c0014 is implemented, so a guard that accepts only registered ids would fail on them.
   - Rejected: registering ids when a change is proposed. The registers are edited by the change's first task (`AGENTS.md` workflow).
   - Rejected: dropping active changes from the scan. Typos in proposals would then pass unnoticed until implementation.

9. **Synthetic test literals.** `tests/unit/test_hypotheses_register.py` holds `SYNTHETIC: dict[str, frozenset[str]]`. It maps a repository path to the unregistered ids allowed in that file, and it names two paths:
   - `tests/unit/core/test_evidence.py`, with the two ids of `test_combine`;
   - the guard file itself, with the same two ids, because it must spell them to declare them. The residue scope excludes its own pattern file for the same reason.

   Anywhere else the literals fail.
   - The guard's temporary-tree cases use ids that the real register holds but the temporary register lacks, so the guard's source cites nothing else that is unregistered.
   - The spec scenarios work the same way, because the archived spec is scanned too. This is why they do not use the brief's example literals.
   - Rejected: one global allowlist, which would let the literals spread.
   - Rejected: replacing the literals in `test_combine` with registered ids. That test checks merging, and real ids would read as evidence.

10. **The two ids that only archived changes cite are registered as pending.** Both rows are `INFERRED`, with result `pending` (table "Hypotheses registered by this change").
    - `H-K-LIB-DRC` (c0008 Decision 18) is settled by c0017's flip oracle, placeholder `tests/kicad/board/test_flip_oracle.py::test_lib_drc`.
    - `H-G-SHAPELY-GC` (c0005 hand-over) is owned by the boolean-backends change in v0.3, placeholder `tests/unit/geometry/test_boolean_shapely.py::test_line_parts_dropped`.

11. **Author reports never promote an operation.** The rule is already public: the docstring of `src/fenolite/core/evidence.py` says an author report "never promotes an operation" to verified in the release matrix. This change gives it a function and tests.
    - `release_verified(level)` is true only for the four levels in `RELEASE_VERIFIED`: `ALTIUM_VERIFIED_KIT`, `KICAD_VERIFIED`, `ORACLE_VERIFIED` and `CORPUS_VERIFIED`.
    - This is the release rule the v0.2a matrix will apply.
    - `is_release_evidence(row)` is true only when the row is not refuted and `release_verified(row.level)` is true. A refuted row carries the level of the run that refuted it (Decision 5), so its level alone would read as support for a claim known to be false. Any reader that counts rows as release support, such as the v0.2a matrix, uses this function.
    - `Evidence.combine` already returns the lowest level. A result that depends on an author report is therefore labelled `ALTIUM-VERIFIED(author-report)` and is not release-verified, even when its other parts are `KICAD-VERIFIED`. A spec scenario pins this.
    - Rejected: defining the rule as `strength(level) > strength(ALTIUM_VERIFIED_AUTHOR_REPORT)`. It is equivalent today, but a level inserted later would silently change the release set. With an explicit set, a test fails instead.
    - Rejected: special-casing author reports in `combine`, which already returns the lowest part.

12. **Author-report rows.** The register gets one `H-A-WRITE-*` row per file type the author validated, and one `H-A-PH-*` row per placeholder or omission choice. The columns are filled as follows:
    - backend `altium`;
    - statement in generic format terms. A write row gives the file type, whether the file was new or an edited existing file, and the edit operations exercised. A placeholder row gives the choice and, when the value is the writer's own choice, its concrete value: the checksum or stamp algorithm, fields written as zero, caches or streams omitted, or the layout version targeted;
    - level `ALTIUM-VERIFIED(author-report; AD <major>.<minor or x>; <YYYY-MM-DD or YYYY-MM>; no artefact)`;
    - test column `kit request (v0.4): …`, plus a criterion;
    - result `reported by the author; no artefact committed`;
    - the date the row is registered.

    Further rules:
    - **Expected ids.** They come from the author's notes; the final list follows the answer in Open Questions. `H-A-WRITE-SCHLIB`, `H-A-WRITE-PCBLIB`, `H-A-WRITE-SCHDOC`, `H-A-WRITE-PCBDOC`; `H-A-PH-CHECKSUM`, `H-A-PH-ZERO-FIELDS`, `H-A-PH-NO-CACHE`, `H-A-PH-LAYOUT`.
    - **Entitlement and provenance** (`LEGAL.md`, block A with P3 and P4, and block B; `AGENTS.md`, clean-room rule).
      - A row is registered only for a validation on files the author created or may use for this purpose, opened with a licence the author may use for it. A file type validated only on other files gets no row.
      - Each `H-A-PH-*` value is a choice made by the author's own writer. A constant measured on, or copied from, non-public files is never recorded. When the provenance of a value is not clear, the row names the kind of choice and leaves the value out.
    - **Content.** No file, screenshot, path, design name or identifier from any organisation is committed, and the residue scan runs on the edit as `make residue`. The Makefile exports the maintainer's private token and blob lists (`private/residue-tokens.txt`, `private/residue-blobs.sha256`) when they exist. A bare `uv run python tools/residue/scan.py` without them prints `private gate: skipped` and checks no organisation token, so it does not count as the content check: the summary line must end with `private gate: on`.
    - **Not format facts.** The rows are hypotheses for the kit to reproduce. No `docs/formats/` page is written, and a later second-backend change documents formats from public sources only.
    - **Fallback** (brief Decision 5). If the author's values are not available when group 5 starts, the expected ids are registered with level `INFERRED` and a result starting `pending (author report)`. The label is upgraded in a one-line follow-up commit. Nothing waits on it, and the guard does not depend on the values.
    - **Guard check.** A row of either family must have one of two levels. The spec ("Author-report rows") states the same check.
      - The full author-report form: the level cell is `ALTIUM-VERIFIED(` + four `;`-separated fields + `)`, with no scope. Stripped, field 1 is `author-report`, field 2 fully matches `AD \d+\.(\d+|x)`, field 3 fully matches `\d{4}-\d{2}(-\d{2})?`, and field 4 equals `no artefact`.
      - Or `INFERRED`, with a result starting `pending (author report)`.
    - Rejected: `ALTIUM-VERIFIED(kit)` for these rows, because no kit result exists.
    - Rejected: one combined row. A later kit run settles file types one by one.

13. **S-0002 licence cell.** The registering task opens the page. It records the licence the page states, or `not stated on the page (checked <date>)`, as for S-0001 and S-0040. Only that cell changes.

14. **Change ids.** Plan items keep their numbers, so plan text and commitments stay readable. Split-offs take c0017 and later numbers in implementation order. `openspec/README.md` gains this table, and a row's slug may still change until its change is proposed:

    | id | slug | roadmap item | parent |
    |---|---|---|---|
    | c0009 | `kicad-board-backend` | 0009 (part 1) | — |
    | c0010 | `kicad-project-file` | 0010 | — |
    | c0011 | `dsl-thin-build` | 0011 (part 1) | — |
    | c0012 | `sheet-templates-kicad` | 0012 | — |
    | c0013 | `kicad-oracle-and-check` | 0013 (part 1) | — |
    | c0014 | `verification-evidence` | 0014 | — |
    | c0015 | `zone-fill` | 0015 | — |
    | c0016 | `routing-plugins` | 0016 | — |
    | c0017 | `kicad-board-writer` | split-off | 0009 |
    | c0018 | `kicad-rules-footprints` | split-off | 0009 |
    | c0019 | `layout-preserve` | split-off | 0011 |
    | c0020 | `check-netlist-drc` | split-off | 0013 |
    | c0021 | `kicad-libs-cache` | follow-up | c0008 |
    | c0022 | `placement-grid` | split-off | 0016 |
    | c0023 | `specctra-freerouting` | split-off | 0016 |
    | c0024 | `manufacturing-exports` | unowned deliverables | — |
    | c0025 | `release-v0-1` | unowned deliverables | — |

    The README also states:
    - c0001–c0008 are archived under `changes/archive/`;
    - a new split-off takes the next free number;
    - ids follow the `cNNNN-<slug>` form, a project convention (the `openspec` CLI accepts any kebab-case name);
    - older planning text that says `tokens.yaml` means `src/fenolite/backends/kicad/data/tokens.toml`.
    - Rejected: renumbering every later plan item, because c0013 would stop meaning "check".
    - Rejected: lettered ids such as `c0009a`, which break the `cNNNN-<slug>` convention.

15. **ADR numbering.** `docs/adr/README.md` line 3 says ADRs are "numbered in order of creation, never renumbered". ADR-0002 is written after 0003 and 0004, so that line contradicts the note. The task rewords it to "numbered in order of allocation, never renumbered", and adds a note:
    - ADR-0002 was allocated by c0001 (Decision 8) before 0003 and 0004 existed, so writing it in c0009 keeps allocation order. It is the only number written out of order.
    - The next free number is one above the highest number written or allocated. Every later ADR takes it when its change is proposed. Numbers are never reserved.
    - ADR numbers are not tied to planning decision numbers.
    - Informative: the sheet-template ADR (c0012) is expected to become 0005 and the routing ADR (c0016) 0006, because no change scheduled before them creates an ADR.
    - Rejected: reserving numbers per planned ADR, which leaves gaps when a plan changes.
    - Rejected: "the lowest unused number". While 0002 was unwritten, that rule would have handed 0002 to another change.

16. **Id prefixes.** The register header states these rules, placed before the reserved-families table:
    - the prefixes stay `H-A-` (second backend), `H-G-` (general) and `H-K-` (KiCad);
    - rows about a tool that acts on KiCad files use `H-K-`, and routing rows are `H-K-KRT-*`;
    - Specctra rows are `H-G-DSN-*`, with backend `specctra`;
    - a refuted row follows Decision 5;
    - an author-report row never raises an operation to verified (Decision 11);
    - `tests/unit/test_hypotheses_register.py` checks the register.
    - Rejected: new prefixes for routing or Specctra. `ID_PATTERN` and every reader would change.

17. **Tests.**
    - The guard lives in `tests/unit/`, so it runs in `make check` and in the `unit` job on every pull request.
    - The parsers have hermetic tests in `tests/unit/verify/` on inline strings and `tmp_path` trees.
    - No `kicad-cli` test is added.

## Files and public API

| file | public API |
|---|---|
| `src/fenolite/verify/__init__.py` | re-exports `HypothesisRow`, `ID_PATTERN`, `REGISTER_HEADER`, `FAMILIES_HEADER`, `parse_level`, `load_register`, `load_families`, `cited_ids`, `proposed_ids`, `RELEASE_VERIFIED`, `release_verified`, `is_release_evidence` |
| `src/fenolite/verify/hypotheses.py` | `ID_PATTERN: re.Pattern[str]`; `REGISTER_HEADER: tuple[str, ...] = ("id", "backend", "statement", "level", "test or kit request", "criterion", "result", "date")`; `FAMILIES_HEADER: tuple[str, ...] = ("family", "backend", "rows for", "owner")`; `@dataclass(frozen=True, slots=True) class HypothesisRow(id: str, backend: str, statement: str, level: Level, level_text: str, test: str, criterion: str, result: str, date: str)` with properties `refuted: bool` and `successor: str \| None`; `parse_level(text: str) -> Level`; `load_register(path: str \| os.PathLike[str]) -> tuple[HypothesisRow, ...]`; `load_families(path: str \| os.PathLike[str]) -> tuple[str, ...]`; `cited_ids(roots: Iterable[str \| os.PathLike[str]], *, base: str \| os.PathLike[str], exclude: Iterable[str \| os.PathLike[str]] = ()) -> dict[str, tuple[str, ...]]`; `proposed_ids(changes_dir: str \| os.PathLike[str]) -> frozenset[str]` |
| `src/fenolite/verify/evidence.py` | `RELEASE_VERIFIED: frozenset[Level]`; `release_verified(level: Level) -> bool`; `is_release_evidence(row: HypothesisRow) -> bool` |
| `tests/unit/verify/test_levels.py` | `parse_level` forms and rejections; `fenolite.verify` imports in a fresh interpreter (`sys.executable`) without `model`, `geometry` or `backends`; AST check that every import in `src/fenolite/verify/` is stdlib, `fenolite.core` or `fenolite.verify` |
| `tests/unit/verify/test_register.py` | `load_register`, `load_families`, `HypothesisRow.refuted`/`successor` on inline registers and on `docs/hypotheses.md` |
| `tests/unit/verify/test_cited_ids.py` | `cited_ids` and `proposed_ids` on `tmp_path` trees |
| `tests/unit/verify/test_release.py` | `release_verified` over every `Level`; the combine scenario; `is_release_evidence` on refuted rows and their successors |
| `tests/unit/test_hypotheses_register.py` | the guard: `ROOTS`, `EXCLUDE`, `SYNTHETIC`, `register_problems(rows: Sequence[HypothesisRow]) -> list[str]`, `citation_problems(root: Path, *, synthetic: Mapping[str, frozenset[str]] = SYNTHETIC) -> list[str]`; live tests `test_register_loads`, `test_register_integrity`, `test_cited_ids_registered`; temporary-tree cases |
| `docs/hypotheses.md` | header (Decision 16), reserved-families table, relabelled rows, `H-K-LIB-DRC`, `H-G-SHAPELY-GC`, `H-A-WRITE-*` and `H-A-PH-*` rows, paragraph "Change c0014 (verification evidence) adds …" |
| `docs/evidence/sources.md` | S-0002 licence cell |
| `docs/evidence/README.md` | one line: the guard checks the register, and `fenolite.verify` reads it |
| `openspec/README.md` | section "Change ids" (Decision 14) |
| `docs/adr/README.md` | numbering note (Decision 15) |

Layering: `fenolite.verify` imports only `fenolite.core.evidence` and the standard library. That is within the `verify` row of `package-layering`.

## Sources registered by this change

None. This change registers no new source and adds no format fact. It settles the licence cell of S-0002 (registered by c0004). Its new rows cite S-0013 (shapely documentation, c0005), S-0020 (observed `kicad-cli` 10.0.6 behaviour, c0006), S-0022 (10.0 command-line manual, c0006; its `pcb drc` use is added to the "used for" cell by c0017, which runs the check) and S-0024 (KiCad demo tree, for the rule-severity key names). If a URL is needed later, the existing id is cited.

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-K-LIB-DRC | `kicad-cli pcb drc --format json --severity-all` checks placed footprints against the library that a project-local `fp-lib-table` names. It reports `lib_footprint_mismatch` for a placement that differs from its library footprint, none for an exact placement, and `lib_footprint_issues` when the table is absent. Command options: S-0022, as c0017 records them. Key names: 10.0.6 demo projects (S-0024), as in c0017. c0008 observed `lib_footprint_issues` on a copy of a demo board (S-0020); tying it to a missing `fp-lib-table` is part of this hypothesis, not that observation | placeholder `tests/kicad/board/test_flip_oracle.py::test_lib_drc` (board writer change, c0017) | on 10.0.6 with an empty `KICAD_CONFIG_HOME`: 0 `lib_footprint_mismatch` for an exact placement, exactly 1 for one altered placement, and `lib_footprint_issues` without the table; the 9.0.9 outcome is recorded |
| H-G-SHAPELY-GC | With `grid_size`, shapely set operations on polygons can return line parts. On shapely 2.1.2 with GEOS 3.13.1, c0005 observed `LINESTRING (10 0, 10 10)` as the intersection of the touching squares `0..10` and `10..20`. A shapely boolean backend must drop such parts, so its results hold polygons only (S-0013) | placeholder `tests/unit/geometry/test_boolean_shapely.py::test_line_parts_dropped` (boolean-backends change, v0.3; `geo` extra) | the touching squares intersect to `()`, and c0005's triangle-and-band case returns polygons only, with the shapely version the `geo` extra pins |
| H-A-WRITE-SCHLIB | A schematic library file written by the author's earlier writer opens and compiles in AD 24.x without a repair prompt (author report: new or edited file and operations as reported) | kit request (v0.4): open, compile and re-save the file with the acceptance kit | opens and compiles with no error or repair prompt |
| H-A-WRITE-PCBLIB | The same for a PCB library file | kit request (v0.4), as above | as above |
| H-A-WRITE-SCHDOC | The same for a schematic document | kit request (v0.4), as above | as above |
| H-A-WRITE-PCBDOC | The same for a PCB document | kit request (v0.4), as above | as above |
| H-A-PH-CHECKSUM | The checksum or stamp algorithm the writer used (value as reported, when it is the writer's own choice) is accepted when the file is opened | kit request (v0.4): open a file written with that algorithm | opens without a repair prompt |
| H-A-PH-ZERO-FIELDS | The fields the writer wrote as zero (list as reported, when it is the writer's own choice) are accepted | kit request (v0.4): open and re-save such a file | opens; each field is recomputed or kept, as recorded |
| H-A-PH-NO-CACHE | The caches or streams the writer omitted (list as reported, when it is the writer's own choice) are rebuilt by the tool or not needed | kit request (v0.4): open and compile such a file | opens and compiles; the tool rebuilds or ignores each omitted part, as recorded |
| H-A-PH-LAYOUT | The storage layout version the writer targeted (value as reported, when it is the writer's own choice) is accepted by AD 24.x | kit request (v0.4): open such a file | opens without an upgrade or repair prompt |

- The `H-A-*` ids above are the expected set. Group 5 registers one row per file type and per choice the author actually reports, and amends this table in the same pull request if the set differs.
- Their level is the author-report form of Decision 12, or `INFERRED` with `pending (author report)` under the fallback.
- The two relabelled rows (`H-K-SEXPR-NUM-WRITE`, `H-K-TOK-FUTURE`) are not new; Decision 5 gives their new level and result.
- No behaviour of this change depends on any of these rows.

## Evidence level per behaviour (before merge)

| behaviour | level required | proof |
|---|---|---|
| Label grammar, register reading, families, cited-id scan, proposed ids | mechanical (unit tests); no format claim | `tests/unit/verify/` |
| Register integrity and the cited-id guard over the live tree | mechanical (unit tests) | `tests/unit/test_hypotheses_register.py` |
| `release_verified`, `is_release_evidence` and the combine rule | mechanical (unit tests) | `tests/unit/verify/test_release.py` |
| Relabelled refuted rows | the level of the refuting run, already recorded: `KICAD-VERIFIED (10.0.x)` (`H-K-SEXPR-NUM-WRITE`), `KICAD-VERIFIED (9.0.x, 10.0.x)` (`H-K-TOK-FUTURE`) | rows and run links already in `docs/hypotheses.md` |
| `H-K-LIB-DRC`, `H-G-SHAPELY-GC` | INFERRED, pending | settled by c0017 and the v0.3 boolean-backends change |
| `H-A-WRITE-*`, `H-A-PH-*` | `ALTIUM-VERIFIED(author-report; …)`, never release-verified; or INFERRED, `pending (author report)` | the author's account; the guard checks the form |
| S-0002 licence | as stated on the page, with the date | the page, opened by task 1.1 |
| Change-id table, ADR note, register header | documentation (no label) | review; `tests/unit/test_adrs.py` |

`fenolite.verify` carries no `EVIDENCE` constant, because it reads repository text and makes no format claim. The `kicad-9` and `kicad-10` jobs run unchanged and must stay green (`gh pr checks`).

## Budget (3 working days; the plan had no line for 0014)

| work | days |
|---|---|
| parsers (`parse_level`, `load_register`, `load_families`, `cited_ids`, `proposed_ids`) and the guard test | 1.0 |
| register hygiene: refuted rows, two pending rows, header and families table | 0.25 |
| author-report rows | 0.5 |
| S-0002 and the two README tables | 0.5 |
| `release_verified`, spec scenario tests and closing | 0.75 |
| **total** | **3.0** |

The batch plan gives 0014 its own 3-day line. The reserved families and proposed ids of Decisions 7 and 8 are small readers over the same Markdown tables, and they fit in the 1.0-day line. If the work overruns, the author-report rows take the fallback of Decision 12 first. The parsers, the guard and the hygiene rows are not optional, because c0009 depends on them.

## Risks / Trade-offs

- [The author is not available for the day-3 values] → the fallback of Decision 12. The guard does not depend on the values.
- [The scan flags legitimate mentions] → family stems, reserved families, proposed ids and the per-file allowlist cover them. Archived changes are excluded as history.
- [Another active change cites an id that no active change proposes] → the guard names the file and the id. Task 3.2 fixes the citing proposal with a wording change, or adds the id to its hypotheses table, in the same pull request. The dry run over the current drafts finds no such case (Context, "Batch load").
- [Refuted rows are read as verification, because they carry the level of the refuting run] → `is_release_evidence` is false for them (Decisions 5 and 11), and a spec scenario checks every refuted row of the live register.
- [Author-report rows are read as verification] → `release_verified` is false for them, and a spec scenario covers the combine case. There is no matrix in v0.1.
- [The guard blocks a pull request that cites an id before registering it] → this is intended. The message names the file and the id, and says where to register it.
- [The scan slows the unit job] → it uses one compiled pattern over a few megabytes of text and skips dot files, dot folders and `__pycache__`. Task 3.1 records the time.

## Migration Plan

- Additive: a new package, new tests and documentation edits. To roll back, remove `src/fenolite/verify/`, `tests/unit/verify/` and `tests/unit/test_hypotheses_register.py`. The register corrections stay, because they are independent of the code.

## Open Questions

- **Author-report scope (question for the user).** Please confirm the scope of your earlier second-backend write validation. My notes say that schematic library, PCB library, schematic document and PCB document files were opened and compiled in AD 24. For each file type I need:
  - the exact 24.x version;
  - the approximate date;
  - whether the file was new or an edited existing file, and, if edited, whether you created that file (this answer decides whether a row is registered; it is not recorded);
  - which edit operations, if any, you exercised;
  - whether you created the files or may use them for this purpose, and whether the licence of the tool you opened them with may be used for it (`LEGAL.md`, P3 and P4). A file type validated only on other files gets no row.

  I also need the concrete placeholder or omission choices: the checksum or stamp algorithm, any fields written as zero, any caches or streams omitted, and the layout version targeted. For each value, please confirm it is a choice your own writer made, not a constant measured on or copied from non-public files (`LEGAL.md`, block B); otherwise only the kind of choice is recorded. Only generic format terms will be recorded.

  The default is the four file types and four choices of the table above. Without an answer when group 5 starts, the rows are registered under the fallback of Decision 12.
- **Re-baselined budget (question for the user, whole batch).** Do you accept about 31 working days for this batch and about 102 to v0.1, against about 36 left in the plan's lines? And the cut order: c0023 to v0.2a first, then c0021, then c0020's measurement-only items? The default is yes. This change's 3 days are part of the batch total.
- **Corrections to the brief.** Please confirm these five: a trailing `-` marks a family reference (Decision 6), the top-level Markdown files are scanned (Decision 6), the reserved families (Decision 7), the proposed-ids rule (Decision 8), and the guard listing itself in `SYNTHETIC` (Decision 9). The default is to adopt them. Without the four others, the guard would fail on grep proofs in tasks, on the register header, on the active batch proposals and on its own allowlist; without the top-level files, a misspelt id in `CHANGELOG.md` would pass.
- Should `tests/unit/test_format_facts.py` use `parse_level` instead of its own `_label`? The default is no, until the v0.2a matrix change touches both.
- Should a similar guard check that every `S-NNNN` cited in live text is registered? The default is no in this change. It is a candidate for v0.2a.
- The c0008 rows `H-K-LIB-RELPATH`, `-FALLBACK`, `-NESTED` and `-CONFIGHOME` still say "follow-up change" in their test column. The default is that c0021 renames them when it implements the probes.
