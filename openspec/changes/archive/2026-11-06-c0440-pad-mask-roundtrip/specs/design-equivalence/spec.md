## MODIFIED Requirements

### Requirement: Differences are located
Every difference SHALL be a `Difference(level, kind, where, field, a, b)`, whose `level` is an `int` of 1 to 8 or the text `S`.
- `where` MUST be the component reference `REF` at levels 1 and 4 and for footprint kinds, and `REF-PIN` (the reference, `-`, the pin or pad number) for pin and pad kinds. A pad without a number MUST give `REF-` followed by `@<x>,<y>`, its footprint-local position in nanometres. At level 5 `where` MUST be the net's name on side `a`, followed, for a kind that concerns one pad set, by `:` and the first three pads of the set joined by `,` (then `,+<n>` for the `n` pads left out).
- At the strict kinds of level 5 and at levels 6 to 8 and S, `where` MUST be the form that "Level 5 strict compares copper items", "Level 6 compares rules", "Level 7 compares exact geometry", "Level 8 compares rendered presentation" and "Level S compares drawn schematics" give.
- `a` and `b` MUST be the two values as strings: text verbatim, lengths as decimal integers of nanometres, points as `<x>,<y>`, sizes as `<w>x<h>`, angles as decimal integers of microdegrees, a missing object as the empty string.
- The kinds and their levels MUST be exactly those of this table.

| level | kind | field | meaning |
|---|---|---|---|
| 1 | `component-missing` | `ref` | a reference that only one side holds |
| 1 | `ref-ambiguous` | `ref` | a reference that a side holds more than once, or an empty reference |
| 1 | `value` | `value` | `Component.value` differs |
| 1 | `dnp` | `dnp` | `Component.dnp` differs |
| 2 | `pin-missing` | `pin` | a `REF-PIN` of a common component that only one side holds |
| 2 | `net` | `net` | a `REF-PIN` whose net block differs |
| 3 | `footprint-missing` | `footprint` | a common component that is placed on one side only |
| 3 | `footprint-name` | `lib_ref` | the footprint names differ |
| 3 | `pad-missing` | `pad` | the two footprints hold different counts of pads of one number |
| 3 | `pad-kind` | `kind` | `Pad.kind` differs |
| 3 | `pad-shape` | `shape` | `Pad.shape` differs |
| 3 | `pad-size` | `size` | the sizes differ beyond the tolerance |
| 3 | `pad-drill` | `drill` | the drills differ beyond the tolerance, or only one pad has a drill |
| 3 | `pad-position` | `position` | the footprint-local positions differ beyond the tolerance |
| 3 | `pad-rotation` | `rotation` | the footprint-relative rotations differ beyond the tolerance |
| 3 | `pad-copper` | `layers` | the copper spans differ |
| 3 | `pad-mask` | `mask_margin` | the solder-mask expansions differ beyond the tolerance (change c0440) |
| 4 | `side` | `side` | `FootprintInstance.side` differs |
| 4 | `position` | `position` | the positions differ beyond the tolerance, in the chosen frame |
| 4 | `rotation` | `rotation` | the rotations differ beyond the tolerance |
| 5 | `route-missing` | `copper` | one side has copper on the net and the other has none |
| 5 | `route-connectivity` | `pads` | the copper of the net joins other pad sets |
| 5 | `route-vias` | `vias` | the via counts per pair of copper spans differ for one pad set |
| 5 | `route-length` | `length` | a routed length per copper span differs beyond the tolerance for one pad set |
| 5 | `route-stub` | `stubs` | the pieces without a pad differ in number or in total length (a notice) |
| 5 | `route-unjudged` | `zones` | the net's connectivity depends on an unfilled zone (a notice) |
| 5 | `track-missing` | `track` | strict: a track that only one side holds |
| 5 | `track-width` | `width` | strict: matched tracks of different widths |
| 5 | `track-net` | `net` | strict: matched tracks on nets of different names |
| 5 | `arc-missing` | `arc` | strict: an arc that only one side holds |
| 5 | `arc-width` | `width` | strict: matched arcs of different widths |
| 5 | `arc-net` | `net` | strict: matched arcs on nets of different names |
| 5 | `via-missing` | `via` | strict: a via that only one side holds |
| 5 | `via-size` | `diameter` | strict: matched vias of different diameters |
| 5 | `via-drill` | `drill` | strict: matched vias of different drills |
| 5 | `via-span` | `layers` | strict: matched vias of different copper spans or types |
| 5 | `via-net` | `net` | strict: matched vias on nets of different names |
| 5 | `copper-locked` | `locked` | strict: matched items whose lock differs (a notice) |
| 6 | `netclass-missing` | `name` | a net class that only one side holds |
| 6 | `netclass-field` | the field | a field of a net class differs |
| 6 | `netclass-members` | `nets` | the nets assigned to a net class differ |
| 6 | `rule-missing` | `name` | a custom rule that only one side holds |
| 6 | `rule-field` | the field | a field of a custom rule differs |
| 6 | `ruleset-field` | the field | a board-wide rule or minimum differs |
| 6 | `stackup-missing` | `layer` | a stack-up layer that only one side holds, or out of order |
| 6 | `stackup-field` | the field | a field of a stack-up layer, or the finish, differs |
| 6 | `layer-missing` | `layer` | a board layer of one kind and ordinal that only one side holds |
| 7 | `outline-missing` | `ring` | an outline ring, cut-out or slot that only one side holds |
| 7 | `zone-missing` | `zone` | a zone outline that only one side holds |
| 7 | `zone-field` | the field | a field of matched zones differs (never the fill) |
| 7 | `keepout-missing` | `keepout` | a rule area that only one side holds |
| 7 | `keepout-field` | the field | a field of matched rule areas differs |
| 7 | `graphic-missing` | `graphic` | a board or footprint graphic that only one side holds |
| 7 | `text-missing` | `text` | a board or footprint text that only one side holds |
| 7 | `text-field` | the field | a field of matched texts differs |
| 7 | `field-pose` | the field | a field of a footprint field (reference, value, user field) differs |
| 7 | `hole-missing` | `hole` | a board hole that only one side holds |
| 7 | `dimension-missing` | `dimension` | a dimension that only one side holds |
| 8 | `render-missing` | `layer` | a layer or sheet that only one side renders |
| 8 | `render-pixels` | `pixels` | a layer or sheet whose rendered masks differ beyond the pixel tolerance |
| S | `sheet-missing` | `sheet` | a sheet instance that only one side holds |
| S | `symbol-missing` | `symbol` | a symbol unit that only one side draws |
| S | `symbol-pose` | the field | the position, rotation or mirror of a matched symbol differs |
| S | `symbol-field` | the field | the pose of a field of a matched symbol differs |
| S | `item-missing` | the item kind | a wire, bus, bus entry, junction, no-connect flag, label, power symbol, sheet reference, sheet pin or opaque item that only one side holds |
| S | `item-field` | the field | a field of a matched label, sheet reference or sheet pin differs |
| S | `drawn-net` | `net` | the drawn connectivity differs (a `REF-PIN` in another group) |

