## ADDED Requirements

### Requirement: Plane nets in the route command
`fenolite route` SHALL take the board's plane layers and track layer rules into its job, SHALL join the SMD pads of plane nets to their planes before the router runs, and SHALL never give a plane net to a router. This requirement extends "Route command" with one option, two result keys, one step and its write rule; a board without a copper layer of type `power` and without `no_tracks` rules MUST give the result it gave before, with `plane_layers` empty and `plane_fanout` holding no net.
- **Rules.** The design MUST get the project's classes and the rules file's lifted rules from `KicadBackend.design_rules` (`backend-protocol`, "Design rules source"; `kicad-file-backend`, "Design rules for the copper check"), in place of the project's classes alone. When the project holds `min_copper_edge_clearance`, the command MUST add to the job's design one board-wide `edge_clearance` rule of that value. A file that cannot be read MUST give `route.project-unread` (warning) and leave the design as the other file gives it.
- **Plane layers and nets.** `plane_layers` MUST be `layers.plane_layers(design)` (`kicad-file-backend`, "Plane layers of a board"), and the plane nets `fanout.plane_nets(design, plane_layers)`. A plane net MUST NOT be a job net, whatever the selection gives, also with `--include-zone-nets`; zone nets without a plane are selected as before. Each plane net that the `--nets` patterns select MUST give one `route.plane-net` (info) instead of `route.zone-net-skipped`. With `--rip`, the selected plane nets MUST be ripped as other selected nets.
- **Fan-out.** Unless `--no-plane-fanout` is given, the command MUST call `plan_fanout` (`routing`, "Plane fan-out") for the selected plane nets, with each net's sizes taken as its width and via sizes are taken for job nets (its class, else the project's `Default` class, else the command's constants), its clearance as the neck, the outline rings of `board_outline`, the largest board-wide `edge_clearance` value, and a clearance callable built from `checks.clearance.ClearanceResolver` over the design and the project's `DesignRules`. Its copper MUST be merged with `routing.merge.apply` before the job is built, so the router sees it as existing copper; its issues MUST join the envelope's.
- **Job.** `RoutingJob.plane_layers` MUST be `plane_layers`, and each `JobNet.layers` the result of `routing.layers.allowed_layers` over the routing layers, `None` when it equals them. A selected net with no allowed layer MUST give `route.no-layer` (warning) and MUST NOT be a job net.
- **Write.** Besides the cases in which "Route command" plans the board's write, the command MUST plan it when the fan-out made copper, also when no net is selected or the router adds nothing.
- **Result.** `result.plane_layers` MUST list the plane layers, and `result.plane_fanout` MUST hold `nets` (the plane nets fanned out, sorted), `pads`, `joined`, `tracks`, `vias` (counts) and `failed` (`REF-NUMBER` of each pad left open, in board order). With `--no-plane-fanout`, `nets` MUST be empty and the counts 0.
- Exit codes MUST follow "Route command": `kicad.fanout.failed`, `route.no-layer` and `route.plane-net` do not change them. `docs/cli-contract.md` MUST describe the option, the keys and the codes.

#### Scenario: Plane nets fanned out, signals routed
- **GIVEN** the bench of `tests/routing/_planebench.py` written as a KiCad board with `In1.Cu` and `In2.Cu` of type `power`, and its project and rules files
- **WHEN** `uv run pytest tests/unit/cli/test_route_cmd.py -k plane_fanout` runs `fenolite route <board> --router direct --dry-run --json`
- **THEN** the exit code is 0, `result.plane_layers` is `["In1.Cu", "In2.Cu"]`, `result.plane_fanout.nets` is `["GND", "VCC"]` with 6 vias and 6 tracks, `issues` hold one `route.plane-net` for each, `result.selected` names neither, and the board written by the same command with `--confirm` holds the fan-out copper

#### Scenario: Fan-out skipped
- **WHEN** the same command runs with `--no-plane-fanout`
- **THEN** `result.plane_fanout.nets` is empty, its counts are 0, and the plane nets are still not selected

#### Scenario: Zone nets option
- **WHEN** the same command runs with `--include-zone-nets`
- **THEN** `result.selected` names neither `GND` nor `VCC`

#### Scenario: Board without plane layers
- **GIVEN** the example board of the route command's `example_args`
- **WHEN** `uv run pytest tests/unit/cli/test_route_cmd.py -k example` runs the mutation example with `--confirm`
- **THEN** it passes as before, with `result.plane_layers` empty and `result.plane_fanout` holding no net and counts 0

#### Scenario: A net with no allowed layer
- **GIVEN** the bench with a `no_tracks` rule on `net SIG5` over `F.Cu` and `B.Cu`
- **WHEN** the first command runs
- **THEN** `issues` hold one `route.no-layer` naming `SIG5`, which is not in `result.selected`
