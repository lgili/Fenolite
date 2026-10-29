## Context

`src/fenolite/dsl/quantity.py` (change c0073) gives `Quantity`, an exact `Fraction` of one of eight units
(`ohm`, `farad`, `henry`, `volt`, `ampere`, `hertz`, `watt`, `second`), with `+`/`-` between quantities of
one unit and `*`/`/` by an `int` or a `Fraction`. A part stores `Quantity.text()` as its value, and the
living requirement "Quantities in the DSL" says that no quantity reaches the model. Net roles (c0222)
store a current and a voltage as whole mA and mV, the only electrical values in the model today.

The research page `docs/research/circuit-as-code.md`, section 2 and core change A, proposes ranges:

```python
v33 = volt("3.3").pct(3)  # 3.201 V .. 3.399 V
r_top = ohm("100k").pct(1)
ripple = between(mv(0), mv(30))
i_load = amp("1.5").max()  # 0 .. 1.5 A
vout = vref * (1 + r_top / r_bot)  # worst-case range arithmetic, exact
vout.within(v33)  # -> bool, used by checks (section 7)
```

Concepts come from atopile (every literal is a range; `3V to 3.6V`) and JITX (a min/typ/max toleranced
value with worst-case arithmetic). Neither's code, grammar or names are taken; both use floats, and
atopile resolves ranges with a solver that its own users find hard to follow. Fenolite keeps exact
integers and fractions and does arithmetic only.

This change is first in the batch's order (with c0247). Later changes read what it adds:

| change | uses |
|---|---|
| c0248 device-catalog | `Range` for device ratings (`vin = { max = "6V" }` parses to `volt("6").max()`) |
| c0252 parametric-interfaces | `Range` for interface parameters (rail voltage, current), `ValueRange` in the model |
| c0253 electrical-contracts | `within()`, `Tolerance` (derating), `Component.value_range` |
| c0254 parametric-part-selection | `Tolerance` defaults, range arithmetic in generators (divider) |
| c0256 design-testing | `within()` in assertions over the model |

## Goals / Non-Goals

**Goals**
- An exact `Range` with worst-case `+ - * /`, a closed unit table, `within()`, and readable text.
- Constructors at the DSL boundary: `Quantity.pct()`, `Quantity.min()`, `Quantity.max()`, `between()`,
  `pct()`.
- Part values given as a range keep today's value text and record the range in the model.
- No change to any written KiCad or Altium file.

**Non-Goals**
- A solver, unknowns, or equations solved backwards.
- Checks that read ranges (c0253), ranges on roles, interfaces and rails (c0252), statistical
  (root-sum-square) tolerance stacking, temperature coefficients.
- New quantity units. A dimensionless ratio exists only as the unit of a `Range`.

## Decisions

### 1. `Range` is a frozen value of one unit with exact bounds

```python
@dataclass(frozen=True, slots=True)
class Range:
    unit: str  # a unit of UNITS, or "ratio"
    low: Fraction | None  # None: unbounded below
    high: Fraction | None  # None: unbounded above
    nominal: Fraction | None = None
```

- At least one bound is given; `low <= high`; a nominal lies within the bounds. Otherwise `DslError`.
- Bounds may be negative for every unit: `r_top - r_bot` is a valid intermediate. Reading a negative
  bound of an unsigned unit back as a `Quantity` (`.min`, `.max`, `.nominal`) raises `DslError`, and a
  part value or model lowering refuses it.
- Equality and hashing compare all four fields. There is no ordering between ranges (`<` raises
  `TypeError`): "is A below B" has three answers for intervals, and `within()` asks the useful question.
- `.min`, `.max`, `.nominal` return a `Quantity` (a `Fraction` for a ratio), or `None` when unbounded or
  without nominal. The fields `low` and `high` hold the raw fractions.

*Alternatives.* Integer bounds in a fixed sub-unit inside the DSL: rejected, `r_top / r_bot` gives
non-terminating fractions that must stay exact until the model boundary. A min/typ/max triple with a
mandatory typical value: rejected, `between(volt("3"), volt("3.6"))` has no meaningful nominal. Floats:
forbidden by the project.

