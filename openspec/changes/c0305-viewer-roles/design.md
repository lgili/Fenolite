## Context

- **Origin.** The role-aware view comes from c0245-engineering-viewer (branch `c0245-engineering-viewer`, at
  `b7f6f089`, another session, 2026-10-29): its `src/fenolite/view/roles.py` (`payload`, `state_of`, the
  schema name `fenolite.view_roles.v0`), its Net Roles workspace (`ui/workspaces/roles.js`: the Nets and
  Groups lists, the role chips with glyphs, the loop overlays, the role findings in Messages, the role
  properties) and its role palette (`ui/shell/themes.js`: seven role colours chosen for Fenolite and checked
  apart under simulated colour-vision deficiency, a glyph and a hatch per role). The maintainer superseded
  that change on 2026-10-29 except for this view; this change ports it, credited here, into the viewer of
  `next-0.7`. Nothing else of that branch is taken: not its menu bar, workspaces, docks, keymaps, layouts,
  plain-JS module system, `roles --forget` or role writes with exact inverses.
- **What exists** on `next-0.7` after the merge of `dev` at `da300adf`:
  - `fenolite roles PATH [--check]` (c0222): `result.roles` (one row per net: `net`, `kind`, `source`,
    `rule`, `confidence`, `pads`, `milliamps`, `working_mv`, `sensitive`), `result.loops`, `kelvins`,
    `gates` (groups with pad labels, `origin`, `rule`, `confidence`), `classes`, `store`, and with `--check`
    `result.measures` and `result.summary`; `issues` with `roles.*` codes whose `where` is a net, a group,
    `group:pad` or a KiCad locator. With `--accept`, `--accept-group` it is a writing command of the
    mutation protocol, writing the role document only.
  - `fenolite check` runs the stage `roles.rules` by default; `check_overlay` knows no `roles.` prefix.
  - The viewer of c0300 to c0304: TypeScript modules linked in the order of `viewer/src/main.ts`, Preact for
    panels, the side bar sections of `ui/section.tsx`, the dock's Properties (inspector models of
    `inspect/model.ts`, pure builders tested under Node) and Layers tabs, the command registry and palette,
    the runs of c0302 and the actions of c0303.

## Goals / Non-goals

- **Goals:** see the roles on the copper, find a role finding on the board, read a net's role in the
  inspector, refresh the roles and confirm inferred ones from a served page, in the look of c0300 and c0301.
- **Non-goals:** the proposal's.

## Decisions

### 1. One data object: `fenolite.view_roles.v0`

`fenolite.view.roles.overlay(reply, scene)` (standard library and `fenolite.model.rules.ROLE_KINDS` only)
returns `{schema, document, sha256, evidence, roles, kinds, groups, measures, summary, store, findings,
counts, notes}`:

- `roles`: the reply's rows unchanged plus `state` (`declared`, `confirmed` or `inferred`, c0245's
  `state_of`) and `net` index into `scene.nets` (`-1` when the board has no such net);
- `kinds`: the count of each role kind, in `ROLE_KINDS` order;
- `groups`: one entry per hot loop (`type: "hot"`), gate loop (`"gate"`, pads drive, gate, source, return)
  and Kelvin pair (`"kelvin"`, element and receiver pads), with `origin`, `rule`, `confidence`, `pads`,
  `points` (scene units, the pads found), the loop measure's `area_nm2`, `bound_nm2` and `ratio_permille`
  when the reply measured it, and the `net` the measure names;
- `findings`: the reply's issues placed by `check_overlay.overlay` (stage `roles.rules`), with the group
  names as aliases (Decision 2); `counts` per severity.

The page converts points to millimetres once, as it does for check findings.

### 2. `check_overlay` learns the role codes

`STAGE_OF` gains `("roles.", "roles.rules")` and `BOARD_STAGES` gains `roles.rules`. `overlay(reply, scene,
aliases=None)` takes a map from a name to pad labels: a `where` part equal to an alias stands for its pads,
and `alias:pad` for that pad. `fenolite view --check` passes the groups of `scene.roles` when there is one,
so a `roles.loop-area` of a `--check` reply lands on its loop.

### 3. Where the roles come from

| source | how |
|---|---|
| `--roles run` | `fenolite roles BOARD --check` run in the view's process through the command's own parser, for every board of the page |
| `--roles FILE` | a saved `roles --check --json` reply; another command's reply or a role document is `FEN-3004` |
| a served page | the run `roles` (Decision 6) |

A reply is bound to the board's SHA-256 and to the role document's size and time. In a served page a reply
that no longer matches is run again in process when the board is built again (after a save or a write), so a
confirm shows at once; a `FILE` reply that does not match the board shows with a note. Without `--roles` and
without a run the scene has no roles and nothing changes.

### 4. Role palette and cues

The seven colours and glyphs of c0245 (`P`, `SW`, `G`, `K`, `GT`, `HV`, `S`), Fenolite's own values; the dark
set on a dark document background, the light set on a light one (the board palette decides, not the chrome
theme). They are canvas colours, so they live in `roles/roles.ts`, not in the chrome's token blocks. A legend
row always shows the glyph and the kind's name; hot loops hatch at 45°, gate loops at 135°, Kelvin pairs are
dashed. `signal` nets are not tinted.

### 5. Page modules (c0304's structure)

- `roles/roles.ts`: the data (`ROLES`), the palette, `rolesToMM`, and between `// ---- roles model (c0305)`
  and `// ---- end roles model` the pure builders the Node tests run: `roleSection(row, groups, f)`,
  `roleLegend(data)`, `groupsOfNet(data, name)`.
- `roles/draw.ts`: `drawRoles()`, called by `draw()` after the check markers: tinted copper through
  `selCache`, loop polygons, Kelvin lines, finding markers.
- `panels/roles.tsx`: the Net roles section (`data-sect="roles"`, board only, hidden without roles).
- The Layers panel shows a Roles group of toggles when the board has roles; the inspector appends the Role
  section to a net's model; the registry gains Roles commands (palette and shortcut sheet; no toolbar
  control).

### 6. Runs and actions

- `runs.ALLOWED` gains `roles` with no option; `ChildRunner.words` builds `roles --check -- BOARD` from a
  fixed template (the MCP catalog lists no read-only `roles` tool). `derive` turns its envelope into
  `scene.roles` for the page, as a `check` run fills the review.
- `actions.ACTIONS` gains `roles` ("Confirm roles"), options `nets` and `groups`, each a list of names
  that the session's role data shows as inferred; the template is `roles --accept=N,… --accept-group=G,…
  -- BOARD` on the board file. Plan, confirm and undo are c0303's: the plan names the role document, the
  receipt lists it, Undo is `restore`. `restore` deletes no file, so undoing the first confirm, which
  created the role document beside a board Fenolite did not build, leaves it in place, as c0303 says of
  every created file.

## Risks / Trade-offs

- `--roles run` costs one `roles --check` per board (seconds on the reference boards): it is opt-in.
- A role document changed by another program while the page is served is noticed at the next build of the
  board, not at once: the watcher follows the board file only.

## Migration Plan

None: new options and a new scene key; a page without roles is unchanged.

## Open Questions

None.
