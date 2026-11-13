# The Python API (`fenolite.api`)

Normative text: `openspec/specs/python-api/spec.md`, `openspec/specs/design-equivalence/spec.md`
("Public equivalence API") and `openspec/specs/design-conversion/spec.md` ("Conversion verified by
equivalence"). This page lists every public name of `fenolite.api`; a name not listed here is not public.

**Stability.** Every name below is frozen for 1.0: its signature keeps its parameters, their order and their
defaults, and its return type keeps its fields. Before 1.0 a change of a frozen name is a breaking change
recorded in `CHANGELOG.md` under "Changed"; after 1.0 it needs a major version. New keyword parameters with
defaults and new fields at the end of a record may be added. The envelope that `run` returns follows the
CLI contract (`docs/cli-contract.md`, schema `fenolite.envelope.v0`).

`import fenolite` does not import `fenolite.api`, and `import fenolite.api` loads no command module: `run`
imports the dispatcher when it is called (capability package-layering, "Public API runs the commands
lazily"). Lengths are integer nanometres, as everywhere in the model.

## Every command: `run`

```python
from fenolite.api import run

reply = run("check", "board.kicad_pcb", "--stages", "drc", cwd="project")
if reply.exit_code == 5:
    for issue in reply.envelope["issues"]:
        ...
```

`run(command: str, *args: str, cwd: str | PathLike | None = None, seed: int | None = None,
timestamp: str | datetime | None = None) -> Reply` runs one command in this process, through the
dispatcher that `fenolite` runs (change c0206), and returns what `fenolite COMMAND ARGS... --json` would
print.

- **`Reply`** (frozen): `exit_code: int`; `envelope: Mapping | None`, the JSON object of stdout, `None`
  when stdout would stay empty (a usage error found before the command ran); `error: Mapping | None`,
  the JSON object of stderr (`code`, `message`, `hint`, `retryable`, `where`), `None` on exit 0. `ok` is
  `exit_code == 0`; `result` is `envelope["result"]`, or `{}`.
- **Same reply as the command line.** For every command's examples, the envelope equals the one the
  command line prints, but for `elapsed_ms` (`tests/consistency/test_api_run.py`). Read the exit code
  first, as the contract says.
- **`cwd`** is the command's working folder (default: the process's). Relative paths in `args`, and the
  paths of planned writes, are relative to it. The process's working folder is not changed.
- **`seed` and `timestamp`** stand for `--seed` and `--timestamp`; passing both a keyword and its flag
  raises `ValueError`.
- **Nothing is printed.** `run` writes nothing on `sys.stdout` or `sys.stderr`, installs no signal
  handler and starts no process of its own (a command that runs a tool, such as `check` with
  `kicad-cli`, still does). `--progress` records are dropped.
- **Terminal-only forms are usage errors** (exit 2, `FEN-2001`): `--help`, `--text`, `restore -` (no stdin
  is read) and `view --serve` (`run` does not block).
- **Python faults raise.** A `command` that is not a command name raises `ValueError`, an argument that is
  not a `str` raises `TypeError`, a `cwd` that is not a folder raises `ValueError`. Every other fault is
  in the reply, with the exit code the command line would give.

### Writing files

The mutation protocol is the command line's (`docs/cli-contract.md`, "Writing files" and "Staged plans"):

```python
planned = run("export", "board.kicad_pcb", "--out", "fab", "--all", "--dry-run", cwd=work)
plan_id = planned.result["plan_id"]  # review planned.result["plan"]
written = run("export", "board.kicad_pcb", "--out", "fab", "--all", "--confirm", "--plan", plan_id, cwd=work)
written.envelope["receipt"]  # every written file with its SHA-256
```

Without `--confirm` a writing command plans and writes nothing (exit 4, `FEN-4001`; exit 0 with
`--dry-run`). A plan id names the same staged plan for `run` and for `fenolite` in the same folder, so a
plan reviewed in Python can be written from the command line, and the other way round.

## Typed reads and analyses

These return the records of the packages that compute them, never dictionaries. None writes a file or
starts a process. A `board` argument is a `Board` or the path of a board file, a KiCad project file or a
project folder.

| Name | Returns | What |
| --- | --- | --- |
| `read_design(path, *, kicad_cli=None, timeout=300.0)` | `ReadSide` | any design that `fenolite equivalent` reads: a board or document, a KiCad project or folder, a root schematic with its sheets, a `.fenolite/` folder |
| `read_board(path)` | `Board` | a board with its board-frame pads; given an Altium edit `Session`, the board of its pending edits (`Session.pending()`, with `api.pending-edit`; change c0501) |
| `connectivity(board, *, nets=None)` | `ConnectivityReport` | the islands and open connections of each net, as `fenolite net` and `fenolite ready` count them (`docs/analyses.md`, "Open connections") |
| `islands(board, *, nets=None, without=())` | `dict[str, tuple[NetIsland, ...]]` | the counted islands of each net with their `members` (`IslandItem`: `kind`, `id`, `where`, `layers`), after leaving out the tracks, arcs, vias or zones that `without` names (model id, native id or locator; an unknown name raises `KeyError`); `docs/analyses.md`, "Open connections" |
| `analyze_current(board, *, temp_rise_mk=None, copper_thickness=None, via_plating=None, requirements=None)` | `AnalysisReport` | the current capacity of each track, arc and via, as `fenolite analyze --kinds current` |
| `analyze_distances(board, *, pairs=(), within=None, requirements=None, board_thickness=None, groove=None, insulation=False)` | `AnalysisReport` | gaps, clearance and creepage between nets (and with `insulation` the distance through the laminate), as `fenolite analyze --kinds clearance,creepage` |

- **`Board`** (frozen): `name`, `sha256`, `backend`, `design` (`fenolite.model.design.Design`), `pads`
  (`tuple[BoardPad, ...]`, `None` when the backend gives no board frame), `issues` (the reader's warnings
  and infos; it raises its errors) and `evidence` (of the reading).
- **`ReadSide`** (frozen): `name`, `sha256`, `backend`, `design`, `issues`, `evidence`, `kind` and, for
  some sides, `tool_version`, `messages`, `netlist_source`, `power_symbols`.
- `ConnectivityReport` is `fenolite.analysis.connectivity.ConnectivityReport` (`nets`, `issues`,
  `evidence`, `open_nets()`, `net(name)`, `total`); `AnalysisReport` is `fenolite.analysis.AnalysisReport`
  (`rows`, `issues`, `summary`, `evidence`, `findings()`). The rows are those of the command, in the same
  order (`tests/unit/api/test_board_api.py`).
- `requirements` is a `fenolite.analysis.requirements.Requirements`, or the path of a TOML file of schema
  `fenolite.requirements.v0` (`docs/analyses.md`). `temp_rise_mk` is in millikelvin; `copper_thickness`
  maps a copper layer to nanometres.
- Each report carries its own evidence; combine it with `Board.evidence` when you report both.

The other analyses (power, insulation alone, lengths, ties, domains, crossings, returns) take more inputs
than a short signature holds: call `run("analyze", ...)`.

## Frames and units

A board has three frames (change c0500). Scripts read the model through `read_board` and convert with a
`Frame`; no float appears in any of them.

| frame | unit | Y | origin | who uses it |
| --- | --- | --- | --- | --- |
| native | 1/10 000 mil (2.54 nm) | up | Altium's absolute zero | the raw records of a `.PcbDoc` |
| model | nm | down | the native zero | `Design`, `check`, `net`, `analyze` |
| board | nm | up | the board origin (`ORIGINX`, `ORIGINY`) | the Altium editor, `edit` sessions |

| Name | What |
| --- | --- |
| `board_frame(board)` | the `Frame` of a `Board` or a board path: for Altium the board origin with `y_up` true; for any other backend origin (0, 0), `y_up` false, so `to_board` is the identity |
| `Frame` | `origin` (the board origin in the model frame), `y_up`, and `from_native(x, y)`, `to_native(p)`, `to_board(p)`, `from_board(p)`; the two native methods raise `SideUsageError` on a non-Altium board |
| `altium_to_nm(units)`, `nm_to_altium(nm)` | native units to nanometres and back, half to even (`core.units.u_to_nm`, `nm_to_u`) |
| `format_length(nm, unit)`, `parse_length(text)` | those of `fenolite.core.units`: the display and the parse of a length |

A unit lambda such as `lambda u: u * 254 / 100` becomes:

```python
from fenolite.api import board_frame, format_length, read_board

board = read_board("board.PcbDoc")
frame = board_frame(board)
pad = board.design.board.footprints[0].position  # model frame, nm, Y down
p = frame.to_board(pad)  # what the Altium editor shows
print(format_length(p.x, "mm"), format_length(p.y, "mm"))
```

An edit session places items in the board frame: `edit.Track(start, end)` built from `frame.to_board`
matches the record it names (`tests/unit/api/test_frames_c0500.py`).

## Comparison and conversion

| Name | Returns | Page |
| --- | --- | --- |
| `equivalent(a, b, *, level=None, tolerances=None, frame=None, ignore_refs=(), profile=None, against=None, kicad_cli=None, timeout=300.0, strict=False, presentation=None)` | `EquivalenceResult` (`report`, `a`, `b` as `Side`, `profile`, `issues`, `evidence`, `to_json()`) | `docs/equivalence.md`, "The public API and the reply" |
| `convert(source, *, to, kicad_version=10, allow_lossy=False, bodies="extruded", name=None, verify=True)` | `ConversionResult` (`conversion`, `equivalence`, `explained`, ...) | `docs/conversion.md` |

Explicit `equivalent(..., level="S")` compares actual drawn schematics and resolved connectivity, with
one schematic level in the existing result shape. Integer/default requests retain their exact result
bytes. See `docs/equivalence.md` for input and option constraints.

## Route search and free channel

Change c0501. `board` is a `Board`, the path of a `.kicad_pcb`, a KiCad project or folder or a `.PcbDoc`,
or an Altium edit `Session` (its pending edits). The routing job takes the board's own rules (`design_rules`
of its backend, `ClearanceResolver` as the clearance in force) and rule areas. `start` and `end` are each
`REF-PIN`, `X,Y@LAYER` in millimetres, or a `(Point, layer)` pair. Nothing is written and no process is
started; lengths are integer nanometres.

