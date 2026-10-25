## Context

- **Request.** P2-10 of the analysis of 2026-10-25: "conferir uma mudança feita por agente".
- **What exists.** `fenolite diff` (record and tree views), the board and sheet scenes, overlays (c0176).

## Goals / Non-Goals

**Goals**
- See the proposal, "What Changes".

**Non-Goals**
- See the proposal.

## Decisions

1. The difference is computed on scenes, not files, so it works for every format the viewer reads.
2. A moved part is one change, not a removal and an addition (as `diff` counts it).
3. The page shows NEW with the overlay over a dimmed board; `X` hides it. Showing OLD itself would embed a second
   scene; the removed primitives drawn in magenta give what a reviewer needs from OLD.
4. The list groups what belongs together: a part added or removed whole is one line, a part whose own
   primitives changed is one line with the counts, a via's copper and hole are one line. On two public
   revisions of S-0175 this gives 66 lines for 40 additions, 17 removals, 6 changed parts and 3 zones.
5. `--compare` runs in `cmd_view` on the cached scenes; `--serve` compares again when the document is saved.
   The agent guide's generated page leaves out the type "string" of arguments (the head says so), to make room
   for this change's lines in the guide's budget.

## Risks / Trade-offs

- **Noise.** Refilled zones change every fill polygon; zone fills are compared by area and net, not by
  vertex, and reported as one change per zone.
