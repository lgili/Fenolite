## Context

- **Readers.** c0039 reads compound files (`read.cfb.open_compound`, `CompoundFile.tree()`), c0040
  schematics and schematic libraries, c0041 PCB documents and libraries, c0042 the text files of a
  project. Each reader keeps every byte and can rebuild each stream from its records
  (`read.sch.encode_stream`, `PcbDocument.rebuild`, `to_bytes()`). c0043 maps the records into the
  neutral model and registers `AltiumBackend` for `detect` and `read`.
- **Commands today.** `fenolite check` finds a KiCad board with `resolve_board` and runs
  `checks.stages.run_checks` with a `Validator` and a `kicad-cli` oracle. `fenolite inspect` reads
  KiCad files; c0039 adds its `--streams` view and makes the summary refuse a compound file.
  `fenolite diff` does not exist, and no active change adds it. The roadmap lists `diff` under v0.2a
  (KiCad) and again under v0.3 ("`inspect`, `check` and `diff` on second-backend files").
- **Round trips today.** RT0 to RT2 are KiCad levels: tree identity, model → KiCad → model, and the
  same DRC violations before and after. Nothing equivalent exists for a compound file.
- **Writers.** `backends.altium.cfb.write_compound` writes version 3 without DIFAT sectors and refuses
  an empty storage. The document writers build from a design script; none writes from an imported
  model. An Altium build stores its model in `.fenolite/`, as a KiCad build does.
- **Units.** A binary PCB length is written in units of 2.54 nm (`pcbrecords.to_units`, S-0163,
  `H-A-UNIT`); angles are written with six decimals of a degree (`pcbdoc.degrees_text`).
- **Corpus.** c0039 to c0043 add the public rows (S-0170 to S-0176, S-0187, S-0188, S-0199, S-0200
  and their own ranges). One PCB document uses DIFAT sectors (154 FAT sectors), which
  `write_compound` cannot write. The folders of S-0174, S-0176 and S-0199 each hold a project file,
  schematic documents and one PCB document (folder listings read on 2026-10-03; no file downloaded).
- **Neighbours.** c0045 adds `fenolite equivalent` in `checks.equivalence`: a verdict per level, with
  tolerances, frames and exclusion lists. c0020 is archived; its text of "Check command input" is the
  living text.

## Goals / Non-Goals

**Goals**

- Define RT-A0, RT-A1 and RT-A2 so that each has one function, one verdict type and one stage.
- Let `check` and `inspect` accept Altium input with the envelope, exit codes and read-only rule
  they have for KiCad.
- Add `diff` once, for every backend, on the model; add the record view where only Altium has one.
- Measure the levels on every public row and on every file Fenolite writes.

**Non-Goals**

- Equivalence levels, tolerant comparison across backends, frames (c0045).
- Altium DRC, rule checks, an ERC beyond the three rules of `erc.lite` (v0.4).
- A writer from an imported model, DIFAT sectors or empty storages in `write_compound` (v0.4).
- A tree diff of KiCad files, `roundtrip`, `fmt`, `explain` (v0.2a).
- New format facts: this change reads no byte itself.

## Decisions

1. **`diff` is added in general, with one Altium-only view.**
   - The model view compares two `Design`s or two `Library`s whatever backend read them. Its engine
     (`checks.diff`) is backend-free, so restricting the command to Altium input would save nothing
     and v0.2a would have to widen it.
   - The records view needs a record codec per stream; only the Altium readers have one. For KiCad
     files it is refused with a hint. v0.2a adds the schematic kinds and KiCad's tree view.
   - *Rejected:* an Altium-only `diff` (a second command later, or a breaking widening); waiting for
     v0.2a (RT-A2 needs the engine now); putting the engine in c0045 (`equivalent` judges levels and
     hides differences by rule, a diff must list all of them).

2. **`diff` and `equivalent` stay apart.** `diff` is exact, exhaustive and exits 0; `equivalent` is a
   verdict with tolerances and exits 5. They share `checks.assignment_compare` and nothing else.
   `ModelScope` gives `diff_designs` a field list and a length tolerance only for RT-A2.
   - *Rejected:* `diff --level N` (two meanings of one command); exit 5 on a difference (a difference
     between two versions of a design is not a finding; an open question keeps the option).

3. **Matching in the model view.** Ids, native ids and provenance never take part: two readings of
   one design by two backends share none of them. Entities with a name are matched by it (`ref`,
   net name, `REF-PIN`); copper and graphics are matched by content, as `docs/design-model.md`
   already says the diff does. References by id are replaced by names first.
   - *Rejected:* matching by id (fails across backends and across `--seed` values); a geometric
     nearest-neighbour match for moved tracks (a moved track is one removal and one addition, which is
     exact and cheap; closeness is c0045's and level 5's subject).

