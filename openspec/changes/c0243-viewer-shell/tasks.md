## 1. Entry

- [ ] 1.1 Validate this change and read the page's current chrome in `viewer/src` (the shell's toolbar and side bar, `core/input.ts` with the `keydown` listener, the panels) and the tests that read its ids; check that `make viewer-check` passes. Proof: `~/.npm/_npx/20f2b75ddc8bce88/node_modules/.bin/openspec validate c0243-viewer-shell --strict --no-interactive` (or `npx openspec validate ...`); `uv run pytest tests/unit/view/test_page.py -q -n 2`.

## 2. Tokens and themes

- [ ] 2.1 Replace the chrome colours, spacing, radii and type sizes of `viewer/src/styles/` by tokens (`tokens.css`, `core/theme.ts`) with dark and light sets, the `prefers-color-scheme` fallback and the stored choice; keep scene colours untouched (requirement "Interface tokens and themes", scenario "Tokens and contrast"). Proof: `uv run pytest tests/unit/view/test_page.py -k tokens -q -n 2`.

## 3. Command registry and toolbar

- [ ] 3.1 Add the command registry (`core/commands.ts`) and drive the existing shortcuts of `core/input.ts` from it with the same context rule; add the palette chord exception (modified requirement "Context-aware viewer shortcuts"). Proof: `uv run pytest tests/unit/view/test_page.py -k registry -q -n 2`; `uv run pytest tests/visual/test_interaction.py -k shortcuts -q` in the `viewer` CI job.
- [ ] 3.2 Build the grouped toolbar as Preact components (`panels/toolbar.tsx`, `ui/icons.tsx`, `ui/menu.tsx`, `ui/tooltip.tsx`) with tooltips with shortcuts, the Measure and Export menus, and remove the duplicate Fit and Clear controls (scenario "No duplicate labels"). Proof: `uv run pytest tests/unit/view/test_page.py -k toolbar -q -n 2`; `uv run pytest tests/visual/test_shell.py -k toolbar -q` in the `viewer` CI job.

## 4. Command palette

- [ ] 4.1 Add `paletteMatch` (`core/palette-match.ts`, between Node-test markers) and the palette dialog (`dialogs/palette.tsx`) over commands, parts, nets and documents, with the `>`, `@` and `#` prefixes and the shortcut sheet (scenarios "Jump to a part from a text field", "Ranking under Node", "The palette chord in a text field"). Proof: `uv run pytest tests/unit/view/test_page.py -k palette_match -q -n 2`; `uv run pytest tests/visual/test_shell.py -k palette -q` in the `viewer` CI job.

## 5. Side bar, status bar and states

- [ ] 5.1 Turn the side bar panels into remembered disclosures with counts (`ui/section.tsx`; the tree, review lists, marks and library list as Preact components, keeping the `.onclick()` of the Marks rows or updating `test_navigation.py` with it), add the sorts of Components and Nets, fold the zero finding groups, and make the project review entry a visible button with its state counts (scenario "Zero groups fold but remain"). Proof: `uv run pytest tests/visual/test_shell.py -k sections -q` in the `viewer` CI job; `uv run pytest tests/visual/test_project_review.py -q` there too.
- [ ] 5.2 Rework the status bar (`panels/status-bar.tsx`) and add the "About this document" popover (`dialogs/about.tsx`); remove `gen` (scenario "The digest moves to the popover"). Proof: `uv run pytest tests/visual/test_shell.py -k about -q` in the `viewer` CI job.
- [ ] 5.3 Add the loading indicator, the empty-list messages (`ui/states.tsx`), the error card with Retry and the no-viewable-document card (scenario "A failed read can be retried"). Proof: `uv run pytest tests/visual/test_shell.py -k retry tests/visual/test_navigation.py -q` in the `viewer` CI job.

## 6. References and documentation

- [ ] 6.1 Regenerate the eight screenshot references and add `kicad_board_light.png` with `uv run python tools/update_view_refs.py` in the `viewer` job's environment; the maintainer reviews the images before they are committed (requirement "Shell references in both themes"). Proof: `uv run pytest tests/visual -q` in the `viewer` CI job on the commit that holds the references.
- [ ] 6.2 Update `docs/viewer.md` ("The page", "Review tools", "Units and measurement") for the toolbar groups, the palette, the shortcut sheet, the side bar sections, the status bar and the About popover. Proof: `uv run pytest tests/unit -k "docs and viewer" -q -n 2`; `make check-fast`.

## 7. Closing

- [ ] 7.1 Run the tests and the residue scan; the committed bundle is a fresh build. Proof: `uv run python tools/build_viewer.py --check`; `make check-fast`, then the CI jobs of the branch, `viewer` included.
- [ ] 7.2 Confirm that no evidence label changes (no format fact is involved). Proof: `uv run python tools/gen_evidence_matrix.py --check`.
- [ ] 7.3 Add an entry to `CHANGELOG.md` under `## [Unreleased]` for each closed task. Proof: `uv run pytest tests/unit -k "release_record or changelog" -q -n 2`.
