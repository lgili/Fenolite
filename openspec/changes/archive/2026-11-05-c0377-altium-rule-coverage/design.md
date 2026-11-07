# Design notes: c0377

## Found on 2026-11-04: public corpus census after the two mapped classes

CI run 41947475460 on cac/lote-15 measured the public Altium documents with the new mapping. Every change
is a rule that now maps because of one of the two classes, with a selector equal to its source expression:

- `altium-third-party-pcbdoc-04`: Board Outline Clearance `not InNet('GND')` (lower-case operator) gives a
  second edge clearance.
- `altium-third-party-pcbdoc-05`: Minimum Annular Ring `NOT IsVia` (upper-case operator) gives a second
  annular ring rule.
- `altium-third-party-pcbdoc-08`: the Clearance rules `Antenna_50ohm` (`(InNet('RF_OUT') or
  InNet('RF_ANT'))`) and `Antenna_50ohm_via` (`(IsVia AND InNet('RF_ANT'))`) map, so the check judges with 4
  clearance rules and 1 stays unread (was 2 and 3); Width and Hole Size with `NETSCOPE=DifferentNets` map;
  Routing Via Style now stops on its template keys (`keys`) instead of its net scope. One polygon is no
  longer refused for a rule scope; an earlier refused polygon of its layer lies within its reach, so it is
  refused as `depends-on-refused` (pour census 13 and 10 become 14 and 9).

The census expectations of `tests/corpus/test_altium_rule_kinds.py`, `test_altium_copper.py` and
`test_altium_pour_census.py` take these values. `test_vias_without_inner_pads` found the generic clearance
rule as the one rule without `/` in its name; the RF rules have none, so it now selects the rule that
applies to all objects (`Selector("all")`, no second selector), the same rule as before.
