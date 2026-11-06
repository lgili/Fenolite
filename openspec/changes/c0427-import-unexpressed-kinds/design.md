# Design: c0427

## 1. Rules the DSL cannot say

`_minimums` dry-runs `_rule_call` on every rule; a constraint kind with a refused rule is *native* when the
source holds the text of each of its rules (`Source.rule_texts`, locator `/kicad_dru/rule[n]` → item text,
read with the source's `.kicad_dru`). Those rules are written with `design.verbatim(..., target="kicad_dru")`
sorted by their index in the file; `with_rules` appends verbatim rule items after the written rules. Keeping
a whole kind, not one rule, keeps the order between the rules of that kind, which is the only order KiCad's
precedence reads (`H-K-DRU-ORDER`: the later matching rule of one constraint governs). For an Altium source
the texts are those of the rules file its in-memory KiCad conversion wrote. A kind with a rule whose text
is unknown stays `custom-rule`. A source whose whole rules file is kept natively (c0359,
`native_rules_text`) is untouched.

`_limits_said` mirrors the checks of `rule()` so a refusal is found before code is emitted.

## 2. Negative silk clearance

KiCad reads `(constraint silk_clearance (min -0.1mm))` and lets silkscreen overlap by up to 0.1 mm; the
canary proves the file is read (an unreadable rule disables every rule silently, `H-K-TOK-RULES-SILENT`).
`NEGATIVE_MIN_KINDS = {"silk_clearance"}` in `dsl.design`.

## 3. Board-only nets of copper graphics

In KiCad 10 boards the net of a graphic is a name; a net that no pad, track, zone or sheet names is not in
the circuit read back. The net variables now include every net a copper graphic names.

## 4. Paste drawings

`DRAWING_LAYER_KINDS` gains `solderpaste`; the importer uses the same tuple.

## 5. Altium texts and cut-outs

`copper.lines()` replaces CR LF by LF in a text's string (ids stay those of the raw string).
`copper.notched()` takes the board shape's edge lines and the `Edge.Cuts` polygons a cut-out became; a
cut-out with vertices inside and outside the shape ring is subtracted (the geometry backend's difference).
When the result is one ring without holes the shape's lines are replaced by the ring's (locator
`Board6/Data#0:notch:V<k>`) and the cut-out goes, with `altium.import.cutout-notch` (info). With an arc in
the shape, no backend, a geometry error or another result, nothing changes.

## Open

- Zero-width arcs on mechanical layers: KiCad 10.0.6 loads a zero-width `gr_arc` as 0.1 mm, so the DSL's
  `width > 0` has no faithful spelling; not reproduced on public data.
- `outline`, `pad-net-unnumbered`, `copper-without-net`: not reproduced on public data.
