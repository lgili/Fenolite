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
  - S-0920 to S-0933 are this proposal's rows; no branch uses S-0934 to S-0949.
  - The maintainer approved the change on 2026-10-29 and accepted every recommended answer of open questions 1 to 8; they are recorded as decisions in `design.md`, "Open Questions". Implementation runs in parallel with c0243 and c0244.
- [ ] 0.2 Add the authored stress fixture `tests/_stress_board.py` (decision 7) and the budget harness, and measure today's page on it in the `viewer` job. Record the p95 frame, cursor and open times under this task. Where today misses a CI budget of `design.md`, record the replacement budget (no worse than today, and 30 % better at task 6.4). Proof: `uv run pytest tests/visual/test_workbench.py -k budget_baseline -q` in the `viewer` job on the pushed commit.

## 1. UI sources

- [ ] 1.1 Split `page.html` into `src/fenolite/view/ui/` (decision 13) and assemble it in `fenolite.view.export.page()`. The assembled page must equal today's `page.html` byte for byte (scenario "Assembly from the UI sources"). Proof: `uv run pytest tests/unit/view/test_ui_sources.py tests/unit/view/test_page.py -q`; `uv run pytest tests/visual -q` in the `viewer` job with the eight references unchanged.
- [ ] 1.2 Add the command registry and the source checks: no `alert`, `confirm` or `prompt`, and every menu entry has a registry id (M4, M9). Proof: `uv run pytest tests/unit/view/test_ui_sources.py -k "modal or registry" -q`.

## 2. Workbench shell

- [ ] 2.1 Add the title line, the menu bar generated from the registry (APG menubar), the toolbar with its grid, unit, view and net drop-downs and Fenolite's own icons, and the status bar with its seven fields (requirement "Workbench shell"). Proof: `uv run pytest tests/visual/test_workbench.py -k shell -q`.
- [ ] 2.2 Add the docks: tabbed groups, title bars, pin and close, keyboard splitters, moves by drag and by panel menu. Wrap today's panels in them unchanged. Proof: `uv run pytest tests/visual/test_workbench.py -k docks -q`; `uv run pytest tests/visual/test_interaction.py tests/visual/test_navigation.py tests/visual/test_project_review.py -q`.
- [ ] 2.3 Add layout persistence: browser storage per workspace, `fenolite.view_layout.v0` save and read, Reset Layout (scenario "A layout survives a reload"). Proof: `uv run pytest tests/visual/test_workbench.py -k layout -q`; `uv run pytest tests/unit/view/test_layout.py -q`.
- [ ] 2.4 Add the narrow drawer (MODIFIED "Review in narrow windows", all three scenarios). Proof: `uv run pytest tests/visual -k narrow -q`.
- [ ] 2.5 Add floating panel windows in served mode at `/panel/<name>`, sharing the selection. Proof: `uv run pytest tests/unit/view/test_server.py -k panel -q`; `uv run pytest tests/visual/test_workbench.py -k float -q`.
- [ ] 2.6 Rebaseline the eight references once with `tools/update_view_refs.py`. Review each difference image and attach them to the pull request. Proof: `uv run pytest tests/visual -q` in the `viewer` job on the pushed commit.

## 3. Selection, messages, provenance

- [ ] 3.1 Add one selection store, read and written by the canvas, panels, layer tabs, status bar, address and served windows (scenario "Five ways to one net"). Proof: `uv run pytest tests/visual/test_workbench.py -k selection -q`.
- [ ] 3.2 Add the Messages panel: columns, filter, explain text, links in both directions, findings without a position (scenario "Both directions"). Proof: `uv run pytest tests/visual/test_workbench.py -k "linked or explain" -q`.
- [ ] 3.3 Add `data-source` and `data-evidence` on every displayed value, and the lowest evidence level in the status bar (scenario "No value without a source", once phase 7 exists; before that, on the check overlay fixture). Proof: `uv run pytest tests/visual/test_workbench.py -k "provenance or evidence" -q`.

## 4. Keymaps

