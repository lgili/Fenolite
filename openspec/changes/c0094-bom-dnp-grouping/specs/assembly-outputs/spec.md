## MODIFIED Requirements

### Requirement: Neutral BOM parts and lines
`fenolite.exports.bom` SHALL define `BomPart(ref, value, footprint, description, datasheet, dnp, properties)`, `BomLine(refs, quantity, fields, key)`, `parts_from_model(design) -> tuple[BomPart, ...]` and `group(parts, template) -> tuple[BomLine, ...]`, where `template` is the `[bom]` table of an assembly template and `key` holds the line's values of the `group_by` fields (its reference when `group_by` is empty), with `DNP` after them for a line of DNP parts as said below.
- `parts_from_model` MUST give one part per component that has a placed footprint, leaving out a component whose footprint has the attribute `board_only` or `exclude_from_bom` and a reference that starts with `#`. `footprint` MUST be `Component.lib_footprint_ref`; `dnp` MUST be true when `Component.dnp` is true or the footprint has the attribute `dnp`; `properties` MUST be the component's properties without `Reference`, `Value`, `Footprint`, `Datasheet` and `Description`; `description` and `datasheet` MUST be those two properties, or `""`.
- Parts MUST be sorted by the natural order of the reference (`R2` before `R10`).
- `group` MUST first leave out DNP parts when the template's `exclude_dnp` is true, then put into one line the parts whose values are equal for every field of `group_by` and whose `dnp` flags are equal, with `refs` in natural order and `quantity` their count. Lines MUST be sorted by the natural order of their first reference. An empty `group_by` MUST give one line per part.
- A DNP part MUST NOT share a line with a part that is not DNP, whether or not `group_by` names `dnp`: every line is all DNP or all fitted. A line of DNP parts has no place of its own in the order: it stands where its first reference puts it.
- When `group_by` is not empty and does not name `dnp`, the `key` of a line of DNP parts MUST be its values of the `group_by` fields followed by `DNP`, so that no two lines of one bill have one key. Every other `key` MUST hold the values of the `group_by` fields and nothing else.
- The value of a field for a line MUST be: `refs` joined with `ref_separator`; `quantity`; `item`, the line's number from 1; and for every other field the value its parts share, or the values of its parts in reference order, without repeats, joined with `ref_separator` when they differ.
- The functions MUST NOT read a file or run a tool, and MUST use no float.

#### Scenario: Grouping by value and footprint
- **GIVEN** the parts `R1` and `R2` with value `10k` and footprint `Mini:Mini_R_0603`, `R10` with value `330` and the same footprint, and `D1`
- **WHEN** `group` runs with `group_by = ("value", "footprint")`
- **THEN** it returns three lines whose `refs` are (`D1`), (`R1`, `R2`) and (`R10`), in this order, with quantities 1, 2 and 1

#### Scenario: A property splits a group
- **GIVEN** the same parts, where `R1` has the property `Bin` `A` and `R2` has `B`
- **WHEN** `group` runs with `group_by = ("value", "footprint", "property:Bin")`
- **THEN** `R1` and `R2` are on two lines

#### Scenario: DNP parts
- **GIVEN** a model whose `R2` has `dnp == True`
- **WHEN** `group` runs with `exclude_dnp` true, and again with false
- **THEN** the first result does not list `R2`, and in the second the line of `R2` has the `dnp` field `DNP`

#### Scenario: DNP parts never share a line with fitted parts
- **GIVEN** the parts `R1`, `R2`, `R3` and `R4` with value `10k` and footprint `Mini:Mini_R_0603`, of which `R2` and `R4` are DNP, and a DNP part `D1`, once as `parts_from_model` gives them and once as `parts_from_kicad` gives them
- **WHEN** `group` runs with `group_by = ("value", "footprint")` and `exclude_dnp` false, and again with `exclude_dnp` true
- **THEN** the first result has three lines whose `refs` are (`D1`), (`R1`, `R3`) and (`R2`, `R4`), in this order, with quantities 1, 2 and 2, the `dnp` fields `DNP`, an empty text and `DNP`, and the keys (`LED`, the footprint, `DNP`), (`10k`, the footprint) and (`10k`, the footprint, `DNP`); the second result has the one line (`R1`, `R3`) with quantity 2

#### Scenario: Parts that are not on the bill
- **GIVEN** a model with a footprint `H1` that has `board_only`, and a component `R3` whose footprint has `exclude_from_bom`
- **WHEN** `parts_from_model` runs
- **THEN** neither `H1` nor `R3` is a part

### Requirement: BOM difference
`bom.difference(a, b) -> tuple[BomChange, ...]` SHALL compare two tuples of lines grouped under one template, matching lines by their `key` (the values of their `group_by` fields, and `DNP` after them for a line of DNP parts as "Neutral BOM parts and lines" says), and SHALL return `BomChange(key, change, a_refs, b_refs)` sorted by key: `added` for a key only in `b`, `removed` for a key only in `a`, and `changed` when the references differ. Equal BOMs MUST give `()`.

#### Scenario: One part more
- **GIVEN** two BOMs equal except that the second has one more `10k` resistor `R3`
- **WHEN** `difference` runs
- **THEN** it returns one `changed` entry whose `a_refs` are (`R1`, `R2`) and whose `b_refs` are (`R1`, `R2`, `R3`)

#### Scenario: A value changed
- **GIVEN** two BOMs in which `R10` goes from `330` to `470`
- **WHEN** `difference` runs
- **THEN** it returns one `removed` entry for the `330` line and one `added` entry for the `470` line

#### Scenario: A DNP part becomes fitted
- **GIVEN** two BOMs grouped with `exclude_dnp` false and without `dnp` in `group_by`, in which the `10k` resistor `R2` is DNP in the first and fitted in the second
- **WHEN** `difference` runs
- **THEN** it returns two `changed` entries, one for the key of the fitted `10k` line, which gains `R2`, and one for the key of the DNP `10k` line, which loses it
