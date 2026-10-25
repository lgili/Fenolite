# KiCad colour themes (`colors/*.json`)

KiCad keeps the colours of its editors in colour theme files. `fenolite view --theme` reads one, so that a
KiCad project is drawn in the user's own colours (change c0178). Without a theme, the viewer uses a palette
that Fenolite authors in KiCad's manner (`fenolite.view.themes.KICAD`). No colour value of KiCad's built-in
themes is used: they live in KiCad's GPL sources, which `LEGAL.md` (block A) does not let Fenolite
transcribe. This page holds the form of the file only; sources are listed in `docs/evidence/sources.md`.

## Facts

| fact | source | label | hypothesis |
|---|---|---|---|
| A colour theme is one JSON file in the `colors` folder of the user settings path; KiCad detects a file copied there at its next start | S-0813 | INFERRED | H-K-THEME |
| The user settings path is `%APPDATA%\kicad\<major>.0` on Windows, `~/.config/kicad/<major>.0` on Linux and `~/Library/Preferences/kicad/<major>.0` on macOS (the page states it for 8.0) | S-0814 | INFERRED | H-K-THEME |
| The file is a JSON object with the objects `board`, `fpedit` and `meta`, and `schematic` in files that theme the schematic editor | S-0813 | INFERRED | H-K-THEME |
| A colour is a string `rgb(r, g, b)` or `rgba(r, g, b, a)`, with r, g and b from 0 to 255 and a from 0 to 1 | S-0813 | INFERRED | H-K-THEME |
| `board.copper` is an object keyed `f`, `b` and `in1` to `in30`; `board` also holds `background`, `f_silks`, `b_silks`, `f_mask`, `b_mask`, `f_paste`, `b_paste`, `f_crtyd`, `b_crtyd`, `f_fab`, `b_fab`, `edge_cuts`, `dwgs_user`, `cmts_user`, `eco1_user`, `eco2_user`, `via_through`, `plated_hole` and `grid`, among others | S-0813 | INFERRED | H-K-THEME |
| `schematic` holds `background`, `bus`, `component_body`, `component_outline`, `fields`, `grid`, `junction`, `label_global`, `label_hier`, `label_local`, `no_connect`, `note`, `pin`, `pin_name`, `pin_number`, `reference`, `sheet`, `sheet_filename`, `sheet_label`, `sheet_name`, `value` and `wire`, with `brightened`, `erc_error`, `erc_warning` and `net_name` | S-0813 | INFERRED | H-K-THEME |
| `meta` holds `filename`, `name` and `version` | S-0813 | INFERRED | H-K-THEME |
| Which theme an installation has selected is not stated by these sources; the user names the theme | S-0813, S-0814 | UNKNOWN | H-K-THEME |

## Fenolite's reading

- Each known key replaces one slot of the `kicad` palette; a key the file leaves out keeps the palette's
  colour, and an unknown key is ignored. The alpha of `rgba` is kept as the slot's opacity.
- `--theme NAME` looks for `NAME.json` in the `colors` folder of each settings folder, majors 10 to 6, then
  takes `NAME` as a path.
