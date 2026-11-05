---
topic: board-completion
title: Completing a routed board
summary: Routing stage order and completion facts.
---

# Completing a routed board

## Reviewed routing completion recipe

Development phases differ from board execution order. Start with a placed board and declared or
confirmed roles; inspect inferred roles before accepting them. Apply the stages below in order.
Each writing command first reviews its own dry-run plan, then uses explicit `--confirm --plan ID`.
Proceed only after its receipt and required checks pass. These are separate transactions, not a
whole-flow atomic write. Values and net names below are examples; use the user's requirements.

```fenolite-cmd
fenolite capabilities --json
fenolite roles board --check --json
fenolite route board --router octilinear --roles critical --dry-run --json
fenolite copper board --dry-run --json
fenolite route board --router octilinear --propose --json
fenolite tidy board --nets SIG --prune --gate drc --dry-run --json
fenolite fill board --dry-run --json
fenolite net board SIG --json
fenolite check board --json
fenolite export board -o board/fab --dry-run --json
fenolite render board -o board/views --svg --dry-run --json
```

After proposals, inspect geometry/facts in the viewer and explicitly accept selected IDs with
a reviewed plan before continuing. Optional tidy must be scoped to approved nets and preserves
manual/locked copper; inspect its plan rather than assuming a style change is safe. Refill before
post-fill connectivity and declared electrical/DRC checks. Retain baseline findings and oracle
versions/limits. Physical opens, rejected alternatives, unattempted subjects and unknown checks
are separate facts. A proposal, rejection or unavailable oracle never counts as connected.
Export only after required checks pass; KiCad-to-Altium readback is INFERRED, not native validation.

## What the proposal run reports

`route --propose` adds `result.completion`. `state` is `open` while the board as read has an open
connection and `unchecked` otherwise; `open` is that physical count and `fill` says whether it was
read on the saved fill or a simulated pour. `subjects` sorts every open subject into exactly one of
`proposed`, `unknown` (a timeout, cancellation or search bound stopped it before a candidate or
its facts), `no-candidate` (the search finished empty), `rejected` and `not-attempted` (outside
`--nets`, `--kind` or `--group`). `checks` is `not-run` and `complete` is
always `false`: a proposal, a rejection or a timeout is not a connection. Only the refill and the
checks after it close the board.

Read next: `route-proposals`, `board-review`, `checks`.
