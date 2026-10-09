## ADDED Requirements

### Requirement: Unnumbered hole pads in authored footprints
`Footprint.pad(number, …)` SHALL accept the empty number `""` for a pad of kind `np_thru_hole`, the form of a mounting hole in KiCad's own library (`H-K-HOLE-FOOTPRINT`), and SHALL refuse it, with `DslError`, for every other kind.
- One footprint MAY hold several unnumbered pads without `shared=True`. The k-th, counted from 1 in declaration order, MUST have the id `derived_id("pad", "fenolite.dsl", "<lib id>:pad::<k>")`, so the ids of numbered pads do not change.
- An unnumbered pad maps to no pin: the build MUST NOT give `build.pad-without-pin` for it, and a `pad_map` that names `""` MUST raise `DslError`.
- The written footprint MUST hold `(pad "" np_thru_hole …)`; the pad's default layers stay `*.Cu` and `*.Mask`, and the drill rules of the other through-hole pads apply.

#### Scenario: Two unnumbered holes
- **GIVEN** `fp = Footprint("Proj", "Two_Holes")` and two calls `fp.pad("", at=(mm(0), mm(0)), size=(mm(3.2), mm(3.2)), shape="circle", kind="np_thru_hole", drill=mm(3.2))` and `fp.pad("", at=(mm(10), mm(0)), size=(mm(2), mm(2)), shape="circle", kind="np_thru_hole", drill=mm(2))`
- **WHEN** `fp.definition` is read and its `.kicad_mod` is written
- **THEN** its two pads have the ids `derived_id("pad", "fenolite.dsl", "Proj:Two_Holes:pad::1")` and `…:pad::2`, and the text holds `(pad "" np_thru_hole circle` twice

#### Scenario: Empty number refused for other kinds
- **WHEN** `fp.pad("", at=(mm(0), mm(0)), size=(mm(2), mm(2)), shape="circle", kind="thru_hole", drill=mm(1))` and `fp.pad("", at=(mm(0), mm(0)), size=(mm(1), mm(1)))` are called
- **THEN** each raises `DslError` naming the pad number

#### Scenario: No pin for an unnumbered hole
- **GIVEN** a part whose authored footprint holds two numbered pads, both connected, and one unnumbered hole
- **WHEN** it is built with `--dry-run --json`
- **THEN** the exit code is 0 and `issues` holds no `build.pad-without-pin`
