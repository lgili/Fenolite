## Why

v0.3 reads the second backend. The project file says which files belong to a design and how nets are
named across sheets; three companion text files carry the output jobs, the design rules and the layer
stack. Fenolite writes a minimal `.PrjPcb` today and reads none of these files.

## What Changes

- **Text forms, kept byte for byte.** A product reader for the four text files of an Altium project.
  Each parse result gives the input bytes back (`to_bytes()`): unknown sections and keys, key order,
  line ends, the byte-order mark and the bytes of the encoding are kept.
- **Project file (`.PrjPcb`).** Documents with their kinds (by extension), project parameters, the
  `[Design]` options with the hierarchy mode, and every other section untouched.
- **Output job (`.OutJob`).** Output groups, their outputs (type, name, category, document, variant,
  enabled) and output media.
- **Rule files (`.RUL`).** Both forms that carry this extension: the rule export of the PCB rules
  editor and the short rule summary written beside Gerber outputs.
- **Stack-up file (`.stackup`).** One property record; layers with name, layer id, copper thickness,
  dielectric height, type, constant and material.
- **Rules onto the neutral model.** Four Altium rule kinds map onto `fenolite.model.rules`: Clearance,
  Width, Routing Via Style and Hole Size. A rule maps only when its kind, scope and keys are inside
  closed tables; every other rule is listed with a reason. No rule is dropped silently and no value is
  approximated.
- **One entry point for c0043.** `load_project(path)` reads the project file and its companion files
  from disk and returns one `AltiumProject`.
- **Corpus.** Twelve public files (MIT, LGPL-3.0), fetched at pinned commits.

**These files are plain text**, not compound files: the reader does not use c0039's container
reader. c0039 comes first for the `read/` package and the corpus rules only.

## Capabilities

### New Capabilities

- `altium-project-reader`: 12 ADDED requirements (text forms, project file, output job, rule files,
  rule mapping, scope grammar, stack-up file, project loading, issue codes, corpus, documentation,
  evidence).

### Modified Capabilities

- None.

## Non-goals

- No writer or editor for these files; `prjpcb.write_prjpcb` stays as it is.
- No import into `Design` and no registered backend (c0043). No CLI command (c0044).
- No compound files, schematics, boards or libraries (c0039 to c0041); no `.Harness`,
  `.PrjPcbStructure`, `.Annotation`, `.BomDoc` or draftsman files (listed as documents, not read).
- No typed variants, configurations or error-reporting options: kept as raw sections.
- No run of an output job; no rule kind beyond the model's six.
- No `OnLayer` scopes, wildcards or operator precedence in scope queries: reported, not guessed.
- No stack-up mapping onto `Board.stackup` (c0043 does it from the typed layers).

## Evidence level required

- Reading and byte identity: `CORPUS-VERIFIED` with three repositories
  (`H-A-RD-PRJ-INI`, `-DOCS`, `-OUTJOB`, `-ENC`); else `INFERRED` (`-PARAM`, `-RUL-EXPORT`, `-RUL-SUMMARY`, `-STACKUP`).
- The meaning of rule keys and scopes: `INFERRED` (`H-A-RD-PRJ-RULE-MAP`, `-SCOPE`). No oracle reads a
  `.RUL` file, so the mapping never claims more.
- The hierarchy-mode numbers: `INFERRED` (`H-A-RD-PRJ-HIER`) until the maintainer's author report
  (Altium Designer 26.5), then `ALTIUM-VERIFIED(author-report)`.
- Sources: Altium's public documentation (S-0293 to S-0296, S-0300), public licensed files (S-0187, S-0188,
  S-0297 to S-0299) and KiCad's importer for facts only (S-0132, S-0160, S-0161). Nothing is decompiled
  or transcribed.

## Impact

- Code: `src/fenolite/backends/altium/read/` (`textfile`, `ini`, `proptext`, `project`, `outjob`,
  `rul`, `rules`, `scope`, `stackup`). No change to `model`, `lens`, `cli` or the writers.
- Tests: `tests/unit/backends/altium/read/`, `tests/corpus/test_altium_text.py`; authored fixtures.
- Docs: `docs/formats/altium/project.md` (extended), `output-job.md`, `rule-file.md` and
  `stackup-file.md` (new); the registers; `PROVENANCE.md`.
- Order: c0039 → c0040 → c0041 → c0042 → c0043, which consumes `load_project` and `map_rules`.
- Size: 7.5 design-days.
