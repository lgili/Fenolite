## 1. Registers and hygiene (`docs/evidence/sources.md`, `docs/hypotheses.md`)

This change adds no source row, no `PROVENANCE.md` row, no `LEGAL-ANNEX.md` session row and no format page, because it touches neither `src/fenolite/backends/` nor `docs/formats/` and adds no format fact (design, "Sources registered by this change").

- [x] 1.1 Open https://dev-docs.kicad.org/en/import-formats/altium/index.html. Replace the licence cell of S-0002 in `docs/evidence/sources.md` with the licence the page states, or with `not stated on the page (checked <date>)` (design Decision 13). Change no other cell. Proof: `grep '^| S-0002 ' docs/evidence/sources.md | grep -c 'to verify'` prints `0`; `uv run pytest tests/unit/test_provenance.py`.
- [x] 1.2 Relabel the two refuted rows of `docs/hypotheses.md` (Decision 5):
  - `H-K-SEXPR-NUM-WRITE` takes level `KICAD-VERIFIED (10.0.x)`, and its result starts with `refuted; superseded by H-K-SEXPR-NUM-WRITE-2`;
  - `H-K-TOK-FUTURE` takes level `KICAD-VERIFIED (9.0.x, 10.0.x)`, and its result starts with `refuted; superseded by H-K-TOK-FUTURE-2`.

  Keep each observation, run link and date after the prefix. Proof: `grep -E '^\| H-K-(SEXPR-NUM-WRITE|TOK-FUTURE) ' docs/hypotheses.md` shows `refuted; superseded by` on both lines; `grep -cE '^\| H-K-(SEXPR-NUM-WRITE|TOK-FUTURE) \|.*\| refuted; superseded by ' docs/hypotheses.md` prints `2`.
- [x] 1.3 Make these edits to `docs/hypotheses.md`:
  - Register `H-K-LIB-DRC` and `H-G-SHAPELY-GC` from the design table "Hypotheses registered by this change", with backend `kicad` and `general`, level `INFERRED`, result `pending` and today's date.
  - Rewrite the header as Decision 16 states: the three prefixes, the routing and Specctra naming rule, the refuted-row rule, the author-report rule and the name of the guard test.
  - Add the reserved-families table of Decision 7, with the rows `H-A-WRITE-*`, `H-A-PH-*`, `H-K-KRT-*` and `H-G-DSN-*`, each family cell in backticks.
  - Add the paragraph "Change c0014 (verification evidence) adds …" under the register table, naming the two new rows, the two relabelled rows and the author-report families.

  Proof: `grep -cE '^\| (H-K-LIB-DRC|H-G-SHAPELY-GC) ' docs/hypotheses.md` prints `2`; ``grep -c '^| `H-' docs/hypotheses.md`` prints `4`; `uv run pytest tests/unit/test_provenance.py tests/unit/test_format_facts.py`.

## 2. The `fenolite.verify` package (`src/fenolite/verify/`)

Tests in `tests/unit/verify/` cite only registered hypothesis ids, because the guard of group 3 scans `tests/` (design Decision 9).

