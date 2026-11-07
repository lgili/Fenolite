# c0384: native identity follow-up after the c0355 re-scope

## Why

On 2026-11-05 the coordinator, on the maintainer's authority, re-scoped c0355: what it proved ships
(the approved TEST-ONLY descriptors with their guards, ledger v5 and the private native-project
context correction), and its descriptor-gated long tail moves here. The long tail could not close
in the 2026-11-05 batch because every remaining step waits for its own coordinator-approved descriptor.

First finding, carried over from c0355 task 4.4: the fresh public RoyalBlue54L-Feather replay
(corpus row kicad-demo-10-0-6-pcb-13, board 535dbe21..., native kicad-cli 10.0.6) still fails at
level 7. Levels 1–6, S and 8 are equal; the derived padvia caches differ in exact geometry, with
source 289 regenerated caches, digest a562fa7965020cc8dfd270a007b7dcf1da04d716c994b7ffeb8a8fb81278ad12,
versus generated 293, digest 4b439125f5f7f38c4fa565299aafcf2a2332a2886730288467ddf06a54e6844c, and the
raw teardrop count is 263 versus 0. The 2026-11-03 production comparison
(c0355 royal-fresh-project-context-proof.json) and the 2026-11-04 replay on 468d8a61
(docs/evidence/public-replays-20261104.json) give the same numbers. The native-project context is
resolved but is not the only cause.

Second finding, carried over from c0355 task 0.4: ledger v5 leaves 10 source PCB Plot numeric
occurrences and 331 of 339 project unknown key paths without an approved role.

## What

Carry c0355 tasks 0.4, 1.0, 1.1, 1.3, 2.1, 2.2, 2.3, 3.1 and 4.4 unchanged in scope and in their gates.
Each step runs only after its descriptor is approved; only public boards are used; no normalization,
renumbering, cache removal, tolerance or acceptance waiver is introduced to reach equality. c0355's
proof files and the branch `codex/cac-royal-identity-copy` stay where they are and are referenced,
not copied.

## Impact

No code, model, public name or evidence level changes with this proposal. A design is written when the
first descriptor is approved.
