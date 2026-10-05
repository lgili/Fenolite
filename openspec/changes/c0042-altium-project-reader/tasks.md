## 1. Registers, pages and corpus rows

- [x] 1.1 Register the sources S-0293 to S-0300 in `docs/evidence/sources.md` (design, "Sources registered by this change") and extend the "used for" cells of S-0138, S-0187 and S-0188; if c0037 has not yet registered S-0187 and S-0188, add them with its wording. Proof: `uv run pytest tests/unit/test_format_facts.py tests/residue`
- [x] 1.2 Register the eleven rows `H-A-RD-PRJ-*` in `docs/hypotheses.md` (design, "Hypotheses"), each `INFERRED` with its test or kit request. Proof: `uv run pytest tests/unit/test_hypotheses_register.py`
- [x] 1.3 Write the fact pages in Fenolite's own words: the section "The project file as Altium saves it" in `docs/formats/altium/project.md`, and the new pages `output-job.md`, `rule-file.md` and `stackup-file.md`; accept the stem `H-A-RD-` in `tests/unit/test_format_facts.py`; add one row per area to `src/fenolite/backends/altium/PROVENANCE.md`. Proof: `uv run pytest tests/unit/test_format_facts.py`
- [x] 1.4 Add the twelve rows to `tests/corpus/manifest.toml` (design, "Corpus rows") under c0039's rules for second-backend rows, with the uses `altium`, `altium-text` and `origin:third-party`; fetch them and record each SHA-256, size and year from the fetched bytes; add a manifest case that an `altium-text` row holds no `cfb`. Proof: `uv run python tools/corpus_fetch.py --uses altium-text && uv run pytest tests/corpus/test_manifest.py`
- [x] 1.5 Write `docs/evidence/altium-project-read.md` with the corpus table (row id, kind, licence, form) and the author-report request for `H-A-RD-PRJ-HIER` (five projects, one per net identifier scope, saved in Altium Designer 26.5; the reported `HierarchyMode` of each) and for the rule export form. Proof: `uv run pytest tests/unit/test_hypotheses_register.py tests/residue`

## 2. Text forms

- [x] 2.1 `read/textfile.py`: `TextLine`, `TextBytes`, `split_text`, `TEXT_READ_CODES`; the byte-order mark, the three line ends, the encoding rule, the compound-file and NUL refusals; create `read/__init__.py` if it is absent. Proof: `uv run pytest tests/unit/backends/altium/read/test_textfile.py`
- [x] 2.2 `read/ini.py`: `IniEntry`, `IniSection`, `IniDocument`, `parse_ini`, with duplicate keys, duplicate sections, stray lines and lines before the first section kept; a hypothesis-based property test of `parse_ini(data).to_bytes() == data` over generated INI bytes. Proof: `uv run pytest tests/unit/backends/altium/read/test_ini.py`
- [x] 2.3 `read/proptext.py`: `PropRecord`, `parse_fields`, `parse_length` (`mil` and `mm`, exact fraction, half to even). Proof: `uv run pytest tests/unit/backends/altium/read/test_proptext.py`
- [x] 2.4 `textfile.text_kind` for the five text kinds, `compound` and `unknown`; author the fixtures of `tests/data/altium/read/` with invented names and values and declare them `origin = "authored"` in `tests/data/MANIFEST.toml`. Proof: `uv run pytest tests/unit/backends/altium/read/test_textfile.py -k kind tests/corpus/test_manifest.py`

## 3. Project file

- [x] 3.1 `read/project.py`: `DOCUMENT_KINDS`, `ProjectDocument`, documents and generated documents by section name, `posix`, the kind table, the unknown-kind info. Proof: `uv run pytest tests/unit/backends/altium/read/test_project_read.py -k documents`
- [x] 3.2 `ProjectOptions`, `HIERARCHY_MODES`, `ProjectParameter`, `ProjectFile`, `read_project`; the warnings for an unknown hierarchy mode and a missing `[Design]`. Proof: `uv run pytest tests/unit/backends/altium/read/test_project_read.py`
- [x] 3.3 Read back the bytes of `prjpcb.write_prjpcb` and the committed sample project files under `tests/data/altium/`. Proof: `uv run pytest tests/unit/backends/altium/read/test_project_read.py -k own`

## 4. Output job

