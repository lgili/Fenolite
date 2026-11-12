## ADDED Requirements

### Requirement: Power analysis in the API
`fenolite.api.analyze_power(board, *, paths=(), requirements=None, temp_rise_mk=None, copper_thickness=None, via_plating=None, resistivity_pohm_m=None, deadline=None)` and `fenolite.api.analyze_split(board, *, power, grid=None, ..., deadline=None)` SHALL take a `Board`, a path or an Altium edit `Session`, read it with `read_board`, and return the `PowerReport` and `SplitReport` that `fenolite analyze --kinds power` and `--split` give for the same inputs (change c0503). `deadline` MUST be seconds or `None`. Nothing MUST be written.

#### Scenario: A fix checked before it is committed
- **GIVEN** a session on the Part J kit board with a queued `clone` of a track of a path's net that widens its narrowest part, and its gate open
- **WHEN** `uv run pytest tests/unit/api/test_power_api.py -k session` runs `analyze_power` on the path and on the session
- **THEN** the session's row has the cloned track as an active element, its `resistance_uohm.high` is lower than the file's, and the document on disk is unchanged
