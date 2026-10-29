## Context

- **What exists** on `dev` at `5191911` with the viewer proposals (`d647b54`):
  - `src/fenolite/view/page.html`, 187 671 bytes, 2 182 lines: a `<style>` block (145 lines), the markup of
    the toolbar, side bar, canvas wrapper, project review and catalog dialog, and one `<script>` of about
    1 900 lines of vanilla JavaScript in one global scope.
  - `fenolite.view.export.template()` reads the file; `page()` replaces `/*__DATA__*/null` (the embedded
    project and packed scenes) and `/*__LIVE__*/false`; `embedded()` reads the data back; `server.py` serves
    `page(live=True)`; `catalog.py` and `cmd_view.py` export it.
  - Tests that read the page's source: `tests/unit/view/test_page.py` (ids, function names, code strings),
    and three files that cut code out of the page between markers and run it under Node:
    `test_scene_v1.py` (`// <decodeV1>` … `// </decodeV1>`), `test_filter.py` (`// ---- query (c0187)` …
    `// ---- end query`), `test_edge_measure.py` (`// ---- edge (c0189)` … `// ---- end edge`), and
    `test_page.py::test_units` (`const MIL_MM` … `function fmtPair`, with `let UNIT = (() =>` patched).
  - `tests/visual` (69 tests, eight references in `tests/visual/refs`, 0.1 % tolerance) drives the page in the
    Chromium of Playwright 1.63.0. `harness.js` waits for the globals `linkReady` and `S`; the job scripts
    call page globals (`openDoc`, `find`, `st`, `SCH`, `set3D`…) and one calls `.onclick()` of a row of
    the Marks list (`test_navigation.py`).
- **Constraints**: the core has no runtime dependency; the page loads nothing from the network; an exported
  page works from `file://`; `pip install fenolite` must not need Node; the sdist allowlist is fixed
  (`repo-layout`, "Source distribution contents").
- **Parallel work**: another agent is adding c0245 and c0246 code to `page.html` inside
  `/* c0245 begin */ … /* c0245 end */` and `/* c0246 begin */ … /* c0246 end */` blocks. The integrator
  ports those blocks into modules after this change lands (decision 10).

## Goals / Non-goals

- **Goals:** typed modules with explicit dependencies; Preact for UI panels; a byte-identical, committed
  build; an unchanged page for users and for every existing test.
- **Non-goals:** the proposal's. The renderers (`draw`, `paintCache`, `drawSch`, the WebGL view) are moved
  into modules and given types, not changed.

## Decisions

### 1. Sources at the top level, in `viewer/`

`viewer/` holds `package.json`, `package-lock.json`, `tsconfig.json`, `build.mjs` and `src/`. Keeping the Node
project outside `src/fenolite/` keeps TypeScript sources, `node_modules` and the Node configuration out of the
wheel (hatch ships every file of the package directory) and out of the sdist, whose allowlist is fixed; ruff,
pyright and pytest never walk it. The alternative, `src/fenolite/view/web/`, would ship the sources in the
wheel or need exclusion rules, and would put `node_modules` inside the Python package. The sdist does not
carry `viewer/`: it builds the wheel from the committed bundle, which is all a Python install needs.

### 2. Module layout

`viewer/src/main.ts` imports every module in link order and calls `start()`. Modules (`.ts`, Preact panels
`.tsx`):

| folder | modules | holds |
|---|---|---|
| `core/` | `env`, `dom`, `state`, `font`, `units`, `viewport`, `documents`, `links`, `input`, `start` | the boot flags, `$`/`esc`/`linkify`/`natural`/`download`, the shared state and its setters, the stroke font, mm/mil, the 2D view transform and `fit`, opening documents and the scene cache, deep links, the toolbar and keyboard, start and polling |
| `board/` | `decode`, `scene`, `geometry`, `cache`, `draw`, `diff`, `overlays`, `hit`, `query`, `variants`, `info`, `tabs`, `load` | the compact-scene decoder, unit conversion, arcs, the Path2D caches, the board renderer, compare, analyses, hit tests, the filter language, variants, the info card, layer tabs, `loadBoard` |
| `measure/` | `snap`, `measure`, `edge`, `edge-tool` | snapping, the measurement, the edge-to-edge distance and its tool |
| `three/` | `math`, `view3d` | matrices; the WebGL view, bodies and models |
| `sch/` | `scene`, `draw`, `hit`, `select`, `project-nets`, `load` | the sheet scene, its renderer, hit test, selection, nets across documents, `loadSch` and cross-probing |
| `review/` | `check` | `--check` findings on the drawing |
| `panels/` | `changes.tsx`, `messages.tsx`, `findings.tsx`, `navigator.tsx`, `marks`, `tree`, `review`, `project-review` | the side bar panels |
| `dialogs/` | `catalog-selection` | the catalog dialog |
| `table/`, `library/`, `export/` | `table`, `library`, `svg` | BOM and output-job tables, libraries, SVG and print |
| `vendor/` | `preact.ts` | the vendor chunk's entry |
| `styles/` | `index.css` and the ten files it imports | the stylesheet, split by area, in the original rule order |