- [x] 4.1 `read/outjob.py`: `OutputMedium`, `JobOutput`, `OutputGroup`, `OutJobFile`, `read_outjob`; the incomplete-output warning and the missing-section error. Proof: `uv run pytest tests/unit/backends/altium/read/test_outjob.py`

## 5. Rule files

- [x] 5.1 `read/rul.py`: the export form with both spellings of the end mark, the malformed-record warning, byte identity. Proof: `uv run pytest tests/unit/backends/altium/read/test_rul.py -k export`
- [x] 5.2 The summary form (header line and records) and the error for an unknown form. Proof: `uv run pytest tests/unit/backends/altium/read/test_rul.py`

## 6. Scope grammar and rule mapping

- [x] 6.1 `read/scope.py`: `parse_scope` for the closed grammar; refusals for mixed operators, `All` below the top level, layer functions, wildcards, quotes and left-over text. Proof: `uv run pytest tests/unit/backends/altium/read/test_scope.py`
- [x] 6.2 `read/rules.py`: `RULE_KIND_MAP`, `PENDING_KINDS`, `Unmapped`, `RuleMapping`, `map_rules` for Clearance and Width, with ids, `native_ids`, the record in `ext["altium"]` and the ordered reasons. Proof: `uv run pytest tests/unit/backends/altium/read/test_rule_map.py -k "clearance or width or reasons"`
- [x] 6.3 Routing Via Style (two rules) and Hole Size (absolute only); the summary case; the partition of record indexes into `sources` and `unmapped` as a property test over generated field lists; a case with the field list of a board's rule record (the 16-bit kind number left out). Proof: `uv run pytest tests/unit/backends/altium/read/test_rule_map.py`
- [x] 6.4 Check that the code tables equal the tables of the fact pages. Proof: `uv run pytest tests/unit/backends/altium/read/test_text_tables.py`

## 7. Stack-up file

- [x] 7.1 `read/stackup.py`: `StackEntry`, `StackupFile`, `read_stackup`; entries by key presence, lengths in `mil` and `mm`, `epsilon_r` as text, the two warnings, the missing-version error. Proof: `uv run pytest tests/unit/backends/altium/read/test_stackup.py`

## 8. Project loading and corpus

- [x] 8.1 `LoadedDocument`, `AltiumProject`, `load_project`: companions inside the folder, the outside-path, missing and unreadable cases, the case-insensitive fallback, issue order. Proof: `uv run pytest tests/unit/backends/altium/read/test_load_project.py`
- [x] 8.2 The import test of the nine text modules (no compound reader, only `core`, `model` and siblings) and the closed-code test. Proof: `uv run pytest tests/unit/backends/altium/read/test_text_imports.py tests/unit/backends/altium/read/test_text_codes.py tests/unit/test_import_graph.py`
- [x] 8.3 `tests/corpus/test_altium_text.py`: identity, codes and the per-kind checks over the twelve rows, naming rows by id only. Proof: `uv run python tools/corpus_fetch.py --uses altium-text && uv run pytest tests/corpus/test_altium_text.py`
- [x] 8.4 Record the corpus census in `docs/evidence/altium-project-read.md` (per row: sections or records counted, rule kinds seen, mapped and unmapped counts by reason) and add to the kind table of `rule-file.md` every rule kind the corpus holds. Proof: `uv run pytest tests/unit/test_format_facts.py tests/unit/backends/altium/read/test_text_tables.py`

## 9. Closing

- [x] 9.1 Run the whole suite and the residue scan; no corpus file, corpus path or corpus value is in the repository. Proof: `make check && uv run pytest tests/residue`
- [x] 9.2 Update the evidence labels: set `H-A-RD-PRJ-INI`, `-DOCS`, `-OUTJOB` and `-ENC` and their fact-page rows to `CORPUS-VERIFIED` with the date and row count; record the corpus result of `-PARAM`, `-RUL-EXPORT`, `-RUL-SUMMARY` and `-STACKUP` as supporting data and keep them at `INFERRED` (fewer than three repositories); keep `H-A-RD-PRJ-RULE-MAP`, `-SCOPE` and `-HIER` at `INFERRED`. Proof: `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_format_facts.py`
- [x] 9.3 Update `CHANGELOG.md` under `## [Unreleased]` and the v0.3 entry of `docs/roadmap.md`. Proof: `uv run pytest tests/unit/verify/test_cited_ids.py tests/unit/test_hypotheses_register.py && openspec validate c0042-altium-project-reader --strict`
