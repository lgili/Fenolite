## ADDED Requirements

### Requirement: Pad zone connections in the DSL
`Part.zone_connection(number, connection, *, index=None, locked=False)` SHALL record one request for how copper zones connect to the pads of the part's footprint that carry `number`, and `dsl.pad_zones(design) -> Mapping[str, tuple[PadZoneRequest, ...]]` SHALL return the requests of every added part that has one, keyed by component path in path order, each tuple sorted by `number` and then `index`, `None` first. A part without a request has no key.
- `number` MUST be a non-empty `str` or an `int`, as in `Part.pad`. `index` MUST be `None` or a non-negative `int`: `None` names every pad that carries the number, an `int` the pad at that position among them, in the footprint's pad order.
- `connection` MUST be `"solid"`, `"thermal"`, `"none"` or `"thru_hole_only"`, the values of `Pad.zone_connection` (`design-model`). `locked` MUST be a `bool`.
- `DslError` MUST be raised at the call for another connection, for a second request for the same number and index of one part, and for a request with an index when the part already holds one for that number without an index, or the reverse: the two would name the same pad.
- `PadZoneRequest` is a frozen dataclass with `number` (a `str`), `index`, `connection` and `locked`.
- `fenolite.dsl` MUST also re-export `PadZoneRequest` and `pad_zones`, as "DSL package" allows, and the package keeps importing only the standard library, `core` and `model`. `to_model` MUST NOT change: a request is not a model object.

#### Scenario: Requests recorded
- **GIVEN** `u1.zone_connection(9, "solid")` and `u1.zone_connection("1", "none", locked=True)`
- **WHEN** `pad_zones(design)["U1"]` is read
- **THEN** it holds `PadZoneRequest("1", None, "none", True)` and then `PadZoneRequest("9", None, "solid", False)`

#### Scenario: One of several pads
- **GIVEN** `j1.zone_connection(1, "thermal", index=0)` and `j1.zone_connection(1, "solid", index=1)`
- **WHEN** `pad_zones(design)["J1"]` is read
- **THEN** it holds the two requests in index order

#### Scenario: Refused calls
- **WHEN** `u1.zone_connection(9, "direct")`, `u1.zone_connection("", "solid")`, a second `u1.zone_connection(9, "thermal")` after `u1.zone_connection(9, "solid")`, and `u1.zone_connection(9, "thermal", index=0)` after it are called
- **THEN** each call raises `DslError`, the last two naming `U1` and `9`

#### Scenario: Import edges
- **WHEN** `uv run pytest tests/unit/test_import_graph.py` runs
- **THEN** it passes with no `ALLOWED` change

### Requirement: Pad zone connections in a build
`lens.build.build_design` SHALL accept the keyword-only argument `pad_zones: Mapping[str, Sequence[PadZoneRequestLike]]`, empty by default, and SHALL apply the requests of each component to the built copy of its footprint with `fenolite.backends.kicad.zones.apply_pad_connections(instance, requests, *, issues=None) -> FootprintInstance`, after placing and before the build checks and `Design.validate()`; `cli/cmd_build.py` SHALL pass `dsl.pad_zones(design)`.
- `PadZoneRequestLike` is a structural protocol with the attributes of `PadZoneRequest`, so `zones.py` never imports the DSL.
- A request MUST set `Pad.zone_connection` of every pad it names: all pads of the footprint with that number, or the one at `index` among them. A pad that no request names keeps the value of the library footprint.
- A request whose number no pad carries, or whose index is beyond the pads that carry it, MUST give `kicad.pad.zone-unknown-pad` (error) naming the part, the number and the index; `build_design` then returns no files, so `build` exits 5 and writes nothing.
- The board writer writes the value as `(zone_connect N)` (`kicad-file-backend`, "Pad zone connection"). Nothing else of the build changes: a call without `pad_zones` MUST behave as before, and `--seed`, `--timestamp` and `PYTHONHASHSEED` MUST NOT change any file of a build with requests.
- With an existing board, `layout-lens`, "Pad zone connections across rebuilds", decides the pads of kept footprints.
- `zones.PAD_ZONE_ISSUE_CODES` MUST be the closed table of the codes of this requirement and of that one. They are `kicad.*` codes, so they pass through `BUILD_ISSUE_CODES` and `PRESERVE_ISSUE_CODES` unchanged, as "Build issue codes" allows.

