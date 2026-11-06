# Design of c0434

## Decisions

1. **Fill a missing limit, do not refuse it.**
   - Every Altium record read holds all its limits (`pcb-copper.md`), so a record without a limit is a form
     Altium has never been seen to write.
   - The missing limit is written so that it bounds nothing a board holds:
     - minimum 0;
     - preferred value as the rule's minimum (its maximum without one), which only steers interactive
       routing;
     - maximum 100 mm, the largest maximum of a public record (3937.0079 mil, S-1930), so the value is one
       Altium has written.
   - The rule is counted `changed` with that reason, so the report and `convert.changed` say it.
   - Fenolite's reader reads the open limit back as a limit. `lift(lower(rules))` therefore equals the
     written rules only for the unchanged ones, and the round-trip test says so.
2. **A via's hole from a hole_size rule.** KiCad has no via drill constraint; its rule set holds the drill
   as `hole_size` on `A.Type == 'Via'`, and has no preferred hole.
   - A `via_diameter` rule without a `via_drill` partner takes the hole limits of the most governing
     `hole_size` rule, looked for in this order:
     1. on the vias of its selector;
     2. of its selector;
     3. on every via;
     4. on every hole.
   - The preferred hole is that rule's minimum.
   - The hole rule still writes its own Hole Size record: it checks the holes in DRC, and the Routing Via
     Style only sets the via used when routing.
   - With no hole rule at all the via rule stays `value-unsupported`, rather than inventing a hole.
3. **The c0424 kinds, written as the public records hold them.**
   - Component Clearance: `GAP`, `COLLISIONCHECKMODE=3`, `VERTICALGAP` equal to `GAP` and
     `SHOWDISTANCES=FALSE`. Nine of the eleven public records hold `VERTICALGAP` equal to `GAP`, and all
     eleven hold mode 3.
   - Silk To Silk Clearance: `SILKTOSILKCLEARANCE`.
   - Differential Pairs Routing: `MAXLIMIT`, `MINLIMIT`, `MOSTFREQGAP`, the 96 per-layer width keys, then
     `MAXUNCOUPLEDLENGTH`.
     - The widths take the governing `track_width` rule on every object, or 0, 0.25 mm and 100 mm.
     - A lone gap rule takes an open uncoupled length.
     - A lone uncoupled rule stays `value-unsupported`, because it would invent a gap.
     - `diff_pair *` is the scope `All`; joined with `and` to a scope, it is that scope. The reader narrows
       the record to pairs again (`read.rules._pairs`).
   - Component Clearance and Silk To Silk Clearance are counted `changed`: Altium measures bodies, not
     courtyards, and splits silk clearance into two kinds.
4. **Every loss in the refusal.** The refusal stays tied to the `refuse` kinds. Its `issues` now hold every
   lost row, in report order, and its message adds "--allow-lossy also loses items of …". The CLI already
   copies a refusal's `issues` into the envelope (`cli/main.py`), so the envelope carries them on a dry run.