### 2. Constructors

| call | range |
|---|---|
| `q.pct(p)` | `[q - abs(q)·p/100, q + abs(q)·p/100]`, nominal `q`; `p >= 0` |
| `q.pct(lo, hi)` | `[q + abs(q)·lo/100, q + abs(q)·hi/100]`, nominal `q`; `lo <= 0 <= hi` |
| `q.pct(t)` with `t = pct(...)` | as above, from a `Tolerance` |
| `q.max()` | `[0, q]`, no nominal; `q >= 0`, else `DslError` (use `between`) |
| `q.min()` | `[q, unbounded)`, no nominal |
| `between(a, b, *, nominal=None)` | `[a, b]`; two quantities of one unit, `a <= b` |
| `pct(p)` / `pct(lo, hi)` | a `Tolerance(lo, hi)` of exact per-cent fractions, no unit |

- A per-cent is an `int`, a `Fraction` or a decimal text (`"0.5"`); a float or a bool is refused, as
  for quantities.
- `Tolerance` exists now so that c0253 (`derating(capacitor_voltage=pct(50))`) and c0254
  (`defaults(resistor={"tolerance": pct(1)})`) take one type; in this change only `Quantity.pct` reads it.
- A `Quantity` stays exact and is not a range. Where a range is expected, a quantity counts as the
  degenerate range `[q, q]` with nominal `q`.

*Alternative.* Writing `q.max()` as `at_most(q)`: shorter in prose, but the research and the batch use
`.max()`; open question 1.

### 3. Worst-case arithmetic, exact

For `a = [a0, a1]`, `b = [b0, b1]` (bounded):

- `a + b = [a0 + b0, a1 + b1]`; `a - b = [a0 - b1, a1 - b0]`; `-a = [-a1, -a0]`;
- `a * b = [min(P), max(P)]` with `P = {a0·b0, a0·b1, a1·b0, a1·b1}`;
- `a / b = a * [1/b1, 1/b0]`, refused with `DslError` naming the divisor when `b0 <= 0 <= b1`.

The nominal of a result is the operation on the nominals when both operands have one, and `None`
otherwise. Operands may be `Range`, `Quantity`, `int` or `Fraction` on either side (`1 + r_top / r_bot`
works); an `int` or `Fraction` is a ratio. Arithmetic on an unbounded range raises `DslError`: it may only
be compared (`within`), which keeps the rules free of infinities.

The result is exact (Python fractions); dependent operands are not detected, so `r / r` gives a range
wider than `[1, 1]`. This is the known over-estimate of interval arithmetic and is always on the safe
side; the generators of c0254 that need tight results compute them from their own formula.

### 4. Closed unit table

`+` and `-` take one unit (a ratio with a ratio). `*` and `/` follow a closed table in
`quantity.UNIT_PRODUCTS` and `quantity.UNIT_QUOTIENTS`; any other pair raises `TypeError` naming both
units.

| `*` | gives | `/` | gives |
|---|---|---|---|
| X · ratio, ratio · X | X | X / X | ratio |
| volt · ampere | watt | X / ratio | X |
| ampere · ohm | volt | volt / ohm | ampere |
| ohm · farad | second | volt / ampere | ohm |
| hertz · second | ratio | watt / volt | ampere |
| | | watt / ampere | volt |
| | | henry / ohm | second |
| | | ratio / second | hertz |
| | | ratio / hertz | second |

