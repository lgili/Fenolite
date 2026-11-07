## ADDED Requirements

### Requirement: Altium rooms are rule areas
An Altium import SHALL read each room of the document (a Room Definition record: `read.rooms`) as a neutral rule area of the room's name, its outline and the copper layer of its side, that restricts nothing (change c0462).

- Only a room whose `LAYER` is `TOP` or `BOTTOM` and whose outline is straight edges MUST give a rule area; its provenance MUST be the room's record (`Rules6/Data#<index>`).
- The room's record MUST stay a kept record (c0434): an Altium write gives it back as it was read, and the Altium writer MUST count the room's rule area `changed` under `keep-out`, not lost, and write no keep-out region for it.
- `RuleSubject.areas` and the `area` leaf MUST keep their meaning: `WithinRoom` stays refused (`altium-project-reader`, `room-membership`), because a pad or a via is in a room by its centre and any other object only wholly within it (S-2212).
- That a document's room record holds the keys of the public rule file's rooms (S-0297) is `INFERRED` (`H-A-RD-ROOM`).

#### Scenario: A rule within a room
- **GIVEN** authored records: the room `PWR` on the top side, a room on no side, a room with an arc, and a Clearance rule scoped `WithinRoom('PWR')`
- **WHEN** `uv run pytest tests/unit/backends/altium/test_rooms_c0462.py -q -n 0` imports it
- **THEN** the design holds the one rule area `PWR`, on `F.Cu`, restricting nothing, its provenance the room's record; the scope is refused `room-membership`; and the Altium writer counts the area `changed`, not lost
