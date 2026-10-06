## ADDED Requirements

### Requirement: Complete board in an Altium build
`fenolite build --target altium` SHALL write the stack, vias, texts, graphics, keep-outs, holes, bodies and polygons of the design as `altium-pcb-writer` requires, and `result.pcb` SHALL hold `written` and `not_lowered`, each mapping a kind to a count.
- An item that is not written MUST give one `altium.not-lowered` (warning) whose `where` is `<kind>/<id>`, or `stackup`.
- A design that uses none of the new items MUST give the files it gave before this change, byte for byte.

#### Scenario: Six-layer sample
- **WHEN** `uv run pytest tests/unit/lens/test_altium_pcb_complete.py -k board6` builds the sample
- **THEN** `result.pcb.not_lowered` is empty, and the committed `tests/data/altium/board6/board6.PcbDoc` equals the built one

#### Scenario: Old samples unchanged
- **WHEN** `uv run pytest tests/unit/lens -k "altium and samples"` builds the committed samples of earlier changes
- **THEN** every file equals the committed one
