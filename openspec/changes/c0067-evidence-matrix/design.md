## Context

Counted on 2026-10-05 on `main`: `src/fenolite/backends/` holds 60 modules in three packages (`kicad` 41, `altium` 16, `specctra` 3). 27 of them declare an evidence constant (`EVIDENCE`, `WRITE_EVIDENCE`, `AUTHORING_EVIDENCE`, `NORMALISE_EVIDENCE`, `RT2_EVIDENCE`), 33 declare nothing. Every one of the 32 constants agrees with `docs/hypotheses.md` today: each id is registered, none is refuted, and no constant is stronger than a row it names. Nothing checks that; only the two constants behind the KiCad capability report are tested (`tests/unit/test_capability_evidence.py`, c0052).

What an agent sees is `result.backends[0].evidence`: one level for the whole KiCad backend. It does not say that drawing sheets are read and written, that projects are, that footprints are written only when authored, or that the Altium writers are experimental kind by kind.

The plan asks for two things in v0.2a (D13, D8 "Discovery", §7.1 rule 4): the matrix `detect / read / write / roundtrip_exact / roundtrip_modified / verified_by`, generated from the declarations in the code, and a CI failure when a backend module declares no level. The plan calls the declarations `# evidence:` markers. The code grew typed constants instead, from c0009 on, and the envelopes use them at run time. Decision 1 keeps the constants and gives the marker the two jobs a constant cannot do.

Living rules this change builds on and does not modify:
- `backend-protocol`, "Capability reports": `CapabilityReport.to_json()` has exactly eight keys; the KiCad report's evidence is `Evidence.combine(pcb.EVIDENCE, pcb.WRITE_EVIDENCE)`; `read_kinds` is what `Backend.read` accepts; `write_kinds` is what the backend can write.
- `cli-contract`, "Backends in capabilities" and "Experimental features in capabilities": both are MODIFIED by c0043 (proposed, v0.3). This change adds a third key next to them and touches neither.
- `verification-evidence`, "Verification package": `fenolite.verify` imports only the standard library and `fenolite.core`.

## Goals / Non-Goals

**Goals**
- One row per backend package and file kind, with a level per operation, in `capabilities` and on a generated page.
- No level written twice: a cell is a module's constant.
- A backend module that declares nothing fails the `unit` job.
- Every backend constant is held to the register, as the capability report is.

**Non-Goals**
- Raising or lowering a level. The audit writes down what the code claims.
- A version dimension, rows for tool reports, a guard outside `backends/`.
- Changing `CapabilityReport`, `result.backends` or `result.experimental`.
- Reading the register at run time.

## Decisions

1. **Constants declare levels; markers declare only delegation and absence.** A module that owns a claim keeps or gains a constant (`EVIDENCE`, `<NAME>_EVIDENCE`). A helper that runs only inside another module's operations carries `# evidence: see <module>`. A module that states nothing about a format or a tool (error classes, issue-code tables, the `backend.py` facade) carries `# evidence: none, <reason>`. The marker is read with `tokenize`, so text in a docstring is not a marker. Rejected: markers that carry the level (`# evidence: KICAD-VERIFIED H-…`), the plan's first idea: the envelopes need the level as a value, so every level would exist twice and drift. Rejected: `EVIDENCE = None` as the "no claim" form: every reader of `module.EVIDENCE` would need a `None` check, and delegation would still need a second name. Rejected: importing the covering module's constant into the helper: `pcb` imports `_pcbwrite`, so the helper cannot import `pcb`.

2. **`claims.py` places constants in cells; it never states a level.** Which constant is the `read` cell of which kind cannot be derived: `fill.EVIDENCE`, `drc.EVIDENCE` and `frame.EVIDENCE` are not about reading a kind, and `mod` holds two constants. So each package has one small table, `claims.MATRIX`, whose cells are attribute references (`pcb.EVIDENCE`) or `Evidence.combine(...)` of them. A test refuses `Level` and a direct `Evidence(...)` call in that file, the rule `backend.py` already follows. Rejected: a naming convention (`EVIDENCE` is read, `WRITE_EVIDENCE` is write): most constants are not about a file kind at all, and only `pcb` and `wks` follow it today. Rejected: a decorator on each reader and writer: the matrix would be spread over 60 files and built as a side effect of imports.

