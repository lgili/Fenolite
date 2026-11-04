# Why
Native schematic instances can declare a footprint library alias different from
the board's nickname for the same footprint basename. Import currently replaces
that field with the board nickname, changing visible source text at level8 even
though pad geometry and electrical connectivity are equal.

# What Changes
Bind original aliases by actual source file/symbol UUID/use-path/ref, retain the
original nonempty source alias where the physical basename agrees, and vendor
the exact board-derived geometry under that local alias. Preserve the existing
L3 namespace-independent basename contract, actual pads, UUID/ref/path bindings
and source drawings. Refuse conflicting source bindings or alias/geometry
definition-lookup collisions before a plan is staged; never change the L3 comparator or invent an
arbitrary Footprint text override. Genuine basename mismatches are not normalized
away. Use existing c0318 footprint_definition to retain exact per-ref physical
variants behind a shared logical alias; no new model/DSL fields are needed.
