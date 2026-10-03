## Context

- **Scope.** Plan item 0016 (plan D11): `fenolite.routing.Router` is a protocol, `route(job: RoutingJob) -> RoutingResult`; plugins register in the entry-point group `fenolite.routers`; `routing.plugins.<x>` may import `backends.<x>`, the protocol may not. v0.1 ships two plugins; this change has the first (KiCadRoutingTools), and c0023 the second (Freerouting through Specctra). Placement went to c0022.
- **Layering.** `package-layering` already has the rows `routing` (may import `model` and `geometry`) and `routing.plugins.<x>` (may import `routing` and `backends.<same>`). A plugin for KiCad files therefore lives in `routing/plugins/kicad/`.
- **The tool (S-0215 to S-0217, read 2026-10-03).**
  - Repository `drandyhaas/KiCadRoutingTools`, licence MIT. Latest tag v0.22.1 (2026-09-17); about 40 tags since December 2025.
  - A grid A* router, octilinear, multi-layer with vias and rip-up; the search core is Rust, the rest Python 3.9+. Dependencies: numpy, scipy, shapely (Pillow for rendering only). No pip package: a checkout plus `python build_router.py`, which downloads a prebuilt binary or builds with cargo.
  - It parses and writes `.kicad_pcb` itself; KiCad's `pcbnew` module is needed only by its GUI plugin. The README states "Compatible with KiCad 9 and KiCad 10".
  - Command: `python py_router/route.py input.kicad_pcb [output.kicad_pcb] [OPTIONS]`; without an output name it writes `input_routed.kicad_pcb`; `--overwrite` edits in place. `--nets` takes globs with `!` exclusions. `--track-width`, `--clearance`, `--via-size`, `--via-drill` and `--grid-step` have defaults, and clearances and via sizes come from the board's net classes when the flags are omitted. `--layers` defaults to all copper layers.
  - Existing tracks are obstacles and are left alone unless `--rip-existing-nets` is given; locked copper is never ripped. Keep-out areas and `Edge.Cuts` cut-outs are honoured. Zones it creates are not filled; its README recommends `kicad-cli pcb drc --refill-zones`.
  - Determinism is not stated anywhere in its documentation. Its documented limits: no push-and-shove, no blind or buried vias.
- **What exists in Fenolite.** `model.board.Track(start, end, width, layer, net_id)`, `Arc`, `Via(position, diameter, drill, layers, net_id, via_type)`; c0017's writer for 9.0 and 10.0; c0019 keeps every track and via of a net the design still has ("Copper items follow their nets"), so routed copper survives rebuilds; c0028's `BoardFrame.board_pads` gives pads in the board frame; c0013's `projectset.project_set` names the project files next to a board; c0020 turns DRC violations and unconnected items into located issues.
- **The loop order** is `build` → `place` → `route` → `fill` → `check`: routing changes the inputs of a fill, so c0019 drops fills after it (`zone.fill-stale`) and `fill` runs next.
- **CLI consistency.** Every command's `example_args` must exit 0 with no subprocess, and a mutating command's `mutation_example_args` must write its files in an empty folder (living `cli-contract`, "Consistency test covers every command").
- **Constraints.** `pyproject.toml` `dependencies` stays empty; the tool is never imported, vendored or installed by Fenolite. The roadmap gives this change 6 days.

## Goals / Non-Goals

**Goals:**
- `fenolite route PATH --router kicadroutingtools --confirm` routes the unrouted nets of a board and writes it for its own major, with every non-copper byte of content kept by Fenolite's writer.
- A router is a plugin: adding one needs no change in `routing`'s protocol or in the command.
- The feasibility gate gives a recorded yes or no on whether KiCadRoutingTools covers v0.1's acceptance item 3 on both majors.
- Tests and examples need no external tool.

**Non-Goals:**
- Everything under "Non-goals" in the proposal.
- Passing tuning options of a router through the command beyond a generic `--router-option KEY=VALUE`.

## Decisions

