## Why

The viewer page is one hand-written file, `src/fenolite/view/page.html`: about 188 KB and 2 200 lines of
inline CSS, markup and vanilla JavaScript in one global scope (the board and sheet canvas renderers, a
hand-written WebGL view, the panels, the project review, the catalog dialog, marks, measurement, compare).
Nothing is type-checked, and the four viewer changes of v0.7 (c0243 to c0246) would each add hundreds
of lines to it. Before the visual redesign (c0243, c0244, paused),
the maintainer decided on 2026-10-29 to move the page to TypeScript modules with Preact (MIT) for the UI
panels only, the canvas and WebGL renderers staying hand-written: ported, not rewritten.

## What Changes

- **TypeScript sources** under `viewer/src/`: one module per concern (state, units, scene decoding, the
  board renderer, hit tests, measurement, the 3D view, the sheet renderer, tables, libraries, links, marks,
  SVG and print, the panels and dialogs), type-checked by the TypeScript compiler. The board, sheet and 3D
  renderers keep their code; the Changes, Messages, Findings and Navigator panels are Preact components.
- **One JS bundle and one CSS bundle**, committed under `src/fenolite/view/static/` with the page's markup
  shell. `fenolite.view.export.template()` inlines both into the shell, so the served page and the
  `--export` file are single offline files exactly as before. No CDN, no external URL.
- **No Node for users.** The wheel carries the committed bundle; `pip install fenolite` needs no Node.
  Node 22 is a contributor tool: `viewer/package.json` pins exact versions, `package-lock.json` is
  committed, `node_modules` never is.
- **A deterministic build and its drift check.** `tools/build_viewer.py` runs the build; `--check` rebuilds
  into memory and fails when the committed files differ. The `viewer` CI job runs it. A manifest of source
  and output digests lets a unit test catch a stale or hand-edited bundle on every platform without Node.
- **Notices.** Preact is the only bundled third-party code: its MIT notice heads the bundle and `NOTICE`
  lists it. esbuild and TypeScript are build tools and ship nothing.
- **Behaviour unchanged.** Same ids, classes, shortcuts, globals the tests read, live polling and export;
  the unit tests of the page and the 69 visual tests with their eight screenshot references pass unchanged.
- c0243 and c0244 are re-planned on the module structure (designs and tasks only, requirements kept).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `board-viewer`: MODIFIED "Viewer page" (the page is assembled from the shell and the committed bundles);
  ADDED "Viewer sources" and "Committed viewer bundle".
- `licensing-and-notices`: MODIFIED "NOTICE lists only real derivations" (bundled code is listed).

## Non-goals

- No visual or behavioural change: the redesign is c0243 and c0244.
- No rewrite of a renderer, no new dependency of the Python package, no change of a server route or scene.
- No minification: the bundle stays readable, as the page was.
- c0245 and c0246 code is being written into `page.html` in parallel; the integrator ports it afterwards
  into the places this change prepares.

## Evidence level required

No format fact is involved, so no evidence label changes. Proof is mechanical: the unchanged unit tests of
the page (several run page code under Node), the unchanged visual tests in the pinned Chromium with their
references, the drift check in the `viewer` job, and the manifest test in every `unit` job.

## Impact

- New: `viewer/` (sources, `package.json`, `package-lock.json`, `tsconfig.json`, `build.mjs`),
  `src/fenolite/view/static/` (`page.html`, `viewer.js`, `viewer.css`, `manifest.json`),
  `tools/build_viewer.py`, `tests/unit/view/test_viewer_bundle.py`, a `Makefile` target.
- Changed: `src/fenolite/view/export.py` (`template()`), `.github/workflows/ci.yml` (`viewer` job),
  `.gitignore`, `NOTICE`, `tools/residue/scope.toml`, `docs/viewer.md`, `CONTRIBUTING.md`, the designs and
  tasks of c0243 and c0244. Removed: `src/fenolite/view/page.html`.
- Size: about 3 days.
