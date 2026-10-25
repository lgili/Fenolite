## Context

- **Request.** Q-14 of the analysis of 2026-10-25.
- **What exists.** Chromium and Playwright in the container; the screenshot scripts of the c0177 to c0180
  reviews (scratch, not committed).

## Goals / Non-Goals

**Goals**
- See the proposal, "What Changes".

**Non-Goals**
- See the proposal.

## Decisions

1. Fixtures are authored in `tests/data/` and exported with `fenolite view --export`.
2. Comparison: per-pixel difference over a 2-level threshold, at most 0.1 % of pixels may differ.
3. Fonts: the page uses system fonts; the CI image pins a font package so text renders the same.

## Risks / Trade-offs

- **Flakiness** from fonts and GPU; the job runs headless with software rendering and a pinned Chromium.
