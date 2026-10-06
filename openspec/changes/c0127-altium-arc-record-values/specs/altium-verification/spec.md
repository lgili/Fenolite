## MODIFIED Requirements

### Requirement: Round-trip level RT-A3
The level RT-A3 SHALL hold for an Altium document when the model that its import gives equals the model that the import gives after Fenolite wrote that model as new documents, inside `RT_A3_SCOPE` within 2 nm, once the items that the write reports as not written are taken out of the first model.
- `AltiumBackend.model_roundtrip(path, *, compare)` MUST make the trip for a PCB document, a schematic document or a project file: read `path` with `read`, write the model with `lower.write_design(..., allow_lossy=True)` into a temporary folder of its own, read the written document of the same kind, and return the verdict of `rta3.rt_a3(first, written, second, compare=…, census=…, from_board=…)`. It MUST write nothing beside the input and MUST remove the folder. `backends.altium.rta3` MUST touch no file, and `backends.altium.roundtrip` stays free of paths.
- `RT_A3_SCOPE` MUST be the written scope of the writers, as `AltiumBackend.written_scope()` returns it, and `docs/altium.md` MUST hold it as a table ("Written scope").
- The verdict (`backends.base.ModelRoundTrip`) MUST hold `judged`, `equal`, the located `differences`, `written` (the model items written, per kind) and `unwritten`: per kind, the model items that the write left out (`lower.AltiumInputs.counts()`) and, under keys that start with `record:`, the records of the first reading that the import maps to no model entity, by the category of the import's census. `unwritten` MUST NOT change `equal`.
- `rta3.without_unwritten` MUST take out of the first model exactly the entities that `AltiumInputs.not_lowered` names; for a PCB document read alone, whose circuit is synthesised from the pads, a component whose footprint was not written and a net member whose pads were not written go too. Nothing else is taken out: a difference of an item that was written is a defect of a writer or of the import.
- A trip is not judged, with the reason `no-document`, when the write gives no document of the kind that was read (the schematic writer refuses the circuit of a project); the PCB document is then still written and counted.
- The schematic of a rewrite is generated from the circuit: the stage's summary MUST say `presentation: regenerated`. Keeping the drawing of an Altium schematic is not part of this level.
- The stage `roundtrip.rta3` MUST be opt-in on document input, MUST write nothing under the input folder, and MUST report each difference as `check.rta3-failed` (error, at most 50) and the unwritten kinds as one `check.rta3-unwritten` (info) with the counts. Its summary MUST hold `level` (`RT-A3`), `holds`, `differences`, `unwritten`, `written`, `files` and `presentation`.
- Its evidence MUST be `roundtrip.EVIDENCE_RT_A3` (`CORPUS-VERIFIED`, `H-A-VER-RTA3`; change c0127) combined with the import's evidence, and `UNVERIFIED` when the stage reports a difference or the trip is not judged. The constant MUST carry the level of its row in `docs/hypotheses.md`: the row's criterion (equal on every listed corpus document, from at least three repositories) is met since change c0127, with which the heavy public document is equal too. The combination is the lowest of its parts, so a stage, a verdict and an envelope stay `INFERRED` while the import's evidence is `INFERRED`. The level says that Fenolite reads its own rewrite of a public Altium PCB document back to an equal model inside the written scope; it says nothing about Altium opening a written file: that stays `INFERRED` until a kit run (changes c0091 and c0092), and no `roundtrip_exact` cell and no write kind follows from this level ("Round-trip claims of the Altium kinds").
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
| `roundtrip.rta3` | `EVIDENCE_RT_A3` (`CORPUS-VERIFIED`, `H-A-VER-RTA3`; change c0127) combined with the import's evidence, which keeps the stage at `INFERRED` while the import is `INFERRED`; `UNVERIFIED` when the stage reports `check.rta3-failed` |

No stage MAY carry `ORACLE-VERIFIED`, `KICAD-VERIFIED` or `ALTIUM-VERIFIED`: no tool other than Fenolite reads the files in this command. The evidence comes from the backend, with each verdict (`ContainerRoundTrip.evidence`) and through `DocumentValidator.stage_evidence()`, so `checks` names no hypothesis of a backend.

#### Scenario: Levels on the own project
- **WHEN** `fenolite check tests/data/altium/blink/blink.PrjPcb --json` runs
- **THEN** no stage has a level above `CORPUS-VERIFIED`, `roundtrip.rta0` names `H-A-VER-RTA0` until that row is confirmed, and the envelope level is the lowest level of the stages that ran

#### Scenario: Failed copy lowers the stage
- **GIVEN** `cfb.write_compound` patched to drop one stream
- **WHEN** `fenolite check tests/data/altium/blink/blink.PcbDoc --stages roundtrip.rta0 --json` runs
- **THEN** the exit code is 5 and the stage level is `UNVERIFIED`
