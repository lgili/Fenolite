# altium-verification Specification

## Purpose
Verify Altium files without external tools: the document set that an input names, the round-trip levels RT-A0 (container), RT-A1 (records per stream) and RT-A2 (built model), `fenolite check` and `fenolite inspect` on Altium inputs, the records view of `fenolite diff`, and the evidence that each stage carries over the public corpus and the committed samples.

## Requirements

### Requirement: Altium document sets
`fenolite.backends.altium.docset.document_set(path: Path) -> DocumentSet` SHALL name the documents that an Altium input holds (`backend-protocol`, "Document sets and container round trips"), reading only the project file and the first eight bytes of each document.
- **Kinds and roles**, by suffix in any letter case: `.PrjPcb` is `altium_prjpcb` with role `project`; `.SchDoc` is `altium_schdoc_binary` when the file starts with the compound file signature and `altium_schdoc_ascii` otherwise, with role `schematic`; `.PcbDoc` is `altium_pcbdoc` with role `pcb`; `.SchLib` is `altium_schlib` with role `symbol-library`; `.PcbLib` is `altium_pcblib` with role `footprint-library`. `ROLES` MUST map each of the six read kinds of c0043's `AltiumBackend` to its role.
- **A document path** MUST give a set whose root is the file's folder and whose only document is that file; `project` is `None`, and `board` is the file when it is a PCB document.
- **A project file** MUST give the project file and every document that c0042's `read.project.read_project` lists for it, that has one of the five suffixes and that lies under the project's folder. Listed paths MUST be turned into POSIX names relative to that folder, with `\` read as a separator. A document's name MUST be spelled as the folder spells it (a listed name that differs only in letter case names the one file that matches), and a document listed twice is one document. A listed document that does not exist MUST go to `missing`; a listed path outside the folder, or of another suffix, MUST be left out.
- **A folder** MUST give the set of its only project file. A folder with no project file or with several MUST raise `ValueError` that names the candidates.
- **Board.** `board` MUST be the PCB document whose stem equals the project file's stem without letter case, else the first PCB document by name, else `None`.
- The function MUST NOT read a document beyond its first eight bytes, and MUST NOT write.

#### Scenario: Own sample project
- **WHEN** `uv run pytest tests/unit/backends/altium/test_docset.py -k blink` calls `document_set(Path("tests/data/altium/blink/blink.PrjPcb"))`
- **THEN** `project` is `blink.PrjPcb`, `board` is `blink.PcbDoc`, the documents are `blink.PcbDoc`, `blink.PcbLib`, `blink.PrjPcb`, `blink.SchDoc` and `blink.SchLib` with the roles `pcb`, `footprint-library`, `project`, `schematic` and `symbol-library`, and `missing` is empty

#### Scenario: ASCII and binary schematics told apart
- **WHEN** `document_set` runs on `tests/data/altium/sample/altium_sample.SchDoc` and on `tests/data/altium/sample/binary/altium_sample.SchDoc`
- **THEN** the kinds are `altium_schdoc_ascii` and `altium_schdoc_binary`

#### Scenario: Listed document absent
- **GIVEN** a copy of the blink project in `tmp_path` without `blink.PcbLib`
- **WHEN** `document_set` runs on the project file
- **THEN** `missing` is `("blink.PcbLib",)` and the set holds four documents

#### Scenario: Folder with two project files
- **GIVEN** a folder that holds `a.PrjPcb` and `b.PrjPcb`
- **WHEN** `document_set(folder)` runs
- **THEN** it raises `ValueError` naming both files

### Requirement: Round-trip level RT-A0
`fenolite.backends.altium.roundtrip.rt_a0(data: bytes, *, kind: str, file: str = "") -> ContainerRoundTrip` SHALL judge whether a copy of a compound file keeps every storage and every stream: the level RT-A0.
- The file MUST be read with `read.cfb.open_compound` (c0039), written with `cfb.write_compound(compound.tree())` and read again. The level passes when both readings have the same storage paths and stream paths, with the stored spelling, and every stream has the same bytes.
- `streams` MUST be the number of streams of the first reading. `different` MUST hold, sorted, every path that is missing on one side or whose bytes differ, and `difference` the first of them.
- CLSIDs, state bits, times, the sector size, the sector layout and free sectors are not part of the level. The copy MUST NOT be written to disk.
- **Not judged.** `cfb.CompoundTooLarge` MUST give `judged=False` with reason `too-large`. Any other `ValueError` of the writer (an empty storage, a name it does not write) MUST give reason `writer-refused`. A kind that is not a compound file (`altium_schdoc_ascii`, `altium_prjpcb`) MUST give reason `not-a-container`.
- A `CompoundError` of the reader MUST be raised unchanged.
- `EVIDENCE_RT_A0` MUST be `INFERRED` with `H-A-VER-RTA0` until that row is confirmed over the corpus, then `CORPUS-VERIFIED`. Every verdict carries it as `ContainerRoundTrip.evidence`.

#### Scenario: Own files pass
- **WHEN** `uv run pytest tests/unit/backends/altium/test_roundtrip.py -k rt_a0_own` runs `rt_a0` on every compound file under `tests/data/altium/`
- **THEN** every verdict is judged and passed, with `streams` equal to the number of streams that `open_compound` lists

#### Scenario: A lost stream is located
- **GIVEN** `cfb.write_compound` patched to drop the stream `Nets6/Data`
- **WHEN** `rt_a0` runs on `tests/data/altium/blink/blink.PcbDoc`
- **THEN** the verdict is judged and not passed, and `different` and `difference` name `Nets6/Data`

#### Scenario: File past the writer's limit
- **GIVEN** a compound file built by `tests/_cfb_build.py` whose FAT needs 240 sectors
- **WHEN** `rt_a0` runs on it
- **THEN** the verdict has `judged=False` and reason `too-large`

#### Scenario: Text file
- **WHEN** `rt_a0` runs on the bytes of `tests/data/altium/blink/blink.PrjPcb` with `kind="altium_prjpcb"`
- **THEN** the verdict has `judged=False` and reason `not-a-container`

### Requirement: Round-trip level RT-A1
`roundtrip.rt_a1(data: bytes, *, kind: str, file: str = "") -> ContainerRoundTrip` SHALL judge whether reading a file and encoding what was read gives equal records in every stream: the level RT-A1.
- **Codecs.** `roundtrip.CODECS` MUST map each of the six read kinds to a `StreamCodec(read, streams, encode, records, opaque)` built only from the public surface of the readers of c0040 to c0042: `read.sch.read_schematic` with `read.sch.encode_stream`, `read.schlib.read_schlib` with `read.schlib.encode_stream`, `read.pcb.read_pcbdoc` with `PcbDocument.rebuild`, `read.pcblib.read_pcblib` with each footprint's `rebuild` (a library has no `rebuild` of its own: its other streams are kept whole), and the project reader's `to_bytes()`. `roundtrip` MUST NOT parse a record itself.
- **Verdict.** For every stream that the reader types, the stream MUST be encoded from the first reading, the encoded streams MUST be read again with the same reader, and the two record sequences of the stream MUST be equal: the same number of records, and each record equal with every key spelling, key order, raw value and kept byte. The ASCII schematic and the project file count as one stream, named `ascii` and `text`. The records of a binary stream are counted from its header, which is record 0. When every encoded stream equals the bytes read, the file to read again is the file itself; otherwise it is the file with its typed streams replaced, written by `cfb.write_compound` for a compound kind. Encoded streams that the reader refuses are a failed verdict whose `different` names the streams whose bytes changed.
- `streams` MUST be the number of typed streams, `records` the number of records compared, and `bytes_equal` the number of typed streams whose encoded bytes equal the bytes read. `different` MUST hold the paths of the streams whose records differ, and `difference` MUST be `<stream>#<index>` of the first differing record of the first such stream, or `<stream>` when the counts differ.
- `opaque_count` MUST be the number of records that the reader keeps without a typed class (`UnknownRecord`, `RawPrimitive`), which `StreamCodec.opaque` gives, plus the number of streams of the container that the reader does not type.
- The level is judged for a file that reads, with one exception: when a stream's encoded bytes differ from the bytes read and the compound writer cannot write the file that holds them, the verdict is not judged, with the reason of `rt_a0` (`too-large` or `writer-refused`). A reader's `FormatError` on the file itself MUST be raised unchanged. Nothing MUST be written to disk.
- `EVIDENCE_RT_A1` MUST map each read kind to `Evidence.combine` of its reader's evidence (`roundtrip.READER_EVIDENCE`) and `INFERRED` with `H-A-VER-RTA1`, until that row is confirmed over the corpus. Every verdict carries the evidence of its kind.