- [ ] 4.1 Record the reserved keys of the pinned Chromium and of current Firefox and Safari in `docs/viewer.md`, each with how it was observed. Proof: `uv run pytest tests/unit/view/test_keymap.py -k reserved -q`.
- [ ] 4.2 Add the keymaps `fenolite`, `altium` (sequences) and `kicad`, each binding traced to S-0920, S-0921 or "Fenolite's choice"; the `fenolite.view_keymap.v0` file; `--keymap`. Proof: `uv run pytest tests/unit/view/test_keymap.py -q`; `uv run pytest tests/visual/test_workbench.py -k keymap -q`.
- [ ] 4.3 Add the focus rules through the keymap (MODIFIED "Context-aware viewer shortcuts", both scenarios) and the Keyboard panel. Proof: `uv run pytest tests/visual/test_interaction.py -k shortcut -q`; `uv run pytest tests/visual/test_workbench.py -k keyboard_panel -q`.

## 5. Themes

- [ ] 5.1 Add the chrome themes `dark`, `light` and `contrast` as tokens, and the contrast test (`H-G-WB-CONTRAST`). Proof: `uv run pytest tests/unit/view/test_themes.py -k contrast -q`.
- [ ] 5.2 Author the light variants of the document palettes (Fenolite's own values) and the role palette with glyphs and hatches, and run the colour-blind test with the simulation that task 0.1 settled (`H-G-WB-CVD`). Proof: `uv run pytest tests/unit/view/test_themes.py -k cvd -q`.

## 6. Performance

- [ ] 6.1 Add the overlay canvas for the crosshair, hover, rubber band and measure line (`H-G-WB-CURSOR`). Proof: `uv run pytest tests/visual/test_workbench.py -k cursor -q`.
- [ ] 6.2 Add the layer bitmap cache with composited panning. Proof: `uv run pytest tests/visual -q` (references unchanged); `uv run pytest tests/visual/test_workbench.py -k frame -q`.
- [ ] 6.3 Add the spatial index for hit testing. Proof: `uv run pytest tests/unit/view/test_ui_sources.py -k hit -q`; `uv run pytest tests/visual/test_interaction.py -q`.
- [ ] 6.4 Measure the budgets in the `viewer` job (`H-G-WB-FRAME`, `H-G-WB-CURSOR`, `H-G-WB-OPEN`) and on the maintainer's PC, and record both under this task. Proof: `uv run pytest tests/visual/test_workbench.py -k budget -q` in the `viewer` job on the pushed commit.

## 7. Net Roles workspace (read-only)

- [ ] 7.1 Add `fenolite.view.roles.roles_payload`, `/roles/<id>.json`, its cache, and its embedding in exports with `--workspace roles` (scenario "The numbers are the command's"). Proof: `uv run pytest tests/unit/view/test_roles_payload.py -q`.
- [ ] 7.2 Add the Net Roles panel (Nets, Groups, Classes) and Properties (Net, Role, Measures) (scenarios "The workspace of the bad buck" and "The switch node explained"). Proof: `uv run pytest tests/visual/test_roles_workspace.py -k "panels or properties" -q`.
- [ ] 7.3 Add the overlays Loop areas, Measures, Corridors, Locked copper and Role copper, and the role highlight (scenario "Hot loop on the copper"). Proof: `uv run pytest tests/visual -k roles_workspace -q`.
- [ ] 7.4 Add `--workspace`, `--roles`, `--layout` and `result.roles` to `cmd_view` (scenario "Roles summary for an agent"). Proof: `uv run pytest tests/unit/cli/test_view_cmd.py -k "workspace or layout" -q`.

## 8. Role writes and undo

- [ ] 8.1 Add `fenolite roles --forget` and `--forget-group` (scenario "Forget after accept"). Proof: `uv run pytest tests/unit/cli/test_roles_cmd.py -k forget -q`.
- [ ] 8.2 Add `--edit`, the server routes `/roles/plan` and `/roles/confirm` with the review header, one staged plan per page, and a refusal of plans the server did not stage (scenarios "Confirm a role from the page", "Read-only without edit" and "Edit needs the server"). Proof: `uv run pytest tests/unit/view/test_role_writes.py -k "confirm or readonly" -q`; `uv run pytest tests/unit/cli/test_view_cmd.py -k edit -q`.
- [ ] 8.3 Add the Pending panel, Apply and Discard, `FEN-4002` with Review again, and receipts logged in Messages. Proof: `uv run pytest tests/visual/test_roles_workspace.py -k pending -q`.
- [ ] 8.4 Add undo and redo with the inverse of each write kind (scenarios "Undo restores the bytes" and "Changed file stops undo"). Proof: `uv run pytest tests/unit/view/test_role_writes.py -k undo -q`.

## 9. Phases (after c0243 and c0244 merge)

- [ ] 9.1 Accept `copper` and `route --roles critical` replies in `--report`, bound to the board's SHA-256, and add the phase status (scenario "Phase 0 only", and the Limited case). Proof: `uv run pytest tests/visual/test_roles_workspace.py -k phases -q`; `uv run pytest tests/unit/view/test_project_review.py -k report -q`.
- [ ] 9.2 Draw corridors, locked copper, role copper and dashed proposals from the settled names (scenario "Corridors and locks"). Proof: `uv run pytest tests/unit/view/test_roles_payload.py -k corridor -q`.
- [ ] 9.3 Accept a proposal through its own command under the Pending flow, only if c0244 gives an exact inverse. Otherwise record the cut under this task. Proof: `uv run pytest tests/unit/view/test_role_writes.py -k proposal -q`.

## 10. Other workspaces

- [ ] 10.1 Move the sheet, library, drawing, BOM and output job, compare and project review views onto the shell's panels, the shared selection and the Messages panel, with their references rebaselined after review. Proof: `uv run pytest tests/visual -q` in the `viewer` job on the pushed commit.

## 11. Optional native window (cut first)

- [ ] 11.1 Add the extra `view-app` (pywebview, imported lazily) and `--serve --window`. With the extra missing, the reply is exit 6 with its hint. Add its line to `docs/viewer.md`, `docs/cli-contract.md` and the agent guide page `commands` (AGENTS.md rule 6). `pyproject.toml` `dependencies` stays empty. Proof: `uv run pytest tests/unit/cli/test_view_cmd.py -k window -q`; `uv run pytest tests/unit/test_pyproject_invariants.py tests/unit/test_no_copyleft_deps.py -q`.

## 12. Closing

- [ ] 12.1 Add the visual references of "Workbench references" with `tools/update_view_refs.py`, reviewed, and the determinism check (`H-G-WB-STABLE`). Record the size of the assembled page (at most 120 KB more than at task 1.1). Proof: `uv run pytest tests/visual -q` in the `viewer` job on the pushed commit.
- [ ] 12.2 Docs:
  - `docs/viewer.md`: rewritten around the workbench (menus, docks, layouts, keymaps with their sources, themes, Messages, the Net Roles workspace, writes and undo, budgets);
  - `docs/roles.md`: the workspace and `--forget`;
  - `docs/cli-contract.md`: the view options, `result.roles` and the roles options.

  Proof: `uv run pytest tests/unit/test_provenance.py tests/unit/cli -k "contract or view or roles" -q`.
- [ ] 12.3 Agent guide (AGENTS.md rule 6):
  - on the page `commands`, a tested line for `view --workspace roles --json`, and one for `roles --forget`, each with a `fenolite-cmd` block;
  - on `board-review`, the review loop "roles in the workspace, confirm through a plan".

  Then run `uv run python tools/gen_agent_guide.py`. Proof: `uv run pytest tests/unit/agent -q`; `uv run python tools/gen_agent_guide.py --check`.
- [ ] 12.4 Residue: every new `.py` starts with its SPDX and copyright lines, the fixtures carry the authored-for-Fenolite line, and no vendor icon, colour file or layout is present. Proof: `make residue`.
- [ ] 12.5 Run `make check-fast` and the focused tests of the touched files, then push the batch and confirm the required CI jobs, `viewer` included, on the exact commit (AGENTS.md rule 4; no full suite on the maintainer's machine). Proof: `make check-fast`, and the required jobs green on the exact commit.
- [ ] 12.6 Evidence: the six `H-G-WB-*` hypotheses in `docs/hypotheses.md` with their measurements; S-0920 to S-0933 cited from a new `src/fenolite/view/PROVENANCE.md` (the package has none today) and from `docs/viewer.md`; the evidence matrix regenerated. Proof: `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_provenance.py -q`; `uv run python tools/gen_evidence_matrix.py --check`.
- [ ] 12.7 Add an entry under `## [Unreleased]` in `CHANGELOG.md`, only after `0.7.0.dev0` has opened. The v0.6 guard requires `[Unreleased]` to be empty while `0.6.0` is cut and not published. Proof: `uv run pytest tests/unit -k changelog -q`; `uv run pytest tests/unit/test_release_record_v06.py -q` until 0.6.0 is published.
