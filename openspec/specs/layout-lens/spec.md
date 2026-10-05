# layout-lens Specification

## Purpose
Keep the work done in KiCad when `fenolite build` runs over an existing project: parts are matched to footprints by uuid, `fenolite.path` or a `moved()` alias; placements follow the precedence locked `place()`, board, `place()`, staging; routing, zones, fills, board-only footprints, board settings, project keys and user rules survive while what they depend on is unchanged; and a rebuild over its own output is byte-identical. Behaviour: `docs/lens.md`; facts: `docs/formats/kicad/board.md`.
## Requirements
### Requirement: Layout lens module
The module `fenolite.lens.preserve` SHALL hold the layout preservation of `build`, and MUST import only the standard library, `core`, `model` and `backends` (`package-layering`), never `geometry`, `dsl` or `lens.build`.
- Public names: `ExistingProject`, `read_existing`, `footprint_uuid`, `FootprintMatch`, `LayoutMatch`, `match_footprints`, `PlacementLike`, `KeptPlacement`, `effective_placements`, `Prepared`, `prepare`, `Merged`, `merge_layout`, `zone_digest`, `fill_inputs_digest`, `drop_stale_fills`, `merge_rules`, `PRESERVE_ISSUE_CODES` and `EVIDENCE`.
- Every function except `read_existing` MUST be pure: it reads no file and no environment variable, and returns new model objects without changing its arguments.
- `footprint_uuid(path)` MUST return `embed.placement_uuid(path, "/footprint")`, the KiCad uuid that c0011's build gives the footprint of the part at component path `path`.
- Geometry is never computed: positions are compared as integers, and fill staleness is a text digest.

#### Scenario: Import edges
- **WHEN** `uv run pytest tests/unit/test_import_graph.py` runs
- **THEN** it passes with no `ALLOWED` change, and `src/fenolite/lens/preserve.py` imports neither `fenolite.geometry`, `fenolite.dsl` nor `fenolite.lens.build`

#### Scenario: Uuid of a component path
- **WHEN** `footprint_uuid("power/R1")` is called
- **THEN** it equals `embed.placement_uuid("power/R1", "/footprint")`, and placing `Mini_R_0603` with key `power/R1` gives a footprint with that uuid

### Requirement: Existing project files
`lens.preserve.read_existing(out_dir, name) -> ExistingProject` SHALL return the texts of `<name>.kicad_pcb`, `<name>.kicad_pro` and `<name>.kicad_dru` in `out_dir`, each `None` when the file does not exist, and `build` SHALL preserve the layout from them unless `--discard-layout` is given.
- The texts MUST be read as UTF-8; a file that does not decode MUST raise `FormatError` (`FEN-3004`) naming it.
- `prepare(design, placements, existing, *, name, moves={}, module_moves={}, net_moves={}, source={}) -> Prepared` MUST read the board text with `read_board(text, file="<name>.kicad_pcb")`, so the relative file name, never an absolute path, reaches provenance. It MUST resolve the aliases with `lens.moved.resolve_aliases` ("Alias resolution"), match with their `parts`, and pass `source` to `effective_placements`. `Prepared.aliases` MUST stay the part aliases, and `Prepared.net_aliases` and `Prepared.module_aliases` MUST hold the resolved `nets` and `modules`. Reader warnings MUST go to `Prepared.issues`; reader infos MUST only be counted in the build summary.
- Refusals MUST happen before any planned write, so `--dry-run` refuses too: a board that does not parse (`FEN-3004`); a board whose header is newer than every known version, a project file of an unknown version or a rules file of version 2 or more (`FEN-3002`, `FEN-3003`); a KiCad 8 board (`FEN-7003`, c0017); a board of major 10 built for target 9 (`DowngradeRefusedError`, `FEN-7002`, c0017); a rules file that `parse_rules` refuses (`FEN-3004`, with the line).
- With `--discard-layout`, none of the three files MUST be read: the build is a fresh build, and the mutation protocol keeps a `.bak` of every replaced file unless `--no-backup` is given.

#### Scenario: Missing files
- **GIVEN** a folder holding only `blink.kicad_pro`
- **WHEN** `read_existing(folder, "blink")` is called
- **THEN** the result has `board is None`, `rules is None` and the project text

#### Scenario: Discarding the layout
- **GIVEN** a confirmed target-10 blink build in `B` whose board was replaced by `tests/_layout_edit.py::edit_blink` of its text
- **WHEN** `fenolite build examples/blink_2layer/design.py --out B --discard-layout --confirm` runs
- **THEN** the exit code is 0, `B/blink.kicad_pcb` is byte-equal to a build into an empty folder, and `B/blink.kicad_pcb.bak` holds the edited board

#### Scenario: Board of major 10 built for target 9
- **GIVEN** a confirmed target-10 blink build in `B`
- **WHEN** `fenolite --kicad-version 9 build examples/blink_2layer/design.py --out B --dry-run --json` runs
- **THEN** the exit code is 7, stderr carries `FEN-7002`, and no file under `B` changes

#### Scenario: Broken rules file
- **GIVEN** a confirmed blink build in `B` whose `blink.kicad_dru` gets the rule `(rule 'big one' (constraint clearance (min 1mm)))` as its third line
- **WHEN** the build runs again with `--dry-run --json`
- **THEN** the exit code is 3, stderr carries `FEN-3004`, and its `where` names `blink.kicad_dru` and `line 3`

### Requirement: Footprint matching
`lens.preserve.match_footprints(design, board, *, moves={}) -> LayoutMatch` SHALL pair each component of `design` that carries a component path in `properties["fenolite.path"]` with at most one footprint of `board`, and each footprint of `board` with at most one component.
- The keys MUST be tried in this order, each over every unmatched component in component-path order before the next key starts:
  1. **uuid**: the footprint whose KiCad uuid (`native_ids["kicad"]`) is `footprint_uuid(path)`;
  2. **path**: the first footprint, in board order, whose `fenolite.path` property equals `path`;
  3. **alias**: when `moves` maps `path` to `old`, the footprint whose uuid is `footprint_uuid(old)`, else the first one, in board order, whose `fenolite.path` property equals `old`.
- A footprint matched once MUST NOT be matched again. References, values and positions MUST NOT be used as keys.
- `LayoutMatch` MUST hold `matches` (component path → `FootprintMatch(path, footprint, key)`, key `uuid`, `path` or `alias`), `orphans` (unmatched footprints that carry a `fenolite.path` property), `board_only` (unmatched footprints without one), both in board order, and `unused_aliases` (aliases that matched nothing, or whose new path was matched by uuid or path), in path order.
- An unused alias MUST give `layout.alias-unused` (warning) naming both paths.

#### Scenario: Moved footprint matched by uuid
- **GIVEN** the board of a target-10 blink build edited by `edit_blink`, which moves `D1` 4 mm to the right and routes `LED_A`, read with `read_board`
- **WHEN** `match_footprints(design, board)` runs with the blink's model design
- **THEN** `U1`, `R1` and `D1` are matched with key `uuid`, and `orphans`, `board_only` and `unused_aliases` are empty

#### Scenario: Path property when the uuid changed
- **GIVEN** the same board with the uuid of `D1`'s footprint node replaced by `00000000-0000-4000-8000-0000000000d1` in the test
- **WHEN** the footprints are matched
- **THEN** `D1` is matched with key `path` to that footprint

#### Scenario: Alias after a rename
- **GIVEN** a blink variant whose `R1` is renamed `R7` and that calls `d.moved("R1", "R7")`, and the board of the original blink
- **WHEN** the footprints are matched with `moves={"R7": "R1"}`
- **THEN** `R7` is matched with key `alias` to the footprint of `R1`, and `orphans` is empty

#### Scenario: Copied footprint
- **GIVEN** the blink board with a copy of `R1`'s footprint node appended after it in the test, with a new uuid and the same `fenolite.path` property
- **WHEN** the footprints are matched
- **THEN** `R1` is matched with key `uuid` to the original node, and the copy is the only orphan

