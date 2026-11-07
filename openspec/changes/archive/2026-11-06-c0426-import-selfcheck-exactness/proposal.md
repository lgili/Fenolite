# Exact import self-check

## Why

A reference sweep of `fenolite import --to python` on 53 private Altium boards and projects refuses 30 with
`import.unequal`. The maintainer reported the counts only. Every case in this change is authored for Fenolite,
and no board data enters the repository.

| kind | items | cases |
|---|---|---|
| level 3 `pad-position`, 10 nm or less | 379 | 27 |
| level 3 `pad-position`, above 1 µm | 24 | 11 |
| level 3 `pad-size`, above 1 µm | 29 | 13 |
| level 3 `pad-copper`, a bottom pad built on top | 3 | 3 |
| level 5 `route-connectivity`, an island split off | 6 | 6 |
| the emitted code does not build: `via_table` "drill not smaller than diameter" | 2 | 2 |

Two causes, both in Fenolite:

- **One file for two footprints.** The import derives its vendored library from the board
  (`library.derive_from_model`). Instances of one footprint that differ are written as `<name>_2`, `<name>_3`
  and so on. The Altium to KiCad conversion already writes a project library whose own footprints are named
  that way: a footprint that differs from its library footprint is `<name>_2`. A derived variant then takes
  the name of another footprint of the board. Both are written to one file, and the second overwrites the
  first. Every part bound to the lost footprint builds with the pads of the other one: a few nanometres off,
  above 1 µm off, another size, or the other side. Its tracks then miss the pad, and an island splits off.
  Measured on a private board: removing the collision makes all its 20 differences go away.
- **A via without a ring is refused.** An Altium document can hold a via whose drill equals its diameter. The
  model and the KiCad writer hold it, but `via_table` and the copper build refuse any drill that is not
  smaller than the diameter, so the emitted code does not build.

Two public PCB documents show the same two causes on `origin/cac/lote-24` 948b6a376: `altium-third-party-pcbdoc-01`
rebuilds one pad 1 nm off, and the code of `altium-third-party-pcbdoc-02` does not build because of a via whose drill
equals its diameter. They are the proof cases of this change.

## What Changes

- **Variant names (library derive).** A variant never takes the name of another footprint of the board, nor of
  another variant: when `<name>_<n>` is taken, the next free number is used. This also applies to
  `fenolite library`.
- **Via without a ring (DSL and copper build).** `via_table`, `via` and the copper build accept a drill equal to
  the diameter, and refuse a larger one with "the drill … is larger than the diameter …". The fanout and the
  other generators keep their strict rule, because they make new vias.

## Out of scope

- A level 2 `net` difference: two pads of one number where only one is on the net (two cases of the sweep). It
  needs a DSL way to connect one pad of a number. It is a follow-up.

## Impact

- `src/fenolite/library/derive.py`, `src/fenolite/dsl/intents.py`, `src/fenolite/backends/kicad/copper.py`.
- Specs: `design-conversion` ("Library made from a board"), `manual-copper` ("Tracks from intents", "Copper issue
  codes"), `design-dsl` (a new requirement for the via without a ring).
- No new command, DSL name or issue code. The meaning of `kicad.copper.bad-size` changes for an equal drill.