3. **The matrix stands beside the capability report.** `MatrixRow` is a new type and `result.matrix` a new key. Rejected: a `matrix` field of `CapabilityReport`: the living requirement fixes its eight keys, and c0043 already holds MODIFIED deltas of the two `capabilities` requirements that list backends, so a third change in that chain would have to be re-based twice.

4. **Rows come from packages, not from registered backends.** `altium` and `specctra` are not registered `Backend`s: their writers are reached through `build --target altium` and through the routing plug-in. They still read and write files, and their rows are the ones a user most needs (experimental writers, an interchange format). `fenolite.backends.matrix.packages()` walks the sub-packages of `fenolite.backends`. When c0043 registers the Altium backend, its rows are already there and gain `read` cells. Rejected: rows only for `registry.all_backends()`.

5. **Cells are labels in JSON; ids are merged per row.** `capabilities` is the first call of every agent session, so the row stays small: five labels or `null`, and `verified_by`. Rejected: `{level, oracle, hypotheses}` per cell: five objects per row for a detail the page gives.

6. **`verified_by` holds hypothesis ids.** An id leads to the statement, the settling test, the tool versions and the result, which is everything "verified by" can mean. The constants hold nothing else: tool versions live in the level text of the register (`KICAD-VERIFIED (9.0.x, 10.0.x)`), which the page prints next to each id. Rejected: a list of tool names: it would be a second, hand-kept statement of what the register says.

7. **`experimental` is declared per operation.** c0043 will put stable readers next to experimental writers of the same Altium kinds, so a flag per row would be wrong on its first day. It is declared, not derived: `INFERRED` is not experimental, and the plan allows `UNVERIFIED` only inside experimental features, which `problems()` enforces for cells.

8. **Round-trip cells need a test, and take the constant of the module that implements them.** For boards that is the reader's constant, which the `roundtrip` stage already reports (`checks/roundtrip.py` passes `validation.read.evidence`). `roundtrip_modified` of a board is the combination of reading and writing, which is the capability report's evidence. For every other kind the audit sets a round-trip cell only when a test of the repository proves the property for that kind, and names the test in the pull request; otherwise the cell stays `None`. The matrix therefore understates rather than overstates.

9. **`report_problems` moves into `fenolite.verify`.** The tool and two test modules need it. It uses only `Evidence`, `strength` and `HypothesisRow`, so the package's import rule holds. The capability test imports it and keeps its scenarios.

10. **The page is generated by a tool with `--check`, and a unit test detects drift**, the pattern of `tools/gen_token_docs.py` and `tests/unit/backends/kicad/test_token_docs.py`. The page joins only the level text of each id, so a register edit that changes a result or a date does not make the page stale. Rejected: rendering the page only when documentation is built: nothing would fail when it is stale.

11. **The guard covers `backends/` only**, as the plan says. `checks`, `lens`, `exports` and the routing plug-ins hold constants too; extending the guard to them is an open question, not part of this change.

12. **Changes in flight.** c0039 to c0043 (Altium readers) and c0060 to c0064 add modules under `backends/`. Whichever lands second declares: if this change lands first, their modules meet the guard, whose message says which of the three forms is missing; if they land first, the audit of task 3 covers them. No spec of those changes needs a re-base.

## Files and public API

