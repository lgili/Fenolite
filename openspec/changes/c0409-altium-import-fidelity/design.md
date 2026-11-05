# Design: c0409

The reports come from a private board conversion and stay with the coordinator. Each section names the code
path, the decision and the authored fixture. No value, name or shape of the private project is used.

## B8: a footprint's own graphics

`backends/altium/adapter/copper.footprint_items` already gives every footprint its tracks, arcs, fills and
regions as `Graphic`s in the pad frame (c0126), and `convert/altium_to_kicad.map_layers` maps their layers
(an Altium mechanical layer to a `User.<n>` row that keeps the Altium name as its user name). The loss was in
`backends/kicad/pcb.py`: a created footprint (no KiCad slots) was built from `CANONICAL_ORDER["footprint"]`,
which had no graphic heads, and `_Writer.footprint` never looked at `fp.graphics`.

- `CANONICAL_ORDER["footprint"]` gains the heads of `_fpmap.FP_GRAPHIC_HEADS` between `attr` and `pad`
  (KiCad's own order), and each `fp_*` head gets its child order. `_WRITE_FIELDS` maps them to the same
  graphic fields as board graphics.
- `_Writer.footprint` writes the graphics of a created footprint in `_write_order`, without a net (a
  footprint's graphic holds none in KiCad). A read footprint keeps its own `fp_*` children in its slots, so
  no read board changes.
- `footprint_files` derives the library footprints from the written board text, so they get the graphics
  too; `import --to python` reads those files, so it gets them as well.
- A created footprint writes no free text of its own. `write_altium` counts `footprint-graphic` and
  `footprint-text` in the census, drops each remaining text after `prepare` with the reason "a text of the
  footprint itself ... is not written", and `convert.WARNED_LOSSES` makes both kinds give `convert.lossy` when
  they lose items, without refusing. The import keeps the conversion's issues, not its report, so this
  warning is how an import says it.

Fixture: the committed blink sample (24 lines, 2 arcs, 1 circle) with one filled region and one text authored
in the test and added in memory.

## B4: rank of imported rules

The KiCad lowering names a rule `fenolite_<priority>_<slug>` and orders rules by `rulemap.rule_order`; the
`.kicad_dru` reader numbers them by position (`priority = total - index + 1`), which keeps the order but not
the numbers. The emitter `_minimums` then folded every plain one-sided rule of a declared class into
`minimum(netclass=)`. `dsl.convert._rules` writes a class minimum at priority 1, the highest, so after
c0403 F2 it governs every rule of its class, Altium's higher-ranked pairwise rules included.

- `_ranked` gives each rule the number of its written name when every rule has one and the numbers give the
  file's order within each kind; otherwise it keeps the reader's numbers. A conversion from Altium keeps
  Altium's numbers this way (they are per kind there, and KiCad orders within a kind only).
- `_foldable` folds a rule into a minimum only where the minimum keeps its rank: a board minimum (priority 0,
  written first) for the first rule of its kind when no other has priority 0, a class minimum (priority 1,
  written last) for the last rule of its kind when no other has priority 1. Any other one-sided rule is
  `rule(where=select.netclass(...))` without `between`, with its priority.
- This agrees with c0403 F2: the statement there ("a class minimum governs every rule of its class") is why a
  class rule ranked below another rule of its kind must not become a minimum. The Specctra rule order of
  c0403 F8 reads the model rules in the same `rule_order`, so both see one ranking.

Fixture: the blink example with a pairwise clearance (priority 1) and a class x All clearance (priority 2),
built for Altium by Fenolite, imported and built again for KiCad.

## B5: PolygonConnect

`backends/altium/connectstyle.read_connect_styles` and `governing_connection` already read the records and
resolve the record governing a pad against a polygon (c0140 write side). `prepare` reads them from the
board's `polygon_connect` pairs before `_clean` empties `ext`, sets each zone's `settings.connection`,
`thermal_gap` and `thermal_spoke_width` from the record governing a pad of the zone's net, and sets
`Pad.zone_connection` where a narrower record governs a pad differently. A per-pad gap or spoke width has no
KiCad field: such a pad is reported as a `rule` change. The DSL emitter already writes zone settings that
differ from the defaults and gains `zone_connection` of a pad.

## B6: zone clearance

The polygon record holds no clearance; the governing value is the Altium clearance rule that applies to the
polygon and the items it pours around (`pcb-pour.md`). `prepare` sets `settings.clearance` from the first
clearance rule, in Altium's order, whose scopes match the zone's net on one side and any item on the other,
the same precedence `backends/altium/pour.Clearances` uses (that file is not edited).

## B9: models on the board

`write_altium` computes the placements before `write_triad` and sets each placed footprint's `models`, which
the board writer writes with `with_models`. The library footprints keep theirs. The import copies the
`.3dshapes` files of the conversion next to its vendored library and points the model paths there.

## B7: netless items

Model v1 must stay input-compatible with the frozen v0 schema (`tests/unit/test_schema_drift.py`), and a new
selector op would change its `op` enum. So the selector is built from the frozen ops: `model.rules.NO_NET` is
`not(net "*")`, which matches exactly the items whose net is `None`, because a net glob never matches an
absent net. `select.no_net()` gives it, `InNet('No Net')` maps to it, the emitter writes it back as
`select.no_net()`, and KiCad lowers it to `A.NetName == ''`, never to a negated glob. The
fact that Altium names the absent net "No Net" in a query is recorded in `docs/formats/altium/rule-file.md`
from Altium's public query documentation.

## B10: project parameters and special strings

`ProjectInput` gains the `[Parameter<n>]` entries; `import_project` puts them in the board's title block
parameters, which the KiCad writer writes as text variables. A board text that is exactly `.NAME` or `=NAME`
of a project parameter becomes `${NAME}`; a predefined special string is left as written and reported as a
`text` change. The facts come from Altium's public special-string documentation.

## B11: render page

`backends/kicad/plot.svg_arguments` gains `--exclude-drawing-sheet --page-size-mode 2` (board area only)
when the board's bounding box is not inside the sheet, or when `render --page board` asks for it;
`--page sheet` keeps the drawing sheet. kicad-cli 9 and 10 take both flags (`pcb export svg --help`).
