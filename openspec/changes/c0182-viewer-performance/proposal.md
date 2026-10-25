## Why

On 2026-10-25 the maintainer asked for an analysis of the viewer of c0176 to c0180 and of what it lacks to be "super útil" and professional, "principalmente para projetos de altium", then: "escreve as specs e começa pela primeira". This change is item P0-2 of that analysis.

The largest public Altium board of the corpus (S-0187: 544 parts, 8 355 tracks, 1 770 vias) takes 12.7 s to
become a scene and gives 5 MB of JSON. `--serve` builds every document again on each open, and `--export`
embeds the scene of every document of the project at once. A project of several such boards is slow to open
and gives a page too large to send.

## What Changes

- **Scene cache.** Scenes are cached by the SHA-256 of their input files and Fenolite's version, under
  `.fenolite/view-cache/` of the project (or the user cache folder with `--cache user`). A cached scene is
  reused when every input hash matches.
- **Lazy documents.** `--serve` sends the tree first and each scene when its document is opened. `--export`
  gains `--docs ID,...` to embed a subset, and embeds scenes gzip-compressed and base64-encoded, decoded in the
  page with `DecompressionStream`.
- **Compact scene.** Board primitives are written as flat integer arrays per layer, with a string table for
  labels; the page decodes them into its caches. The scene schema becomes `fenolite.view_scene.v1`; `v0` is
  still read.
- **Measured budget.** A test fixes the build time and the scene size of an authored large board, and the
  corpus test records S-0187's numbers.

## Capabilities

### New Capabilities

- `viewer-performance`: the scene cache, the lazy loading, the compact encoding and the budgets.

### Modified Capabilities

- `cli-contract`: ADDED "View command caches scenes".

## Non-goals

- A WebGL 2D renderer: the canvas renderer stays, with its caches.
- Incremental rebuilds of one changed layer.

## Evidence level required

- Budgets are measured, not labelled: the test records numbers on the CI runner, and the corpus test the
  numbers on S-0187 (cached, heavy row).

## Impact

- **New:** `src/fenolite/view/cache.py`, `tests/unit/view/test_cache.py`, `tests/unit/view/test_scene_v1.py`.
- **Changed:** `view/scene.py`, `view/export.py`, `view/server.py`, `view/page.html`, `cli/cmd_view.py`,
  `docs/viewer.md`, `docs/cli-contract.md`.
- **Size:** 4 design-days.
