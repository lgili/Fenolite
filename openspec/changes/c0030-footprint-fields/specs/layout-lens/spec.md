## ADDED Requirements

### Requirement: Footprint fields across rebuilds
`lens.fields.merge_fields(merged, board, match, requests) -> FieldMerge` SHALL decide every field of a matched part when a build merges an existing board, with this precedence: a locked request, then the board's field, then an unlocked request, then the library's field. GUI edits therefore win over generated placements unless the script locks them.
- `build_design` MUST call it on the `Merged` result of `merge_layout`, with `prepared.board`, `prepared.match` and its `fields` keyword, before the merged layout is validated and written. The normal-form pass of "Preservation is the build's normal form" MUST NOT call it, because the written board already holds the merged fields.
- **Kept footprints** (the board's own node, "Kept and re-placed footprints"): each field MUST stay as `merge_layout` left it, the board's field with the script's user-property values ("User properties" below), except that every locked request MUST be applied with `apply_requests`, resolved against the kept footprint. An unlocked request whose result differs from the board's field MUST NOT be applied.
- **Re-placed footprints** whose `lib_ref` and side equal those of the matched board footprint: each field of the built copy that the board footprint also has MUST take the values of the board's field (position, rotation, layer, size, thickness, visibility, justification and mirror), unless a locked request names it. The field keeps the built copy's id, uuid and slot list.
- Every other footprint keeps the fields of the built copy, that is the library's fields with every request applied.
- **User properties.** "Kept and re-placed footprints" gives the values of a kept footprint's user properties to the script and keeps everything else from the board. After this change `merge_layout` MUST apply that rule to fields, and `merge_fields` MUST leave what it sets:
  - a user property that is a field of the kept footprint (same name after `str.casefold()`) MUST keep the board's position, rotation, layer, size, thickness, visibility, justification, mirror, uuid and every other slot; only the `Opaque` slot of its value atom MUST take the script's value, and its name the script's spelling;
  - a missing user property MUST be added after the kept footprint's last field as the built copy's field, with that field's slot list, `native_ids["kicad"]` equal to `embed.placement_uuid(<component path>, "/footprint/property:<name>")` and the id that "Footprint fields on boards" derives for the kept footprint, so the writer emits it after the last field node (`kicad-slots`, "Order-preserving rebuild");
  - a user property whose node is not a field stays a projected `Opaque` slot of the footprint and MUST be edited as "Kept and re-placed footprints" says;
  - the component MUST take the script's values, so "Projected fields on write" passes. Requests never name a user property, and user properties never enter `kept`, `forced` or `carried`.
  On a re-placed footprint the built copy's fields already hold the script's values; only their placement and appearance come from the board, as above.
- `FieldMerge` MUST hold `design` and three sorted lists of `"<component path>:<field name>"`: `kept` (unlocked requests whose result differs from the board's field, which wins on a kept or re-placed footprint), `forced` (locked requests that changed a board field) and `carried` (fields of re-placed footprints changed by taking the board's values). `result.preserved.fields` MUST report the three lists, empty when no existing board was read; "Layout preservation evidence" allows the key.
- `merge_fields` MUST be pure and MUST change nothing but fields. Run again on its own result with the same board, match and requests, it MUST return a `design` equal to that result.

#### Scenario: A GUI edit wins over an unlocked request
- **GIVEN** a confirmed target-10 build of a blink variant whose `design.py` calls `r1.field("Reference", outside="top")`, whose board then gets the `at` of `R1`'s `Reference` property moved by 1 mm by token edit
- **WHEN** the build runs again with `--confirm`
- **THEN** the written `Reference` property of `R1` keeps the edited `at`, `result.preserved.fields.kept == ["R1:Reference"]`, and `forced` and `carried` are empty

#### Scenario: A locked request wins
- **GIVEN** the same edited board, and the request in `design.py` given `locked=True`
- **WHEN** the build runs again with `--confirm`
- **THEN** `R1`'s `Reference` field equals what `place_outside(r1, "Reference", side="top")` gives, and `result.preserved.fields.forced == ["R1:Reference"]`

#### Scenario: Fields follow a forced move
- **GIVEN** the same edited board with the unlocked request, and `R1` given a locked `place()` 2 mm to the right of its board position
- **WHEN** the build runs again with `--confirm`
- **THEN** `R1` is re-placed (`layout.place-forced`), its `Reference` field has the edited field's `position` and `rotation`, and `result.preserved.fields` has `carried == ["R1:Reference"]` and `kept == ["R1:Reference"]`

#### Scenario: A side change takes the library fields
- **GIVEN** the same edited board, and `R1` given a locked `place()` on the bottom side
- **WHEN** the build runs again with `--confirm`
- **THEN** `R1`'s `Reference` field is the built copy's, on `B.SilkS` and mirrored, and `carried` is empty

#### Scenario: User property on a kept footprint
- **GIVEN** a confirmed target-10 build of a blink variant whose `R1` has `properties={"Part number": "PN-330"}`, whose board then gets, by token edit, the `at` of `R1`'s `Part number` property moved by 1 mm and its `(hide yes)` removed, after which `design.py` sets `Part number` to `PN-470` and adds `"Supplier code": "S-1"`
- **WHEN** the build runs again with `--confirm` and the written board is read with `read_board`
- **THEN** `R1` is listed under `result.preserved.kept`; its `Part number` field has the edited position, `visible == True` and its former uuid, and the component maps `Part number` to `PN-470`; a `Supplier code` field follows the last field, with the uuid `embed.placement_uuid("R1", "/footprint/property:Supplier code")`; and the three lists of `result.preserved.fields` are empty

#### Scenario: Rebuilds of an unedited board are quiet and stable
- **GIVEN** a confirmed target-9 build of the variant with the unlocked request
- **WHEN** the build runs twice more with `--confirm`
- **THEN** the three lists are empty, and both rebuilds write every file with the bytes of the first build
