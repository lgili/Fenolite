## ADDED Requirements

### Requirement: Path command
`fenolite path PATH --net NET --from A --to B (--width W | --widest)` SHALL be registered by
`src/fenolite/cli/cmd_path.py` and SHALL search one connection or measure a free channel on a `.kicad_pcb` or
a `.PcbDoc`, with the board's own rules, through `fenolite.api.find_route` and `free_channel` (change c0501).
- `A` and `B` MUST each be `REF-PIN` or `X,Y@LAYER` in millimetres; an unknown pad or layer MUST exit 2 with
  `FEN-2001` and the closest names in the hint.
- Options: `--layers`, `--grid` (default 0.1 mm), `--max-states` (default 200 000), `--max-vias` (default 2
  with `--width`, 0 with `--widest`), `--resolution` (default 10 µm, `--widest` only), `--pours kept|refilled`
  (default `kept` for a `.PcbDoc`, `refilled` for a `.kicad_pcb`) and `--timeout`.
- **With `--width`.** `result.path` MUST give the runs, vias and length; a refusal MUST be `result.refusal`
  (reason, `proven`, wall, widest free gap) with `route.no-path` or `route.path-limit` and exit 5. A found
  path MUST be written only through the mutation protocol: `--dry-run` plans it, `--confirm --plan ID` writes
  the reviewed bytes. A `.PcbDoc` MUST be written as an edit session commit and MUST be refused (exit 2,
  `FEN-2001`) without `--gate clone`; with it, the reply MUST hold `route.altium-edit-unconfirmed` and the
  session's `INFERRED` evidence.
- **With `--widest`.** The command MUST NOT write; `result.channel` MUST give `low`, `high`, `grid_limited`,
  `pinch` and the path at `low`.
- Lengths MUST be integer nanometres; the output MUST be deterministic for the same bounds and hold no
  absolute path. `example_args` MUST be `(EXAMPLE_BOARD, "--net", "GND", ...)` on the authored two-layer board.

#### Scenario: Route a return trace on an Altium document
- **GIVEN** an authored PCB document written by the test from `tests/_route_benches.py` (`return_trace`): two
  capacitor pads of net `GND` with a keep-out of poured copper only and a pad of another net between them
- **WHEN** `fenolite path <doc> --net GND --from C1-2 --to C2-2 --width 0.5mm --gate clone --dry-run --json`
  runs
- **THEN** the exit code is 0, `result.path` crosses the keep-out, keeps the clearance from the other pad,
  and `result.plan` names the document; `--confirm --plan <id>` writes it, and `fenolite check` of the
  written document reports no new copper finding

#### Scenario: A PcbDoc write without the opt-in
- **WHEN** the same command runs without `--gate clone`
- **THEN** the exit code is 2 and the hint names `--gate clone`

#### Scenario: A channel
- **WHEN** `fenolite path tests/data/kicad/board/two_layer.kicad_pcb --net GND --from <a> --to <b> --widest
  --json` runs
- **THEN** the exit code is 0, `result.channel.low <= result.channel.high`, and no plan is made
