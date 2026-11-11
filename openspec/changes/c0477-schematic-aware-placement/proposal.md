# Schematic-aware component placement

## Why

A placement can pass courtyard checks and have short airwires while leaving a dense IC without
pad escape or putting a gate drive far from its return. Grid and region strategies seed a board,
and constrained placement searches translations one component at a time. A connectivity-aware
optimizer should choose poses jointly, respect electrical and mechanical intent, and test
strong alternatives against the existing router.

## What changes

- Optimize a selected region or group first, then plan the whole board by functional blocks.
  Generate proposals directly for KiCad and Altium boards. Review and apply on KiCad,
  including on a converted copy with an export back to Altium.
- Interpret resolved schematic connectivity, hierarchy, physical pin-to-pad maps, confirmed roles
  and user intent. Offer reviewable suggestions for decoupling, oscillators, gate drives,
  current sensing, signal chains and power domains.
- Combine hard legality checks, bounded joint search, pin-aware objectives and per-layer demand
  estimates. Refine the shortlist with routing probes on temporary board copies.
- Report alternate poses, per-rule outcomes and blockers. Protect fixed parts and existing
  attached copper. Apply only a selected candidate through a reviewed plan. Preserve the layout
  through rebuild.
- Compare the optimizer with existing placers and authored references using equal routing budgets.
  Include cases where shorter estimated connections produce a worse routed result.

## Capabilities

- New: schematic-aware placement.
- Modified: CLI contract and board viewer.

## Dependencies and sequencing

Reuse constrained placement (c0096), proximity and height rules (c0113/c0140), regions (c0205),
roles and critical routes (c0222/c0244), relative placement and block layouts (c0255/c0271),
the layout lens, and proposal/search/role-cost routing (c0280/c0365/c0366). The bounded local
optimizer comes first. Block floorplanning, solver experiments and viewer integration follow
their proofs. This proposal plans the roadmap's deferred optimizing placer without assigning
a release.

## Non-goals

Schematic rewrites, changing stackup or rules, pin or net swaps, deriving safety distances from
net names, moving attached copper in the first version, direct Altium PCB writes, final routing,
EMC or thermal qualification, and a global optimality guarantee.

## Evidence level required

Authored tests establish INFERRED topology suggestions, search behavior and placement metrics.
The supported KiCad targets must independently verify preserved geometry and checked routed
benchmarks for corresponding KICAD-VERIFIED claims. Provisional routing evidence covers its
declared subjects. Missing electrical, assembly and native evidence stays explicit.

See [design](design.md), [electronic placement rules](engineering-rules.md) and the
[evaluation protocol](evaluation.md).
