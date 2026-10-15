## MODIFIED Requirements

### Requirement: Round-trip level RT-A3
The level RT-A3 SHALL hold for an Altium document when the model that its import gives equals the model that the import gives after Fenolite wrote that model as new documents, inside `RT_A3_SCOPE` within 2 nm, once the items that the write reports as not written are taken out of the first model.
- `AltiumBackend.model_roundtrip(path, *, compare)` MUST make the trip for a PCB document, a schematic document or a project file: read `path` with `read`, write the model with `lower.write_design(..., allow_lossy=True, rewrite=True)` (change c0128: the trip is the rewrite of a document that was read, so a via whose drill equals its diameter is written) into a temporary folder of its own, read the written document of the same kind, and return the verdict of `rta3.rt_a3(first, written, second, compare=…, census=…, from_board=…)`. It MUST write nothing beside the input and MUST remove the folder. `backends.altium.rta3` MUST touch no file, and `backends.altium.roundtrip` stays free of paths.
- `RT_A3_SCOPE` MUST be the written scope of the writers, as `AltiumBackend.written_scope()` returns it, and `docs/altium.md` MUST hold it as a table ("Written scope").
- The verdict (`backends.base.ModelRoundTrip`) MUST hold `judged`, `equal`, the located `differences`, `written` (the model items written, per kind) and `unwritten`: per kind, the model items that the write left out (`lower.AltiumInputs.counts()`) and, under keys that start with `record:`, the records of the first reading that the import maps to no model entity, by the category of the import's census. Since change c0126 the lines, arcs, fills, regions and texts of a footprint are model items: what a write leaves out of them is counted under `footprint-graphic`, `footprint-copper` and `footprint-text`, and `record:footprint-graphics` counts only the primitives of a component without a readable position. `unwritten` MUST NOT change `equal`.
- `rta3.without_unwritten` MUST take out of the first model exactly the entities that `AltiumInputs.not_lowered` names; for a PCB document read alone, whose circuit is synthesised from the pads, a component whose footprint was not written and a net member whose pads were not written go too. Nothing else is taken out: a difference of an item that was written is a defect of a writer or of the import.
- A trip is not judged, with the reason `no-document`, when the write gives no document of the kind that was read (the schematic writer refuses the circuit of a project); the PCB document is then still written and counted.
- The schematic of a rewrite is generated from the circuit: the stage's summary MUST say `presentation: regenerated`. Keeping the drawing of an Altium schematic is not part of this level.
- The stage `roundtrip.rta3` MUST be opt-in on document input, MUST write nothing under the input folder, and MUST report each difference as `check.rta3-failed` (error, at most 50) and the unwritten kinds as one `check.rta3-unwritten` (info) with the counts. Its summary MUST hold `level` (`RT-A3`), `holds`, `differences`, `unwritten`, `written`, `files` and `presentation`.
- Its evidence MUST be `roundtrip.EVIDENCE_RT_A3` (`CORPUS-VERIFIED`, `H-A-VER-RTA3`; change c0127) combined with the import's evidence, and `UNVERIFIED` when the stage reports a difference or the trip is not judged. The constant MUST carry the level of its row in `docs/hypotheses.md`: the row's criterion (equal on every listed corpus document, from at least three repositories) is met since change c0127, with which the heavy public document is equal too. The combination is the lowest of its parts, so a stage, a verdict and an envelope stay `INFERRED` while the import's evidence is `INFERRED`. The level says that Fenolite reads its own rewrite of a public Altium PCB document back to an equal model inside the written scope; it says nothing about Altium opening a written file: that stays `INFERRED` until a kit run (changes c0091 and c0092), and no `roundtrip_exact` cell and no write kind follows from this level ("Round-trip claims of the Altium kinds").
- `fenolite roundtrip PATH --level rta0|rta1|rta2|rta3` MUST accept Altium input and run the stage `roundtrip.<level>` of the document check: `result.level` is the level when it holds and `none` otherwise, `result.<level>` holds the stage's status, reason and summary, and for `rta3` `result.unwritten` repeats the counts. Without `--level`, Altium input is judged at `rta1`. A KiCad level on Altium input, and an Altium level on another input, MUST exit 2 with `FEN-2001`.

#### Scenario: Own sample
- **WHEN** `fenolite roundtrip tests/data/altium/board6 --level rta3 --json` runs
- **THEN** the exit code is 0, `result.level` is `rta3`, `result.rta3.differences` is 0, `result.unwritten` holds no key `record:footprint-graphics`, no `text`, no `footprint-graphic` and counts 1 graphic (on the keep-out layer), `result.written` counts 27 under `footprint-graphic`, and no file is written under the sample folder