#### Scenario: Own files pass with equal bytes
- **WHEN** `uv run pytest tests/unit/backends/altium/test_roundtrip.py -k rt_a1_own` runs `rt_a1` on every file under `tests/data/altium/` whose suffix is one of the five
- **THEN** every verdict is passed, `bytes_equal` equals `streams`, and `records` is at least 1

#### Scenario: Encoder that changes a record
- **GIVEN** the codec of `altium_schdoc_binary` patched so that `encode` drops the last field of record 3 of `FileHeader`
- **WHEN** `rt_a1` runs on `tests/data/altium/sample/binary/altium_sample.SchDoc`
- **THEN** the verdict is not passed, `different` is `("FileHeader",)` and `difference` is `FileHeader#3`

#### Scenario: Encoder that only changes bytes
- **GIVEN** a fake codec whose `encode` returns bytes that differ from the stream and that read back to equal records
- **WHEN** `rt_a1` runs with it
- **THEN** the verdict is passed and `bytes_equal` is `streams - 1`

#### Scenario: Unknown records are counted
- **GIVEN** an authored binary schematic with one record of an id that `read.sch` does not type
- **WHEN** `rt_a1` runs on it
- **THEN** the verdict is passed and `opaque_count` is 1

### Requirement: Round-trip level RT-A2
The level RT-A2 SHALL hold for a built Altium project when the model that the build stored in `.fenolite/` equals the reading of the documents the build wrote, inside the scope of what the writers write. It is judged by the `roundtrip.rta2` stage (`verification-loop`, "Document check pipeline") with `roundtrip.RT_A2_SCOPE`, which `AltiumBackend.written_scope()` returns.
- **What the built model holds.** The model that an Altium build stores is the model of the script with the board that the build wrote (`altium-build`, "Stored board of an Altium build"): one footprint per placed component with the pads that are written, and the tracks, arcs, vias and zones of the PCB document. The circuit kinds `component`, `net` and `no_connect` are compared with the schematic reading; `netclass`, a record of the PCB document, and the board kinds are compared with the PCB reading. Every kind of the scope is compared ("RT-A2 on a written model"): an entity that only the reading holds, or only the model, is a difference. The PCB reading is first moved into the frame of the built model (`backend-protocol`, "Model writers").
- **Written values.** The build MUST store in the built model the value that its documents hold: a component whose value is empty in the script is written with its symbol's name as the comment, and `lens.altium.with_written_values` gives the built model that value.
- `RT_A2_SCOPE.length_tolerance` MUST be 2: a length is written in units of 2.54 nm, so the written value is at most 1.27 nm from the model's, and its reading is rounded to a whole nanometre. Angles are written with six decimals of a degree and MUST be equal.
- `RT_A2_SCOPE.fields` MUST hold at least: `component` with `ref` and `value`; `net` with `name` and `members`; `no_connect`; `footprint` with `position`, `rotation` and `side`; `pad` with `number`, `net_id`, `position` and `size`; `track` with `start`, `end`, `width`, `layer` and `net_id`; `arc` with `start`, `mid`, `end`, `width`, `layer` and `net_id`; `via` with `position`, `diameter`, `drill` and `net_id`; `zone` with `outline`, `layers` and `net_id`; `netclass` with `name`.
- Every field of those kinds that the scope leaves out MUST be listed in `docs/altium.md`, section "Round trips", with the reason: the writer does not write it, the writer writes a fixed value, or the reader maps it elsewhere. A field MUST NOT be removed from the list above to make a sample pass; a difference inside the scope is a defect of a writer or of the import.
- RT-A2 is not judged for a file that no Fenolite build wrote: the stage is then skipped with reason `native-input`. The level of such a file is RT-A3 ("Round-trip level RT-A3").
- The stage's evidence MUST be `INFERRED` with `H-A-VER-RTA2-3` (`roundtrip.EVIDENCE_RT_A2`) combined with the readings' evidence: Fenolite's writers are read by Fenolite's readers, so the level proves consistency, not that Altium reads the files. `H-A-VER-RTA2`, which claimed the level for every scoped kind when no built model held a footprint or copper, and `H-A-VER-RTA2-2`, which bounded the claim to what the built model held, are refuted rows; `H-A-VER-RTA2-3` is their successor.

#### Scenario: Built blink holds RT-A2
- **GIVEN** `examples/blink_2layer/design.py` built with `fenolite build … --target altium --confirm` into `tmp_path`
- **WHEN** `uv run pytest tests/unit/lens/test_altium_rta2.py -k blink` runs `fenolite check <dir> --stages roundtrip.rta2 --json`
- **THEN** the exit code is 0, the stage has status `ok`, `summary.holds` is `true`, `summary.differences` is 0, `summary.compared` is `component`, `net` and `no_connect` for the schematic and every other kind of `RT_A2_SCOPE` for the PCB document, the summary holds no `not_in_model`, and the stored board holds 3 footprints with 36 pads

#### Scenario: Every own example holds RT-A2
- **WHEN** `uv run pytest tests/unit/lens/test_altium_rta2.py` builds every script under `examples/` that the Altium build accepts, in the binary and in the ASCII form (the script that needs the official KiCad libraries only where they are installed), and one with module sheets
- **THEN** each build holds RT-A2 with 0 differences, and a script that the test does not name fails it