4. **RT-A0 is a container copy, judged on streams.** Read with c0039, write with the existing
   writer, read again; equal paths and equal bytes per stream. Directory metadata and layout are
   left out: the writer writes zero CLSIDs and times by design, and c0039 records which public files
   carry them.
   - A file the writer cannot write is **not judged**, with a reason, and is counted. It is neither
     a pass nor a failure.
   - *Rejected:* byte identity of the whole file (the sector layout is free in MS-CFB, S-0145);
     adding DIFAT sectors to `write_compound` here (a writer feature with its own Altium evidence,
     v0.4); treating a text file as a trivial pass (a level that cannot fail proves nothing).

5. **RT-A1 uses the readers' own encoders.** c0040 to c0042 each promise that a stream is rebuilt
   from its records. RT-A1 turns that into one verdict per file for all six kinds: encode, read
   again, compare records. `bytes_equal` is reported beside the verdict. `roundtrip` holds a codec
   table and no parsing code.
   - Equal records with different bytes is a pass with an info: an encoder may normalise slack that
     no record holds. `H-A-VER-BYTES` states that this never happens on the corpus.
   - *Rejected:* a second set of encoders in this change (two encoders for one format drift apart);
     requiring equal bytes (that is the readers' identity requirement, tested there; RT-A1 is the
     level the roadmap row names); adding a model comparison to RT-A1 (equal records give an equal
     import; import determinism is c0043's).

6. **RT-A2 is judged on built input, inside a written scope.** The model of `.fenolite/` is compared
   with the reading of the files the build wrote, by `diff_designs` under `RT_A2_SCOPE`.
   - The writers are lossy by design (generic bodies, fixed text sizes, no schematic geometry in the
     model), so full equality cannot hold. The scope lists what is written; every field left out is
     documented with its reason, and a test compares the list with the model's dataclasses.
   - The tolerance is 2 nm: half a unit (1.27 nm) from the write plus half a nanometre from the read.
   - **Not judged for files Altium saved.** That needs a writer from an imported model. The
     requested "over the public corpus" is therefore met for RT-A0 and RT-A1 only; this is the one
     deviation from the row, stated in the proposal.
   - *Rejected:* an exact comparison (fails on rounding); a snapped comparison that repeats the
     writer's rounding (depends on the import's rounding mode at exact halves); RT-A2 on corpus
     libraries through `write_pcblib` and `write_schlib` (those writers refuse or drop content of
     arbitrary libraries, so the result would measure the refusals; see Open Questions).

7. **Document input has its own pipeline.** `run_checks` is built around one board, one `Validator`
   and one oracle. An Altium project is a set of documents with two independent readings and no
   oracle. `checks.documents.run_document_checks` reuses `StageResult`, `CheckReport`, `ran`,
   `skipped`, `erc_lite`, `model_netlist`, `board_netlist` and `compare`.
   - Stage names are shared where the stage means the same (`model.validate`, `erc.lite`,
     `netlist.assignment_compare`); the round trips get their own names (`roundtrip.rta0`, `.rta1`,
     `.rta2`), in the form of `roundtrip.rt2`.
   - `model.validate` reports only `Design.validate()` findings: `check.footprint-unresolved` would
     flag every component of a schematic read alone.
   - *Rejected:* a `ProjectSet` with a fake board for `run_checks` (every KiCad stage would need a
     skip); new names for the shared stages (an agent would learn two vocabularies).

8. **The comparison "against the project's own documents" is the partition compare of c0020.**
   Native input: (`schematic`, `pcb`). Built input: (`model`, `schematic`) and (`model`, `pcb`), the
   model being the hub. Elements only one side covers are coverage, not differences.
   - It overlaps level 2 of c0045 in arithmetic only (`compare` is shared). This stage is fixed to the
     documents of one project and has no option.
   - c0043's `H-A-IMP-NETLIST` judges the import's connectivity on the public project sets. This
     change runs the stage on the same sets and records the counts; it registers no second
     hypothesis for the same fact.

9. **`ProjectRead` gives two readings, not a merged design.** c0043's project read merges sheets and
   PCB and links components. A merged design cannot be compared with itself, so
   `read_documents` returns the schematic side (`adapter.import_circuit` over every sheet of the
   set) and the PCB side (`adapter.import_board`) apart. `import_project` is not used here.

10. **Protocols in `backends.base`, methods on c0043's backend.** `DocumentValidator` keeps `checks`
    and the CLI free of `backends.altium`. `Validator`, `Validation` and `RoundTrip` are not changed:
    `RoundTrip.level` is the literal `RT1` and three KiCad-shaped booleans.
    - *Rejected:* widening `RoundTrip` (a MODIFIED of "Validation operation" and of the KiCad
      backend for no gain).

