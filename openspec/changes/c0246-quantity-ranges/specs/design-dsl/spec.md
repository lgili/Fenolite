## MODIFIED Requirements

### Requirement: Quantities in the DSL
`fenolite.dsl.quantity` SHALL provide `Quantity`, an exact value of one unit among `ohm`, `farad`, `henry`, `volt`, `ampere`, `hertz`, `watt` and `second`, and the constructors `ohm(x)`, `farad(x)`, `henry(x)`, `volt(x)`, `amp(x)`, `hertz(x)`, `watt(x)` and `second(x)`; `fenolite.dsl` SHALL re-export `Quantity` and the constructors (an addition under "DSL package").
- **Input.** `x` MUST be an `int`, a `fractions.Fraction`, or a text: a decimal number, an optional SI prefix among `p`, `n`, `u`, `µ`, `m`, `k`, `M` and `G`, and an optional symbol of the constructor's unit (`Ω`, `ohm` or `R`; `F`; `H`; `V`; `A`; `Hz`; `W`; `s`), with optional blanks between number and prefix; or the IEC 60062 letter code, where the prefix letter, or `R` for ohms, stands for the decimal point (`4k7`, `2R2`, `1n5`).
- A `float`, a `bool`, a symbol of another unit, a text that does not parse, or a negative value for a unit other than volts and amperes MUST raise `DslError` naming the input.
- **Value.** The value MUST be held as a `Fraction` of the unit. Equality, ordering and hashing MUST compare the unit and the exact value; ordering between different units MUST raise `TypeError`.
- **Arithmetic.** `+` and `-` MUST take two quantities of one unit; `*` and `/` MUST take an `int` or a `Fraction`. An operand that is a `Range` ("Ranges in the DSL") MUST give a `Range` by the rules of "Range arithmetic in the DSL", the quantity counting as the range `[q, q]` with nominal `q`. Any other operand MUST raise `TypeError`.
- **Ranges from a quantity.** `q.pct(...)`, `q.min()`, `q.max()` and `q.within(r)` MUST behave as "Ranges in the DSL" states.
- **Text.** `text()` MUST print the value scaled by the largest SI prefix, in steps of 1 000 from `p` to `G`, that keeps its magnitude at least 1 (no prefix between 1 and 1 000), as the shortest exact decimal, followed by the prefix (`u` for micro) and the symbol (`Ω`, `F`, `H`, `V`, `A`, `Hz`, `W`, `s`). A value that is not a terminating decimal at that scale MUST raise `DslError`. `text(code=True)` MUST print the IEC 60062 letter code for ohms, farads and henries, the prefix letter (or `R` without a prefix, for ohms) standing for the decimal point and no symbol, and MUST raise `DslError` for the other units.
- A quantity MUST NOT reach the model or `.fenolite/` as such: it is a script value. The one way an electrical value reaches the model is a part value given as a `Range` ("Part values from quantities"), stored as a `ValueRange` (`design-model`, "Value ranges in the circuit model").

#### Scenario: Equal forms
- **WHEN** `ohm("4k7")`, `ohm("4.7k")`, `ohm("4.7 kΩ")` and `ohm(4700)` are compared
- **THEN** they are equal, have one hash, and `text()` of each is `4.7kΩ`

#### Scenario: Canonical texts
- **WHEN** `farad("0.1u").text()`, `volt("3.30").text()`, `hertz(16_000_000).text()` and `ohm("2R2").text(code=True)` are computed
- **THEN** they are `100nF`, `3.3V`, `16MHz` and `2R2`

#### Scenario: Float refused
- **WHEN** `ohm(4.7e3)` is called
- **THEN** `DslError` is raised naming the value

#### Scenario: Wrong unit
- **WHEN** `farad("10V")` is called
- **THEN** `DslError` is raised naming `10V`

#### Scenario: A quantity with a range gives a range
- **WHEN** `volt("1") + between(volt("0"), volt("1"))` is computed
- **THEN** the result is a `Range` of unit `volt` from 1 V to 2 V without nominal

#### Scenario: Two quantities of different units still refused
- **WHEN** `volt("1") * amp("1")` is computed
- **THEN** `TypeError` is raised, as before this change

