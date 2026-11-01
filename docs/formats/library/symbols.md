# Generated symbols: layout constants and conventions

The symbol generator of change c0261 (`fenolite.catalog.generate.symbol`) draws a symbol from a pin table
(`fenolite.pins.v0`, described in [`docs/symbols.md`](../../symbols.md)). This page records the facts it
relies on, with their sources, and the constants it uses, which are Fenolite's own choices.

## Facts from public sources

| fact | source | label | hypothesis |
|---|---|---|---|
| KiCad's library convention asks that the origin (connection point) of every pin lie on a node of a 100 mil (2.54 mm) grid | S-0339 (KLC S4.1, "General pin requirements", read in the `klc` repository at commit `6e8cbad9`) | INFERRED | H-G-SYMBOL-LAYOUT |
| The same convention asks for pins of at least 100 mil (2.54 mm), all pins of a symbol of one length, and the alternate-pin-function feature for pins of several functions | S-0339 (KLC S4.1) | INFERRED | H-G-SYMBOL-LAYOUT |

The generator follows the first two facts for its own output: every connection point, pin length and
body corner is a multiple of 2.54 mm, every pin is 2.54 mm long, and a table's `alternates` are written as
KiCad alternates. Nothing of any library, generator or convention text is copied; the rule below is
Fenolite's.

## Constants (Fenolite-authored)

| constant | value | label | why |
|---|---|---|---|
| `G` | 2 540 000 nm (100 mil) | INFERRED | grid and pin pitch: the 100 mil grid above; a multiple of the Altium writer's 10-mil grid (254 000 nm) |
| `L` | 2 540 000 nm | INFERRED | pin length: the shortest length the convention asks for |
| `A` | 1 016 000 nm | INFERRED | estimated advance of one character of a pin name at the 1.27 mm font, not a font metric |
| stroke | 254 000 nm | INFERRED | the body outline, the width of the hand-drawn catalog symbols |
| `split_above` | 100 visible rows (16 … 1000) | INFERRED | a table with more visible rows is split into units |
| `unit_pins` | 48 rows (8 … 200) | INFERRED | the largest automatic unit |

Body size per unit, with `nL`, `nR` the slots of the left and right sides (gaps included), `nT`, `nB` the
pins on top and at the bottom, and `cL`, `cR`, `cT`, `cB` the longest names in characters (overbar markup
removed): `W = max(ceil2G(A·(cL + cR) + 2G), ceil2G((max(nT, nB) + 1)·G), 4G)` and
`H = max(ceil2G((max(nL, nR) + 1)·G), ceil2G(A·(cT + cB) + 2G), 4G)`, where `ceil2G(x)` is the smallest
multiple of `2G` not below `x`. W and H are multiples of `2G`, so the body is centred on the origin with
its corners on the grid.

## Default groups (Fenolite-authored, INFERRED)

| type | default group | side |
|---|---|---|
| `power_in` whose name matches `(?i)^(A\|D\|P\|S)?(GND\|VSS)` or `(?i)^(EP\|PAD\|THERMAL)$` | `ground` | bottom |
| other `power_in` | `supply` | top |
| `input` | `input` | left |
| (explicit only) | `control` | left |
| `output`, `power_out`, `open_collector`, `open_emitter`, `tri_state` | `output` | right |
| `bidirectional` | `io` | right |
| `passive`, `free`, `unspecified` | `passive` | left |
| `no_connect` | `nc` | right |

Group order per side: left `input`, `control`, `passive`; right `output`, `io`, `nc`; then any group a
row moves to that side with an explicit `side`. One empty slot separates two groups of one side.
