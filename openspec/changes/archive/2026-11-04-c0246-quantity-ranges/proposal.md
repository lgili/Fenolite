## Why

A real 10 kΩ resistor is 9.9 kΩ to 10.1 kΩ, a 3.3 V rail is
3.201 V to 3.399 V, and a feedback divider sets its output only within the tolerance of its resistors.
Fenolite holds values exactly today: `ohm("10k")` is one `Fraction`, and "Quantities in the DSL" keeps
every quantity out of the model. So no check can ask "is this divider's output inside the rail's
window?", and the later changes (electrical contracts c0253, parametric interfaces c0252,
part selection and generators c0254) have nothing to compare.

The research `docs/research/circuit-as-code.md`, section 2 and core change A, found that atopile makes
every value a range and that JITX does worst-case arithmetic on toleranced values; both use floats, and
atopile hides the arithmetic in a constraint solver. Fenolite takes only the concept: exact ranges,
worst-case arithmetic, comparisons, and no solver.

## What Changes

- **`Range` in `fenolite.dsl.quantity`.** An exact interval of one unit: a lower and an upper bound
  (`Fraction`, or unbounded on one side) and an optional nominal. Built at the DSL boundary only:
  - `volt("3.3").pct(3)`, `ohm("100k").pct(1)`, asymmetric `farad("10u").pct(-20, 80)`;
  - `between(volt("3"), volt("3.6"))`;
  - `amp("1.5").max()` (0 to 1.5 A) and `volt("4.5").min()` (4.5 V and up);
  - `pct(5)`, a `Tolerance` value that later changes take as a default or a derating.
- **Worst-case arithmetic.** `+`, `-`, `*`, `/` on ranges, quantities and exact numbers give the exact
  interval that holds every result, with a closed table of unit products and quotients (V/Ω is A,
  Ω/Ω is a ratio). Division by a range that holds zero is refused. There is no solver.
- **Comparison.** `vout.within(v33)` answers whether one range lies inside another; `.min`, `.max` and
  `.nominal` read the bounds back as quantities.
- **Part values with a tolerance.** `Part(..., value=ohm("10k").pct(1))` writes the nominal text
  (`10kΩ`) as today and records the range.
- **Ranges in the model.** A new value object `ValueRange` (unit, low, nominal, high, each an exact
  decimal as integer mantissa and exponent, rounded outward to 15 digits; 0.1 mΩ to 10 TΩ, 0.1 pF to
  3 000 F fit) and `Component.value_range`, stored in `circuit.json`
  only when set. The written KiCad and Altium files do not change.

## Capabilities

### Modified Capabilities

- `design-dsl`: MODIFIED "Quantities in the DSL" and "Part values from quantities"; ADDED seven
  requirements on range values, constructors, containment, text and names, and five on arithmetic.
- `design-model`: ADDED five requirements on `ValueRange`, its units, outward rounding, the component
  field and backend files.

## Non-goals

- No solver, no equation restated "for the solver", no unknown to solve for.
- No check that reads the ranges: ratings, rails and `expect()` are c0253. No zero-tolerance warning
  (c0253 decides it).
- No ranges on net roles, interfaces or rails (c0252, c0253), and no tolerance field written to KiCad.
- No floats anywhere, and no new runtime dependency.

## Evidence level required

- Arithmetic, rounding and text: unit and property tests against `fractions.Fraction`; no external
  evidence is needed, since nothing here is a fact about a format or a part.
- Builds: `KICAD-VERIFIED` that a design with ranged values writes the same KiCad files, byte for
  byte, as the same design with exact values; only `.fenolite/circuit.json` differs.

## Impact

- Changed: `src/fenolite/dsl/quantity.py` (`Range`, `Tolerance`, `between`, `pct`), `dsl/part.py`,
  `dsl/convert.py`, `dsl/__init__.py`, `src/fenolite/model/circuit.py` (`ValueRange`,
  `Component.value_range`), `schemas/fenolite.model.v0/circuit.json` (regenerated), `docs/dsl.md`,
  `docs/design-model.md`, the agent guide pages `parts` and `dsl-reference` (generated),
  `CHANGELOG.md`.
- Tests: `tests/unit/dsl/test_range.py` (new), `tests/unit/dsl/test_quantity.py`,
  `tests/unit/model/test_value_range.py` (new), a build test in `tests/unit/lens/`.
- Dependencies: none. First of the batch c0246 to c0258; c0247 is implemented with it; c0252, c0253 and
  c0254 build on `Range` and `ValueRange`.
- Size: about 4 design-days.
