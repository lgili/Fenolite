## ADDED Requirements

### Requirement: Copper intents in the DSL
The DSL SHALL record copper as intents, plain data that the build resolves after placement, through `Part.pad`, `via_step`, `Design.track`, `Design.via`, `Design.stitch` and `dsl.copper(design)`, and MUST still import only `core` and `model`.
- `part.pad(number, *, index=None) -> PadRef` names the pads of the part with that number. `number` MUST be a non-empty `str` or an `int` (`part.pad(9)` names the same pads as `part.pad("9")`), and `index` a non-negative `int` or `None`.
- `via_step(x, y, *, to, diameter=None, drill=None) -> ViaStep` is a through via at `BOARD_ORIGIN + (x, y)` after which the track continues on the copper layer `to`.
- `Design.track(key, *path, layer="F.Cu", width=None, net=None)` takes `PadRef`s, via steps and points written as `(x, y)` pairs of lengths in the frame of `place()`. `Design.via(key, x, y, *, net, diameter=None, drill=None)` and `Design.stitch(key, *, net, pitch, along=(), region=(), origin=None, diameter=None, drill=None, clearance=None, margin=None)` take the same pairs; `origin` defaults to the corner of the board, (0, 0) in that frame. Lengths follow "DSL lengths and angles", and nets MUST be `Net` objects.
- `DslError` MUST be raised at the call for: a key that does not match `^[A-Za-z0-9_.+-]+(/[A-Za-z0-9_.+-]+)*$` or that the design already uses for copper; a track path with fewer than two elements, starting with a via step, holding an element of another type, or holding two consecutive elements at the same point; an empty `layer` or `to`; a width, diameter, drill or pitch that is not positive, or a negative margin; a stitch with both or neither of `along` and `region`, fewer than two `along` points or fewer than three `region` points.
- `dsl.copper(design)` MUST return the intents as frozen dataclasses of `dsl/intents.py`, in key order: `PadEnd(component, number, index)` with the part's component path, `ViaStep(at, layer, diameter, drill)`, `TrackIntent(key, path, layer, width, net)`, `ViaIntent(key, at, net, diameter, drill)` and `StitchIntent(key, net, pitch, along, region, origin, diameter, drill, clearance, margin)`. Points MUST be `BOARD_ORIGIN` plus their offsets, lengths `int` nanometres and nets their names. A `PadRef` of a part that is not in the design, or a net that is not in it, MUST raise `DslError` naming it.
- `fenolite.dsl` MUST re-export `PadRef`, `via_step`, `copper`, `PadEnd`, `ViaStep`, `TrackIntent`, `ViaIntent`, `StitchIntent` and `CopperIntent`, and `dsl/intents.py` is a module of the package; "DSL package" lets later requirements add both. `to_model` MUST NOT change: intents are not model objects.

#### Scenario: A track in board coordinates
- **GIVEN** the blink with `design.track("led_a", r1.pad(2), (mm(36), mm(9)), via_step(mm(36), mm(14), to="B.Cu"), d1.pad(2), width=mm(0.3))`
- **WHEN** `copper(design)` is called
- **THEN** it returns one `TrackIntent` with key `led_a`, the path `PadEnd("R1", "2", None)`, `Point(136_000_000, 109_000_000)`, `ViaStep(Point(136_000_000, 114_000_000), "B.Cu", None, None)`, `PadEnd("D1", "2", None)`, layer `F.Cu`, width `300_000` and net `None`

#### Scenario: Malformed intents fail at the call
- **WHEN** `design.track("led a", r1.pad(1), d1.pad(1))`, `design.track("k", via_step(mm(1), mm(1), to="B.Cu"), r1.pad(1))`, `design.track("k2", r1.pad(1), (1, 2))` and `design.stitch("s", net=gnd, pitch=mm(2))` are called
- **THEN** each raises `DslError`, the third naming the point argument

#### Scenario: Key order and repeated keys
- **GIVEN** a via intent `b` added before a via intent `a`
- **WHEN** `copper(design)` is called, and then `design.via("a", mm(1), mm(1), net=gnd)` is called again
- **THEN** the intents come in the order `a`, `b`, and the second call raises `DslError` naming `a`

#### Scenario: Part not in the design
- **GIVEN** a track intent from `r9.pad(1)` of a part `R9` that was never added
- **WHEN** `copper(design)` is called
- **THEN** `DslError` is raised naming `R9`

### Requirement: Copper intents in a build
`lens.build.build_design` SHALL accept the keyword-only argument `copper_intents: Sequence[CopperIntentLike] = ()` and SHALL resolve it with `copper.resolve_copper` (`manual-copper`) after placing, staging, setting layers and assigning pad nets, and before the build checks and `Design.validate()`; `cli/cmd_build.py` SHALL pass `dsl.copper(design)`.
- `unplaced` MUST be the component paths that the build staged, so an intent that ends at a staged part gives `kicad.copper.end-unplaced` and creates nothing.
- The result MUST be the built model: `BuildOutput.design` holds the script copper, the written board holds it, and with an existing board `lens.preserve.merge_layout` merges it (`layout-lens`, "Script copper in a merge").
- An error of `resolve_copper` MUST make `build_design` return no files, so `build` exits 5 and writes nothing.
- When intents are given, the envelope MUST also combine `copper.EVIDENCE` and `frame.EVIDENCE`. `result.copper` MUST report `intents`, `tracks` and `vias` (created), and `regenerated`, `stale` and `duplicates` (from the merge, 0 without an existing board).
- The extension is additive, as "Built project files" (the keyword and its step), "Build command" (`result.copper`), "Build evidence" (the two evidence rows) and "Build issue codes" (the `kicad.copper.*` and `kicad.frame.*` codes, which pass through unchanged) allow: a call without `copper_intents` MUST behave as those requirements define, and `--seed`, `--timestamp` and `PYTHONHASHSEED` MUST NOT change any file of a build with intents.

#### Scenario: Routed blink
- **WHEN** `fenolite build examples/blink_routed/design.py --out B --dry-run --json` runs for target 10
- **THEN** the exit code is 0, `result.copper` reports 4 intents, 11 tracks and 7 vias, and `read_board` of the planned board holds those tracks and vias, each with a copper uuid

#### Scenario: A copper error stops the build
- **GIVEN** a variant of `examples/blink_routed/design.py` whose track `led_drv` ends at `D1` pad `2` instead of `R1` pad `1`
- **WHEN** it is built with `--confirm`
- **THEN** the exit code is 5, `issues` hold `kicad.copper.net-conflict`, and nothing is written

#### Scenario: Intent to a staged part
- **GIVEN** a variant of the routed blink without `d1.place(…)`
- **WHEN** it is built with `--dry-run --json`
- **THEN** the exit code is 0, `issues` hold `layout.unplaced` and `kicad.copper.end-unplaced` naming `D1`, and the planned board holds no script copper ending at `D1`

#### Scenario: Reproducible routed builds
- **WHEN** `uv run pytest tests/unit/lens/test_build_copper.py -k reproducible` builds the routed blink twice for target 9 and target 10, by subprocess with `PYTHONHASHSEED=1`/`--seed 1` and `PYTHONHASHSEED=2`/`--seed 2`
- **THEN** both builds write every file with the same bytes
