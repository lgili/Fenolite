## MODIFIED Requirements

### Requirement: Altium write of a model
`AltiumBackend.write(design, *, target=None, allow_lossy=False, rewrite=False)` SHALL accept a `Design` that holds a circuit and a board and SHALL return a `lower.ProjectWrite`: the files of an Altium project by name (the PCB document, and the schematic, its libraries and the project file), the issues of the write and the inputs they were written from. It is `backends.altium.lower.write_design(design, allow_lossy=…, rewrite=…)`, which goes through `lower.from_design`.
- The placements, pads, copper, zones, rules, stack and classes MUST come from the model; no script, library path or other file is read.
- What the model holds and the writers cannot carry MUST be reported once per kind with `altium.not-lowered`, whose `where` is the kind. A loss of an item of `lower.LOSS_KINDS` (a footprint, a pad, a track, an arc, a via, a zone, a net, a net class, a shape on copper, an internal plane) is a warning and MUST need `allow_lossy`: without it the write raises `lower.LossyWriteError` (`FEN-7001`) with those issues. Every other loss is an info.
- `rewrite` (change c0128) is the caller's statement that `design` is the reading of an Altium document and that the write gives the document back; it is an argument, and the write does not infer it from the design. With it, a value that a document Altium saved holds and that a build refuses is written as it was read: today one, a via whose drill equals its diameter (`altium-pcb-writer`, "Imported boards are written from the model"). `AltiumBackend.model_roundtrip` passes `True`; `lens.altium.write_model` and `fenolite build --target altium` never do. `rewrite=True` for a design whose board was not read from an Altium document MUST raise `ValueError`.
- `target` MUST be `None`: the Altium writers have one form, and any other value raises `ValueError`.
- The write MUST be deterministic: two calls on equal designs give equal bytes.
- When the schematic writer refuses the circuit (a text that no record holds, one pin on two nets), the PCB document MUST still be written, and one `altium.not-lowered` info with `where` `schematic` says why the schematic and the project file are not.
- The model holds no corner ratio of a rounded-rectangle pad. A pad read from an Altium document carries its corner percentage in its `altium` bag, which `from_design` reads; a pad read from a KiCad board keeps the ratio in KiCad's own bag, which a backend does not read. `lens.altium.write_model(design, allow_lossy=…)` is the write of such a design: it reads the ratios (`lens.altium.corner_ratios`) and passes them to `lower.write_design(…, corner_ratios=…)`. Without a ratio a rounded-rectangle pad is not written and counts as a lost pad; no ratio is guessed.
- The write is experimental: `capabilities()` of the backend names no write kind and lists no `write` operation (`altium-import`, "Altium backend").
- The write runs no check of the board: the copper guard of `fenolite build --target altium` (change c0088, "Copper guard of an Altium build") belongs to the build command, so a model with a short is written as it is. `fenolite check` on the written documents judges it.
- `fenolite build --target altium` does not go through this write (`altium-build`, "Stored board of an Altium build"): it stores the board it wrote, and writing that stored model gives a PCB document that reads to the same model.

#### Scenario: A KiCad board written as Altium documents
- **GIVEN** the routed two-layer KiCad sample `tests/data/kicad/board/two_layer.kicad_pcb`, read with the KiCad backend
- **WHEN** `lens.altium.write_model(design)` runs and the written PCB document is imported
- **THEN** the imported design is equal to the KiCad design at levels 1 to 5 of `equivalent`, in the relative frame and within 2 nm, the written unit

#### Scenario: Build and write agree
- **WHEN** `uv run pytest tests/unit/backends/altium/test_lower.py -k build_agrees` builds the routed blink and writes its stored model with `write_model`
- **THEN** the PCB document of the build and the one of the write read to equal models inside the written scope, the stored model equals the reading of the write in its own frame, and the two files are not equal byte for byte (the build writes the graphics of the library footprints)

#### Scenario: Rewrite is the caller's word
- **GIVEN** the reading of `tests/data/altium/routed/routed.PcbDoc` with the drill of one via set to the via's diameter
- **WHEN** `AltiumBackend().write(design)` runs, then `write(design, allow_lossy=True)`, then `write(design, rewrite=True)`
- **THEN** the first raises `LossyWriteError` with one `altium.not-lowered` warning whose `where` is `via`, the second counts one via as not written, and the third writes every via and reports no issue for `via`

#### Scenario: A loss needs allow_lossy
- **GIVEN** the design read from `tests/data/altium/blink/blink.PcbDoc` with one pad given the shape `custom`
- **WHEN** `AltiumBackend().write(design)` runs, and again with `allow_lossy=True`
- **THEN** the first raises `LossyWriteError` with one `altium.not-lowered` warning whose `where` is `pad`, and the second writes a PCB document with 35 pads and counts one pad as not written