- [x] 2.1 Create `src/fenolite/verify/__init__.py` and `src/fenolite/verify/hypotheses.py`, each with the SPDX and copyright lines. Implement `ID_PATTERN` and `parse_level` with the grammar of Decision 3. Write `tests/unit/verify/test_levels.py`, including the fresh-interpreter check (run with `sys.executable`) that importing `fenolite.verify` loads no `fenolite.model`, `fenolite.geometry` or `fenolite.backends` module, and an AST check that every import statement in `src/fenolite/verify/`, at any depth, names a standard-library module (`sys.stdlib_module_names`), `fenolite.core` or `fenolite.verify`. Proof: `uv run pytest tests/unit/verify/test_levels.py tests/unit/test_import_graph.py`, covering every scenario of "Evidence label grammar" and "Verification package".
- [x] 2.2 Implement `REGISTER_HEADER`, `FAMILIES_HEADER`, `HypothesisRow` (with `refuted` and `successor`), `load_register` and `load_families` (Decisions 4 and 7). Errors carry `<path>:<line>`. Write `tests/unit/verify/test_register.py` on inline registers in `tmp_path` and on the live `docs/hypotheses.md`. Proof: `uv run pytest tests/unit/verify/test_register.py`, covering every scenario of "Hypothesis register table" and "Reserved id families", and the scenario "Settling tests are named" of "Ids cited only in archived changes are registered" (the rows exist since task 1.3).
- [x] 2.3 Implement `cited_ids` (Decision 6) and `proposed_ids` (Decision 8). `cited_ids` handles the exclusions, the UTF-8 skip, family references keyed `<stem>-*` (after `-`, `*` or `…`) and POSIX paths relative to `base`. `proposed_ids` reads the first column of every table in each active change's section "Hypotheses registered by this change", with enclosing backticks removed and qualified cells such as `H-K-LIB-DRC (c0014)` reduced to their id. Write `tests/unit/verify/test_cited_ids.py` on `tmp_path` trees. Proof: `uv run pytest tests/unit/verify/test_cited_ids.py`.
- [x] 2.4 Create `src/fenolite/verify/evidence.py` with `RELEASE_VERIFIED`, `release_verified` and `is_release_evidence` (Decisions 5 and 11), and add the re-exports to `fenolite.verify`. Write `tests/unit/verify/test_release.py`: every `Level`, the two combine scenarios, and `is_release_evidence` on the live register. Proof: `uv run pytest tests/unit/verify -q`, covering every scenario of "Release-verified levels", the first two scenarios of "Author reports never promote an operation", and the scenarios "Refuted row gives no release support", "Successor gives release support" and "No refuted row counts" of "Refuted rows keep their id"; `uv run pyright src` reports 0 errors.

## 3. Register guard (`tests/unit/test_hypotheses_register.py`)

- [x] 3.1 Write the guard with these parts:
  - `ROOTS`, `EXCLUDE` and `SYNTHETIC` (Decisions 6 and 9);
  - `register_problems(rows)`: duplicate ids, refuted rows without a registered successor or superseded by themselves, and the form of author-report family rows (Decisions 5 and 12);
  - `citation_problems(root, *, synthetic=SYNTHETIC)`: plain ids, family references, reserved families, proposed ids inside active changes, and the allowlist (Decisions 6–9);
  - the live tests `test_register_loads`, `test_register_integrity` and `test_cited_ids_registered`;
  - the temporary-tree cases of the spec. They use ids that the real register holds but the temporary register lacks, so the guard's source cites nothing unregistered outside `SYNTHETIC`.

  Record the time of the live scan in the pull request. Proof: `uv run pytest tests/unit/test_hypotheses_register.py -q --durations=5`, covering every scenario of "Register integrity", "Cited ids are registered", "Family references", "Ids proposed by active changes", "Synthetic test literals", the third scenario of "Author reports never promote an operation", and the `register_problems` scenarios of "Author-report rows" ("Bare author-report label is refused", "Malformed version and date fields are refused", "Well-formed author-report row is accepted", "Pending rows are accepted").
- [x] 3.2 Run the guard while the batch proposals that are present (c0009, c0017, c0018, c0010) sit under `openspec/changes/`. For each problem it reports in an active change, do one of two things:
  - add the id to that change's table "Hypotheses registered by this change";
  - or reword the citation, changing wording only and no scope. An id owned by a change outside the batch is reworded to name the owning change without spelling the id.

  The dry run of design Context, "Batch load" finds no problem in the current drafts, so this task is a re-check for drafts edited later; when it finds nothing, the pull request says so.

  List every edited file in the pull request description. Proof: `uv run pytest tests/unit/test_hypotheses_register.py::test_cited_ids_registered -q`; `openspec validate --changes --strict --no-interactive`.

## 4. Numbering and documentation

- [x] 4.1 Add the section "Change ids" to `openspec/README.md`:
  - the table of Decision 14, with the 17 rows c0009–c0025;
  - the sentence on c0001–c0008 (archived);
  - the next-free-number rule;
  - the `cNNNN-<slug>` form;
  - the note that `tokens.yaml` in older planning text means `src/fenolite/backends/kicad/data/tokens.toml`.

  Proof: `grep -cE '^\| c00(09|1[0-9]|2[0-5]) ' openspec/README.md` prints `17`; `grep -n 'tokens.yaml' openspec/README.md` prints a line that also names `tokens.toml`.
