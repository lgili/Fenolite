## Why

`fenolite view` (c0176 to c0193, c0233 to c0240) draws boards, sheets, libraries and drawings well, in the
colours of their own tools, but the page around the drawing looks like a debugging aid. At 1440 × 900 the
toolbar is one flat row of fifteen text buttons with no grouping and no icons; two controls read "Fit" (the
view and the print scale) and two read "Clear" (the selection and the filter); "Edge" and "Link" say little.
The side bar is a long list of flat sections (every finding group, the many at 0 included) and the project
review hides behind a small underlined "Review". The status bar shows a SHA-256 next to the cursor. Nothing
reaches a command, a part, a net or a document without knowing where it sits.

This change gives the viewer a professional shell. It changes no drawing, no scene and no server route.

## What Changes

- **Design tokens and a light theme.** One set of CSS custom properties for spacing, type scale, radii,
  surface and text colours, the accent and the focus ring. A light theme of the interface next to the dark
  one, following the system setting until the user picks one. Documents keep their own colours.
- **Grouped toolbar.** Three groups, View (2D/3D, Fit, Top/Bottom), Tools (Measure with point and edge
  modes, Mark, units) and Share (Copy link, Export: SVG and Print with its scale). Each button has an inline
  SVG icon drawn for Fenolite, a short label and a tooltip with its shortcut. The duplicate "Fit" and
  "Clear" controls go: the print scale moves into the Print menu, the selection clears with `Esc` or the
  palette.
- **Command palette.** `Ctrl+K` (`Cmd+K` on macOS) opens one search box that runs commands and jumps to
  parts, nets and documents. One command registry feeds the toolbar, the palette and a shortcut sheet (`?`).
- **Collapsible side bar.** Each section is a disclosure with a count badge, open state remembered.
  Components and Nets sort by column. Finding groups at 0 fold into one line that still lists them. The
  project review becomes a visible entry with its state summary.
- **Status bar and document details.** Cursor coordinates, grid, units, zoom, current layer, selection and
  live state. The file's SHA-256, size, backend, evidence level and scene version move to an "About this
  document" popover where the hash can be copied.
- **Loading, empty and error states** for documents, lists and panels.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `board-viewer`: interface tokens and themes, grouped toolbar, command palette, side bar sections, status
  bar and document details, loading states; the palette chord as the one exception of "Context-aware viewer
  shortcuts".
- `viewer-visual-tests`: references of the shell in both themes.

## Non-goals

- No change of a scene, of a document's colours (`docs/viewer.md`, "Colours") or of a server route.
- The inspector, the layers panel, the net emphasis and the 3D controls are c0244; running commands is c0245;
  writing actions are c0246.
- No icon font, no framework, no external URL: the page stays one offline file that `--export` embeds.
- No icon or palette value taken from a vendor tool or a third-party icon set.

## Evidence level required

No format fact is involved, so no evidence label changes. Each behaviour is proven by tests: static and
Node checks of `page.html` in `tests/unit/view/`, and Chromium interaction and screenshot tests in
`tests/visual` run by the `viewer` CI job (Playwright 1.63.0). The screenshot references are regenerated
in that job's environment and reviewed by the maintainer before they are committed.
