# Tasks: c0500-pcbdoc-connectivity-query

Rules for every task:

- The maintainer's board is private. Nothing from it (names, nets, coordinates, files) goes into tests,
  fixtures, commits or messages. Test boards are authored for Fenolite.
- Needs c0495 (b) (`load_board` reads a `.PcbDoc`) for the CLI tasks; tasks 1.x do not.
- Run each touched test file alone with `-n 0`, and `tests/unit/roles` because `roles.proposals` calls
  `net_islands`.

## 1. Islands and removal

- [ ] 1.1 `IslandItem` and `NetIsland.members` in `analysis/connectivity.py` (design D1); scenario "Members of
  each island"; `roles.proposals` output unchanged.
  - Proof: `uv run --extra dev pytest tests/unit/analysis/test_connectivity.py tests/unit/roles -q -n 0`
- [ ] 1.2 `ties._names` becomes `ties.item_names`; `net_islands(..., without=)` with `KeyError` for an unknown
  name (D2); scenarios "A cut splits the net", "A parallel path keeps it whole", "An unknown name".
  - Proof: `uv run --extra dev pytest tests/unit/analysis/test_connectivity.py tests/unit/analysis/test_ties.py -q -n 0`

## 2. CLI

- [ ] 2.1 `fenolite net PATH NAME --islands [--without …]` in `cli/cmd_net.py` (D4), the `net.islands` page,
  the cut note when the net has a zone; scenarios of "Islands in the net command", on an authored
  `.PcbDoc` and on `two_layer.kicad_pcb`.
  - Proof: `uv run --extra geo --extra dev pytest tests/unit/cli/test_net_islands_c0500.py -q -n 0`

## 3. Python API, frames and units

- [ ] 3.1 `backends.altium.frame.board_origin`, `api/frames.py` (`Frame`, `board_frame`), the four unit
  re-exports and `api.islands` (D5); scenarios of "Frames and units" and "Islands from Python".
  - Proof: `uv run --extra dev pytest tests/unit/api/test_frames_c0500.py tests/unit/api/test_board_api.py tests/unit/backends/altium/test_frame.py -q -n 0`
- [ ] 3.2 The edit session agrees: for every free track of the authored edit documents, the session's
  `Track(start, end)` built from `to_board` matches exactly one record.
  - Proof: `uv run --extra dev pytest tests/unit/api/test_frames_c0500.py -k edit -q -n 0`
- [ ] 3.3 `docs/api.md`: the new names, the frame table and an example that replaces a unit lambda;
  `docs/analyses.md` ("Open connections"): members, removal and the no-repour limit.
  - Proof: `uv run --extra dev pytest tests/unit/api/test_run_api.py -k page -q -n 0`

## 4. Teach and record

- [ ] 4.1 Teach `net --islands --without` on `board-grounds.md` and the frame helpers on `altium.md` of the agent
  guide; update "net" in `docs/cli-contract.md`; regenerate the command pages.
  - Proof: `uv run python tools/gen_agent_guide.py --check && uv run --extra dev pytest tests/unit/agent/test_pages.py -q -n 0`
- [ ] 4.2 Regenerate the schemas for the new result keys; declare new files under `tests/data` in
  `tests/data/MANIFEST.toml`.
  - Proof: `uv run python tools/gen_schemas.py --check && uv run --extra dev pytest tests/corpus/test_manifest.py -q -n 0`
- [ ] 4.3 Add the change to `CHANGELOG.md` under `## [Unreleased]`, and run `make check-fast`.
  - Proof: `make check-fast`