| file | content |
|---|---|
| `src/fenolite/backends/base.py` | `MATRIX_OPERATIONS`; `MatrixRow` with `verified_by()` and `to_json()` |
| `src/fenolite/backends/matrix.py` (new) | `packages()`, `rows()`, `ModuleClaim`, `module_claims(package)`, `problems(packages=None)` |
| `src/fenolite/backends/{kicad,altium,specctra}/claims.py` (new) | `MATRIX: tuple[MatrixRow, ...]` |
| `src/fenolite/backends/*/*.py` | one declaration in each module that has none (33 on 2026-10-05) |
| `src/fenolite/verify/evidence.py`, `verify/__init__.py` | `report_problems(evidence, rows)` |
| `src/fenolite/cli/cmd_capabilities.py` | `result.matrix` |
| `src/fenolite/cli/cmd_inspect.py` | `HEADER_EVIDENCE` becomes `versions.EVIDENCE` (same value) |
| `tools/gen_evidence_matrix.py` (new) | `render() -> str`, `main()` with `--check` |
| `docs/evidence/matrix.md` (new, generated) | the page |
| `docs/cli-contract.md`, `docs/evidence/README.md`, `tools/README.md` | `result.matrix`; the page and its generator |
| `tests/unit/backends/test_matrix_row.py`, `tests/unit/backends/test_evidence_declared.py`, `tests/unit/test_evidence_register.py`, `tests/unit/test_evidence_matrix_page.py`, `tests/unit/cli/test_capabilities_matrix.py` (new) | the scenarios |

**Starting point of the audit** (task 3 confirms each line against the module and the register):

| module | declaration |
|---|---|
| `kicad.versions` | constant, the value `cmd_inspect.HEADER_EVIDENCE` holds today; it is the `detect` cell |
| `kicad.sexpr`, `kicad.libs` | constants over the `H-K-SEXPR-*` and `H-K-LIB-*` rows they depend on |
| `kicad._pcbwrite`, `layers`, `roundtrip`, `slots`, `zones` | see `pcb` |
| `kicad._fpmap` | see `mod`, `pcb` |
| `kicad._libread` | see `mod`, `sym` |
| `kicad._json` | see `pro` |
| `kicad.rulemap` | see `dru` |
| `kicad.copperrules` | see `dru`, `pro` |
| `kicad.triad` | see `dru`, `pcb`, `pro` |
| `kicad.canary`, `projectset` | see `oracle` |
| `kicad.cli` | see `helpmatrix` |
| `kicad.ipcd356` | see `padnets` |
| `kicad.backend`, `liberrors`, `proerrors`, `libcache` | none |
| `altium.ascii` | constant over the row it names |
| `altium.altsym` | see `schlib` |
| `altium.cfb` | see `binary` |
| `altium.docboard` | see `pcbdoc` |
| `altium.libboard` | see `pcblib` |
| `altium.layout`, `prjpcb`, `schdoc`, `symbols` | see `project` |
| `specctra.lexer` | see `dsn` |
| `specctra.ses` | constant over the three rows its docstring names |

**Starting rows.** `kicad`: `kicad_pcb` (fixed by the spec), `kicad_mod`, `kicad_sym`, `kicad_wks`, `kicad_dru`, `kicad_pro`, and `kicad_sch` once `backends/kicad/sch.py` exists. `kicad_sym` has a writer since c0058 (`sym.write_symbol_library`, for the symbols a design authors), which declares no constant, names no hypothesis and is not in `write_kinds`. The audit gives `sym.py` a `WRITE_EVIDENCE` of level `UNVERIFIED`, the level of a writer with no row behind it, and lists the `write` cell of `kicad_sym` as experimental, so `write_kinds` stays as it is. The cell leaves `experimental` when a change registers a row for the writer, as c0061 does with the schematic. `altium`: one row per write kind of the two experimental features. `specctra`: `specctra_dsn`, `specctra_ses`.

## Sources registered by this change

None. No format fact and no tool behaviour is added. S-0355 to S-0359 stay unused.

## Hypotheses registered by this change

None. The matrix repeats levels declared by modules and settles nothing. Ids used in tests without changing their level: `H-K-PCB-READ`, `H-K-PCB-WRITE`, `H-K-LIB-READ`, `H-K-WKS-CORNER`, `H-K-TOK-CONSTANTS`.

## Evidence level per behaviour (before merge)

