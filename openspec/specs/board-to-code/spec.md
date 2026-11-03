# board-to-code Specification

## Purpose
TBD - created by archiving change c0345-custom-footprint-field-poses. Update Purpose after archive.
## Requirements
### Requirement: Explicitly preserve custom footprint property presentation
Board import SHALL preserve representable custom property poses using typed
field requests for properties declared by that part. Unsupported source poses
SHALL refuse before staging rather than silently lowering presentation.

#### Scenario: A rotated footprint has a hidden custom property
- **WHEN** a source footprint has a custom property whose board angle differs from its body angle
- **THEN** import and fresh build retain its complete typed field pose and value
- **AND** strict geometry and rendering comparisons remain active

#### Scenario: A property pose is not representable by the public API
- **WHEN** a custom property has unsupported size, layer or an inexact board-frame anchor
- **THEN** import refuses with a located error before planning writes

#### Scenario: Unknown field name
- **WHEN** a script requests placement of a field that is neither conventional nor a declared user property
- **THEN** the DSL rejects that request

### Requirement: Current import coverage observations
Current corpus coverage expectations SHALL be measured from the same reader and complete emission ledger as `fenolite import`, with date, input SHA-256 and measurement SHA-256. They MUST be separate from historical conversion proofs. The helper MUST match full CLI results on authored and public inputs. Full corpus imports MUST still independently require exit 0 and equivalent=true, including heavy rows.

#### Scenario: DSL coverage changes
- **WHEN** the emitter gains support for a formerly unexpressed item
- **THEN** current observations change through measurement while historical equivalence and elapsed-time records remain intact

### Requirement: Teardrops in an import
`fenolite import --to python` SHALL read a via's opaque `teardrops` child and write it as `teardrop=teardrop(...)` on its via table, grouping vias by settings too. Unreadable settings MUST be counted as `teardrop-setting`, and that via MUST be written without settings.

#### Scenario: Settings kept and zones regenerated
- **GIVEN** the authored two-sheet board with the demo teardrop settings on its via at (110, 133) and one `padvia` teardrop zone (`tests/_importcode.py::teardropped`)
- **WHEN** it is imported with `--confirm` and the code is built
- **THEN** `copper.py` holds `teardrop=teardrop(` in the table of that via, `issues` hold `import.teardrops-regenerated`, `result.unexpressed` holds no teardrop kind, and the built via holds a `teardrops` child of nine children

#### Scenario: Settings lost
- **GIVEN** the same board whose via holds `(teardrops (enabled maybe))`
- **WHEN** it is imported with `--allow-lossy --dry-run`
- **THEN** `result.unexpressed` holds `teardrop` (1) and `teardrop-setting` (1), and no `import.teardrops-regenerated`

### Requirement: Blind vias over the board in an import
A blind via whose two layers are the outer copper layers SHALL be written as a row of a via table with `kind="blind"` and those layers ("Blind vias over the board in via tables"), not left out as `via-span`.

#### Scenario: Demo vias kept
- **GIVEN** the two-sheet board whose via at (130, 133) is `(via blind … (layers "F.Cu" "B.Cu"))`
- **WHEN** it is imported and built
- **THEN** the table `GND/via/1` holds that row with `kind="blind"`, `result.unexpressed` holds no `via-span`, and the built via is blind on both layers

### Requirement: Parts not populated and net ties in an import
The import SHALL write a part whose component is not populated as `Part(..., dnp=True)`, and MUST NOT count it as unexpressed. A footprint's net-tie pad groups SHALL come back with its vendored footprint and MUST NOT be counted as unexpressed.

#### Scenario: One part not populated, one net tie
- **GIVEN** the two-sheet board with R101's attribute `(attr smd dnp)` and R201 holding `(net_tie_pad_groups "1, 2")` (`tests/_importcode.py::unfitted`)
- **WHEN** it is imported with `--confirm` and the code is built
- **THEN** `result.unexpressed` is empty, `design.py` holds one `dnp=True`, and the built board holds `(attr smd dnp)` for R101 and the net-tie groups for R201

