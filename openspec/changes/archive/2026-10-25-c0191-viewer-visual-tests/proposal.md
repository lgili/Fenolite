## Why

On 2026-10-25 the maintainer asked for an analysis of the viewer of c0176 to c0180 and of what it lacks to be "super útil" and professional, "principalmente para projetos de altium", then: "escreve as specs e começa pela primeira". This change is item Q-14 of that analysis.

The page has eight unit tests and no test of what it draws. Two errors of c0180 (a sheet upside down, texts
past their boxes) were only seen in a browser review. A professional viewer needs every change to its drawing
checked automatically.

## What Changes

- **Visual regression tests.** Playwright (already in the container image and installable in CI) opens
  exported pages of authored fixtures, one per scene kind (KiCad board, Altium board, Altium sheet, KiCad
  sheet, footprint library, symbol library, Draftsman drawing), at fixed sizes, and compares screenshots with
  committed references within a pixel tolerance.
- **Interaction tests.** Scripted clicks check selection, measurement, unit switch and cross-probe.
- **CI job.** A `viewer` job runs them on Linux; `make check-fast` skips them when Playwright is absent.
- **Update path.** `uv run python tools/update_view_refs.py` rewrites the references after an intended change;
  the diff images are kept as CI artefacts.

## Capabilities

### New Capabilities

- `viewer-visual-tests`: screenshot and interaction tests of the page.

### Modified Capabilities

- None.

## Non-goals

- Pixel-exact references across browsers: one Chromium version, a tolerance.

## Evidence level required

- The references are images of Fenolite's own fixtures; no third-party file is committed.

## Impact

- **New:** `tests/visual/`, `tools/update_view_refs.py`, a CI job in `.github/workflows/`.
- **Changed:** `Makefile`, `CONTRIBUTING.md`.
- **Size:** 3 design-days.
