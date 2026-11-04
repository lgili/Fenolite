# Root-sheet identity

## Measured trigger

The actual `sonde_xilinx` replay on signed
`1918e63214a7d0123e1f5fa8ef095c73fd2e1472` returns exit 5 with only two
level-8 findings: `sheet:sonde xilinx.kicad_sch` and
`sheet:sonde_xilinx.kicad_sch`. Levels 1–7/S are equal, with no acceptance.
The original inputs are declared public corpus bytes; no CAD is copied here.

## Bounded pairing

Resolve each project's board using the existing project resolver. Its matching
`.kicad_sch` is the explicit root, never the first sorted filename. When both
root scenes exist and their relative filenames differ, compare the rebuilt
root under the original root's identity. All primitives, masks and child scene
keys remain intact. Equal root names keep existing replies byte-for-byte.

If either spelling collides with a child identity on the opposite side, refuse
the ambiguous pairing explicitly. Do not overwrite a scene. Missing roots are
not guessed or synthesized, and unrelated sibling projects remain excluded by
the existing one-project selection. No hierarchy-wide basename matching or
general path equivalence is introduced.

## Proof

First reproduce the false missing panels using a completely original authored
hierarchical project whose root has a space. Preserve source-format versions,
all input hashes and nonempty routed copper. After the correction, prove all
nine levels for targets 9/10 with zero accepted differences. Prove collisions,
unchanged child panels and retained visible differences independently, then
repeat the actual public sonde proof on a clean signed source.

Keep the default pixel/grid tolerances, byte guards, model 0, prepared model-1
hold and native/full/exact-head CI gates unchanged.
