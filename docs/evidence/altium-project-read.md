# Altium project reader: corpus results and author-report requests

This page records the evidence of the text readers of change c0042
(`fenolite.backends.altium.read`: `textfile`, `ini`, `proptext`, `project`, `outjob`, `rul`, `rules`,
`scope`, `stackup`; capability `altium-project-reader`). The facts themselves are in
`docs/formats/altium/project.md`, `output-job.md`, `rule-file.md` and `stackup-file.md`; the
hypotheses are the rows `H-A-RD-PRJ-*` of `docs/hypotheses.md`.

- The corpus files are public files saved by Altium Designer, fetched at pinned commits with
  `uv run python tools/corpus_fetch.py --uses altium-text` and never committed. This page names them by
  row id only and gives counts and key names, never a name, a path or a value of a file.
- `tests/corpus/test_altium_text.py` (marker `needs_corpus`) reads every row with the reader of its
  kind and checks byte identity, the issue codes and the per-kind checks.
- A `CORPUS-VERIFIED` label needs rows of at least three repositories (`corpus-policy`, "Second-backend
  corpus rows"). Project files and output jobs meet it; rule files, stack-up files and project
  parameters do not, so their corpus results are supporting data and their rows stay `INFERRED`.
- No `kicad-cli` command reads these files, so no row is `ORACLE-VERIFIED`. Reading a key is no proof
  of its meaning: the rule mapping (`H-A-RD-PRJ-RULE-MAP`), the scope grammar (`H-A-RD-PRJ-SCOPE`) and
  the hierarchy-mode numbers (`H-A-RD-PRJ-HIER`) stay `INFERRED` whatever the corpus shows.

## Corpus rows

| row | kind | source | licence | form |
|---|---|---|---|---|
| `altium-third-party-prjpcb-01` | project file | S-0187 | MIT | INI; UTF-8 with a byte-order mark; LF |
| `altium-third-party-prjpcb-02` | project file | S-0188 | LGPL-3.0 | INI; 7-bit ASCII; CR LF |
| `altium-third-party-prjpcb-03` | project file | S-0297 | MIT | INI; bytes above `7F` that are not UTF-8; CR LF |
| `altium-third-party-outjob-01` | output job | S-0187 | MIT | INI; 7-bit ASCII; LF |
| `altium-third-party-outjob-02` | output job | S-0297 | MIT | INI; 7-bit ASCII; LF |
| `altium-third-party-outjob-03` | output job | S-0299 | MIT | INI; 7-bit ASCII; LF |
| `altium-third-party-rules-01` | rule file | S-0297 | MIT | export form; end mark `B6`; LF |
| `altium-third-party-rules-02` | rule file | S-0298 | MIT | summary form; CR LF |
| `altium-third-party-rules-03` | rule file | S-0188 | LGPL-3.0 | summary form; CR LF |
| `altium-third-party-stackup-01` | stack-up file | S-0297 | MIT | property text; no line end |
| `altium-third-party-stackup-02` | stack-up file | S-0297 | MIT | property text; no line end |
| `altium-third-party-stackup-03` | stack-up file | S-0187 | MIT | property text with a byte-order mark; no line end |

Repositories per kind: project files 3, output jobs 3, rule files 3 (one with the export form, two
with the summary form), stack-up files 2.

## Corpus census (2026-10-05)

`FENOLITE_CENSUS_OUT=<file> uv run pytest tests/corpus/test_altium_text.py` on the twelve rows, all
passing: every row reads with `to_bytes()` equal to the fetched bytes and no issue code outside
`TEXT_READ_CODES`; every project row lists schematic and PCB documents; every output job has a group
and no output without its type; in every rule row the mapped and the unmapped records partition the
record indexes; every stack-up row has at least two copper entries with a thickness. Counts only; the
rule kinds are listed in `docs/formats/altium/rule-file.md`, "Rule kinds seen".

| row | counts | issues |
|---|---|---|
| `altium-third-party-outjob-01` | 4 sections; 1 group, 8 media, 12 outputs (1 with `OutputEnabled<i>=1`) | none |
| `altium-third-party-outjob-02` | 4 sections; 1 group, 4 media, 3 outputs (3 with `OutputEnabled<i>=1`) | none |
| `altium-third-party-outjob-03` | 4 sections; 1 group, 4 media, 9 outputs (1 with `OutputEnabled<i>=1`) | none |
| `altium-third-party-prjpcb-01` | 81 sections; `[Design]` 48 keys, `HierarchyMode` 0; documents: annotation 1, bom 1, draftsman 2, harness 16, integrated-library 1, output-job 1, pcb 1, pcb-library 4, schematic 18, schematic-library 2; 2 generated; 5 parameters | none |
| `altium-third-party-prjpcb-02` | 71 sections; `[Design]` 34 keys, `HierarchyMode` 0; documents: annotation 1, harness 9, output-job 1, pcb 1, pcb-library 1, schematic 13, schematic-library 1; 19 generated; 0 parameters | none |
| `altium-third-party-prjpcb-03` | 34 sections; `[Design]` 34 keys, `HierarchyMode` 2; documents: integrated-library 1, pcb 1, pcb-library 1, schematic 4, schematic-library 1; 0 generated; 0 parameters | `altium.project.hierarchy-mode-unknown` 1, `altium.text.encoding-assumed` 1 |
| `altium-third-party-rules-01` | export form; 48 records of 32 kinds; 4 records mapped (rules: clearance 1, hole_size 1, track_width 1, via_diameter 1, via_drill 1); unmapped: no-counterpart 44 | `altium.text.encoding-assumed` 1 |
| `altium-third-party-rules-02` | summary form; 4 records of 4 kinds; 0 records mapped (rules: none); unmapped: summary-form 4 | none |
| `altium-third-party-rules-03` | summary form; 5 records of 4 kinds; 0 records mapped (rules: none); unmapped: summary-form 5 | none |
| `altium-third-party-stackup-01` | 311 fields; 2 copper and 3 dielectric entries; thicknesses in mm | none |
| `altium-third-party-stackup-02` | 347 fields; 4 copper and 5 dielectric entries; thicknesses in mm | none |
| `altium-third-party-stackup-03` | 406 fields; 6 copper and 7 dielectric entries; thicknesses in mil | none |

Findings:

- Two rows of one repository (S-0297) are not UTF-8 and have no byte-order mark: the project file
  holds single bytes above `7F` (such as `B0`) in values of its variant section, and the rule file ends each record with the single
  byte `B6`. Both read as Latin-1 with `altium.text.encoding-assumed` and come back byte for byte.
  The hypothesis that every row is ASCII or UTF-8 (`H-A-RD-PRJ-ENC`) is refuted by them; its
  successor `H-A-RD-PRJ-ENC-2` states the three forms seen and stays `INFERRED` (one repository, no
  permitted source for the code page).
- One project file holds `HierarchyMode=2`, which `HIERARCHY_MODES` does not hold: it reads with
  `net_scope = None` and `altium.project.hierarchy-mode-unknown`, as designed. The author report R1
  names its scope.
- The export form ends a record with the byte `B6`, not with `C2 B6`: both are recognised.
- Of the 48 records of the export row, the four kinds of `RULE_KIND_MAP` map (one record each, five
  neutral rules); the other 44 records are of kinds without a neutral counterpart. No record is
  refused for its keys, values or scopes: all four mapped records have the scope `All`.
- Project parameters are in one row only (five, each with a name), so `H-A-RD-PRJ-PARAM` stays
  `INFERRED`.

## Levels after the census

| hypothesis | level | basis |
|---|---|---|
| `H-A-RD-PRJ-INI` | `CORPUS-VERIFIED` | six rows of four repositories |
| `H-A-RD-PRJ-DOCS` | `CORPUS-VERIFIED` | three project rows of three repositories |
| `H-A-RD-PRJ-OUTJOB` | `CORPUS-VERIFIED` | three output-job rows of three repositories |
| `H-A-RD-PRJ-ENC` | refuted (`CORPUS-VERIFIED` run) | two rows of S-0297 are not UTF-8; successor `H-A-RD-PRJ-ENC-2` |
| `H-A-RD-PRJ-ENC-2` | `INFERRED` | the text that is not UTF-8 comes from one repository |
| `H-A-RD-PRJ-PARAM` | `INFERRED` | parameters in one repository; supporting data |
| `H-A-RD-PRJ-RUL-EXPORT` | `INFERRED` | one repository; supporting data |
| `H-A-RD-PRJ-RUL-SUMMARY` | `INFERRED` | two repositories; supporting data |
| `H-A-RD-PRJ-STACKUP` | `INFERRED` | two repositories; supporting data |
| `H-A-RD-PRJ-RULE-MAP` | `INFERRED` | a corpus result is no proof of a key's meaning |
| `H-A-RD-PRJ-SCOPE` | `INFERRED` | a corpus result is no proof of a scope's meaning |
| `H-A-RD-PRJ-HIER` | `INFERRED` | pending author report R1 |

## Author-report requests

These requests are for the maintainer, in Altium Designer 26.5. The result is recorded here and in the
row named, at the level `ALTIUM-VERIFIED(author-report; AD 26.5; <date>; no artefact)`; an author report
never raises an operation to verified.

### R1: hierarchy modes (`H-A-RD-PRJ-HIER`)

1. Create a new PCB project with one schematic sheet and save it.
2. In the project options, set the option "Net Identifier Scope" to Automatic and save the
   project. Note the value of `HierarchyMode` in `[Design]` of the saved `.PrjPcb`.
3. Repeat step 2 for Flat, Hierarchical, Strict Hierarchical and Global: five saved projects, one per
   scope.
4. Report the five pairs (scope, `HierarchyMode`). No file needs to be sent.

Until the report, `project.HIERARCHY_MODES` holds only `0 → automatic`, and every other number reads
with `net_scope = None` and the warning `altium.project.hierarchy-mode-unknown`.

### R2: the export form of a rule file (`H-A-RD-PRJ-RUL-EXPORT`)

1. Open any PCB document, then "Design » Rules".
2. Right-click the rule tree, choose "Export Rules", select Clearance, Width, Routing Via Style and Hole
   Size, and save the `.RUL` file.
3. Report: whether each line is one rule ending with a pilcrow sign, the bytes of that sign (`B6` or
   `C2 B6`), the line end, whether the file starts with a byte-order mark, and the keys of each record
   (key names only).

Until the report, the export form is known from one public file of an older Altium.