11. **`erc.lite` runs on a schematic reading.** An Altium schematic has pin electrical types and No
    ERC directives (c0040, c0043), which a KiCad board read alone lacks. The rules are unchanged.
    `H-A-VER-ERC` bounds the claim.
    - `REMOVE_IN = (0, 2)` is kept. When v0.2a replaces the KiCad stage by `sch erc`, it must keep the
      three rules for document input; that change owns the edit (Open Questions).

12. **Three MODIFIED deltas, each minimal.**
    - `verification-loop` "Check command input": living text (c0020, archived) plus the bullet
      **Document input** and three scenarios.
    - `verification-loop` "ERC lite stage": text of c0036 (active) plus one sentence and one
      scenario.
    - `cli-contract` "Inspect command": text of c0039 (active); the summary now reads a file of a
      `DocumentValidator` backend, so c0039's scenario "Compound file without the stream view" is
      replaced by one with a compound file that no backend reads.
    - Everything else is ADDED. *Rejected:* ADDED requirements that contradict the three texts.

13. **Corpus use `rta`, by URL suffix.** The sibling changes tag their rows differently (`cfb`,
    `altium-sch`, `altium-pcbdoc`, …). One use chosen by suffix covers them all without depending
    on those names. Project sets are c0043's.

14. **No subprocess, no write.** Copies exist only in memory. The corpus tests copy project sets to
    pytest's temporary directory because `check` takes a path.

## Interfaces this change needs

| interface | from | used for | if absent |
|---|---|---|---|
| `read.cfb.open_compound`, `CompoundFile.tree()`, `.streams()`, `.as_dict()`, `CompoundError` | c0039 | RT-A0 | — (specified) |
| `read.sch.read_schematic`, `encode_stream`, `UnknownRecord`; `read.schlib.read_schlib`, `encode_stream` | c0040 | RT-A1, records view, summary counts | — (specified) |
| `read.pcb.read_pcbdoc`, `PcbDocument.rebuild`; `read.pcblib.read_pcblib`, `LibFootprint.rebuild`; `RawPrimitive` | c0041 | RT-A1, records view | — (specified) |
| the project reader with `to_bytes()` and its document list; `load_project` | c0042 | `document_set`, RT-A1 of `.PrjPcb` | — (specified) |
| `backend.AltiumBackend` with six read kinds named `altium_prjpcb`, `altium_schdoc_ascii`, `altium_schdoc_binary`, `altium_schlib`, `altium_pcbdoc`, `altium_pcblib` | c0043 | everything | task 1.4 takes c0043's kind names and corrects the spec text if they differ |
| `adapter.import_circuit(sheets, …)` and `adapter.import_board(doc, …)`, apart from `import_project` | c0043 | the two sides of `read_documents` | — (specified) |
| No ERC directives as `Circuit.no_connects`; pin electrical types as `Pin.etype` | c0043 | `erc.lite` | `H-A-VER-ERC` is recorded as refuted and the stage carries a warning |
| corpus requirement "Altium project sets" (use `altium-set:<nn>`) | c0043 | `test_altium_documents.py` | task 1.3 adds the missing sets from S-0245 to S-0247 |

c0041 and c0042 had no design and c0042 no spec when this change was written. At integration
(2026-10-03) every name of the table was checked against the specs of c0039 to c0043 and exists
there: c0039 owns the container API (`open_compound(data, *, file, limits, strict)`, methods, no
`issues` argument), `encode_stream` and `rebuild` are specified by c0040 and c0041, and `to_bytes()`
by c0042. Task 1.4 checks them again against the code.

**Names as implemented (task 1.4, 2026-10-05).** Checked against the code of c0039 to c0043 on the branch:

- `read.sch` is a package (`read/sch/`); `read_schematic`, `encode_stream` and `UnknownRecord` are its
  exports. A record of a binary stream is counted from the stream header, which is record 0.
- `read.pcb.read_pcbdoc(source, *, file, strict)` takes no `issues` list; the reader's issues are
  `PcbDocument.issues`. `PcbDocument.rebuild(storage)` takes the storage name, so the typed stream of a
  PCB document is `<storage>/Data`.
- `PcbLibrary` has no `rebuild`: only `LibFootprint.rebuild()` exists, and the library's other streams are
  kept whole in `PcbLibrary.storages`. The codec bullet of "Round-trip level RT-A1" was corrected.
- `RawPrimitive` is defined in `read.pcbprims`; `read.project.read_project(data)` returns the
  `ProjectFile` whose `to_bytes()` RT-A1 uses, and `load_project(path)` the document list.
- `adapter.import_circuit(sheets, *, options, issues)` takes `adapter.SheetInput` values and
  `adapter.import_board(doc, *, file, sha256, issues)` a `PcbDocument`; both exist apart from
  `import_project`.