#### Scenario: Empty value is stored as written
- **WHEN** `uv run pytest tests/unit/lens/test_altium_rta2.py -k written_value` builds `examples/altium_sample/design.py`, whose `J1` has no value
- **THEN** the built model holds the value `HDR2` for `J1`, the name of its symbol, and no component of the built model has an empty value

#### Scenario: A changed document is caught
- **GIVEN** the built blink whose `.fenolite/circuit.json` gives `R1` another value by a text edit
- **WHEN** `fenolite check <dir> --stages roundtrip.rta2 --json` runs
- **THEN** the exit code is 5 and the issues hold one `check.rta2-failed` error whose `where` is `schematic:/component/R1/value`

#### Scenario: Left-out fields are documented
- **WHEN** `uv run pytest tests/unit/backends/altium/test_roundtrip.py -k scope_documented` compares `RT_A2_SCOPE` with the model's dataclass fields and with `docs/altium.md`
- **THEN** every field of a scoped kind is either in the scope or named in the section "Round trips"

### Requirement: Altium backend validates documents
c0043's `fenolite.backends.altium.backend.AltiumBackend` SHALL satisfy `DocumentValidator`.
- `documents(path)` MUST return `docset.document_set(path)`.
- `read_documents(documents)` MUST give as `schematic` a design whose circuit is c0043's `adapter.import_circuit` of every schematic document of the set, with the nets of the whole set and no board, and as `pcb` the design of `adapter.import_board` for the document `documents.board`. Neither side MAY hold content merged from the other. A document whose reading raises `FormatError` MUST be recorded in `errors` under its name, and its side MUST be `None`.
- `container_roundtrip(path, level)` MUST return `rt_a0` or `rt_a1` of the file's bytes, with the kind that `document_set` gives the file.
- `written_scope()` MUST return `RT_A2_SCOPE`.
- `stage_evidence()` MUST return `roundtrip.STAGE_EVIDENCE`: `H-A-VER-ERC` for `erc.lite`, c0043's `H-A-IMP-NETLIST` for `netlist.assignment_compare` and `H-A-VER-RTA2-2` for `roundtrip.rta2`, each at the level of its row in `docs/hypotheses.md`.
- The backend's `read`, `detect` and capability report are unchanged, and no method MAY write a file or run a subprocess. `backend.py` MUST hold the typed function `document_validator()` that returns an `AltiumBackend` as `DocumentValidator`, which `pyright` checks.
- With a project file, the schematic documents MUST be read in the order the project file lists them, and the net options MUST be those of the project file.

#### Scenario: Protocol satisfied
- **WHEN** `uv run pytest tests/unit/backends/altium/test_backend_documents.py -k protocol` and `uv run pyright src` run
- **THEN** `isinstance(registry.for_path(Path("x.PrjPcb")), DocumentValidator)` is true, and pyright reports no error

#### Scenario: Two readings of one project
- **WHEN** `read_documents` runs on the set of `tests/data/altium/blink/blink.PrjPcb`
- **THEN** `schematic.design.board` is `None`, `pcb.design.board` holds the three footprints of the sample, and `errors` is empty

#### Scenario: Refused document recorded
- **GIVEN** a copy of the blink project whose `blink.PcbDoc` is cut to 100 bytes
- **WHEN** `read_documents` runs
- **THEN** `pcb` is `None`, `errors` has the key `blink.PcbDoc` with a `FormatError`, and `schematic` is read

### Requirement: Check on Altium inputs
`fenolite check PATH` SHALL check an Altium document, project file or project folder as document input (`verification-loop`, "Check command input"), read-only and without any external tool.
- **Path.** A missing path MUST exit 3 with `FEN-3001`. A folder that holds Altium files, no KiCad project or board, and not exactly one project file MUST exit 2 with `FEN-2001` and a hint that lists the candidates.
- **Built or native.** The input MUST be built when `<root>/.fenolite/meta.json` or `<root>/.fenolite/build.json` exists, `<root>` being the set's root, and native otherwise. The built model MUST be loaded with `model.canonical.load_dir`; a failure gives the `cache_error` of the pipeline.
- **Stages.** Without `--stages`, every stage of `DOCUMENT_STAGES` MUST be selected. A stage of `OPT_IN_DOCUMENT_STAGES` (`roundtrip.rta3`) MUST run only when `--stages` names it. An unknown or empty stage name MUST exit 2 with `FEN-2001` and a hint that lists `ALL_DOCUMENT_STAGES`.
- **Result.** `result.project` MUST hold `backend` (`altium`), `project` and `board` (names or `null`), `built`, `files` (the sorted document names), `documents` (objects `{name, kind, role}` sorted by name) and `skipped` (objects `{name, reason}` with reason `missing`). `result.stages` MUST hold one object per selected stage. `input` MUST describe the file that `PATH` names, or the project file for a folder, with its name relative to the root, its SHA-256 and its read kind.
- **Exit codes.** 0 without an issue of severity `error`, 5 (`FEN-5001`) with one, and never 6. When `CheckReport.read_error` is set, the command MUST exit 3 with that error's FEN code by raising `cmd_check.ReadRefusedError` with `issues = CheckReport.issues`, as for a KiCad board.
- **Read-only.** "Check is read-only" applies: the snapshot of the project folder MUST be equal before and after, no `.fenolite/` entry MUST be created, and no subprocess MUST run.
- **Determinism.** "Check output is deterministic" applies: two runs give the same stdout apart from `elapsed_ms`, with names relative to the root.

#### Scenario: Own project is clean
- **WHEN** `uv run fenolite check tests/data/altium/blink/blink.PrjPcb --json` runs
- **THEN** the exit code is 0, `result.project.backend` is `altium`, `result.project.board` is `blink.PcbDoc`, `result.project.built` is `false`, the stages `model.validate`, `erc.lite`, `copper.clearance`, `parity`, `netlist.assignment_compare`, `roundtrip.rta0` and `roundtrip.rta1` have status `ok`, `copper.clearance` reports no short and no clearance finding, every count of `parity` is 0, the pair is (`schematic`, `pcb`) with 0 differences, and `roundtrip.rta2` is skipped with reason `native-input`

#### Scenario: One library alone
- **WHEN** `fenolite check tests/data/altium/blink/blink.PcbLib --json` runs
- **THEN** the exit code is 0, `roundtrip.rta0` and `roundtrip.rta1` have status `ok`, `model.validate` reports no issue and is skipped with reason `not-judged` (a library gives no reading to judge), `erc.lite` and `parity` are skipped with the reason `no-schematic`, and `copper.clearance` and `netlist.assignment_compare` with `single-source`