| Name | Returns | What |
| --- | --- | --- |
| `find_route(board, *, net, start, end, width, layers=None, grid=100_000, max_states=200_000, max_vias=2, pours=None, timeout=None)` | `RouteSearch` | one connection by the bounded search of `routing.search` |
| `free_channel(board, *, net, start, end, layers=None, grid=100_000, max_states=200_000, max_vias=0, resolution=10_000, pours=None, timeout=None)` | `Channel` | the widest track that fits, bracketed by `routing.channel.widest` |

- **`RouteSearch`** (frozen): `board`, `found` (`RouteFound` or `None`), `refusal` (`RouteRefusal` or
  `None`), `issues` (`route.no-path`, `route.path-limit`, `route.repour-needed`) and `evidence`.
- **`RouteFound`** (frozen): `net`, `width`, `runs` (layer, points), `vias`, `via_diameter`, `via_drill`,
  `length`; `result(design)` gives the copper as a `RoutingResult` for `routing.merge.apply`, and
  `queue_on(session)` queues it on an Altium edit session as `clone` operations (one per segment, one per
  via; `route.via-template` and nothing queued when no via of the net has the via size) and declares the
  net's connectivity.
- **`RouteRefusal`** (frozen): `reason`, `proven`, `wall` (`WallItem`: `blocker`, `refused`) and `widest`
  (`Gap`: `a`, `b`, `free`).
