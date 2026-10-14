## MODIFIED Requirements

### Requirement: Stored board of an Altium build
An Altium build that writes a PCB document SHALL store in `.fenolite/board.json` the board that it wrote: `backends.altium.lower.stored_board(model, spec)` gives the board of the script's model with one `FootprintInstance` per placed component and the copper of the document, in the frame of the script.
- A footprint MUST hold the component's id, the footprint link, the placement (position, rotation, side, locked) and the pads that the document holds, in the footprint frame of the model: the position is the written position taken back through the placement without a mirror, the angle is relative to the footprint, the layers are those the pad lies on (a pad of a bottom-side component names the bottom layers), and `net_id` is the id of the net of the design. A rounded-rectangle pad MUST hold `corner_ratio`, 5 000 ppm per written percent, and keeps the extension bag of its library definition. The footprint MUST hold the graphics that the document holds, in the pad frame and in the written form: a rectangle is its four lines in the writer's order.
- The tracks, arcs and vias MUST be those of the document with the net ids of the design. A zone MUST be one entity per written polygon (a zone on two layers is two), without fills.
- The outline, the layers, the stack-up, the texts, graphics, keep-outs, holes, the drawing sheet reference and the title block of the script's board MUST be kept as they are.
- Ids MUST be derived from the component's id and the entity's place, so two builds of one script store equal texts.
- A build that writes no PCB document MUST store the script's board unchanged. No project file of a build changes: the committed samples keep their bytes.
- The build goes through `lower.from_design` ("Altium build through the lowering"). The stored board is still made from the written specification, so it holds what the document holds, and it is the only file of a build that change c0126 changes.

#### Scenario: Stored board of the routed blink
- **WHEN** `uv run pytest tests/unit/backends/altium/test_lower.py -k build_agrees` builds `examples/blink_routed/design.py` and loads `.fenolite/`
- **THEN** the stored board holds the footprints and the tracks of the PCB document, its three footprints hold the 27 lines and arcs of the document, and the samples under `tests/data/altium/` keep their bytes (`uv run pytest tests/unit/lens -k "altium and (samples or golden)"`)

## ADDED Requirements

### Requirement: Altium build through the lowering
`lens.altium.build_altium` SHALL make its PCB document with `backends.altium.lower.from_design(model, issues=…, options=…)`: the one lowering of a model. `lens.altium.pcb_document` and `lens.altium.corner_ratios` MUST no longer exist.
- Before the lowering, `lens.altium.place_footprints` MUST give the model's board one `FootprintInstance` per component with a written footprint: the placement of the script or the staged place ("PCB document output"), and the pads and graphics that `pcblib.check_footprint` keeps of the library definition, in the pad frame, a bottom footprint mirrored and on the bottom layers. A rounded pad gets `corner_ratio = 5000 · pcbrecords.corner_percent(ratio)`, the value that is written. Pad nets come from the circuit through the pin-to-pad map.
- The copper of the script, or of a copper source, MUST be put into the model's board (tracks, arcs, vias, zones and the copper layers) before the lowering, which writes it as it writes the copper of any model.
- `lower.LowerOptions` MUST hold what a build decides and a model does not: the name of the files, the footprints of `<name>.PcbLib` (`library`: a component's pattern is the name of its definition there, its library file `<design>.PcbLib` for a KiCad link and its symbol library `<design>.SchLib`), the sheet mode (a component on a module sheet links through the sheet symbols of its module), the copper layers and the planes that the lens checked, and the form of the body records. The schematic form, the directions, the drawing sheets and the output job stay arguments of `project.write_project`: the output job is made from the stack of the lowered document, so it cannot be an option of the lowering (design, "Found on 2026-10-08", 12). With `options=None` the lowering is the write of a model of `altium-pcb-writer`, "Imported boards are written from the model".
- **No project file changes.** Every file that a build wrote before this change MUST hold the same bytes, and `result` of `fenolite build --target altium`, its `result.pcb` and its issue list MUST be unchanged. The one file that changes is `.fenolite/board.json` ("Stored board of an Altium build").
- A build of a model whose components have no footprint definition (an Altium footprint link) writes no PCB document, as before.
- If a field of the PCB document's specification cannot be given by a model and these options, the build MUST keep its former path, and the change MUST say which field under "Found" in its design: no field is approximated to make the paths meet.

#### Scenario: The two paths give one specification
- **WHEN** `uv run pytest tests/unit/backends/altium/test_lower_build_spec.py` builds every script under `examples/` in both sheet modes, on the commit before the switch
- **THEN** the `PcbDocSpec` of `pcb_document` and the one of `from_design` with the build's options are equal field by field in everything a record is written from (every field of the specification and of a placed component; of a placed footprint its pattern and the pads and graphics that `pcblib.check_footprint` keeps, without their ids, bags and provenance, with the corner percentage and the net of each pad), with no listed exception, and `pcbdoc.write_pcbdoc` gives the same bytes for both. The ids of the entities of a placed footprint are not compared: an instance's pads have ids of their own (design, "Found on 2026-10-08", 1). After the switch, which removes `pcb_document`, the test holds the SHA-256 of each example's PCB document as the former path wrote it, and the build through the lowering MUST write the same bytes from the specification it lowered

#### Scenario: Committed samples keep their bytes
- **WHEN** `uv run pytest tests/unit/lens -k "altium and (samples or golden)" tests/unit/cli/test_build_altium.py tests/unit/lens/test_altium_issues.py` runs after the switch, with no edit of those tests
- **THEN** every test passes: no file under `tests/data/altium/` changes

#### Scenario: Pins move by the stored board alone
- **WHEN** `uv run pytest tests/unit/lens/test_build_bytes_pinned.py -k altium` runs after the switch
- **THEN** for each of the ten entries of the `ALTIUM` table the digest of the files outside `.fenolite/` is the one measured before this change, and the entry is changed with the reason "`.fenolite/board.json` holds the footprint graphics and corner ratios (c0126)"
