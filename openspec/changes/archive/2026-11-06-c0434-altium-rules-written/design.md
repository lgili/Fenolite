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

4. **A board property, not KiCad rules and not a file beside the board.** The records travel in the
   root property `Fenolite.Altium.Rules6` of the `.kicad_pcb` (`backends.kicad.boardcarrier`, shared with
   change c0450), not as KiCad rules, not as comments of the rules file and not in a file beside the
   project, which goes stale or is lost when only the board travels. KiCad keeps neither comments nor
   unknown constraints when it saves a rules file; a re-save keeps a board property (H-K-FENOLITE-PROPS).
   The property holds each record from `RULEKIND` on, the form the kept records of c0424 use, and the
   SHA-256 of each rule list the record gave as Fenolite writes it (`dru.rule_text`). A record is kept when
   each of its rule lists is in the rules file with that hash; a reformatted list counts as edited, which
   errs on the side of KiCad's rule.
5. **Records first, then what KiCad added.** With source records, `rule_records` writes them as given,
   then the lowered rules that no kept record accounts for (KiCad-only or edited) with the next priority of
   their kind and a name not yet written, then the kept records of c0424. No c0038 rule and no `All`
   default. The Plane Connect and Plane Clearance rules of c0389 only for a kind no record holds. The
   Polygon Connect Style records of the zones are not written when a record of that kind is.
6. **Which losses refuse.** A lost rule whose rule list a source record gave is `SOURCE_RULE_LOST`
   (refuse class): the user edited a source rule into a form Altium cannot hold. A rule only KiCad holds
   is still a `report` loss. The report's `rule` row counts the rules the written records stand for.
   Netclass counting in this mode covers the width and via kinds only, which are the ones c0038 wrote.

## Proof

`tests/corpus/test_altium_rules_c0434.py` converts the public -08 to KiCad and back with outline pours. It
compares the written rule records with the source's by kind and limits. It reads kinds, counts and limits
only.
With the carrier, the test asserts that the 56 records come back equal, keys and values from `RULEKIND` on.
`tests/unit/convert/test_rule_carrier_c0434.py` proves the edited, removed and added cases on an authored
document.