#### Scenario: Unreadable single document
- **GIVEN** a copy of `blink.PcbDoc` in `tmp_path` cut to 100 bytes
- **WHEN** `fenolite check <copy> --json` runs
- **THEN** the exit code is 3, stderr carries `FEN-3004`, and the envelope on stdout has `ok` false and `issues` holding one `check.read-refused`

#### Scenario: Project with one unreadable document
- **GIVEN** a copy of the blink project whose `blink.PcbDoc` is cut to 100 bytes
- **WHEN** `fenolite check <folder> --json` runs
- **THEN** the exit code is 5, the first issue is `check.read-refused` with a `where` that starts with `blink.PcbDoc`, and `netlist.assignment_compare` is skipped with reason `single-source`

#### Scenario: Read-only and without tools
- **GIVEN** a copy of the built blink project, with `subprocess.run` and `subprocess.Popen` patched to raise
- **WHEN** `uv run pytest tests/unit/cli/test_check_readonly.py -k altium` runs `check` and `inspect` on it
- **THEN** each snapshot of the folder is equal before and after, and no subprocess ran

#### Scenario: Two runs are equal
- **WHEN** `fenolite check tests/data/altium/blink --json` runs twice
- **THEN** the two stdouts are equal apart from `elapsed_ms`, and hold no absolute path

### Requirement: Altium check stage evidence
Each stage of an Altium check SHALL carry its own evidence, and the envelope SHALL combine them as "Document check pipeline" says.