### Requirement: Placement precedence
`lens.preserve.effective_placements(placements, match, *, design, board, source={})` SHALL decide each part's placement with the fixed precedence: a locked `place()`, then the existing board, then the part's entry in the placements file (`source`, "Placements file"), then `place()`, then the build's staging (later, c0022's placer). `prepare` SHALL call it, and `cmd_build` SHALL pass the result to `build_design` as its `placements`.
- `placements` MUST be `dsl.placements(design)` (c0011): component path → an object with `at`, `rotation`, `side` and `locked`. "Locked" means `place(…, locked=True)` in the script.
- `source` MUST map component paths to `SourcePlacement` entries. An entry that wins MUST be given as a `KeptPlacement` with the entry's position, rotation, side and lock, so the build writes the entry's lock; that lock gives the entry no precedence.
- For a matched part: a locked `place()` MUST win. Otherwise, when its footprint is off the board, the part's `source` entry MUST win, then its `place()`, and without either the part MUST be left unplaced, so the build stages it again (`layout.unplaced`). Otherwise the footprint's own position, rotation, side and lock MUST be used, as a `KeptPlacement`.
- A footprint is off the board when its position lies outside the closed bounding box of the points of `design.board.outline`, and only when the board's edge content is absent or is exactly that outline ("Board content outside the design is kept"). Otherwise no footprint counts as off the board.
- For an unmatched part: a locked `place()`, then its `source` entry, then its `place()`; otherwise it is left unplaced and staged by the build.
- Without an existing board, `prepare` MUST return what `effective_placements` gives with an empty match and `board=None`, which is `placements` unchanged when `source` is empty, and no match. With `board=None` no footprint is off the board, and a design without an outline has none either.
- An unlocked `place()` whose position, rotation or side differs from a kept board placement MUST give `layout.place-overridden` (info), naming the part and both placements, with the hint "lock the placement in the script, move the footprint in KiCad, or re-run with --discard-layout". When it differs from a `source` entry that wins, the same code MUST be given with the hint "lock the placement in the script, or edit placements.toml".
- A `source` entry of a part that keeps a board placement different from the entry MUST give `layout.source-stale` (info) naming the part and both placements, with the hint "run fenolite sync --to-source". An entry that names no part of the design MUST give `layout.source-unknown` (warning).
- A locked `place()` that differs from the board's position, rotation, side or lock MUST give `layout.place-forced` (warning), because the footprint is then re-placed from its definition ("Kept and re-placed footprints").

#### Scenario: The board wins over place()
- **GIVEN** a confirmed target-10 blink build in `B` whose board was edited by `edit_blink`
- **WHEN** the build runs again with `--confirm`
- **THEN** `D1` stays 4 mm right of its `place()` position, `issues` holds one `layout.place-overridden` naming `D1`, and the exit code is 0

#### Scenario: A locked place() wins
- **GIVEN** a confirmed blink build whose `U1`, locked in `design.py`, was moved 2 mm down in its board by token edit
- **WHEN** the build runs again with `--confirm`
- **THEN** `U1` is back at its `place()` position and locked, and `issues` holds `layout.place-forced` naming `U1`

#### Scenario: A staged part placed by the script
- **GIVEN** a confirmed build of a blink variant whose `R1` has no `place()`, so it is staged beside the outline, after which `design.py` gains `r1.place(mm(20), mm(10))`
- **WHEN** the build runs again with `--confirm`
- **THEN** `R1` is at (120 mm, 110 mm) and `issues` holds no `layout.unplaced`

#### Scenario: A staged part stays staged
- **GIVEN** the same staged build and `design.py` unchanged
- **WHEN** the build runs again with `--confirm`
- **THEN** `R1` keeps its staged position, `issues` holds one `layout.unplaced` naming `R1`, and every file keeps its bytes

#### Scenario: The file places an unmatched part
- **GIVEN** an existing blink board without `R1`'s footprint, a design whose `R1` has an unlocked `place()`, and a `source` entry for `R1` at another position
- **WHEN** `effective_placements` runs
- **THEN** `R1` takes the entry's placement as a `KeptPlacement`, and the issues hold one `layout.place-overridden` with the hint that names `placements.toml`

#### Scenario: The board wins over a stale file
- **GIVEN** the board edited by `edit_blink` and a `source` entry for `D1` at its `place()` position
- **WHEN** `effective_placements` runs
- **THEN** `D1` keeps its board placement, and the issues hold one `layout.source-stale` naming `D1`

#### Scenario: A locked footprint in the file
- **GIVEN** no existing board and a `source` entry for `R1` with `locked = true`
- **WHEN** the blink is built
- **THEN** `R1` is written at the entry's position with `(locked yes)`, and a later edit of the board still wins over the entry

### Requirement: Kept and re-placed footprints
`lens.preserve.merge_layout(built, board, match, *, net_aliases={}, identities={}) -> Merged` SHALL keep the existing board's own footprint node for every matched part that stays where the board has it, and SHALL use the built copy otherwise. `identities` maps the component path of an alias match to its identity map, which `build_design` computes from the part's definition (`embed.uuid_locators`); an alias match without one MUST be re-placed.
- A matched footprint MUST be kept when its key is `uuid`, `path` or `alias`, its `lib_ref` equals the built component's `lib_footprint_ref`, and the built copy has the footprint's position, rotation, side and lock.
- A kept footprint MUST keep every slot of its node: properties, texts, graphics and pads as edited in KiCad, except its user properties. Its `component_id` MUST become the built component's id, and each pad MUST take the net of the built copy's pad with the same number, or none. The component MUST take the projected `properties` of the kept node, its user properties included, so c0017's "Projected fields on write" passes, and keeps the built `ref` and `value`, which c0017's writer writes into the Reference and Value atoms.
- **User properties belong to the script** (`design-dsl`, "User properties on built footprints"). They are the `property` nodes that the built copy holds after its `fenolite.path` node. For each of them, the kept node's `property` node whose name is equal after `str.casefold()` MUST take its name and value and keep every other child, its uuid, position and visibility included. A missing one MUST be appended after the kept node's last `property` node as the built copy has it, with the uuid `embed.placement_uuid(<component path>, "/footprint/property:<name>")`, which no index-derived uuid equals. A property that the script does not name stays, because one added in KiCad cannot be told from one that the script no longer names. Without a `fenolite.path` node (`H-K-BUILD-PATHPROP` refuted), the kept node keeps its properties.
- **A footprint kept through an alias** MUST take the new identity of its part. Its identity map is `lens.moved.identity_map(old, new, locators)` ("Alias resolution"), where `locators` are the locators of every node of the built copy that holds a `uuid` child. Every `uuid` child of the kept node whose text is a key of the map MUST take the mapped text, and every other `uuid` child MUST stay. Its `fenolite.path` property MUST take the new path. Its `path`, `sheetname` and `sheetfile` children MUST take the built copy's when the built copy has them, and otherwise stay. It MUST give `layout.alias-used` (info) naming both paths and the word `kept`.
- Any other matched footprint MUST be replaced by the built copy, c0011's placed copy at the effective placement, keyed by the component path: with `layout.alias-used` (info) naming both paths and the word `replaced` for an alias match, `layout.footprint-replaced` (warning) when the lib id changed, and `layout.place-forced` from "Placement precedence".
- Footprints MUST keep the board's order; new and re-placed built copies follow in component-path order.
- Later requirements MAY change named slots of a kept node or of a re-placed built copy, such as its fields; each such requirement names this one.

#### Scenario: Silkscreen edit kept
- **GIVEN** the edited target-10 blink board, whose `Reference` property of `R1` is also moved 1 mm by token edit
- **WHEN** the build runs again
- **THEN** that property node is tree-equal to the edited one, and `R1` is listed under `result.preserved.kept`

#### Scenario: Value changed in the script
- **GIVEN** the same board and `R1`'s value set to `4k7` in `design.py`
- **WHEN** the build runs again
- **THEN** `R1`'s `Value` property holds `4k7` and is otherwise tree-equal to the edited node

#### Scenario: User property changed in the script
- **GIVEN** a confirmed target-10 build of a blink variant whose `R1` has `properties={"Part number": "PN-330"}`, whose board then gets `R1`'s `Reference` property moved 1 mm by token edit, after which `design.py` sets `Part number` to `PN-470` and adds `"Supplier code": "S-1"`
- **WHEN** the build runs again and the written board is read with `read_board`
- **THEN** `R1` is listed under `result.preserved.kept`, its `Reference` node is tree-equal to the edited one, its `Part number` node holds `PN-470` with its former uuid and position, a `Supplier code` node follows it, and the read-back `R1` has both values

#### Scenario: Property added in KiCad kept
- **GIVEN** a confirmed blink build whose board gets a hidden property `Note` on `R1` by token edit
- **WHEN** the build runs twice
- **THEN** both builds keep the `Note` node, and the second writes every file with the bytes of the first

#### Scenario: Footprint changed in the script
- **GIVEN** the same board and `R1`'s footprint changed in `design.py` to `Mini:Mini_LED_THT_3mm`
- **WHEN** the build runs again
- **THEN** `R1`'s footprint is `Mini:Mini_LED_THT_3mm` at the position, rotation and side `R1` had on the board, and `issues` holds `layout.footprint-replaced` naming `R1`

#### Scenario: Rename through an alias
- **GIVEN** a confirmed blink build, after which `design.py` renames `R1` to `R7` and calls `d.moved("R1", "R7")`
- **WHEN** the build runs again, and once more after the `moved()` call is removed
- **THEN** the first rebuild keeps the board node of `R1` for `R7`, where `R1` was, with uuid `footprint_uuid("R7")`, `fenolite.path` `R7`, every pad uuid derived from `R7`, `R7` under `result.preserved.kept` and `layout.alias-used`, and the second rebuild matches `R7` by uuid and writes the same bytes

