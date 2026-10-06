## MODIFIED Requirements

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

## ADDED Requirements

## ADDED Requirements

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
