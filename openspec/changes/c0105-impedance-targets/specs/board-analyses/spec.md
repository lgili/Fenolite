## ADDED Requirements

### Requirement: Impedance estimates
`fenolite.analysis.impedance` SHALL estimate the quasi-static impedance of single-ended lines with closed forms from public sources, under the rules of "Analysis package and report" (pure functions, `decimal`, no `float`).
- `microstrip_mohm(width, height, thickness, epsilon_r) -> int` MUST compute the one-formula microstrip form of 1977 with its thickness correction, as the source S-0641 states it, with `Z_VACUUM_OHM = Decimal("376.730313412")` (S-0643).
- `stripline_mohm(width, spacing, thickness, epsilon_r) -> int` MUST compute the thick-strip form for a strip centred between two planes `spacing` apart, as the source S-0642 states it; `stripline_in_range(…)` MUST be true only inside the condition under which S-0642 claims its accuracy.
- `offset_stripline_mohm(width, below, above, thickness, epsilon_r) -> int` MUST combine the centred lines of spacings `2·below + thickness` and `2·above + thickness` in parallel, `2·Z₁·Z₂ / (Z₁ + Z₂)`, as S-0642 describes.
- Lengths MUST be `int`s of nanometres above 0, `thickness` below `height` or `spacing`, and `epsilon_r` the decimal text of a number of at least 1; anything else MUST raise `ValueError`. Results MUST be computed in a local context of 40 digits and returned in milliohms, rounded half to even.
- `dielectric_between(stackup, layer, reference) -> Dielectric | None` MUST take the entries of c0101's `Stackup.between(upper, lower)` for the two copper layers in stack order, and give the summed thickness of its dielectric entries, their permittivity combined in series (`h / Σ(hᵢ / εᵢ)`) as decimal text, whether their permittivities differ, and whether a copper entry lies between; a layer absent from the stack-up or a dielectric entry without `epsilon_r` MUST give `None`.
- `estimate(stackup, layers, geometry) -> Estimate` MUST use the microstrip form for one reference on an outer copper layer and the stripline form for two references on an inner layer (the centred form when the two heights are equal). `Estimate` MUST hold `mohm`, `form`, `in_range`, `heights`, `epsilon_r`, `mixed` and `reason`; for a differential geometry, any other structure or a missing input, `mohm` MUST be `None` and `reason` MUST name the cause (`differential`, `structure`, `stackup`). `solve_width(target_mohm, …)` MUST return the multiple of 1 µm whose estimate is nearest the target, the lower width on a tie.
- `analysis.impedance.EVIDENCE` MUST be `Evidence(Level.INFERRED, hypotheses=("H-G-AN-ZMS", "H-G-AN-ZSL"))`; `fenolite.analysis.EVIDENCE` is unchanged. No default thickness, height, permittivity or impedance MUST exist ("No shipped requirement values").

#### Scenario: Microstrip of the bench
- **WHEN** `uv run pytest tests/unit/analysis/test_impedance.py -k microstrip` calls `microstrip_mohm(350_000, 200_000, 35_000, "4.3")`
- **THEN** the result is within 1 mΩ of the same form computed in the test with `math` (about 50 763 mΩ)

#### Scenario: Stripline against the exact thin strip
- **GIVEN** widths from 0.1 to 2 times the spacing and a thickness of 10⁻⁶ of the spacing
- **WHEN** `stripline_mohm` is compared with the exact zero-thickness value `30π/√εr · K(k)/K(k′)`, `k = sech(π·w / (2·spacing))`, computed in the test
- **THEN** every pair differs by less than 1 %

#### Scenario: Offset form at equal heights
- **WHEN** `offset_stripline_mohm(150_000, 182_500, 182_500, 35_000, "4.3")` and `stripline_mohm(150_000, 400_000, 35_000, "4.3")` are computed
- **THEN** they are equal

#### Scenario: No estimate for a pair
- **GIVEN** a differential geometry on `F.Cu` over `In1.Cu`
- **WHEN** `estimate` is called
- **THEN** it returns an `Estimate` whose `mohm` is `None` and whose `reason` is `differential`

### Requirement: Impedance formula sources are recorded
`docs/analyses.md` SHALL hold the table "Impedance formulas" with one row per named constant of `fenolite.analysis.impedance` (`Z_VACUUM_OHM` and each number of the two forms): its name, value, unit, a source id registered in `docs/evidence/sources.md`, the label `INFERRED` and a hypothesis id. The page MUST state, in Fenolite's own words, each form's claimed accuracy and range, and what the forms leave out: solder mask, etch angle, frequency, loss and copper roughness. `src/fenolite/analysis/PROVENANCE.md` MUST hold a row per source (S-0641, S-0642, S-0643), facts only: each form is re-derived and written in Fenolite's own code, and no text of a source is copied.

#### Scenario: Table equals the code
- **WHEN** `uv run pytest tests/unit/analysis/test_facts_page.py -k impedance` parses the table "Impedance formulas"
- **THEN** every named constant of `fenolite.analysis.impedance` has exactly one row with an equal value, a registered source id, the label `INFERRED` and a registered hypothesis id
