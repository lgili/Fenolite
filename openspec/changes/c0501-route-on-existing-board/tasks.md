# Tasks: c0501-route-on-existing-board

Rules for every task:

- The field board is private. Nothing from it (names, nets, designators, coordinates, rules, files) goes
  into tests, fixtures, commits or messages. Every bench is authored for Fenolite, in `tests/_route_benches.py`
  or the Part J kit board.
- Run each touched test file alone with `-n 0`; heavier runs go through `~/.local/bin/fenolite-heavy`.

## 1. A board from a pending session

- [x] 1.1 `Session.pending()` (design D1) and `read_board(session)` with `api.pending-edit`; tests for
  "Pending bytes of a session" and "A pending edit session".
  - Proof: `uv run --extra dev pytest tests/unit/backends/altium/edit/test_pending.py tests/unit/api/test_board_api.py -q -n 0`

## 2. The routing world

- [x] 2.1 One function for the rule areas of an Altium document: `AltiumBackend.rule_areas(design, data)`, used
  by `convert.altium_to_kicad` and by the world (design D3); the conversion tests stay green.
  - Proof: `uv run --extra geo --extra dev pytest tests/unit/convert/test_to_kicad.py tests/unit/backends/altium/test_pcb_graphics.py tests/unit/routing/test_world_areas.py -q -n 0`
- [x] 2.2 Rule areas, copper graphics and kept fills in `World`, `World.blocker`, `extra["pours"]` (design D3);
  tests "A keep-out of poured copper only" and "A keep-out of tracks".
  - Proof: `uv run --extra dev pytest tests/unit/routing/test_world_areas.py -q -n 0`
- [x] 2.3 The octilinear and search tests stay green with the new obstacles; record the candidate ids that change
  and why in the task note.
  - Proof: `~/.local/bin/fenolite-heavy uv run --extra dev pytest tests/unit/routing -q -n 2`
  - Note: no candidate id of the routing tests changed (the new obstacles are only rule areas, graphics and
    kept fills, which those benches do not hold). The first run found 16 failures from a zero-width edge probe
    in the search; fixed, then the routing tests and the octilinear/proposal reference files passed.
- [x] 2.4 Add `H-A-PCBX-KEEPOUT-GAP` to `docs/hypotheses.md` (INFERRED, kit case to be requested) and a row to
  `docs/formats/altium/pcb-records.md`, "Regions and keep-outs", naming the open question.
  - Proof: `uv run --extra dev pytest tests/unit/test_hypotheses_register.py tests/unit/test_inferred_hypotheses.py -q -n 0`
  - Note: the kit case that confirms the hypothesis in Altium is not run: maintainer runs in VM.

## 3. Walls and the channel

- [x] 3.1 `Outcome.wall` and `proven` (design D4); tests "A closed ring of pads", "A gap off the grid", "A cut
  search proves nothing".
  - Proof: `uv run --extra dev pytest tests/unit/routing/test_search_wall.py -q -n 0`
- [x] 3.2 `routing.channel.widest` (design D5); tests "A slot between two nets of different classes" and "No
  channel at all"; one property test: on 30 seeded random benches, the path at `low` passes the copper check
  and every `proven` `high` has no path in a search on a 4× finer grid.
  - Proof: `uv run --extra dev pytest tests/unit/routing/test_channel.py -q -n 0`

## 4. Public API

- [x] 4.1 `api/route.py`: the job from the board's rules (design D2, `_job_checks` moved out of `cmd_route`),
  `find_route`, `free_channel`, `RouteSearch`, `Channel`; tests "Same answer from a file and from a session" and
  "Net-class clearance from the board's rules"; `fenolite route` tests stay green.
  - Proof: `uv run --extra dev pytest tests/unit/api/test_route_api.py tests/unit/cli/test_route_cmd.py -q -n 0`
- [x] 4.2 `RouteFound.queue_on(session)` and `route.via-template` (design D6); tests "A path with a via" and "No
  via to copy".
  - Proof: `uv run --extra dev pytest tests/unit/api/test_route_api.py -k queue -q -n 0`

## 5. The command

