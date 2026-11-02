---
topic: equivalent-s
title: Compare drawn schematics
summary: Drawings and nets.
---

# Compare drawn schematics

Local property variants require `load_schematic(..., symbol_contexts="symbol-contexts.toml")`.
The closed index binds every sheet's full native property snapshot and digest-named assets;
missing/stale bindings, unsafe paths and symlinks refuse. Pin/body/flag/core-default conflicts still refuse.
This input changes no model/S field; ordinary projects keep their existing bytes.
Schema `fenolite.symbol-contexts.v0` requires every used native definition once a variant exists.
Build/sync plans bind all inputs; `FEN-4002` requires review again after an edit.
Sync refuses changed cache metadata; contextual projects require KiCad schematic output.

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