| code | severity | when |
|---|---|---|
| `kicad.pad.zone-unknown-pad` | error | a request names a pad number or index that the footprint does not have |
| `kicad.pad.zone-forced` | warning | a locked request replaced the setting that a pad of a kept footprint carries |
| `kicad.pad.zone-overridden` | info | an unlocked request differs from the setting that a pad of a kept footprint carries, which stays |

- `--target altium` MUST NOT read the requests, as it does not read field requests; `docs/dsl.md` MUST say so, and MUST describe the call, the four values and the rebuild rule under "Zones".
- The evidence of the build does not change: the written child is covered by the board writer's evidence, and its effect on a fill by `H-K-ZONE-CONNECT`. That a pad which differs from its library pad only by this child raises no library mismatch in KiCad's DRC is `H-K-PAD-ZONE-LIB`.

#### Scenario: Solid exposed pad
- **GIVEN** a blink pour variant in which `d1.zone_connection(1, "solid")` is called
- **WHEN** it is built with `--dry-run --json` for target 10 and the planned board is read with `read_board`
- **THEN** the exit code is 0, pad `1` of `D1` has `zone_connection == "solid"`, its other pad has `None`, and the board text holds `(zone_connect 2)` exactly once

#### Scenario: Unknown pad stops the build
- **GIVEN** the same variant with `d1.zone_connection(7, "solid")`
- **WHEN** it is built with `--confirm`
- **THEN** the exit code is 5, `issues` hold one `kicad.pad.zone-unknown-pad` naming `D1` and `7`, and nothing is written

#### Scenario: Builds with requests are reproducible
- **WHEN** `uv run pytest tests/unit/lens/test_build_pad_zones.py -k reproducible` builds the variant twice for target 9 and target 10 with different seeds and `PYTHONHASHSEED` values
- **THEN** both builds write every file with the same bytes

#### Scenario: KiCad reports no library mismatch
- **WHEN** `uv run pytest tests/kicad/zones/test_pad_zone_requests.py` builds the variant once per connection value, with its vendored library in place, and runs `pcb drc` on 9.0.9 and on 10.0.6
- **THEN** each run writes a report that holds no `lib_footprint_mismatch` and no violation naming pad `1` of `D1`, and the probe `pad-zone-lib` records `absent` on both majors (`H-K-PAD-ZONE-LIB`)

