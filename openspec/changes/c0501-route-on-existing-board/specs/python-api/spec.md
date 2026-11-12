## MODIFIED Requirements

### Requirement: Typed design and board reads
`fenolite.api.read_design(path)` SHALL return the `ReadSide` that `equivalent` reads, and `read_board(given)` a frozen `Board` (name, SHA-256, backend, design, board-frame pads, warnings, evidence) of a board file, KiCad project file or folder, or of the pending edits of an Altium edit `Session` (change c0501). A missing path MUST raise `SideMissingError`, and a file that is not a board `SideUsageError`. For a session the board MUST be read from `Session.pending()` with `AltiumBackend.board_from_bytes`, `sha256` MUST be the digest of those bytes, its issues MUST hold `api.pending-edit` (info) with the number of queued operations, and a refused queue MUST raise `SideUsageError` with the session's issues. Neither MUST write a file or start a process.

#### Scenario: Records, not dictionaries
- **WHEN** `uv run pytest tests/unit/api/test_board_api.py -k "read or hermetic"` reads the two-layer board, its folder and a text file
- **THEN** a `Board` and a `ReadSide` with the board's digest come back, the text file raises `SideUsageError`, and no process ran

#### Scenario: A pending edit session
- **GIVEN** a session on an authored PCB document with one queued `move` of a track by 1 mm and the gate open
- **WHEN** `uv run pytest tests/unit/api/test_board_api.py -k pending` reads it with `read_board`
- **THEN** the board's track is 1 mm away from its place on disk, its `sha256` is not the file's, and the file is unchanged

## ADDED Requirements

### Requirement: Route search and free channel in the API
`fenolite.api.find_route(board, *, net, start, end, width, layers=None, grid, max_states, max_vias, pours=None, timeout=None) -> RouteSearch` and `fenolite.api.free_channel(board, *, net, start, end, layers=None, grid, max_states, resolution, pours=None, timeout=None) -> Channel` SHALL take a `Board`, a path or a `Session`, build the routing job with the board's own design rules (`design_rules` of its backend, `ClearanceResolver` as the clearance in force) and its rule areas, and return frozen records (change c0501). `start` and `end` MUST each be `REF-PIN` or a point and a layer. `RouteSearch` MUST hold either `found` (runs, vias, length, and `queue_on(session)`) or `refusal` (reason, `proven`, wall, widest free gap); `Channel` MUST hold `low`, `high`, `grid_limited`, `pinch` and the path at `low`. Every length MUST be integer nanometres; nothing MUST be written.

#### Scenario: Same answer from a file and from a session
- **GIVEN** an authored PCB document and a session on it with nothing queued
- **WHEN** `uv run pytest tests/unit/api/test_route_api.py -k same` runs `find_route` on the path and on the session
- **THEN** both give the same runs and vias

#### Scenario: Net-class clearance from the board's rules
- **GIVEN** an authored PCB document whose clearance rule between class `HV` and everything is 1 mm and whose default is 0.2 mm
- **WHEN** `free_channel` measures a channel of a net of class `HV` next to a pad of another net
- **THEN** the free gap of `pinch` is the distance less 1 mm on the `HV` side
