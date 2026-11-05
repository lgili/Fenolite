# c0388: native Draftsman document after gate G2 failed in c0172

## Why

On 2026-11-04 the coordinator, on the maintainer's authority, decided that gate G2 of c0172 failed: Altium
Designer 24.5.2.23 refused the minimal document FP3 and the shell FP4 that Fenolite's writer made, with
"Value cannot be null. Parameter name: source" (S-1575), and the rebuild of S-1581 gave equal bytes. No
corrected form was known, so no correction round could be made that day, and FP5, the template route,
needs a document template registered in Altium's Preferences, which was not tried. By c0172's Decision 9
and cut order 6 the native `.PCBDwf` was cut from c0172; its reader, census, gated writer and gated build
plumbing shipped.

Finding carried over from c0172: every document that Altium saved in round F0 (S-1421, S-1574) holds 38
root members, and FP3 and FP4 hold 6 of them, a candidate cause of the refusal.

## What

- One correction round first: FP3 and FP4 built again with the root members that the saved documents hold,
  and FP5 tried as a template registered in Preferences; G2 is decided again from that report only.
- Carry c0172 tasks 3.3, 4.1, 4.2, 6.1, 6.2 and 6.3 unchanged in scope and in their gates, with the
  requirements "Fabrication sheet of a Draftsman document", "Assembly sheets of a Draftsman document" and
  "Draftsman scope round trip" that c0172 moved here.
- If no probe opens after the round, route P of c0172's Decision 9 is decided here.

## Amendment (2026-11-05)

The coordinator chose to write the views, tables and dimensions (tasks 4.1 and 4.2) before the correction
round reports, with `draftsman.NATIVE_WRITE` still `False`. Plainly: no output of that code reaches a user
while the gate is off; it is judged only by unit tests against the member rows of round F0 (S-1421), which
say nothing about Altium's acceptance; the FPC correction round still decides the probes, and its result can
force this code to be reworked or removed; and task 6.3, which turns the gate on, still needs FP1 to FP4 to
pass. The requirement "Draftsman native document correction round" says so.

## Impact

No code, public name or evidence level changes with this proposal. `draftsman.NATIVE_WRITE` stays `False`
until FP1 to FP4 pass (task 6.3). c0172's design, Decisions 3 to 9, stays the design of this change; a
design is written here only if the correction round changes it.