### Requirement: Groups in an import
The import SHALL write a group of the board whose members it all writes (parts, drawings, zones, rule areas and groups) as `design.group()` after the drawings, an inner group before the group that holds it, with the source name as name and key when the key pattern takes it and `key="group/<n>"` otherwise, and `locked=True` for a locked group. A group holding an item the code does not write MUST be the unexpressed kind `group`.

#### Scenario: Nested groups
- **GIVEN** the `drawn` board with a locked group `logo` of J1, a text and a dimension, an unnamed group of `logo` and a text, and a group `lost` of the hidden text (`tests/_importcode.py::drawn_grouped`)
- **WHEN** it is imported with `--allow-lossy --confirm` and built
- **THEN** `result.unexpressed` holds `group` (`lost`), `design.py` holds two `design.group()` calls, and the built board holds `logo`, locked, with the uuids of J1's footprint, the text and the dimension, and the unnamed group with the uuids of `logo` and the text

### Requirement: Board-only parts in an import
The import SHALL write footprints with shared or unnameable references (including empty and `REF**`), and footprints already marked board-only, as `Part(ref, ..., name=key, board_only=True)`. Their key MUST be the reference cut to the path alphabet (`fp` when empty), then the lowest unused `_<n>`, assigned in placement order. They MUST NOT be unexpressed or gain a lock entry.

#### Scenario: Two footprints of one reference and a REF**
- **GIVEN** the two-sheet board with R201 renamed R101 and J1 renamed `REF**` (`tests/_importcode.py::shared`)
- **WHEN** it is imported with `--confirm` and built
- **THEN** `result.unexpressed` is empty, `import.board-only` names 3 footprints of which 3 gain the attribute, `design.py` holds three `board_only=True`, and the built board holds two footprints `R101` and one `REF**`, each with `board_only`

### Requirement: Board items in an import
The import SHALL keep user layers through the highest `User.<n>` and their names; copper-graphic nets (resolving target-9 numbers); filled strokes of -1 nm as `width=None`; free vias grouped by `free`; zone smoothing and radius; mils/automatic dimension units; and silkscreen material. A dashed copper graphic or one naming an undeclared net MUST be unexpressed as `drawing`.

#### Scenario: Items of change c0277
- **GIVEN** the two-sheet board with user layers `User.1` and `User.2` (`notes`), a copper rectangle of `GND`, a filled polygon of stroke −1 nm, a text on `User.2`, a dimension in automatic units, its via at (110, 133) free and its GND zone smoothed with fillets of 0.5 mm (`tests/_importcode.py::itemized`)
- **WHEN** it is imported with `--confirm` and built
- **THEN** `result.unexpressed` is empty, the code holds each call, and the built board holds the user layers, `(net "GND")` on the rectangle, `(width -0.000001)`, `(units 3)` and one free via at (110, 133)

### Requirement: Verbatim items in an import
The import SHALL write permitted opaque root items with no DSL call as `design.verbatim("<head>/<n>", text)`, keyed in file order. Numeric nets MUST resolve through the source table and copper `members` UUIDs through their emitted table rows. A reference to omitted copper or an unknown net MUST be unexpressed by its head. Groups MAY name verbatim items by key.

#### Scenario: A tuning pattern in a group
- **GIVEN** the two-sheet board with a `generated` tuning pattern over its first track, a group `tuned` holding it, and a placement area of `/CH1/` (`tests/_importcode.py::tuned`)
- **WHEN** it is imported with `--confirm` and built
- **THEN** `result.unexpressed` is empty, `design.py` holds `design.verbatim("generated/1", …)`, `design.group("tuned", "generated/1")` and `placement="/CH1/"`, and the built board's `generated` names a track of the board in `members`, inside the group `tuned`

### Requirement: Zone arcs in an import
The import SHALL write a zone outline that the reader keeps in the zone's slots because it holds an arc — one `polygon` of `xy` and `arc` items — as `outline=` with `arc_to` steps (change c0277); another kept outline (several polygons, an unknown item) MUST stay `zone-outline`.