- [x] 5.1 `cmd_path.py` (design D7): search, channel, the plan for a `.kicad_pcb` and for a `.PcbDoc`,
  `--gate clone`, the five codes in `routing/codes.py` and `explain.toml`; tests for the three scenarios of
  "Path command" and "Codes explained".
  - Proof: `uv run --extra geo --extra dev pytest tests/unit/cli/test_path_cmd.py tests/unit/cli/test_explain_cmd.py -q -n 0`
- [x] 5.2 The written Altium document reads back with the found tracks and via, and `fenolite check` of it gives
  no new copper finding against the source (bench `return_trace`).
  - Proof: `uv run --extra geo --extra dev pytest tests/unit/cli/test_path_cmd.py -k written -q -n 0`
- [x] 5.3 Regenerate the schemas for the new results and the CLI surface.
  - Proof: `uv run python tools/gen_schemas.py --check && uv run python tools/model_review.py --check`

## 6. Docs, guide, changelog

- [x] 6.1 `docs/cli-contract.md`, "path" and the code rows; `docs/routing.md`, "Routing an existing board" and
  "Free channel"; `docs/api.md` for `find_route`, `free_channel`, `RouteSearch`, `Channel`.
  - Proof: `uv run --extra dev pytest tests/unit/api/test_run_api.py -k page -q -n 0`
- [x] 6.2 Teach `fenolite path`, `--widest`, `--gate clone` and the five codes on the agent guide page
  `route-search.md`, then regenerate the guide.
  - Proof: `uv run python tools/gen_agent_guide.py --check && uv run --extra dev pytest tests/unit/agent/test_pages.py -q -n 0`
- [x] 6.3 Add the change to `CHANGELOG.md` under `## [Unreleased]` and run `make check-fast`.
  - Proof: `make check-fast`

## Decisions

- Decision (maintainer, 2026-11-13): `fenolite.api` may import `routing` (package-layering spec delta in this
  change); the route search is a public API, not a CLI-only feature.
- Decision (maintainer, 2026-11-13): `RouteFound.queue_on` declares the routed net's connectivity on the
  session. Joining a net's islands changes its connectivity signature, so D6's "nothing to declare" did not
  hold; shorts to other nets are still refused by `verify`.
- Decision (maintainer, 2026-11-13): `Result.fail_on_codes` lets a command exit 5 on a named info code, so a
  `route.path-limit` refusal exits 5 as the spec asks without making the code a warning.
- Decision (maintainer, 2026-11-13): a template via matches the found via within 10 nm (`VIA_TOLERANCE`), the
  rounding of Altium document units.
- Decision (maintainer, 2026-11-13): "A path with a via" uses an authored two-sided document; the kit board
  has no Bottom track to clone.
- Decision (maintainer, 2026-11-13): "No channel at all" uses a ring whose clearances overlap (free gap
  -0.1 mm); a positive gap always lets a 1 um track through.
- Decision (maintainer, 2026-11-13): the channel's `high` may lie up to 2 x MARGIN (4 um) below the exact width
  that fits; the slot test asserts `low <= 2.3 mm <= high + 2 * MARGIN`.
- Decision (maintainer, 2026-11-13): the wall lists every blocker the search met, interior ones too, ordered by
  refusals; a probe outside the outline records an `edge` blocker.
- Decision (maintainer, 2026-11-13): copper graphics carry their own net, so same-net graphics do not block.
- Decision (maintainer, 2026-11-13): `.PcbDoc --width` without `--gate clone` is refused (exit 2) before the
  search runs.
- Decision (maintainer, 2026-11-13): a `Board` record given to the API uses its design's own rules; with no
  files there is no project rule file to read.
- Decision (maintainer, 2026-11-13): the search evidence is INFERRED under `H-G-OCTI-CHECK`, combined with the
  board's evidence.
- Decision (maintainer, 2026-11-13): the hypothesis is registered as `H-A-PCBX-KEEPOUT-GAP` and not under a
  new `ROUTE` family: the fact tables of the Altium pages admit only the existing `H-A-*` families, and
  the question is about the PCB document's keep-outs (`PCBX`).
- Decision (maintainer, 2026-11-13): `fenolite path --width` takes `-o/--out` (relative to the working folder) like
  `route` and `tidy`, so its mutation example writes into the working folder; `--out` is refused with `--widest`.