- The six read kinds of `AltiumBackend` are the six of the table. c0043 lists five project sets
  (`altium-set:01` to `05`), so task 1.3 adds no row and S-0245 to S-0247 stay unused.

Corpus rows: c0039 owns the id scheme. A set that task 1.3 adds reuses every row that already
holds a URL (S-0199's document is `altium-third-party-pcbdoc-04`, S-0176's is `-02` and its
schematic `altium-third-party-schdoc-13`, S-0174's is `altium-third-party-pcbdoc-05`) and adds only
the missing files, with the next free numbers and without `cfb`, `altium-sch`, `altium-pcbdoc` or
`altium-text`.

## Files and public API

| File | Change | Public API |
|---|---|---|
| `src/fenolite/backends/base.py` | types | `DocumentRole`, `Document`, `DocumentSet`, `ProjectRead`, `ContainerRoundTrip`, `ModelScope`, `DocumentValidator` |
| `src/fenolite/backends/altium/docset.py` | new | `document_set(path) -> DocumentSet`, `ROLES`, `SUFFIX_KINDS` |
| `src/fenolite/backends/altium/roundtrip.py` | new | `rt_a0`, `rt_a1`, `diff_records`, `StreamCodec`, `CODECS`, `RT_A2_SCOPE`, `EVIDENCE_RT_A0`, `EVIDENCE_RT_A1` |
| `src/fenolite/backends/altium/backend.py` (c0043) | methods | `AltiumBackend.documents`, `read_documents`, `container_roundtrip`, `written_scope` |
| `src/fenolite/checks/documents.py` | new | `DOCUMENT_STAGES`, `run_document_checks` |
| `src/fenolite/checks/containers.py` | new | `container_stage(name, level, verdicts)` |
| `src/fenolite/checks/rta2.py` | new | `rta2_stage(model, read, scope)`, `CIRCUIT_KINDS` |
| `src/fenolite/checks/diff.py` | new | `Change`, `DiffReport`, `diff_designs`, `diff_libraries` |
| `src/fenolite/checks/codes.py` | rows | six codes in `ISSUE_CODES` |
| `src/fenolite/checks/stages.py` | type | `StageSkip` gains `no-schematic`, `single-source`, `not-judged` |
| `src/fenolite/cli/cmd_check.py` | dispatch | document input; `HELP` names both backends |
| `src/fenolite/cli/cmd_inspect.py` | dispatch | the Altium summary |
| `src/fenolite/cli/cmd_diff.py` | new | `COMMAND` (`diff`, `mutates=False`) |
| `src/fenolite/cli/_documents.py` | new | shared helpers: built detection, result of a document check, input loading for `diff` |
| `tests/unit/backends/altium/test_docset.py`, `test_roundtrip.py`, `test_backend_documents.py`, `test_diff_records.py` | new | tests |
| `tests/unit/checks/test_documents.py`, `test_containers.py`, `test_rta2.py`, `test_diff.py`; `fakes.py` | new, extended | tests, fake `DocumentValidator` |
| `tests/unit/cli/test_check_altium.py`, `test_diff_cmd.py`; `test_inspect_cmd.py`, `test_check_readonly.py`, `test_hermetic_examples.py` | new, extended | tests |
| `tests/unit/lens/test_altium_rta2.py` | new | RT-A2 on every example build |
| `tests/corpus/test_altium_roundtrip.py`, `test_altium_documents.py`; `test_manifest.py`; `manifest.toml` | new, extended | corpus runs, the use `rta` |
| `tests/unit/test_altium_roundtrip_page.py`, `test_altium_verification_docs.py`, `tests/unit/backends/test_base_types.py` | new, extended | tests |
| `docs/evidence/altium-roundtrip.md` | new | the three level tables |
| `docs/altium.md`, `docs/cli-contract.md`, `docs/roadmap.md`, `docs/hypotheses.md`, `docs/evidence/sources.md`, `src/fenolite/backends/altium/PROVENANCE.md` | sections, rows | — |

Layering: `checks.*` import `core`, `model`, `geometry`, `backends.base`. `backends.altium.docset` and
`roundtrip` import `core`, `model`, `backends.base` and their own package. The CLI reaches the
backend through `registry` and `DocumentValidator`. `tests/unit/test_import_graph.py` needs no
`ALLOWED` change. `pyproject.toml` `dependencies` stays empty.

## Sources registered by this change

| id | URL | licence | used for |
|---|---|---|---|
| S-0245 | the repository and commit of S-0199, folder `NG6011_Dot_projector/PCB/`: the project file and its three schematic documents | MIT (`LICENSE`) | a project set (project file, schematics, the PCB document of S-0199), only if c0043 lists fewer than three sets |
| S-0246 | the repository and commit of S-0176, folder `Hardware/miniFOC_driver/`: the project file and `foc.SchDoc` (Git LFS) | Apache-2.0 (`LICENSE`) | the same, second set |
| S-0247 | the repository and commit of S-0174: the project file and the schematic document (Git LFS) | BSD-2-Clause (`LICENSE.txt`) | the same, third set |

- Task 1.1 writes each row with its full URL, the commit and the SHA-256, through the fetch tool. A
  row is registered only when it is used; an id that c0040, c0042 or c0043 already registered for the
  same file is cited instead.
- Existing ids cited: S-0145 ([MS-CFB]: the sector layout is free), S-0163 and `H-A-UNIT` (the
  unit), S-0164 and S-0141 (components and pads are linked by designator), S-0170 to S-0176, S-0187,
  S-0188, S-0199 and S-0200 (the corpus files).
- S-0248 to S-0252 stay unused. No code is read or transcribed, and no file is committed.

## Hypotheses registered by this change

| id | statement | test | criterion |
|---|---|---|---|
| `H-A-VER-RTA0` | A copy through `open_compound` and `write_compound` keeps every storage path, stream path and stream byte of every public compound file the writer can write | `tests/corpus/test_altium_roundtrip.py` | every judged row passes; at least three repositories per compound kind |
| `H-A-VER-WRITER` | The only public files the writer cannot copy are those that need DIFAT sectors: no file holds an empty storage or a name the writer refuses | the same test | the count of `writer-refused` is 0 |
| `H-A-VER-RTA1` | Every typed stream of every public file gives equal records after encode and read | the same test | every row passes RT-A1 |
| `H-A-VER-BYTES` | The encoded bytes of every typed stream equal the bytes read | the same test | `bytes_equal == streams` on every row |
| `H-A-VER-RTA2` | Every Altium build of Fenolite's examples reads back equal to its built model inside `RT_A2_SCOPE`, within 2 nm | `tests/unit/lens/test_altium_rta2.py` | 0 differences on every example, both schematic forms |
| `H-A-VER-RTA2-2` | (registered at implementation, when the probe refuted `H-A-VER-RTA2`) Every Altium build reads back equal to its built model on what the built model holds; a board kind the built model does not hold is counted, not compared | the same test | 0 differences on every example, both schematic forms |
| `H-A-VER-ERC` | The three `erc.lite` rules on an imported schematic report no pin that carries a No ERC directive and no pin that a net lists | `tests/unit/checks/test_documents.py`, and the stage on the project sets | no `erc.lite.floating-pin` for a marked pin on any set; counts recorded |

All start at `INFERRED`. No id exists in `docs/hypotheses.md` or in an active change. `H-A-IMP-NETLIST`
(c0043) and the readers' identity rows (`H-A-RD-*`) are cited, not registered.

## Evidence level per behaviour (before merge)

| Behaviour | Level | Basis |
|---|---|---|
| RT-A0 on public files | `CORPUS-VERIFIED` once `H-A-VER-RTA0` holds; `INFERRED` before | corpus test, census |
| RT-A1 on public files | the readers' level combined with `H-A-VER-RTA1` | corpus test |
| RT-A0 and RT-A1 on Fenolite's files | Fenolite's own rule | unit tests on `tests/data/altium/` |
| RT-A2 | `INFERRED` (`H-A-VER-RTA2`) | example builds; never above `INFERRED`: one tool writes and reads |
| schematic against PCB on public sets | the lowest of both readings (`H-A-IMP-NETLIST`) | corpus test, counts in the page |
| `erc.lite` on a schematic reading | `INFERRED` (`H-K-CHECK-ERC`, `H-A-VER-ERC`) | unit tests, project sets |
| `diff`, model view | no label of its own; lowest of both inputs | unit tests of the matching rules |
| `diff`, records view | the reader's level | unit tests |
| `inspect` summary | the reading's evidence | unit tests against the test-only readers |
| unjudged files | counted per reason, never a pass | page table |

No behaviour claims `ORACLE-VERIFIED`, `KICAD-VERIFIED` or `ALTIUM-VERIFIED`.

## Size (design-days)

| work | design-days |
|---|---|
| 1. sources, hypotheses, provenance, pages, corpus use, name reconciliation | 0.75 |
| 2. base types, document sets, backend methods | 1.0 |
| 3. RT-A0, RT-A1, codecs | 1.25 |
| 4. document pipeline, container stage, codes, `erc.lite` | 1.5 |
| 5. model difference engine | 1.5 |
| 6. RT-A2 scope, stage, example builds | 1.5 |
| 7. `check` on Altium input | 1.0 |
| 8. `inspect` summary | 0.75 |
| 9. `diff` command and records view | 1.25 |
| 10. corpus runs and the evidence page | 1.0 |
| 11. documentation | 0.5 |
| 12. closing | 0.5 |
| **total** | **12.5** |

A size, not a calendar estimate. First cut: the records view (1.0). Second cut: the summary counts
of `inspect` beyond the model counts (0.25).

## Overlaps with other active changes

- **c0020 (archived on 2026-10-03).** Its text of "Check command input" and its "Assignment compare
  stage" are living text; nothing to order.
- **c0029 (copper check).** It MODIFIES "Stages added for findings and round trips" and ADDS
  "Copper clearance stage" and "Copper stage issue codes". This change touches none of them and does
  not change `STAGE_ORDER`. `copper.clearance` is not in `DOCUMENT_STAGES`; adding it for Altium
  boards needs an Altium `DesignRulesSource` and is left to v0.4. Both changes add rows to
  `ISSUE_CODES` and lines to `docs/cli-contract.md`; no order is needed between them.
- **c0015 and c0024.** They ADD the stages `zone.fill` and `render` to `STAGE_ORDER` only. No overlap.
- **c0036.** "ERC lite stage" is MODIFIED from its text: c0036 archives first.
- **c0039.** "Inspect command" is MODIFIED from its text: c0039 archives first.
- **c0043.** It MODIFIES "Backend registry", "Backends in capabilities" and "Experimental features in
  capabilities"; this change touches none and changes no capability report.
  - Its "Own files import to the model they were written from" compares nets, no-connect marks,
    `ref`, `value` and footprint name of the example builds in a test. RT-A2 is the same idea as a
    named level and a `check` stage, and adds placement, pads, copper and net classes. The two
    tests build the same examples; a failure of c0043's test also fails RT-A2.
  - Its "Altium project sets agree" is the gate on public projects (`H-A-IMP-NETLIST`, with
    `altium-import:known-diff`). This change runs the product stage on the same sets and only
    records the counts.
- **c0045.** It adds `checks.equivalence` and `cmd_equivalent.py`; no requirement name is shared.
  Either order works after c0043.
- **Requirement names.** None of this change's names exists in the living specs or in an active
  change (checked on 2026-10-03).
- **Archive order:** c0036, c0039, c0040, c0041, c0042, c0043, then c0044.

## Risks / Trade-offs

- **The sibling changes were unfinished when this was written.** Names may differ. → The interface
  table and task 1.4.
- **RT-A0 does not judge the largest public board.** → It is counted and named in the page; RT-A1
  judges it; the limit is lifted with the v0.4 writers.
- **RT-A2 finds defects in the writers or the import.** That is its purpose, and it may cost more
  than its line. → A defect is fixed in the owning module with a regression test; the scope is never
  shrunk to hide one.
- **RT-A2 proves consistency only.** → The label stays `INFERRED`, and the page says what it does
  not prove.
- **Public projects may be out of sync** (a schematic saved after the last PCB update). → The corpus
  test records differences per set and does not fail; c0043 judges them.
- **Content matching is quadratic in the worst case under a tolerance.** → The tolerance is used
  only for RT-A2 on Fenolite's own small builds; without a scope the match is by hash.
- **RT-A1 doubles the read time of a large board.** → Measured in task 10.1 and recorded; the stage
  can be left out with `--stages`.
- **A third pipeline entry point** (`run_document_checks` beside `run_checks`). → Shared result
  types and stage helpers; one dispatch point in `cmd_check`.

## Migration Plan

- Additive. KiCad input of `check` and `inspect` behaves as before, byte for byte in its output.
- The one visible change: `inspect` of an Altium file returned exit 2 after c0039 and returns a
  summary after this change.
- `diff` is a new command; `capabilities` lists it through command discovery.
- Rollback: remove `cmd_diff.py` and the dispatch branches; no stored data changes.

## Open Questions

1. **Should `diff` have `--fail-on-difference` (exit 5)?** Default: no; agents read `result.equal`.
2. **RT-A2 on public libraries through `write_pcblib` and `write_schlib`?** Default: not in this
   change; it would measure the writers' refusals. Revisit with the v0.4 writers.
3. **Lift the writer's limits for RT-A0 (DIFAT sectors, empty storages)?** Default: no; count the
   files. If `H-A-VER-WRITER` is refuted, the count is reported and the question returns.
4. **`erc.lite` after 0.2.** Default: v0.2a's change keeps the three rules for document input and
   moves `REMOVE_IN` to the KiCad use only.
5. **Should a built Altium project also run `copper.clearance` (c0029)?** Default: no; v0.4.
6. **Maintainer:** is "RT-A2 on Fenolite's own files only" acceptable for v0.3? Default: yes, as the
   proposal states.

## Implementation notes

Recorded while implementing (2026-10-05), on `origin/dev` with c0039 to c0043 and the batch c0060, c0064,
c0066, c0068, c0071 and c0073. Where a note says "spec amended", the delta in this folder was changed to
what the scenarios and the code show. The text above is kept as it was written; these notes win.

**What had changed under this design.**

1. **`diff` already existed (c0066).** `checks.diff` (`Change`, `DiffReport`, `diff_designs`,
   `diff_libraries`) and `cmd_diff.py` (model and tree views, the paged list `differences`) landed with
   c0066, which also added `roundtrip`, `fmt` and `explain`. Decision 1, the Non-goals about a tree diff
   and those commands, and the migration line "`diff` is a new command" are out of date.
   - The two ADDED requirements that repeated c0066's names were replaced. `verification-loop` now adds
     **"Model difference scope"** (the `scope` argument that c0066's "Model difference report" allows a
     later change to add), and `cli-contract` adds **"Diff of document inputs and the records view"**.
     Both name c0066's requirements and change nothing in them, so no archive order is needed between
     c0066 and this change. Tasks 5.1 and 9.1 extended the existing modules.
   - `--limit` is c0066's paging (`paged = "differences"`, default 200), not an option of the command.
2. **Three MODIFIED deltas, re-checked against the living specs.** "Check command input" and "ERC lite
   stage" (`verification-loop`) and "Inspect command" (`cli-contract`) start from the living text of
   2026-10-05 word for word; c0036 and c0039 are archived, so no order remains. c0062 (active) also
   modifies "ERC lite stage": the change that lands second re-bases on the first.
3. **Five project sets exist** (c0043, `altium-set:01` to `05`), so task 1.3 added no row and the source
   ids S-0245 to S-0247 stay unused. The use `rta` is on 65 rows.
4. **Two public PCB documents need DIFAT sectors**, not one (154 and 354 FAT sectors; the second is the
   heavy row).

**Additions to the protocol (spec amended, `backend-protocol`).**

5. **`ContainerRoundTrip.evidence`.** The design gave `run_document_checks` and `container_stage` no
   evidence argument and still wanted `checks` to name no hypothesis of a backend. A verdict therefore
   carries the evidence of its level and kind.
6. **`DocumentValidator.stage_evidence()`**, a fifth method: the evidence the backend adds to a stage
   (`H-A-VER-ERC`, `H-A-IMP-NETLIST`, `H-A-VER-RTA2-2`). `roundtrip.STAGE_EVIDENCE` holds it, at the
   levels of the register.
7. **`Change`, `ChangeKind` and `DiffReport` live in `backends.base`** and are re-exported by
   `checks.diff`: `diff_records` returns a `DiffReport`, and `backends.altium` may not import `checks`
   (`package-layering`).
8. Small additions: `ContainerLevel`; `DocumentSet.named` and `of_role`; a set refuses unsorted
   `documents` and `missing`.

**Round trips.**

9. **`PcbLibrary` has no `rebuild`**; only its footprints do. The codec bullet was corrected (task 1.4).
10. **RT-A1 reads again without the writer when it can.** When every encoded stream equals the bytes
    read, the file read again is the file itself; this is what lets the two files past the writer's limit
    be judged. A file whose encoded bytes differ and that the writer cannot write is not judged (the
    reason of RT-A0). Encoded streams that do not read are a failed verdict. Records are compared with
    `==`, two NaN values of one field counting as equal. Spec amended.
11. **`EVIDENCE_RT_A1` is a mapping per read kind** (the readers have different levels);
    `PROJECT_READ_EVIDENCE` names `H-A-RD-PRJ-INI`, because the project reader defines no constant.
12. **The writer package's import rules.** `tests/unit/backends/altium/test_project.py` forbids file
    access and other packages for every top-level module of `backends/altium` except `backend.py`;
    `docset.py` and `roundtrip.py` joined that exception (`READING_MODULES`), and `test_roundtrip.py`
    holds the rule for `roundtrip.py` (bytes only, no `open`, no `struct`). `roundtrip.py` uses no `math`,
    which another test of the package forbids.

**RT-A2: the probe refuted `H-A-VER-RTA2`.**

13. **The built model of an Altium build is the script's model.** Its board holds the outline and no
    footprint, pad, track, arc, via or zone; the build writes those from the placements, the library
    footprints and the copper source, which are not in the model. The KiCad build stores the board it
    wrote; the Altium build does not. 39 to 184 entities of each PCB reading therefore have no
    counterpart, and the claim "every scoped kind reads back equal" cannot be judged for them.
    - `H-A-VER-RTA2` is kept as refuted, with the successor `H-A-VER-RTA2-2`: the level holds for what
      the built model holds. Spec amended ("Round-trip level RT-A2", "Document check pipeline").
    - `rta2_stage` compares a board kind only when the built model holds an entity of it, and lists the
      others in `summary.not_in_model`. The scope keeps every field of the required list, so a build
      that stores its board makes those kinds compared without a change here.
    - **Today RT-A2 judges components, nets, no-connect marks and net class names.** It says nothing
      about footprints, pads and copper. This is the main shortfall against the proposal, which expected
      placement, pads and copper. Closing it needs the Altium build to store the board it writes: a change
      of the build of c0035 and c0038, not done here.
14. **Net classes go with the PCB reading.** A class is a record of the PCB document; a schematic holds
    none. `CIRCUIT_KINDS` is `component`, `net`, `no_connect`. Spec amended.
15. **One difference inside the scope, fixed in the build.** A component whose value is empty in the
    script was written with its symbol's name as the comment (both writers). The built model now stores
    that value (`lens.altium.with_written_values`); the golden files are unchanged, and a regression test
    holds it.

**The document pipeline (spec amended, `verification-loop`).**

16. `container_stage` takes `None` for a document whose reading was refused; a skipped container stage
    keeps its summary and infos. A refusal found only by `container_roundtrip` is an input issue too.
17. `model.validate` on native input without any reading is skipped with `not-judged` when nothing was
    refused (a library alone); `read-refused` would count as `UNVERIFIED` in the envelope for a file that
    reads. Its summary is keyed by side. `netlist.assignment_compare` on built input with an unreadable
    cache is skipped with `cache-unreadable`.
18. `checks.assignment_compare` gained the public names `net_names`, `pair_issues` and `pair_summary`
    (the strict type check refuses a private name across modules); nothing else of c0020 changed.

**Commands.**

19. **`check`.** A folder with a KiCad project or board and Altium files without exactly one project file
    stays KiCad input. `cli/_documents.py` holds the built detection that `cmd_check` had (`built_cache`).
20. **`inspect`.** The record counts of a schematic and the header's version come from the Altium readers,
    imported lazily in `cmd_inspect.py` as the stream view does; the model counts come from the backend's
    reading. The case of c0039's scenario in `test_inspect_streams.py` now uses a compound file that no
    backend reads.
21. **Records view.** Records are aligned by content (frame kind and payload, or bytes), because a
    record's index and offset change with its place and would report every record after an insertion.
    Past 4 000 000 cells the middle is aligned by `difflib`. Changes are in stream and record order.
    Spec amended.

**Corpus and levels (task 12.2).**

22. **`H-A-VER-RTA0` and `H-A-VER-RTA1` stay `INFERRED`.** Every judged row passes (57 of 65, and 65 of
    65), but the judged PCB libraries come from two repositories and the criterion asks for three per
    compound kind. `tests/corpus/test_altium_roundtrip.py` pins the count. `EVIDENCE_RT_A0` and
    `EVIDENCE_RT_A1` are unchanged.
23. **Confirmed, `CORPUS-VERIFIED`:** `H-A-VER-WRITER` (no row is `writer-refused`), `H-A-VER-BYTES` (450
    of 450 typed streams) and `H-A-VER-ERC` (five sets of five repositories).
24. **The project sets exit 5**: `model.validate` passes on `model.body-height` errors of the PCB readings
    (and `model.duplicate-ref` on set 02). They are findings of c0043's import on public files, recorded
    in the page and not judged here.
25. **CI.** The `kicad-10` job fetches the corpus by use; `rta` was added to its fetch step and to
    `ALTIUM_READER_USES`. c0043's test of the set rows now leaves `rta` out of the uses it counts.
26. **`fenolite explain`** has an entry for each of the six new codes.

**Rebased for landing (2026-10-05, on `origin/dev` at dcd9c04).**

27. The branch was replayed as one commit on a head that also holds the follow-up of c0066 (schematics in
    `diff` and `roundtrip`), c0045 (`equivalent`), c0069, c0074 and the archives of c0043 and c0045.
    - `checks/diff.py` keeps both: `diff_sheets` with its sheet kinds, and the scope and tolerance of
      `diff_designs`. `diff_libraries` and `diff_sheets` take no scope. `Change`, `ChangeKind` and
      `DiffReport` stay in `backends.base`; c0066's and c0045's code imports them from `checks.diff`,
      which re-exports them.
    - `cmd_diff.py` reads a KiCad schematic first, then a project folder of a document backend, then any
      file a backend reads; the three views are `model`, `tree` and `records`.
    - `checks/assignment_compare.py`: c0045 had made `net_names` public (and added `net_text`), so this
      change adds only `pair_issues` and `pair_summary`.
    - The three MODIFIED deltas were compared again with `openspec/specs/`: each still differs from the
      living text only by what this change adds. No file of c0043's or c0045's change folder was edited.

**Left open.**

- Tasks 12.1 and 12.3 need the full `make check`, which the coordinator runs once at landing;
  `make check-fast` (7104 passed) and the tests of every touched file ran here.
- RT-A2 for footprints, pads and copper (note 13), and a third repository of PCB libraries (note 22).