#### Scenario: Corpus documents
- **WHEN** `uv run pytest tests/corpus/test_altium_rta3.py -rA` runs with the corpus cached
- **THEN** every listed PCB document is equal inside the scope, the equal documents come from at least three repositories, and the test prints the written and the unwritten counts per kind for the evidence page

#### Scenario: Vias with a full drill
- **WHEN** `uv run pytest tests/corpus/test_altium_rta3.py -k full_drill` reads the public document `altium-third-party-pcbdoc-02` with the corpus cached
- **THEN** 48 of its 242 via records hold a hole equal to their diameter, the trip counts 242 vias as written and no via as not written and is equal inside the scope, and a write of the same model without `rewrite` counts 48 vias as not written

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

## ADDED Requirements

### Requirement: Footprint graphics in the Altium round trips
`roundtrip.RT_A2_SCOPE`, which is `RT_A3_SCOPE` and what `AltiumBackend.written_scope()` returns, SHALL compare the graphics of footprints and the corner ratio of pads: the kind `footprint_graphic` with `kind`, `layer`, `points`, `width` and `filled`, and the field `corner_ratio` of the kind `pad` (`verification-loop`, "Footprint items in the model difference").
- Lengths are compared within the scope's 2 nm. The points of an `arc` graphic are compared under the rule that holds for the points of a copper arc.
- **RT-A2.** The stored board of a build holds the graphics in the written form (`altium-build`, "Stored board of an Altium build"). `ModelWriter.in_model_frame` of the Altium backend MUST name the layers `Mech.13`, `Mech.14`, `Mech.15` and `Mech.16` of the reading `F.Fab`, `B.Fab`, `F.CrtYd` and `B.CrtYd` when the model was not read from an Altium document, the inverse of `pcbrecords.LAYER_MAP`.
- A built project whose stored board holds footprints without graphics while the PCB reading holds some (`checks.rta2.predates_graphics`) MUST skip `roundtrip.rta2` with the reason `model-predates-graphics` and report no issue.
- **RT-A3.** `rta3.without_unwritten` takes out of the first model the footprint graphics that `AltiumInputs.not_lowered` names, as it does for every other kind.
- The fields and the texts of a footprint are written and MUST NOT be part of the scope in this change; `docs/altium.md`, "Round trips" and "Written scope", MUST say so with the reason (the stored board of a build holds no field for the texts that the writer places itself), and MUST list the three new keys of `unwritten`.
- Evidence: `H-A-VER-RTA2-GFX` and `H-A-VER-RTA3-GFX`, `INFERRED`. The level of a stage does not change.
- The measured numbers of `docs/evidence/altium-roundtrip.md`, section "RT-A3", MUST be measured again in the same commit: the column of the records without a model entity, the new keys per document, and the size of `board.json` of each import before and after.

#### Scenario: Every example compares its footprint graphics
- **WHEN** `uv run pytest tests/unit/lens/test_altium_rta2.py` builds every script under `examples/` in both schematic forms
- **THEN** each build with a PCB document compares `footprint_graphic` with 0 differences, and its stored board holds at least one graphic per footprint that the document draws

#### Scenario: A moved silkscreen line is caught
- **GIVEN** the built blink with one overlay track of `R1` moved by record edit
- **WHEN** `fenolite check <dir> --stages roundtrip.rta2 --json` runs
- **THEN** the exit code is 5 and every `check.rta2-failed` has a `where` that starts with `pcb:/footprint_graphic/`

#### Scenario: Corpus documents keep their verdicts
- **WHEN** `uv run pytest tests/corpus/test_altium_rta3.py -rA` runs with the corpus cached
- **THEN** every document that was equal inside the scope before this change is equal, no document counts a `record:footprint-graphics`, and the test prints the three new keys per document

#### Scenario: KiCad reads the footprint lines of a rewrite
- **WHEN** `uv run pytest tests/kicad/altium/test_fpitems_oracle.py -rA` runs on KiCad 10.0.6 with the corpus cached
- **THEN** for each own document and each listed public document, the board that `kicad-cli pcb import` gives for the rewrite holds, per footprint and layer class, as many lines and arcs as Fenolite's reading of the rewrite, and the probe `altium-fpitems-kicad` is `equal`
