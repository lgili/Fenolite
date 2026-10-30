# Value codes of ordering-code grammars

The grammar families of change c0263 (`fenolite.family.v1`, [`docs/picking.md`](../../picking.md),
"Families with ordering codes") spell the value of a part in one of four schemes, implemented by
`fenolite.pick.grammar.valuecodes`. This page records each rule, its public source and its evidence label.
Every source is registered in [`docs/evidence/sources.md`](../../evidence/sources.md); no table of any
source is copied or transcribed (the E96 values come from Fenolite's own `pick.series.SERIES`, S-0940), and
no paywalled standard was read.

## Facts from public sources

| fact | source | label |
|---|---|---|
| A chip resistor value is marked with 2 or 3 significant digits followed by one multiplier digit, the number of zeros (472 = 4700 Ω, 1331 = 1330 Ω, 330 = 33 Ω) | S-0971; S-0942 (marking section: "first two digits for significant figure and 3rd digit for number of zeros", the same with three digits) | INFERRED |
| Lower values use `R` as the decimal point (4R7 = 4.7 Ω, 34R8 = 34.8 Ω) | S-0971 | INFERRED |
| A capacitance code in pF is two significant digits and the number of zeros | S-0943 (ordering information, "Capacitance Code (pF)") | INFERRED |
| The EIA-96 code is two digits, the position 01 … 96 of the value in the E96 series, followed by one multiplier letter (88A = 806 × 10⁰ Ω, 07B = 1.15 kΩ) | S-0971; S-0942 (88A = 806 Ω); S-0970 | INFERRED |
| The EIA-96 multiplier letters Y = 0.01, X = 0.1, A = 1, B = 10, C = 100, D = 1000, E = 10 000 | S-0971 and S-0972 agree on these seven | INFERRED |
| The letters R and S are given opposite meanings (R = 0.1 and S = 0.01 in S-0971; R = 0.01 and S = 0.1 in S-0972); H = 10 is a synonym of B; Z = 0.001 and F = 100 000 are in S-0972 only | S-0971, S-0972 | UNVERIFIED: not read by Fenolite |
| In the RKM code the letters R, K, M and G stand for the decimal point and the multipliers 1, 10³, 10⁶ and 10⁹ of a resistance (R47, 4R7, 4K7, 47K, 4M7); extra trailing zeros, as in 15M0, are written to imply a tighter tolerance | S-0970 | INFERRED |

## The schemes (Fenolite's canonical spellings)

Each scheme has **one canonical spelling** per value, chosen by Fenolite; decode accepts only that spelling,
so `decode_value(encode_value(v)) == v` on the domain and no other text decodes. `x` is the value in the
field's `unit` (`unit = "pF"`: one step is 1 pF). Every step is integer or `Fraction` arithmetic.

| scheme | canonical spelling | width | examples |
|---|---|---|---|
| `eia3` | `x ≥ 10`: two digits `10`…`99` then the number of zeros `0`…`9`; `1 ≤ x < 10`: `dRd`; `0.1 ≤ x < 1`: `Rdd` | 3 | `104` = 100 nF (pF), `4R7`, `R47` |
| `eia4` | `x ≥ 100`: three digits `100`…`999` then the number of zeros; below, `R` as the decimal point (`49R9`, `4R99`, `R499`) | 4 | `1002` = 10 kΩ, `1331` = 1.33 kΩ |
| `eia96` | the index `01`…`96` of the mantissa in E96, then one of `Y X A B C D E` (10⁻² … 10⁴) | 3 | `88A` = 806 Ω, `01B` = 1 kΩ |
| `rkm` | the largest of `R K M G` that keeps the number at least 1 (`R` below 1), the integer digits before it, the decimals after it without trailing zeros, no leading zero | varies | `4K7`, `100R`, `1K`, `R47` |

- A leading zero (`010`), another width, a letter outside the lists or a non-canonical RKM spelling (`1K0`,
  `0K47`) does not decode; a value the scheme cannot spell (three significant digits in `eia3`, a value
  outside E96 in `eia96`, a non-terminating decimal in `rkm`) is outside the field's domain, and a
  `[[valid]]` row that admits one gives `family.value-unencodable`.
- `eia3`, `eia4` and `eia96` have a fixed width, so their codes are prefix-free by construction. `rkm`
  spellings vary in width (`1K` is a prefix of `1K5`): the lint checks them over the family's domain and
  reports `family.ambiguous-code`, so such a family is split or its domain cut.
- No other multiplier convention is read: a series that spells small values another way describes them
  with its own code field.

All rules are `INFERRED` (hypothesis `H-G-FAMILY-ROUNDTRIP`, `docs/hypotheses.md`): the property tests of
`tests/unit/pick/grammar/test_valuecodes.py` prove the round trip of every scheme over E192 values across
twelve decades and the index of every E96 value; no manufacturer table was compared code by code.
