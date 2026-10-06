## ADDED Requirements

### Requirement: Component bodies in the round trips
`backends.altium.roundtrip.BODY_SCOPE` SHALL name what a written component body carries of the model's body (`kind`, `height`, `standoff`, `outline`, `layer`, `name`), and RT-A2 and RT-A3 SHALL compare the kind `body` inside it, within 2 nm, exactly when bodies were written.
- The outline MUST be compared as a ring: the same points in the same order from the smallest point. `layer` MUST be compared as the layer the writer's rule gives the model's body, so a body without a layer equals its default layer.
- Only the bodies that the write reports as written are compared: `rta3.without_unwritten` MUST take the others out of the first model by the ids of `not_lowered`, as for every kind, and RT-A2 MUST do the same with the stored model. A body that was written and reads back different is a difference `…/body/<n>`.
- `AltiumBackend.model_roundtrip(path, *, compare, bodies="off")` MUST pass `bodies` to the write, and the stage `roundtrip.rta3` MUST run with `off`: the numbers of `docs/evidence/altium-roundtrip.md` do not change by this change.
- `tests/corpus/test_altium_rta3.py` MUST run every listed PCB document once more with `bodies="extruded"` and print, per document, the bodies written, the bodies not written by reason and the verdict; `docs/evidence/altium-roundtrip.md` MUST hold that table under "RT-A3", beside the table of the default.
- The evidence of a comparison of bodies MUST be `INFERRED` with `H-A-PCBX-BODY-READBACK`: Fenolite reads what Fenolite wrote.

#### Scenario: Own sample
- **WHEN** `uv run pytest tests/unit/lens/test_altium_bodies.py -k "readback or rta"` builds `body2` with `--altium-bodies extruded` and runs RT-A2 on the build and RT-A3 on `tests/data/altium/body2/body2.PcbDoc` with `bodies="extruded"`
- **THEN** both levels hold with 0 differences, three bodies are compared, and the one body of kind `model` is not in the reading and not a difference

#### Scenario: A moved vertex is caught
- **GIVEN** `body2.PcbDoc` with one vertex of one body moved by 100 units in both storages by record edit
- **WHEN** RT-A2 runs on the build
- **THEN** it reports one difference whose `where` starts with `pcb:/body/`

#### Scenario: Corpus documents with bodies
- **WHEN** `FENOLITE_REQUIRE=corpus uv run pytest tests/corpus/test_altium_rta3.py -k bodies -rA` runs
- **THEN** every document that is equal inside the scope without bodies is equal with them, the written bodies are exactly the extruded bodies with a component, and every other body is counted under the reason of "Component bodies are reported"

## MODIFIED Requirements

### Requirement: RT-A2 on a written model
For a project that Fenolite built, the level RT-A2 SHALL compare every kind of `RT_A2_SCOPE` between the stored model and the reading of the written documents: components, nets, no-connect marks, net classes, footprints, pads, tracks, arcs, vias and zones, within 2 nm.
- No kind of the scope MAY be only counted: `checks.rta2.rta2_stage` MUST compare a kind also when the stored model holds no entity of it, and its summary MUST hold no `not_in_model`.
- A built project whose stored model predates this change (`checks.rta2.predates_board`: its board holds no footprint while the PCB reading holds one) MUST skip the stage with the reason `model-predates-board` and MUST report no issue. A build that wrote no PCB document has no PCB reading and is judged on its schematic alone.
- The PCB reading MUST be compared in the frame of the stored model: when the validator is a `ModelWriter` (`backend-protocol`, "Model writers"), the pipeline calls `in_model_frame(model, reading)` before the comparison.
- A build that wrote component bodies (its summary holds `pcb.bodies == "extruded"`; change c0121) MUST also be compared in the kind `body` ("Component bodies in the round trips"); a build without them compares no body, and `RT_A2_SCOPE` itself holds no `body`.
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
