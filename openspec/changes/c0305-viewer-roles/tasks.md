## 1. Entry

- [x] 1.1 Validate this change and read the role view of `origin/c0245-engineering-viewer` (its `view/roles.py`, `ui/workspaces/roles.js`, `ui/shell/themes.js`, tests and design decisions 6, 10 and 11); record in the design what is taken and what is not. Proof: `~/.npm/_npx/20f2b75ddc8bce88/node_modules/.bin/openspec validate c0305-viewer-roles --strict --no-interactive`.

## 2. Data

- [x] 2.1 `check_overlay`: the stage `roles.rules` for `roles.*` codes and the `aliases` of `overlay` (requirement "Role findings in the viewer", scenario "A Kelvin finding located"). Proof: `uv run pytest tests/unit/view/test_check_overlay.py -q -n 2`.
- [x] 2.2 `fenolite.view.roles`: `read_reply`, `overlay`, `summary` (requirement "Role data on a board", scenario "The bad buck joined to its scene"). Proof: `uv run pytest tests/unit/view/test_roles.py tests/unit/test_import_graph.py -q -n 2`.
- [x] 2.3 `fenolite view --roles run|FILE`, `result.roles`, the evidence, the groups passed to `--check` (requirement "View command shows roles"). Proof: `uv run pytest tests/unit/cli/test_view_cmd.py -k roles -q -n 2`.

## 3. Served page

- [x] 3.1 The run `roles` and its derived role data, the binding of a session reply and its run again on a build (requirement "Roles from a served page"). Proof: `uv run pytest tests/unit/view/test_runs.py tests/unit/view/test_server.py -k roles -q -n 2`.
- [x] 3.2 The action `roles` ("Confirm roles") with names checked against the session's role data (scenario "Confirm a role from the page"). Proof: `uv run pytest tests/unit/view/test_actions.py -k roles -q -n 2`.

## 4. Page

- [x] 4.1 `roles/roles.ts` (data, palette, pure builders) and the Role section of the inspector (requirement "Role section of the inspector"). Proof: `uv run python tools/build_viewer.py --check`; `uv run pytest tests/unit/view/test_page.py -k role -q -n 2`.
- [x] 4.2 `roles/draw.ts`, the Roles group of the Layers panel, the Net roles section, the role findings, the Roles commands, the roles run and Confirm roles in the page (requirements "Net roles panel", "Role overlays"). Proof: `FENOLITE_REQUIRE=browser uv run pytest tests/visual/test_roles.py -q`.

## 5. Teaching and documentation

- [x] 5.1 A tested line for `view --roles` in the agent guide, the generated command guide, `docs/viewer.md` ("Net roles") and `docs/cli-contract.md` ("view"). Proof: `uv run pytest tests/unit/agent -q -n 2`; `uv run python tools/gen_agent_guide.py --check`.
- [x] 5.2 An entry in `CHANGELOG.md` under `## [Unreleased]`, the row of `openspec/README.md` and the roadmap line. Proof: `uv run pytest tests/unit/test_release_record_v06.py -q -n 2`.

## 6. Closing

- [x] 6.1 Screenshots of the six reference variants built to KiCad, looked at; the visual tests as the `viewer` CI job runs them. Proof: `FENOLITE_REQUIRE=browser uv run pytest tests/visual -q -n 2`.
- [ ] 6.2 Run the focused tests and the CI jobs of the branch. Proof: `make check-fast` on the maintainer's machine, then the CI jobs, `viewer` included.

Open on the branch (2026-10-29): 6.2 waits for `make check-fast` on the maintainer's machine and the CI jobs of the branch, `viewer` included (only focused tests ran here: ruff, ruff format, pyright of the changed modules, `tests/unit/view`, `tests/unit/cli/test_view_cmd.py`, `tests/unit/roles`, `tests/unit/agent`, `tests/consistency`, the import graph, the release records, and `tests/visual` with `FENOLITE_REQUIRE=browser`).