### Requirement: Part values from quantities
`Part(ref, lib_id, footprint=None, value="")` SHALL accept a `Quantity` or a `Range` as `value`; a string value MUST keep working unchanged.
- A `Quantity` MUST be stored as its `text()`, and `Part.value_range` MUST be `None`.
- A `Range` MUST have a nominal, two bounds, no negative bound for a unit other than volts and amperes, and a unit other than `ratio`; its model form MUST have exponents within −30..30 (`design-model`, "Value range object in the model"). Otherwise `DslError` MUST be raised at the call, naming the ref and the range. `Part.value` MUST be the `text()` of the nominal and `Part.value_range` the range.
- The model's `Component.value` MUST be that text, so two parts given equal quantities, or ranges with equal nominals, have equal values whatever their spelling in the script. `to_model` MUST set `Component.value_range` from `Part.value_range` (`None` when there is none).

#### Scenario: One value for two spellings
- **GIVEN** `Part("R1", "Mini:Mini_R", value=ohm("4k7"))` and `Part("R2", "Mini:Mini_R", value=ohm("4700"))` in one design
- **WHEN** `to_model` runs
- **THEN** both components have the value `4.7kΩ`

#### Scenario: A ranged value keeps the value text
- **GIVEN** `Part("R1", "Mini:Mini_R", value=ohm("10k").pct(1))` in a design
- **WHEN** `to_model` runs
- **THEN** `R1` has the value `10kΩ` and `value_range == ValueRange("ohm", Decimal10(99, 2), Decimal10(1, 4), Decimal10(101, 2))`

#### Scenario: A range without nominal is refused as a value
- **WHEN** `Part("R1", "Mini:Mini_R", value=between(ohm("9k"), ohm("11k")))` is called
- **THEN** `DslError` is raised naming `R1` and saying that a part value needs a nominal

## ADDED Requirements

### Requirement: Range values in the DSL
`fenolite.dsl.quantity` SHALL provide `Range`, a frozen exact interval with `unit` (a unit of `Quantity`, or `ratio`), `low` and `high` (`Fraction`, or `None` for an unbounded side) and `nominal` (`Fraction` or `None`). At least one bound MUST be given, `low <= high`, and a nominal MUST lie within the bounds, else `DslError`. Bounds MAY be negative. Equality and hashing MUST compare the four fields; ordering between ranges MUST raise `TypeError`. There is no solver.

#### Scenario: Ranges compare by value
- **WHEN** `Range("volt", Fraction(3), Fraction(4))` is compared with an equal range and with `Range("volt", Fraction(3), Fraction(4), Fraction("3.5"))`
- **THEN** the first pair is equal with one hash, the second is not equal, and `<` between them raises `TypeError`

#### Scenario: Inconsistent range refused
- **WHEN** `Range("volt", None, None)`, `Range("volt", Fraction(2), Fraction(1))` and `Range("volt", Fraction(1), Fraction(2), Fraction(3))` are built
- **THEN** each raises `DslError`

### Requirement: Range bounds read back
`Range.min`, `Range.max` and `Range.nominal` SHALL return the lower bound, the upper bound and the nominal as a `Quantity` (as a `Fraction` for `ratio`), or `None` for an unbounded side or a missing nominal. A negative value of a unit other than volts and amperes MUST raise `DslError` naming it.

#### Scenario: Bounds as quantities
- **GIVEN** `r = ohm("10k").pct(1)`
- **WHEN** `r.min`, `r.max` and `r.nominal` are read
- **THEN** they are `ohm("9.9k")`, `ohm("10.1k")` and `ohm("10k")`

### Requirement: Ranges from a quantity
For a quantity `q`, `q.pct(p)` SHALL give `[q − |q|·p/100, q + |q|·p/100]` with nominal `q` for `p >= 0`; `q.pct(lo, hi)` SHALL give `[q + |q|·lo/100, q + |q|·hi/100]` with nominal `q` for `lo <= 0 <= hi`; `q.pct(t)` with a `Tolerance` SHALL equal `q.pct(t.lo, t.hi)`. `q.max()` SHALL give `[0, q]` without nominal and MUST raise `DslError` for `q < 0`; `q.min()` SHALL give `[q, unbounded)`.

