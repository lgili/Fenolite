# Units and conversions

Evidence label for this page: **INFERRED** (from public documentation) until the hypotheses at the
bottom are confirmed on corpus files.

## Fenolite model units

| Quantity | Unit | Type |
|---|---|---|
| length, coordinate | nanometre (nm) | `int` |
| angle, rotation | microdegree (µdeg) | `int` |

`fenolite.core.units.parse_length("0.25mm") == 250_000`; values that are not an exact number of
nanometres are rejected. Length units accepted: `nm`, `um`/`µm`, `mm`, `cm`, `m`, `mil`/`thou`
(25 400 nm), `in` (25 400 000 nm). Angle units: `deg`, `udeg`/`µdeg`.

## KiCad board and footprint files

- Lengths are written in millimetres; the internal resolution is 1 nm, so every length in a file is
  an exact number of nanometres (S-0001).

## The second backend's binary PCB files

- Lengths are integers in units of 1/10 000 mil; one unit is 2.54 nm, i.e. `nm = u × 127 / 50`
  (S-0002).

### Conversion (integer-only, round half to even, symmetric)

```
u_to_nm(u)  = round_half_even(u × 127 / 50)
nm_to_u(nm) = round_half_even(nm × 50 / 127)
```

| Direction | Ties (exact .5 results) | Largest error |
|---|---|---|
| u → nm | whenever `u ≡ 25 (mod 50)`: `u = ±25 → ±64`, `u = ±75 → ±190`, `u = ±125 → ±318` | 0.5 nm |
| nm → u | never (127 is odd) | 1.26 nm |

Whole multiples convert exactly: `u_to_nm(50) = 127`, `nm_to_u(127) = 50`, 10 mil = 254 000 nm =
100 000 u. Because the conversion is lossy by up to 1.26 nm, importers keep the original integers
of untouched objects in `ext` and writers prefer them.

## The second backend's schematic files

- A schematic length is an integer number of units of 10 mil plus an optional fraction in 1/100 000 of a
  unit (S-0130, S-0131). `SchLength.value` holds it as one integer count of 1/100 000 unit, 2.54 nm per
  step, the same step as the binary PCB unit: `nm = value × 127 / 50`, rounded half to even, exact for
  every multiple of 50.
- Connectivity is computed on `SchLength.value`, never on nanometres, so no rounding enters a connection.

## Import rules of the second backend (change c0043)

- A binary PCB length becomes `u_to_nm(u)`. A length written as text (`10mil`, `1.27mm`) is parsed as an
  exact fraction and rounded half to even.
- The model's Y axis points down and Altium's up: a PCB point `(x, y)` becomes `(u_to_nm(x), −u_to_nm(y))`.
  No origin is subtracted. A point of a schematic library keeps its sign on both axes.
- A stored angle `d` (a double, degrees, counter-clockwise) becomes `round_half_even(Fraction(d) × 10^6)`
  microdegrees, reduced to one turn. It is exact when the double nearest to the result is `d`.
- The original value of an inexact conversion is kept in the entity's `altium` bag (`u`, `deg`); an exact
  one leaves no pair. `altium.import.inexact` counts them once per import.

## Hypotheses

`H-K-UNIT`, `H-A-UNIT`, `H-G-ANGLE` in `../hypotheses.md`.
