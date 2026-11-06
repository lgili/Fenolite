# Design of c0434

## Decisions

1. **A write of a model writes its own rules, and of the c0038 rules only what KiCad checks.**
   - Change c0038 wrote a Clearance, Width and Routing Via Style record per net class and an `All` default
     per kind, so that a build from a script, whose net classes the user wrote, carries its widths to
     Altium. A build keeps them.
   - A write of a model has rules of its own: those a source record gave (a KiCad rules file, an Altium
     record read back) or the user wrote. Its net classes come from the source project. A KiCad project
     gives every class a clearance, a track width and a via size, KiCad's defaults when the board came
     from Altium.
   - KiCad's DRC checks a class's clearance and does not check its track width or via size (those set
     the router's defaults). So a write of a model writes no class Width or Routing Via Style record.
     -08's 2292 Width violations came from such records.
   - A clearance rule with no condition overrides every class clearance in KiCad. Altium writes the
     design's rules first, so a class Clearance record would never apply, and it would still add records.
     So when a Clearance record of the design has the scopes `All` and `All`, no class Clearance record is
     written. Otherwise the class clearances and the `All` clearance stay. A KiCad board without a rules
     file needs them, and the computed pour reads them.
   - The switch is `PcbDocSpec.class_kinds`, set by `from_design`. Every caller of `pcbdoc` that builds a
     spec itself keeps all three kinds, as before.
   - A class whose values are left out is counted `changed` under `netclass`, so the report says it. It is
     not a loss: the class and its members are written.
2. **No invented limit.** The first version of c0434 wrote a missing limit open (min 0, max 100 mm). A
   board minimum or a class minimum then became a Width, Hole Size or Routing Via Style record with
   limits no source gave. That part is dropped. A rule lacking a limit stays `value-unsupported`, as
   before. The pairing of a lone `via_diameter` rule with a `hole_size` rule, and the Component Clearance,
   Silk To Silk Clearance and Differential Pairs Routing rows, are dropped too: each wrote keys that no
   neutral rule holds.
3. **Every loss in the refusal.** The refusal stays tied to the `refuse` kinds. Its `issues` now hold every
   lost row, in report order, and its message adds "--allow-lossy also loses items of …". The CLI already
   copies a refusal's `issues` into the envelope (`cli/main.py`), so the envelope carries them on a dry run.

## Proof

`tests/corpus/test_altium_rules_c0434.py` converts the public -08 to KiCad and back with outline pours. It
compares the written rule records with the source's by kind and limits. It reads kinds, counts and limits
only.