#### Scenario: A rounded pour
- **GIVEN** the two-sheet board whose GND zone has an arc edge through (157, 120) (`tests/_importcode.py::rounded`)
- **WHEN** it is imported with `--confirm` and built
- **THEN** `result.unexpressed` is empty, `design.py` holds `arc_to((mm("57"), mm("20")), (mm("55"), mm("28")))`, and the built zone's `pts` hold `(arc (start 155 112) (mid 157 120) (end 155 128))`

### Requirement: Outlines closed by a footprint in an import
When the root edge graphics of a source board do not close an outline and the `Edge.Cuts` of its footprints close it (change c0277), the import SHALL declare the closed outline, and the KiCad writer SHALL NOT write an edge of a created outline that the `Edge.Cuts` of a footprint of the board draws, in either direction.

#### Scenario: A notch drawn by a footprint
- **GIVEN** the two-sheet board whose left edge is an `Edge.Cuts` line of D101 instead of a root line (`tests/_importcode.py::notched`)
- **WHEN** it is imported with `--confirm` and built
- **THEN** `result.unexpressed` is empty, `design.py` holds `design.board(mm("60"), mm("40"))`, and the built board holds three root `Edge.Cuts` lines, none from (100, 140)

### Requirement: Texts and dimensions in an import
The import SHALL write supported board texts, including copper, with their preserved `knockout`, `bold`, `italic`, `face`, paired size, multiline and empty text. Hidden texts and mirrors inconsistent with the layer side MUST be unexpressed as `text`. Supported dimensions MUST preserve every representable field; unsupported styles MUST be reported without silent loss.

#### Scenario: Styled texts and an older dimension
- **GIVEN** the two-sheet board with a knocked-out bold text of size 2 × 1.25 mm, a text of two lines, an empty text, a copper text, a text with a face and italic, a hidden text, an aligned dimension with extension offset 0 and one with a prefix (`tests/_importcode.py::drawn`)
- **WHEN** it is imported with `--allow-lossy --confirm` and built
- **THEN** `result.unexpressed` is `text` (1, the hidden one) and `dimension-style` (1), `design.py` holds the five texts and `extension_offset=mm("0")`, and the built board holds `(layer "F.SilkS" knockout)` and `(font (size 2 1.25) (thickness 0.275) (bold yes))`

### Requirement: Regenerated teardrops in an import
Only `padvia` teardrop zones whose settings survive SHALL be omitted as regenerated, reported once by `import.teardrops-regenerated` (info). Pad settings remain in vendored footprints. Other teardrop types, unreadable via settings, or omitted vias/footprints holding settings MUST make every affected zone unexpressed as `teardrop`.

#### Scenario: Lost settings prevent regeneration
- **GIVEN** a source with padvia zones and a via whose settings are unreadable
- **WHEN** it is imported with loss allowed
- **THEN** `teardrop` and `teardrop-setting` are reported, with no regeneration finding

### Requirement: Board-only import accounting
The import SHALL report board-only footprints once as `import.board-only` (info), including how many gain the native attribute. Its self-check MUST pair their shared references by placement as Level 1 specifies.

#### Scenario: Already marked footprint
- **GIVEN** an already-board-only source footprint
- **WHEN** it is imported
- **THEN** it stays board-only, counts in the finding, and does not count as gaining the attribute

### Requirement: Imported placement areas and pad geometry
The import SHALL keep placement areas as `placement=` and preserve bottom-footprint chamfers and pads of one number assigned to distinct unconnected nets. A disabled placement without a sheet SHALL mean no placement; another unsupported placement MUST be `rule-area-placement`.

#### Scenario: Supported native placements
- **GIVEN** the authored tuned board and its `/CH1/` placement area
- **WHEN** it is imported and rebuilt
- **THEN** the placement sheet name and supported pad geometry survive

### Requirement: Imported dimension style coverage
Aligned and orthogonal dimensions SHALL use `design.dimension()` when their format/style matches a created dimension, preserving line width and `extension_offset`. Another format/style MUST be `dimension-style`; an unrepresented dimension kind MUST be `dimension`. Other supported kinds SHALL use their corresponding DSL calls.

#### Scenario: Prefix cannot be represented
- **GIVEN** an aligned dimension with a prefix
- **WHEN** it is imported
- **THEN** `dimension-style` reports the unsupported prefix rather than silently dropping it
