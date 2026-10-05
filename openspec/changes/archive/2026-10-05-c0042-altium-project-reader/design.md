## Context

- **Need.** v0.3 reads Altium projects. The import change (c0043) needs to know which files form a
  project, how nets are scoped across sheets, and which design rules and layer stack the user keeps in
  text files beside the board.
- **Today.** `backends/altium/prjpcb.py` writes a minimal project file (`[Design]`, `Version=1.0`, one
  `[Document<n>]` per file). Nothing reads a project file, an output job, a rule file or a stack-up
  file. `docs/formats/altium/project.md` holds the writer's facts.
- **The files are plain text.** None of the four is a compound file. The reader works on bytes and
  does not use c0039's container reader (Decision 1).
- **Research of 2026-10-03** (public sources only; nothing saved in the repository):
  - **Project file.** Two Altium-saved projects were read (S-0187, MIT; S-0188, LGPL-3.0).
    - One is UTF-8 with a byte-order mark and LF line ends; the other is 7-bit ASCII with CR LF. So
      the encoding, the mark and the line end vary and must be kept.
    - Both hold `[Design]` with `Version=1.0`, `HierarchyMode=0` and about forty more keys, then
      `[Preferences]`, numbered `[Document<n>]`, `[GeneratedDocument<n>]`, `[Configuration<n>]`,
      `[OutputGroup<n>]` and a dozen option sections. One adds `[ProjectVariant<n>]` and
      `[Parameter<n>]` (`Name`, `Value`).
    - A document section holds `DocumentPath` and about fourteen more keys, with `DocumentUniqueId`.
      Paths use `\`. Documents seen: schematics, the board, libraries, harness files, an output job,
      a bill of materials document, draftsman documents and an annotation file.
    - One project lists an output job that its repository does not hold: a missing companion is a
      normal state.
    - Altium documents five net identifier scopes and says the options are stored in the project
      file (S-0138). No permitted source gives the number of each scope; only `0` was seen.
  - **Output job.** Altium documents it as an ASCII file with outputs, containers and hard copy
    (S-0293). Public files (S-0297, S-0299) are INI files: `[OutputJobFile]` with `Version`,
    `[PublishSettings]`, `[GeneratedFilesSettings]` and `[OutputGroup1]` with numbered keys per output
    (`OutputType<i>`, `OutputName<i>`, `OutputCategory<i>`, `OutputDocumentPath<i>`,
    `OutputVariantName<i>`, `OutputEnabled<i>`, `OutputEnabled<i>_OutputMedium<j>`) and per medium
    (`OutputMedium<j>`, `OutputMedium<j>_Type`).
  - **Rule file.** Two different files carry the extension `.RUL`.
    - The **export** of the PCB rules editor (S-0294): one record per line, `KEY=VALUE` parts joined
      by `|`, the keys of a PCB document's rule record (c0038's research), each record ended by a
      pilcrow sign (bytes `C2 B6`) and LF. One public file (S-0297, MIT) holds 48 rules of 32 kinds.
    - A **summary** written beside Gerber outputs (S-0298, S-0188): a line
      `DRC Rules Export File for PCB: <path>`, then lines `RuleKind=…|RuleName=…|Scope=Board|<key>=<number>`
      with CR LF. The numbers carry no unit, and the first line can hold a user's absolute path.
  - **Rules.** Altium documents ten rule categories, the scopes (All, Net, Net Class, Layer, Net and
    Layer, Custom Query), unary and binary rules, and the priority: 1 is the highest, and the first
    rule whose scopes match is applied (S-0294). It documents Width (minimum, preferred, maximum; the
    minimum and maximum are checked), Routing Via Style (diameter and hole, each minimum, preferred
    and maximum), Hole Size (absolute or percent) and Board Outline Clearance (S-0295), and the query
    functions (S-0296). It does not state the operator precedence of a query.
  - **Stack-up file.** The Layer Stack Manager saves a `*.stackup` file (S-0300). Public files
    (S-0297, S-0187) are one property text that starts with `|STACKUPVERSION=1`, without a line end;
    one starts with a byte-order mark and holds bytes above `7F`. Layers are `LAYER_V8_<i><KEY>` with
    the keys of the board record's stack (`docs/formats/altium/pcb-library.md`): `NAME`, `LAYERID`,
    `COPTHICK`, `DIELTYPE`, `DIELCONST`, `DIELHEIGHT`, `DIELMATERIAL`, `COMPONENTPLACEMENT`. Lengths
    are written in `mm` in one file; the board record uses `mil`.
- **Neutral model.** `model.rules` has six kinds (`clearance`, `track_width`, `via_diameter`,
  `via_drill`, `hole_size`, `edge_clearance`), a selector algebra whose leaf values are globs, and a
  priority in which 1 is the highest. `model.board.StackLayer` holds `epsilon_r` as text.
- **Sibling changes** (written in parallel; read on 2026-10-03 for names).
  - c0039 creates `backends/altium/read/` with `cfb.py`, and the `corpus-policy` requirement
    "Second-backend corpus rows", whose id pattern already has the kinds `prjpcb`, `outjob`, `rules`
    and `stackup`.
  - c0040 keeps its property text in `read/sch/props.py`, c0041 in `read/pcbprops.py`. c0041's
    `RuleRecord` gives `rule_kind`, `name`, `enabled`, `priority`, `scope1`, `scope2` and `fields`,
    and leaves the mapping of rule kinds to this change.
  - c0043 calls `read.project.load_project` and `read.rules.map_rules`.

## Goals / Non-Goals

**Goals**
- Parse the four text files and give the input bytes back.
- Type what c0043 needs: documents and kinds, parameters, the hierarchy mode, output groups, rule
  records, stack entries.
- Map the rule kinds that have a neutral counterpart, exactly or not at all, and list every other rule.
- Give c0043 one function for a project folder.

**Non-Goals**
- Writing or editing these files; the import into `Design`; a registered backend; CLI commands.
- Typed variants, configurations, error-reporting, comparator and class-generation options.
- Running output jobs.
- `.Harness` (listed as documents of the kind `harness`, not read), `.PrjPcbStructure`, `.Annotation`, `.BomDoc`, draftsman files, `.stacktemplate`.
- Rule kinds outside the neutral model; `OnLayer` scopes; wildcards; operator precedence.
- The stack-up as a `Board.stackup` (c0043, from `StackEntry`).

## Decisions

1. **No dependency on the compound reader.** The text modules import only the standard library,
   `fenolite.core` and `fenolite.model`. A test checks it.
   - c0039 still comes first in the order: it creates `backends/altium/read/` and the manifest
     rules for second-backend corpus rows. If the package is absent when this change is implemented,
     task 2.1 creates its `__init__.py`.
   - Data with the compound-file signature is refused with a message that names the other reader.
   - Rejected: a common "open any Altium file" function here. `text_kind` tells the kinds apart;
     dispatch belongs to c0043 and c0044.
2. **Bytes are the source of truth.** `TextBytes` keeps the mark and each line's bytes and line end;
   every typed view is derived and `to_bytes()` joins the stored bytes.
   - Rejected: decode, parse and re-encode. A file that mixes line ends or holds bytes outside UTF-8
     would not come back equal.
   - Rejected: `configparser`. It drops duplicate keys, order of duplicates, comments and stray lines.
   - The typed text is UTF-8 when the bytes allow it, else Latin-1 with a warning. Latin-1 maps every
     byte, so reading never fails on an encoding (`H-A-RD-PRJ-ENC`).
3. **One lossless INI layer for the project file and the output job.** `ini.parse_ini` knows nothing
   of Altium. `project` and `outjob` read typed views from it by section and key name.
   - Names are matched exactly as written (both saved projects agree on the spelling).
   - Numbered sections are taken by name, not by position, and the numbers need not be consecutive.
4. **Typed views are small and closed; the rest stays raw.** The project view types documents,
   generated documents, parameters and seven `[Design]` options. c0043 reaches any other key through
   `ProjectFile.ini`.
   - Rejected: typing every `[Design]` key. Their meanings have no permitted source.
5. **Document kinds come from the extension**, without case, through a closed table. KiCad's project
   importer does the same (S-0132). An unknown extension is `other` with an info.
6. **The hierarchy mode is a number; the scope name is a looked-up fact.** `HIERARCHY_MODES` holds
   only what the fact page states: `0 → automatic`, `INFERRED` under `H-A-RD-PRJ-HIER`.
   - Any other number gives `net_scope = None` and a warning. c0043 then decides (its default is the
     automatic rule of S-0138).
   - The maintainer's author report (Altium Designer 26.5: five projects, one per scope) fills the
     other four rows. Until then they are absent, not guessed.
   - Rejected: numbering the scopes in the order of the dialog. It is a guess that would change
     connectivity silently.
7. **Both `.RUL` forms are read; only the export form can map.**
   - The form is told from the content: a first line that starts with `DRC Rules Export File for PCB:`
     is the summary; a line with `RULEKIND=` is the export.
   - The summary's numbers have no unit, so its records are listed with the reason `summary-form`.
   - Rejected: assuming mils. Nothing permitted states it.
   - The pilcrow end mark is kept in the raw line and stripped from the last value, as `C2 B6` or `B6`.
8. **Rule mapping is exact or absent.** A record maps only when its kind, its header values, its keys
   and its scopes are all inside closed tables; otherwise it becomes an `Unmapped` with one of ten
   reasons. The invariant `mapped sources + unmapped = records` is a test, also on the corpus.
   - Four kinds map: Clearance, Width, Routing Via Style (two neutral rules: diameter and drill) and
     Hole Size (absolute values only).
   - `BoardOutlineClearance` has a neutral counterpart (`edge_clearance`), but no permitted source
     gives its keys. It is listed as `no-verified-keys`, apart from `no-counterpart`, so the gap is
     visible (Open Question 1).
   - A key the table does not know blocks the mapping (`keys`). This is why a Clearance rule with an
     object matrix (`OBJECTCLEARANCES`) or a Width rule with per-layer values is reported, not
     flattened.
   - A disabled rule is not mapped. Rejected: severity `ignore`. In Altium a disabled rule is skipped
     and the next rule applies; a neutral rule with `ignore` would silence the check.
   - Altium's priority goes into `Rule.priority` unchanged: 1 is the highest in both. Altium numbers
     priorities per kind, and rules of different kinds never compete, so no renumbering is needed.
   - The preferred value becomes `opt`. The KiCad lowering refuses `opt` on `via_drill` and
     `hole_size`; c0043 or the user decides what to do then (Open Question 2). Rejected: dropping the
     preferred value here, which would lose data before anyone could choose.
   - Each rule keeps its record text in `ext["altium"]` and the rule's unique id in `native_ids`.
9. **Lengths.** `<decimal>mil` or `<decimal>mm`, converted as a fraction and rounded half to even to
   the nanometre with `core.units.round_half_even_div`.
   - Altium prints its 2.54 nm unit with a few decimals, so `3.937mil` is 99 999.8 nm: rounding is
     unavoidable and its error is below 1 nm. No issue is raised for it.
   - Rejected: refusing values that are not whole nanometres. Every metric rule would be unmapped.
10. **Closed scope grammar, no precedence.** `All`, `InNet`, `InNetClass`, `InComponent`, `IsTrack`,
    `IsVia`, `IsPad`, `And`/`&&`, `Or`/`||`, `Not` and parentheses.
    - One parenthesis level holds one operator kind. Altium's editor writes generated scopes this way;
      a hand-written query that relies on precedence is reported.
    - Values with `*`, `?`, `[`, `]` or `'` are refused: a neutral leaf value is a glob, so a literal
      `*` would change meaning, and Altium's own wildcard rules are not stated.
    - `OnLayer` is refused: it needs the board's layer names mapped to neutral names, which only
      c0043 can do (Open Question 3).
    - `IsPolygon` is refused: a neutral `zone` and an Altium polygon pour are not shown to be the
      same set of objects.