| stage | evidence |
|---|---|
| `model.validate`, native | `Evidence.combine` of the readings judged |
| `model.validate`, built | `INFERRED` (Fenolite's structural rules) |
| `erc.lite`, native | `Evidence.combine(erc_lite.EVIDENCE, <schematic reading>, stage_evidence()["erc.lite"])`, which adds `H-A-VER-ERC` |
| `erc.lite`, built | `erc_lite.EVIDENCE` |
| `copper.clearance` | `Evidence.combine` of the PCB reading, of `checks.copper.EVIDENCE`, of `DesignRules.evidence` and of `stage_evidence()["copper.clearance"]`, which adds `H-A-DRC-SAME`; `UNVERIFIED` when the stage reports `copper.rules-incomplete` or `copper.item-unsupported` |
| `parity` | `Evidence.combine(parity.EVIDENCE, SideOutcome.evidence, <both readings>, stage_evidence()["parity"])`, which adds `H-A-DRC-PARITY` |
| `netlist.assignment_compare` | `Evidence.combine` of the readings compared and of `stage_evidence()["netlist.assignment_compare"]`, with `INFERRED` on built input; its hypotheses hold c0043's `H-A-IMP-NETLIST` |
| `roundtrip.rta0` | the evidence of the judged verdicts, `EVIDENCE_RT_A0`; `UNVERIFIED` when the stage reports `check.rta0-failed` |
| `roundtrip.rta1` | the evidence of the judged verdicts, `EVIDENCE_RT_A1` of their kinds, combined; `UNVERIFIED` when the stage reports `check.rta1-failed` |
| `roundtrip.rta2` | `INFERRED` with `H-A-VER-RTA2-3`, combined with the readings |
| `roundtrip.rta3` | `EVIDENCE_RT_A3` (`INFERRED`, `H-A-VER-RTA3`) combined with the import's evidence; `UNVERIFIED` when the stage reports `check.rta3-failed` |

No stage MAY carry `ORACLE-VERIFIED`, `KICAD-VERIFIED` or `ALTIUM-VERIFIED`: no tool other than Fenolite reads the files in this command. The evidence comes from the backend, with each verdict (`ContainerRoundTrip.evidence`) and through `DocumentValidator.stage_evidence()`, so `checks` names no hypothesis of a backend.

#### Scenario: Levels on the own project
- **WHEN** `fenolite check tests/data/altium/blink/blink.PrjPcb --json` runs
- **THEN** no stage has a level above `CORPUS-VERIFIED`, `roundtrip.rta0` names `H-A-VER-RTA0` until that row is confirmed, and the envelope level is the lowest level of the stages that ran

#### Scenario: Failed copy lowers the stage
- **GIVEN** `cfb.write_compound` patched to drop one stream
- **WHEN** `fenolite check tests/data/altium/blink/blink.PcbDoc --stages roundtrip.rta0 --json` runs
- **THEN** the exit code is 5 and the stage level is `UNVERIFIED`

### Requirement: Altium file summary
`fenolite inspect FILE --summary` on an Altium file SHALL give the result keys of "Inspect command" (`cli-contract`) from the product readers, without running any tool.
- `kind` MUST be the read kind that `document_set` gives the file. `format_version` MUST be the version text of the file's header (`5.0` for a schematic or a schematic library, `6.0` or `5.0` for a PCB file, as the header reads), or `null` for a project file. `major`, `generator` and `generator_version` MUST be `null`, and `status` MUST be `supported`.
- `counts`: for a PCB document the board counts of "Inspect command" from the read design, plus `components` and `rules`; for a schematic `components`, `pins`, `nets` and `no_connects` (the marked pins) from the read design and `wires`, `labels`, `power_ports`, `ports` and `sheet_symbols` from the records; for a schematic library `symbols`, `units` and `pins`; for a PCB library `footprints`, `pads` and `graphics`; for a project file `documents` (the documents it lists with one of the five suffixes, without the project file itself), `missing`, and one count per role of the documents that exist.
- `opaque_count` MUST be `ContainerRoundTrip.opaque_count` of RT-A1, and `result.streams` MUST hold `typed` and `opaque` (stream counts). For a project file `result.documents` MUST list `{name, kind, role, exists}` sorted by name; a listed document that does not exist has `exists` false and `kind` and `role` `null`.
- `model_findings` MUST count the `model.*` findings of the read content by severity, and the readers' issues MUST be reported as issues, as for a KiCad file.
- A read error MUST exit 3 with its code, and a missing file with `FEN-3001`. `input.kind` MUST be the read kind.
- The envelope evidence MUST be that of `backend.read(FILE)`.

#### Scenario: Own PCB document
- **WHEN** `uv run fenolite inspect tests/data/altium/blink/blink.PcbDoc --json` runs
- **THEN** the exit code is 0, `result.kind` is `altium_pcbdoc`, `result.major` is `null`, `result.counts.footprints` is 3, `result.counts.pads` equals the pads that `tests/_altium_pcb_read.read_pcbdoc` counts, and `result.streams.typed` is at least 1

#### Scenario: Own schematic in both forms
- **WHEN** `inspect` runs on `tests/data/altium/sample/altium_sample.SchDoc` and on `tests/data/altium/sample/binary/altium_sample.SchDoc`
- **THEN** the kinds are `altium_schdoc_ascii` and `altium_schdoc_binary`, both `format_version` values are `5.0`, and both `counts` are equal

#### Scenario: Project file
- **WHEN** `inspect` runs on `tests/data/altium/blink/blink.PrjPcb`
- **THEN** `result.counts.documents` is 4, `result.format_version` is `null`, and `result.documents` lists four names with `exists` true

#### Scenario: Truncated file
- **GIVEN** a copy of `blink.PcbLib` cut to 100 bytes
- **WHEN** `inspect` runs on it
- **THEN** the exit code is 3 and stderr carries `FEN-3004`

### Requirement: Records view of two Altium files
`fenolite diff A B --view records` SHALL compare two Altium files of the same read kind stream by stream, through `roundtrip.diff_records(a: bytes, b: bytes, *, kind: str) -> DiffReport` (`backends.base.DiffReport`).
- Streams are matched by path and typed streams are read with the codec of the kind. A stream on one side only is `removed` or `added` with path `/<stream>`. An opaque stream whose bytes differ is `changed` with path `/<stream>`, `a` and `b` being the SHA-256 of each side.
- The records of a typed stream are aligned by the longest common subsequence of equal records. Two records are equal for the alignment when their content is equal (`roundtrip.record_content`: the frame kind and payload of a record, or its bytes): a record's index, offset and owner references follow from its place and take no part, so one inserted record moves no other. Past `roundtrip.LCS_CELLS` cells of the alignment table, the middle of two streams is aligned by the matching blocks of `difflib.SequenceMatcher`, which need not be the longest. A record on one side only is `removed` or `added` with path `/<stream>#<index>`, the index being its own side's and the header of a binary stream being record 0. Two unaligned records at the same place whose record kind (the reader's class name) is equal are one `changed` with path `/<stream>#<index of a>`.
- `a` and `b` of a record change MUST be the JSON text `{"kind": <record kind>, "fields": {…}}` with the keys or field names that differ (every key of a record on one side only), and MUST hold a value only for a property whose text is at most 80 bytes; a longer or binary value is given as its length and SHA-256.
- `summary` MUST map each stream that has a change to its counts, and `changes` MUST be in the order of the stream paths and, in a stream, of the record indices. Two files of different kinds, or a kind that `CODECS` does not hold, MUST exit 2 with `FEN-2001`.
- The two binary and ASCII schematic kinds are different kinds: the records view does not convert a form.

#### Scenario: A file against itself
- **WHEN** `fenolite diff tests/data/altium/blink/blink.SchDoc tests/data/altium/blink/blink.SchDoc --view records --json` runs
- **THEN** `result.view` is `records`, `result.equal` is `true` and `result.total` is 0

#### Scenario: One key changed
- **GIVEN** two authored binary schematics that differ in the `TEXT` value of one net label
- **WHEN** `uv run pytest tests/unit/backends/altium/test_diff_records.py -k one_key` runs `diff_records`
- **THEN** the only change is `changed` at `/FileHeader#<index>`, and its `a` and `b` name the key `TEXT` with both values

#### Scenario: One record inserted
- **GIVEN** the same schematic with one more wire record in the middle of `FileHeader`
- **WHEN** `diff_records` runs
- **THEN** the only change is one `added` record, and no later record is reported

#### Scenario: Different kinds refused
- **WHEN** `fenolite diff tests/data/altium/blink/blink.SchDoc tests/data/altium/blink/blink.PcbDoc --view records` runs
- **THEN** the exit code is 2 with `FEN-2001`

### Requirement: Round trips over the corpus and the samples
The three levels SHALL be measured on every public file of the corpus and on every file Fenolite writes, and the results SHALL be recorded in `docs/evidence/altium-roundtrip.md`.
- `tests/corpus/test_altium_roundtrip.py` (marker `needs_corpus`) MUST run `rt_a0` and `rt_a1` on every cached row whose `uses` holds `rta` (`corpus-policy`, "Round-trip use on Altium rows"). Every judged verdict MUST pass. A verdict that is not judged MUST have one of the reasons `too-large`, `writer-refused` or `not-a-container`. A file that the reader refuses fails the test, unless its row is listed in the page with the reader's hypothesis that it refutes.
- `tests/corpus/test_altium_documents.py` (marker `needs_corpus`) MUST copy each project set of c0043's "Altium project sets" (`corpus-policy`, the rows of one use `altium-set:<nn>`) into pytest's temporary directory and run `fenolite check` on it. It MUST record, per set, the status of each stage and the counts of the pair (`schematic`, `pcb`): `common`, `only_a`, `only_b` and `differences`. A set with differences MUST be listed in the page with its count; it does not fail this test, because c0043's "Altium project sets agree" judges it (`H-A-IMP-NETLIST`).
- Both tests MUST write, only to the file named by `FENOLITE_CENSUS_OUT`, per row id: the kind, the size, the verdict of each level, the reason when not judged, and the counts `streams`, `records`, `bytes_equal` and `opaque_count`. They report ids, kinds, stream names and counts only.
- `tests/unit/backends/altium/test_roundtrip.py` and `tests/unit/lens/test_altium_rta2.py` MUST run the three levels on every Altium file under `tests/data/altium/` and on every example build, without the corpus.
- The page MUST hold one table per level with the row ids, the counts, every unjudged file with its reason, every stream with `bytes_equal` false, and the date and commit of the run. `H-A-VER-RTA0` and `H-A-VER-RTA1` are confirmed only when every judged row passes and at least three repositories are judged per compound kind that the corpus holds; `H-A-VER-BYTES` when every typed stream of every row has equal bytes. `tests/corpus/test_altium_roundtrip.py` MUST pin the number of repositories of each compound kind that is below three (`SHORT_OF_THREE`), so that a new repository fails the test and the rows are settled again.
- Derived files MUST stay under pytest's temporary directory ("Derived corpus files stay out of the repository").

#### Scenario: Corpus round trips
- **GIVEN** the cached `rta` rows and `FENOLITE_REQUIRE=corpus`
- **WHEN** `uv run pytest tests/corpus/test_altium_roundtrip.py -q` runs
- **THEN** every judged row passes RT-A0 and RT-A1, each row with DIFAT sectors (two PCB documents, one of them heavy) is unjudged for RT-A0 with reason `too-large` and judged for RT-A1, and the census file holds one entry per row

#### Scenario: Project sets
- **GIVEN** the cached project sets and `FENOLITE_REQUIRE=corpus`
- **WHEN** `uv run pytest tests/corpus/test_altium_documents.py -q` runs
- **THEN** every set is checked without a crash, every project folder copy is unchanged afterwards, and the census file holds the pair counts of each set

#### Scenario: Corpus absent
- **GIVEN** an empty corpus cache and no `FENOLITE_REQUIRE`
- **WHEN** both corpus tests run
- **THEN** every case is skipped with the corpus hint, and the run exits 0

#### Scenario: Page matches the census
- **WHEN** `uv run pytest tests/unit/test_altium_roundtrip_page.py` reads `docs/evidence/altium-roundtrip.md`
- **THEN** the page holds the three level tables, a run date and a commit, and names no row outside the manifest

### Requirement: Altium verification is documented
`docs/altium.md`, `docs/cli-contract.md` and `docs/roadmap.md` SHALL describe the levels and the commands.
- `docs/altium.md` MUST gain the section "Round trips": the three levels with what each proves and does not prove, the reasons for an unjudged level, the scope of RT-A2 with every left-out field and its reason, and the commands that report each level.
- `docs/cli-contract.md` MUST describe `check` on Altium input (stages, skip reasons, result keys, the six new codes), the Altium summary of `inspect`, and the section "diff" with both views.
- `docs/roadmap.md` MUST define RT-A0, RT-A1 and RT-A2 next to RT0 to RT2, and MUST say that `diff` (added by c0066 with the model view and the tree view) reads second-backend inputs and has the records view from this change.
- The pages MUST name no company, person or project of a corpus file.

#### Scenario: Pages name the levels and the codes
- **WHEN** `uv run pytest tests/unit/test_altium_verification_docs.py` reads the three pages
- **THEN** each of `RT-A0`, `RT-A1` and `RT-A2` appears in `docs/altium.md` and in `docs/roadmap.md`, every name of `DOCUMENT_STAGES` and each of the six codes appears in `docs/cli-contract.md`, and `docs/cli-contract.md` has a heading `diff`

### Requirement: Document stage order
`checks.documents.DOCUMENT_STAGES` SHALL be `model.validate`, `erc.lite`, `copper.clearance`, `parity`, `netlist.assignment_compare`, `roundtrip.rta0`, `roundtrip.rta1`, `roundtrip.rta2`, in this order, and every stage SHALL be a default stage that runs no external tool. `copper.clearance` and `parity` keep the relative order they have in `STAGE_ORDER`.

#### Scenario: Order
- **WHEN** `uv run pytest tests/unit/checks/test_document_copper.py -k stage_order` reads the tuple
- **THEN** it equals the list above

### Requirement: Copper check on Altium boards
On document input that holds a PCB document, the stage `copper.clearance` SHALL run `checks.copper.copper_stage` on the PCB reading with the rules that the backend gives for that document (`DesignRulesSource`) and its pads (`BoardFrame`), built and native input alike, through `checks.documents.document_copper`. The copper check judges shorts, clearance and zone-outline overlaps; it judges no board-edge clearance on any backend.
- The stage MUST be skipped with `single-source` when the documents hold no PCB document, and with `read-refused` when it could not be read.
- The findings MUST use the codes and severities of "Copper stage issue codes" of `verification-loop`, unchanged, and `summary` MUST hold the keys of that stage and two more counts, `unpoured` and `zones_unjudged`.
- **Rules.** Enabled `Clearance` records of the document that the rule table does not map MUST be counted in `summary.rules.opaque_clearance_rules` and MUST give `copper.rules-incomplete` (warning). Rule kinds that the copper check does not read (every kind but `Clearance`) MUST NOT give an issue of this stage: the import reports them.
- **Polygons.** A polygon with poured regions MUST be checked as a filled zone. A zone without a fill MUST be counted in `summary.unpoured`; when the count is not zero the stage MUST add one `copper.item-unsupported` (warning) with the count.
- **No invented clearance.** A polygon holds no clearance of its own, so the model's default zone clearance MUST NOT be judged. A filled zone for which no clearance is in force whatever the other item is (no rule, class or board minimum applies to copper of its net on a layer of its fills) MUST be counted in `summary.zones_unjudged`; when the count is not zero the stage MUST add one `copper.rules-incomplete` (warning, `where` = `zone`) with the count. Such a zone is still judged for shorts.
- **Planes.** What the rules source left out (`DesignRules.left_out`) MUST give one `copper.item-unsupported` (warning) per kind, `where` = the kind.
- The stage's evidence MUST be `UNVERIFIED` when it reports `copper.rules-incomplete` or `copper.item-unsupported`.

#### Scenario: A short on an Altium board
- **GIVEN** the routed blink whose script holds one more track of `LED_A` that crosses the track of `LED_DRV` on `F.Cu`, built for Altium with `--copper-check warn`
- **WHEN** `fenolite check <dir> --stages copper.clearance --json` runs
- **THEN** the exit code is 5 and one `copper.short` names the two nets

#### Scenario: Unpoured polygons are said
- **WHEN** `fenolite check tests/data/altium/routed --stages copper.clearance --json` runs (a built board with two unpoured polygons and no other fault)
- **THEN** the exit code is 0, it reports one `copper.item-unsupported` with the count 2, `summary.unpoured` is 2, and its evidence level is `UNVERIFIED`

#### Scenario: A pour without a clearance rule
- **GIVEN** a board model with one filled zone, no clearance rule, and a track of another net 0.3 mm from the fill
- **WHEN** `uv run pytest tests/unit/checks/test_document_copper.py -k default` runs the stage
- **THEN** it reports no `copper.clearance`, one `copper.rules-incomplete` that counts 1 zone, `summary.zones_unjudged` is 1, and the level is `UNVERIFIED`

#### Scenario: Same board, two backends
- **WHEN** `uv run pytest tests/kicad/altium/test_copper_same.py` checks the routed blink built for KiCad and for Altium, as built and with a planted short, a planted clearance fault and both
- **THEN** the copper findings of the two readings are equal by kind, net pair and place within 2 nm

#### Scenario: Public documents
- **WHEN** `uv run pytest tests/corpus/test_altium_copper.py -k copper` runs the stage on every public PCB document
- **THEN** no finding has the source `zone`, a document without a mapped `Clearance` rule has no clearance finding, and every finding that the 5 nm slack removes is short by 5 nm at most

### Requirement: Board frame of an imported board
`AltiumBackend` SHALL satisfy `BoardFrame` (`backend-protocol`), through `fenolite.backends.altium.frame`: `board_pads(design)` gives one `BoardPad` per pad of every footprint of an imported board, and `placed_extents(design)` one `PlacedExtent` per footprint.
- A pad's position MUST be the footprint's position plus the pad's own position turned by the footprint's angle, with no further mirror, and its rotation the sum of the two angles. The copper of a layer of a stack MUST lie at the pad's position plus that layer's offset.
- A circle, an oval, a rectangle and a rounded rectangle with its corner percentage (the pair `corner_percent` of the pad's `altium` bag; the radius is that share of half the shorter side) MUST give exact entries. Any other shape MUST give the rectangle of its size with `exact` false. A non-plated hole MUST give no copper.
- An extent MUST be the hull of its footprint's pad copper on the face of its side, with `source` = `pads` and `exact` false, or `source` = `none` without pad copper.
- The module MUST declare its evidence (`backend-protocol`, "Backend modules declare their evidence") and MUST NOT import `fenolite.backends.kicad` or `fenolite.checks`.

#### Scenario: Pads of the routed sample
- **WHEN** `uv run pytest tests/unit/backends/altium/test_frame.py -k frame` reads `tests/data/altium/routed/routed.PcbDoc`
- **THEN** `board_pads` gives 36 pads, every entry is exact, each through-hole pad has an entry on each of the four copper layers, and each surface pad one entry on `F.Cu`

### Requirement: Clearance rules of a PCB document
`AltiumBackend` SHALL satisfy `DesignRulesSource` (`backend-protocol`): `design_rules(design, project)` gives the clearance in force for the import `design` of the PCB document `project.board`.
- `DesignRules.design` MUST be `design` with the clearance of every zone at 0, with every `clearance` rule lowered by `UNIT_SLACK_NM` = 5 nm (`docs/formats/altium/import.md`, "Clearance of the copper check"). It MUST hold every track and every arc of `design`: the import makes no copper of an object on an internal plane (`altium-import`, "Objects on an internal plane"), so the rules source takes nothing out.
- `opaque_clearance_rules` MUST count the enabled `Clearance` records of `Rules6/Data` that `read.rules.map_rules` does not map; a disabled record MUST NOT count. `min_clearance` MUST be `None`, `rules_over_classes` true and `floor_over_rules` false.
- `left_out` MUST hold one entry of kind `plane` with the number of internal plane layers when the board has any, and be empty otherwise. An internal plane layer is a copper layer whose `altium` bag holds a `layer_id` from 39 to 54. The entry's reason MUST hold the number of objects that the import left out on those layers, the sum of their `plane_cuts`.
- A document that cannot be read MUST be named in `unread` and MUST NOT raise.

#### Scenario: Rules of a built sample
- **WHEN** `uv run pytest tests/unit/backends/altium/test_frame.py -k rules_source` asks for the rules of `routed.PcbDoc`
- **THEN** both zones have the clearance 0, the two clearance rules are 199 995 nm, no rule is opaque, and a missing document is named in `unread`

#### Scenario: Planes of an imported board
- **GIVEN** an authored document whose chain is 1 → 39 → 32, with two free tracks without a net on layer 39 and one track on layer 1
- **WHEN** `uv run pytest tests/unit/backends/altium/test_frame.py -k plane` imports it and asks for its rules
- **THEN** `DesignRules.design` holds the one track of the import, `left_out` is one entry `plane` with the count 1 whose reason names 2 objects, and a board without a plane layer has an empty `left_out`

### Requirement: Parity on Altium projects
On document input that holds a PCB document and schematic documents, the stage `parity` SHALL compare the two readings with `checks.parity.compare`, with the schematic side that the backend builds from them (`DocumentParity` of `backend-protocol`; for Altium `adapter.parity.side_of(schematic, board)`): components by designator, the value from the comment, the footprint from the current footprint model, the pads that the pins name (the pad of a pin's own designator, or those of `Component.pin_pad_map` when the component holds one), the nodes from the imported nets.
- **Two spellings are read as one**, because they differ between the two documents of a project without being a difference of the design: a footprint whose name (the text after the last `:`) equals the name of the footprint of the same designator on the board is given in the board's spelling; and a net whose pads, over the pads both sides hold on a net, are exactly the pads of one board net is given that net's name. Any other footprint and any other net MUST keep the schematic's spelling, so a split, joined or open net stays a finding.
- `fold` and `single_prefix` of the side MUST be empty, and no component MUST carry an attribute.
- The stage MUST be skipped with `no-schematic` without a schematic document, with `single-source` without a PCB document, with `read-refused` when a side was refused, and with `netlist-unavailable` when the backend gives no side.
- Every finding MUST become an issue with the codes of the parity comparison (`checks.parity.PARITY_ISSUE_CODES`); `summary` MUST hold `netlist` = `own`, `compared` = `false`, `differences` = 0 and the counts of `ParityReport.summary`.
- `fenolite parity PATH` MUST accept an Altium project file, a project folder, or a PCB document beside the one project file whose board it is, with the result keys of the KiCad branch (`board`, `schematic`, `netlist`, `summary`, `findings`); `--netlist kicad` on such input MUST exit 2 with `FEN-2001`, and a set without a PCB document or without a schematic document MUST exit 3 with `FEN-3001`.

#### Scenario: Renamed designator
- **GIVEN** the routed blink built for Altium, with the PCB document of a build of the same script in which `R1` is `R99`
- **WHEN** `fenolite check <dir> --stages parity --json` runs
- **THEN** the exit code is 5, and the issues hold `parity.missing-footprint` at `R1` and `parity.extra-footprint` at `R99`

#### Scenario: Agreeing project
- **WHEN** `fenolite parity tests/data/altium/blink --json` runs
- **THEN** the exit code is 0 and every summary count is 0

#### Scenario: Committed samples agree
- **WHEN** `uv run pytest tests/unit/backends/altium/adapter/test_parity_side.py -k committed` compares the samples `blink`, `routed` and `board6` with their own boards
- **THEN** no sample gives a finding

#### Scenario: Public project sets
- **WHEN** `uv run pytest tests/corpus/test_altium_copper.py -k parity` compares each public project set
- **THEN** every `parity.net-conflict` names a pad that the pad-net comparison of the two readings flags

### Requirement: RT-A2 on a written model
For a project that Fenolite built, the level RT-A2 SHALL compare every kind of `RT_A2_SCOPE` between the stored model and the reading of the written documents: components, nets, no-connect marks, net classes, footprints, pads, tracks, arcs, vias and zones, within 2 nm.
- No kind of the scope MAY be only counted: `checks.rta2.rta2_stage` MUST compare a kind also when the stored model holds no entity of it, and its summary MUST hold no `not_in_model`.
- A built project whose stored model predates this change (`checks.rta2.predates_board`: its board holds no footprint while the PCB reading holds one) MUST skip the stage with the reason `model-predates-board` and MUST report no issue. A build that wrote no PCB document has no PCB reading and is judged on its schematic alone.
- The PCB reading MUST be compared in the frame of the stored model: when the validator is a `ModelWriter` (`backend-protocol`, "Model writers"), the pipeline calls `in_model_frame(model, reading)` before the comparison.
- Rules are not part of `RT_A2_SCOPE` in this change. The PCB document also holds the rules that the writer derives from the net classes and from its defaults, which are no rule of the model, so a comparison of the two rule lists has no clean equal state; the read-back of the lowered rules is judged by `altium-build`, "Rules in an Altium build" (`rulemap.lift` and `same_rules`).
- The stage's evidence MUST be `INFERRED` with `H-A-VER-RTA2-3` combined with the readings' evidence.

#### Scenario: Every kind compared on every example
- **WHEN** `uv run pytest tests/unit/lens/test_altium_rta2.py` builds every script under `examples/` in both schematic forms
- **THEN** each build holds RT-A2 with 0 differences, each build with a PCB document compares `arc`, `footprint`, `netclass`, `pad`, `track`, `via` and `zone` with the PCB reading, and its stored board holds at least three footprints

#### Scenario: Copper compared
- **GIVEN** the routed blink built for Altium, with one track of the PCB document moved by record edit
- **WHEN** `fenolite check <dir> --stages roundtrip.rta2 --json` runs
- **THEN** the exit code is 5, and every `check.rta2-failed` has a `where` that starts with `pcb:/track/`

#### Scenario: Model without the board
- **GIVEN** the built blink whose `.fenolite/board.json` is rewritten without its footprints
- **WHEN** `fenolite check <dir> --stages roundtrip.rta2 --json` runs
- **THEN** the exit code is 0 and the stage is skipped with reason `model-predates-board`

### Requirement: Round-trip level RT-A3
The level RT-A3 SHALL hold for an Altium document when the model that its import gives equals the model that the import gives after Fenolite wrote that model as new documents, inside `RT_A3_SCOPE` within 2 nm, once the items that the write reports as not written are taken out of the first model.
- `AltiumBackend.model_roundtrip(path, *, compare)` MUST make the trip for a PCB document, a schematic document or a project file: read `path` with `read`, write the model with `lower.write_design(..., allow_lossy=True)` into a temporary folder of its own, read the written document of the same kind, and return the verdict of `rta3.rt_a3(first, written, second, compare=…, census=…, from_board=…)`. It MUST write nothing beside the input and MUST remove the folder. `backends.altium.rta3` MUST touch no file, and `backends.altium.roundtrip` stays free of paths.
- `RT_A3_SCOPE` MUST be the written scope of the writers, as `AltiumBackend.written_scope()` returns it, and `docs/altium.md` MUST hold it as a table ("Written scope").
- The verdict (`backends.base.ModelRoundTrip`) MUST hold `judged`, `equal`, the located `differences`, `written` (the model items written, per kind) and `unwritten`: per kind, the model items that the write left out (`lower.AltiumInputs.counts()`) and, under keys that start with `record:`, the records of the first reading that the import maps to no model entity, by the category of the import's census. `unwritten` MUST NOT change `equal`.
- `rta3.without_unwritten` MUST take out of the first model exactly the entities that `AltiumInputs.not_lowered` names; for a PCB document read alone, whose circuit is synthesised from the pads, a component whose footprint was not written and a net member whose pads were not written go too. Nothing else is taken out: a difference of an item that was written is a defect of a writer or of the import.
- A trip is not judged, with the reason `no-document`, when the write gives no document of the kind that was read (the schematic writer refuses the circuit of a project); the PCB document is then still written and counted.
- The schematic of a rewrite is generated from the circuit: the stage's summary MUST say `presentation: regenerated`. Keeping the drawing of an Altium schematic is not part of this level.
- The stage `roundtrip.rta3` MUST be opt-in on document input, MUST write nothing under the input folder, and MUST report each difference as `check.rta3-failed` (error, at most 50) and the unwritten kinds as one `check.rta3-unwritten` (info) with the counts. Its summary MUST hold `level` (`RT-A3`), `holds`, `differences`, `unwritten`, `written`, `files` and `presentation`.
- Its evidence MUST be `roundtrip.EVIDENCE_RT_A3` (`INFERRED`, `H-A-VER-RTA3`) combined with the import's evidence, and `UNVERIFIED` when the stage reports a difference or the trip is not judged.
- `fenolite roundtrip PATH --level rta0|rta1|rta2|rta3` MUST accept Altium input and run the stage `roundtrip.<level>` of the document check: `result.level` is the level when it holds and `none` otherwise, `result.<level>` holds the stage's status, reason and summary, and for `rta3` `result.unwritten` repeats the counts. Without `--level`, Altium input is judged at `rta1`. A KiCad level on Altium input, and an Altium level on another input, MUST exit 2 with `FEN-2001`.

#### Scenario: Own sample
- **WHEN** `fenolite roundtrip tests/data/altium/board6 --level rta3 --json` runs
- **THEN** the exit code is 0, `result.level` is `rta3`, `result.rta3.differences` is 0, `result.unwritten` counts 2 texts and 6 graphics (on a mechanical layer that no record of the writer carries) and 33 `record:footprint-graphics`, and no file is written under the sample folder

#### Scenario: Corpus documents
- **WHEN** `uv run pytest tests/corpus/test_altium_rta3.py -rA` runs with the corpus cached
- **THEN** every listed PCB document is equal inside the scope, the equal documents come from at least three repositories, and the test prints the written and the unwritten counts per kind for the evidence page

#### Scenario: Project sets
- **WHEN** the same test runs `test_sets` on the project sets of c0043
- **THEN** each set is equal through its project file or is listed in `UNJUDGED_SETS` with the reason why the schematic writer refuses its circuit, and on an equal set `netlist.assignment_compare` reports on the rewrite what it reported on the original, apart from one `netlist.uncovered` info where pads were not written

#### Scenario: A writer defect is caught
- **GIVEN** a writer patched to drop the last via
- **WHEN** `AltiumBackend().model_roundtrip` runs on `tests/data/altium/routed/routed.PcbDoc`
- **THEN** `equal` is false, the one difference is `/via/0`, and `fenolite check … --stages roundtrip.rta3` exits 5 with one `check.rta3-failed`

#### Scenario: KiCad reads the rewrite
- **WHEN** `uv run pytest tests/kicad/altium/test_rta3_oracle.py -rA` runs on KiCad 10.0.6 with the corpus cached
- **THEN** `kicad-cli pcb import` reads the rewrite of each own document and of each listed public document as Fenolite does, with no difference at the levels 1 to 5 of `equivalent` under the profile, and the probe `altium-rta3-kicad` is `equal`

### Requirement: Round-trip claims of the Altium kinds
`backends/altium/claims.py` SHALL state for each Altium read kind what the round-trip levels support: its docstring MUST no longer say that no Altium file is read and written back, and `claims.ROUND_TRIP_NOTES` MUST map each read kind to a note that names the highest level that holds over the corpus (`RT-A1`, or `RT-A3 inside the written scope`) with its hypothesis. The evidence matrix has no column for a note (`backend-protocol`, "Evidence matrix rows"), so the notes are in the module and in `docs/evidence/altium-roundtrip.md`.
- The `write` cell of `altium_pcbdoc` MUST combine `lower.EVIDENCE`: a model with a board is written without a script.
- A `roundtrip_exact` cell MUST be set only when RT-A3 holds on the corpus list with no unwritten record for that kind; otherwise it MUST stay empty.
- No cell MAY be set from files that Fenolite wrote itself.

#### Scenario: Matrix follows the run
- **WHEN** `uv run python tools/gen_evidence_matrix.py --check` runs after the corpus run was recorded
- **THEN** the matrix is up to date, the `write` cell of `altium_pcbdoc` names `H-A-VER-RTA3`, no Altium kind has a `roundtrip_exact` or `roundtrip_modified` cell, and `uv run pytest tests/unit/backends/altium/test_claims_notes.py` finds a note with a registered hypothesis for each of the six read kinds
