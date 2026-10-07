# Routing

Fenolite treats routers as local plugins. `fenolite.routing` defines plain-data jobs and results, the
`fenolite.routers` entry-point group discovers implementations, and the command merges only routed
tracks, arcs and vias back into Fenolite's board. A plugin reports whether it sends design data off
the machine; `fenolite route` requires explicit permission for such a router. Route results are
`UNVERIFIED`: run `fenolite check` to judge the board.

## Built-in routers

- `direct` joins a two-pad net with a straight segment. It avoids no obstacles and is intended for
  hermetic tests and small examples.
- `kicadroutingtools` runs KiCadRoutingTools from a separate checkout as a subprocess. Fenolite does
  not install or import it. Install the pinned `v0.22.1` checkout and build its Rust router with
  `python build_router.py`; keep its dependencies in an environment separate from Fenolite. Set
  `FENOLITE_KRT` to the checkout and `FENOLITE_KRT_PYTHON` to the interpreter that has the tool's
  dependencies. The pinned commit and platform-specific setup are recorded in
  [routing evidence](evidence/routing.md).

- `freerouting` runs [Freerouting](https://github.com/freerouting/freerouting) 2.4.1, a GPL-3.0 autorouter,
  as a subprocess. Fenolite does not bundle or import it, and downloads it only when you ask:
  `fenolite fetch freerouting --confirm`. It is the only router that needs no
  KiCad file: Fenolite writes a Specctra design file of its own from the model and reads the session
  Freerouting writes back (`fenolite.backends.specctra`, [format notes](formats/specctra/dsn.md)).
  See [Freerouting](#freerouting) below.

Discover routers with `fenolite capabilities --json`; `fenolite doctor --json` checks their local
availability. Route with `fenolite route BOARD --router NAME --dry-run`, inspect the plan, then rerun
with `--confirm` to write. `--nets` may be repeated with glob patterns; `--rip` permits the selected
unlocked copper to be replaced. Routed files from external tools are read for copper only, then
Fenolite's writer produces the board.

## Freerouting

**Install.** Let Fenolite fetch the pinned jar:

```
fenolite fetch freerouting --dry-run
fenolite fetch freerouting --confirm
```

- `--dry-run` shows the file, its size, its SHA-256, its address and its licence (GPL-3.0), and makes no
  request. `--confirm` downloads `freerouting-2.4.1.jar` from the project's release page, checks its size
  and its SHA-256 against the values recorded in [routing evidence](evidence/routing.md), and writes it
  only when both match. No other command downloads anything
  ([ADR-0007](adr/0007-fetching-external-tools.md)), and no design data is sent.
- The jar goes to the **tools folder**, outside your project, where `route --router freerouting` finds it:

  | platform | folder |
  |---|---|
  | any, when `FENOLITE_TOOLS_DIR` is set (an absolute path) | that folder |
  | any, when `XDG_CACHE_HOME` is set | `$XDG_CACHE_HOME/fenolite/tools` |
  | macOS | `~/Library/Caches/fenolite/tools` |
  | Windows | `%LOCALAPPDATA%\fenolite\tools` |
  | elsewhere | `~/.cache/fenolite/tools` |

  The jar is `freerouting/freerouting-2.4.1.jar` in it. It is a cache entry: delete it and fetch it again.
- On a machine without a network, download the jar another way and run
  `fenolite fetch freerouting --from FILE --confirm`: the same size and digest are checked.

**Install by hand** (the second way). Download `freerouting-2.4.1.jar` from the project's release page
yourself, check its SHA-256 against the one the release lists (recorded in
[routing evidence](evidence/routing.md)), keep it outside your project, and set `FENOLITE_FREEROUTING_JAR`
to it, or pass `--router-path JAR`. Both win over the tools folder.

Freerouting 2.4.1 needs **Java 25** or newer: `java` on `PATH`, or `FENOLITE_JAVA`. `fetch` does not
install it. `fenolite doctor --json` reports the jar, where it came from (`source`: `argument`, `env` or
`fetched`), its version and the Java major in the `freerouting` entry of `result.routers`.

**Run.**

```
fenolite route BOARD --router freerouting --allow-offsite --dry-run
```

- The board needs a closed outline: a design file cannot be written without one.
- Every component is written locked in place, and the copper already on the board is written as protected;
  the router adds copper and removes none. Only the copper of the selected nets is taken from its session.
- `--router-option max-passes=N` sets the number of autorouter passes (default 20). `--timeout SECONDS`
  bounds the run (default 900 for this router). No other option is passed on.
- The route is a proposal (`UNVERIFIED`): run `fenolite fill` and `fenolite check` afterwards.
- Net-class widths, clearances and vias reach the router; custom rules of the model do not, so KiCad's DRC
  stays the judge of every route.

**Data leaving your machine.** Freerouting sends anonymous usage data unless told otherwise. Fenolite always
passes the flag that disables it (`-da`), runs the tool in a temporary folder that is also its `HOME`, and
never uses its hosted API. A run of the pinned image with the network disabled routes a board
(`H-G-DSN-OFFLINE`, recorded on 2026-10-04), so `fenolite capabilities` lists this router with
`sends_data_offsite: false` and `fenolite route` does not ask for `--allow-offsite`.


**Net classes and open connections.** `fenolite route` reads the net classes from the project file beside
the board (a KiCad board holds none), so each net is routed with the track width, clearance and via size of
its own class. A net that Freerouting reports with unrouted connections is listed under `unrouted` even
when it has copper; run `fenolite check` afterwards, where KiCad's DRC is the judge.

`--router-path docker:<image>` runs a container image of Freerouting instead of a local
jar, with the run folder mounted and `--network none`; Fenolite never pulls the image.

## Loop order

Use `build` → `place` → `route` → `fill` → `check`. Routing changes copper inputs used by a fill, so
refill after routing. Later builds keep routed tracks and vias whose nets remain in the design.

## Tool smoke job

The optional `routing` CI job runs the pinned tool and oracle smoke tests on KiCad 9.0.9 and 10.0.6.
It downloads external code and a router binary, so it is informative evidence rather than a required
merge check. It runs the feasibility probes and the `build` → `place` → `route` → `fill` → `check`
loop on each target. It also installs Java 25 and the pinned Freerouting jar, checked against its SHA-256,
and runs the Freerouting probes and the same loop with `--router freerouting`.
