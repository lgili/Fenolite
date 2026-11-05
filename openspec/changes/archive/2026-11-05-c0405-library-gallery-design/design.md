# c0405 design

## Images

Fenolite already draws symbols and footprints for the library viewer and the review sheets (c0262): the
catalog scenes of `fenolite.view.catalog` hold the primitives in micrometres (symbol scenes: polylines,
polygons, ellipses, arcs, texts with colours; footprint scenes: per-layer segments, arcs, circles,
polylines and filled rings, plus the pad list). `fenolite.library.gallery_images` turns one such scene
into a standalone SVG: integer coordinates, a fixed palette, no font file (`font-family` system stacks
only), no script. A footprint draws the front copper, silkscreen, courtyard and fabrication layers (the
back ones when the footprint has no front copper), the pad numbers, and an outline around pad 1 (the pad
numbered `1`, else `A1`, else the first pad in the scene's order). A device shows the images of the
symbol and the footprint it depends on.

The item's geometry is read the way `library check` reads it (`_library_check.load` on the item's own
files: `pins.toml`, `package.toml`, a record with a generated `.kicad_sym` or `.kicad_mod`, or a plain
KiCad file), so the gallery shows the same definition that was reviewed. Reading or drawing failures do
not stop the site: the item gets a placeholder naming the error.

Boards and blocks need KiCad or the execution of item code, which the core command never does: the
library workflow builds them and hands the images over with `--renders DIR`, a folder that mirrors the
gallery (`<item dir>/top.svg`, `bottom.svg` for a board, cropped to the board by `kicad-cli pcb export svg
--page-size-mode 2 --exclude-drawing-sheet`; `schematic.kicad_sch` for a block, the usage's sheet, which
Fenolite draws from the scene of its schematic viewer without the drawing sheet and cropped to what the
sheet holds; or a ready `schematic.svg`) and may hold
`failures.json` (`{item id: reason}`). Missing files become placeholders with the reason from
`failures.json`, or "no render was supplied".

Same input bytes give the same output bytes: rows are sorted, numbers are integers or fixed-format
decimals, and there is no timestamp.

## Pages

`assets/site.css` and `assets/site.js` are written once and linked relatively. CSS custom properties
carry a light and a dark palette; the theme follows `prefers-color-scheme` until the visitor picks one
(kept in `localStorage`). The script only filters cards (text, kind, licence), switches the theme and
copies the `get` command; every page works without it. Each card holds the thumbnail (`loading="lazy"`),
the title, kind and licence badges and the short attribution. The item page holds the large previews, the
attribution line (unchanged), the facts table, the command with a copy button, proof and evidence, and
links to the item folder, its LICENSE and NOTICE at the release tag.

## Alternatives

`kicad-cli sym export svg` and `fp export svg` would draw the same items, but they need KiCad in every
environment that builds the site and their bytes change with the KiCad version; Fenolite's scenes are
already reviewed by c0262 and run in the unit tests. KiCad stays for boards, where Fenolite has no SVG
renderer. `fenolite render --svg` plots the whole drawing sheet, so the board shows small in a card; the
workflow calls `kicad-cli` with the same layers and the crop options instead of changing `render`.
`kicad-cli sch export svg` has no crop option, so block sheets go through Fenolite's schematic scene.
