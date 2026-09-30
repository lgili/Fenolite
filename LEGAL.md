# Legal notes

Fenolite is licensed under the Apache License, Version 2.0 (see `LICENSE` and `NOTICE`).
This file explains where Fenolite's knowledge of third-party file formats comes from and how the
project relates to earlier, non-public work in the same domain. It is a statement of project
policy, not legal advice.

## A. Format analysis

Fenolite reads and writes files produced by other electronic design automation (EDA) tools.

1. Knowledge of third-party file formats comes **only** from public documentation (official
   documentation, published specifications, public developer documentation of open-source tools)
   and from files the contributor is entitled to read (files they created themselves, or files
   published under a licence that permits the use).
2. Every format fact used by the code is recorded in `docs/formats/<backend>/*.md` with its public
   source, listed in `docs/evidence/sources.md`, and carries an evidence label. Code is written
   from those pages, never from third-party source code. Reading public copyleft sources to learn
   a **fact** is allowed only when the fact is recorded there with its source.
3. Copyleft software (GPL, AGPL and similar) is used only behind a process boundary (a
   subprocess exchanging files or documented JSON) or through a plugin API that its project
   publishes; it is never imported, vendored or transcribed (ADR-0004).

The following are **forbidden** (ADR-0003):

- **(P1)** decompiling, disassembling or otherwise reverse engineering vendor software — contributors
  never decompile a tool to learn its format;
- **(P2)** transcribing, compiling or converting GPL/AGPL parser sources or machine-readable grammar
  files (for example Kaitai `.ksy` descriptions) into Fenolite code;
- **(P3)** using files the contributor is not entitled to read (for example an employer's design
  files, or files obtained under terms that do not allow this use);
- **(P4)** using an employer's software licence to study or reverse engineer a tool for Fenolite.

Opening a file one is entitled to read in a tool one is licensed to use, and reporting what the
tool does with it, is ordinary use and may be recorded as a fact with evidence label
`…(author-report)`; no file used in such a session enters the repository unless it is authored for
Fenolite or published under a licence listed as embeddable in the corpus manifest.

## B. Material from organisations

Fenolite is developed **clean-room** with respect to non-public material:

- no design files, templates, title blocks, rule sets, part libraries, parameter conventions,
  constants measured on non-public files, seeds, fixtures, test data, statistics, vocabularies or
  examples belonging to any organisation (including a contributor's employer or clients) are added
  to Fenolite, even when such files were used privately to try an idea;
- every format fact is derived from the public sources in block A and recorded with them;
- work sessions on format code are logged in `LEGAL-ANNEX.md`.
