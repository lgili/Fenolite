# Preserve formatted group-bus prefixes

## Why

The native drawn census owner017 retains all 4712 pins, but has 1427 own electrical groups versus 1355 native groups and 24 unmatched sheet-pin errors. Parent and child port spellings agree exactly. The rejected port family uses formatted braces in a group prefix; the current group splitter rejects braces anywhere in the prefix. This affects fifteen declared owner-context rows. Standalone-unowned hierarchical ports and inputs below the published reader floor are different boundaries and are not covered by this correction.

The primary KiCad 10 Schematic Editor manual, section Buses, permits markup in bus prefixes. That prose is format knowledge, not a copied implementation or grammar. Actual native authored controls must establish the exact literal naming and pin behavior before code changes.

## What changes

After independent native proof, recognize only the measured balanced formatting spans in an otherwise existing group-bus prefix. Preserve the complete prefix text and expanded member cardinality. Keep ordinary group, alias, vector and bus identity policies unchanged. Do not add text-variable expansion, quoted-space syntax, arbitrary nested groups, warnings suppression, baseline changes or loss acceptance.
