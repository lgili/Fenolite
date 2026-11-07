# Design: exact import self-check

## Context

`import --to python` builds the code it emits and compares the result with the source (`importer.check`, levels 1
to 5, no tolerance). The level 3 comparison reads each pad in its footprint's own frame. A difference of a few
nanometres therefore cannot come from a rotation, because positions are not turned. It has to come from a
different footprint.

## Decisions

1. **Fix the name, not the tolerance.** The differences were not rounding. The rebuilt part used another
   footprint's pads, because two footprints shared one file. A tolerance would hide that, and it would not
   explain the cases above 1 µm, the size or the side. So the import tolerance stays 0, and the variant name
   becomes unique.
2. **Next free number.** The variant of `<name>` is `<name>_<n>` with the lowest `n` that names no footprint
   of the board and no earlier variant. The names of the board's footprints are collected first, so an
   instance read later cannot take a name a variant already holds. A board without such a name keeps today's
   names, so existing outputs do not move.
3. **An equal drill is accepted.** KiCad's file and the model hold a via whose drill equals its diameter. The
   DSL now accepts it, so the import writes it as it reads it, without a native fallback. A larger drill has no
   meaning as a via, and it is still refused. The fanout and the other generators, which make new vias, keep the
   strict rule. A rule check (`annular_width`) still reports the missing ring where the design asks for one.

## Risks

- A library made by `fenolite library` from a board that holds `<name>_2` as a footprint of its own now names
  the variant `<name>_3`. Before, it overwrote the file, so nothing that worked changes.