| behaviour | level required | proof |
|---|---|---|
| a cell equals a module constant | mechanical | `tests/unit/backends/test_evidence_declared.py` |
| every backend module declares | mechanical | the same test, `-k live` |
| declarations agree with the register | mechanical | `tests/unit/test_evidence_register.py` |
| `result.matrix` equals `rows()` | mechanical | `tests/unit/cli/test_capabilities_matrix.py` |
| the page is current and repeatable | mechanical | `tests/unit/test_evidence_matrix_page.py` |

## Budget (5 days)

| part | days |
|---|---|
| `MatrixRow`, collector, markers, `problems()` | 1.25 |
| audit of the KiCad modules and rows | 1.0 |
| audit of the Altium, Specctra and v0.2a modules | 0.5 |
| register agreement, `report_problems` moved | 0.5 |
| `capabilities` and the contract page | 0.5 |
| generator, page, drift test | 0.75 |
| closing | 0.5 |

Cut order: first the "Modules" section of the page, then its "Hypotheses" section. The declaration guard, the register agreement and `result.matrix` are never cut: they are the change.

## Risks / Trade-offs

- **A marker hides a claim.** `# evidence: none` is one line. Mitigation: the page lists every module with its marker and reason, and a new marker makes the page stale, so it shows in the diff of the pull request that adds it.
- **A cell placed on the wrong constant.** Mitigation: a cell cannot be stronger than the module's own constant, the register bounds the constant, and a round-trip cell needs a named test (Decision 8).
- **The matrix reads weaker than the truth.** Most KiCad cells are `INFERRED` although their rows are `KICAD-VERIFIED`, because a constant states what holds for any file. That is the meaning the capability report already has; the page puts the register level next to each id so both facts are visible.
- **`capabilities` imports more.** `claims.py` imports the modules that own constants. Mitigation: the import happens inside `_run`; task 5.1 records the time of `fenolite capabilities --no-tools` before and after in the pull request.
- **The guard stops a parallel branch.** Intended. The message names the module and the three forms, and the fix is one line.

## Migration Plan

Additive. `result.matrix` is a new key of a free-form `result`, so `schemas/fenolite.envelope.v0.json` does not change. `report_problems` changes its import path for one test module. No file Fenolite writes changes. If the change is reverted, the declarations stay harmless: constants are plain values and markers are comments.

## Open Questions

- **Library tables.** `libs.write_lib_table` writes `fp-lib-table` and `sym-lib-table`, which `write_kinds` does not list. Default: the audit adds the row `kicad_lib_table` and the kind to `write_kinds`, as "Write capability fields" allows ("later writers add their kinds to the same tuple"), and updates the example in `docs/cli-contract.md`.
- **Guard outside `backends/`.** Default: not in v0.2a; the page already lists what is declared there only for backends.
- **A `tested` level per row.** The weakest register level of a row's ids would say what tests covered. It needs the register at run time. Default: page only.
- **Version dimension.** Default: v1.0, with the conformance matrix.

## Implementation notes (2026-10-05)

The change was implemented on `origin/dev` while c0061 (schematic writer) and c0065 were still being
written, so the guard lands before their modules. This section records what the audit found, what the
spec had wrong about the code, and what stays open.

### Corrections to the spec

1. **`altium` is a registered backend.** Decision 4 was written when only `kicad` was registered. Since
   c0043 `registry.all_backends()` gives `altium` with six read kinds, so "Evidence matrix rows" asks for
   `detect` and `read` on those rows. `read` is `Evidence.combine(<reader constant>, import_evidence.EVIDENCE)`:
   the backend returns the import's evidence for every read, and the reader's ids are worth listing.
   `detect` is `import_evidence.EVIDENCE`, the evidence of the backend's report, whose operations are
   `detect` and `read`. No register row is about detection by suffix alone (see "Not settled").
2. **A constant is any module-level `Evidence` assigned in the module**, not only `EVIDENCE` and
   `<NAME>_EVIDENCE`: `altium/read/cfb.py` names its constants `EVIDENCE_V3` and `EVIDENCE_V4`
   (`altium-compound-reader` fixes those names). A rule by name would have let them, and any later
   constant with an unusual name, escape the register check. A name the module only imports
   (`adapter/evidence.py` re-exports `EVIDENCE`) is not a declaration: the module carries a `see` marker.
