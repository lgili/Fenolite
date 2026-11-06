# c0434: write the rules a KiCad rule set gives to Altium, and list every loss before consent

## Why

A board converted from Altium to KiCad and then written back to Altium loses 16 to 19 of about 125 rules
on the owner's board, so the DRC rule set of the written PCB document is incomplete. The public document
`altium-third-party-pcbdoc-01` shows the same: 4 of its 8 rules are not written on the way back (S-1931).
- `track_width`, `via_diameter` and `hole_size` give `value-unsupported`, netclass-scoped rules too:
  - KiCad's board minimums give `min` only, and an Altium record holds every limit.
  - KiCad holds a via's drill as a `hole_size` rule on vias, so the `via_diameter` rule has no
    `via_drill` partner of its selector.
- `courtyard_clearance`, `silk_clearance`, `diff_pair_gap` and `diff_pair_uncoupled` give
  `no-counterpart`, although change c0424's reader maps Component Clearance, Silk To Silk Clearance and
  Differential Pairs Routing back to them.

The refusal without `--allow-lossy` (`FEN-7001`) names the `refuse` kinds only, so the losses of the
`report` kinds (rules, texts, graphics) show up only after the user has consented.

## What Changes

- **Missing limits.** A limit that a rule does not give is written open and the rule is counted changed,
  not lost:
  - a missing minimum is written as 0;
  - a missing preferred value is written as the rule's minimum;
  - a missing maximum is written as 100 mm, the largest maximum of a public record.
- **Via holes.** A lone `via_diameter` rule takes the hole limits of the governing `hole_size` rule on its
  vias.
- **New kinds.** `courtyard_clearance` is written as `ComponentClearance` (24), `silk_clearance` as
  `SilkToSilkClearance` (55), and `diff_pair_gap` with `diff_pair_uncoupled` as `DiffPairsRouting` (51),
  with the key order of the public records.
- **Every loss before consent.** `LossyConversionError` and the Altium writer's `LossyWriteError` list
  every loss that consent would accept, and their messages name the other lost kinds.

## Capabilities

- `altium-pcb-writer`: "Rule lowering table" and "Scoped rule records", modified.
- `design-conversion`: "Lossy conversions need consent", modified.
- `altium-build`: "Rule minimums in an Altium build", modified (a width or hole minimum is written open).

## Out of scope

- A negative silk-to-silk minimum, which c0427 keeps.
- Silk To Solder Mask Clearance: its kind is not mapped by the reader.
- An Altium run of the new records (`H-A-RULE-OPEN-LIMIT` stays `INFERRED` until a kit run).

## Impact

- `backends/altium/rulemap.py`, `backends/altium/lower.py`, `backends/altium/read/rules.py` (three keys
  marked read-only), `convert/__init__.py`; the `changed` list of `result.rules` (`cli/results`,
  `schemas/`) and of `lens/altium_copper.py` and `exports/altium_rul.py`.
- Docs: `altium.md`, `pcb-copper.md`, `hypotheses.md`, `sources.md` (S-1930, S-1931), `matrix.md`.
