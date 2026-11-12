# Design: c0504

## D1 F33: `Session.unpour` and the stale-pour warning

**Operation.** `unpour(state, item: Polygon)`: `View.find(item)`, then `state.remove(storage, positions)` for
each storage of `ops._poured(state, index)`. These are the same lines that end `ops.set_outline`, which now calls
`unpour`'s helper. The polygon record, its index and every other polygon are unchanged. A polygon with no
poured primitive is refused with `altium.edit.assertion` ("has no pour to remove"). A script that unpours a set
of polygons must know they are poured. `Session.unpour` queues it under the new gate `unpour`, rows
`H-A-EDIT-SHAPE` and `H-A-EDIT-KIT`.

**Evidence.** The record change is the one `set_outline` makes: a polygon record kept, its pour gone.
S-2111 (2026-11-06, agent run, `set_outline`) saw Altium open such a document with no message and repour it.
`H-A-EDIT-SHAPE` stays `INFERRED`. The new Part J case `J-unpour` (numbered when written) unpours a polygon of
the kit board and repours it in Altium.

**Stale pour.** In `verify`, after the gates: for each copper record the session added, removed or changed (from
`state.added` and `state.removed`) that is not itself a poured primitive, take its box. Each polygon on that
layer that still holds poured primitives, and whose outline box meets that box, gives one
`altium.edit.pour-stale` (warning): "<n> edited items on <layer> lie in the box of the poured polygon <name>",
hint `Session.unpour(Polygon(<name>))`. A box test is a coarse filter. It may warn for an edit that lies in the
box but outside the polygon. It never misses an edit inside the polygon. It does not refuse.

**Alternative.** Mark the polygon for a repour by a key instead of removing the pour. No source names such a key.
The saved form of "needs a repour" in the corpus is a polygon without pour regions (`pcb-pour.md`;
`pcbdoc.ZONE_UNPOURED`).

**Not here.** Pouring it again with the c0463 engine. That needs c0463's pour to reach Altium's on saved
documents, which c0463 measures on conversions only.

## D2 F46: findings compared by identity

`integrity._finding` gains a `key: tuple[str, ...]`, which the rules fill. The `Issue` is unchanged: the key
travels in a side mapping, `check_document_keyed(doc, compound) -> list[tuple[key, Issue]]`. The keys:

- `subpoly-gap`: `(code, polygon name, pour index, missing values)`;
- `pour-index-twice`: `(code, pour index, sorted polygon names)`;
- `unique-id-*`: `(code, the id)`;
- parameter, model and layer rules: `(code, component designator or model id, the layer pair)`.

None of these holds a record position. `verify` computes the keys of the source and of the result. A result
finding whose key the source holds is inherited. The inherited findings give one `altium.edit.integrity-inherited`
(info), "<n> integrity findings the source already holds: <code> × <k>, …", and no `altium.edit.integrity`. A new
finding keeps today's message, positions included, so that the user can find the records.

`fenolite check --stages altium.integrity` on a single document has no source to compare with. It keeps its
findings. The hint of `subpoly-gap` adds "a document saved by Altium can hold this; compare with the source
document".

## D3 F47: degree signs and other compatibility characters

**First, reproduce (task 1.1).** An authored design with one component whose description is `-40 °C to 125 °C`
and a second whose description is `-40 ℃`. Each is run through:

- a build to the binary and to the ASCII schematic form;
- a schematic library write (`schlib.component_record`);
- an edit session `set_property` on a PCB component key.

Each path's outcome (written, refused with which reason, written with `?`) is recorded in the test as the
"before" fact. A path that already writes `°` correctly is left alone.

**Rule** (`ascii.fold(text) -> tuple[str, bool]`):

1. A character in the code page, or in 7-bit ASCII, is kept.
2. Else, if `unicodedata.normalize("NFKC", ch)` is all in the code page, it replaces the character: `℃` → `°C`,
   `µ` stays (it is in Windows-1252), `Ω` (U+2126) → `Ω` (U+03A9), which is still outside, so it is refused.
3. Else the text is refused with the reason `text_problem` gives today.

A folded value is written with its `%UTF8%` twin holding the folded text, so the two twins agree. The writer
reports `altium.text-folded` (warning): the field, the source text and the written text. NFKC is in the standard
library, so it adds no dependency.

**Where it applies.**

- `record_bytes`: in place of `errors="replace"`.
- `text_problem(form="binary")`: through the fold, so the binary form accepts a text that folds.
- `edit/records._encode`: through the fold, then the code page. `ops.set_property` turns a `RecordError` into
  `Refused("altium.edit.assertion", …)`, so `Session.apply` reports it and nothing is written.

**Description.** `COMPONENTDESCRIPTION` (schematic library and sheet component) joins the comment and the
parameter values as a text that may use Windows-1252 in the binary form. It is free text, never a file, storage
or net name. The ASCII form stays 7-bit (S-0133), and its refusal names the binary form, as today.

**Evidence.** The `%UTF8%` twin and the code-page value are rows of `schematic-records.md` ("Text"),
`H-A-SCHX-TEXT`, `INFERRED`. Folding is Fenolite's choice of what to write, not a format fact, so it needs no row.
The kit check that Altium shows `°C` in a description joins the existing `H-A-SCHX-TEXT` case.

**Alternative.** Refuse every character outside the code page and leave the change to the user. That is the
current behaviour for `text_problem`, and it failed the field user on a datasheet string with one obvious
spelling. Folding changes only characters whose Unicode compatibility form is that spelling, and it says so.

## D4 F41: tidy findings and any board

**Already covered** by copper-tidy, "Style report": jogs and off-45° (`other`) joints are counted per net class
and layer, and acute joints get `tidy.acute` with a place.

**Added**:

- `tidy.jog` (info) at the middle of each jog: a track shorter than `JOG_WIDTHS` widths between two turns, the
  rule the count already uses;
- `tidy.off-45` (info) at each joint of kind `other`;
- `tidy.collinear` (info) at each point where exactly two tracks of one net, layer and width meet in a straight
  line with nothing else there. That point can be removed. `straighten` already merges such runs on a KiCad
  board. The report counts these joints as `collinear` beside `45`, `90`, `acute` and `other`.

The findings are info, so a report stays exit 0. `--format concise` folds them per code with counts, as for any
code. `JOINT_KINDS` gains `collinear`. The report's JSON gains that key, which v0 allows (`docs/cli-contract.md`,
"Stability").

**Any board.** `cmd_tidy` resolves PATH with c0495's `_boardview` resolver when `--report` or `--compare` is
given. A step on a non-KiCad board stays a usage error: "tidy steps write KiCad boards; `--report` reads any
board". The design given to `style` is the backend's model, which the Altium reader builds with tracks, arcs and
nets.

**Dependency.** c0495 (b) must land first. If it has not, task 4.2 uses `registry.for_path` directly, as c0495
D2 describes, and leaves a `shortcut:` comment that points to c0495.