3. **`__init__.py` may hold constants.** `altium/read/sch/__init__.py` assigns `EVIDENCE`. An `__init__`
   need not declare, but one that assigns constants is listed under its package's name (`read.sch`) and
   can be named by `see`.
4. **`packages()` returns dotted names** (`fenolite.backends.kicad`), the form `module_claims` and
   `problems` take, so the functions compose and the tests can pass a temporary package.
5. **`read.sch.EVIDENCE` named a refuted row.** `H-A-RD-SCH-TEXT` is refuted and superseded by
   `H-A-RD-SCH-TEXT-2`, and the living requirement asked the constant to name "every registered" id. A
   refuted row supports no claim, so `report_problems` rejects it. The constant now names the ids that are
   not refuted (`HYPOTHESES` still lists all, `REFUTED` the refuted ones); its level stays `INFERRED`.
   `altium-schematic-reader`, "Schematic reader entry points", is MODIFIED for this one sentence.
6. **Layering and import rules.** `backends/matrix.py` is a top-level module of `backends` (it imports
   `registry` inside a function), so `tests/unit/test_import_graph.py` lists it next to `base` and
   `registry`. `altium/claims.py` imports `fenolite.backends.base`, so
   `tests/unit/backends/altium/test_project.py::test_imports_only_core_and_model` skips it as it skips
   `backend.py`.
7. **The guard's message.** The requirement now fixes the text a failing guard prints
   (`matrix.failure_text`: the problems, then `matrix.HELP`), because modules of changes in flight will
   meet it without having read this change.
8. **The literal scenario** builds its `claims` module in a temporary package named `kicad` instead of
   copying the live file, so the test of task 2.2 does not depend on task 3.2.

### Decisions taken

- **Library tables (Open Questions).** The default was taken: row `kicad_lib_table`, `read` =
  `libs.EVIDENCE`, `write` = `libs.WRITE_EVIDENCE` (`INFERRED`, `H-K-BUILD-LIBTABLE`), and the kind is
  added to `CAPABILITIES.write_kinds`.
- **`kicad_sym` write.** `sym.WRITE_EVIDENCE` is `UNVERIFIED` with no id, and the cell is experimental,
  as the design said: no register row covers `sym.write_symbol_library`.
- **New constants are never above `INFERRED`.** Where the audit gave a module a constant
  (`kicad.versions`, `kicad.sexpr`, `kicad.libs`, `altium.ascii`, `altium.read.project`, `specctra.ses`),
  it names the rows the module's own text names, or every row of its family that is not refuted, at
  `INFERRED`. Several of those rows are stronger; raising the constant is the business of a change that
  shows the row covers an arbitrary file.
- **Round-trip cells and their tests** (Decision 8):

  | row | cell | constant | test |
  |---|---|---|---|
  | `kicad_pcb` | `roundtrip_exact`, `roundtrip_modified` | fixed by the spec | `tests/unit/backends/kicad/test_pcb_rebuild.py`, `tests/unit/backends/kicad/test_pcb_write.py` |
  | `kicad_sch` | `roundtrip_exact` | `sch.EVIDENCE` | `tests/unit/backends/kicad/test_sch_rebuild.py::test_roundtrip_of_every_fixture`, `tests/corpus/test_schematic_rt.py` |
  | `kicad_wks` | `roundtrip_exact` | `wks.EVIDENCE` | `tests/unit/backends/kicad/test_wks_read.py::test_rt1_on_authored_fixtures` |
  | `kicad_pro` | `roundtrip_exact` | `pro.EVIDENCE` | `tests/unit/backends/kicad/test_pro.py::test_fixture_round_trip` (byte-identical) |

  Left unset because no test proves "the whole content, modelled or not": `kicad_mod` (`test_mod_write.py::test_round_trip`
  compares the model and the opaque fragments with the header rows left out), `kicad_dru` (only the fixture
  `comments` is compared as text), `kicad_sym` and `kicad_lib_table` (no rebuild from slots), every
  `roundtrip_modified` but the board's, and every Altium and Specctra row (no file is read and written back).

