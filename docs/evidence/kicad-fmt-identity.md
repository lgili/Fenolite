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
