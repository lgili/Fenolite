# Altium rules without loss

## Why

The maintainer wants a lossless conversion of an Altium board. On a private board, 43 rules in 31 groups are
reported lost as unmapped, and 12 more are lost with `via_drill takes no 'opt' limit`. The reports are
descriptions only. Every case in this change is authored for Fenolite, and no rule name, value or record
from that board enters the repository.

Four causes, all in Fenolite:

- **Closed mapping table.** `read.rules.RULE_KIND_MAP` maps eight Altium kinds. Several more have a model
  kind that KiCad writes: Silk To Silk Clearance (`silk_clearance`), Component Clearance
  (`courtyard_clearance`), Differential Pairs Routing (`diff_pair_gap`, `diff_pair_uncoupled`), Routing
  Layers (`no_tracks` per layer), and Hole To Hole Clearance with stacked micro vias allowed
  (`hole_to_hole`).
- **Counted as lost.** A record that maps to nothing is one `altium.import.rule-unmapped` group, and the
  Altium to KiCad conversion counts each group as a lost `rule`. Fenolite then forgets the record, so an
  Altium write of the imported design cannot keep it either. A disabled rule is treated the same way.
- **An unwritable limit drops the whole rule.** KiCad's `hole_size` constraint of a via drill takes `min`
  and `max` only. The conversion lowers each imported rule alone and drops the rule when the lowering
  refuses its `opt`, so the drill's minimum and maximum are lost too. `import --to python` converts first,
  so the rule is missing from `design.py`.
- **Shadowed rules.** A build of the imported design reports `rules.shadowed`. Nobody has checked whether
  the governing order still matches Altium's priorities.

## What Changes

- **More kinds map (reader).** `RULE_KIND_MAP` gains Silk To Silk Clearance, Component Clearance,
  Differential Pairs Routing and Routing Layers. Hole To Hole Clearance maps with either value of
  `ALLOWSTACKEDMICROVIAS`. Keys and value forms come from the public rule file S-0297 and the eight public
  PCB documents (S-1838). The meaning of each kind comes from Altium's rule pages (S-1830 to S-1837).
- **Kept, not lost (import).** The import keeps every rule record that gives no rule which the Altium
  writer lowers again: its kind number and its keys from `RULEKIND` on, as a `kept_rule` pair of the
  board, in record order. This includes disabled records, records of a kind without a model counterpart,
  and records the mapper refuses. A rule mapped from a kept record is marked, so the Altium lowering
  leaves it to the record.
- **Written back (Altium writer).** The PCB document of an imported board writes its kept records again,
  after the records of their kind. A kept record of a kind with no lowered rule keeps its own priority.
- **Fate of every record (conversion).** The Altium to KiCad conversion gives each rule record exactly one
  outcome:
  - `written`: KiCad holds it as it is;
  - `changed`: KiCad holds it in another form, for a stated reason;
  - `kept`: KiCad cannot hold it, so it is a declared format limit, kept in the model for an Altium write.

  A record that matches none of these is `lost`. The report gains the outcome `kept`, and a row's `kept`
  count is shown when it is above zero.
- **Partial limits are written (conversion).** When KiCad's constraint takes no `opt`, the conversion
  writes the rule's `min` and `max` and reports the rule as `changed`. The model keeps `opt`. The rule
  reaches the KiCad rules file and, through it, `design.py`.
- **Shadowed rules checked.** A test proves that the governing order of the imported rules is Altium's
  (priority 1 governs) after `import --to python` and a build. `rules.shadowed` then states Altium's own
  overriding and changes nothing.
- **Not touched.** The Polygon Connect Style mapping onto zones and the "no net" clearance scope belong to
  change c0420. Their records keep the handling they have today.

## Impact

- Code: `backends/altium/read/rules.py`, `backends/altium/adapter/rules.py`, `adapter/board.py`,
  `backends/altium/lower.py`, `pcbdoc.py`, `rulemap.py` (the lowering skips marked rules),
  `convert/report.py`, `convert/altium_to_kicad.py`, `convert/to_kicad.py`, `api/schema.py`.
- Schemas: `ReportReason.outcome` gains `kept` and `ReportRowReply` gains an optional `kept`. The model
  schema does not change, because the board keeps its pairs in its existing `altium` bag.
- Docs: `docs/formats/altium/rule-file.md` (new rows, kept records, fates), `docs/evidence/sources.md`
  (S-1830 to S-1838), `docs/altium.md`, and the agent guide page for the report outcome.