### Audit

Every module of the three packages on `origin/dev` at `1cc5f93f`, with what it declares. "yes" marks a
declaration this change added; the other constants existed and keep their level. The same list, kept
current, is the "Modules" section of `docs/evidence/matrix.md`.

**`altium`**

| module | declaration | added by this change |
|---|---|---|
| `adapter.board` | see `import_evidence` | yes |
| `adapter.bodies` | see `import_evidence` | yes |
| `adapter.circuit` | see `import_evidence` | yes |
| `adapter.codes` | none: issue codes of the import and the counters of its census | yes |
| `adapter.connectivity` | see `import_evidence` | yes |
| `adapter.context` | see `import_evidence` | yes |
| `adapter.copper` | see `import_evidence` | yes |
| `adapter.evidence` | see `import_evidence` | yes |
| `adapter.ids` | see `import_evidence` | yes |
| `adapter.layers` | see `import_evidence` | yes |
| `adapter.library` | see `import_evidence` | yes |
| `adapter.netlist` | see `import_evidence` | yes |
| `adapter.pads` | see `import_evidence` | yes |
| `adapter.parts` | see `import_evidence` | yes |
| `adapter.pins` | see `import_evidence` | yes |
| `adapter.project` | see `import_evidence` | yes |
| `adapter.rules` | see `import_evidence` | yes |
| `adapter.units` | see `import_evidence` | yes |
| `altsym` | see `project`, `schlib` | yes |
| `ascii` | `EVIDENCE` INFERRED (1 ids) | yes |
| `backend` | none: the facade of the registered backend: every read returns the evidence of import_evidence | yes |
| `binary` | `EVIDENCE` INFERRED (5 ids) |  |
| `cfb` | see `binary`, `pcbdoc`, `pcblib`, `schlib` | yes |
| `docboard` | see `pcbdoc` | yes |
| `hierarchy` | `EVIDENCE` INFERRED (10 ids) |  |
| `import_evidence` | `EVIDENCE` INFERRED (20 ids) |  |
| `layout` | see `project` | yes |
| `libboard` | see `pcbdoc`, `pcblib` | yes |
| `pcbdoc` | `EVIDENCE` INFERRED (18 ids) |  |
| `pcblib` | `EVIDENCE` INFERRED (5 ids) |  |
| `pcbrecords` | `EVIDENCE` INFERRED (13 ids) |  |
| `prjpcb` | see `project` | yes |
| `project` | `EVIDENCE` INFERRED (10 ids) |  |
| `read.bodies` | see `import_evidence` | yes |
| `read.cfb` | `EVIDENCE_V3` CORPUS-VERIFIED (2 ids); `EVIDENCE_V4` INFERRED (3 ids) |  |
| `read.ini` | see `read.project` | yes |
| `read.outjob` | see `read.project` | yes |
| `read.pcb` | `EVIDENCE` CORPUS-VERIFIED (8 ids) |  |
| `read.pcblib` | `EVIDENCE` CORPUS-VERIFIED (4 ids) |  |
| `read.pcbprims` | see `read.pcb`, `read.pcblib` | yes |
| `read.pcbprops` | see `read.pcb`, `read.pcblib` | yes |
| `read.pcbstack` | see `read.pcb`, `read.pcblib` | yes |
| `read.project` | `EVIDENCE` INFERRED (11 ids) | yes |
| `read.proptext` | see `read.project` | yes |
| `read.rul` | see `read.project` | yes |
| `read.rules` | see `import_evidence`, `read.project` | yes |
| `read.sch` | `EVIDENCE` INFERRED (15 ids) | yes |
| `read.sch._build` | see `read.sch` | yes |
| `read.sch._container` | see `read.sch` | yes |
| `read.sch.census` | see `read.sch` | yes |
| `read.sch.document` | see `read.sch` | yes |
| `read.sch.framing` | see `read.sch` | yes |
| `read.sch.issues` | none: issue codes of the schematic reader and their collector | yes |
| `read.sch.pins` | see `read.sch` | yes |
| `read.sch.props` | see `read.sch` | yes |
| `read.sch.records` | see `read.sch` | yes |
| `read.sch.units` | see `read.sch` | yes |
| `read.schlib` | see `read.sch` | yes |
| `read.scope` | see `import_evidence`, `read.project` | yes |
| `read.sheet` | `EVIDENCE` INFERRED (8 ids) |  |
| `read.stackup` | see `read.project` | yes |
| `read.textfile` | see `read.project` | yes |
| `schdoc` | see `project` | yes |
| `schlib` | `EVIDENCE` INFERRED (6 ids) |  |
| `symbols` | see `project` | yes |