- [x] 4.2 In `docs/adr/README.md`, reword line 3 to "numbered in order of allocation, never renumbered" and add the numbering note of Decision 15. Add one line to `docs/evidence/README.md` saying that `tests/unit/test_hypotheses_register.py` checks the register and that `fenolite.verify` reads it. Proof: `uv run pytest tests/unit/test_adrs.py tests/unit/test_repo_layout.py`; `grep -n 'ADR-0002' docs/adr/README.md` prints the note; `grep -n 'next free number' docs/adr/README.md` prints the rule; `grep -c 'numbered in order of creation' docs/adr/README.md` prints `0`.

## 5. Author-report rows (author input)

- [x] 5.1 Ask the author the question in design "Open Questions" (file types, exact 24.x version, approximate date, new or edited file, operations exercised, and whether the files and the tool licence may be used for this purpose). Register one `H-A-WRITE-*` row per reported file type that was validated on files the author created or may use for this purpose, with a licence the author may use for it (Decision 12, "Entitlement and provenance"); a file type validated only on other files gets no row. Each row has the columns and level of Decision 12, in generic format terms. Commit no file, path, screenshot or identifier from any organisation. If the set of file types differs from the design table, amend that table in the same pull request. If the author's values are not available, register the expected ids under the fallback of Decision 12 (`INFERRED`, `pending (author report)`). Proof: `grep -c '^| H-A-WRITE-' docs/hypotheses.md` prints the number of registered file types (`4` by default); `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/verify -q`; `make residue` exits 0 and its summary line ends with `private gate: on` (a run with `private gate: skipped` does not count).
- [x] 5.2 Register one `H-A-PH-*` row per reported placeholder or omission choice: checksum or stamp algorithm, fields written as zero, caches or streams omitted, layout version targeted. Use the same rules and fallback as 5.1. Give a concrete value, in generic format terms, only when the author confirms it is a choice of the author's own writer and not a constant measured on or copied from non-public files (`LEGAL.md`, block B); otherwise name the kind of choice and leave the value out. Proof: `grep -c '^| H-A-PH-' docs/hypotheses.md` prints the number of registered choices (`4` by default); `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/verify -q`, which checks the live rows against "Author-report rows" (its `register_problems` scenarios are written by task 3.1); the scenario "Rows exist for both families" holds; `make residue` exits 0 and its summary line ends with `private gate: on` (a run with `private gate: skipped` does not count).

## 6. Closing

- [x] 6.1 Run the residue and full test suites and `make check`. No `LEGAL-ANNEX.md` row is needed, because the change touches neither `backends/` nor `docs/formats/`; `tests/unit/test_provenance.py` confirms this. Proof: `make check` exits 0; `uv run pytest tests/residue` exits 0; `make residue` exits 0 and its summary line ends with `private gate: on`; `uv run python tools/gen_schemas.py --check` exits 0 (model unchanged); `uv run pytest tests/unit/test_provenance.py tests/unit/test_adrs.py tests/unit/test_import_graph.py` passes; `openspec validate c0014-verification-evidence --strict --no-interactive` passes.
- [x] 6.2 Update the evidence labels from the results:
  - the `H-A-WRITE-*` and `H-A-PH-*` rows carry `ALTIUM-VERIFIED(author-report; AD 24.<minor>; <date>; no artefact)` as reported. Under the fallback they stay `INFERRED`, `pending (author report)`, and a one-line follow-up commit upgrades them when the author answers;
  - `H-K-LIB-DRC` and `H-G-SHAPELY-GC` stay `INFERRED`, `pending`, with their placeholder tests;
  - `H-K-SEXPR-NUM-WRITE` and `H-K-TOK-FUTURE` keep the labels of task 1.2;
  - no label in `docs/formats/` changes, because this change adds no format fact.

  Proof: `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/verify tests/unit/test_format_facts.py -q`; the updated rows appear in `docs/hypotheses.md`; `gh pr checks` shows `unit`, `kicad-9` and `kicad-10` passing, with the KiCad jobs unchanged.
- [x] 6.3 Add to `CHANGELOG.md` under Unreleased: "Verification evidence: `fenolite.verify` (label grammar with qualified labels, hypothesis-register reader, cited-id scan, `release_verified`) and a guard test that keeps `docs/hypotheses.md` consistent with every hypothesis id cited in live text; refuted rows relabelled, `H-K-LIB-DRC` and `H-G-SHAPELY-GC` registered as pending, author-report rows for the earlier second-backend write validation (never release-verified), the S-0002 licence settled, and the change-id and ADR numbering rules written down". Proof: `git diff CHANGELOG.md`.