#### Scenario: Symmetric per-cent
- **WHEN** `volt("3.3").pct(3)` is computed
- **THEN** it equals `Range("volt", Fraction("3.201"), Fraction("3.399"), Fraction("3.3"))` and its `text()` is `3.3V (3.201V..3.399V)`

#### Scenario: Asymmetric per-cent and a tolerance value
- **WHEN** `farad("10u").pct(-20, 80)` and `farad("10u").pct(pct(-20, 80))` are computed
- **THEN** both give 8 µF to 18 µF with nominal 10 µF

#### Scenario: At most and at least
- **WHEN** `amp("1.5").max()` and `volt("4.5").min()` are computed
- **THEN** the first is 0 A to 1.5 A without nominal, the second has `low == 4.5`, `high is None` and `text()` `4.5V..`

### Requirement: Between and per-cent constructors
`between(a, b, *, nominal=None)` SHALL take two quantities of one unit with `a <= b` and an optional nominal of that unit within them. `pct(p)` SHALL give `Tolerance(-p, p)` for `p >= 0`, and `pct(lo, hi)` `Tolerance(lo, hi)` for `lo <= 0 <= hi`. A per-cent MUST be an `int`, a `Fraction` or a decimal text; a `float`, a `bool`, an unparsable text or a per-cent outside these rules MUST raise `DslError` naming it.

#### Scenario: Refused inputs
- **WHEN** `volt("3.3").pct(-1)`, `volt("3.3").pct(1.5)`, `pct(True)`, `between(volt("2"), volt("1"))`, `between(volt("1"), amp("2"))` and `volt("-1").max()` are called
- **THEN** each raises `DslError`

#### Scenario: Decimal text per-cent
- **WHEN** `ohm("100").pct("0.5")` is computed
- **THEN** it is 99.5 Ω to 100.5 Ω with nominal 100 Ω

### Requirement: Range containment
`a.within(b) -> bool` SHALL be true exactly when every value of `a` lies in `b`, an unbounded side of `b` holding every value on that side. `a` and `b` MAY each be a `Range` or a `Quantity` (as `[q, q]`) and MUST have one unit, else `TypeError`.

#### Scenario: Containment
- **GIVEN** `v33 = volt("3.3").pct(3)`
- **WHEN** `between(volt("3.25"), volt("3.35")).within(v33)`, `volt("3.4").within(v33)` and `v33.within(volt("3").min())` are computed
- **THEN** they are `True`, `False` and `True`

#### Scenario: Different units
- **WHEN** `volt("3.3").pct(3).within(amp("1").max())` is computed
- **THEN** `TypeError` is raised

### Requirement: Range text
`Range.text()` and `str()` SHALL print `<nominal> (<low>..<high>)`, or `<low>..<high>` without a nominal, each value as `Quantity.text()` prints it and a ratio as a plain decimal, an unbounded side left empty. A value that does not terminate at its prefix MUST be rounded outward (lower bound down, upper bound up, nominal to nearest, ties to even) to four significant digits and preceded by `~`. `text()` MUST NOT raise.

#### Scenario: Non-terminating text
- **WHEN** `(between(ohm("1"), ohm("2")) / ohm("3")).text()` is computed
- **THEN** it is `~0.3333..~0.6667` and no error is raised

### Requirement: Range names and documentation
`fenolite.dsl` SHALL re-export `Range`, `Tolerance`, `between` and `pct` (an addition under "DSL package"), with no new import edge. `docs/dsl.md` MUST gain a section "Ranges" with the constructors, the arithmetic and its over-estimate (a result can be wider than the true range, never narrower), the unit tables, `within()`, the text and the model form.

#### Scenario: Re-exports
- **WHEN** `python -c "from fenolite.dsl import Range, Tolerance, between, pct; print(Range.__module__)"` and `uv run pytest tests/unit/test_import_graph.py` run
- **THEN** the first prints `fenolite.dsl.quantity`, and the second passes with no `ALLOWED` change

