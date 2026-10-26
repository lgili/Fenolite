## ADDED Requirements

### Requirement: Board items declared in the script
`lens.preserve.merge_layout(built, board, match)` SHALL pass the existing board and the built design to `fenolite.backends.kicad.boarditems.merge_items(existing, built) -> ItemMerge`, SHALL keep only the existing rule areas, texts, graphics and dimensions that it keeps, and SHALL add after them, in the built order, the built design's items whose KiCad uuid is an item uuid (`kicad-file-backend`, "Board items of a script are written"). Script items are regenerated on every build, as script copper is.
- This takes out of "Copper items follow their nets" (its rule that rule areas are kept unchanged) and out of "Board content outside the design is kept" exactly the existing items whose KiCad uuid is an item uuid. Every other rule area, text, graphic and dimension stays as those requirements say, so items drawn in KiCad are kept.
- An existing item with an item uuid MUST be dropped. When `built` holds an item with that uuid, it is regenerated, with one `kicad.board-item.regenerated` info naming its kind, uuid and the fields that differ, when a modelled field differs (an edit in KiCad): for a rule area its name, outline, layers and settings; for a text its string, position, layer, size, thickness, rotation and justification; for a graphic its kind, layer, points, width and fill; for a dimension its kind, layer, points, offset, direction, units and precision. Otherwise it is stale, with one `kicad.board-item.stale` warning naming its kind, its uuid, and its name or layer.
- `merge_items` SHALL report only the codes of the closed table `boarditems.MERGE_ISSUE_CODES`. They are `kicad.*` codes, so they pass through `PRESERVE_ISSUE_CODES` and `lens.build.BUILD_ISSUE_CODES` unchanged, as "Layout issue codes" and `design-dsl` "Build issue codes" allow.

| code | severity | when |
|---|---|---|
| `kicad.board-item.stale` | warning | an item the script wrote in an earlier build is no longer declared and is removed |
| `kicad.board-item.regenerated` | info | an item the script declares was edited in KiCad and is written again from the script |

- `result.preserved.board_items` MUST report `regenerated` and `stale` (counts), as "Layout preservation evidence" allows; both are 0 without an existing board.
- `fill_inputs_digest` ("Zone fills and the staleness digest") MUST NOT change for a rebuild whose script items did not change, because a regenerated rule area has the same outline, layers and settings; a rule area added, moved or removed by the script changes it, and the fills it concerns are dropped.
- `lens.preserve` still never imports `geometry`: `merge_items` compares points and fields as integers and texts.

#### Scenario: Edited label is written again
- **GIVEN** a confirmed target-10 build of a blink variant with `d.text("rev", "REV A", (mm(2), mm(2)))`, whose board then gets the text moved by 1 mm by token edit, keeping its uuid
- **WHEN** the build runs again with `--confirm`
- **THEN** the text is back at its script position with the same uuid, and `issues` hold one `kicad.board-item.regenerated` naming the text and `position`

#### Scenario: Removed rule area is removed
- **GIVEN** a confirmed build of the variant with the rule areas `ANT` and `HV`, after which `HV` is removed from `design.py`
- **WHEN** the build runs again
- **THEN** the board holds only `ANT`, and `issues` hold one `kicad.board-item.stale` naming `HV`

#### Scenario: Drawings made in KiCad are kept
- **GIVEN** a confirmed build of the variant whose board gets, by token edit, a `gr_text` and a rule area with version-4 uuids
- **WHEN** the build runs twice
- **THEN** both are kept, `issues` hold no `kicad.board-item.*` code, and the second build writes every file with the bytes of the first

#### Scenario: Board item merge codes are closed
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_boarditems.py -k closed_set` collects every issue code that `merge_items` produces in its tests
- **THEN** each is a key of `MERGE_ISSUE_CODES` with the severity of this table, and every key is produced by at least one test