1. **Feasibility gate first.** Task group 2 runs KiCadRoutingTools at the pinned tag on the built blink for targets 9 and 10, from a small script that uses only `write_board`, `read_board` and `subprocess`, and pins four facts as probes run where the tool is present: its arguments and outputs (`krt-cli`), the routed blink under `kicad-cli` (`krt-route-t9`, `krt-route-t10`), what it changes besides copper (`krt-keep`), and two runs compared (`krt-repeat`).
   - **Gate.** Passed when `krt-route-t9` and `krt-route-t10` record `equal`: 0 unconnected items after the route, and no violation of severity error that the unrouted board lacks, on the major the board targets.
   - **If it fails on a major**, the row is refuted with a successor, the plugin reports the nets it could not route, and c0023 stays in v0.1 (roadmap, "Proposed cuts"). The protocol, the command and `direct` still land.
   - The probes are recorded in `docs/evidence/routing.md` and, when the `routing` job has run them, in a results file of their own (`docs/evidence/routing/krt-<tag>.json`), never in `docs/evidence/kicad/probes/`: those files must stay reproducible with `kicad-cli` alone.

2. **A job is plain model data.** `routing.protocol`:
   - `JobPad(ref, number, net, position, layers, drill)`;
   - `JobNet(name, net_id, pads, width, clearance, via_diameter, via_drill)`, the four lengths from the net's class, else the board defaults the command passes;
   - `RoutingJob(design, nets, layers, options)`: the model, the nets to route, the copper layer names in stack order, and a `Mapping[str, str]` of router options;
   - `RoutingResult(tracks, arcs, vias, routed, unrouted, issues, tool, tool_version, log, evidence)`, with `tracks`, `arcs` and `vias` as model entities whose `net_id` is set;
   - `Router`, a `Protocol` with `name`, `description`, `sends_data_offsite: bool`, `available() -> RouterStatus` and `route(job) -> RoutingResult`.
   - `routing` cannot import `backends.base`, so the command builds `JobPad`s from `BoardFrame.board_pads` and passes them in.
   - `RoutingResult.evidence` is `UNVERIFIED` for every router: a route is a proposal, and KiCad's DRC is the judge (plan, appendix B).
   - Rejected: a file path in the job. A file is one backend's form; the model is what every router plugin can be given.

3. **Registry.** `routing.registry.routers() -> Mapping[str, Router]` loads the entry points of group `fenolite.routers` with `importlib.metadata`; `pyproject.toml` declares `direct` and `kicadroutingtools`. A plugin whose import fails is listed as unavailable with the error text, never raised. Names are unique; a duplicate from another distribution is ignored with a warning in `doctor`.
   - Rejected: a hard-coded table. Third-party routers are the point of the protocol.