### Requirement: Range arithmetic bounds
`Range` SHALL support `+`, `-`, `*`, `/` and unary `-` with exact worst-case bounds, operands being a `Range`, a `Quantity` (`[q, q]`, nominal `q`), an `int` or a `Fraction` (a `ratio` `[x, x]`, nominal `x`) on either side. For `a = [a0, a1]`, `b = [b0, b1]`: `a + b = [a0+b0, a1+b1]`, `a − b = [a0−b1, a1−b0]`, `−a = [−a1, −a0]`, `a·b = [min P, max P]` over the four bound products `P`, `a/b = a·[1/b1, 1/b0]`. No float MAY appear.

#### Scenario: Divider output, worst case
- **GIVEN** `vref = volt("0.8").pct(1)`, `r_top = ohm("100k").pct(1)` and `r_bot = ohm("31.6k").pct(1)`
- **WHEN** `vout = vref * (1 + r_top / r_bot)` is computed
- **THEN** `vout` is a `Range` of unit `volt` whose bounds equal, as exact fractions, `0.792 · (1 + 99000/31916)` and `0.808 · (1 + 101000/31284)`

#### Scenario: Every sampled result is contained
- **WHEN** a property test draws bounded ranges `a`, `b` and points `x` in `a` and `y` in `b`, and computes `a + b`, `a - b`, `a * b` and, when `b` excludes zero, `a / b`
- **THEN** each result contains `x + y`, `x - y`, `x * y` and `x / y` respectively

### Requirement: Range arithmetic refusals
Dividing by a range `[b0, b1]` with `b0 <= 0 <= b1` SHALL raise `DslError` naming the divisor's text, and arithmetic with an unbounded range SHALL raise `DslError` saying that an unbounded range may only be compared.

#### Scenario: Divisor holding zero
- **WHEN** `volt("1") / between(ohm("0"), ohm("10"))` is computed
- **THEN** `DslError` is raised naming `0Ω..10Ω`

#### Scenario: Unbounded operand
- **WHEN** `volt("4.5").min() + volt("1")` is computed
- **THEN** `DslError` is raised

### Requirement: Range nominal propagation
The nominal of an arithmetic result SHALL be the same operation on the operands' nominals when both have one, and `None` otherwise.

#### Scenario: Nominal of a divider
- **GIVEN** the operands of "Divider output, worst case"
- **WHEN** `vout` is computed
- **THEN** its nominal equals `0.8 · (1 + 100000/31600)`, and `vref * (1 + r_top / between(ohm("31k"), ohm("32k")))` has no nominal

### Requirement: Range unit products
`+` and `−` SHALL take operands of one unit. `*` SHALL follow the closed table `quantity.UNIT_PRODUCTS`: X·ratio and ratio·X give X; volt·ampere gives watt; ampere·ohm gives volt; ohm·farad gives second; hertz·second gives ratio (and each pair in either order). Any other pair MUST raise `TypeError` naming both units.

#### Scenario: Unit outside the table
- **WHEN** `farad("1u").pct(10) * henry("1u").pct(10)` is computed
- **THEN** `TypeError` is raised naming `farad` and `henry`

#### Scenario: Power from voltage and current
- **WHEN** `volt("5").pct(10) * amp("1").max()` is computed
- **THEN** the result has unit `watt`, low 0 and high 5.5

### Requirement: Range unit quotients
`/` SHALL follow the closed table `quantity.UNIT_QUOTIENTS`: X/X gives ratio; X/ratio gives X; volt/ohm gives ampere; volt/ampere gives ohm; watt/volt gives ampere; watt/ampere gives volt; henry/ohm gives second; ratio/second gives hertz; ratio/hertz gives second. Any other pair MUST raise `TypeError` naming both units.

#### Scenario: Ohm's law through the unit table
- **WHEN** `volt("12").pct(10) / ohm("1k").pct(5)` is computed
- **THEN** the result has unit `ampere`, low `10.8/1050` and high `13.2/950`

#### Scenario: Quotient outside the table
- **WHEN** `ohm("1k").pct(1) / volt("1")` is computed
- **THEN** `TypeError` is raised naming `ohm` and `volt`
