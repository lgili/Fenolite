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

## 6. Straight arcs

An Altium arc of a tiny sweep reads as three model points rounded to the nanometre, and they may lie on one
line. `design.arc()` takes no such arc, so the import left it out as a `drawing`. `_graphic_call` writes it as
`design.line()` from its start to its end, of its width and on its layer, when its middle point lies between
its ends: the stroke it draws. An arc of one point, or whose middle point lies beyond an end, draws no such
line and stays a `drawing`. The Altium writer does the same for a copper arc (`straight_arc`, change c0435).

## Authored reproductions, 2026-11-10

`tests/unit/importer/test_remaining_unexpressed_c0427.py` now reproduces the remaining refusal branches
without private inputs. The baseline used four temporary variants from Fenolite's authored two-sheet board:

| Variant | Reported kind | Current limitation |
|---|---|---|
| Remove the root Edge.Cuts graphics | `outline` | The DSL creates a closed board instead of an absent outline. |
| Add one through via on no net | `copper-without-net` | Via tables currently require a Net; netless tracks and arcs already have support. |
| Add an unnumbered through pad on GND | `pad-net-unnumbered` | Pin-based connections cannot name that pad. |
| Add a user-layer arc with width zero | `drawing` | The drawing DSL cannot express that width. This is a reader/import reproduction, not a native Altium run. |

In the baseline, each case refused by default (exit 7). An explicit lossy dry-run reported one omitted
item without changing source bytes or writing outputs. The slices below address the four authored cases.

## Netless vias in copper tables

A via whose model net is absent uses the existing no-net table sentinel, as tracks and arcs do. The
emitter omits `net`; `Design.via_table` accepts its absence because diameter and drill are already
required at the call. Lowering retains the via's geometry, span, protection, flags and key, with no
net id. The single-via and path-via APIs retain their existing net requirements. A nonempty unresolved
net id is an error case, not evidence that the source via was netless.

## Zero-width user-layer arcs

A curved board arc on a KiCad user drawing layer can have a stored width of zero. Preserve the
three points, layer and literal width in `import --to python` and the rebuilt board. KiCad 10.0.6
normalizes the width to 0.1 mm on a native save of either board. Keep the positive-width requirement
for copper, edge and other technical layers, and keep collinear zero-width arcs as a reported loss.

## Boards without a closed outline

Use the explicit empty tuple `board(outline=())` to declare the layer table without a logical
outline. Board declaration is tracked independently of the closed ring. In the model the outline is
absent, and any supported root edge is emitted as a drawing with its own width. An open boundary can
therefore be rebuilt without inventing board geometry. Board-relative placement, cut-outs, milled
slots and implicit zone outlines still require a closed ring. Explicit zone outlines and other
board drawings do not depend on a ring.

## Nets on unnumbered pads

A physical pad assignment is separate from schematic connectivity. The instance names the
unnumbered pad by its zero-based index in the vendored footprint's pad order and registers the
net with the design, even if nothing in the schematic uses it. Build assigns the model net ID
to the physical pad and reports an error for an absent or non-copper pad. The vendoring path
removes instance net fields but preserves pad order. The importer uses the same order and
emits board-level instance calls after any sheet-owned nets become accessible at the root.
On a rebuild the kept footprint's pads are matched by KiCad UUID, with unique exact physical
geometry as a fallback. Unmatched assignments stop the build. Several empty pad numbers are
never collapsed to one net.