- The differences of a level MUST be sorted by `(where, kind, field)` in code-point order, so that equal inputs give equal output.
- A component reported as `component-missing` or `ref-ambiguous` MUST NOT be compared at any level, and a component reported as `footprint-missing` MUST NOT be compared further at levels 3 and 4: each fault is reported once.
- `difference_issues(report)` MUST return one `Issue` of severity `error` per difference that no rule excludes, with `where` as above. Its code MUST be `netlist.assignment-differs` for kind `net` (c0020's code, built with `checks.codes.issue`) and `equiv.<kind>` for every other kind. It MUST then return one `Issue` per notice of a level (`LevelResult.notices`) that no rule excludes, of code `equiv.<kind>` and of severity `warning` for `route-stub` and `copper-locked` and `info` for `route-unjudged`; a notice is located as a difference is and never makes `EquivalenceReport.equivalent` false. `EQUIVALENCE_CODES` (also named `ISSUE_CODES` in `codes.py`, the name by which `fenolite explain` finds issue-code tables) MUST map each `equiv.*` code this capability emits to its severities, including `equiv.excluded` (info), `equiv.import-message` (info), `equiv.no-exclusion-profile` (warning) and `equiv.oracle-failed` (error).

#### Scenario: Kinds table is closed
- **WHEN** `uv run pytest tests/unit/checks/equivalence/test_codes.py` runs
- **THEN** the kinds of `levels.py` equal the table above, each `equiv.*` code matches `fenolite.core.errors.ISSUE_CODE`, and `docs/equivalence.md` lists the same kinds

#### Scenario: Output order is stable
- **GIVEN** two designs with differences on `R2`, `R10` and `C1`
- **WHEN** `compare_designs` runs twice, the second time with the footprints of both designs in reverse order
- **THEN** both reports are equal, and the level-1 differences come in the order `C1`, `R10`, `R2`

#### Scenario: Pad mask expansion
- **GIVEN** the pads of the KiCad board above written to Altium with their own margins, and the original `blink.PcbDoc`, whose pads follow the rules of a document without a `SolderMaskExpansion` rule
- **WHEN** `uv run pytest tests/unit/convert/test_pad_mask_c0440.py` runs level 3 of `equivalent`
- **THEN** the written document and the KiCad board give no `pad-mask` difference, and the original and the written document give one per pad, with `a` = `rules`: a pad's expansion is its own margin, else its Altium manual value (`none` for mode 0), else the expansion of its side's first enabled `SolderMaskExpansion` rule of scope `All`; a KiCad pad without a margin follows the board's setting, which agrees with any value
