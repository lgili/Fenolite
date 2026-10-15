## ADDED Requirements

### Requirement: Net-tie groups on boards and footprints
`read_board` SHALL project the `net_tie_pad_groups` child of each footprint into `FootprintInstance.net_ties`, and `read_footprint` into `FootprintDef.net_ties` (`design-model`, "Net-tie groups in the model"):
- each string atom is one group; it is split at commas, the spaces around a number are dropped, and empty parts are dropped, so `"1, 2"` and `"1,2"` give `("1", "2")` (both spellings occur in KiCad's demo boards, S-0058);
- the child MUST stay a projected slot ("Projected fields on write"), written back byte for byte, so a read board keeps its token as KiCad wrote it;
- a read footprint whose `net_ties` differs from the projection of its child, or that gains groups without having the child, MUST give `kicad.board.projection-read-only` on write, naming `net_ties` and the footprint's locator;
- `embed.place_footprint` MUST carry the child of a library definition into the placed footprint, so a library net tie placed by `build` keeps its groups on the board;
- an authored definition is written from its field (`dsl-footprint-authoring`, "Net-tie groups in authored footprints").
`docs/formats/kicad/libraries.md` and `board.md` MUST state the form, the two spellings and the position after `attr`, with S-0018, S-0042 and S-0058.

#### Scenario: Official form read
- **GIVEN** a board holding KiCad's `NetTie-2_SMD_Pad0.5mm` placed with pads on nets `A` and `B`, its child written `(net_tie_pad_groups "1, 2")`
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_net_ties.py -k read` reads it
- **THEN** the footprint has `net_ties == (("1", "2"),)`, and `write_board` of the unchanged design gives the input bytes

#### Scenario: Spelling and several groups
- **WHEN** footprints holding `(net_tie_pad_groups "1,2")` and `(net_tie_pad_groups "1, 2" "3, 4")` are read
- **THEN** their groups are `(("1", "2"),)` and `(("1", "2"), ("3", "4"))`

#### Scenario: Edited groups refused
- **GIVEN** the board of "Official form read" with the footprint's `net_ties` changed to `(("1",),)`
- **WHEN** it is written for target 10
- **THEN** `LossyWriteError` is raised with `kicad.board.projection-read-only` naming `net_ties`

#### Scenario: Placed library net tie keeps its groups
- **GIVEN** a design whose part uses `NetTie:NetTie-2_SMD_Pad0.5mm` from the fetched library
- **WHEN** `fenolite build` plans the board and the copper guard reads it back
- **THEN** the placed footprint holds the child and `net_ties == (("1", "2"),)`

### Requirement: Project files carry the check severities
A written project file SHALL carry the severities of `RuleSet.severities` (`design-model`, "Check severities in the rules layer"): this requirement takes the keys `/board/design_settings/rule_severities/<key>` that they name out of the template-value rule and the keep rule of "Project files are synthesised and preserved".
- **Key.** The key of a code `kicad.drc.<suffix>` is the suffix with `-` replaced by `_`. `pro.SEVERITY_KEYS[target]` MUST be the set of `rule_severities` keys of the target's packaged template: exactly the keys 10.0.6 applies for target 10 (`H-K-PRO-SEV-KEYS`), and, for target 9, the keys of a template derived from 10's, `INFERRED`.
- **Write.** `synthesize_project` and `update_project` MUST set each such key to its level when the key is in `SEVERITY_KEYS[target]`. A key the design does not name keeps its template value on synthesis and its file value on update, its spelling and its position included.
- **Unknown key.** A code whose key is outside `SEVERITY_KEYS[target]` MUST raise `LossyWriteError` (`FEN-7001`, `droppable=True`) with the error `kicad.project.unknown-check` naming the code and the target; with `allow_lossy=True` the key MUST NOT be written, and `issues` MUST hold the warning `kicad.project.dropped-check` instead.
- **Codes.** This requirement adds two rows to "Project issue codes": `kicad.project.unknown-check` (error) and `kicad.project.dropped-check` (warning).
- `docs/formats/kicad/project.md` MUST state the key rule, both key sets, and the six template keys that no 9.0.9.1 demo project holds (S-0058).

#### Scenario: Synthesis writes a named key
- **GIVEN** a design with `RuleSet.severities == {"kicad.drc.silk-overlap": "ignore"}`
- **WHEN** `synthesize_project(design, target=10, board_name="b")` is called
- **THEN** `/board/design_settings/rule_severities/silk_overlap` is `"ignore"` and every other `rule_severities` value equals the template's

#### Scenario: Update changes only the named key
- **GIVEN** a target-10 project text whose `rule_severities` sets `silk_overlap` to `warning` and `track_dangling` to `ignore`
- **WHEN** `update_project` runs with `severities == {"kicad.drc.silk-overlap": "error"}`
- **THEN** `silk_overlap` is `"error"`, `track_dangling` is still `"ignore"`, and every other `rule_severities` member keeps its value and position

#### Scenario: Unknown key refused
- **GIVEN** `severities == {"kicad.drc.silk-overlaps": "ignore"}`
- **WHEN** the project is synthesised for target 10
- **THEN** `LossyWriteError` is raised with `droppable == True` and the error `kicad.project.unknown-check`; with `allow_lossy=True` no `silk_overlaps` key is written and `issues` holds `kicad.project.dropped-check`

### Requirement: Stored exclusions are read
`read_project` SHALL also return `ProjectInfo.exclusions: tuple[StoredExclusion, ...]` (`backend-protocol`, "Stored exclusions source"), read from `/board/design_settings/drc_exclusions` in file order. An entry MUST be either a string `key` (the plain form, comment `""`) or a list `[key, comment]` of two strings (the pair form), the key being `<type>|<x>|<y>|<uuid>|<uuid>` with `x` and `y` integers in nm (S-0058, `H-K-DRC-EXCL`). An entry of any other shape MUST give the info `kicad.project.unread-entry` and be skipped. `KicadBackend.stored_exclusions(project)` MUST return the exclusions of the project file of the copy set, and `()` when the set has none or it fails to read. Neither writes the project file; `update_project` keeps `drc_exclusions` verbatim, as before.

#### Scenario: Both forms read
- **GIVEN** a project text whose `drc_exclusions` holds `["via_dangling|30123456|20654321|<uuid>|00000000-0000-0000-0000-000000000000", "test point"]` and the plain string `"courtyards_overlap|1000000|2000000|<uuid a>|<uuid b>"`
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_pro_read.py -k exclusion` reads it
- **THEN** `exclusions` holds two entries, the first with position `Point(30_123_456, 20_654_321)` and comment `test point`, the second with comment `""`

#### Scenario: A malformed entry is skipped
- **GIVEN** a `drc_exclusions` entry `["via_dangling|1.5|2|<uuid>", 3]`
- **WHEN** the project is read with an `issues` list
- **THEN** `exclusions` is empty and `issues` holds one `kicad.project.unread-entry`