11. **`map_rules` takes field lists, not files.** A PCB document stores each rule as a property text
    with the same keys (c0038's research). c0041's `RuleRecord.fields` and this change's
    `PropRecord.fields` are both lists of `(key, value)` pairs, so c0043 passes either. One mapping,
    two carriers.
    - Rejected: a signature of typed arguments (kind, name, priority, …). The kind's keys would still
      travel as a field list, and the header values are fields of the same list.
12. **Stack-up file: one record, typed entries by key presence.** An entry with `COPTHICK` is copper;
    one with `DIELHEIGHT` is a dielectric (a solder mask has `DIELTYPE=3` and is a dielectric entry;
    c0043 maps the type). Entries without a thickness (overlays, paste, mechanical) are not typed.
    - `epsilon_r` stays text, as the model wants.
    - The generation number in `LAYER_V<g>_` is read from the key, not fixed to 8.
13. **`load_project` opens only text companions inside the project folder.**
    - Paths that leave the folder are not opened and not printed (a project can name a path on its
      author's machine).
    - A missing or unreadable companion is a warning: the project still loads.
    - File names are matched without case as a fallback, because the files come from Windows.
    - Schematics, boards and libraries are listed with `present`; c0043 opens them with their readers.
14. **Issues are warnings and infos; malformed input raises `FormatError`.** The CLI maps it to
    `FEN-3004` (existing code). No new `FEN` code.
15. **Corpus first, fixtures authored.** Twelve public files are fetched at pinned commits. The unit
    fixtures under `tests/data/altium/read/` are written by hand for Fenolite, with invented names and
    values, and declared `origin = "authored"`.
16. **No capability report change.** The `altium` backend's `read_kinds` change when c0043 registers
    the reader. This change adds library functions only.

## Interface for c0043

```python
from fenolite.backends.altium.read.project import load_project, read_project
from fenolite.backends.altium.read.rules import map_rules
from fenolite.backends.altium.read.proptext import parse_fields

project = load_project(path)            # AltiumProject
project.project.options.net_scope       # "automatic" | … | None
project.documents                       # LoadedDocument(document, file, present)
project.rules                           # ((document index, RuleMapping), …)
project.stackups                        # ((document index, StackupFile), …)
map_rules([r.fields for r in doc.rules], origin="board.PcbDoc")   # c0041's RuleRecord
```

- c0043 opens the documents of the kinds `schematic`, `pcb`, `schematic-library` and `pcb-library`
  with the readers of c0040 and c0041; this change opens none of them.
- `RuleMapping.ruleset` is a neutral `RuleSet`. Settled with c0043 (2026-10-03):
  - c0043 calls `map_rules([r.fields for r in doc.rules], origin=<file name>)`. c0041's
    `RuleRecord.fields` is the whole pair list of the record, typed keys included, so the mapper
    finds `RULEKIND`, `NAME`, `PRIORITY`, `ENABLED` and the scopes there. The 16-bit kind number of
    `Rules6` is not passed: `RULEKIND` decides.
  - The mapper owns the kind table, the limits, the selectors, `priority` and `severity`. The
    adapter takes those unchanged and re-keys the header for the imported design: it replaces
    `Rule.id`, `RuleSet.id`, `native_ids` and `ext["altium"]` by those of its own tables
    (c0043, "Identifiers and provenance" and "Extension bags"), and adds the provenance. The ids
    and the bag of this change stand for a caller that uses `map_rules` alone.
  - The adapter does not forward the per-rule infos `altium.rule.unmapped`: it reports one
    `altium.import.rule-unmapped` per rule kind, with the count and the reasons of
    `RuleMapping.unmapped`. Other issues of the mapper are forwarded.
  - A disabled rule is `Unmapped` (`disabled`); c0043 follows (Open Question 8).
- The top sheet is not given by the document order (c0037's research); c0043 finds it from the
  sheet symbols.

## Files and public API

| file | public API |
|---|---|
| `src/fenolite/backends/altium/read/__init__.py` | created only if c0039 has not created it; no re-exports |
| `src/fenolite/backends/altium/read/textfile.py` | `TextLine(raw, end)`, `TextBytes(bom, encoding, lines)` with `to_bytes()`; `split_text(data, *, file="", issues=None) -> TextBytes`; `TextKind`; `text_kind(data, *, name="") -> TextKind`; `TEXT_READ_CODES` |
| `src/fenolite/backends/altium/read/ini.py` | `IniEntry(key, value, line)`, `IniSection(name, entries, line)` with `get(key)`, `IniDocument(form, sections, issues)` with `to_bytes()`, `section(name)`, `numbered(stem)`; `parse_ini(data, *, file="") -> IniDocument` |
| `src/fenolite/backends/altium/read/proptext.py` | `PropRecord(fields)` with `get(key)`, `keys()`, `text`; `parse_fields(text) -> PropRecord`; `parse_length(text) -> Nm \| None` |
| `src/fenolite/backends/altium/read/project.py` | `DocumentKind`, `DOCUMENT_KINDS`, `HIERARCHY_MODES`, `ProjectDocument`, `ProjectParameter`, `ProjectOptions`, `ProjectFile`, `read_project(data, *, file="") -> ProjectFile`; `LoadedDocument`, `AltiumProject`, `load_project(path) -> AltiumProject` |
| `src/fenolite/backends/altium/read/outjob.py` | `OutputMedium`, `JobOutput`, `OutputGroup`, `OutJobFile`, `read_outjob(data, *, file="") -> OutJobFile` |
| `src/fenolite/backends/altium/read/rul.py` | `RuleFileKind`, `RuleFile(form, kind, header, records, issues)`, `read_rule_file(data, *, file="") -> RuleFile` |
| `src/fenolite/backends/altium/read/scope.py` | `parse_scope(text) -> Selector \| str` |
| `src/fenolite/backends/altium/read/rules.py` | `RULE_KIND_MAP`, `PENDING_KINDS`, `UnmappedReason`, `Unmapped`, `RuleMapping(ruleset, unmapped, issues)` with `sources`; `map_rules(records, *, origin, summary=False) -> RuleMapping` |
| `src/fenolite/backends/altium/read/stackup.py` | `StackEntry`, `StackupFile(form, record, version, layers, issues)`, `read_stackup(data, *, file="") -> StackupFile` |
| `tests/unit/backends/altium/read/` | `test_textfile.py`, `test_ini.py`, `test_proptext.py`, `test_project_read.py`, `test_outjob.py`, `test_rul.py`, `test_scope.py`, `test_rule_map.py`, `test_stackup.py`, `test_load_project.py`, `test_text_codes.py`, `test_text_tables.py`, `test_text_imports.py` |
| `tests/corpus/test_altium_text.py` | corpus identity and census, `needs_corpus` |
| `tests/data/altium/read/` | authored fixtures: `project_utf8.PrjPcb`, `project_crlf.PrjPcb`, `project_companions.PrjPcb`, `jobs.OutJob`, `rules_export.RUL`, `rules_summary.RUL`, `two_layer.stackup` |
| `docs/formats/altium/` | `project.md` (extended), `output-job.md`, `rule-file.md`, `stackup-file.md` |
| `docs/evidence/altium-project-read.md` | corpus results and the author-report request for the hierarchy modes |

Every dataclass is frozen with slots. Layering: `backends.altium` may import `model`, `geometry` and
`backends.base`; these modules use `core` and `model` only (`package-layering`, unchanged).

## Sources registered by this change

The range of this change was moved from S-0229–S-0236 to S-0293–S-0300 at integration (2026-10-03):
the first range overlaps the ranges of the active changes c0023, c0024 and c0025.

| id | source | licence | used for |
|---|---|---|---|
| S-0293 | https://www.altium.com/documentation/altium-designer/preparing-for-manufacture/output-jobs | Altium documentation, all rights reserved (read for facts) | an output job is an ASCII file of the project; output categories, containers, hard copy, per-output source, variant and enabled state |
| S-0294 | https://altium.com/documentation/node/254486/printable/print, https://www.altium.com/documentation/knowledge-base/altium-designer/import-or-export-design-rules and https://altium.com/documentation/altium-designer/pcb-design-rule-types?version=17 | Altium documentation, all rights reserved (read for facts) | rule categories and types; scopes; unary and binary rules; priority 1 is the highest and the first matching rule applies; name, comment, unique id, enabled; export and import of rules as a `.RUL` file |
| S-0295 | https://www.altium.com/documentation/altium-designer/pcb-electrical-rules, https://www.altium.com/documentation/altium-designer/pcb-routing-rules and https://altium.com/documentation/altium-designer/pcb-manufacturing-rules?version=22 | Altium documentation, all rights reserved (read for facts) | Clearance (net options, one value or an object matrix), Width, Routing Via Style, Hole Size, Board Outline Clearance |
| S-0296 | https://www.altium.com/documentation/altium-designer/pcb/query-functions | Altium documentation, all rights reserved (read for facts) | names of the query functions (membership, object type, layer checks) and operators; no precedence stated |
| S-0297 | https://github.com/odriverobotics/ODriveHardware at commit `079f30ac58f193226fcc552e4d6ba24553027ee1`: `v2/SEEEDSTUDIO.RUL`, `v2/Inverter.OutJob`, `v3/2layer.stackup`, `v3/4layer.stackup`, `v3/two_ax_PCB.PrjPcb` | MIT (`LICENSE`); files saved by Altium Designer, fetched to the corpus cache, never committed | the export form of a rule file, an output job, two stack-up files, a project file |
| S-0298 | https://github.com/Hack-a-Day/Vectorscope at commit `ea5fab24017abf67b1afa3762c5e563fb1956b0f`: `hardware/vectorscope/Gerber/vectorscope.RUL` | MIT (`LICENSE.txt`); fetched, never committed | the summary form of a rule file |
| S-0299 | https://github.com/Fermium/AltiumTemplates at commit `27f7fadb4443602b9cf23ff1ae71de0c2edb0e2d`: `020_Fabrication.OutJob` | MIT (`LICENSE`); fetched, never committed | an output job with fabrication outputs |
| S-0300 | https://www.altium.com/documentation/altium-nexus/pcb-dlg-layerstackmanagerlayer-stack-manager-ad and https://www.altium.com/documentation/cstu/layer-stack-manager | Altium documentation, all rights reserved (read for facts) | the Layer Stack Manager saves and loads a `*.stackup` file |

Existing ids cited: S-0132 (document sections, kinds by extension), S-0134, S-0138 (its row gains
"net identifier scopes; project options are stored in the project file"), S-0143, S-0160 and S-0161
(rule keys a second reader uses; facts only), S-0163 (mil text), S-0187 and S-0188 (registered by
c0037; their rows gain the project file, the output job, the stack-up file and the summary rule file
read here).

## Hypotheses registered by this change

| id | statement | settled by | level until then |
|---|---|---|---|
| `H-A-RD-PRJ-INI` | An Altium-saved project file and output job are INI text that `parse_ini` reads and returns byte for byte | corpus test (6 rows) | INFERRED → CORPUS-VERIFIED |
| `H-A-RD-PRJ-DOCS` | Documents are the sections `Document<n>` with `DocumentPath`, relative to the project folder with `\`; the kind follows from the extension | corpus test (3 rows) | INFERRED → CORPUS-VERIFIED |
| `H-A-RD-PRJ-PARAM` | Project parameters are the sections `Parameter<n>` with `Name` and `Value` | corpus test (the row that holds them) | INFERRED; the corpus count is supporting data until rows of three repositories hold parameters |
| `H-A-RD-PRJ-HIER` | `HierarchyMode` holds the net identifier scope; `0` is Automatic; the other four numbers are those of the author report | author report (five saved projects, AD 26.5) | INFERRED |
| `H-A-RD-PRJ-ENC` | A text file with a byte-order mark is UTF-8; without one it is ASCII or UTF-8 in every corpus row | corpus test (no `encoding-assumed` in 12 rows) | INFERRED → CORPUS-VERIFIED |
| `H-A-RD-PRJ-ENC-2` | Successor of `-ENC` (refuted at implementation, see "Implementation notes"): a file without a byte-order mark is 7-bit ASCII, UTF-8 or text of a single-byte code page, typed as Latin-1 with `altium.text.encoding-assumed` | corpus rows of three repositories with such text, and a permitted source for the code page | INFERRED |
| `H-A-RD-PRJ-OUTJOB` | An output job has `[OutputJobFile]` and `[OutputGroup<n>]` with the numbered output and medium keys | corpus test (3 rows) | INFERRED → CORPUS-VERIFIED |
| `H-A-RD-PRJ-RUL-EXPORT` | The export form holds one record per line, ended by a pilcrow sign, with the keys of a board's rule record | corpus test (1 row); author report on the form AD 26.5 exports | INFERRED; one repository, supporting data |
| `H-A-RD-PRJ-RUL-SUMMARY` | The summary form is a header line and `RuleKind`/`RuleName`/`Scope` records without units | corpus test (2 rows) | INFERRED; two repositories, supporting data |
| `H-A-RD-PRJ-RULE-MAP` | The keys of `RULE_KIND_MAP` mean what the table says (minimum gap; minimum, preferred and maximum width; via diameter and hole; absolute hole limits) | no test can settle it; S-0160, S-0161 and S-0295 agree | INFERRED |
| `H-A-RD-PRJ-SCOPE` | The closed grammar selects the objects the table says | no test can settle it; S-0294, S-0296 | INFERRED |
| `H-A-RD-PRJ-STACKUP` | A stack-up file is one property text with `LAYER_V<g>_<i>` keys from top to bottom | corpus test (3 rows) | INFERRED; two repositories, supporting data |

A `CORPUS-VERIFIED` label needs rows of at least three repositories (c0039, "Second-backend corpus
rows", **Origins**). Project files (S-0187, S-0188, S-0297) and output jobs (S-0187, S-0297, S-0299)
meet it. Rule files (one repository for the export form, two for the summary form), stack-up files
(two) and project parameters (one) do not: their rows stay `INFERRED`, and the corpus result is
recorded as supporting data. A row of a third repository, added later, raises them.

No id of this list exists in `docs/hypotheses.md` (checked 2026-10-03; the writer's rows are
`H-A-PRJ-OPEN` and `H-A-PRJ-KEEP`).

## Evidence per behaviour

| behaviour | level before merge |
|---|---|
| Byte identity and typed content of project files and output jobs (documents, kinds, output groups) | CORPUS-VERIFIED (rows of three repositories per kind) plus unit fixtures |
| Byte identity and typed content of rule files (both forms), stack-up files and project parameters | INFERRED; the corpus test runs on them and its result is supporting data (fewer than three repositories) |
| Rule mapping and scope grammar | INFERRED; unit tests prove the tables are applied, not that Altium means the same |
| Hierarchy-mode names | INFERRED until the author report |
| Fenolite's own project file reads back | unit test (no evidence claim about Altium) |

## Corpus rows

The rows follow c0039's "Second-backend corpus rows" (`corpus-policy`): ids
`altium-third-party-<kind>-NN`, a 40-digit commit, `uses = ["altium", "altium-text",
"origin:third-party"]`, `embeddable = false`, notes with the source id, kind, size and year only. The
SHA-256 of the two rows marked * is known from c0037's research; task 1.4 records the others from the
fetched bytes.

| id | source | path | licence |
|---|---|---|---|
| `altium-third-party-prjpcb-01` * | S-0187 | `DM3370_RAE/PCB/DM3370.PrjPcb` | MIT |
| `altium-third-party-prjpcb-02` * | S-0188 | `BMS/Battman.PrjPcb` | LGPL-3.0 |
| `altium-third-party-prjpcb-03` | S-0297 | `v3/two_ax_PCB.PrjPcb` | MIT |
| `altium-third-party-outjob-01` | S-0187 | `NG2092_OAK-D-IoT-40/PCB/KingTop.OutJob` | MIT |
| `altium-third-party-outjob-02` | S-0297 | `v2/Inverter.OutJob` | MIT |
| `altium-third-party-outjob-03` | S-0299 | `020_Fabrication.OutJob` | MIT |
| `altium-third-party-rules-01` | S-0297 | `v2/SEEEDSTUDIO.RUL` (export form) | MIT |
| `altium-third-party-rules-02` | S-0298 | `hardware/vectorscope/Gerber/vectorscope.RUL` (summary form) | MIT |
| `altium-third-party-rules-03` | S-0188 | `BMS/Project Outputs for Battman/Gerber/BMS.RUL` (summary form) | LGPL-3.0 |
| `altium-third-party-stackup-01` | S-0297 | `v3/2layer.stackup` | MIT |
| `altium-third-party-stackup-02` | S-0297 | `v3/4layer.stackup` | MIT |
| `altium-third-party-stackup-03` | S-0187 | `NG2092_OAK-D-IoT-40/PCB/NG2092.stackup` | MIT |

URLs are `https://raw.githubusercontent.com/<repository>/<commit>/<path>` with the commits of the
source rows. The names in the paths appear only in `url`. If c0039 or c0040 has already taken a
number of the `prjpcb` kind, these rows take the next free numbers.

## Size

7.5 design-days (a size, not calendar time).

| group | size |
|---|---|
| 1 Registers, pages, corpus rows | 0.75 |
| 2 Text forms, INI, property text | 1.0 |
| 3 Project file | 1.0 |
| 4 Output job | 0.5 |
| 5 Rule files | 0.75 |
| 6 Scope grammar and rule mapping | 1.5 |
| 7 Stack-up file | 0.75 |
| 8 Project loading and corpus test | 0.75 |
| 9 Closing | 0.5 |

Cut order: the output job (group 4, −0.5), then the summary form of the rule file (−0.25). Not
optional: text forms, the project file, the export form and its mapping, the stack-up file.

## Spec deltas and archive order

- One new capability, `altium-project-reader`, with 12 ADDED requirements. No MODIFIED requirement.
- No requirement name collides with a living spec or an active change (checked against
  `openspec/specs/` and `openspec/changes/` on 2026-10-03).
- The corpus rows rely on c0039's ADDED `corpus-policy` requirement "Second-backend corpus rows";
  this change adds no delta to `corpus-policy`.
- Archive order: c0039 → c0040 → c0041 → c0042 → c0043. This change needs nothing from c0040 or
  c0041, and from c0039 only the package folder and the manifest rules, so it can be implemented in
  parallel with c0040 and c0041.

## Risks / Trade-offs

- [One public file in the export form, from an older Altium] → the form is also the board's rule
  record, which five newer documents hold (c0038's research). The author report asks for the form
  that Altium Designer 26.5 exports. A new key only moves a rule to `Unmapped` (`keys`).
- [Newer Clearance or Width records carry matrix or per-layer keys, so few rules map] → that is the
  intended outcome of "exact or absent". The corpus census in the evidence page shows the rate; a
  follow-up widens the table from sources.
- [The summary's header line holds a user's absolute path] → it is kept in the bytes and in `header`
  only. Tests and issues never print it.
- [Latin-1 is the wrong guess for a file in another code page] → the bytes are kept, the warning says
  so, and only the typed text of the affected values is wrong.
- [Case-insensitive file matching picks a wrong file] → only when exactly one file matches.
- [Three property-text parsers exist after v0.3] → Open Question 4.
- [The hierarchy mode stays unknown for values other than 0] → c0043 falls back to the automatic rule
  and reports the warning; the author report closes it.
- [Stack-up files of newer versions add `$LSM$` keys with other values] → they stay in `record`; only
  the eight named keys are typed.

## Migration Plan

- Additive: new modules, pages, tests and corpus rows. No existing behaviour, file or golden changes.
- `tests/corpus/test_manifest.py` gains one case beyond c0039's rules: an `altium-text` row holds no `cfb`.
- `tests/unit/test_format_facts.py` accepts the stem `H-A-RD-` on Altium pages.
- Rollback: remove the modules and rows; nothing stored depends on them.

## Open Questions

1. Should `BoardOutlineClearance` map to `edge_clearance`? Default: no, reason `no-verified-keys`,
   until a permitted source or a public file gives its keys; then one row is added to the table.
2. Should the preferred via hole be dropped so that the KiCad lowering accepts the rule? Default: no;
   the mapping keeps `opt`, and c0043 or the convert step decides.
3. Should `OnLayer('<name>')` map to a `layer` selector? Default: no here; c0043 can extend the
   grammar once it has the board's layer map.
4. Three changes parse property text (`read/sch/props.py`, `read/pcbprops.py`, `read/proptext.py`),
   each for its own carrier. Should they merge? Default: not in v0.3; each change stays independent,
   and a later refactor joins them once all three exist.
5. Should `load_project` follow document paths outside the project folder? Default: no; they are
   listed with a warning.
6. Should variants (`[ProjectVariant<n>]`) be typed? Default: no in v0.3; they stay in `ini`.
7. Should `.PrjPcbStructure` be read to find the top sheet? Default: no; c0043 derives it from sheet
   symbols, since the file is optional and derived.
8. **Settled (integration, 2026-10-03): a disabled rule is not mapped.** c0043's requirement "Rules
   where they map" gave a disabled rule the severity `ignore`. This change's rule won: a disabled
   rule is `Unmapped` (`disabled`), because an `ignore` rule would silence the next matching rule
   (Decision 8). c0043 was edited to count it under `altium.import.rule-unmapped`.
9. **Settled (integration, 2026-10-03): `.Harness` files are listed here and read by no v0.3
   change.** This change owns the file kind: a `.Harness` document is listed with the kind `harness`
   and its `present` flag. Its content is not parsed. Harness connectivity comes from the harness
   records of the sheets (c0040) and c0043's "Harnesses"; a definition file adds nothing those
   records lack, and c0043 reports `altium.import.harness-nested` where it would. A reader of the
   file's content is a later change (after v0.3) in `read/project.py`; c0039 reserves the corpus id
   kind `harness` for it. c0040's spec was edited to say this.

## Implementation notes

Recorded while implementing the change (2026-10-05), in task order.

1. **Research corrections from the corpus.** The rows fetched for task 1.4 differ from the research of
   2026-10-03 in three points; the requirements already allowed each, so no behaviour changed:
   - The export-form rule file ends each record with the single byte `B6`, not with `C2 B6`, and is
     therefore not UTF-8. The requirement already named both marks. The reader strips a lone `B6` only
     when the file is read as Latin-1: in UTF-8 text a final `B6` is the continuation byte of another
     character.
   - One project file (S-0297) holds `HierarchyMode=2`; "only `0` was seen" no longer holds. It reads
     with `net_scope = None` and `altium.project.hierarchy-mode-unknown`, as Decision 6 wants; author
     report R1 settles it.
   - That project file has no byte-order mark and holds bytes above `7F` that are not UTF-8.
2. **`H-A-RD-PRJ-ENC` refuted.** Its criterion ("no `encoding-assumed` in 12 rows") fails on two rows
   of S-0297 (the project file and the export rule file). The row is kept, refuted at the level of the
   run (`CORPUS-VERIFIED`), with the successor `H-A-RD-PRJ-ENC-2`, `INFERRED` (one repository; no
   permitted source names the code page). Task 9.2 therefore raises `-INI`, `-DOCS` and `-OUTJOB`
   only. The spec delta ("Text reader evidence") and the proposal were amended; the encoding row of
   `project.md` names `-ENC-2`.
3. **Fact rows split for honest labels (task 9.2).** A fact row of `project.md` or `output-job.md` is
   `CORPUS-VERIFIED` only where `tests/corpus/test_altium_text.py` asserts it on all three rows of
   three repositories. Rows that mixed a tested and an untested statement were split; rows seen in
   fewer than three repositories, or about a meaning (relative paths, the enabled value per container,
   the publish settings), stay `INFERRED`. The corpus test gained the assertions those rows rest on.
4. **`ini`: key lines before the first section** form a section named `""` with `line` 0, so they stay
   reachable; the requirement only said they are kept.
5. **`proptext.parse_fields`:** a `|` at the very start or end of the text gives no part, because a
   stack-up file starts with `|` and can end with one; an empty part between two `|` is kept as
   `("", None)`. `PropRecord` has a second field, `text`, the text it was read from.
6. **`text_kind`:** a `.RUL` file whose content shows neither form is `unknown`; the extension decides
   only `.PrjPcb`, `.OutJob` and `.stackup`, because the extension does not tell the two rule forms
   apart.
7. **`RuleMapping.rule_records`:** a fourth field, the record index of each rule of `ruleset`, from which
   the property `sources` is derived. A rule does not carry its record index otherwise.
8. **Rule mapping details.** An empty `RULEKIND` or `NAME` is `malformed`, like an absent one. A missing
   `SCOPE1EXPRESSION`, or a missing `SCOPE2EXPRESSION`, is `scope`. `GENERICCLEARANCE` equals `GAP`
   when both parse to the same nanometres. The ``Unmapped`` of a summary record takes its kind and name
   from `RuleKind` and `RuleName`.
9. **`load_project`.**
   - `AltiumProject.issues` holds the issues of the project file and of each document (outside,
     missing, unreadable, and the companions' read issues), in document order. The issues of each
     `RuleMapping` stay in `rules`: c0043 replaces the per-rule infos by its own summary.
   - A path's inner `..` is resolved by name before the file is looked up (`sub\..\a.RUL`); a path
     whose file resolves outside the folder through a symbolic link is treated as outside.
   - An `OSError` while reading a companion is `altium.project.companion-unreadable`, like a
     `FormatError`; the message names the document index and the reason, never a path.
10. **Repository files beyond the table of files.** `.gitattributes` marks `*.OutJob`, `*.RUL` and
    `*.stackup` as `-text` so that the CR LF fixtures keep their bytes; `tests/unit/test_format_facts.py`
    lists the three new pages (its pattern already accepted `H-A-RD-`, from c0039); `LEGAL-ANNEX.md`
    gained the session row of the week. The corpus rows record as the year the last commit that touched
    each file at the pinned commit.
11. **Blink rules read back on the writer's grid.** The scenario "Fenolite's own rules map" holds; the
    preferred width of `Width_PWR` reads as 499 999 nm, because the writer prints `19.685mil` (the
    2.54 nm unit), and the mapper reads that text exactly.
12. **Task 9.1 order.** The full suite was run once, after tasks 9.2 and 9.3, so that it covers the
    final tree; its result is recorded in task 9.1.

**Added at landing (coordinator, 2026-10-05): the CI fetch.** The twelve corpus rows carry `altium-text` and neither `rt0` nor `cfb`, so the `kicad-10` job, which runs `tests/corpus` with `FENOLITE_REQUIRE=kicad,corpus`, did not fetch them and `test_altium_text.py` would have failed there. The job's fetch step now also passes `--uses altium-text`, and `tests/unit/test_ci_workflow.py` checks it (`ALTIUM_READER_USES`). No task named this. The living `ci-baseline` requirement "kicad-10 oracle job" still prints the fetch command without `--uses cfb` (c0039 changed the workflow without a delta); this change adds no delta either, and the stale command line is left for a follow-up that rewrites that step once.
