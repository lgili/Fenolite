## 1. Entry

- [x] 1.1 Validate this change and read the page's current chrome in `viewer/src` (the shell's toolbar and side bar, `core/input.ts` with the `keydown` listener, the panels) and the tests that read its ids; check that `make viewer-check` passes. Proof: `~/.npm/_npx/20f2b75ddc8bce88/node_modules/.bin/openspec validate c0300-viewer-shell --strict --no-interactive` (or `npx openspec validate ...`); `uv run pytest tests/unit/view/test_page.py -q -n 2`.

## 2. Tokens and themes

- [x] 2.1 Replace the chrome colours, spacing, radii and type sizes of `viewer/src/styles/` by tokens (`tokens.css`, `core/theme.ts`) with dark and light sets, the `prefers-color-scheme` fallback and the stored choice; keep scene colours untouched (requirement "Interface tokens and themes", scenario "Tokens and contrast"). Proof: `uv run pytest tests/unit/view/test_page.py -k tokens -q -n 2`.

## 3. Command registry and toolbar

- [x] 3.1 Add the command registry (`core/commands.ts`) and drive the existing shortcuts of `core/input.ts` from it with the same context rule; add the palette chord exception (modified requirement "Context-aware viewer shortcuts"). Proof: `uv run pytest tests/unit/view/test_page.py -k registry -q -n 2`; `uv run pytest tests/visual/test_interaction.py -k shortcuts -q` in the `viewer` CI job.
- [x] 3.2 Build the grouped toolbar as Preact components (`panels/toolbar.tsx`, `ui/icons.tsx`, `ui/menu.tsx`, `ui/tooltip.tsx`) with tooltips with shortcuts, the Measure and Export menus, and remove the duplicate Fit and Clear controls (scenario "No duplicate labels"). Proof: `uv run pytest tests/unit/view/test_page.py -k toolbar -q -n 2`; `uv run pytest tests/visual/test_shell.py -k toolbar -q` in the `viewer` CI job.

## 4. Command palette

- [x] 4.1 Add `paletteMatch` (`core/palette-match.ts`, between Node-test markers) and the palette dialog (`dialogs/palette.tsx`) over commands, parts, nets and documents, with the `>`, `@` and `#` prefixes and the shortcut sheet (scenarios "Jump to a part from a text field", "Ranking under Node", "The palette chord in a text field"). Proof: `uv run pytest tests/unit/view/test_page.py -k palette_match -q -n 2`; `uv run pytest tests/visual/test_shell.py -k palette -q` in the `viewer` CI job.

## 5. Side bar, status bar and states

- [x] 5.1 Turn the side bar panels into remembered disclosures with counts (`ui/section.tsx`; the tree, review lists, marks and library list as Preact components, keeping the `.onclick()` of the Marks rows or updating `test_navigation.py` with it), add the sorts of Components and Nets, fold the zero finding groups, and make the project review entry a visible button with its state counts (scenario "Zero groups fold but remain"). Proof: `uv run pytest tests/visual/test_shell.py -k sections -q` in the `viewer` CI job; `uv run pytest tests/visual/test_project_review.py -q` there too.
- [x] 5.2 Rework the status bar (`panels/status-bar.tsx`) and add the "About this document" popover (`dialogs/about.tsx`); remove `gen` (scenario "The digest moves to the popover"). Proof: `uv run pytest tests/visual/test_shell.py -k about -q` in the `viewer` CI job.
- [x] 5.3 Add the loading indicator, the empty-list messages (`ui/states.tsx`), the error card with Retry and the no-viewable-document card (scenario "A failed read can be retried"). Proof: `uv run pytest tests/visual/test_shell.py -k retry tests/visual/test_navigation.py -q` in the `viewer` CI job.

## 6. References and documentation

- [x] 6.1 Regenerate the eight screenshot references and add `kicad_board_light.png` with `uv run python tools/update_view_refs.py` in the `viewer` job's environment; the maintainer reviews the images before they are committed (requirement "Shell references in both themes"). Proof: `uv run pytest tests/visual -q` in the `viewer` CI job on the commit that holds the references.
- [x] 6.2 Update `docs/viewer.md` ("The page", "Review tools", "Units and measurement") for the toolbar groups, the palette, the shortcut sheet, the side bar sections, the status bar and the About popover. Proof: `uv run pytest tests/unit/view/test_page.py tests/unit/view/test_themes.py tests/unit/view/test_viewer_bundle.py tests/unit/agent/test_pages.py -q`; `make check-fast`.

  Completed 2026-11-02: the literal four-module proof passes all 128 cases
  (`test_page.py`, `test_themes.py`, `test_viewer_bundle.py`, `agent/test_pages.py`).
  The documented shell/inspector/layers/3D/unit surfaces remain discoverable and
  root's actual `make check-fast` on `ea762411cbb24bc5f9ba5a16d8b372ae7c720568`
  passes (19564 passed, 55 skipped, exit 0). This closes the documentation proof
  only; task 7.1 still requires the complete exact-head CI result. Existing image
  reference evidence is preserved without regeneration or a new browser claim.

## 7. Closing

