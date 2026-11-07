# c0434: write only the rules a source holds, and list every loss before consent

## Why

Flow B (an Altium PCB document converted to KiCad and back to Altium) adds rules that the source never had.
On the public row `altium-third-party-pcbdoc-08` (DM3370), Altium 24.5 counted 18 rules where the source
has 4, and 2292 Width violations where the source has none (S-1930; reported by the session
`altium-rounds-2`).

- The Altium writer adds the rules of change c0038 to every PCB document: one Clearance, Width and Routing
  Via Style rule per net class that holds the value, and one `All` rule per kind with Fenolite's default.
- A KiCad project holds a clearance, a track width and a via size in every net class. A board converted
  from Altium gets KiCad's defaults there (0.2 mm, 0.2 mm, 0.6/0.3 mm), because an Altium net class holds
  no rule values. -08 has 14 such classes.
- On the way back, each class becomes a Clearance, Width and Routing Via Style record that no source record
  gave. Each of those records tightens or adds a check.

The first version of c0434 (reverted on `cac/lote-26` as 0dd270812) made this worse. It wrote a rule that
lacked a limit with an open limit, so board minimums and class minimums became Width, Hole Size and Routing
Via Style records too.

The refusal without `--allow-lossy` (`FEN-7001`) names the `refuse` kinds only. So the losses of the
`report` kinds (rules, texts, graphics) show up only after the user has consented.

## What Changes

- **Rules of a model write.** A write of a model (`lower.write_design`, `convert --to altium`,
  `AltiumBackend.write`) writes the records of the design's rules (`rulemap.lower`), the rules that a source
  record or the user gave.
  - Of the c0038 rules it writes only what KiCad checks. That is the class clearances and the `All`
    clearance, and none of them when a clearance rule of the design applies to every object, which
    overrides them as an unconditioned KiCad rule does. It writes no class track width and no via size.
  - A build (`from_design` with options) keeps every c0038 rule, because its net classes are the user's.
  - A net class with a value left out is counted `changed` under `netclass`.
- **Rules lacking a limit stay refused.** A rule that gives fewer limits than its record holds is still
  refused (`value-unsupported`), as before c0434. A board or class minimum is never written as a record
  with invented limits.
- **Every loss before consent.** `LossyConversionError` and the Altium writer's `LossyWriteError` list
  every loss that consent would accept. Their messages name the other lost kinds.
- **Rule records through KiCad** (extension, owner's board report). A board taken from Altium to KiCad and
  back lost every record that KiCad has no rule for (Component Height, Silk To Board Region, Minimum Solder
  Mask Sliver, disabled rules, Assembly Test Point Usage, Plane Clearance and Connect, about 16 records),
  wrote the others with generated names (`Clearance_<class>_to_<class>`) and new priorities, and refused
  the Routing Via Style, Width and Hole Size records whose limits KiCad holds in part.
  - The conversion to KiCad writes the board property `Fenolite.Altium.Rules6` (zlib and base64, through
    the shared `backends.kicad.boardcarrier`): every rule record of the source as read, with a hash of each
    rule list of the rules file it gave.
  - The conversion back writes each record whose rule lists are unchanged, or that gave none, as read:
    name, priority, scopes, enabled state and limits. Only the rules no such record accounts for are
    lowered, with the next priority of their kind. Nothing is added: no class rule, no `All` default.
  - A rule of an edited source record that cannot be written is a loss of reason `SOURCE_RULE_LOST`, which
    needs `--allow-lossy`. A rule that only KiCad holds stays a reported loss.

## Capabilities

- `altium-pcb-writer`: "Design rule records", modified; "Source rule records written back", added.
- `design-conversion`: "Lossy conversions need consent", modified; "Rule records through KiCad", added.

## Out of scope

- The Plane Connect and Plane Clearance `All` records of change c0389 (task 2.7). They stand for Altium's
  own default when a stack holds a plane.
- Checking the carried records in KiCad. KiCad keeps the property and does not use it; a record KiCad has no rule for is
  carried, not checked.
- Writing Component Clearance, Silk To Silk Clearance and Differential Pairs Routing records from neutral
  rules. Each needs keys that no neutral rule holds.

## Impact

- `backends/altium/pcbdoc.py` (`PcbDocSpec.class_kinds`), `backends/altium/lower.py`,
  `convert/__init__.py`, `convert/rulecarrier.py` (new), `backends/kicad/boardcarrier.py` (new),
  `convert/to_kicad.py`, `convert/to_altium.py`, `convert/report.py`, `backends/kicad/lowering.py` (`written_names`).
- Docs: `altium.md`, `pcb-copper.md`, `rule-file.md`, `conversion.md`, `kicad/board.md`, `hypotheses.md`, `sources.md` (S-1930, S-1931).
