# c0401: fidelity census follow-up after c0278

## Why

c0278 shipped the corpus round-trip test, its ratchet (`tests/kicad/fidelity/accepted.toml`) and the
zone-outline probe. Its strict census of 2026-11-04 (`docs/evidence/fidelity.md`, "Strict census —
2026-11-04") left rows that are not a measured zero count. The coordinator, on the maintainer's
delegation of 2026-11-04, closed c0278 on its own proofs and moves these rows here:

- four compared rows whose differences have no attribution yet: `kicad-demo-10-0-6-pcb-14`
  (5:track-width=4), `kicad-demo-9-0-9-1-pcb-01` (7:opaque-count=1, 8:render-pixels=1),
  `kicad-demo-9-0-9-1-pcb-02` (7:opaque-count=1, 7:zone-field=1) and `kicad-demo-9-0-9-1-pcb-05`
  (7:graphic-missing=5). `kicad-demo-10-0-6-pcb-13` (RoyalBlue) already belongs to c0384;
- rows refused before comparison: imports `FEN-5001` (10.0.6 pcb-01, 07, 11, 17) and `FEN-3004` (10.0.6 pcb-05),
  `verify-source` `FEN-3004` (10.0.6 pcb-09);
- the two heavy rows skipped by the census (10.0.6 pcb-06 and pcb-18).

Decision recorded with this change: `H-K-FID-ZONE-OUTLINE` targets KiCad 10.0.x only. `kicad-cli pcb upgrade`
exists in 10.0 and not in 9.0 (`H-K-FMT-RESAVE`), so the 9.0.x half of c0278 task 6.1 cannot be measured
by the probe and is dropped, not deferred.

## What

Attribute each listed difference to Fenolite, to KiCad or to the input, with its evidence; fix the
Fenolite ones in their own changes; turn every row into a measured `[[row]]` or a documented refusal.
No tolerance, normalization, level subset or acceptance waiver is added to reach a zero count.

## Impact

No code, model, public name or evidence level changes with this proposal. A design is written when the
first attribution is made.
