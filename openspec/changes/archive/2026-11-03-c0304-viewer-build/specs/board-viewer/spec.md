## MODIFIED Requirements

### Requirement: Viewer page
`fenolite.view.export.template()` SHALL give one HTML file with inline styles and scripts and no external URL, assembled from the committed shell and bundles of `src/fenolite/view/static/`, that draws a scene in 2D (canvas) and 3D (WebGL) with the project tree, layer tabs, Top and Bottom views, highlight, search, measurement, overlays and notes; `page(tree, scenes)` SHALL embed a tree and its scenes into it.
- The page MUST read a scene embedded (export) or from the routes of "Live server".
- Texts MUST be drawn in Fenolite's own stroke font.

#### Scenario: Standalone page round-trips
- **GIVEN** the tree and the scene of `two_layer.kicad_pcb`
- **WHEN** `uv run pytest tests/unit/view/test_page.py` exports the page and reads the embedded JSON back
- **THEN** the JSON equals the scene, and the page holds no `http://` or `https://` URL

#### Scenario: The served page is the assembled page
- **GIVEN** the committed shell, `viewer.js` and `viewer.css`
- **WHEN** `uv run pytest tests/unit/view/test_viewer_bundle.py -k assembled` builds `page(live=True)`
- **THEN** the page holds the CSS bundle inside its `<style>` element and the JS bundle inside its last `<script>` element, and no placeholder of the shell is left

## ADDED Requirements

### Requirement: Viewer sources
The page's code SHALL be TypeScript modules under `viewer/src`, type-checked by the TypeScript compiler, with Preact used only for UI panels and the canvas and WebGL renderers written by hand. The linked script MUST keep each module's top-level names as page globals, and the build MUST fail on a type error or on a top-level name that two modules declare.

#### Scenario: A name declared twice fails the build
- **GIVEN** a module of `viewer/src` that declares a top-level `function draw()` beside the board renderer's
- **WHEN** `uv run python tools/build_viewer.py --check` runs
- **THEN** it exits non-zero, names `draw` and both modules, and writes nothing

#### Scenario: Panels render through Preact
- **GIVEN** the committed `viewer.js`
- **WHEN** `uv run pytest tests/unit/view/test_viewer_bundle.py -k preact` reads it
- **THEN** the Preact vendor chunk assigns the global `preact` and the Messages, Changes, Findings and Navigator panels call `preact.render`

### Requirement: Committed viewer bundle
The wheel SHALL carry the built bundle, so installing Fenolite needs no Node. The build MUST give the same bytes on every run; `tools/build_viewer.py --check` SHALL fail when the committed files differ from a fresh build, and a unit test SHALL fail, without Node, when the recorded digests of the sources or of the outputs do not match the files.

#### Scenario: A stale bundle fails without Node
- **GIVEN** a file of `viewer/src` edited after the last build
- **WHEN** `uv run pytest tests/unit/view/test_viewer_bundle.py -k manifest` runs on a machine without Node
- **THEN** the test fails and says to run `make viewer`

#### Scenario: The viewer job rebuilds
- **GIVEN** the `viewer` job of `.github/workflows/ci.yml` with Node 22
- **WHEN** it runs `uv run python tools/build_viewer.py --check` before the visual tests
- **THEN** the step passes only when a fresh build equals the committed `page.html`, `viewer.js`, `viewer.css` and `manifest.json`

#### Scenario: The wheel holds the bundle and no sources
- **WHEN** `uv build` builds the wheel and its file list is read
- **THEN** it holds `fenolite/view/static/viewer.js`, `viewer.css`, `page.html` and `manifest.json`, and no file of `viewer/`
