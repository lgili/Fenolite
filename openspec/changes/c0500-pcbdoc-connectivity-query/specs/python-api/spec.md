## ADDED Requirements

### Requirement: Islands from Python
`fenolite.api.islands(board, *, nets=None, without=())` SHALL return `net_islands` of the board, a `Board` or a
path, with its board-frame pads: a `dict` from net name to a tuple of `NetIsland` (change c0500). An unknown
name in `without` MUST raise `KeyError`. It MUST write no file and start no process.

#### Scenario: Same islands as the command
- **WHEN** `uv run pytest tests/unit/api/test_frames_c0500.py -k islands` calls `islands` and
  `run("net", …, "--islands")` on the same authored board
- **THEN** the pads and members of each island are equal

### Requirement: Frames and units
`fenolite.api.board_frame(board)` SHALL return a frozen `Frame(origin, y_up)` with `from_native`,
`to_native`, `to_board` and `from_board` (change c0500). `fenolite.api` SHALL also export `altium_to_nm`,
`nm_to_altium`, `format_length` and `parse_length`, the functions of `fenolite.core.units`.
- For an Altium board, `origin` MUST be the board origin of the document in the model frame
  (`backends.altium.frame.board_origin`), and `y_up` MUST be true. `to_board` MUST give nanometres from that
  origin with Y up, the frame of the Altium edit session.
- For a board of any other backend, `origin` MUST be (0, 0), `y_up` false and `to_board` the identity.
  `from_native` and `to_native` MUST raise `SideUsageError`.
- No conversion MUST use a float. `docs/api.md` MUST list the three frames and every name.

#### Scenario: A point of an Altium document
- **GIVEN** an authored PCB document with `ORIGINX=1000mil`, `ORIGINY=1000mil` and a track that starts at
  native (12 000 000, 15 000 000)
- **WHEN** `uv run pytest tests/unit/api/test_frames_c0500.py -k altium` converts it
- **THEN** `from_native` gives (30 480 000, -38 100 000), `to_board` of that gives (5 080 000, 12 700 000),
  `from_board` gives the model point back, and `to_native` gives the native pair back

#### Scenario: The edit session's frame
- **WHEN** `uv run pytest tests/unit/api/test_frames_c0500.py -k edit` names each free track of the authored
  edit documents by `to_board` of its model ends
- **THEN** the edit session matches each one to exactly one record

#### Scenario: A KiCad board
- **WHEN** `board_frame` reads `tests/data/kicad/board/two_layer.kicad_pcb`
- **THEN** `to_board` returns its argument, and `from_native` raises `SideUsageError`
