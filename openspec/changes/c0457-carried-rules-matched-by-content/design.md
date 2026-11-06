# Design of c0457

## Decisions

1. **Keys without names.** A build of an imported design names its rules from the design, not from the
   conversion (`fenolite_0_min_clearance` for an unscoped rule the import made a board minimum). So the
   key of a rule list is the SHA-256 of its children after the name, each in compact form, in sorted
   order, a condition's runs of spaces made one. The shape key leaves out the values of `min`, `opt` and
   `max`, so it tells an edit of limits from an edit of a condition, a layer, a severity or a constraint.
2. **Matching.** Each block of a record takes a distinct rule of the same content, one of its own name
   first. A record whose blocks all find one is kept. Then every other rule of a content a kept record took
   is taken too: it is a copy of the same rule, which the record already writes. Lowering it would add a
   rule the source does not have.
3. **Version 0.** A property written by c0434 keyed each list by `digest(rule_text(node))`, the name
   inside. Such a key still matches a rule renamed since: the rule is printed under the record's name and
   hashed again. It has no shape key, so an edited version-0 record is lowered.
4. **Edited limits.** A record whose rules are all in the file under their names, with their shapes, has
   its limits edited. `rulemap.edited_fields` writes each limit into the keys that hold it for that record
   kind (a Routing Via Style takes the `hole_size` of vias in `MINHOLEWIDTH` and `MAXHOLEWIDTH`). A key
   whose value did not change keeps its text. A limit that no key holds falls back to lowering.
5. **The pour stays.** The pour of the way back refuses a polygon a Clearance record of unread scope could
   govern, as the pour of the source does. lote-27 poured such polygons only because the record was lost.
   An experiment poured them with the record ignored and with the larger of its gap and the governing gap;
   compared by M1 with the regions the source document saves, 8 of 9 polygons of -04 and 4 of -07 failed
   (S-2160). A pour that cannot match Altium's copper is not written as poured, so the refusal stays.

## Proof

- `tests/unit/convert/test_rule_carrier_c0457.py`: renamed and reordered rules, an edited limit, an added
  condition, a version-0 property, and flow A on an authored document.
- `tests/corpus/test_altium_pour_c0457.py`: public row -04 refuses on the way back the 9 polygons the pour
  of its source refuses, and writes them.
