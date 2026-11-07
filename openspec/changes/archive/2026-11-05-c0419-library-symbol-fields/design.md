# Design: c0419

Base: `origin/cac/lote-22` (c54e884b).

## Model

```python
@dataclass(frozen=True, slots=True)
class SymbolField:
    name: str                                  # Reference, Value, Footprint, Datasheet or Description
    at: Point                                  # symbol frame, Y up, nanometres
    rotation: int = 0                          # microdegrees, 0 or 90 000 000
    justify: Literal["", "left", "right"] = "" # "" is centred
    hidden: bool = False

SymbolDef.fields: tuple[SymbolField, ...] = ()  # ordered as written
```

Only standard fields: other properties are written hidden at the origin today and stay so.

## Pins record

```toml
[symbol]
reference = "R"
fields = [
  { name = "Reference", at = ["2.54mm", "1.27mm"], justify = "left" },
  { name = "Value", at = ["2.54mm", "-1.27mm"], justify = "left" },
  { name = "Footprint", at = ["0mm", "0mm"], hide = true },
]
```

- `name` one of the five standard fields, unique; `at` a point; `rotation` an angle, `0deg` or `90deg`
  (KiCad shows field text horizontal or vertical); `justify` `left`, `right` or absent; `hide` a boolean.
- Canonical text: `fields = [...]` after `pin_numbers_hidden`/`pin_name_offset`/`units` and before `pins`,
  each entry with `name` and `at`, then `rotation`, `justify` and `hide` only when not default.
- The record digest changes only for records that add `fields`.

## Writer

```text
(property "Reference" "R"
    (at 2.54 1.27 0)
    (effects (font (size 1.27 1.27)) (justify left))
)
(property "Footprint" ""
    (at 0 0 0)
    (effects (font (size 1.27 1.27)) (hide yes))
)
```

- Placed: `(at x y r)` with r in degrees; effects `(justify left|right)` when set, `(hide yes)` when hidden.
- Not placed: today's line (`(at 0 y 0)`, `(justify left)`, shown).
- A derived symbol writes only the properties it has, as today; its own placed fields follow the same rule.

A line of n ≥ 2 points: `(polyline (pts p1 … pn) …)`. For n = 2 that is today's text.

## Proof

- Unit: bytes unchanged without `fields`; placed and hidden fields written; record parse, refusal of an
  unknown or repeated name, canonical round trip; a three-point line keeps every point.
- KiCad 10.0.6 (`needs_kicad`): `sym export svg` plots the library; `sym upgrade --force` saves it and the
  saved file holds each property at its `at` with its `hide`, and the polyline's three points.

## Decisions

- 2026-11-05: placement is explicit per record, not computed: a computed default would change the bytes of
  every symbol that design builds embed.
- 2026-11-05: G-5 is fixed in the writer (all points), not by refusing longer lines in the parser: the record
  form already allows them and the author's intent is clear.
