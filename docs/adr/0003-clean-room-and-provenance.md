# ADR-0003: Clean-room development and provenance of format knowledge

## Status
Accepted (2026-09-30)

## Context
Fenolite reads and writes the file formats of other EDA tools. Much of that knowledge is not
published by the vendors and has to be learned from public documentation of other open-source
projects and from sample files. Contributors may also have access to non-public design files
(from an employer or clients), for example to try an idea on real boards. Without explicit rules,
material derived from such files (constants measured on them, seeds, fixtures, statistics,
vocabularies, templates) could leak into an open-source repository, and copyleft code could leak
into an Apache-2.0 package.

## Decision
1. Fenolite is developed **clean-room**. No design files, constants measured on non-public files,
   seeds, fixtures, test data, statistics, vocabularies, parameter sets, templates or examples
   belonging to or derived from any organisation's material enter the repository. Code is written
   for Fenolite; nothing is ported from non-public projects.
2. Format knowledge comes only from public sources. Every fact the code relies on is recorded in
   `docs/formats/<backend>/*.md` with a source id from `docs/evidence/sources.md`, and every backend
   package carries a `PROVENANCE.md` listing the public sources read for it.
3. Work sessions on `src/fenolite/backends/` and `docs/formats/` are logged in `LEGAL-ANNEX.md`
   (date, area, files touched, public sources consulted).
4. The rules are enforced mechanically: a residue scan (public structural patterns, public blob
   hashes, private token and blob lists kept outside the repository), a copyleft-dependency test,
   a no-ported-code test, a provenance test and a corpus manifest in which only CC0 or authored
   files may be committed.
5. No list of private identifiers is ever committed, in clear or hashed form.

## Alternatives
- **Use non-public boards as committed test fixtures**: realistic coverage, but the files, and any
  value measured on them, would become public through the repository, its history and the built
  packages; rejected. Such files may only be used privately and leave no trace in the tree.
- **Strict clean-room with two separate people** (one reads, one writes): the classic pattern for
  learning formats, not available to a small project; the session log and the "facts only, with a
  public source" rule are the practical substitute.
- **Policy documents without enforcement**: rejected; leaks happen by accident, not by intent.

## Consequences
- The second backend is written from public documentation and public sample files, which takes
  longer than porting.
- Every format fact is traceable to a public URL, which also makes the documentation useful to
  other projects.
- Contributors need a small amount of ceremony: a `PROVENANCE.md` row per source, a session-log
  row per week of format work, and a green residue scan.

## Evidence
- `LEGAL.md` (blocks A and B), `LEGAL-ANNEX.md`, `docs/provenance.md`.
- Tests: `tests/residue/`, `tests/unit/test_no_copyleft_deps.py`, `tests/unit/test_no_ported_code.py`,
  `tests/unit/test_provenance.py`, `tests/corpus/test_manifest.py`.
