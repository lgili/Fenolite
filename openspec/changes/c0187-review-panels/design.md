## Context

- **Request.** P1-7 of the analysis of 2026-10-25.
- **What exists.** `find()` by reference or net, the board Properties (c0176, c0179), the schematic
  Navigator (c0177).

## Goals / Non-Goals

**Goals**
- See the proposal, "What Changes".

**Non-Goals**
- See the proposal.

## Decisions

1. The query grammar is Fenolite's: `key:value` terms joined by spaces (and), `|` (or), `-` (not), `*` and `?`
   wildcards, quoted values. It runs on the scene, so boards of both tools behave alike.
2. Panels are lazy lists (virtual scrolling) to keep 10 000 nets responsive.

## Risks / Trade-offs

- **Scale.** S-0187 has 1 000+ nets; panels must render in under 100 ms (measured in task 2.1).