`globals.d.ts` declares `EMBED` and `LIVE`, which stay in an inline script of the shell.

### 3. Build: the TypeScript compiler links the app, esbuild bundles Preact and the CSS

`viewer/build.mjs`:

1. Creates one TypeScript program from `tsconfig.json` and fails on any diagnostic (`noEmitOnError`).
2. Emits each module as ES2022 with comments kept, then links them in the order `main.ts` imports them:
   import declarations and `export` keywords are removed by their positions in the module's syntax tree, a
   `// ---- <module>` line separates modules, and the build fails when two modules declare the same
   top-level name or a module declares `preact`.
3. Bundles `vendor/preact.ts` with esbuild as an IIFE that assigns the global `preact`, and
   `styles/index.css` with esbuild's CSS bundler (target `esnext`, nothing lowered).
4. Writes `src/fenolite/view/static/viewer.js` (header, Preact's MIT notice, the vendor chunk, the app),
   `viewer.css`, `page.html` (the shell, copied) and `manifest.json` (decision 8).

esbuild's own bundler is not used for the app modules, for three measured reasons (esbuild 0.28.2): when it
bundles it rewrites top-level `const` and `let` into `var` (`test_units` looks for `const MIL_MM`), it drops
ordinary comments (four tests cut code at comment markers), and it renames a top-level name that collides
across modules while the harness and the job scripts read the page's top-level names as globals. The
compiler's emit keeps declarations, comments and names; the linker keeps the order.

### 4. The page's top level stays its public surface

The linked app is one classic script with `"use strict"`, so every top-level declaration of every module is
a page global, as before: `S`, `st`, `view`, `linkReady`, `openDoc`, `find`, `applyQuery`, `set3D`… The
linker's unique-name rule keeps them unrenamed. A module's top-level code may read only bindings of modules
linked before it (function declarations are hoisted); `env`, `dom` and `state` import nothing.

### 5. Shared state

Read-mostly state is imported (live bindings). A `let` that another module assigns gets a setter in its own
module: `setProject`, `setDoc`, `setS`, `setCtx` and `setP2D` in `core/state`, `setDpr` and `setFitted` in
`core/viewport`, `setLinkReady` in `core/links`, `setLib` in `library/library`. A `let` assigned only by its
own module (`navigation`, the Path2D caches, `VARIANT`, `MARKS`, `PROJ_NET`…) stays there without one. The
compiler refuses an assignment to an import, so none is missed. Objects (`st`, `view`, `SCH`, `V3`, `REVIEW`, `CATSEL`, `TBL`)
stay `const` and are mutated in place, as before.

### 6. Preact for panels only

The entry `vendor/preact.ts` re-exports `h`, `render`, `Fragment` and `Component`; modules use
`import * as preact from "preact"` (types from the package; the import is removed by the linker), and JSX
compiles to `preact.h`. The panels converted are Changes (`buildDiffList`), Messages (`buildMessages`),
Findings (`buildFindings`) and Navigator (`buildNav`): their `build*` functions keep their names and call
`preact.render(<Panel …/>, box)`, producing the same elements, classes, titles and texts; nothing else writes
into those containers (`loadSch` calls `clearFindings()`, an empty render, instead of clearing it). Rows of
different kinds carry different keys, so Preact never reuses one for the other and leaves no attribute behind. Not converted in
this change: Marks (a visual test calls `.onclick()` of its rows, which a Preact listener does not set), the
tree, the virtual lists of the review panels, the project review and the catalog dialog; c0243 and c0244
convert what they redesign. Preact's dist holds five `http://www.w3.org/…` namespace literals; the build
rewrites each into a joined string, as the page's own `SVG_NS`, so the page holds no URL; a different count
fails the build. Canvas and WebGL code never goes through Preact.

### 7. The shell and the Python loader

`static/page.html` is the markup with `<style>/*__CSS__*/</style>`, the inline script
`const EMBED = /*__DATA__*/null;` / `const LIVE = /*__LIVE__*/false;`, and `<script>/*__JS__*/</script>`.
`template()` inlines `viewer.css` and `viewer.js` into it (read once per process); `page()` and `embedded()`
are unchanged, so the served page and the export are one file with no external URL. A bundle that
contained `</script` or `</style` would end its element early; the build refuses one.

### 8. Determinism and the drift check

Exact versions in `package.json` (esbuild 0.28.2, TypeScript 5.9.3, Preact 10.29.8) and
`package-lock.json`, installed with `npm ci`; `engines.node` is `>=22`. The build has no timestamps or
absolute paths and writes LF. `tools/build_viewer.py` runs `npm ci` when `viewer/node_modules` is missing
and then the build; `--check` builds into memory and fails, naming the files, when they differ from the
committed ones. `make viewer` and `make viewer-check` call it; the `viewer` CI job runs `--check` before the
visual tests (Node 22 is set up there). `manifest.json` records the SHA-256 of the sources (every file of
`viewer/src`, `package.json`, `package-lock.json`, `tsconfig.json`, `build.mjs`, in path order, each as path,
NUL, content, NUL) and of each output; `tests/unit/view/test_viewer_bundle.py` recomputes both in Python, so
a source edited without a rebuild, or an output edited by hand, fails every `unit` job, Windows included.

### 9. Licences

Preact (MIT) is the only third-party code in the package's files: `NOTICE` gains its entry and
`viewer.js` starts with its copyright and permission notice (the MIT condition). esbuild (MIT) and
TypeScript (Apache-2.0) run only at build time. `tools/residue/scope.toml` excludes
`viewer/package-lock.json` as it excludes `uv.lock` (hashes and versions of third-party packages only).
The licence inventory of c0220 (`docs/licences.md`, not yet written) should list the packages of
`viewer/package-lock.json` too; c0220's tasks are not edited here.

### 10. Where c0245 and c0246 go

- c0245 (run checks): `review/runs.ts` (the client of `GET /runs`, `POST /run`, `GET /run/<job>`, cancel,
  polling under the navigation guard, the run state), `panels/run-strip.tsx` (the strip under the toolbar,
  Preact), the Run controls in `panels/project-review.ts`, and the Run menu in `core/input.ts` until the
  command registry of c0243 exists.
- c0246 (actions): `actions/actions.ts` (the client of `GET /actions`, plans, confirm, receipts, undo),
  `dialogs/plan-review.tsx` (the modal review of a plan, Preact), `panels/receipts.tsx`.
- Merging: `page.html` is gone on this branch, so a merge reports modify/delete. The integrator takes the
  blocks from the other branch's `page.html`, moves each into its module with the imports the compiler asks
  for, adds new modules to `main.ts`, runs `make viewer` and commits the rebuilt bundle.

### 11. Tests

The existing tests pass unchanged; that is the proof that the port is faithful. New:
`tests/unit/view/test_viewer_bundle.py` (manifest digests; the shell's placeholders; Preact's notice in the
bundle and in `NOTICE`; no `</script` in the bundle). The drift check runs in the `viewer` job.

## Risks / Trade-offs

- **The emitted code is reformatted.** The compiler reprints statements (one per line), so the bundle does not
  read like the old file. Every string a test looks for was checked against the emit.
- **Contributors need Node to change the page.** Only for the viewer; the manifest test says when a rebuild
  is due, and `make viewer` is one command.
- **Two parallel changes edit the removed file.** Decision 10 gives their places and the merge steps.
- **Preact upgrades** may change the namespace literals; the build counts them and fails.
- **c0244 modifies "Viewer page" too.** Its block is rebased on this change's wording and carries the
  scenario "The served page is the assembled page"; c0247 is archived before c0244.

## Open Questions

- Should the sdist carry `viewer/` (a change of the allowlist of `repo-layout`)? This change keeps it out.
