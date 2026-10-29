# Public presentation assets

All captures use Fenolite **0.5.0**, based on tag `v0.5.0` / commit `3a0bfb7d`.
No employer or private project input is used. These small boards are software examples, not approved
production designs. The screenshots and GIF show the actual Fenolite viewer without redrawn UI.

| Asset | Source | What is shown |
|---|---|---|
| `hero.png` | `examples/blink_routed/design.py` and its authored Mini libraries | KiCad board generated with the script's copper intents |
| `board.png` | Packaged `blink` starter, emitted by `fenolite init` | Built-in parts, placed by the starter and routed with the demonstration `direct` router |
| `schematic.png` | `tests/data/altium/blink/blink.PrjPcb` and its authored documents | Altium-format sheet in Fenolite, after component cross-probe and fit |
| `viewer-demo.gif` | The same authored Altium fixture | Board, selected resistor net, cross-probe to U1, fitted schematic; four actual states held for five seconds each |
| `social-card.svg`, `social-card.png` | Original vector composition plus `hero.png` | Name, short description and a real screenshot; no vendor artwork |

The example scripts are CC0-1.0; the Altium fixture is authored for Fenolite and declared in
`tests/data/MANIFEST.toml`. New capture tools and the original card composition are Apache-2.0 under
this repository's license. Generated captures are distributed under Apache-2.0. No official CAD library
file is copied into these assets.

## Reproduce

From a clean checkout of this presentation branch, with Python 3.11+, Node, FFmpeg and development-only
Node packages `playwright` and `sharp`:

```bash
uv sync --extra dev
uv run python tools/marketing/prepare.py
node tools/marketing/capture.cjs
```

`prepare.py` refuses an existing `build/presentation` folder. Move it aside before a fresh run; generated
HTML, raw frames and CLI state stay outside the tracked media. Every CLI write uses a dry run followed by
confirmation of the exact plan. It builds and routes the starter, builds the routed example, then exports
the two KiCad views and authored Altium project. No KiCad, Altium, external router or network request is
needed by the design/viewer operations.

Install the Node tools in a separate developer environment, or a scratch folder, rather than adding them
to Fenolite's Python runtime dependencies. Set `NODE_PATH` to that environment's `node_modules` if needed.
Run `npx playwright install chromium` for its browser. `FENOLITE_PLAYWRIGHT` can name an alternate Playwright
package and `FENOLITE_CHROMIUM` an existing compatible Chromium executable. FFmpeg must be on `PATH`.

The capture tool prints browser version, frame count and any page errors. PNG screenshots are 1280 × 800;
the GIF is 960 × 600; the social card is 1280 × 640 and must remain below 1 MB. Browser/font versions may
change pixels; the captures are illustrative, not pixel-identical cross-platform references.

Original capture environment: Chromium `148.0.7778.96` on macOS. Four animation frames, zero page errors.
The board inputs are unchanged. The social card's typography and crop are composed in `capture.cjs`;
`social-card.svg` embeds the screenshot so it can be reviewed as one self-contained vector file.

## Review

Open `hero.png`, `board.png`, `schematic.png`, `social-card.png` and the GIF. Confirm that no local paths or
private content appear, captions identify the right example, the application is readable and the
animation really selects a net and crosses to its schematic. Promotion does not raise any format evidence level.