**`kicad`**

| module | declaration | added by this change |
|---|---|---|
| `_fpmap` | see `mod`, `pcb` | yes |
| `_json` | see `pro` | yes |
| `_libread` | see `mod`, `sym` | yes |
| `_pcbwrite` | see `pcb` | yes |
| `altium_import` | `IMPORT_EVIDENCE` INFERRED (2 ids) |  |
| `backend` | none: the facade of the registered backend: a read or a write returns its module's evidence | yes |
| `canary` | see `oracle` | yes |
| `cli` | see `altium_import`, `helpmatrix`, `oracle`, `plot` | yes |
| `copper` | `EVIDENCE` INFERRED (2 ids) |  |
| `copperrules` | see `dru`, `pro` | yes |
| `drc` | `EVIDENCE` KICAD-VERIFIED (1 ids) |  |
| `dru` | `EVIDENCE` KICAD-VERIFIED (4 ids) |  |
| `embed` | `EVIDENCE` KICAD-VERIFIED (3 ids) |  |
| `fields` | `EVIDENCE` INFERRED (3 ids) |  |
| `fill` | `EVIDENCE` KICAD-VERIFIED (3 ids) |  |
| `frame` | `EVIDENCE` INFERRED (5 ids) |  |
| `helpmatrix` | `EVIDENCE` KICAD-VERIFIED (1 ids) |  |
| `ipcd356` | see `padnets` | yes |
| `layers` | see `pcb` | yes |
| `libcache` | none: pins, hashes and stamps of the fetched libraries: no statement about a KiCad format or tool | yes |
| `liberrors` | none: issue codes and the error class of library reading | yes |
| `libs` | `EVIDENCE` INFERRED (6 ids); `WRITE_EVIDENCE` INFERRED (1 ids) | yes |
| `lowering` | `EVIDENCE` KICAD-VERIFIED (4 ids) |  |
| `mod` | `AUTHORING_EVIDENCE` INFERRED (1 ids); `EVIDENCE` INFERRED (1 ids) |  |
| `oracle` | `EVIDENCE` KICAD-VERIFIED (2 ids); `NORMALISE_EVIDENCE` KICAD-VERIFIED (1 ids); `RT2_EVIDENCE` KICAD-VERIFIED (1 ids) |  |
| `outline` | `EVIDENCE` INFERRED (2 ids) |  |
| `padnets` | `EVIDENCE` KICAD-VERIFIED (1 ids) |  |
| `pcb` | `EVIDENCE` INFERRED (1 ids); `WRITE_EVIDENCE` INFERRED (1 ids) |  |
| `plot` | `EVIDENCE` KICAD-VERIFIED (1 ids) |  |
| `pro` | `EVIDENCE` INFERRED (1 ids) |  |
| `proerrors` | none: issue codes of the project file | yes |
| `projectset` | see `oracle` | yes |
| `replace` | `EVIDENCE` KICAD-VERIFIED (1 ids) |  |
| `roundtrip` | see `pcb` | yes |
| `rulemap` | see `dru`, `lowering` | yes |
| `sch` | `EVIDENCE` CORPUS-VERIFIED (2 ids) |  |
| `sexpr` | `EVIDENCE` INFERRED (7 ids) | yes |
| `slots` | see `dru`, `mod`, `pcb`, `sch`, `sym`, `wks` | yes |
| `sym` | `EVIDENCE` INFERRED (1 ids); `WRITE_EVIDENCE` UNVERIFIED (0 ids) | yes |
| `triad` | see `dru`, `pcb`, `pro` | yes |
| `versions` | `EVIDENCE` INFERRED (1 ids) | yes |
| `wks` | `EVIDENCE` INFERRED (1 ids); `WRITE_EVIDENCE` INFERRED (1 ids) |  |
| `zones` | see `pcb` | yes |