#### Scenario: Closed code table
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_pad_zones.py -k closed_set` collects every code that `apply_pad_connections` and `keep_pad_connections` produce in their tests
- **THEN** each is a key of `PAD_ZONE_ISSUE_CODES` with the severity of this table, and every key is produced by at least one test

## MODIFIED Requirements

### Requirement: Copper intents in the DSL
The DSL SHALL record copper as intents, plain data that the build resolves after placement, through `Part.pad`, `via_step`, `arc_to`, `Design.track`, `Design.via`, `Design.stitch` and `dsl.copper(design)`, and MUST still import only `core` and `model`.
- `part.pad(number, *, index=None) -> PadRef` names the pads of the part with that number. `number` MUST be a non-empty `str` or an `int` (`part.pad(9)` names the same pads as `part.pad("9")`), and `index` a non-negative `int` or `None`.
- `via_step(x, y, *, to, diameter=None, drill=None, kind="through") -> ViaStep` is a via of `kind` (`through`, `blind`, `buried` or `micro`) at `BOARD_ORIGIN + (x, y)` after which the track continues on the copper layer `to`.
- `arc_to(mid, end) -> ArcStep` is an arc from the point of the path element before it through `mid` to `end`, both `(x, y)` pairs of lengths in the frame of `place()`; the path continues from `end`.
- `Design.track(key, *path, layer="F.Cu", width=None, net=None)` takes `PadRef`s, via steps, arc steps and points written as `(x, y)` pairs of lengths in the frame of `place()`. `Design.via(key, x, y, *, net, diameter=None, drill=None, kind="through", layers=None)`, whose `layers` are the two copper layer names of a via that is not a through via, and `Design.stitch(key, *, net, pitch, along=(), region=(), origin=None, diameter=None, drill=None, clearance=None, margin=None)` take the same pairs; `origin` defaults to the corner of the board, (0, 0) in that frame. Lengths follow "DSL lengths and angles", and nets MUST be `Net` objects.
- `DslError` MUST be raised at the call for: a key that does not match `^[A-Za-z0-9_.+-]+(/[A-Za-z0-9_.+-]+)*$` or that the design already uses for copper; a track path with fewer than two elements, starting with a via step or an arc step, holding an element of another type, or holding two consecutive elements at the same point, the point of an arc step being its `end`; an arc step whose `mid` equals its `end`; a `kind` outside the four; `layers` given for a `through` via, or anything but two different non-empty layer names for another kind; an empty `layer` or `to`; a width, diameter, drill or pitch that is not positive, or a negative margin; a stitch with both or neither of `along` and `region`, fewer than two `along` points or fewer than three `region` points.
- `dsl.copper(design)` MUST return the intents as frozen dataclasses of `dsl/intents.py`, in key order: `PadEnd(component, number, index)` with the part's component path, `ViaStep(at, layer, diameter, drill, kind="through")`, `ArcStep(mid, end)`, `TrackIntent(key, path, layer, width, net)`, `ViaIntent(key, at, net, diameter, drill, kind="through", layers=None)` and `StitchIntent(key, net, pitch, along, region, origin, diameter, drill, clearance, margin)`. Points MUST be `BOARD_ORIGIN` plus their offsets, lengths `int` nanometres and nets their names. A `PadRef` of a part that is not in the design, or a net that is not in it, MUST raise `DslError` naming it.
- `fenolite.dsl` MUST re-export `PadRef`, `via_step`, `arc_to`, `copper`, `PadEnd`, `ViaStep`, `ArcStep`, `TrackIntent`, `ViaIntent`, `StitchIntent` and `CopperIntent`, and `dsl/intents.py` is a module of the package; "DSL package" lets later requirements add both. `to_model` MUST NOT change: intents are not model objects.

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

#### Scenario: Arc step recorded
- **GIVEN** the blink with `design.track("bend", (mm(10), mm(10)), arc_to((mm(11), mm(11)), (mm(10), mm(12))), (mm(10), mm(15)), net=gnd, width=mm(0.25))`
- **WHEN** `copper(design)` is called
- **THEN** the path of the `TrackIntent` holds `Point(110_000_000, 110_000_000)`, `ArcStep(Point(111_000_000, 111_000_000), Point(110_000_000, 112_000_000))` and `Point(110_000_000, 115_000_000)`

#### Scenario: Via kinds recorded, earlier calls unchanged
- **GIVEN** a track whose path holds `via_step(mm(5), mm(5), to="In1.Cu", kind="blind")`, the via `design.via("core", mm(8), mm(8), net=gnd, kind="buried", layers=("In1.Cu", "In2.Cu"))`, and the track `led_a` of "A track in board coordinates"
- **WHEN** `copper(design)` is called
- **THEN** the first step has `kind == "blind"`, the via intent has `kind == "buried"` and `layers == ("In1.Cu", "In2.Cu")`, and the via step of `led_a` still equals `ViaStep(Point(136_000_000, 114_000_000), "B.Cu", None, None)`

#### Scenario: Refused arc and via calls
- **WHEN** `design.track("k", arc_to((mm(1), mm(1)), (mm(2), mm(0))), r1.pad(1))`, `arc_to((mm(1), mm(1)), (mm(1), mm(1)))`, `via_step(mm(1), mm(1), to="B.Cu", kind="laser")`, `design.via("v", mm(1), mm(1), net=gnd, layers=("F.Cu", "B.Cu"))` and `design.via("w", mm(1), mm(1), net=gnd, kind="blind")` are called
- **THEN** each raises `DslError`, the last naming `layers`
