# c0408: KiCad's net spelling for pins named like their number and for sheet-path nets

## Why

c0384 finding 1.4 (2026-11-05): the build of the public flat_hierarchy demo (KiCad 9.0.9.1 demos) fails
KiCad's own parity test against the schematic the build writes beside the board. `pcb drc
--schematic-parity` (10.0.6) reports 67 `net_conflict`, in two groups:

- (a) 56 pads of pins on no net whose pin name equals the pin number. KiCad names such a pin like a pin
  without a name (`unconnected-(J1-Pad1)`; S-1490, `eeschema/sch_pin.cpp` at 9.0.9.1 and 10.0.6, read for
  facts only; probe `sch-unconnected-samename` = `absent` on both majors), while
  `netnames.unconnected_name` writes `unconnected-(J1-1-Pad1)`.
- (b) 11 pads on 4 nets named by a local label of a child sheet. KiCad names them with the raw slashes of
  the sheet path (`/pic_programmer/VPP_ON`); the board writer writes every `/` of a created net as
  `{slash}` (`{slash}pic_programmer{slash}VPP_ON`), which is right only for a slash of a label text.

This is a build bug, so it is its own change; c0384 keeps the fidelity work and its task 1.4 points here.
The coordinator approved both fixes on 2026-11-05, with (b) on the board side only: the schematic
generator's files belong to the readable-schematic change c0406 and are not edited.

## What

- (a) `netnames.unconnected_name` treats a pin name equal to the pad number as no name. Every caller
  (the generator's `pad_nets`, the drawn lowering, the own netlist) follows through the one function.
- (b) The build of a drawn schematic gives each circuit net that the drawing names by a local or
  hierarchical label the spelling KiCad gives it (`/<sheet names>/` with raw slashes, then the label text
  with `{slash}`), kept as the existing `stored` pair of the net's `kicad` bag, which
  `pcb.stored_net_name` already writes first. The spelling is read from what the drawn lowering already
  produces (the written sheets, resolved by `drawn.resolve_sheets`); no generator file changes.
- Proof: an authored kicad-needed test on a flat_hierarchy-shaped case (sheet-path nets on a child sheet,
  a part with pins named like their numbers left open) whose built board passes `pcb drc
  --schematic-parity` with no item, with a control that respells one net and is reported.

## Impact

- Board and project texts of builds whose drawn nets are named by local or hierarchical labels and whose
  code names are the sheet-path names change spelling; builds of pins named like their number change net
  names. The design lists every golden or snapshot that changes.
- No public name, command argument or `FEN-` code changes. `lens.build.sheet_spellings` is added to the
  module's `__all__`; `drawn_netlist_issues` returns the spellings as a third item.
- Evidence: the S-1490 fact row and `H-K-SCH-UNCONNECTED` stop saying netnames does not apply the rule.
