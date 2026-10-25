## Why

On 2026-10-25 the maintainer asked for an analysis of the viewer of c0176 to c0180 and of what it lacks to be "super útil" and professional, "principalmente para projetos de altium", then: "escreve as specs e começa pela primeira". This change is item P1-7 of that analysis.

An Altium user reviews a board through panels: the PCB panel's Nets and Components lists, the PCB Filter,
"Find Similar Objects", the Properties of a part with all its parameters, and a highlight mode that dims what
is not selected. The viewer has a search box, a click, and a short Properties panel.

## What Changes

- **Nets and Components panels** for boards: every net with its pad count and routed length, every part with
  its footprint, value, side and parameters; a filter on each; a click selects and zooms.
- **Filter.** A small query (`net:GND`, `ref:R*`, `footprint:0402*`, `layer:"Top Layer"`, `side:bottom`,
  `value:10k`) that selects and highlights; "Find similar" fills it from the selection.
- **Highlight mode.** Dim (Altium's default), mask (others hidden) or normal, with `Shift+C` to clear.
- **Full parameters.** The Properties of a part show every parameter the file holds (Altium component
  parameters, KiCad fields), with links for URL-valued parameters.

## Capabilities

### New Capabilities

- `review-panels`: the Nets and Components panels, the filter query, Find similar, highlight modes and full parameters.

### Modified Capabilities

- None.

## Non-goals

- Altium's full query language.
- Editing parameters.

## Evidence level required

- Routed length is computed from the scene's tracks and arcs of the net (Fenolite's computation); parameters
  are as the readers give them.

## Impact

- **New:** `tests/unit/view/test_filter.py` (the query parser under Node).
- **Changed:** `view/scene.py` (parameters, lengths), `view/page.html`, `docs/viewer.md`.
- **Size:** 4 design-days.
