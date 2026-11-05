## MODIFIED Requirements

### Requirement: Board drawings in the DSL
`Design.text(key, text, at, *, layer="F.SilkS", size=None, thickness=None, rot=0, justify=None, knockout=False, bold=False, italic=False, face=None)`, `Design.line(key, start, end, *, layer, width, net=None)`, `Design.rect(key, start, end, *, layer, width, fill=False, net=None)`, `Design.circle(key, center, edge, *, layer, width, fill=False, net=None)`, `Design.arc(key, start, mid, end, *, layer, width, net=None)`, `Design.polygon(key, points, *, layer, width, fill=False, net=None)` and `Design.dimension(key, start, end, *, offset, layer="Dwgs.User", direction=None, units="mm", precision=4, size=None, thickness=None, width=None, extension_offset=None)` SHALL each declare one board drawing. `dsl.to_model` SHALL put one `Text`, `Graphic` or `Dimension` per drawing into `Board.texts`, `Board.graphics` and `Board.dimensions`, each in key order.
- `board()` MUST have been called first, in either of its forms. `key` MUST match `^[A-Za-z0-9_.+-]+(/[A-Za-z0-9_.+-]+)*$` and MUST NOT be the key of another drawing of the design, whichever of the seven calls made it. `Design.drawings` MUST map each key to its record, in call order.
- Points are `(x, y)` pairs of lengths in the board frame of "Board and placements in the DSL", written with `BOARD_ORIGIN` added; lengths and angles follow "DSL lengths and angles".
- `layer` MUST be a layer of the board whose kind is `silkscreen`, `soldermask`, `fabrication` or `user` (`dsl.items.DRAWING_LAYER_KINDS`), a user layer declared by `Design.user_layers` ("User layers in the DSL"), or, for a text and the five graphics (change c0277), a copper layer of `Design.copper_layers`. A line, an arc and an unfilled rectangle MAY also be on `Edge.Cuts`, where they declare explicit physical root outline edges (changes c0349, c0401; "Explicit physical root edges with a logical outline"). A copper layer for a dimension, `Edge.Cuts` for any other drawing or for a filled rectangle, or a layer of another kind MUST raise `DslError` naming the layer.
- **Copper art** (change c0277). `net` MUST be `None` or a `Net`, which joins the design, and is accepted only on a copper layer; the graphic takes the net's id as `net_id`. `knockout` MUST be a `bool`, and `True` only on a copper or silkscreen layer; the text takes it as `knockout`. Both fields are left out of the model's canonical JSON when unset. The KiCad writer SHALL write a graphic's net as `(net …)` after its `layer`, in the net form of the target. The copper check SHALL judge a graphic on a copper layer as copper of its net (of no net without one): its stroke around its outline, and its inside when it is filled; a copper text stays `copper.text-unchecked`.
- **Text.** `text` MUST be a `str` whose lines, split at `\n`, are each printable (`str.isprintable()`); an empty text is accepted, as KiCad keeps one (change c0277). `size` MUST be a positive length or a `(width, height)` pair of positive lengths, and `thickness` positive; they default to 1 mm and 0.15 mm, the values the KiCad writer gives created footprint fields. `justify` MUST be `None` or one of `dsl.part.FIELD_JUSTIFY`. `bold` and `italic` MUST be bools and `face` `None` or a printable font name; the text takes them, left out of the canonical JSON when unset.
- **Graphics.** `width` MUST be at least 0, and above 0 for a line, an arc and a shape that is not filled; a filled shape MAY take `width=None`, no outline, which the model holds as −1 nm and the KiCad writer writes as `(width -0.000001)` (change c0277). A rectangle's corners MUST differ in x and in y; a circle's `edge` MUST differ from its `center`; an arc's three points MUST be distinct and not on one line (an exact integer test); a polygon MUST hold at least three points. `fill` MUST be a `bool`.
- **Dimension.** `start` and `end` MUST differ. `offset` is a length, written as KiCad's `height`. `direction` is `None` for an aligned dimension, or `horizontal` or `vertical` for an orthogonal one, whose measured coordinate difference MUST NOT be 0. `text_at` MAY place the text by hand, written as `text_position_mode 2` with the text at that point (change c0277). `units` MUST be `mm`, `in`, `mils` or `auto` (change c0277; the codes 2, 0, 1 and 3 of the file, a created `auto` dimension caching its text in millimetres), `precision` an `int` from 0 to 4, `size`, `thickness` and `width` positive lengths or `None`, and `extension_offset` a length of at least 0 or `None` (change c0277; the model's `Dimension.extension_offset`, left out of the canonical JSON when `None`).
- Each violation MUST raise `DslError` at the call, naming the argument, and MUST record nothing.
- The model entities MUST have the ids `derived_id("txt", "dsl", "text:<key>")`, `derived_id("gfx", "dsl", "graphic:<key>")` and `derived_id("dim", "dsl", "dimension:<key>")`. A text takes `Size(size, size)` (or the pair as `Size(width, height)`), `thickness`, the rotation and the justification (`h_justify`, `v_justify`; `center` for what `justify` does not name). A graphic takes the kind `line`, `rect`, `circle`, `arc` or `polygon`, the points in the order of its call, `width` and `filled`. A dimension takes the kind `aligned` or `orthogonal`, `direction`, `units`, `precision`, and `size`, `thickness` and `width` as given (`None` meaning the backend's default).

#### Scenario: Label and fabrication line in the model
- **GIVEN** a design with `board(mm(50), mm(30))`, `d.text("rev", "REV A", (mm(2), mm(28)), justify="left bottom")` and `d.line("fab/edge", (mm(0), mm(15)), (mm(50), mm(15)), layer="F.Fab", width=mm(0.1))`
- **WHEN** `to_model(d)` runs
- **THEN** `board.texts` holds one `Text` with text `REV A`, position (102 mm, 128 mm), layer `F.SilkS`, `size == Size(1_000_000, 1_000_000)`, `thickness == 150_000`, `h_justify == "left"` and `v_justify == "bottom"`, and `board.graphics` holds one `line` on `F.Fab` from (100 mm, 115 mm) to (150 mm, 115 mm) of width 100 000 nm

#### Scenario: Dimension in the model
- **WHEN** `d.dimension("width", (mm(0), mm(0)), (mm(50), mm(0)), offset=mm(-5))` is declared on the same board and `to_model(d)` runs
- **THEN** `board.dimensions` holds one `aligned` dimension with the id `derived_id("dim", "dsl", "dimension:width")`, layer `Dwgs.User`, start (100 mm, 100 mm), end (150 mm, 100 mm), `offset == -5_000_000`, `direction is None`, `units == "mm"` and `precision == 4`

#### Scenario: Refused drawing calls
- **WHEN** `d.dimension("t1", (mm(0), mm(0)), (mm(5), mm(0)), offset=mm(1), layer="F.Cu")`, `d.rect("l1", (mm(0), mm(0)), (mm(1), mm(1)), layer="Edge.Cuts", width=mm(0.1), fill=True)`, `d.line("rev", …)` after the text `rev`, `d.arc("a1", (mm(0), mm(0)), (mm(1), mm(1)), (mm(2), mm(2)), layer="F.Fab", width=mm(0.1))`, `d.dimension("d1", (mm(0), mm(0)), (mm(0), mm(9)), offset=mm(2), direction="horizontal")`, `d.dimension("d2", …, precision=5)` and `d.text("t2", "A\tB", (mm(1), mm(1)))` are called
- **THEN** each raises `DslError`, naming `F.Cu`, `Edge.Cuts`, `rev`, the arc's points, `direction`, `precision` and `text`

#### Scenario: Copper text and text styles
- **WHEN** `d.text("cu/rev", "REV B", (mm(5), mm(5)), layer="F.Cu", knockout=True)`, `d.text("silk/wide", "WIDE", (mm(5), mm(10)), size=(mm(2), mm("1.25")), bold=True)` and `d.text("silk/lines", "A\nB", (mm(5), mm(15)), italic=True, face="KiCad Font")` are declared and the blink with them is built for targets 9 and 10
- **THEN** the model texts hold `knockout`, `Size(2_000_000, 1_250_000)` with `bold`, and `italic` with the face; the board writes `(layer "F.Cu" knockout)` and `(font (face "KiCad Font") (size 1.25 2) (thickness 0.15) (bold yes) (italic yes))` in that order for a text with every style; `issues` hold one `copper.text-unchecked`; and `d.text("t", "A", …, layer="F.Fab", knockout=True)` raises `DslError` naming `knockout`

#### Scenario: Copper text and a copper shape on a net
- **WHEN** `d.text("logo", "REV B", (mm(5), mm(5)), layer="F.Cu", knockout=True)` and `d.polygon("spreader", [(mm(10), mm(10)), (mm(20), mm(10)), (mm(20), mm(20))], layer="B.Cu", width=mm(0.2), fill=True, net=gnd)` are declared and `to_model(d)` runs
- **THEN** `board.texts` holds `REV B` on `F.Cu` with `knockout` true, `board.graphics` holds one filled polygon on `B.Cu` whose `net_id` is the id of `GND`, and `d.line("x", (mm(0), mm(0)), (mm(1), mm(0)), layer="F.SilkS", width=mm(0.1), net=gnd)` raises `DslError` naming `net`

#### Scenario: A copper shape across a pad of another net
- **GIVEN** the blink with `d.rect("cu/bad", (mm(30), mm(7)), (mm(34), mm(11)), layer="F.Cu", width=mm("0.2"), fill=True, net=gnd)` over a pad of `LED_DRV`
- **WHEN** it is built for target 10
- **THEN** the build exits 5 with `copper.short`; without the overlap the rectangle is written as `(gr_rect … (layer "F.Cu") (net "GND") (uuid …))` for target 10 and with the net's number for target 9

#### Scenario: A shaped board takes drawings
- **GIVEN** `d.board(outline=shape.rect(mm(0), mm(0), mm(50), mm(30), radius=mm(3)))`
- **WHEN** each of the seven calls `text`, `line`, `rect`, `circle`, `arc`, `polygon` and `dimension` is called once
- **THEN** none raises, `d.drawings` holds the seven keys in call order, and the blink with `board(outline=…)` writes the rule areas, texts, drawings and dimensions, with their uuids, that the same blink with `board(mm(50), mm(30))` writes

#### Scenario: Keys, not order
- **GIVEN** two designs that make the same drawing calls in opposite orders
- **WHEN** `to_model` runs on both
- **THEN** every text, graphic and dimension has the same id in both models, and the tuples are in key order