#### Scenario: Silkscreen edit survives a rename
- **GIVEN** a confirmed target-10 blink build whose `Reference` property of `R1` is moved 1 mm by token edit, after which `design.py` renames `R1` to `R7` and calls `d.moved("R1", "R7")`
- **WHEN** the build runs again
- **THEN** the `Reference` node of `R7` is tree-equal to the edited node of `R1` except for its uuid, which is `placement_uuid("R7", <its locator>)`

#### Scenario: Item added in KiCad keeps its uuid
- **GIVEN** the same build whose footprint of `R1` gets, by token edit, an `fp_line` on `F.SilkS` with the uuid `00000000-0000-4000-8000-0000000000e1`, and the same rename
- **WHEN** the build runs again
- **THEN** the footprint of `R7` holds that line with that uuid

#### Scenario: Alias with a new footprint is re-placed
- **GIVEN** the same rename, with `R7`'s footprint changed in `design.py` to `Mini:Mini_LED_THT_3mm`
- **WHEN** the build runs again
- **THEN** `R7` is the built copy at `R1`'s board placement, `issues` hold `layout.alias-used` with the word `replaced` and `layout.footprint-replaced`

### Requirement: Orphan and board-only footprints
`lens.preserve.merge_layout` SHALL remove every orphan footprint and SHALL keep every board-only footprint.
- An orphan, a footprint that carries `fenolite.path` and matched no part, MUST be removed, with `layout.orphan` (warning) naming its reference, path, uuid and position. The items on its nets follow "Copper items follow their nets".
- A board-only footprint, one without `fenolite.path` that matched no part (for example a mounting hole added in KiCad), MUST be kept verbatim with the component that `read_board` gives it, which joins the layout's circuit and so the `.fenolite/` model. Its pads MUST take the design's net of the same name, or none, and it MUST give `layout.board-only` (info).
- Each pin of a board-only component MUST be a member of every net that a pad of its number takes, and of no other net, so the layout's circuit and the written board give each of its numbered pads the same net.
- A board-only component MUST keep the empty `lib_symbol_ref` that `read_board` gives it, and its `properties` MUST hold no `fenolite.path` key. That absence marks it as board-only for `check` (`verification-loop`, "Model validation stage").
- A board-only reference equal to a built reference MUST be left to `Design.validate()` (`model.duplicate-ref`, exit 5, nothing written).

#### Scenario: Removed part
- **GIVEN** a confirmed target-10 blink build in `B` whose board was edited by `edit_blink`, and `R1` with its connections removed from `design.py`
- **WHEN** the build runs again with `--confirm`
- **THEN** the board holds no footprint `R1`, `issues` holds `layout.orphan` naming `R1`, and the exit code is 0

#### Scenario: Footprint added in KiCad
- **GIVEN** the same edited board with a footprint `H1` added by token edit, made from `Mini_R_0603` without a `fenolite.path` property, with pad `1` on `GND` and pad `2` on no net
- **WHEN** the build runs twice
- **THEN** `H1` is kept with pad `1` on `GND`, the net `GND` of the `.fenolite/` model lists pin `1` of `H1`'s component and no net lists its pin `2`, `issues` holds `layout.board-only` naming `H1`, and the second build writes the same bytes as the first

#### Scenario: Board-only reference collides
- **GIVEN** the same board with that footprint's reference set to `R1`
- **WHEN** the build runs with `--confirm`
- **THEN** the exit code is 5, `issues` holds `model.duplicate-ref`, and nothing is written

### Requirement: Copper items follow their nets
`lens.preserve.merge_layout` SHALL keep every track, arc, via and zone of the existing board, with all its slots, when it has no net, when its net name is a net of the built design, or when its net name is the old name of a resolved net alias ("Alias resolution") whose new name is a net of the built design, and SHALL drop it otherwise.
- A kept item MUST take the built design's net of the same name, or of the alias's new name; its uuid and every other slot MUST stay unchanged. A pad of a board-only footprint on the old name of a net alias MUST take the new net.
- Each net alias under which at least one item or pad was kept MUST give one `layout.net-alias-used` (info) naming both names and the counts of tracks, arcs, vias, zones and pads.
- Each net that loses items MUST give one `layout.net-removed` (warning) naming the net and the counts of dropped tracks, arcs, vias and zones and of board-only footprint pads left without a net.
- Rule areas (`Keepout`) MUST be kept unchanged.
- Later requirements MAY take named items out of this rule, such as copper or zones that the script declares; each such requirement names this one and the items it takes, and those items follow it instead.

#### Scenario: Tracks intact
- **GIVEN** a confirmed target-9 blink build whose board was edited by `edit_blink`
- **WHEN** the build runs again and the written board is read with `read_board`
- **THEN** both segments and the via of the edit are present with the same uuids, end points, widths, layers and the net `LED_A`

#### Scenario: Net removed
- **GIVEN** the same edited board and a `design.py` in which `R1` pin 2 and `D1` pin 2 are connected to nothing
- **WHEN** the build runs again
- **THEN** the board holds neither segment nor the via, and `issues` holds one `layout.net-removed` naming `LED_A` with 2 tracks and 1 via

#### Scenario: Renamed net keeps its routing
- **GIVEN** a confirmed target-10 blink build edited by `edit_blink`, after which `design.py` renames the net `LED_A` to `LED_ANODE` and calls `d.moved_net("LED_A", "LED_ANODE")`
- **WHEN** the build runs again and the written board is read with `read_board`
- **THEN** both segments and the via of the edit are present with their uuids on `LED_ANODE`, `issues` hold one `layout.net-alias-used` with 2 tracks and 1 via, and no `layout.net-removed`

#### Scenario: Rename without an alias
- **GIVEN** the same edit and rename without the `moved_net()` call
- **WHEN** the build runs again
- **THEN** the board holds neither segment nor the via, and `issues` hold one `layout.net-removed` naming `LED_A`

### Requirement: Board content outside the design is kept
`lens.preserve.merge_layout` SHALL keep the existing board's layers, graphics, texts, rule areas, title block, paper and every opaque root child (setup, stack-up, groups, dimensions and the rest) unchanged, except the group members that follow a renamed footprint, and SHALL keep its edge content in place of the design's outline.
- The layout's `Board` MUST be the existing board with its root slots, so c0017's writer re-emits read content in place.
- Each `members` atom of a root `group` node whose text is a key of the identity map of a footprint kept through an alias ("Kept and re-placed footprints") MUST take the mapped text. No other atom of a group MUST change, and Fenolite MUST NOT add or remove a group.
- When the board holds a `Graphic` on a layer of kind `edge`, every such graphic MUST be kept and the layout's `Board.outline` MUST be `None`. When those graphics are not exactly the lines of the built outline (`line` graphics whose end points, as unordered pairs, equal the outline's edges), `layout.outline-kept` (warning) MUST name both. Without edge graphics, the built outline MUST be used.
- The copper layer names of the board, in table order, MUST equal those of `layers.created_layers(copper)`. Otherwise `layout.copper-mismatch` (error) MUST be given, and nothing is written.

#### Scenario: Board setup kept
- **GIVEN** a confirmed blink build whose board's `setup` child has `(pad_to_mask_clearance 0)` changed to `(pad_to_mask_clearance 0.05)` by token edit
- **WHEN** the build runs again
- **THEN** the written `setup` node is tree-equal to the edited one

#### Scenario: Outline edited in KiCad
- **GIVEN** a confirmed blink build whose right `Edge.Cuts` line is moved 5 mm right, with the top and bottom lines lengthened to meet it, by token edit
- **WHEN** the build runs again
- **THEN** the written edge lines equal the edited ones, `issues` holds `layout.outline-kept`, and the exit code is 0

#### Scenario: Copper count changed in the script
- **GIVEN** a confirmed two-layer blink build and `design.py` changed to `copper=4`
- **WHEN** the build runs again with `--confirm`
- **THEN** the exit code is 5, `issues` holds `layout.copper-mismatch`, and nothing is written

#### Scenario: Group follows a renamed footprint
- **GIVEN** a confirmed target-10 blink build whose board gets, by token edit, a root `group` with the uuid `00000000-0000-4000-8000-0000000000f1` holding the footprints of `R1` and `D1`, after which `design.py` renames `R1` to `R7` with `d.moved("R1", "R7")`
- **WHEN** the build runs again
- **THEN** the group holds `footprint_uuid("R7")` and `D1`'s uuid, in the order of the edited group, and keeps its own uuid

