---
topic: equivalent-s
title: Compare drawn schematics
summary: Drawings and nets.
---

# Compare drawn schematics

Request `--level S` to compare actual native schematic sheets and resolved pin connectivity. A raw
schematic, a KiCad project, or a build with written sheets can be a side. This comparison reads the
embedded symbols and hierarchy; it needs no netlist export or external tool.

```fenolite-cmd
fenolite equivalent before.kicad_sch after.kicad_sch --level S --json
```

Python callers use `fenolite.api.equivalent(a, b, level="S")`. The result has the existing keys, with
`level: "S"` and one level named `schematic`. Every integer/default comparison keeps its prior behavior.
Missing or unreadable sheets are a usage error naming the side. Altium drawings are not read by S.

S compares symbol and field poses, sheets, wires, buses, labels, power symbols and opaque drawing items.
A missing junction gives `equiv.item-missing`; when it changes pin connectivity, `equiv.drawn-net` stays
visible too. An explicit exclusion for the junction item does not exclude the changed net. Exit 5 lists
remaining differences. Geometry tolerances default to zero; S compares the actual sheet coordinates.

`--strict`, `--ignore-ref` and the PCB import triangle apply to other comparison modes; S refuses them
instead of silently dropping drawing content. Scoped S profile reasons stay in the profile; `excluded`
records their matching rule ids. The drawing proof is **INFERRED**, with native gates recorded separately.

Read next: `checks`, `files`.
