# c0457: carried rule records matched by content, and edited rules written

## Why

Change c0434 carries every rule record of an Altium document through KiCad (`Fenolite.Altium.Rules6`) and
writes a record back as read when its rule lists are still in the `.kicad_dru`. On `cac/lote-28`
(abe1de83f) the maintainer's board shows two regressions, both blocking flow A (counts and codes only,
the board is private):

- **Flow A refuses.** `import --to python`, one clearance edited (0.25 → 0.26 mm), `build`, then
  `convert --to altium`: 11 rules are reported `SOURCE_RULE_LOST`, so the conversion exits 7 without
  `--allow-lossy`.
  - c0434 keys each rule list by its text, its name included. A build of the imported design writes the
    rules file again, with other names (an unscoped rule becomes a board minimum, `fenolite_0_min_*`).
    So untouched records look edited.
  - A record edited in KiCad is lowered from the KiCad rule. Any rule whose limits KiCad holds in part
    (Routing Via Style, Width) is then refused. So no rule edit reaches Altium.
- **The computed pour refuses.** Flow B writes all 28 polygons unpoured: "a Clearance rule with a scope
  Fenolite does not read could govern the polygon". On `cac/lote-27` the same board poured all 28.
  - The record was lost on the way to KiCad before c0434. Now it comes back, and the pour refuses every
    pair that the record could govern.
  - Public row `altium-third-party-pcbdoc-04` shows the same: 9 polygons poured on lote-27, 9 unpoured on
    lote-28 (S-2160). The pour of the source document refuses the same 9 polygons for the same record.
  - Pouring them anyway does not give Altium's copper. With the record ignored, or with the larger of its
    gap and the governing gap, 8 of the 9 saved pours of -04 differ by 3.5 to 7.4 times the M1 allowance,
    and 4 polygons of -07 by up to 10.9 times (S-2160). So lote-28's refusal is right, and lote-27 poured
    copper Altium would not.

## What Changes

- **Matched by content.** The property keys each rule list by its content and its shape (version 1, schema
  `fenolite.altium-rules.v1`, `rulecarrier.rule_keys`). Both leave out the rule's name, the order of its
  children and the spaces of its condition; the shape also leaves out the values of `min`, `opt` and `max`.
  - A record is kept when each of its lists is a distinct rule of the file of the same content.
  - A rule of the same content as a kept record's rule is a copy (a board minimum the import made from it).
    It is taken too, not lowered.
  - Version 0 properties (c0434) are still read: a rule then matches under its own name or under the name
    the record gave.
- **Edited rules are written.** A record whose rules keep their names and shapes, with other limits, is
  written with KiCad's limits: its name, priority, scopes and enabled state stay (`rulemap.edited_fields`).
  It counts `changed` under `rule`. Any other edit is lowered as a rule of its kind and counts `changed`.
  `SOURCE_RULE_LOST` stays for an edit that no Altium record can hold.
- **The pour follows the source.** No change to the pour. A corpus test pins that the way back refuses
  the polygons the pour of the source refuses, and still writes them.

## Capabilities

- `design-conversion`: "Carried rule records matched by content", "Source rules edited in KiCad" and
  "The pour of the way back follows the source", added.

## Out of scope

- Reading the scopes the pour refuses today (`InPolygon`, `HasFootprint`, `InDifferentialPairClass`,
  layer queries): a change of its own, measured against the census.
- Rules that the import turns into net-class values of the project.

## Impact

- `convert/rulecarrier.py`, `convert/to_kicad.py`, `convert/to_altium.py`, `backends/altium/rulemap.py`.
- Docs: `rule-file.md`, `pcb-pour.md`, `sources.md` (S-2160, S-2161), CHANGELOG.