These are definitions of SI derived units (Ohm's law, P = V·I, τ = RC = L/R, f = 1/t), not engineering
data. The table can grow in a later change; it never guesses a unit.

### 5. `within()` and text

- `a.within(b) -> bool` is true when every value of `a` lies in `b` (`b.low <= a.low` and
  `a.high <= b.high`, an unbounded side of `b` holding everything). Both must have one unit, else
  `TypeError`. `Quantity.within(b)` is the same for `[q, q]`.
- `text()` prints `<nominal> (<low>..<high>)`, or `<low>..<high>` without a nominal, with each bound as
  `Quantity.text()` prints it (`3.3V (3.201V..3.399V)`); an unbounded side is left empty (`4.5V..`). A
  ratio prints as a plain decimal. A bound that is not a terminating decimal at its prefix is rounded
  outward (low down, high up; nominal to nearest, ties to even) to four significant digits and prefixed
  with `~` (`~1.333`). `text()` never raises, so messages can always quote a range. `str()` is `text()`.

### 6. Part values with a range

`Part(ref, lib_id, footprint, value=ohm("10k").pct(1))` sets `Part.value` to `nominal.text()` (`10kΩ`,
exactly what `value=ohm("10k")` gives today) and `Part.value_range` to the range. A range without a
nominal, unbounded, or with a negative bound for an unsigned unit is refused at the call; a ratio is
refused. Strings and quantities keep working unchanged.

*Alternative.* Writing the tolerance into the value text (`10kΩ 1%`): it changes the KiCad Value field
and the BOM of every existing design that adopts ranges; rejected for this change, open question 2.

### 7. `ValueRange` in the model: exact decimals as (mantissa, exponent)

`fenolite.model.circuit` gains two value objects (no id, no entity header, like `PinRef`):

```python
@dataclass(frozen=True, slots=True)
class Decimal10:  # the value m · 10^e, in the unit of the range
    m: int  # |m| <= 10^15 - 1 (15 significant digits, below 2^53)
    e: int  # -30 <= e <= 30


RangeUnit = Literal["ohm", "farad", "henry", "volt", "ampere", "hertz", "watt", "second"]


@dataclass(frozen=True, slots=True)
class ValueRange:
    unit: RangeUnit
    low: Decimal10 | None = None
    nominal: Decimal10 | None = None
    high: Decimal10 | None = None
```

and `Component.value_range: ValueRange | None = None`, the last field of `Component`.

- **Canonical form.** `m` has no trailing zero digit (`m % 10 != 0`), and zero is `Decimal10(0, 0)`, so
  one value has one form and one byte sequence. `10kΩ ±1%` is stored as
  `{"unit": "ohm", "low": {"m": 99, "e": 2}, "nominal": {"m": 1, "e": 4}, "high": {"m": 101, "e": 2}}`.
- **Exactness.** Every terminating decimal with at most 15 significant digits is stored exactly. Any
  other value (a non-terminating fraction, or more digits) is rounded outward to 15 significant digits:
  `low` down, `high` up, the nominal to nearest with ties to even, so the stored interval always contains
  the exact one. Every integer stays below 2⁵³, so a JSON reader that uses doubles (the viewer) reads it
  exactly.
- **Magnitude.** With `e` in −30..30, a value of any unit runs from 10⁻³⁰ to about 10⁴⁵ at full
  precision. A value outside raises `DslError` at the `Part` call, naming the value.
- `Decimal10` and `ValueRange` raise `ValueError` for a non-canonical or out-of-bounds pair, no bound,
  `low > high`, or a nominal outside the bounds (compared as exact fractions). `canonical` omits
  `value_range` when it is `None`, so every existing `circuit.json` keeps its bytes; `SCHEMA_VERSION`
  stays `"0"` and `schemas/fenolite.model.v0/circuit.json` is regenerated.
- No backend writes or reads `value_range`: a KiCad or Altium build keeps it in `.fenolite/` only, and a
  board read from KiCad without `.fenolite/` has `None`.

**Ranges each quantity must cover.** All of them fit with 15 significant digits of resolution:

| quantity | smallest useful value | largest useful value | decades | covered |
|---|---|---|---|---|
| resistance | 0.1 mΩ (current shunt) | 10 TΩ (insulation) | 17 | yes |
| capacitance | 0.1 pF (RF trim) | 3 000 F (supercapacitor) | 16.5 | yes |
| inductance | 0.1 nH (trace, RF) | 10 H (mains choke) | 11 | yes |
| voltage | 1 µV (sense offset) | 50 kV (insulation test) | 10.7 | yes |
| current | 1 pA (leakage) | 10 kA (pulse, busbar) | 16 | yes |
| frequency | 1 mHz | 100 GHz | 14 | yes |
| power | 1 nW | 100 kW | 14 | yes |
| time | 1 fs | 10⁶ s | 21 | yes |

**Why not one fixed sub-unit per quantity.** A fixed integer scale covers at most 15.9 decades below
2⁵³. Resistance (17 decades), capacitance (16.5), current (16) and time (21) do not fit: µΩ stops at
9 GΩ, mΩ loses the 0.5 mΩ shunt; fF stops at 9 F, pF loses 0.5 pF parts. The mantissa and exponent pair
covers every quantity with one rule and one table-free reader.

*Alternatives.* A fixed sub-unit per quantity (above): rejected, it cannot cover the table. Decimal
strings (`"9.9k"`): exact, but the model stores integers only and string order is not numeric order. A
numerator and denominator pair: exact, but unreadable in a diff (`1/3` is fine, `990000/99` is not) and
unbounded in size. Big integers beyond 2⁵³ at a fixed scale: lose exactness in JavaScript readers.

### 8. Files and public API

- `src/fenolite/dsl/quantity.py`: `Range`, `Tolerance`, `between`, `pct`, `UNIT_PRODUCTS`,
  `UNIT_QUOTIENTS`; `Quantity.pct`, `Quantity.min`, `Quantity.max`, `Quantity.within`, and the
  reflected operators with a `Range`.
- `src/fenolite/dsl/__init__.py` re-exports `Range`, `Tolerance`, `between` and `pct` (an addition under
  "DSL package").
- `src/fenolite/dsl/part.py`: `Part.value_range`; `dsl/convert.py` lowers it with `range_to_model()`.
- `src/fenolite/model/circuit.py`: `Decimal10`, `ValueRange`, `RangeUnit`, `Component.value_range`.

## Evidence level per behaviour

| behaviour | level before merge |
|---|---|
| arithmetic, rounding, text, constructors | unit tests and property tests against `Fraction` (no label: no external fact) |
| model round trip, schema | unit tests, `tools/gen_schemas.py --check` |
| unchanged KiCad files | `KICAD-VERIFIED`: build of the blink with and without ranges, equal SHA-256 outside `.fenolite/`, and `kicad-cli` ERC/DRC as for any build |

## Risks / Trade-offs

- **Interval over-estimate** for dependent operands (Decision 3). Mitigation: documented, always safe;
  exact formulas belong in generators (c0254).
- **Unit table too small.** A product outside it is a `TypeError` that names the units; extending the
  table is additive.
- **Name clash** between `Quantity.max()` (a constructor) and `Range.max` (a bound). Mitigation: the
  docs and the guide show both; open question 1.
- **15 significant digits.** A value with more digits is widened outward by at most one unit in the
  fifteenth digit; no part value needs more. Mitigation: documented; the containment is preserved.

## Open Questions

1. Keep `q.max()` / `q.min()` as named in the research, or call them `q.at_most()` / `q.at_least()` to
   avoid the clash with `Range.max`? *Recommended:* keep `max()`/`min()`, as the batch's other proposals
   already write them; revisit before 1.0 if users stumble.
2. Should a ranged part value print its tolerance in the KiCad Value field (`10kΩ 1%`) or in a separate
   `Tolerance` field? *Recommended:* neither in this change; decide in c0248 with the BOM, where MPN and
   tolerance columns are designed together.
3. Is 15 significant digits and an exponent range of −30..30 the right bound? *Recommended:* yes; it
   keeps every integer below 2⁵³ and covers every quantity of the table in Decision 7 with room to spare.
4. Should `Range` offer an absolute tolerance (`volt("3.3").plus_minus(volt("50m"))`)? *Recommended:* not
   yet; `between(q - d, q + d, nominal=q)` covers it, and c0252 can add it if interface tables need it.
