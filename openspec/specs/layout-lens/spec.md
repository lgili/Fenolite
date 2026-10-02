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
- `prepare(design, placements, existing, *, name, moves={}) -> Prepared` MUST read the board text with `read_board(text, file="<name>.kicad_pcb")`, so the relative file name, never an absolute path, reaches provenance. Reader warnings MUST go to `Prepared.issues`; reader infos MUST only be counted in the build summary.
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
`lens.preserve.effective_placements(placements, match, *, design, board)` SHALL decide each part's placement with the fixed precedence: a locked `place()`, then the existing board, then `place()`, then the build's staging (later, c0022's placer). `prepare` SHALL call it, and `cmd_build` SHALL pass the result to `build_design` as its `placements`.
- `placements` MUST be `dsl.placements(design)` (c0011): component path → an object with `at`, `rotation`, `side` and `locked`. "Locked" means `place(…, locked=True)` in the script.
- For a matched part: a locked `place()` MUST win. Otherwise, when its footprint is off the board, the part's `place()` MUST win, and without one the part MUST be left unplaced, so the build stages it again (`layout.unplaced`). Otherwise the footprint's own position, rotation, side and lock MUST be used, as a `KeptPlacement`.
- A footprint is off the board when its position lies outside the closed bounding box of the points of `design.board.outline`, and only when the board's edge content is absent or is exactly that outline ("Board content outside the design is kept"). Otherwise no footprint counts as off the board.
- For an unmatched part: its `place()` when given; otherwise it is left unplaced and staged by the build.
- Without an existing board, `prepare` MUST return `placements` unchanged, with no match. A design without an outline has no off-board footprint.
- An unlocked `place()` whose position, rotation or side differs from a kept board placement MUST give `layout.place-overridden` (info), naming the part and both placements, with the hint "lock the placement in the script, move the footprint in KiCad, or re-run with --discard-layout".
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

### Requirement: Kept and re-placed footprints
`lens.preserve.merge_layout(built, board, match) -> Merged` SHALL keep the existing board's own footprint node for every matched part that stays where the board has it, and SHALL use the built copy otherwise.
- A matched footprint MUST be kept when its key is `uuid` or `path`, its `lib_ref` equals the built component's `lib_footprint_ref`, and the built copy has the footprint's position, rotation, side and lock.
- A kept footprint MUST keep every slot of its node: properties, texts, graphics and pads as edited in KiCad, except its user properties. Its `component_id` MUST become the built component's id, and each pad MUST take the net of the built copy's pad with the same number, or none. The component MUST take the projected `properties` of the kept node, its user properties included, so c0017's "Projected fields on write" passes, and keeps the built `ref` and `value`, which c0017's writer writes into the Reference and Value atoms.
- **User properties belong to the script** (`design-dsl`, "User properties on built footprints"). They are the `property` nodes that the built copy holds after its `fenolite.path` node. For each of them, the kept node's `property` node whose name is equal after `str.casefold()` MUST take its name and value and keep every other child, its uuid, position and visibility included. A missing one MUST be appended after the kept node's last `property` node as the built copy has it, with the uuid `embed.placement_uuid(<component path>, "/footprint/property:<name>")`, which no index-derived uuid equals. A property that the script does not name stays, because one added in KiCad cannot be told from one that the script no longer names. Without a `fenolite.path` node (`H-K-BUILD-PATHPROP` refuted), the kept node keeps its properties.
- Any other matched footprint MUST be replaced by the built copy, c0011's placed copy at the effective placement, keyed by the component path: with `layout.alias-used` (info) for an alias match, `layout.footprint-replaced` (warning) when the lib id changed, and `layout.place-forced` from "Placement precedence".
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
- **THEN** the first rebuild places `R7` where `R1` was, with uuid `footprint_uuid("R7")`, `fenolite.path` `R7` and `layout.alias-used`, and the second rebuild matches `R7` by uuid and writes the same bytes

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
`lens.preserve.merge_layout` SHALL keep every track, arc, via and zone of the existing board, with all its slots, when it has no net or its net name is a net of the built design, and SHALL drop it otherwise.
- A kept item MUST take the built design's net of the same name; its uuid and every other slot MUST stay unchanged.
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

### Requirement: Board content outside the design is kept
`lens.preserve.merge_layout` SHALL keep the existing board's layers, graphics, texts, rule areas, title block, paper and every opaque root child (setup, stack-up, groups, dimensions and the rest) unchanged, and SHALL keep its edge content in place of the design's outline.
- The layout's `Board` MUST be the existing board with its root slots, so c0017's writer re-emits read content in place.
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

### Requirement: Zone fills and the staleness digest
A rebuild SHALL keep the fills of a kept zone only when `zone_digest` of that zone and `fill_inputs_digest` of the board are both equal for the existing board and for the layout to be written; otherwise `lens.preserve.drop_stale_fills` SHALL drop that zone's fills with `zone.fill-stale` (warning).
- `zone_digest(design, zone) -> str` MUST be the SHA-256 hex digest of a canonical text of: the outline points, or, when the outline is empty, the texts of the zone's opaque `polygon` slots; the net name; the layers; the priority; and the texts of the zone's other opaque slots (its fill settings). Fills, uuids and net forms MUST NOT enter it.
- `fill_inputs_digest(design, *, project, rules) -> str` MUST be the SHA-256 hex digest of a canonical text of: every footprint's `lib_ref`, position, rotation, side and modelled pad fields; every track, arc and via's modelled fields; every zone's `zone_digest`; every rule area; every graphic on a layer of kind `edge` and the outline; the classes, patterns and assignments that c0010's `pro.read_project` gives for `project` (none when `None`); and the texts of the rule items of c0018's `parse_rules(rules)` (none when `None`). Nets MUST enter by name; ids, uuids, provenance and slots MUST NOT enter it, and each collection MUST be sorted.
- The existing board MUST be digested with the existing project and rules texts, and the layout with the texts this build writes.
- The digests are text only: `lens` never imports `geometry`.

#### Scenario: Unchanged rebuild keeps fills
- **GIVEN** a confirmed blink build whose board gets, by token edit, a zone on `GND` on `B.Cu` holding two authored `filled_polygon` lists
- **WHEN** the build runs again
- **THEN** both fills are written unchanged and `issues` holds no `zone.fill-stale`

#### Scenario: A removed part drops fills
- **GIVEN** the same filled board and `R1` removed from `design.py`
- **WHEN** the build runs again
- **THEN** the zone is kept without fills and `issues` holds `zone.fill-stale` naming it

#### Scenario: A class change drops fills
- **GIVEN** the same filled board and the clearance of class `PWR` changed from 0.2 mm to 0.3 mm in `design.py`
- **WHEN** the build runs again
- **THEN** the zone is kept without fills and `issues` holds `zone.fill-stale`

#### Scenario: Digests ignore ids and formats
- **GIVEN** the filled board of a target-9 build read with `read_board`, and the same board written by `write_board` for target 10 and read again
- **WHEN** `fill_inputs_digest` and `zone_digest` are computed for both with the same project and rules texts
- **THEN** the digests are equal

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
| `layout.orphan` | warning | a footprint with `fenolite.path` matched no part and is removed |
| `layout.alias-unused` | warning | a `moved(old, new)` alias matched nothing, or its part matched by uuid or path |
| `layout.place-forced` | warning | a locked `place()` re-placed a footprint whose board placement differed |
| `layout.footprint-replaced` | warning | the part's footprint lib id changed; the footprint is re-placed |
| `layout.net-removed` | warning | items on a net the design no longer has were dropped |
| `layout.outline-kept` | warning | the board's edge content differs from the design's outline and is kept |
| `zone.fill-stale` | warning | a zone's fills were dropped because a digest changed |
| `layout.place-overridden` | info | an unlocked `place()` differs from the kept board placement |
| `layout.alias-used` | info | a part was matched through `moved()` and re-placed under its new path |
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

