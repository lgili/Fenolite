# Design equivalence

`fenolite equivalent A [B]` says whether two designs are the same design, level by level, and locates
every difference at a component (`REF`) or at a pin or pad (`REF-PIN`). The two sides may come from
different file formats: each is read into the design model (`docs/design-model.md`) and the models are
compared. The command, its options, its result keys and its exit codes are in `docs/cli-contract.md`,
"equivalent"; this page defines what is compared.

`fenolite diff` is a different tool: it lists every exact difference between two models of one family and
gives no verdict. `equivalent` removes what cannot be the same across formats (ids, net names, library
nicknames, one translation on request) and answers per level.

The comparison is the package `fenolite.checks.equivalence`. It is pure: `compare_designs(a, b, level=…)`
reads no file, runs no tool and uses no floating-point number.

## Levels

Levels are cumulative: `--level N` runs the levels 1 to `N`. The default is the highest level both sides
hold: 4 when both have at least one footprint, else 2 (a schematic has no footprint).

| level | name | compares |
|---|---|---|
| 1 | `components` | the components by reference: which exist, their value, their do-not-populate flag |
| 2 | `netlist` | the net of every `REF-PIN`, as a partition of the elements into nets |
| 3 | `footprints` | per component, the footprint name and every pad, in the footprint's own frame |
| 4 | `placement` | per footprint, the side, the position and the rotation |

Levels 5 to 8 of the roadmap (routing, rules, geometry, presentation) are not built.

- **Components are paired by reference.** Model ids differ between backends. A reference that a side
  holds more than once, or an empty reference, cannot be paired: it gives one `ref-ambiguous` difference
  and takes no further part. `--ignore-ref GLOB` leaves such references out.
- **Each fault is reported once.** A component reported as missing or ambiguous at level 1 is not
  compared at the later levels, and a component placed on one side only is reported at level 3 and not at
  level 4.
- **Level 2 never compares net names.** It is the partition comparison of `fenolite check`'s assignment
  stage (`fenolite.checks.assignment_compare.compare`): two sides agree when the same pins are together.
  A renamed net is counted in `summary.renamed` and is no difference. Pads on no net form one class. A
  side with footprints gives the pads of its board; a side without gives the pins of its circuit.
  `summary.sources` says which. A pad without a number is not an element; `summary.unnumbered` counts
  them.
- **Level 3 does not see placement.** `Pad.position` and `Pad.rotation` are relative to the footprint, so
  a moved, turned or flipped footprint with unchanged pads is equal at level 3. Pads are paired by
  number; several pads of one number are sorted by `(x, y)` and paired in that order. Per-layer pad
  stacks, mask and paste, custom outlines, graphics, attributes and 3D models are not compared.

## Kinds of difference

A difference is `{level, kind, where, field, a, b}`. `a` and `b` are the two values as exact strings: text
verbatim, a length as an integer of nanometres, a point as `x,y`, a size as `wxh`, an angle as an integer
of microdegrees, and the empty string for a missing object. `where` is `REF`, or `REF-PIN` for pin and pad
kinds; a pad without a number is `REF-@x,y`, its position in the footprint. The differences of a level
are sorted by `where`, then kind.

| level | kind | field | meaning |
|---|---|---|---|
| 1 | `component-missing` | `ref` | a reference that only one side holds |
| 1 | `ref-ambiguous` | `ref` | a reference that a side holds more than once, or an empty reference; `a` and `b` are the two counts |
| 1 | `value` | `value` | the values differ |
| 1 | `dnp` | `dnp` | the do-not-populate flags differ |
| 2 | `pin-missing` | `pin` | a `REF-PIN` of a common component that only one side holds |
| 2 | `net` | `net` | a `REF-PIN` whose net block differs; `a` and `b` are the net names |
| 3 | `footprint-missing` | `footprint` | a common component that is placed on one side only |
| 3 | `footprint-name` | `lib_ref` | the footprint names differ |
| 3 | `pad-missing` | `pad` | the two footprints hold different counts of pads of one number; `a` and `b` are the counts |
| 3 | `pad-kind` | `kind` | surface-mount, through-hole, unplated hole or connector |
| 3 | `pad-shape` | `shape` | the shapes differ |
| 3 | `pad-size` | `size` | the sizes differ beyond the tolerance |
| 3 | `pad-drill` | `drill` | the drills differ beyond the tolerance, or only one pad has a drill |
| 3 | `pad-position` | `position` | the positions in the footprint differ beyond the tolerance |
| 3 | `pad-rotation` | `rotation` | the rotations relative to the footprint differ beyond the tolerance |
| 3 | `pad-copper` | `layers` | the copper spans differ |
| 4 | `side` | `side` | top on one side of the comparison, bottom on the other |
| 4 | `position` | `position` | the positions differ beyond the tolerance, in the chosen frame |
| 4 | `rotation` | `rotation` | the rotations differ beyond the tolerance |