### Requirement: Zone fills and the staleness digest
A rebuild SHALL keep the fills of a kept zone only when `zone_digest` of that zone and `fill_inputs_digest` of the board are both equal for the existing board and for the layout to be written; otherwise `lens.preserve.drop_stale_fills` SHALL drop that zone's fills, set its `filled` to false, and report `zone.fill-stale` (warning).
- `zone_digest(design, zone) -> str` MUST be the SHA-256 hex digest of a canonical text of: the outline points, or, when the outline is empty, the texts of the zone's opaque `polygon` slots; the net name; the layers; the priority; the canonical JSON of `zone.settings.effective()`; and the texts of the zone's other opaque slots (among them fill settings that the reader kept opaque). Fills, `filled`, `locked`, uuids and net forms MUST NOT enter it.
- `fill_inputs_digest(design, *, project, rules) -> str` MUST be the SHA-256 hex digest of a canonical text of: every footprint's `lib_ref`, position, rotation, side and modelled pad fields; every track, arc and via's modelled fields; every zone's `zone_digest`; every rule area; every graphic on a layer of kind `edge` and the outline; the classes, patterns and assignments that c0010's `pro.read_project` gives for `project` (none when `None`); and the texts of the rule items of c0018's `parse_rules(rules)` (none when `None`). Nets MUST enter by name; ids, uuids, provenance and slots MUST NOT enter it, and each collection MUST be sorted.
- The existing board MUST be digested with the existing project and rules texts, after its net names are mapped through the resolved net aliases ("Alias resolution"), and the layout with the texts this build writes. A pure rename therefore keeps the fills; a rename that also moves a pin drops them.
- The digests are text only: `lens` never imports `geometry`.

#### Scenario: Unchanged rebuild keeps fills
- **GIVEN** a confirmed blink build whose board gets, by token edit, a zone on `GND` on `B.Cu` holding two authored `filled_polygon` lists
- **WHEN** the build runs again
- **THEN** both fills are written unchanged and `issues` holds no `zone.fill-stale`

#### Scenario: A removed part drops fills
- **GIVEN** the same filled board and `R1` removed from `design.py`
- **WHEN** the build runs again
- **THEN** the zone is kept without fills and with `filled == False`, and `issues` holds `zone.fill-stale` naming it

#### Scenario: A class change drops fills
- **GIVEN** the same filled board and the clearance of class `PWR` changed from 0.2 mm to 0.3 mm in `design.py`
- **WHEN** the build runs again
- **THEN** the zone is kept without fills and `issues` holds `zone.fill-stale`

#### Scenario: A zone setting change drops fills
- **GIVEN** a confirmed build of the blink pour variant whose zone `GND` is declared with `locked=True` and gets, by token edit, `(fill yes …)` and two authored `filled_polygon` lists, after which `design.py` changes the zone's clearance to 0.4 mm
- **WHEN** the build runs again
- **THEN** the zone is written with the clearance 0.4 mm, without fills and without the `yes` atom of `fill`, and `issues` holds `zone.fill-stale` and `kicad.zone.forced`

#### Scenario: Digests ignore ids and formats
- **GIVEN** the filled board of a target-9 build read with `read_board`, and the same board written by `write_board` for target 10 and read again
- **WHEN** `fill_inputs_digest` and `zone_digest` are computed for both with the same project and rules texts
- **THEN** the digests are equal

#### Scenario: A renamed net keeps its fills
- **GIVEN** the filled board of "Unchanged rebuild keeps fills", after which `design.py` renames `GND` to `GND0` and calls `d.moved_net("GND", "GND0")`
- **WHEN** the build runs again
- **THEN** the zone is written on `GND0` with both fills, and `issues` hold no `zone.fill-stale`

### Requirement: Project and rules files are merged
`build` SHALL write the project file through c0010's `triad.write_triad(…, existing_project=<existing text>)`, and SHALL write the rules file through `lens.preserve.merge_rules(lowered, existing, *, target, file="", allow_lossy=False, issues=None) -> str` when an existing rules text is given.
- `write_triad` merges with c0010's `update_project`, which keeps every key Fenolite does not own.
- `merge_rules` MUST take every item of `parse_rules(lowered)` (the version item and Fenolite's rules), followed by every item of `parse_rules(existing, file=file)` except its version item and the rule items whose name starts with `fenolite_` (c0018's lowered names), in file order, and print them with `print_rules`. The text MUST then go through `write_rules(read_rules(text), target=target, allow_lossy=allow_lossy, issues=issues)`, so c0018's target gating and self-check apply to the user's rules too; its result is the written text.
- The user's rules therefore follow Fenolite's, and the later rule governs (`H-K-DRU-ORDER`).
- `build` MUST pass `file="<name>.kicad_dru"`, so a parse error names the file and its line.
- An existing rules file whose version is 2 or more MUST raise `FutureFormatError` (`FEN-3002`).

#### Scenario: User rule kept after Fenolite's
- **GIVEN** a confirmed blink build whose `blink.kicad_dru` gets a comment line and `(rule user_gap (constraint clearance (min 0.3mm)))` after `(version 1)`
- **WHEN** the build runs twice
- **THEN** the written file holds `(version 1)`, then the comment and `user_gap`, both builds write the same bytes, and `read_rules` gives `user_gap` priority 1

#### Scenario: Ten-only user rule for target 9
- **GIVEN** a confirmed target-9 blink build whose rules file gets `(rule mask (constraint bridged_mask))`
- **WHEN** the build runs again with `--confirm`, and then with `--allow-lossy --confirm`
- **THEN** the first exits 7 with `FEN-7001` and `kicad.token.too-new`, and the second exits 0 with the rule dropped and `rules.dropped-for-target` in `issues`

#### Scenario: User class kept in the project
- **GIVEN** a confirmed blink build whose `blink.kicad_pro` gets a net class `USER` by JSON edit
- **WHEN** the build runs again
- **THEN** the written project still holds the class `USER`, and `PWR` keeps the values of `design.py`

### Requirement: Preservation is the build's normal form
`lens.build.build_design` SHALL derive the layout it reports and caches from the board text it writes: `BuildOutput.layout` and the `.fenolite/` layer files MUST be `merge_layout` of the built model with `read_board(that text, file="<name>.kicad_pcb")`, matched by `match_footprints`. The issues of that read and merge MUST NOT be reported, because they describe Fenolite's own output.
- Without an existing board, the board text MUST be c0011's: `write_triad` of the built model.
- With one, the board text MUST be `write_board`'s for the merged layout, after `drop_stale_fills` has removed the fills whose digests changed.
- So a rebuild over the build's own output MUST write identical bytes for every file, `.fenolite/` included and `.bak` files excluded. The first rebuild over a board saved by KiCad rewrites it in Fenolite's form, and the next rebuild MUST NOT change it.
- Deleting `.fenolite/` and rebuilding MUST restore the same bytes (`design-model`, "Layout authority").
- The values of `--seed`, `--timestamp` and `PYTHONHASHSEED` MUST NOT change any file, and no output MUST hold an absolute path or a date.

#### Scenario: Fresh build unchanged
- **WHEN** the blink is built into an empty folder for targets 9 and 10
- **THEN** `blink.kicad_pcb` equals the text of `write_board(output.design, target=…)`, and `match_footprints(output.design, read_board(that text))` matches `U1`, `R1` and `D1` with key `uuid`

#### Scenario: Two rebuilds over a routed board
- **GIVEN** confirmed target-9 and target-10 blink builds whose boards were edited by `edit_blink`
- **WHEN** `uv run pytest tests/unit/lens/test_preserve_determinism.py` rebuilds each twice, in-process and by subprocess with `PYTHONHASHSEED=1` and `--seed 1`, then `PYTHONHASHSEED=2` and `--seed 2`
- **THEN** the second rebuild writes every file with the bytes of the first

#### Scenario: Cache regenerated over a routed board
- **GIVEN** such a rebuilt folder whose `.fenolite/` is deleted
- **WHEN** the build runs again
- **THEN** `.fenolite/` holds the same seven files with the same bytes as before

### Requirement: Layout issue codes
`lens.preserve` SHALL report its findings only with the codes of the closed table `PRESERVE_ISSUE_CODES`, which `lens.build.BUILD_ISSUE_CODES` includes; every `kicad.*` code, of the readers, the writers and the backend merges that later requirements call from `merge_layout`, the `rules.*` codes and the `model.*` codes MUST pass through unchanged.

| code | severity | when |
|---|---|---|
| `layout.copper-mismatch` | error | the board's copper layers differ from `board(copper=…)` |
| `layout.source-invalid` | error | a table or key of `placements.toml` is invalid |
| `layout.orphan` | warning | a footprint with `fenolite.path` matched no part and is removed |
| `layout.alias-unused` | warning | a part alias, given or expanded from a module alias, matched nothing, or its part matched by uuid or path |
| `layout.net-alias-unused` | warning | a `moved_net(old, new)` alias names no net of the board |
| `layout.source-unknown` | warning | a table of `placements.toml` names no part of the design |
| `layout.place-forced` | warning | a locked `place()` re-placed a footprint whose board placement differed |
| `layout.footprint-replaced` | warning | the part's footprint lib id changed; the footprint is re-placed |
| `layout.net-removed` | warning | items on a net the design no longer has were dropped |
| `layout.outline-kept` | warning | the board's edge content differs from the design's outline and is kept |
| `zone.fill-stale` | warning | a zone's fills were dropped because a digest changed |
| `layout.place-overridden` | info | an unlocked `place()` differs from the kept board placement or from the `placements.toml` entry that wins |
| `layout.alias-used` | info | a part was matched through an alias and kept or re-placed under its new path |
| `layout.net-alias-used` | info | items of a board net were kept under the net's new name |
| `layout.source-stale` | info | a `placements.toml` entry differs from the kept board placement |
| `layout.board-only` | info | a footprint without `fenolite.path` matched no part and is kept |

