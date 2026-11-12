## ADDED Requirements

### Requirement: Pending bytes of a session
`Session.pending()` SHALL return the bytes that a commit of the queued operations would write before its
read-back, or `None` and the issues of a refused operation, without writing a file and without changing the
queue (change c0501).

#### Scenario: Read the pending edit
- **GIVEN** a session on the Part J kit board (`edit.PcbDoc` of the `board` fixture of
  `tests/unit/backends/altium/edit/conftest.py`) with one queued `clone` of a track and its gate open
- **WHEN** `uv run pytest tests/unit/backends/altium/edit/test_pending.py` calls `pending()` twice, then
  `commit(out)`
- **THEN** both calls give the same bytes, the document on disk is unchanged, and the committed file reads
  back to the same tracks as `board_from_bytes` of the pending bytes

### Requirement: Found copper queued on a session
`RouteFound.queue_on(session)` SHALL queue one `clone` of a template track per segment and one `clone` of a
template via per via of the found path (change c0501). The template track MUST be the first track of the
net on the segment's layer, else the first track of the document; the template via the first via of the net
whose diameter and drill equal the job's via size. Without such a via nothing MUST be queued and
`route.via-template` (error) MUST be returned.

#### Scenario: A path with a via
- **GIVEN** the Part J kit board with one via of net `GND` of the job's size and a path of two segments on
  `Top`, a via and one segment on `Bottom`
- **WHEN** `uv run pytest tests/unit/api/test_route_api.py -k queue` queues it and commits with the `clone`
  gate open
- **THEN** the session holds four queued `clone` operations, and the committed document holds three new
  tracks and one new via of `GND` at the path's places

#### Scenario: No via to copy
- **WHEN** the document has no via of the job's size
- **THEN** nothing is queued and the outcome holds `route.via-template`