- **`Channel`** (frozen): `board`, `low` (`None`: no path at the smallest width tried), `high`,
  `grid_limited`, `undecided`, `pinch` (`Gap`), `path` (`RouteFound` at `low`), `issues` and `evidence`.
- An unknown pad, net or layer raises `EndpointError` (a `SideUsageError`) with the closest names in its hint.
  See `docs/routing.md`, "Routing an existing board" and "Free channel".

## Trial edits

| Name | Returns | Page |
| --- | --- | --- |
| `trial(board, edit, *, kicad_cli=None, refill=True, gate=False, timeout=300)` (change c0209) | `TrialResult` (`board_text`, `findings`, `kept`, `dropped`, `baseline`, `edited`, `runs`, `refilled`, `tool_version`, `evidence`, `issues`) | `docs/cli-contract.md`, "Trial edits" |

`edit(design)` returns the edited design and the ids it added, removed or changed. Both copies go through
the same writer and KiCad's DRC; with `gate=True` the items that bring new findings are dropped. It needs
`kicad-cli` (`ToolMissingError` otherwise).

## Errors

The read errors are `SideError` subclasses, a `FenoliteError` with `cli_code` (the code the command would
report), `where` and `hint`:

| Error | `cli_code` | When |
| --- | --- | --- |
| `SideUsageError` (also a `ValueError`) | `FEN-2001` | no backend reads the path, a library, a file that is not a board, a bad option |
| `SideMissingError` | `FEN-3001` | the path does not exist |
| `ToolMissingError` | `FEN-6001` | no `kicad-cli` where one is needed |
| `ToolMajorError` | `FEN-6002` | a `kicad-cli` of another major than the triangle needs |
| `ExtraMissingError` | `FEN-6001` | the board's cut-outs overlap and the `geo` extra is not installed (`analyze_distances`) |

A reader's own error (`FormatError` and the other `FenoliteError`s) keeps its type and code.
