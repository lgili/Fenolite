# c0405: library gallery design and item images

## Why

The maintainer saw the first deployed gallery (https://lgili.github.io/fenolite-library/, 2026-11-05) and
judged it unusable: a white page with a list of links, no images for symbols, footprints, devices or
blocks, and boards whose render failed shown without explanation. The gallery of c0279 task 4.3 wrote
plain cards and only boards had images (rendered by the library workflow). The workflow also ran
`kicad-cli` in its container without a home directory, so every call logged "Directory '/.cache'
couldn't be created (error 13)".

## What

- `fenolite library gallery` writes a designed static site: a header, a responsive card grid with search
  and filters by kind and licence, a light and dark theme, item pages with a large preview, a facts table,
  the `fenolite get` command with a copy button, the proof level and the licence and NOTICE links, and a
  benchmark page with the same style. Plain HTML and CSS, inline SVG, a little vanilla JavaScript; no CDN,
  no third-party fonts, no runtime dependency.
- Item images drawn by Fenolite: a symbol as an SVG of the symbol, a footprint as an SVG of its land
  (pads, courtyard, silkscreen, fabrication, pin 1 marked), a device as its symbol and footprint side by
  side, both from the library viewer's scenes. Boards keep the `top.svg`/`bottom.svg` renders and blocks
  show the schematic of their usage design; both come from the library workflow through a new
  `--renders DIR` option.
- An item whose image cannot be made shows a placeholder that names why; the command lists these in
  `result.placeholders` and the library workflow writes them into the job summary instead of failing.
- The attribution line and the restricted-marks rule of c0279 stay as they are.
- Library side: the pinned-Fenolite action gives `kicad-cli` a writable `HOME`, and the gallery workflow
  takes its tooling from the workflow's ref and the items from the tag (library PR 2).

## Impact

- `fenolite library gallery` gains `--renders DIR`; its result gains `placeholders`. The pages change
  completely; their names (`index.html`, `bench.html`, `<kind>/<namespace>/<name>/index.html`) do not.
- New module `fenolite.library.gallery_images` and a public `catalog_scene` in `fenolite.view.catalog`.
- No new FEN code, no new dependency, no model change.