#### Scenario: Closed set enforced
- **WHEN** `uv run pytest tests/unit/lens/test_preserve_issues.py -k closed_set` collects every issue code produced by the preservation tests
- **THEN** each code other than `kicad.*`, `rules.*`, `model.*` and the codes of c0011's table is a key of `PRESERVE_ISSUE_CODES` with the severity of this table, and every key is produced by at least one test

#### Scenario: Warnings do not fail
- **GIVEN** the edited blink with `R1` removed from `design.py`
- **WHEN** the build runs with `--confirm`
- **THEN** the exit code is 0 and `issues` holds `layout.orphan`

### Requirement: Layout preservation evidence
`lens.preserve.EVIDENCE` SHALL be `Evidence(Level.INFERRED, hypotheses=("H-K-LENS-KEEP", "H-K-LENS-FILL", "H-K-UUID-KEEP-2", "H-K-BUILD-PATHPROP"))`, and the `build` envelope SHALL combine it only when an existing board was read.
- The level MUST stay `INFERRED` even when `H-K-LENS-KEEP` is `KICAD-VERIFIED`: that row covers the edited blink, not every board.
- `result.preserved` MUST report `board` (whether an existing board was read), `kept`, `replaced` and `added` (component paths), `orphans` and `board_only` (references), `dropped` (counts of tracks, arcs, vias and zones), `fills` (counts kept and dropped), `aliases` (new path → old path) and `reader_infos` (a count).
- Later requirements MAY add keys to `result.preserved`; each such requirement names this one.

#### Scenario: Envelope over an existing board
- **GIVEN** a confirmed blink build in `B`
- **WHEN** the build runs again with `--dry-run --json`
- **THEN** `evidence.level` is `INFERRED`, `evidence.hypotheses` contains `H-K-LENS-KEEP`, and `result.preserved.board` is `true`

#### Scenario: Fresh envelope
- **WHEN** the blink is built into an empty folder with `--dry-run --json`
- **THEN** `evidence.hypotheses` does not contain `H-K-LENS-KEEP`, and `result.preserved.board` is `false`

### Requirement: Layout facts are documented
The preservation rules and the facts they rely on SHALL be documented in Fenolite's own words, with sources and evidence labels.
- `docs/lens.md` (new) MUST cover the keys and their order, `moved()`, the precedence and the off-board rule, what is kept, re-placed or dropped, the script's user properties on kept footprints, board-only footprints, the outline rule, the two digests, the project and rules merge, the normal form, `--discard-layout`, the issue codes and the evidence.
- `docs/dsl.md` MUST describe `Design.moved` and `moves`; `docs/cli-contract.md` MUST describe `result.preserved` and the narrowed `build.layout-exists`.
- `docs/formats/kicad/board.md` MUST hold, as fact rows with source, label and hypothesis, the re-save facts the oracle measures (`H-K-LENS-KEEP`).
- `docs/hypotheses.md` MUST register `H-K-LENS-KEEP` and `H-K-LENS-FILL`.

#### Scenario: Registers hold the new rows
- **WHEN** `grep -c '^| H-K-LENS-' docs/hypotheses.md` runs
- **THEN** it prints `2`

#### Scenario: Fact tables are labelled
- **WHEN** `uv run pytest tests/unit/test_format_facts.py tests/unit/test_hypotheses_register.py` runs
- **THEN** it passes, and every new row of `board.md` has a source id, a valid label and, below `KICAD-VERIFIED`, a hypothesis

### Requirement: Script copper in a merge
`lens.preserve.merge_layout(built, board, match)` SHALL pass the existing board and the built design to `copper.merge_copper` (`manual-copper`, "Script copper is regenerated") and SHALL keep only the existing tracks, arcs and vias that it keeps; "Copper items follow their nets" then applies to those, and the built design's tracks and vias whose KiCad uuid is a copper uuid MUST follow them in the layout, in the built order.
- This takes out of "Copper items follow their nets" exactly the existing tracks, arcs and vias that `merge_copper` drops: those whose KiCad uuid is a copper uuid, and those without one that equal a script item.
- The issues of `merge_copper` (`kicad.copper.stale`, `kicad.copper.regenerated`, `kicad.copper.duplicate`) MUST join the merge's issues; as `kicad.*` codes they pass through `PRESERVE_ISSUE_CODES` unchanged, as "Layout issue codes" allows, and `result.copper` counts them.
- A footprint moved in KiCad therefore pulls its script copper along on the next build; an intent removed from the script removes its copper; copper drawn in KiCad, whose uuid is not a copper uuid, stays under "Copper items follow their nets".
- `lens.preserve` still never imports `geometry`: `merge_copper` compares points and fields as integers and texts.

#### Scenario: Copper follows a moved footprint
- **GIVEN** a confirmed target-10 build of `examples/blink_routed/design.py` in `B`, whose board had `D1` moved 4 mm to the right by `tests/_layout_edit.py::move_footprint`
- **WHEN** the build runs again with `--confirm` and the written board is read with `read_board`
- **THEN** the `led_a` track that ends at `D1` pad `2` ends at the pad's new position with its uuid unchanged, `issues` hold one `kicad.copper.regenerated` per moved track and no `kicad.copper.stale`

#### Scenario: Removed intent, removed copper
- **GIVEN** the same confirmed build and the stitch intent `gnd_fence` removed from `design.py`
- **WHEN** the build runs again with `--confirm`
- **THEN** the board holds none of its vias, and `issues` hold one `kicad.copper.stale` warning per removed via

#### Scenario: KiCad edit of script copper is replaced
- **GIVEN** the same confirmed build whose `led_drv` segment `seg[0]` was moved 1 mm by token edit, keeping its uuid
- **WHEN** the build runs again with `--confirm`
- **THEN** the segment is back at its pads, and `issues` hold one `kicad.copper.regenerated` naming its uuid

#### Scenario: Copper drawn in KiCad is kept
- **GIVEN** the same confirmed build with one `GND` track added by token edit with a version-4 uuid
- **WHEN** the build runs twice
- **THEN** the track is kept, and the second build writes every file with the bytes of the first