- [x] 7.1 Run the tests and the residue scan; the committed bundle is a fresh build. Proof: `uv run python tools/build_viewer.py --check`; `make check-fast`, then the CI jobs of the branch, `viewer` included.
- [x] 7.2 Confirm that no evidence label changes (no format fact is involved). Proof: `uv run python tools/gen_evidence_matrix.py --check`.
- [x] 7.3 Add an entry to `CHANGELOG.md` under `## [Unreleased]` for each closed task. Proof: `uv run pytest tests/unit -k "release_record or changelog" -q -n 2`.

Open on the branch (2026-10-29): 6.1 — the nine references (the eight, and `kicad_board_light.png`) were regenerated with `tools/update_view_refs.py` in this session's Linux container, with Playwright 1.63.0's Chromium and `tests/visual/fonts.conf`, where the unchanged references of `dev` passed pixel for pixel before the change; they wait for the maintainer's review and the `viewer` CI job. 6.2 — `docs/viewer.md` is updated ("The page", "Review tools", "Units and measurement"); its proof `tests/unit -k "docs and viewer"` selects no test, and `make check-fast` is left to the maintainer's machine (AGENTS.md). 7.1 — `tools/build_viewer.py --check` passes; `make check-fast` and the CI jobs are open; only focused checks ran here: ruff check and format of `tests` and `tools`, the residue scan, `tests/unit/view`, `tests/unit/cli/test_view_cmd.py`, `tests/unit/agent`, `tests/consistency`, `tests/unit/test_import_graph.py` and `tests/visual` (88 passed, `FENOLITE_REQUIRE=browser`). The visual harness now opens every page with `colorScheme: dark` unless a job asks for light (Playwright's default is light), so the references show the dark interface as before.

Local reference review, 2026-11-01, source `b02e09fea8145442f0af61f571e58a075385df9e`: exact CI Playwright 1.63.0 / Chromium 153.0.8010.12 ran 104 visual cases successfully. The literal reference generator regenerated all eleven PNGs byte-identically. All eleven were inspected: readable toolbar/dock, distinct light/dark chrome, located net emphasis, schematic/library/document views and role hatches. Bundle freshness passed after correcting a local dependency-cache setup error. No reference changed. The final UI union, complete fast gate and exact published-head CI remain unproved here.

The corrected documentation/control proof passed 123 cases on 2026-11-01. The documented toolbar, palette, shortcut sheet, panel sections, About, dock, layer groups, emphasis and unit rows were checked against the observed controls. Task 6.2 stays open for its required complete fast gate.


Published viewer proof, 2026-11-01: exact commit `96d687d18450f429bcc57b60087f9e6f43dfb707`, [CI run 41359100272, viewer job 125005408616](https://github.com/lgili/Fenolite/actions/runs/41359100272/job/125005408616), completed successfully: the bundle freshness step exited 0 and all 104 visual cases passed in 155.64 seconds. The eleven PNG digests are identical across the reviewed `b02e09fea8145442f0af61f571e58a075385df9e`, that published commit and model0 cut `dbfd6fc36e18300c4a9aef1983f7130fea4e3b71`. Together with the recorded delegated image review and regeneration, this closes only task 6.1. The complete fast gate, documentation gate and remaining CI tasks stay open.


## Scoped implementation closure — 2026-11-03

The maintainer clarified that problematic geometry was already outside this
closure CI batch before the run. Close only this specification’s implementation
on tested source 985f59a1d01a612b2eac0219243199896c24075a and reviewed
archival documentation. Run 41708879698 remains FAILURE: the27known c0332
geometry failures are DEFERRED_NOT_PASSED, not passed tests. KiCad9 and all
five unit jobs succeeded. The relevant KiCad10 module results are inferred
from complete unfiltered collection and the exhaustive -ra non-pass report.
Explicitly contracted unsupported-target skips remain skips; no nominal
PASSED line or green KiCad10 job is claimed.

`scoped-ci-985f59a1.json` binds the exact tests, explicit KiCad9 positive
lines, complete log hashes, reused fast proof and existing scoped records.
The isolated runtime/tests/tools/configuration remain byte-identical to985;
this does not validate later CAC runtime, close c0355 or replace subsequent
integration CI. Existing authored/native/default-map proofs and limitations
remain intact. No suite, native CAD test or CI rerun was started for archive.

Entry refresh: previously implemented prerequisites are now archived in the
required order: no literal prior archive requirement. Existing APIs and reviewed normative
unions were checked against the current living text; no runtime change or
external publication was needed. Contracted native9/10 unsupported-target
skips remain skips and are explicitly retained in the portable receipt.

The existing viewer job126171394431 passed bundle freshness and104visual
cases on source985. All eleven PNG references exactly match the prior
reviewed/published/source985 maps, preserving the dated delegated image
inspection without inventing a new approval from automation. Unit, viewer
and applicable MCP/DCO jobs are recorded individually in the portable proof.
No bundle, PNG, runtime, assertion or measurement was regenerated here.
The missing three native action CI cases ofc0303 and six real variant views
ofc0305 remain separate open requirements; neither is closed by this record.