The issue code of a difference is `equiv.<kind>`, except `net`, which carries
`netlist.assignment-differs`, the code of the assignment comparison.

## Tolerances and normalisation

Two integers: `--tolerance-nm` for lengths and `--tolerance-udeg` for angles. Both default to 0, because
the model is exact and two reads of one file must be identical.

- **Length.** Two lengths are equal when they differ by at most the tolerance. Points and sizes are
  compared per coordinate; no distance is taken.
- **Angle.** Angles are compared on the circle: −90° and 270° are equal. The period is 360° unless the pad
  rule below says otherwise.
- **Text.** Values, references, pin numbers and footprint names are exact strings: no case folding, no
  trimming.
- **Footprint name.** The part of the library reference after its last `:`. The nickname before it
  belongs to a library table, not to the board.
- **Pad rotation by shape.** A circle, and an oval whose two sizes are equal, has no rotation: the field
  is not compared. A rectangle, an oval and a rounded rectangle are compared modulo 180°, and such a pad
  also equals the pad with its two sizes swapped and its rotation a quarter turn away (1.0 × 0.5 at 0° is
  0.5 × 1.0 at 90°); then neither `pad-size` nor `pad-rotation` is reported. A trapezoid and a custom
  shape are compared modulo 360°. When the two shapes differ, the smaller period applies.
- **Copper span.** Which of `top`, `inner` and `bottom` a pad's layers reach, by the ordinals of the
  board's copper layers, so `F.Cu` in one file and the top layer of another are the same. A layer name
  the board does not declare makes the span unknown: it is not compared and is counted in
  `summary.copper_unknown`.
- **Side.** Compared exactly.
- **Frame.** `--frame absolute` compares positions as they are. `--frame relative` first removes one
  translation: per axis, the lower median over the compared footprints of the position on side `b` minus
  the position on side `a`. The median is a value of the data and stays right while fewer than half of
  the footprints moved. The result holds the translation. No rotation and no mirror of a whole board is
  removed: a flipped axis would be a fault and must stay visible.

## Exclusion files

A known difference can be named in a TOML file and applied with `--exclusions FILE --profile NAME`. An
excluded difference stays in the output, under `result.excluded` with the id of its rule, and never
fails the command. A rule never stops a comparison.

```toml
schema = 1

[[profile]]
name = "my-board"
tool = "none"
tool_version = "1"
frame = "relative"
tolerance_nm = 10
tolerance_udeg = 0

[[profile.rule]]
id = "j3-footprint-renamed"
level = 3
kind = "footprint-name"
where = "J3"
attribution = "undecided"
reason = "the connector's footprint was renamed in one of the two libraries"
hypothesis = "H-G-EQ-FPNAME"
```

- A profile holds `name`, `tool`, `tool_version`, `frame`, `tolerance_nm`, `tolerance_udeg` and its
  rules. The profile supplies the frame and the tolerances; an option on the command line overrides them.
- A rule holds `id` (unique in the file), `level`, `kind` (a kind of that level), `where` (a glob over the
  difference's `where`, matched with letter case), `attribution` (`importer` or `undecided`), `reason`
  and `hypothesis`, and may hold `field` and `corpus` (a list of corpus row ids). The first matching rule
  in file order wins.
- Any other key, a missing key, a kind of another level or a duplicate id is refused (`FEN-3004`).
- A rule selects by level, kind, field and `where` only. It cannot match a value.

## The triangle

`fenolite equivalent A.PcbDoc --against kicad-import` reads one Altium PCB document twice: with
Fenolite's Altium backend, and with `kicad-cli pcb import --format altium` (KiCad 10.0 only) followed by
Fenolite's KiCad reader. The two models are compared under the profile `kicad-import` of the running
`kicad-cli` version line, which ships in
`src/fenolite/backends/kicad/data/altium_import_exclusions.toml`.

- The profile's frame is `relative`: KiCad moves an imported board on its sheet. Its tolerance for 10.0
  is 10 nm: KiCad holds a converted length in steps of 10 nm.
- Each rule of the profile names one behaviour of KiCad's importer that was observed by running the tool.
  `importer` means that a public source or the tool's own output shows that the importer makes the change.
  `undecided` means that the two reads differ and no public source says which is right. A difference that
  Fenolite causes gets no rule: it is fixed.
- A `kicad-cli` version line without a profile runs with no rule and gives the warning
  `equiv.no-exclusion-profile`.
- The warnings and errors of the import are reported as `equiv.import-message` infos.
- Pads that belong to no component are footprints without a reference in both reads, so they give one
  `ref-ambiguous` difference; pass `--ignore-ref ""` to leave them out.

What the label means: `evidence.oracle` is `kicad-cli`, and a result without difference says that two
independent readers of one file agree at that level. It says nothing about Altium Designer, and both
readers could share a mistake. The measured results per public document, the rules and what remains
undecided are in `docs/evidence/equivalence-triangle.md`.
