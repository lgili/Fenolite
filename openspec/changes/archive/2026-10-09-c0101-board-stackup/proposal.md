## Why

A complex board is ordered with a stack-up: copper thickness per layer, dielectric heights and materials, solder mask, finish, total thickness. Fenolite has the types (`Stackup`, `StackLayer`), but no KiCad reader fills them, no KiCad writer writes them and no script declares them (`origin/dev` at `9aba2dff`). The review of 2026-10-05 of the gaps to a complex board found that a built board's Gerber job file states KiCad's default stack-up and the finish `None` as the design's, and that `analyze` must be told the thickness; its proposals are milestone v0.4 (`docs/roadmap.md`, "v0.4: proposals on other branches"). Only the Altium side uses the types today: the Altium import fills them, and c0085's writer takes the document's stack values from them.

Measured on `kicad-cli` 10.0.6 and 9.0.9 (design, Context; 2026-10-05, on the branch where this proposal was written, not repeated on `dev`):

- KiCad uses a `(stackup …)` node only when its rows name the board's silkscreen, paste, mask and copper layers, with one dielectric row between neighbouring copper rows. Otherwise the job file states no thickness, silently.
- The job file takes `BoardThickness` from `(general (thickness …))`, IPC-2581 from the sum of the rows.
- Both majors write the same job file for the same node, on 2 to 8 copper layers.

## What Changes

- **Model.** `StackLayer.dielectric_kind` (`core` or `prepreg`), `StackLayer.color`, `Stackup.impedance_controlled`; `thickness()`, `depth()`, `between()`; three `model.stackup-*` findings.
- **Reading.** `read_board` projects a stack-up that KiCad uses into `Board.stackup`; `setup` stays an opaque slot. Warnings name a node KiCad ignores and a thickness that differs from the sum.
- **Writing.** Created boards get the complete node, missing rows added from the layer table, and `general` thickness equal to the sum. A read board's node is rewritten only when the model changed.
- **Script.** `design.stackup(stack.mask(…), stack.copper("35um"), stack.prepreg(…), …, finish="ENIG")`, checked at the call.
- **Rebuilds.** The board's stack-up wins over an unlocked script stack-up, as for zones; `locked=True` replaces it.
- **Outputs.** `analyze` says where its thicknesses came from; `export` notes a job file with KiCad's default; `inspect` shows the stack-up.
- **Altium.** A stack-up with masks, sheets and stated kinds reaches the Altium document: masks are passed over, a stated `core` or `prepreg` is written, a gap of several sheets falls back to the default values with `altium.not-lowered`, and values without a key in the document are named once.
- **Presets** from public fabricator pages, each with URL and date (cut first); their source ids are S-0720 to S-0722 (corrected on 2026-10-08 from S-0620 to S-0622, design Decision 12).

Size: 9 design-days; 7.25 after the cuts of the design.

## Prerequisites

- Release 0.3.0 is out, with c0085, c0090 and c0126 archived: the Altium requirement of this change is worded on c0085's stack ("Layer stacks of any even count"), the round-trip tests of c0090 run on the new model fields, and c0126 gives the convention and the 0.2.0 fixture for additive model keys.
- c0100 is on `dev`: six and eight layers, `Design.copper_layers`, and its text of "Created board header", on which this change regenerates its delta.
- c0096, c0097 and c0099 are not touched.
- This change lands before c0102 (stack-up reset on a count change), c0103 and c0112 (shared requirements, order in the design, Decision 13), c0105, c0106, c0115, c0116 and c0117.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `design-model`: ADDED "Stack-up in the board model".
- `kicad-file-backend`: MODIFIED "Modelled board content", "Created board header", "Projected fields on write"; ADDED "Stack-up on boards", "Stack-up written to boards".
- `kicad-oracle`: ADDED "Stack-up job file parity".
- `design-dsl`: ADDED "Stack-up in the DSL", "Stack-up in a build", "Stack-up presets".
- `layout-lens`: ADDED "Stack-up across rebuilds".
- `board-analyses`: ADDED "Stack-up thicknesses in analyze".
- `manufacturing-exports`: ADDED "Stack-up note in exports".
- `cli-contract`: ADDED "Stack-up in inspect"; MODIFIED "Export command" (an info does not stop the writes; on c0084's delta).
- `altium-build`: ADDED "Stack-ups with masks, sheets and kinds in an Altium build".

## Non-goals

- Impedance targets: c0105. Length through vias: c0106. Stack-up table on a drawing: c0117. IPC-2581 and ODB++: c0116. Six and eight layers from a script: c0100.
- Rigid-flex sub-stacks, coverlay, via spans, back-drill, and modelling edge connector, castellation and edge plating (kept as read): nowhere in v0.4, because no yardstick item needs them.
- No new Altium record or key: mask thickness, colours, the finish and the impedance flag have no recorded key in the Altium document and are named by one `altium.not-lowered`; the Altium import does not fill the new fields. Joining the sheets of one gap into one Altium dielectric: nowhere for now (open question).
- No ounce unit and no material values: nowhere, because the user gives every number (plan D6).

Limits: a board without a stack-up has no thickness in the model; a mask the script omits is written 0 thick; at most three presets; the export note covers `gerbers` only; KiCad's job file is the oracle, no fabricator checks it.

## Evidence level required

- `H-K-STACKUP-JOB`, `-COMPLETE`, `-DEFAULT`: `KICAD-VERIFIED (9.0.x, 10.0.x)` by probes; `H-K-STACKUP-RESAVE`: `KICAD-VERIFIED (10.0.x)` (9.0.9 has no `pcb upgrade`).
- Model, script and merge: mechanical. `analyze` stays `INFERRED`; presets `INFERRED`, sourced. The Altium part is mechanical on existing format facts (`DIELTYPE`), and the evidence of the Altium build does not rise.

## Impact

- New: `backends/kicad/stackup.py`, `dsl/stack.py`, preset data, tests, one board fixture (declared in `tests/data/MANIFEST.toml`).
- Changed: `model/board.py`, `model/design.py`, `backends/kicad/pcb.py`, `dsl/design.py`, `dsl/convert.py`, `lens/build.py`, `lens/altium_copper.py`, `backends/altium/lower.py`, four commands, `cli/data/explain.toml`, the board schema, docs.
- A read board with a node gains `Board.stackup`; its `.fenolite/board.json` changes once.
- Three model keys are added (`dielectric_kind`, `color`, `impedance_controlled`). Documents written before load unchanged; release 0.2.x cannot read a document that carries one of them, because its reader refuses an unknown key.
