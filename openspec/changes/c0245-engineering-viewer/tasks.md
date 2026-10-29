## 0. Entry check

- [x] 0.1 Read `openspec list` and the living specs this change touches (`board-viewer`, `viewer-visual-tests`, `cli-contract`, `net-roles`). Under this task, write the date and the base commit, and record:
  - whether c0243 and c0244 are merged, and the settled names of corridors (`role.corridor.<group>`, `role-corridor:<group>:<net>` or the maintainer's `role.corridor.<group>.<net>`), of the reply fields of `copper` and of `route --roles critical`, and the `--rip` inverse of a group. Phase 9 uses the settled names;
  - which open change holds a delta of "Viewer page", "Context-aware viewer shortcuts" or "Review in narrow windows". If one was archived, regenerate the MODIFIED blocks from the living text;
  - that S-0920 to S-0933 are still the rows this proposal registered, and that no other branch used S-0934 to S-0949;
  - the maintainer's answers to the open questions of `design.md`.

  Proof: `openspec validate c0245-engineering-viewer --strict --no-interactive`; `uv run pytest tests/unit/test_provenance.py tests/unit/test_hypotheses_register.py -q`.

  Note (2026-10-29, base `dedad4c7` of `origin/dev`, branch head `3db3446d`):
  - c0243 and c0244 are not merged; both are open on their branches (`63597a79`, `186e397c`). The corridor name is settled for both as `role.corridor.<group>.<net>` (the coordinator's message of 2026-10-29; c0244's design, decision 9, and its README row). The viewer matches the prefix `role.corridor.`. The reply fields of `copper` and `route --roles critical` and the `--rip` inverse of a group are not settled, so phase 9 waits for both merges.
  - No open change on `dev` or any branch holds a delta of "Viewer page", "Context-aware viewer shortcuts" or "Review in narrow windows"; the MODIFIED blocks stand as written.
  - S-0920 to S-0933 are this proposal's rows; no branch uses S-0934 to S-0949. (Task 4.1 added S-0934 and S-0935 inside that free block.)
  - The maintainer approved the change on 2026-10-29 and accepted every recommended answer of open questions 1 to 8; they are recorded as decisions in `design.md`, "Open Questions". Implementation runs in parallel with c0243 and c0244.
- [x] 0.2 Add the authored stress fixture `tests/_stress_board.py` (decision 7) and the budget harness, and measure today's page on it in the `viewer` job. Record the p95 frame, cursor and open times under this task. Where today misses a CI budget of `design.md`, record the replacement budget (no worse than today, and 30 % better at task 6.4). Proof: `uv run pytest tests/visual/test_workbench.py -k budget_baseline -q` in the `viewer` job on the pushed commit.

  Note (2026-10-29): the stress board (2 000 pads, 10 000 tracks, 1 500 vias, 40 zone fills; 23 584 scene primitives) measured on today's page, canvas 840 x 606 px:
  - `viewer` job, commit `bbbcdab3` (run 40863901856): open 333 ms; pan/zoom frame p95 75.5 ms (median 74.7); cursor move p95 0.10 ms; 0 board paints during 200 moves.
  - this machine (Chromium of Playwright 1.56.1): open 366–384 ms; frame p95 82.4–86.5 ms; cursor p95 0.10 ms.
  - The frame budget of 50 ms is missed today. Replacement budget for task 6.4: p95 ≤ 52.9 ms in the `viewer` job (30 % under 75.5 ms), measured at the same canvas size of 840 x 606 px (the budget test widens its viewport by the docks). The cursor (≤ 4 ms) and open (≤ 2.5 s) budgets stand; the cursor figure is low today because the page draws no crosshair, so task 6.1 holds the crosshair to it.

## 1. UI sources

- [x] 1.1 Split `page.html` into `src/fenolite/view/ui/` (decision 13) and assemble it in `fenolite.view.export.page()`. The assembled page must equal today's `page.html` byte for byte (scenario "Assembly from the UI sources"). Proof: `uv run pytest tests/unit/view/test_ui_sources.py tests/unit/view/test_page.py -q`; `uv run pytest tests/visual -q` in the `viewer` job with the eight references unchanged.

  Note (2026-10-29): `page.html` was cut at its section boundaries into 29 parts under `src/fenolite/view/ui/` (`page/`, `css/`, `core/`, `canvas/`, `panels/`, `workspaces/`, `shell/`), joined in the order of `export.PARTS` by `template()`. Before the file was removed, the join equalled it byte for byte (SHA-256 `18a8e038…722d` both). `page.html` is no longer in the repository. Proof passed: the unit tests here, and the `viewer` job on `db8de372` (run 40866191266) with the eight references unchanged; the `wheel` job shows the parts ship in the package.
- [x] 1.2 Add the command registry and the source checks: no `alert`, `confirm` or `prompt`, and every menu entry has a registry id (M4, M9). Proof: `uv run pytest tests/unit/view/test_ui_sources.py -k "modal or registry" -q`.

  Note (2026-10-29): `ui/shell/registry.js` holds the commands (id, label, menu, group, keys, `when`, `run`), the keymap lookup, the key dispatcher with sequences, and an undo history. The keydown chain of `commands.js` became registered commands with the same keys and order, so the interaction tests pass unchanged. The review-mark note is typed in an inline form, a deleted mark comes back with Ctrl+Z, and a link that the clipboard refuses is shown in Properties for copying: no `alert`, `confirm` or `prompt` remains. The catalog selection of c0240 keeps its modal dialog (a separate catalog mode, named in the test). Proof passed.

## 2. Workbench shell

- [x] 2.1 Add the title line, the menu bar generated from the registry (APG menubar), the toolbar with its grid, unit, view and net drop-downs and Fenolite's own icons, and the status bar with its seven fields (requirement "Workbench shell"). Proof: `uv run pytest tests/visual/test_workbench.py -k shell -q`.

  Note (2026-10-29): `ui/shell/menubar.js` (menu bar from the registry, APG keyboard: F10, Alt with the underlined letter, arrows, Enter, Escape), `ui/shell/icons.js` (Fenolite's own 16-pixel icons), `ui/shell/workbench.js` (toolbar decorated from the registry, Net and Grid drop-downs, title line, status bar with x/y, dx/dy, grid, net, layer, tool and lowest evidence, dot grid, crosshair on an overlay canvas) and `ui/css/workbench.css`. The status bar names the reading backend and the checking tool with its version (from the evidence label, such as `kicad-cli 10.0.7`); Fenolite's own version is in its tooltip only, so a version bump does not change the screenshots. Proof passed (`test_shell`, and `test_menu_runs_its_command`).
- [x] 2.2 Add the docks: tabbed groups, title bars, pin and close, keyboard splitters, moves by drag and by panel menu. Wrap today's panels in them unchanged. Proof: `uv run pytest tests/visual/test_workbench.py -k docks -q`; `uv run pytest tests/visual/test_interaction.py tests/visual/test_navigation.py tests/visual/test_project_review.py -q`.

  Note (2026-10-29): `ui/shell/docks.js`: tabbed groups with blue title bars, collapse on the title, close, a panel menu (move to another dock or a new group), drag of a tab or title onto a group, keyboard splitters between groups and on each dock's inner edge. Today's panels became Projects, PCB, Navigator, Library, Layers, Findings, Changes, Marks, Notes, Shortcuts, Properties (the former info card) and Messages (a table, replacing the sidebar list). The modal prompts of review marks and links were replaced in task 1.2. Proof passed: `test_docks`; `test_interaction.py`, `test_navigation.py`, `test_project_review.py` (the desktop-width assertions of `test_interaction.py` and `test_catalog.py` now expect the right dock beside the canvas, scenario "Desktop remains unchanged").
- [x] 2.3 Add layout persistence: browser storage per workspace, `fenolite.view_layout.v0` save and read, Reset Layout (scenario "A layout survives a reload"). Proof: `uv run pytest tests/visual/test_workbench.py -k layout -q`; `uv run pytest tests/unit/view/test_layout.py -q`.

  Note (2026-10-29): layouts per workspace in `localStorage` (`fenolite.view.layout.<workspace>`), Window ▸ Save Layout As, Load Layout, Reset Layout, and `fenolite.view.layout.parse_layout` / `read_layout` for the coming `--layout` (task 7.4). Proof passed (`test_layout` in both files).
- [x] 2.4 Add the narrow drawer (MODIFIED "Review in narrow windows", all three scenarios). Proof: `uv run pytest tests/visual -k narrow -q`.

  Note (2026-10-29): at 760 px or below every dock renders into the drawer (`#side`), the right and bottom docks are hidden, the canvas keeps the width. Proof passed: `-k narrow` (`test_narrow_drawer_holds_every_dock`) and the three narrow-window tests of `test_interaction.py`.
- [x] 2.5 Add floating panel windows in served mode at `/panel/<name>`, sharing the selection. Proof: `uv run pytest tests/unit/view/test_server.py -k panel -q`; `uv run pytest tests/visual/test_workbench.py -k float -q`.

  Note (2026-10-29): Float in a Window (served pages only) opens `/panel/<name>?doc=<id>`, which the server sends to `/#float=<name>&doc=<id>`; that page shows the panel alone, follows the documents of the main window and the shared net, and the panel returns to its dock when its window closes. Proof passed.
- [x] 2.6 Rebaseline the eight references once with `tools/update_view_refs.py`. Review each difference image and attach them to the pull request. Proof: `uv run pytest tests/visual -q` in the `viewer` job on the pushed commit.

  Note (2026-10-29): the eight references were rewritten once with `tools/update_view_refs.py` after the shell of tasks 2.1 to 2.5. Each drawing is unchanged; the frame around it changed (title line, menu bar, icon toolbar, left, right and bottom docks, blue status bar), so 69 % to 99 % of the pixels differ. Before, after and difference images, reviewed one by one: `c0245-shots/before/`, `c0245-shots/after/`, `c0245-shots/diff/` in the session's scratch folder (no pull request is opened for this branch, by the coordinator's instruction). The default dark theme tokens were settled for contrast first (task 5.1's checks), so later tasks do not change these eight references. The first push (`fd6b60e2`, run 40869216292) showed that references written by this machine's Chromium (Playwright 1.56.1) differ from the pinned Chromium of the `viewer` job on `altium_sheet` by 0.22 % (antialiased sheet borders), so the references are the eight screenshots of that run, taken in the pinned Chromium as `ci.yml` requires; on this machine `altium_sheet` stays 0.22 % off, the other seven match. Proof passed: the `viewer` job on `69feb4e2` (run 40870001982) with these references.

## 3. Selection, messages, provenance

- [x] 3.1 Add one selection store, read and written by the canvas, panels, layer tabs, status bar, address and served windows (scenario "Five ways to one net"). Proof: `uv run pytest tests/visual/test_workbench.py -k selection -q`.

  Note (2026-10-29): `ui/shell/selection.js`: `selectionState()` reads the one selection (document, net, part, finding) by name; every way of selecting ends in a draw, and the draw calls `selectionChanged()`, which updates the status bar, the Net drop-down, the highlight of the Components and Nets lists, the Messages rows and a live region. A finding that names a net selects that net too. The test uses c0222's `bad` buck (fixture `buck_page`) and a finding given to the Messages panel, since role findings arrive in phase 7. Proof passed.
- [x] 3.2 Add the Messages panel: columns, filter, explain text, links in both directions, findings without a position (scenario "Both directions"). Proof: `uv run pytest tests/visual/test_workbench.py -k "linked or explain" -q`.

  Note (2026-10-29): the Messages table takes rows from every registered source (check findings now); a row frames its finding on its layer (the time from the click to the framed view is checked under 100 ms), a marker within 9 px of a click selects its row, a `?` button shows the code's `fenolite explain` text below the row (embedded by `view --check` as `check.explain`), and a code without one names the command to run. Proof passed (`test_linked`, `test_explain`, and `test_check_findings_carry_their_explanations` of `test_view_cmd.py`).
- [x] 3.3 Add `data-source` and `data-evidence` on every displayed value, and the lowest evidence level in the status bar (scenario "No value without a source", once phase 7 exists; before that, on the check overlay fixture). Proof: `uv run pytest tests/visual/test_workbench.py -k "provenance or evidence" -q`.

  Note (2026-10-29): `showInfo(html, prov)` marks every text with a digit in Properties with `data-value`, `data-source` and `data-evidence` (by default the document and the backend that read it, with its evidence; a finding passes its stage and evidence), and the message and source cells of Messages carry theirs. The status bar shows the lowest evidence level of the document and the findings shown, and the checking tool with its version. Tested on the KiCad board with given findings; the scenario on the roles workspace follows in phase 7. Proof passed (`test_provenance`).

## 4. Keymaps

- [x] 4.1 Record the reserved keys of the pinned Chromium and of current Firefox and Safari in `docs/viewer.md`, each with how it was observed. Proof: `uv run pytest tests/unit/view/test_keymap.py -k reserved -q`.

  Note (2026-10-29): the list is `reserved` of `ui/shell/keymaps.js` (read by `fenolite.view.keymap` as JSON), recorded in `docs/viewer.md`, "Keys the browser keeps", from Chrome's (S-0934) and Safari's (S-0935) documented shortcuts. It could not be observed: synthetic key events in the pinned Chromium reach the page for every key. Firefox's list was not consulted (its help page did not load); a check of Firefox and Safari in real use is left to the maintainer. Proof passed.
- [x] 4.2 Add the keymaps `fenolite`, `altium` (sequences) and `kicad`, each binding traced to S-0920, S-0921 or "Fenolite's choice"; the `fenolite.view_keymap.v0` file; `--keymap`. Proof: `uv run pytest tests/unit/view/test_keymap.py -q`; `uv run pytest tests/visual/test_workbench.py -k keymap -q`.

  Note (2026-10-29): `altium` binds V,F and V,D (fit) and X,A (clear the selection) from S-0921; `kicad` binds ` (highlight the net under the cursor), ~ (clear), N and Shift+N (grid), Alt+1 and Alt+2 (fast grids, values Fenolite's choice) from S-0920; each binding names its source in the Keyboard panel. `--keymap fenolite|altium|kicad|FILE` reaches the page as `settings.keymap` (exported pages and `/project.json`); a bad file is `FEN-3004`, a missing name `FEN-3001`. Tools ▸ Keymap switches and is kept in the browser. Proof passed (`test_keymap.py`, `test_workbench.py -k keymap`, `test_view_cmd.py -k keymap`).
- [x] 4.3 Add the focus rules through the keymap (MODIFIED "Context-aware viewer shortcuts", both scenarios) and the Keyboard panel. Proof: `uv run pytest tests/visual/test_interaction.py -k shortcut -q`; `uv run pytest tests/visual/test_workbench.py -k keyboard_panel -q`.

  Note (2026-10-29): the dispatcher of `registry.js` runs a Ctrl, Meta or Alt chord only when the active keymap binds it (scenario "An unbound combination passes through", `test_interaction.py`). The Keyboard panel (Tools ▸ Keyboard Preferences) lists every command with its keys and where they come from, captures new keys (Enter keeps, Escape cancels, Backspace unbinds), refuses a browser key, names conflicts, saves the keymap file and resets. A command search (Ctrl+K) runs any command by name. Proof passed (`-k shortcut` selects the focus tests of `test_interaction.py`; `-k keyboard_panel`, `-k command_search`).

## 5. Themes

- [x] 5.1 Add the chrome themes `dark`, `light` and `contrast` as tokens, and the contrast test (`H-G-WB-CONTRAST`). Proof: `uv run pytest tests/unit/view/test_themes.py -k contrast -q`.

  Note (2026-10-29): the tokens of `dark`, `light` and `contrast` are in `ui/css/workbench.css`; View ▸ Theme switches, the choice is kept in the browser, and a first visit follows the reader's `prefers-color-scheme` (open question 8). Overrides for the light and contrast themes are scoped to those themes, so the dark references are unchanged; the harness now emulates a dark scheme, as the references were drawn dark. Contrast measured by `test_contrast`: dark text pairs ≥ 4.55:1 (muted on the current tab, the lowest) and controls ≥ 3.51:1; light and contrast pass the same checks. Proof passed.
- [x] 5.2 Author the light variants of the document palettes (Fenolite's own values) and the role palette with glyphs and hatches, and run the colour-blind test with the simulation that task 0.1 settled (`H-G-WB-CVD`). Proof: `uv run pytest tests/unit/view/test_themes.py -k cvd -q`.

  Note (2026-10-29): `ui/shell/themes.js` holds the role palette for dark and light canvases, a glyph and a hatch per role, and the light variant of a board palette (Fenolite's rule: a light background and board, each layer darkened to lightness 0.22–0.42; sheets keep their paper, the sheet workspace turns light grey). The role colours were searched for separation and checked by `test_cvd` with the severity-1.0 matrices of S-0928 recorded in the test: worst pairwise CIEDE2000 20.9 on the dark canvas and 15.8 on the light one (criterion 12), every colour at 3:1 or more on its canvas. Renders of the light and contrast themes reviewed: `c0245-shots/themes/`. Proof passed.

## 6. Performance

- [x] 6.1 Add the overlay canvas for the crosshair, hover, rubber band and measure line (`H-G-WB-CURSOR`). Proof: `uv run pytest tests/visual/test_workbench.py -k cursor -q`.

  Note (2026-10-29): `#ov` holds the crosshair, the cursor readout and the measurement in progress (hover mark, rubber line, readout); `drawMeasure(g, preview)` draws the placed points on the board and the cursor's part on the overlay, so moving the mouse while measuring paints no board layer (`test_cursor`: 0 paints over 50 moves). The page has no rubber-band selection, so there is none to move. Proof passed.
- [x] 6.2 Add the layer bitmap cache with composited panning. Proof: `uv run pytest tests/visual -q` (references unchanged); `uv run pytest tests/visual/test_workbench.py -k frame -q`.

  Note (2026-10-29): instead of one bitmap per layer, the page keeps one bitmap of the last full frame (`FRAME`): a pan by drag or a zoom by wheel moves and scales it at once (`drawInteractive`), and the board is drawn in full 120 ms after the last event. Programmatic draws stay full draws, so screenshots are unchanged; after the rest the board equals a fresh draw pixel for pixel (`test_frame`). Selecting a finding uses the same path to frame it. Proof passed: `tests/visual` (references unchanged; `altium_sheet` 0.22 % off on this machine only, task 2.6) and `-k frame`.
- [x] 6.3 Add the spatial index for hit testing. Proof: `uv run pytest tests/visual/test_workbench.py -k hit -q` (the index picks what the full scan picks; a static check of the sources could not show that, so the proof runs in the browser); `uv run pytest tests/visual/test_interaction.py -q`.

  Note (2026-10-29): `pick()` uses a 2 mm grid per layer, built on the first click after a scene loads, and tests the candidates in the order of the full scan, so the result is the same; `pickScan()` keeps the scan for the comparison. On the stress board: 500 points, no difference, the grid faster than the scan. Proof passed.
- [ ] 6.4 Measure the budgets in the `viewer` job (`H-G-WB-FRAME`, `H-G-WB-CURSOR`, `H-G-WB-OPEN`) and on the maintainer's PC, and record both under this task. Proof: `uv run pytest tests/visual/test_workbench.py -k budget -q` in the `viewer` job on the pushed commit.

  Note (2026-10-29): the `viewer` job on 8ae0c27e measured: open 416 ms (budget 2.5 s); pan and zoom event p95 1.5 ms, median 1.4 ms, no board painted (budget 52.9 ms, from 75.5 ms before the workbench); the full draw when the hand rests p95 77.6 ms (not budgeted); cursor p95 0.10 ms, no board painted (budget 4 ms); a Messages click 8.3 ms (budget 100 ms); 23 584 primitives on 840 x 606 px. Recorded in `docs/hypotheses.md`. Still open: the measurement on the maintainer's PC, which this session cannot reach (`uv run pytest tests/visual/test_workbench.py -k budget -q -s` prints the line there).

## 7. Net Roles workspace (read-only)

- [x] 7.1 Add `fenolite.view.roles.roles_payload`, `/roles/<id>.json`, its cache, and its embedding in exports with `--workspace roles` (scenario "The numbers are the command's"). Proof: `uv run pytest tests/unit/view/test_roles_payload.py -q`.

  Note (2026-10-29): the import rules keep `fenolite.view` from importing the roles or the commands, so `cmd_view.roles_payload` runs `roles BOARD --check` in process and read-only and `fenolite.view.roles.payload` turns its envelope into `fenolite.view_roles.v0` (the reply's roles with a state, groups, classes, measures, limits, findings and evidence unchanged; the explanations of its codes; the locked tracks, arcs and vias by the scene's labels); the page joins it to the scene (pads to polygons, findings to places). `roles --check` now replies with `limits`: each limit in force for each role and group, with its unit, origin and source. Served pages read `/roles/<id>.json`, built again when the board file changes; exported pages embed the data of every board with `--workspace roles`. The requirement text of "Roles payload" was corrected to this split. Proof passed.
- [x] 7.2 Add the Net Roles panel (Nets, Groups, Classes) and Properties (Net, Role, Measures) (scenarios "The workspace of the bad buck" and "The switch node explained"). Proof: `uv run pytest tests/visual/test_roles_workspace.py -k "panels or properties" -q`.

  Note (2026-10-29): `ui/workspaces/roles.js`: the Net Roles panel (Nets with glyph, role, current, confidence and state; Groups; Classes; a filter; Ctrl+click selects several nets for the writes of phase 8), the role Properties with the tabs Net (Group), Role and Measures (each measure with its analysis and copper, each limit with its source, the router phases with phase 0 from the check and phases 2 and 1 "not run"), the role findings in Messages and as diamond markers, the Roles view drop-down (role colours, confirmation, layer colours), Window ▸ Workspace and Roles ▸ Net Roles Workspace. The scenario "The switch node explained" uses the inferred gate net `GH` and the hot loop `hot_SW`, since `SW` is declared by the `bad` buck's script. Proof passed.
- [ ] 7.3 Add the overlays Loop areas, Measures, Corridors, Locked copper and Role copper, and the role highlight (scenario "Hot loop on the copper"). Proof: `uv run pytest tests/visual -k roles_workspace -q`.
- [x] 7.4 Add `--workspace`, `--roles`, `--layout` and `result.roles` to `cmd_view` (scenario "Roles summary for an agent"). Proof: `uv run pytest tests/unit/cli/test_view_cmd.py -k "workspace or layout" -q`.

  Note (2026-10-29): `fenolite view --workspace board|roles`, `--roles FILE`, `--layout FILE` (`fenolite.view.layout`, `FEN-3004`/`FEN-3001`) and `--edit` (with `--serve` only, `FEN-2001`); `--workspace roles` on a document that is not a board is `FEN-2001`; `--workspace roles --json` adds `result.roles` (counts by state, findings by severity, groups, locked items) and writes nothing. The agent guide's commands page was regenerated. Proof passed.

## 8. Role writes and undo

- [x] 8.1 Add `fenolite roles --forget` and `--forget-group` (scenario "Forget after accept"). Proof: `uv run pytest tests/unit/cli/test_roles_cmd.py -k forget -q`.

  Note (2026-10-29): `--forget NET[,NET]` drops the stored role and current of each net, `--forget-group NAME` a stored group decision (confirmed or rejected), both through the plan protocol and writing only the role document; forgetting a declared net is `FEN-2001` naming the script, an unknown group `FEN-2001`; no `roles.*` code was added. The agent guide's commands page was regenerated. Proof passed.
- [x] 8.2 Add `--edit`, the server routes `/roles/plan` and `/roles/confirm` with the review header, one staged plan per page, and a refusal of plans the server did not stage (scenarios "Confirm a role from the page", "Read-only without edit" and "Edit needs the server"). Proof: `uv run pytest tests/unit/view/test_role_writes.py -k "confirm or readonly" -q`; `uv run pytest tests/unit/cli/test_view_cmd.py -k edit -q`.

  Note (2026-10-29): `POST /roles/plan`, `/roles/confirm` and `/roles/discard` take the same guards as `/marks` (the server's own host and origin, `X-Fenolite-Review: 1`, JSON, at most the mark size) and answer 403 without `--edit`. A plan takes only the options of `fenolite.view.roles.WRITE_FLAGS` (no path, no other option), runs `fenolite roles BOARD … --check --dry-run` in process and stages its `plan_id`, one per board; a confirm runs `--confirm --plan` with the staged plan only, else 409 `FEN-4002`. The plan reply adds the SHA-256 of each file as it is now, the finding counts after, and the inverse (8.4). The workspace's data is built again when the board or its role document changes. Proofs passed.
- [x] 8.3 Add the Pending panel, Apply and Discard, `FEN-4002` with Review again, and receipts logged in Messages. Proof: `uv run pytest tests/visual/test_roles_workspace.py -k pending -q`.

  Note (2026-10-29): the role actions (Confirm, Set, Reject, Forget, Current, Confirm all high; Confirm, Reject, Forget for a group) sit above the Net Roles table and in the Roles menu; each plans on the server and the Pending panel (bottom dock) shows the command, the file it writes with its size and SHA-256, each net's role before and after, and the findings before and after; Apply (or Enter) writes, Discard drops the plan on the server too. A refused confirm shows the server's message with Review again, Apply disabled. Each receipt is listed in the panel and in Messages (source `fenolite roles`, code `roles.write`, SHA-256). Without `--edit`, and in an exported page, the actions read "copy only" and give the exact `fenolite roles … --dry-run --json` line. Proof passed (a page served with `--edit` on a copy of the bad buck: plan, Apply, undo, a plan dropped behind the page's back, and the exported page's command line).
- [x] 8.4 Add undo and redo with the inverse of each write kind (scenarios "Undo restores the bytes" and "Changed file stops undo"). Proof: `uv run pytest tests/unit/view/test_role_writes.py -k undo -q`.

  Note (2026-10-29): the server computes the inverse with the plan, from the stored roles before the write (`fenolite.view.roles.inverse`): an inferred net is forgotten; a net confirmed from an inference is forgotten and accepted again, with its current; a net set by hand is set back with its working voltage, sensitivity and current; an inferred group is forgotten, a confirmed one forgotten and accepted again, a rejected one rejected again; `--accept-all` is undone net by net and group by group. Ctrl+Z plans the inverse steps and applies them at once only while the role document's SHA-256 is the receipt's, else the plan waits in Pending with a note; Ctrl+Y redoes with the original options. The history is the page's and lost on reload, as the tooltips of Undo and Redo in the Edit menu say. The test applies each of the nine write kinds on a copy of the bad buck, undoes it and checks the role document's bytes, and redoes it to the same bytes; the bad buck's build writes the role document, so the "created the file" case does not arise there. Proof passed.

## 9. Phases (after c0243 and c0244 merge)

- [ ] 9.1 Accept `copper` and `route --roles critical` replies in `--report`, bound to the board's SHA-256, and add the phase status (scenario "Phase 0 only", and the Limited case). Proof: `uv run pytest tests/visual/test_roles_workspace.py -k phases -q`; `uv run pytest tests/unit/view/test_project_review.py -k report -q`.
- [ ] 9.2 Draw corridors, locked copper, role copper and dashed proposals from the settled names (scenario "Corridors and locks"). Proof: `uv run pytest tests/unit/view/test_roles_payload.py -k corridor -q`.
- [ ] 9.3 Accept a proposal through its own command under the Pending flow, only if c0244 gives an exact inverse. Otherwise record the cut under this task. Proof: `uv run pytest tests/unit/view/test_role_writes.py -k proposal -q`.

## 10. Other workspaces

- [ ] 10.1 Move the sheet, library, drawing, BOM and output job, compare and project review views onto the shell's panels, the shared selection and the Messages panel, with their references rebaselined after review. Proof: `uv run pytest tests/visual -q` in the `viewer` job on the pushed commit.

## 11. Optional native window (cut first)

- [x] 11.1 Add the extra `view-app` (pywebview, imported lazily) and `--serve --window`. With the extra missing, the reply is exit 6 with its hint. Add its line to `docs/viewer.md`, `docs/cli-contract.md` and the agent guide page `commands` (AGENTS.md rule 6). `pyproject.toml` `dependencies` stays empty. Proof: `uv run pytest tests/unit/cli/test_view_cmd.py -k window -q`; `uv run pytest tests/unit/test_pyproject_invariants.py tests/unit/test_no_copyleft_deps.py -q`.

## 12. Closing

- [ ] 12.1 Add the visual references of "Workbench references" with `tools/update_view_refs.py`, reviewed, and the determinism check (`H-G-WB-STABLE`). Record the size of the assembled page (at most 120 KB more than at task 1.1). Proof: `uv run pytest tests/visual -q` in the `viewer` job on the pushed commit.
- [x] 12.2 Docs:
  - `docs/viewer.md`: rewritten around the workbench (menus, docks, layouts, keymaps with their sources, themes, Messages, the Net Roles workspace, writes and undo, budgets);
  - `docs/roles.md`: the workspace and `--forget`;
  - `docs/cli-contract.md`: the view options, `result.roles` and the roles options.

  Proof: `uv run pytest tests/unit/test_provenance.py tests/unit/cli -k "contract or view or roles" -q`.
- [x] 12.3 Agent guide (AGENTS.md rule 6):
  - on the page `commands`, a tested line for `view --workspace roles --json`, and one for `roles --forget`, each with a `fenolite-cmd` block;
  - on `board-review`, the review loop "roles in the workspace, confirm through a plan".

  Then run `uv run python tools/gen_agent_guide.py`. Proof: `uv run pytest tests/unit/agent -q`; `uv run python tools/gen_agent_guide.py --check`.
- [x] 12.4 Residue: every new `.py` starts with its SPDX and copyright lines, the fixtures carry the authored-for-Fenolite line, and no vendor icon, colour file or layout is present. Proof: `make residue`.
- [ ] 12.5 Run `make check-fast` and the focused tests of the touched files, then push the batch and confirm the required CI jobs, `viewer` included, on the exact commit (AGENTS.md rule 4; no full suite on the maintainer's machine). Proof: `make check-fast`, and the required jobs green on the exact commit.
- [ ] 12.6 Evidence: the six `H-G-WB-*` hypotheses in `docs/hypotheses.md` with their measurements; S-0920 to S-0935 cited from a new `src/fenolite/view/PROVENANCE.md` (the package has none today) and from `docs/viewer.md`; the evidence matrix regenerated. Proof: `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_provenance.py -q`; `uv run python tools/gen_evidence_matrix.py --check`.
- [ ] 12.7 Add an entry under `## [Unreleased]` in `CHANGELOG.md`, only after `0.7.0.dev0` has opened. The v0.6 guard requires `[Unreleased]` to be empty while `0.6.0` is cut and not published. Proof: `uv run pytest tests/unit -k changelog -q`; `uv run pytest tests/unit/test_release_record_v06.py -q` until 0.6.0 is published.


## Continuation evidence (2026-10-30)

- 7.3: downloaded `viewer-differences` from the branch's latest pre-continuation run 40884483891,
  SHA b7f6f08985dbb92c9033067e392bdac51639416f. Reviewed `roles_workspace.png` and copied the CI
  Chromium screenshot unchanged into refs. Existing overlays are retained. Browser behaviour proofs
  pass locally; the macOS pixels differ from CI fonts, so the checkbox awaits the pushed viewer proof.
- 10.1: Project Review now occupies a movable dock; comparison and recorded operation findings use
  Messages. Sheet findings clear sheet selection; library items and table rows enter the selection
  store. Reviewed existing/new screenshots; the checkbox awaits the complete viewer proof in CI.
- 11.1: proof passed: three window CLI tests (serve required, missing extra, server/window lifecycle),
  pyproject and copyleft invariants, and pyright. `view-app` is optional and imported only for `--window`.
  The test host exercises lifecycle; no platform-engine rendering claim is made.
- 12.1: authored the six workbench views, including stronger role hatches; reviewed the local renders.
  CI-font references and the whole visual proof remain to be adopted on the pushed SHA. Independent
  contexts check PNG equality. The assembly budget is tested against task 1.1's 187,671 exact bytes.
- 12.2: contract/view/roles proof passed, 123 tests; docs now cover the workbench and options.
- 12.3: generator and tested command lines updated, including workspace/role-file/layout/keymap/edit/window
  and forget/group. Generated commands inventory already exceeds 12 KB on this branch; c0256 owns its
  split on a separate branch, intentionally not copied here. Full agent proof remains under validation.
- 6.4 remains open: maintainer PC measurement is unavailable here; existing CI measurements are retained.
- Phase 9 remains open: c0244 is in dev, c0243 is not; no dev merge was performed to bypass that dependency.
- 12.7 remains open as requested: no changelog entry until dev is merged into this branch and its release
  guard permits it. This explicit deferral overrides the usual per-change Unreleased update for this batch.

- 12.2/12.3/12.4 proofs (2026-10-30): 123 contract/view/roles tests passed; the complete focused
  agent suite passed 101 tests; guide generation `--check` passed. Residue found 0 hits in 4,533
  scanned files. The optional native dependency remains isolated in its extra. The six comment
  delimiters used by the decoder/query/edge unit oracles are preserved in the compact sources.
- Quick iteration note (2026-10-30): an initial 4-worker run was interrupted after code changes and
  is not a pass. The next reached 15,320 passes / 42 skips but found six failures: the capabilities
  extra allowlist and comment delimiters used by five JS oracle tests. It too was stopped for repair;
  no interrupted run authorizes a push. A fresh complete gate is required after the focused repairs.