4. **Net selection.** `routing.select.unrouted(design, *, patterns=("*",), include_zone_nets=False) -> tuple[str, ...]`:
   - a net is a candidate when it has two or more pads and no track, arc or via of its own;
   - a net that has a zone is skipped unless `include_zone_nets`, because a pour connects it (`route.zone-net-skipped`, info);
   - `patterns` are `fnmatch` globs on net names, `!` excluding;
   - `rip=True` in the command first removes the unlocked tracks, arcs and vias of the selected nets (c0031's `locked` on copper, when present), so they become candidates.
   - This is a selection rule, not a connectivity analysis: a half-routed net is not a candidate. `check` reports what stays unconnected.

5. **Merge.** `routing.merge.apply(design, result) -> Design` appends the result's tracks, arcs and vias to the board, after the existing ones.
   - An item whose `net_id` is not a net of the design, whose layer is not a copper layer of the board, or whose id repeats an existing id is refused with `route.bad-item` (error), and nothing is merged.
   - Ids are the router's. A router without ids of its own uses `core.ids.derived_id` over the net name and the item's geometry, so equal routes get equal ids.
   - The merged design is written by `write_board` for the board's own major; the written text must pass `roundtrip.rt1`.

6. **`direct`.** For each selected net with exactly two pads that share a copper layer, one `Track` from pad to pad on the first shared layer, with the net's width. Other nets are `unrouted`. It checks no clearance and avoids nothing; its description says so, and its results are `UNVERIFIED` like any other. It makes the command, the merge, the lens interplay and the examples testable without a tool.
   - Rejected: no built-in router, with a `needs_tool` exemption in the consistency suite. A command that cannot be exercised hermetically is not covered by the contract.

7. **KiCadRoutingTools plugin** (`routing/plugins/kicad/routingtools.py`).
   - **Where the tool is.** `--router-path DIR`, else `FENOLITE_KRT`. The interpreter is `--router-python PATH`, else `FENOLITE_KRT_PYTHON`, else `python3` on `PATH`; it must have the tool's dependencies. Missing either gives `FEN-6001` with a hint naming the repository and the pinned tag.
   - **Version.** `PINNED_TAG = "v0.22.1"`. The plugin reads the tool's own version from its checkout (task 2.1 records where it is stated); a version other than the pinned one is allowed and reported with `route.tool-unpinned` (warning), and the result's evidence says which version ran.
   - **Run folder.** A fresh temporary directory holding the board written by `write_board` for its own major, and the project's other files of `project_set` (the project file carries the net classes the tool reads). The command is `<python> <DIR>/py_router/route.py <board> <routed> --nets <names…>`, with `cwd` the run folder, `LANG=C`, a timeout (default 600 s), and the options of `--router-option` appended as `--key value`.
   - **Lift.** The routed board is read with `read_board`. The result holds exactly the tracks, arcs and vias whose uuid the input board lacks. Everything else in the tool's file is ignored, so nothing the tool might rewrite (footprints, zones, the header) reaches the user's board.
   - A track, arc or via of the input that the routed file lacks is reported with `route.copper-removed` (warning) and stays on the board: the plugin never removes copper.
   - A non-zero exit, a timeout or a missing output gives `route.tool-failed` (error) with the first sanitised line of the tool's output; no board is written.
   - Blind and buried vias, which the tool does not make, and arcs are passed through as the model holds them.
   - `sends_data_offsite` is `False`: its documentation names no network use in routing; `build_router.py` downloads a binary, which the user runs, not Fenolite.
   - Rejected: adopting the tool's output file as the board. Its writer is not Fenolite's; lifting copper keeps RT1 and every opaque slot.
   - Rejected: installing it into Fenolite's environment. It has three heavy dependencies and no package.

8. **`fenolite route PATH`** (`cli/cmd_route.py`, `mutates=True`). Flags: `--router NAME` (required), `--nets GLOB` (repeatable; default `*`), `--rip`, `--include-zone-nets`, `--router-path`, `--router-python`, `--router-option KEY=VALUE` (repeatable), `--timeout SECONDS`, `-o/--out FILE`.
   - An unknown router exits 2 (`FEN-2001`) listing the registered names. An unavailable one exits 6 (`FEN-6001`).
   - A router with `sends_data_offsite` needs `--allow-offsite`, else exit 2 with a hint; no shipped router has it.
   - One `PlannedWrite` for the board; none when no net was selected or nothing was routed.
   - `result`: `board`, `router`, `tool_version`, `selected`, `routed`, `unrouted`, `tracks`, `vias`, `ripped`, `log` (at most 20 sanitised lines).
   - Issues: `route.*` and the reader's. A router that leaves selected nets unrouted gives `route.unrouted` (warning) per net; the exit code stays 0, because `check` is the gate.
   - Evidence: `UNVERIFIED`, with the router and its version as the oracle text.
   - `example_args`: `(EXAMPLE_UNROUTED, "--router", "direct", "--out", "fenolite-routed.kicad_pcb", "--dry-run")`; `EXAMPLE_UNROUTED` is an authored board with one unrouted two-pad net (`tests/data/kicad/routing/two_pads.kicad_pcb`).

9. **Capabilities and doctor.** `capabilities.result.routers` lists `name`, `description`, `sends_data_offsite` and `builtin` for each registered router, without running anything. `doctor.result.routers` adds `available`, `path` and `version` from `Router.available()`; a registered router that is not available gives `doctor.tool-missing` naming it. With `--no-run`, `doctor` lists names only.

10. **Fills after routing.** `route` writes no fills. When the board has fills, the result says `fills_stale: true` and the issue `route.fill-stale` (info) names `fenolite fill`; the next `build` drops them by c0019's digest in any case.

11. **Rebuilds keep routes.** No lens change: routed copper is on nets the design has. The oracle proof builds, places, routes, fills and rebuilds, and requires the second build to write the bytes of the first.

12. **CI.** A job `routing` in `.github/workflows/ci.yml`: the pinned `kicad-10` image, the tool cloned at `PINNED_TAG` with its commit recorded, `python build_router.py`, its three dependencies in a virtual environment of its own, then `uv run pytest tests/routing -m needs_router`. The job is not a required check: it downloads third-party code and a binary. `needs_router` skips without `FENOLITE_KRT`, and fails in required-resource mode when `router` is listed in `FENOLITE_REQUIRE`.
    - The 9.0 half of the gate runs locally in the pinned 9.0.9 image with the tool mounted, and is recorded in `docs/evidence/routing.md`; a second CI job for it is c0025's decision.

13. **No model or schema change, no new FEN code; one MODIFIED requirement.** `route.*` codes live in `routing.codes.ISSUE_CODES`. `package-layering` "Allowed import edges" gains `model` and `geometry` for `routing.plugins.<x>` (see "Files and public API").

## Files and public API

| file | public API |
|---|---|
| `src/fenolite/routing/__init__.py` (new) | re-exports the protocol types, `routers`, `unrouted`, `apply`, `ISSUE_CODES` |
| `src/fenolite/routing/protocol.py` (new) | `JobPad`, `JobNet`, `RoutingJob`, `RoutingResult`, `RouterStatus(available, path, version, reason)`, `Router` (Decision 2) |
| `src/fenolite/routing/registry.py` (new) | `GROUP = "fenolite.routers"`; `routers() -> Mapping[str, Router]`; `unavailable() -> Mapping[str, str]` |
| `src/fenolite/routing/select.py`, `merge.py`, `codes.py` (new) | `unrouted(…)`; `rip(design, nets) -> tuple[Design, int]`; `apply(design, result) -> Design`; `ISSUE_CODES` |
| `src/fenolite/routing/direct.py` (new) | `DirectRouter` |
| `src/fenolite/routing/plugins/kicad/routingtools.py` (new) | `PINNED_TAG`; `KicadRoutingToolsRouter(path=None, python=None, timeout=600)`; `EVIDENCE` |
| `src/fenolite/cli/cmd_route.py` (new) | `COMMAND` (`route`, `mutates=True`) |
| `src/fenolite/cli/cmd_capabilities.py`, `cmd_doctor.py`, `_examples.py` (extended) | routers; `EXAMPLE_UNROUTED` |
| `pyproject.toml` | `[project.entry-points."fenolite.routers"]` with `direct` and `kicadroutingtools` |
| `tests/unit/routing/` (new) | protocol, registry, select, merge, direct, and the plugin with a fake tool (`tests/_fakerouter.py`) |
| `tests/unit/cli/test_route_cmd.py` (new) | hermetic |
| `tests/routing/` (new) | `test_krt_gate.py`, `test_route_oracle.py` (`needs_router`, `needs_kicad`) |
| `docs/routing.md` (new); `docs/cli-contract.md`; `docs/evidence/routing.md` (new) | user guide and plugin contract; the `route` section; gate outcomes |

Layering: `routing` imports `core`, `model` and `geometry`; `routing.plugins.kicad` imports `routing`, `backends.kicad`, `model` and `geometry`. The living row for `routing.plugins.<x>` allows only `routing` and `backends.<x>`, and a plugin must build `Track` and `Via` entities and transform pads, so this change MODIFIES "Allowed import edges" (the full text copied, plus `model` and `geometry` for plugins) and updates `tests/unit/test_import_graph.py` in the same commit. No other active change modifies that requirement.

## Sources registered by this change

| id | URL | licence of source | used for |
|---|---|---|---|
| S-0215 | https://github.com/drandyhaas/KiCadRoutingTools (README at the pinned tag) | MIT (LICENSE file: "MIT License", "Copyright (c) 2026 drandyhaas") | what the tool is, installation, KiCad 9 and 10 compatibility, treatment of existing copper, keep-outs and zones, stated limits |
| S-0216 | https://github.com/drandyhaas/KiCadRoutingTools/blob/main/docs/configuration.md | MIT | script names, `route.py` arguments and defaults |
| S-0217 | https://github.com/drandyhaas/KiCadRoutingTools/blob/main/docs/api-kicad-parser.md and `requirements.txt` | MIT | that it reads the file format directly; its dependencies |
| S-0218 | https://docs.python.org/3/library/importlib.metadata.html | to verify on the page | entry-point groups read with `importlib.metadata.entry_points` |

Task 1.1 opens each page at the pinned tag and records the commit. The tool's source is not read for format knowledge and none of it is copied: it is run as a program. S-0219 stays unused.

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-K-KRT-CLI | At the pinned tag, `python py_router/route.py IN OUT --nets <names>` exits 0, writes `OUT`, and takes clearances and via sizes from the board's net classes when no flag is given (S-0216) | `tests/routing/test_krt_gate.py::test_cli` | for the built blink of targets 9 and 10: exit 0, `OUT` exists and reads with `read_board`; the routed tracks of a net have the width passed with `--track-width`; outcome `krt-cli` = `present` |
| H-K-KRT-ROUTE | The blink routed by the tool has no unconnected item and no violation of severity error that the unrouted blink lacks, under `kicad-cli` of the board's own major (S-0215) | `tests/routing/test_krt_gate.py::test_route` | on 10.0.6 for target 10 and on 9.0.9 for target 9, after `route` and, on 10.0.6, `fill`: `unconnected_items` is empty and the error-type set is a subset of the unrouted board's; outcomes `krt-route-t9`, `krt-route-t10` = `equal` |
| H-K-KRT-KEEP | The tool's output differs from its input only in tracks, arcs and vias: every footprint, zone, rule area, graphic and net of the input reads back equal (S-0215) | `tests/routing/test_krt_gate.py::test_keep` | `read_board` of input and output, compared without tracks, arcs, vias and provenance, are equal for both targets; outcome `krt-keep` = `equal`. The plugin does not rely on it (it lifts copper only); a `different` outcome is recorded and names what changed |
| H-K-KRT-REPEAT | Two runs of the tool on the same input give the same tracks and vias (not stated by its documentation) | `tests/routing/test_krt_gate.py::test_repeat` | geometry of tracks and vias equal across two runs, ids ignored; outcome `krt-repeat` = `equal` or `different`, recorded either way; nothing depends on it |

Ids used without changing their level: `H-K-PCB-READ`, `H-K-PCB-WRITE`, `H-K-DRC-JSON`, `H-K-DRC-TYPES`, `H-K-LENS-FILL`.

## Evidence level per behaviour (before merge)

| behaviour | level required | proof |
|---|---|---|
| Protocol, registry, selection, merge, `direct` | mechanical | `tests/unit/routing` |
| `route` command | mechanical; results `UNVERIFIED` | `test_route_cmd.py` |
| Tool arguments and outputs | observed at the pinned tag on both majors, `H-K-KRT-CLI` | `test_krt_gate.py::test_cli` |
| Routed blink | `KICAD-VERIFIED (9.0.x, 10.0.x)` for the pinned tag, `H-K-KRT-ROUTE` | `::test_route` |
| Loop with routes kept | mechanical with the lens; observed on both majors | `test_route_oracle.py::test_loop` |

`routingtools.EVIDENCE` names the four rows and stays `INFERRED`; it describes the plugin, not a route.

## Budget (7.5 days; the roadmap gives 6)

| work | days |
|---|---|
| registers, docs skeleton | 0.25 |
| feasibility gate | 1.5 |
| protocol, registry | 0.75 |
| selection, merge | 1.0 |
| `direct` | 0.5 |
| plugin | 1.25 |
| `route` command, capabilities, doctor | 1.0 |
| oracle loop, CI job | 0.75 |
| docs, closing | 0.5 |
| **total** | **7.5** |

Cut order: (1) the CI job (the gate is then local only, recorded in `docs/evidence/routing.md`); (2) `--rip`; (3) routers in `doctor`. Not optional: the gate on both majors, the protocol, `direct`, the plugin, the command.

## Risks / Trade-offs

- [The tool changes its arguments between tags] → one pinned tag, checked by `krt-cli`; another version is allowed with a warning and its own evidence text.
- [The tool's Rust binary is absent for a platform] → `available()` reports it; `FEN-6001` names the build step.
- [The tool is not repeatable] → recorded; rebuilds keep the copper that is on the board, so repeatability of the build does not depend on it.
- [It routes with a default width because the board has no class] → the command passes the net's class values, or the board defaults, as flags, so the route never depends on the tool's defaults.
- [A third-party plugin sends designs off the machine] → `sends_data_offsite` is part of the protocol, shown by `capabilities`, and needs `--allow-offsite`.
- [The gate fails] → Decision 1: c0023 stays in v0.1.

## Migration Plan

Additive: a package, a command, entry points and an optional CI job. To roll back, remove them.

## Open Questions

- **Where the tool states its version.** The research found release tags and no `--version` flag. Default: task 2.1 records the file that carries it; if none does, the plugin reports the checkout's tag through `git describe --tags` when `git` is present, else `unknown`.
- **Required or optional CI job.** Default: optional (Decision 12). c0025 decides whether the release gate runs it.
- **`direct` in the released CLI.** Default: shipped and described as a test router; it is the only router that needs nothing.
- **Routing with a grid step.** Default: the tool's (`--grid-step 0.1` mm); settable with `--router-option grid-step=…`.
- **After the gate.** If it passes, the maintainer decides whether c0023 leaves v0.1 (roadmap, "Proposed cuts").
