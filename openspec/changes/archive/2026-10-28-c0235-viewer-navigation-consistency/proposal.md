## Why

Browser document loads are asynchronous. A delayed scene, failure or version reply from an earlier selection can replace the document the user selected later. The tree can highlight a schematic while the canvas shows a board, and a stale response can also replace a newer scene in the cache. The server generation guard of c0224 does not guard these browser requests. The first version poll also accepted its version without reloading an older cached scene, leaving that scene stale indefinitely.

## What Changes

- Give each document navigation a generation and publish scenes, empty results and failures only for that navigation.
- Bind version polling to the selected document, navigation and request order; stale replies cannot update status, version or trigger a reload.
- Guard per-document cache publication so an older decode or read cannot replace a newer cached scene.
- Cancel delayed selection actions after navigation, preserving ordinary cross-probe, mark and BOM selection behavior.
- Document the behavior and prove races with deterministic browser tests.

## Capabilities

### Modified Capabilities
- `board-viewer`: asynchronous browser navigation and cache consistency.

## Impact

Viewer page, focused browser tests and viewer documentation. No public CLI, file format, CAD data, runtime dependency or evidence changes. The coordinator records Unreleased and the combined local gate; complete validation remains in CI.
