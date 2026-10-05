# Altium stack-up file (`.stackup`)

This page states, in Fenolite's own words, what the stack-up reader
`fenolite.backends.altium.read.stackup` (change c0042) relies on. The sources are Altium's public
documentation (S-0300) and three public stack-up files saved by Altium Designer from two repositories
(S-0297, S-0187; corpus rows `altium-third-party-stackup-01` to `-03`), fetched to the corpus cache and
never committed. The layer keys are those of the board record's stack (`pcb-library.md`). No parser code
of another project was read.

## Facts

| fact | source | label | hypothesis |
|---|---|---|---|
| The Layer Stack Manager saves a layer stack to a `*.stackup` file and loads one from it | S-0300 | INFERRED | H-A-RD-PRJ-STACKUP |
| A stack-up file is one property text: `KEY=VALUE` fields, each after a `\|`, with no line end. After an optional UTF-8 byte-order mark it starts with `\|STACKUPVERSION=1`; one file ends with a last `\|` | S-0297, S-0187 | INFERRED | H-A-RD-PRJ-STACKUP |
| A layer is the set of keys `LAYER_V<g>_<i><KEY>`, where `<g>` is a generation number (`8` in every file read) and `<i>` the position from 0, from the top of the stack to the bottom, then the mechanical layers | S-0297, S-0187 | INFERRED | H-A-RD-PRJ-STACKUP |
| A layer holds `NAME`, `LAYERID`, `ID` and `USEDBYPRIMS`. A copper layer adds `COPTHICK` and `COMPONENTPLACEMENT` (`1` on the top layer, `2` on the bottom layer, `0` on an inner layer). A dielectric adds `DIELTYPE`, `DIELCONST`, `DIELHEIGHT` and `DIELMATERIAL`; a solder mask is written as a dielectric with `DIELTYPE=3`, the cores and prepregs with `DIELTYPE` `1` or `2`. Overlays, paste and mechanical layers have no thickness | S-0297, S-0187, S-0170 | INFERRED | H-A-RD-PRJ-STACKUP |
| Thicknesses are written as a decimal number with the unit: `mm` in one repository, `mil` in the other. `DIELCONST` is a decimal number written as text | S-0297, S-0187, S-0163 | INFERRED | H-A-RD-PRJ-STACKUP |
| Besides the layers the file holds the master stack and its sub-stacks (`LAYERMASTERSTACK_V<g>…`, `LAYERSUBSTACK_V<g>_<n>…`), `DISPLAYUNIT`, and in the newer file a document id, features, via spans, impedance profiles, trace impedances and layer keys that start with `$LSM$` or with a braced id | S-0297, S-0187 | INFERRED | H-A-RD-PRJ-STACKUP |

## Fenolite's choices

- `StackupFile.to_bytes()` gives the input back; `record` holds every field in order.
- An entry is typed when its keys hold `COPTHICK` (kind `copper`) or `DIELHEIGHT` (kind `dielectric`),
  in ascending position. The kind of a dielectric (core, prepreg, solder mask) stays the integer
  `dielectric_type`; the import (c0043) maps it.
- `thickness` is the length in nanometres (`proptext.parse_length`, `mil` or `mm`, rounded half to even
  to the nanometre); a value that does not parse gives `None` and the warning
  `altium.stackup.length-unreadable`. `epsilon_r` is the `DIELCONST` text as written, never a float.
- The generation number is read from the keys, not fixed to 8. Keys of more than one generation give
  the warning `altium.stackup.unknown-form`, and the entries are read from the highest one.
- Every other key stays in `record` and is not typed.
