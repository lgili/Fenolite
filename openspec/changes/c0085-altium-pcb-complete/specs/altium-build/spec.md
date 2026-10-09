## ADDED Requirements

### Requirement: Complete board in an Altium build
`fenolite build --target altium` SHALL write the stack, vias, texts, graphics, keep-outs, holes, bodies and polygons of the design as `altium-pcb-writer` requires, and `result.pcb` SHALL hold `written` and `not_lowered`, each mapping a kind to a count.
- An item that is not written MUST give one `altium.not-lowered` (info, the severity the code has) whose `where` is `<kind>/<id>`, or `stackup`; a micro via gives `altium.via-unsupported` (warning) with `where` `via/<id>` instead. Without a PCB document the items stay in the model with one `altium.not-lowered` per kind, as before this change, and `result.pcb` is `null`.
- A design that uses none of the new items MUST give the files it gave before this change, byte for byte.

#### Scenario: Six-layer sample
- **WHEN** `uv run pytest tests/unit/lens/test_altium_pcb_complete.py -k board6` builds the sample
- **THEN** `result.pcb.not_lowered` is empty, and the committed `tests/data/altium/board6/board6.PcbDoc` equals the built one

#### Scenario: Old samples unchanged
- **WHEN** `uv run pytest tests/unit/lens -k "altium and samples"` builds the committed samples of earlier changes
- **THEN** every file equals the committed one

## MODIFIED Requirements

### Requirement: Copper issue codes
`lens.altium.ALTIUM_ISSUE_CODES` SHALL gain these rows. This requirement extends c0032's "Altium build issue codes", whose closed-set rule and scenarios hold for them. The lens MUST find each case before `write_pcbdoc` runs, so no `ValueError` of the writer reaches the user. The rows apply to copper of every source.

| code | severity | when |
|---|---|---|
| `altium.copper-stack` | error | the count of the board's copper layers differs from `copper`, a copper layer is named twice, or a plane names a layer that is not an inner layer or a net the design does not hold |
| `altium.copper-layer` | error | a track, arc, via or zone names a layer outside the board's copper layers |
| `altium.via-unsupported` | warning | a via is a micro via; it is not written and the build goes on (change c0085) |
| `altium.zone-unsupported` | error | a zone has fewer than three outline points (an outline kept as an opaque slot) |
| `altium.copper-invalid` | error | a track of zero length, a width of 0 or less, a drill not below its diameter, a via that does not span two different copper layers, or a net id that names no net |
| `altium.plane-copper` | error | a track or arc lies on a plane layer, or a zone on a plane layer has another net than the plane |
| `altium.copper-board-mismatch` | error | a copper source does not match the design: a component, a footprint, a pad net or the outline |
| `altium.copper-net-missing` | error | copper of a source is on a net whose name the design does not hold |
| `altium.copper-no-document` | error | a copper source is given and the PCB document is not planned |
| `altium.zones-unpoured` | info | polygons are written without poured copper |
| `altium.plane-zone-merged` | info | a zone on a plane layer with the plane's net is left to the plane |
| `altium.placement-from-board` | info | components are placed as the board of `--copper-from` places them, not as the script requests |

- One issue MUST be given per entity (per net name for `altium.copper-net-missing`), with the entity id, component path or net name in `where` and the layer or via type in the message.
- With an error the build MUST write no file, as c0032 rules. Nothing is dropped to make a document fit; a micro via is the one item left out, with its warning, whose `where` is `via/<id>`.

#### Scenario: Closed set with the copper rows
- **WHEN** `uv run pytest tests/unit/lens/test_altium_issues.py -k closed_set` runs
- **THEN** every row of this table is produced by at least one test with its severity

#### Scenario: Micro via left out
- **GIVEN** the routed model with one more via of `via_type="micro"` between `F.Cu` and `In1.Cu`
- **WHEN** `build_altium` runs
- **THEN** the files are written, `issues` holds one `altium.via-unsupported` warning whose `where` is `via/<id>`, and `result.pcb.not_lowered` is `{"via": 1}`

#### Scenario: Blind via refused
- **GIVEN** the routed model with one more via of `via_type="blind"` whose two layers are both `F.Cu` (a blind via with a span of two different copper layers is written since this change)
- **WHEN** `build_altium` runs
- **THEN** `files` is empty and `issues` holds one `altium.copper-invalid` error whose `where` is the via's id

#### Scenario: Copper on a missing layer
- **GIVEN** the routed model built with `copper=2`
- **WHEN** `build_altium` runs
- **THEN** `files` is empty and `issues` holds three `altium.copper-layer` errors: the track on `In1.Cu`, the track on `In2.Cu` and the zone

#### Scenario: Three copper layers refused
- **GIVEN** a model whose `board.layers` holds the copper layers `F.Cu`, `In1.Cu` and `B.Cu`
- **WHEN** `build_altium` runs
- **THEN** with `copper=4` `files` is empty and `issues` holds one `altium.copper-stack` that names the three layers

#### Scenario: Source without a document
- **GIVEN** a blink variant without `design.board(...)` and a `CopperSource`
- **WHEN** `build_altium` runs
- **THEN** `files` is empty and `issues` holds `altium.copper-no-document`
