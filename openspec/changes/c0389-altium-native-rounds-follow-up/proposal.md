# c0389: Altium native rounds follow-up after the 2026-11-05 review

## Why

On 2026-11-05 the coordinator, under the maintainer's directive of 2026-11-04, decided that a recorded
Claude-agent run in Altium Designer 24.5.2.23, made at the maintainer's request, satisfies a
"Maintainer, in Altium Designer" task when its proof criteria pass as written. The open Altium tasks were
reviewed against the agent runs S-1570 to S-1589. Two passed and were ticked in their own changes: c0166 3.5
(the planted DRC and both clearance-matrix requests) and c0180 2.4a (the external comparison packet). For
c0177, c0180 and c0186 the coordinator accepts a public project in place of the maintainer's own, provided the
comparison criteria pass.

The other tasks did not pass: a criterion failed or a step was not run. Each one's exact blocker is written
under the source task and repeated here. The main blockers are these:

- K5.6 of Part S fails, so `kit verify` judges `H-A-SLOT-KIT` fail.
- K6 `kit verify` exits 5: M2 at P3 and P8, and dead copper on `P5_NONET`.
- Part Q: Q8 fails, Q9 passes in part, and Q3 was not run.
- Part J: `remap_layer` and `set_rule` fail, and J33 was not run.
- Part T: T6 exists only for PADSTACK, and no source has a `connect` pad.
- The acceptance-tree graduation lacks the six-layer stack, the rule kinds, a K1–K8 kit run and exact-source CI.
- The viewer comparisons differ on the title block, the drawing views, the BOM and the variant marks.

## What

Carry the open tasks (c0092 5.3 6.2, c0160 5.3, c0166 2.1 3.1 3.2 3.3 3.4, c0168 5.2, c0173 2.4 7.4 8.3, c0215 7.4, c0241 1.2 4.2 6.2, c0177 2.4, c0180 2.4, c0186 2.2) unchanged in scope, proof and gates. Each source box is ticked "Moved to c0389"
and keeps its history. No run is repeated until green, and no code changes to make a step pass. A failure stays
recorded as a result.

## Impact

No code, model, public name, gate or evidence level changes with this proposal. `CUTOUT_REGIONS` and
`EMBEDDED_ARRAYS` stay off (`CUTOUT_REGIONS` meets its S3–S5 condition, but the coordinator keeps it off until a K5 round
passes as a whole), and every hypothesis row keeps its level. A design is written when the first moved
task is taken up.
