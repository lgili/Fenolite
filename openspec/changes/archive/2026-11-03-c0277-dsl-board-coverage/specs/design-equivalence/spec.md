## MODIFIED Requirements

### Requirement: Level 1 compares components
Level 1 SHALL compare the components of `Design.circuit.components` by their `ref`.
- A reference matching one of the `ignore_refs` globs (`fnmatch.fnmatchcase`) MUST be left out on both sides and counted in the summary as `ignored`.
- **Shared references** (change c0277). Before level 1, `compare_designs` SHALL pair a reference that both sides hold equally often, more than once or empty, when it matches no `ignore_refs` glob and each of its holders has exactly one footprint on its side: the holders of each side, in placement order (side, x, y, rotation, footprint name), MUST take the references `REF#1`, `REF#2`, … for every level, unless one of those names is already a reference of either side.
- An empty reference, and a reference that a side holds more than once, that is not paired MUST give one `ref-ambiguous` difference per reference, with the two counts as `a` and `b`.
- A reference held by one side only MUST give `component-missing`, with the other side's value empty.
- For each reference both sides hold once, `value` and `dnp` MUST be compared.
- `LevelResult.compared` MUST be the count of references both sides hold once.

#### Scenario: Missing and changed components
- **GIVEN** side `a` with `R1` (`10k`), `R2` (`1k`) and `C1`, and side `b` with `R1` (`10k`), `R2` (`2k2`) and `D1`
- **WHEN** level 1 runs
- **THEN** it reports `component-missing` for `C1` and for `D1`, and `value` for `R2` with `a` `1k` and `b` `2k2`, and `compared` is 2

#### Scenario: Duplicate references are not compared
- **GIVEN** side `a` holding the reference `REF**` twice and side `b` holding it once
- **WHEN** levels 1 to 4 run, and then again with `ignore_refs=("REF[*][*]",)`
- **THEN** the first run reports exactly one difference for `REF**`, of kind `ref-ambiguous`, and the second reports none and counts `ignored`

#### Scenario: Shared references are paired by placement
- **GIVEN** two sides that each hold `STITCH1` twice, placed at x 0 and 1 mm, and `R1`, the second `STITCH1` of side `b` with the value `x`
- **WHEN** levels 1 to 4 run
- **THEN** `compared` is 3 at level 1 and the only difference is `value` at `STITCH1#2`; with both values empty the sides are equivalent, and the same holds for an empty reference
