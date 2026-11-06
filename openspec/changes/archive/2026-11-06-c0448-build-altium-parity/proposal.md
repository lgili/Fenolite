# c0448: build-altium-parity

## Why

`build --target altium` of a design imported from an Altium board (`import --to python`) writes less than
`convert --to altium` of the same board now writes (S-2070..S-2079):

1. A net-tie footprint with a copper graphic (an `F.Cu` line joining its pads) is refused by the library
   check, so the footprint and the whole PCB document are not written. c0431 fixed this in the lowering,
   which only a conversion reached.
2. Every pad's own solder-mask margin is reported dropped (`altium.primitive-dropped`), though c0440's pad
   writer writes it as a manual expansion.
3. An outline with an arc (public row `altium-third-party-pcbdoc-06`) gives no PCB document at all, and
   for a build the lowering writes the outline's points without c0441's arc vertices.

## What changes

- `pcblib.check_footprint` takes the copper graphics of a footprint with net-tie groups; the PCB document
  writes them through the lowering of c0431 (component kind 4).
- `lens.altium.pad_extras` no longer drops a margin the model holds.
- The build plans the document for an outline with arcs, and the lowering writes each arc of a build's
  outline as one arc vertex, as for a conversion.

## Not in this change

- Public row `-01` stops before these items: 12 parts without a reference give `altium.text-unwritable`
  and `model.duplicate-ref` in the build (follow-up).
