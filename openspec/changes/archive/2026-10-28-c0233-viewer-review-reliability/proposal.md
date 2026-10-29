## Why

A delayed background model refinement can replace a more recent live scene. Viewer shortcuts also run while select controls have focus, and the fixed sidebar leaves only 130 pixels for a board in a 390-pixel window. These defects make review less reliable and harder to use.

## What Changes

- Bind each rebuild and background refinement to a generation, with an atomic generation check and scene publication.
- Keep viewer shortcuts out of text/select editing and browser modifier shortcuts.
- Add a collapsible sidebar and compact toolbar on narrow windows, preserving the desktop layout.
- Correct stale viewer documentation about Altium mask openings and Draftsman side views.

## Capabilities

### Modified Capabilities

- `board-viewer`: live-scene publication, keyboard context and narrow-window review.

## Impact

src/fenolite/view/server.py, src/fenolite/view/page.html, focused server/browser tests and docs/viewer.md. No public CLI change, runtime dependency, CAD file edit, or evidence promotion. The parent change records the aggregate changelog and full CI validation.