### Requirement: Footprint fields across rebuilds
`lens.fields.merge_fields(merged, board, match, requests) -> FieldMerge` SHALL decide every field of a matched part when a build merges an existing board, with this precedence: a locked request, then the board's field, then an unlocked request, then the library's field. GUI edits therefore win over generated placements unless the script locks them.
- `build_design` MUST call it on the `Merged` result of `merge_layout`, with `prepared.board`, `prepared.match` and its `fields` keyword, before the merged layout is validated and written. The normal-form pass of "Preservation is the build's normal form" MUST NOT call it, because the written board already holds the merged fields.
- **Kept footprints** (the board's own node, "Kept and re-placed footprints"): each field MUST stay as `merge_layout` left it, the board's field with the script's user-property values ("User properties" below), except that every locked request MUST be applied with `apply_requests`, resolved against the kept footprint, so a value that the request does not give keeps the board's. A request for a field that the kept footprint no longer holds is skipped. An unlocked request whose result differs from the board's field MUST NOT be applied.
- **Re-placed footprints** whose `lib_ref` and side equal those of the matched board footprint: each field of the built copy that the board footprint also has MUST take the values of the board's field (position, rotation, layer, size, thickness, visibility, justification and mirror), unless a locked request names it. The field keeps the built copy's id, uuid and slot list.
- Every other footprint keeps the fields of the built copy, that is the library's fields with every request applied.
- **User properties.** "Kept and re-placed footprints" gives the values of a kept footprint's user properties to the script and keeps everything else from the board. After this change `merge_layout` MUST apply that rule to fields, and `merge_fields` MUST leave what it sets:
  - a user property that is a field of the kept footprint (same name after `str.casefold()`) MUST keep the board's position, rotation, layer, size, thickness, visibility, justification, mirror, uuid and every other slot; only the `Opaque` slot of its value atom MUST take the script's value, and its name the script's spelling;
  - a missing user property MUST be added after the kept footprint's last field as the built copy's field, with that field's slot list, `native_ids["kicad"]` equal to `embed.placement_uuid(<component path>, "/footprint/property:<name>")` and the id that "Footprint fields on boards" derives for the kept footprint, so the writer emits it after the last field node (`kicad-slots`, "Order-preserving rebuild");
  - a user property whose node is not a field stays a projected `Opaque` slot of the footprint and MUST be edited as "Kept and re-placed footprints" says;
  - the component MUST take the script's values, so "Projected fields on write" passes. Requests never name a user property, and user properties never enter `kept`, `forced` or `carried`.
  On a re-placed footprint the built copy's fields already hold the script's values; only their placement and appearance come from the board, as above.
- `FieldMerge` MUST hold `design` and three sorted lists of `"<component path>:<field name>"`: `kept` (unlocked requests whose result differs from the board's field, which wins on a kept or re-placed footprint; the result is the request applied to the footprint that holds the board's field values), `forced` (locked requests that changed a board field) and `carried` (fields of re-placed footprints changed by taking the board's values). `result.preserved.fields` MUST report the three lists, empty when no existing board was read; "Layout preservation evidence" allows the key.
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

### Requirement: Zones declared in the script
`lens.preserve.merge_layout(built, board, match)` SHALL merge the zones of the built design, which `design-dsl` "Zones in the DSL" declares, with the zones of the existing board through `fenolite.backends.kicad.zones.merge_zones(built, board)`. For the board zones that match a built zone, and those whose uuid is a script-zone uuid (below), it replaces the zone rule of "Copper items follow their nets"; every other zone of the board follows that requirement.
- A built zone and a board zone MUST match when the board zone's KiCad uuid (`native_ids["kicad"]`) equals `pcb.kicad_uuid` of the built zone.
- The values compared for a matched pair are `outline`, `layers`, the net name, `priority`, `locked` and `settings.effective()`.
- A matched board zone MUST be kept with all its slots, and take the built design's net of its name, when the built zone is not locked or the compared values are equal. When the built design no longer holds a net of that name, the kept zone MUST take the built zone's net. When they differ and the built zone is not locked, `kicad.zone.overridden` (info) MUST name the zone and the values that differ, with the hint "lock the zone in the script, edit it in KiCad, or re-run with --discard-layout".
- When they differ and the built zone is locked, the built zone MUST replace the board zone and take its `fills` and `filled`, which "Zone fills and the staleness digest" then judges, and `kicad.zone.forced` (warning) MUST name the zone and the values that differ.
- A built zone without a match MUST be added after the board's zones, in name order.
- A board zone without a match whose uuid equals `zones.script_zone_uuid(<its name>)`, the uuid that `pcb.kicad_uuid` gives a zone with the id `derived_id("zon", "dsl", "zone:<its name>")`, was written by the script for a zone that it no longer declares. It MUST be removed, with `kicad.zone.orphan` (warning) naming its name and uuid.
- Zone names alone MUST NOT match zones.
- `merge_zones` SHALL report only the codes of the closed table `zones.MERGE_ISSUE_CODES`. They are `kicad.*` codes, so they pass through `lens.preserve.PRESERVE_ISSUE_CODES` and `lens.build.BUILD_ISSUE_CODES` unchanged, as "Layout issue codes" and `design-dsl` "Build issue codes" allow.

| code | severity | when |
|---|---|---|
| `kicad.zone.forced` | warning | a locked `zone()` replaced a board zone that differed from it |
| `kicad.zone.orphan` | warning | a zone the script wrote for a `zone()` that it no longer declares was removed |
| `kicad.zone.overridden` | info | an unlocked `zone()` differs from the kept board zone |

#### Scenario: Clearance edited in KiCad wins
- **GIVEN** a confirmed target-10 build of the blink pour variant of "Zones in a build", whose zone `GND` gets the clearance 0.5 mm in its `connect_pads` by token edit
- **WHEN** the build runs again with `--confirm`
- **THEN** the exit code is 0, the written zone node is tree-equal to the edited one, and `issues` holds `kicad.zone.overridden` naming `GND` and `settings`

#### Scenario: A locked zone wins
- **GIVEN** the same edited build, and the script's zone declared with `locked=True`
- **WHEN** the build runs again with `--confirm`
- **THEN** the written zone has the clearance 0.3 mm and holds `(locked yes)`, and `issues` holds `kicad.zone.forced` naming `GND`

#### Scenario: Zone added to the script
- **GIVEN** a confirmed build of the pour variant, after which `design.py` declares a second zone `VIN_TOP` on `F.Cu`
- **WHEN** the build runs again
- **THEN** the board holds `GND` and then `VIN_TOP`, and `issues` holds no `kicad.zone.*` code

#### Scenario: Zone removed from the script
- **GIVEN** a confirmed build with the zones `GND` and `VIN_TOP`, after which `VIN_TOP` is removed from `design.py`
- **WHEN** the build runs again
- **THEN** the board holds only `GND`, and `issues` holds `kicad.zone.orphan` naming `VIN_TOP`

#### Scenario: Zone drawn in KiCad
- **GIVEN** a confirmed build of the pour variant whose board gets, by token edit, a second zone on `GND` that is also named `GND`, with the uuid `00000000-0000-4000-8000-0000000000a1`
- **WHEN** the build runs again
- **THEN** both zones are written, and `issues` holds no `kicad.zone.*` code

#### Scenario: Fresh builds report no zone code
- **WHEN** the pour variant is built into an empty folder for targets 9 and 10
- **THEN** `issues` holds no `kicad.zone.*` code

#### Scenario: Zone merge codes are closed
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_zone_merge.py -k closed_set` collects every issue code that `merge_zones` produces in its tests
- **THEN** each is a key of `MERGE_ISSUE_CODES` with the severity of this table, and every key is produced by at least one test

### Requirement: Pad zone connections across rebuilds
`lens.build.build_design` SHALL decide the zone connection of every pad that a request names (`design-dsl`, "Pad zone connections in the DSL") when a build merges an existing board, with this precedence: a locked request, then a setting that the pad carries on the board, then an unlocked request, then the pad of the library footprint. A setting made in KiCad therefore wins over the script unless the script locks the request, as for zones ("Zones declared in the script") and fields ("Footprint fields across rebuilds").
- The step MUST run on the `Merged` result of `merge_layout`, after `merge_fields` and before the merged layout is validated and written. The normal-form pass of "Preservation is the build's normal form" MUST NOT run it, because the written board already holds the decided pads.
- **Kept footprints** (the board's own node, "Kept and re-placed footprints"). Each named pad MUST be decided by `fenolite.backends.kicad.zones.keep_pad_connections(kept, requests, *, where, issues=None) -> FootprintInstance`, `where` being the component path:
  - a pad whose `zone_connection` equals the request stays as it is, without an issue;
  - a pad whose `zone_connection` is `None`, that is a pad without a setting of its own on the board, MUST take the request's value, locked or not, without an issue;
  - a pad that carries another value than an unlocked request MUST stay as the board has it, with one `kicad.pad.zone-overridden` (info) naming the part, the pad, both values and the hint "lock the request in the script, edit the pad in KiCad, or re-run with --discard-layout";
  - a pad that carries another value than a locked request MUST take the request's value, with one `kicad.pad.zone-forced` (warning) naming the part, the pad and both values;
  - a request whose number or index the kept footprint does not have MUST give `kicad.pad.zone-unknown-pad`, as on a built copy.
- **Re-placed and new footprints** keep the pads of the built copy: the library's pads with every request applied (`design-dsl`, "Pad zone connections in a build"). A pad edit made in KiCad is not carried to a re-placed footprint.
- A pad that no request names MUST stay as "Kept and re-placed footprints" leaves it: as edited in KiCad on a kept footprint.
- `keep_pad_connections` MUST be pure and MUST change nothing but `Pad.zone_connection` of the named pads. Run again on its own result with the same requests, it MUST return an equal footprint, and a locked request then reports nothing.
- `result.preserved.pad_zones` MUST hold two sorted lists of `"<component path>:<pad number>"`, each entry once: `kept` (unlocked requests that differ from the setting of a board pad) and `forced` (locked requests that replaced the setting of a board pad). Both are empty when no existing board was read; "Layout preservation evidence" allows the key.

#### Scenario: A pad edited in KiCad wins over an unlocked request
- **GIVEN** a confirmed target-10 build of the blink pour variant whose `design.py` calls `d1.zone_connection(1, "solid")`, whose board then gets `(zone_connect 1)` in pad `1` of `D1` by token edit
- **WHEN** the build runs again with `--confirm`
- **THEN** the written pad holds `(zone_connect 1)`, `issues` holds one `kicad.pad.zone-overridden` naming `D1`, pad `1`, `solid` and `thermal`, and `result.preserved.pad_zones` has `kept == ["D1:1"]` and an empty `forced`

#### Scenario: A locked request wins
- **GIVEN** the same edited board, and the request in `design.py` given `locked=True`
- **WHEN** the build runs again with `--confirm`
- **THEN** the written pad holds `(zone_connect 2)`, `issues` holds one `kicad.pad.zone-forced`, and `result.preserved.pad_zones.forced == ["D1:1"]`

#### Scenario: A request added after the first build
- **GIVEN** a confirmed build of the pour variant without a request, after which `design.py` gains `d1.zone_connection(1, "solid")`
- **WHEN** the build runs again with `--confirm`
- **THEN** `D1` is listed under `result.preserved.kept`, its pad `1` gains `(zone_connect 2)`, `issues` holds no `kicad.pad.*` code, and both lists of `result.preserved.pad_zones` are empty

#### Scenario: Rebuilds of an unedited board are quiet and stable
- **GIVEN** a confirmed target-9 build of the variant with the unlocked request
- **WHEN** the build runs twice more with `--confirm`
- **THEN** both lists are empty, `issues` holds no `kicad.pad.*` code, and both rebuilds write every file with the bytes of the first build

#### Scenario: A re-placed footprint takes the request
- **GIVEN** the edited board of the first scenario, and `D1` given a locked `place()` 2 mm to the right of its board position
- **WHEN** the build runs again with `--confirm`
- **THEN** `D1` is re-placed (`layout.place-forced`), its pad `1` holds `(zone_connect 2)`, and `issues` holds no `kicad.pad.*` code

### Requirement: Alias resolution
`fenolite.lens.moved` SHALL resolve the aliases of a build: `resolve_aliases(design, board, *, moves, module_moves, net_moves) -> tuple[Aliases, tuple[Issue, ...]]`, with `Aliases(parts, modules, nets, explicit_nets)`, and `identity_map(old, new, locators) -> Mapping[str, str]`.
- The module MUST import only the standard library, `core`, `model` and `backends`, and every function MUST be pure.
- `parts` MUST equal `moves`, the expanded part aliases of `dsl.moves` (new path → old path), and `modules` MUST equal `module_moves` (`design-dsl`, "Path aliases in the DSL").
- `nets` (new name → old name) MUST hold every entry of `net_moves` whose old name is a net of `board`. For every other net of `board` whose name is not a net of `design` and starts with `<old>/` for a module alias `new → old`, it MUST hold `<new>/<rest> → <name>` when `<new>/<rest>` is a net of `design` that no entry of `net_moves` names. When several module aliases apply, the longest `old` MUST win.
- `explicit_nets` MUST be the keys of `nets` that come from `net_moves`.
- An entry of `net_moves` whose old name is not a net of `board` MUST give `layout.net-alias-unused` (warning) naming both names. With `board=None`, `nets` MUST be empty and no issue given.
- `identity_map(old, new, locators)` MUST return `{embed.placement_uuid(old, loc): embed.placement_uuid(new, loc)}` for every locator given.
- `result.preserved` MUST gain `module_aliases` (new module path → old) and `net_aliases` (new name → old), empty without an existing board; "Layout preservation evidence" allows the keys.

#### Scenario: Module alias with its nets
- **GIVEN** a design holding `Module("supply")` with parts `R1` and `R2` and the net `supply/FB`, with `d.moved("power", "supply")`, and a board holding the net `power/FB`
- **WHEN** `resolve_aliases` runs with the values of `dsl.moves`, `dsl.module_moves` and `dsl.net_moves`
- **THEN** `parts` is `{"supply/R1": "power/R1", "supply/R2": "power/R2"}`, `nets` is `{"supply/FB": "power/FB"}`, `explicit_nets` is empty and no issue is given

#### Scenario: An explicit net alias wins
- **GIVEN** the same design with its net renamed `supply/VFB` and `d.moved_net("power/FB", "supply/VFB")`
- **WHEN** the aliases are resolved
- **THEN** `nets` is `{"supply/VFB": "power/FB"}` and `explicit_nets` is `("supply/VFB",)`

#### Scenario: Explicit alias without a board net
- **GIVEN** `d.moved_net("VX", "VY")` and a board without a net `VX`
- **WHEN** the aliases are resolved
- **THEN** `nets` is empty and the issues hold one `layout.net-alias-unused` naming `VX` and `VY`

#### Scenario: Identity map
- **WHEN** `identity_map("R1", "R7", ["/footprint", "/footprint/pad[0]"])` is called
- **THEN** it maps `placement_uuid("R1", "/footprint")` to `placement_uuid("R7", "/footprint")` and `placement_uuid("R1", "/footprint/pad[0]")` to `placement_uuid("R7", "/footprint/pad[0]")`, and holds nothing else

### Requirement: Placement extraction
`fenolite.lens.extract.extract_placements(board, match, *, design) -> Extracted` SHALL give the placement of every matched footprint that lies on the board, with `Extracted(placements, unplaced)`.
- `placements` MUST map each component path of `match.matches` whose footprint is not off the board ("Placement precedence") to a `SourcePlacement` ("Placements file") with the footprint's position in the written frame, its rotation, its side and its lock, in path order.
- `unplaced` MUST list the other matched paths, in path order: a staged part copied into the file would look placed and lose its `layout.unplaced` warning.
- Orphans and board-only footprints MUST NOT be extracted.
- The function MUST be pure and MUST import neither `geometry` nor `dsl`.

#### Scenario: Moved footprint extracted
- **GIVEN** the board of a target-10 blink build edited by `edit_blink`, read with `read_board`, and its match
- **WHEN** `extract_placements` runs
- **THEN** `placements` holds `D1`, `R1` and `U1`, the entry of `D1` is 4 mm right of its `place()` position in the written frame, and `unplaced` is empty

#### Scenario: Staged part not extracted
- **GIVEN** the board of a blink variant whose `R1` has no `place()` and is staged beside the outline
- **WHEN** `extract_placements` runs
- **THEN** `placements` holds no `R1`, and `unplaced` is `("R1",)`

### Requirement: Placements file
`fenolite.lens.placements` SHALL read and write `placements.toml`, the committed copy of a layout's placements, with `SCHEMA = "fenolite.placements.v0"`, `FILE_NAME = "placements.toml"`, `SourcePlacement(at, rotation, side, locked)`, `PlacementsFile(entries, issues)`, `read_placements(text, *, origin, file="") -> PlacementsFile` and `write_placements(entries, *, origin) -> str`.
- **Form.** The top-level key `schema` MUST be `SCHEMA`. Each entry MUST be a table `[part."<component path>"]` with the keys `x` and `y` (millimetres, both required), `rotation` (degrees, default 0), `side` (`"top"` or `"bottom"`, default `"top"`) and `locked` (boolean, default false). No other key is allowed.
- **Frame.** `x` and `y` are the position in the frame of `place()`: `SourcePlacement.at` MUST be `origin` plus (`x`, `y`) on reading, and `write_placements` MUST print `at` minus `origin`. Callers pass `dsl.BOARD_ORIGIN`.
- **Values.** The text MUST be read with `tomllib` and `parse_float=Decimal`, so no float is created. `x` and `y` MUST be whole nanometres and `rotation` whole microdegrees in [0, 360). `locked` is the footprint's lock in KiCad, never a precedence ("Placement precedence").
- **Errors.** A text that is not TOML, or whose `schema` is missing or differs, MUST raise `FormatError` (`FEN-3004`) naming `file`. A table whose path is not a component path, an unknown key, a missing `x` or `y`, a value off its unit or of the wrong type, or a `side` other than the two names MUST give `layout.source-invalid` (error) naming the table and the key, and that entry MUST be left out.
- **Printing.** `write_placements` MUST write the comment `# Written by fenolite sync --to-source.`, the `schema` line, an empty line, then one table per entry in component-path order, each with `x`, `y`, `rotation`, `side` and `locked` in this order. Numbers MUST be printed in their shortest exact decimal form (`30`, `12.7`, `-0.000001`). Nothing MUST depend on the clock, the platform or `PYTHONHASHSEED`.
- **Round trip.** `read_placements(write_placements(entries, origin=o), origin=o).entries` MUST equal `entries` for every mapping of component paths to whole-unit placements.

#### Scenario: Position in millimetres
- **GIVEN** the text `schema = "fenolite.placements.v0"`, `[part."power/R1"]`, `x = 12.7`, `y = 30`, `rotation = 90`
- **WHEN** it is read with `origin` (100 mm, 100 mm)
- **THEN** `power/R1` has `at == Point(112_700_000, 130_000_000)`, rotation `90_000_000`, side `top` and `locked` false, and no issue is given

#### Scenario: Value off the nanometre
- **GIVEN** an entry with `x = 1.0000005`
- **WHEN** it is read
- **THEN** the issues hold one `layout.source-invalid` naming the table and `x`, and the entry is left out

#### Scenario: Missing schema
- **GIVEN** a text with one table and no `schema` key
- **WHEN** it is read with `file="placements.toml"`
- **THEN** `FormatError` is raised naming `placements.toml`

#### Scenario: Round trip
- **WHEN** `uv run pytest tests/unit/lens/test_placements_file.py -k round_trip` runs its property test over generated entries
- **THEN** every printed text reads back to its entries, and printing them again gives the same text

### Requirement: Symbol placement extraction
`fenolite.lens.schplacements` SHALL gain `extract_symbol_placements(sheets, *, design) -> tuple[Mapping[str, SymbolPlacement], tuple[Issue, ...]]` and `write_placements(entries) -> str`, which turn the symbols of a generated schematic, as edited in KiCad, into the text of `schematic-placements.toml` that `read_placements` reads (`design-dsl`, "Schematic placements file", c0061).
- `sheets` MUST be the sheets that `sch.read_schematic` (c0060) gives for the root file and for every child sheet file it names.
- Each placed symbol unit whose `fenolite.path` property is a component path of `design` MUST give an entry keyed `<path>` for unit 1 and `<path>#<unit>` above it, with its position, rotation and mirror. Symbols without that property, power flags included, MUST give no entry and no issue.
- A position off the 1.27 mm grid, or a (rotation, mirror) pair outside `schlayout.PROVED_FRAMES`, MUST give `sync.symbol-off-grid` (warning) naming the key, and no entry.
- `write_placements` MUST print one table per entry in key order, with `x` and `y` in millimetres in their shortest exact decimal form, then `rotation` when it is not 0 and `mirror` when the symbol is mirrored. `read_placements` of the text MUST give the entries back.

#### Scenario: Moved symbol extracted
- **GIVEN** the schematic of a target-10 blink build whose symbol `R1` was moved 2.54 mm to the right by token edit, read with `sch.read_schematic`
- **WHEN** `extract_symbol_placements` runs and its entries are printed and read back with `read_placements`
- **THEN** `R1` is 2.54 mm right of its generated position, no issue is given, and the read-back entries equal the extracted ones

#### Scenario: Symbol off the grid
- **GIVEN** the same schematic with `R1` moved 1 mm instead
- **WHEN** `extract_symbol_placements` runs
- **THEN** the result has no `R1` entry, and the issues hold one `sync.symbol-off-grid` naming `R1`

### Requirement: Sync of the source tree
`fenolite.lens.sync.plan_sync(design, existing, *, name, aliases, origin, placements_text, symbol_placements_text, sheets) -> SyncPlan` SHALL compute what `fenolite sync --to-source` writes and reports, without reading or writing a file, with `SyncPlan(files, result, issues)`.
- `existing` MUST be the `ExistingProject` of the output folder; its board text MUST be present, and the board MUST be read, refused and matched as "Existing project files" and "Footprint matching" do, with `aliases.parts`. `aliases` holds the script's aliases, with the names of `moved_net()` in `nets`; `plan_sync` MUST resolve them against the board with `resolve_aliases`.
- `files` MUST map `placements.toml` to `write_placements(extract_placements(…).placements, origin=origin)` when that text differs from `placements_text` (`None` when the file does not exist). When `sheets` is given, it MUST map `schematic-placements.toml` to the printed symbol placements when that text differs from `symbol_placements_text`.
- `result` MUST hold `board` (the file name), `placements` (the number of entries), `unplaced`, `orphans` and `board_only` (references), `symbols` (the number of symbol entries, or `null` without `sheets`) and `files` (the names in `files`).
- The issues MUST use only the codes of the closed table `SYNC_ISSUE_CODES`, besides those of the board read and of "Symbol placement extraction":

| code | severity | when |
|---|---|---|
| `sync.would-change` | error | with `--check`, a file would change |
| `sync.orphan` | warning | a footprint with `fenolite.path` matches no part; the next build removes it |
| `sync.net-dropped` | warning | the board holds copper on a net that no design net or alias covers; the next build drops it |
| `sync.value-differs` | warning | the board's value, library footprint or user property of a matched part differs from the script's; the next build writes the script's |
| `sync.symbol-off-grid` | warning | a symbol's position or frame cannot be written to `schematic-placements.toml` |

- `sync.would-change` MUST be added by the command, not by `plan_sync`, and MUST name the file and its first table whose text differs.
- `lens.sync.EVIDENCE` MUST equal `lens.preserve.EVIDENCE`.

#### Scenario: Edited board synced
- **GIVEN** a confirmed target-10 blink build in `B` edited by `edit_blink`, and no `placements.toml`
- **WHEN** `plan_sync` runs with `placements_text=None`
- **THEN** `files` holds `placements.toml` with tables for `D1`, `R1` and `U1`, `D1` at `x` 4 mm more than its `place()` value, and no issue is given

#### Scenario: Nothing to write
- **GIVEN** the same build and the text that the first run printed as `placements_text`
- **WHEN** `plan_sync` runs again
- **THEN** `files` is empty

#### Scenario: Orphaned complement reported
- **GIVEN** the same edited board and a `design.py` without `R1`, whose `D1` pin 2 is connected to nothing
- **WHEN** `plan_sync` runs
- **THEN** the issues hold `sync.orphan` naming `R1`, and `sync.net-dropped` naming `LED_A` with its 2 tracks and 1 via

#### Scenario: Value edited in KiCad
- **GIVEN** the same build whose board gets `R1`'s value `4k7` by token edit, while `design.py` keeps `330`
- **WHEN** `plan_sync` runs
- **THEN** the issues hold one `sync.value-differs` naming `R1`, `value`, `4k7` and `330`

#### Scenario: Closed set
- **WHEN** `uv run pytest tests/unit/lens/test_sync.py -k closed_set` collects the codes produced by its tests
- **THEN** each `sync.*` code is a key of `SYNC_ISSUE_CODES` with the severity of the table, and every key is produced by at least one test

### Requirement: Lens acceptance fixture
`tests/unit/lens/test_lens_acceptance.py` SHALL run the plan's lens acceptance on a design authored for Fenolite, for targets 9 and 10, and every check of this requirement MUST hold.
- **Fixture.** `tests/data/lens/acceptance/design.py` MUST use only parts of the Mini test libraries. It MUST hold a part `U1` at the top and two modules, `power` and `io`, with at least three parts each, every part placed by `place()`, and module-local nets named `f"{m.path}/<name>"`, among them `power/FB`.
- **Edits in place of the GUI**, by token edit of the built board with `tests/_layout_edit.py`: five footprints moved by distinct offsets, three of them in `power`; three tracks with version-4 uuids, from pad to pad, on `power/FB`, on a net of `io` and on a top-level net; the `Reference` property of one `power` footprint moved by 1 mm; and a root `group` with a version-4 uuid holding two `power` footprints. When c0061 is archived, the board then passes through `update_from_schematic`.
- **Script edits**: a part `R9` added to `io` without `place()`, and the module `power` renamed `supply` with `d.moved("power", "supply")`.
- **Checks after the rebuild**: every moved footprint has its edited position and rotation; the three tracks keep their uuids, ends, widths and layers, the first on `supply/FB`; the moved `Reference` property is tree-equal to the edited one after the identity map; the group lists the two renamed footprints by their new uuids; `R9` is staged with `layout.unplaced`; `issues` hold no `layout.orphan`, `layout.net-removed`, `layout.footprint-replaced` or `zone.fill-stale`; `result.preserved.kept` lists every part but `R9`.
- **Normal form**: with the `moved()` call removed, the next build MUST write every file with the bytes of the previous one.
- **Source tree**: `fenolite sync --to-source --confirm` MUST then write `placements.toml`, and a `--discard-layout` build into an empty folder MUST place every footprint that was on the board at its edited position.

#### Scenario: Everything preserved through a module rename
- **WHEN** `uv run pytest tests/unit/lens/test_lens_acceptance.py -k rename` runs for targets 9 and 10
- **THEN** every check of the rebuild holds, and the build after the `moved()` call is removed writes the same bytes

#### Scenario: Layout restored from the source tree
- **GIVEN** the rebuilt folder of that test and the `placements.toml` that `sync` wrote
- **WHEN** the design is built with `--discard-layout` into an empty folder
- **THEN** every footprint that was on the board is at its edited position, and `R9` is staged

#### Scenario: After the stand-in update
- **GIVEN** c0061 archived, and the edited board passed through `update_from_schematic` before the script edits
- **WHEN** the same test runs
- **THEN** every check still holds, and the footprints keep their `sheetname` and `sheetfile` children

### Requirement: Complete lens is documented
The additions of this change SHALL be documented in Fenolite's own words.
- `docs/lens.md` MUST gain the sections "Module aliases", "Net aliases", "Renamed footprints keep their edits" (the identity map, group members, and DRC exclusions that have to be made again), "placements.toml" (form, frame, precedence, `--discard-layout`) and "sync" (both files, `--check`, the issues), and its precedence and issue tables MUST match "Placement precedence" and "Layout issue codes".
- `docs/dsl.md` MUST describe `moved()` on module paths and `moved_net()`.
- `docs/hypotheses.md` MUST register `H-K-LENS-RENAME` (backend `kicad`, level `INFERRED`, the test of "Renamed footprints pass the oracle").

#### Scenario: Register holds the new row
- **WHEN** `grep -c '^| H-K-LENS-RENAME ' docs/hypotheses.md` runs
- **THEN** it prints `1`, and `uv run pytest tests/unit/test_hypotheses_register.py` passes

