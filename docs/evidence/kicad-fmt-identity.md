# KiCad printer layout: Fenolite against 9.0-written boards

This page counts the line differences between `dumps(parse(f))` and the 9.0-written demo boards of the
corpus (`tests/corpus/test_fmt_identity_9.py`, `needs_corpus`). Only counts are recorded, never file
content. Measured on 2026-10-01 over the cached non-heavy `kicad-demos` boards with header `20241229`
and `generator_version "9.0"`.

| class | count | meaning |
|---|---|---|
| `files` | 18 | boards compared |
| `identical` | 14 | byte-identical with Fenolite's printer |
| `atom-list-wrap` | 83 | continuation lines of long atom-only lists (`members`) that KiCad 9 wraps (`H-K-FMT-ATOMWRAP`) |
| `atom-after-list` | 2 | an atom written on the same line as the list before it (`(loss_tangent 0.02) addsublayer`), against `H-K-FMT-MIXED` |
| `glued-lists` | 68819 | every differing line of a board whose published layout glues lists together (`)(`); the demo published malformed at 9.0.9.1 has the same splice at 10.0.6, where it still parses |
| `other` | 69 | head and closing lines of the same wrapped lists |

Reading: apart from the published irregularity, Fenolite's printer reproduces 9.0 writes except two
rules it does not implement: the wrap of long atom-only lists (`members`, about 88 columns) and an atom
kept on the line of the preceding list in `stackup` layers (`addsublayer`). Byte identity with 10.0
writes is measured by the typed board writer change (`H-K-FMT-INDENT`).

## 10.0 writes

`tests/kicad/test_fmt_identity_10.py::test_byte_identity_kicad10` (change c0020), measured on 2026-10-03
with kicad-cli 10.0.6 (macOS): `dumps(parse(f))` against `pcb upgrade --force` copies, made in memory, of
the 24 non-heavy `oracle` boards of the corpus, of `tests/data/kicad/board/two_layer.kicad_pcb` and of the
target-10 triad written by `write_board`. Each original line of a differing block is counted once.

| measure (10.0 writes) | count |
|---|---|
| files compared | 26 |
| byte-identical with Fenolite's printer | 19 |
| lines holding `(xy ` (`xy-packing`) | 31 |
| continuation lines of wrapped atom-only lists (`atom-list-wrap`) | 4933 |
| an atom on the line of the list before it (`atom-after-list`) | 2 |
| head and closing lines of those lists (`other`) | 84 |
| lists glued together (`glued-lists`) | 0 |

Reading: 19 of 26 files are byte-identical with Fenolite's printer, so the indentation and the head-line
rules hold there (`H-K-FMT-INDENT`). The seven others differ where 10.0.6 wraps long atom-only lists, which
Fenolite prints on one line (`H-K-FMT-ATOMWRAP`), in 31 lines of `xy` packing (`H-K-FMT-XYWRAP`), and in
the two `addsublayer` lines that 9.0 also writes (`H-K-FMT-MIXED`). The printer is not changed because of
this measurement: byte identity with KiCad's printer is not a goal, and a wrap rule belongs to
`fmt --check` (v0.2a).


## The canonical print is a fixed point (`fenolite fmt`)

`tests/corpus/test_fmt_idempotent.py` (change c0066, `H-K-FMT-IDEMPOTENT`), measured on 2026-10-05 on
macOS with the corpus cached: for every `rt0` row of the manifest whose file is cached and not heavy, and
for every authored KiCad S-expression file under `tests/data/`, `canonical(t) = dumps(parse(t))` is
printed twice and parsed again. The census is written through `tests/_boards.py::census`
(`FENOLITE_CENSUS_OUT`).

| measure | corpus (`rt0` rows) | authored files (`tests/data/`) |
|---|---|---|
| rows in the manifest | 138 | not applicable |
| files measured | 136 | 106 |
| accepted by `canonical` | 136 | 94 |
| of them `.kicad_pcb` | 24 | 29 |
| of them `.kicad_mod` | 104 | 28 |
| of them `.kicad_sch` | 1 | 1 |
| of them `.kicad_sym` | 1 | 3 |
| of them `.kicad_wks` | 1 | 33 |
| of them `fp-lib-table` files | 5 | 0 |
| refused: does not parse | 0 | 11 |
| refused: invalid UTF-8 | 0 | 1 |
| refused: the printer refuses the tree | 0 | 0 |
| `canonical(canonical(t)) != canonical(t)` | 0 | 0 |
| canonical print not tree-equal to the source | 0 | 0 |

Reading: on every file that `canonical` accepts, formatting a formatted file changes nothing, and the
print holds the same tree as the source. The two manifest rows that were not measured are heavy items, which are
not cached on this machine (`FENOLITE_HEAVY=1` includes them where they are). The twelve authored files that are refused are the parser's authored
negatives. The printer refused no tree: the parser accepts comments before the root only, so a parsed file
never holds a comment below it. Nothing here says that KiCad writes the same bytes; the sections above
measure that. The corpus holds one schematic today: the schematic rows that change c0060 adds carry the
use `rt0` and are measured by the same test.
