# c0437: check-speed

## Why

`fenolite check` on a medium-large converted board took 2256 s under the heavy-test lock. Profiled on the
KiCad conversion of public row `altium-third-party-pcbdoc-08` (544 parts), the copper check is the largest
stage, and 240 s of its 264 s under cProfile go to the exact distance between an arc and the other shape
(`thick._curved_distance`): every segment of a nearby fill or zone ring is measured with sums of square
roots, also when float bounds already settle it.

## What changes

- `geometry._curved.closest` evaluates exactly only the segments whose float lower bound, less a safe
  slack, is not above the smallest float upper bound plus that slack; the result is unchanged.
- `geometry._curved.within` answers the copper check's threshold question (`thick_touch`,
  `thick_closer_than`) without the distance: it visits only the segments within the threshold box, settles
  a segment by its float bounds when the slack allows, and stops at the first segment within.
- Times of `check --stages copper.clearance` without a profiler, with the same findings (codes, messages
  and locations) before and after: row `-08` (544 parts, 4334 findings) 102.4 s before, 47.8 s after; row
  `-01` (260 parts, 41 findings) 9.6 s before, 7.2 s after on a quiet machine, 34.1 s and 26.9 s under load.

## Not in this change

- The other stages: the KiCad refill and DRC subprocesses, the round trip and the S-expression parser.
- Pairs without an arc, which already use integer arithmetic.
