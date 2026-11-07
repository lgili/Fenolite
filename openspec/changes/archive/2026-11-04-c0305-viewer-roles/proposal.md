## Why

c0222 (in `0.6.0`) gives each net of a board a role (`power`, `switch_node`, `ground`, `kelvin`, `gate`,
`high_voltage`, `signal`), groups pads into hot loops, gate loops and Kelvin pairs, and judges the copper
against them in the stage `roles.rules`. All of it is JSON: a reviewer cannot see which copper is the switch
node, where the hot loop runs, or which pad a `roles.kelvin-outer` finding names, without reading the reply
and finding the pads by hand. Confirming a role takes a command line.

Another session wrote c0245-engineering-viewer, a competing viewer redesign with a Net Roles workspace. The
maintainer decided on 2026-10-29 that the viewer of `next-0.7` (c0300 to c0304) is the base and that
c0245-engineering-viewer is superseded, except for its role-aware view, which this change brings over into
the TypeScript and Preact viewer of c0304.

## What Changes

- **Role data on the board.** `fenolite view BOARD --roles run` runs `fenolite roles BOARD --check` in
  process and read-only; `--roles FILE` reads a saved reply of it. `fenolite.view.roles.overlay(reply,
  scene)` joins the reply to the scene as `scene.roles` (`fenolite.view_roles.v0`): the reply's role rows
  with their state and net, the groups with the points of their pads, the loop measures, and the role
  findings placed on the board. The numbers are the reply's, unchanged.
- **Net roles panel.** A side bar section with a legend (colour, glyph and count of each role kind), the
  role of each net (glyph, net, kind, current, confidence, state) and the groups. A net row highlights its
  net; a group row frames its pads.
- **Role overlays.** In the dock's Layers panel, a Roles group with three toggles: role colours (the copper
  of each role net tinted by its role), loops (hot loops and gate loops as hatched polygons through their
  pads, labelled with their area) and Kelvin pairs (dashed sense lines). Colour is never the only cue: each
  role has a glyph, each overlay its own hatch or dash.
- **Role findings.** The panel lists the reply's `roles.*` findings by code with markers on the board; a
  finding opens in the inspector. `check_overlay` places `roles.*` codes under the stage `roles.rules` and
  resolves a `where` that names a group or a `group:pad`, so `--check` replies place them too.
- **Inspector.** The Net section of a net with a role is followed by a Role section: kind, state, rule,
  confidence, evidence pads, current, working voltage, sensitivity and the groups that hold the net.
- **From a served page.** `roles` joins the read-only run allow-list (no option; a fixed command line), and
  with `--allow-actions` a Confirm roles action plans `fenolite roles --accept NETS --accept-group NAMES`
  through the existing plan, confirm and undo mechanism of c0303.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `board-viewer`: role data on a board, the Net roles panel, role overlays, role findings, the Role section
  of the inspector, the roles run and the Confirm roles action.
- `cli-contract`: `fenolite view --roles run|FILE`.

## Non-goals

- No menu bar, workspaces, docks, keymaps or plain-JS module system of c0245-engineering-viewer: the shell of
  c0300, the inspector and Layers panel of c0301 and the module structure of c0304 stay.
- No `fenolite roles --forget` and no exact-inverse undo of role writes: undo is `restore` of the receipt, as
  for every action of c0303. No role set, reject or current from the page.
- No router phase status, corridors or locked copper: c0243 and c0244 (another session) are not merged.

## Evidence level required

The view adds no fact. Role data keeps the reply's evidence (`INFERRED`, c0222 "Role evidence"); `fenolite
view` with `--roles` reports the lower of the scene's and the roles' evidence, by the lowest-wins rule. The
join is proven by unit tests on the authored reference boards of `examples/roles`, the page by Node tests of
its pure builders and Chromium tests in `tests/visual`, in the `viewer` CI job.