**`specctra`**

| module | declaration | added by this change |
|---|---|---|
| `dsn` | `EVIDENCE` INFERRED (3 ids) |  |
| `lexer` | see `dsn`, `ses` | yes |
| `ses` | `EVIDENCE` INFERRED (3 ids) | yes |

### Not settled

These are declared at the lowest defensible level, or with the marker that fits the code as it is, but
the audit could not decide them from the register and the module text alone:

- **`altium` `detect`.** Detection is by file suffix (`backend.SUFFIXES`); no row states it. The cell
  repeats the report's evidence. A row of its own, or a `None` cell with a relaxed rule for `read_kinds`,
  would be more exact.
- **`altium.read.project` and the readers of c0042** (`read.ini`, `read.outjob`, `read.rul`, `read.rules`,
  `read.scope`, `read.stackup`, `read.textfile`, `read.proptext`). They had no constant. One constant in
  `read.project` names the eleven `H-A-RD-PRJ-*` rows that are not refuted, at `INFERRED`, and the others
  point at it. `read.outjob`, `read.rul` and `read.stackup` are readers of their own file kinds, which
  have no matrix row because no backend report lists them.
- **`altium.read.bodies`** (c0043) points at `import_evidence`, which names `H-A-IMP-BODY`; no
  `H-A-RD-*` row is about the body records themselves.
- **`kicad.libs`.** `EVIDENCE` names six `H-K-LIB-*` rows about tables and path variables; whether
  `H-K-LIB-NAME-STEM`, `H-K-LIB-SYMDIR` and `H-K-LIB-EXTENDS` belong to `libs`, `mod` or `sym` is open.
  `WRITE_EVIDENCE` names `H-K-BUILD-LIBTABLE`, which the build oracle settled for `fp-lib-table` only.
- **`kicad.sexpr`.** `EVIDENCE` names the seven `H-K-SEXPR-*` rows that are not refuted. The printers
  also rest on `H-K-FMT-*` rows, which `cmd_fmt` declares outside `backends/`.
- **`kicad.cli`** points at the four modules that run the tool (`altium_import`, `helpmatrix`, `oracle`,
  `plot`); the runner's own behaviour (copies, isolation) has rows (`H-K-CHECK-COPYSET`) that `oracle` names.
- **`kicad.libcache`** is marked `none`: it pins and hashes fetched libraries. If the pins count as a
  statement about the official libraries, it needs a constant.
- **Levels that existing constants claim for an arbitrary file.** `kicad.sch.EVIDENCE` is
  `CORPUS-VERIFIED` and `kicad.dru.EVIDENCE`, `kicad.lowering.EVIDENCE` are `KICAD-VERIFIED`, each equal
  to its weakest row, while `pcb`, `mod`, `sym`, `wks` and `pro` stay `INFERRED` below stronger rows
  "because a constant states what holds for any file". Both conventions pass the register rule, and the
  matrix repeats them unchanged; the maintainer may want one convention.
- **`altium.import_evidence.LEVELS`** repeats the level of twenty rows in code. A test keeps it equal to
  the register, so it is not a second source of truth for the matrix, but it is one for the module.
- **Size of `verified_by` on Altium rows.** The Altium constants name every row of their family, so a
  row lists 30 to 60 ids. Decision 5 wanted small rows; the ids are what the constants declare.
