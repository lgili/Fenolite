## ADDED Requirements

### Requirement: Temperatures in the DSL
`fenolite.dsl` SHALL export `celsius(x)` and `kelvin(x)`, quantities of c0246's new unit `kelvin`: `celsius(x)` is `kelvin(x + 273.15)` exactly. A float or a bool MUST raise `DslError`. In messages and requirement rows an absolute temperature MUST print in degrees Celsius and a temperature difference in kelvin.

#### Scenario: A Celsius range
- **WHEN** `uv run pytest tests/unit/dsl/test_quantity.py -k celsius` builds `between(celsius(-20), celsius(70))` and `kelvin(15)`
- **THEN** the range runs from exactly 253.15 K to 343.15 K, its temperature text is `-20°C..70°C`, `kelvin(15)` prints `15K`, and `celsius(20.5)` raises `DslError`

### Requirement: Products of ranges
c0246's closed unit table SHALL gain volt·volt → `volt_squared`, ampere·ampere → `ampere_squared`, `ampere_squared`·ohm → watt, `volt_squared`/ohm → watt and watt/ohm → `ampere_squared`, with worst-case bounds as for every product. Any other pair MUST still raise `TypeError`.

#### Scenario: The power of a bleeder
- **WHEN** `(volt("13.2") * volt("13.2")) / ohm("1k").pct(1)` and `amp("0.5") * amp("0.5") * ohm("0.1")` are computed
- **THEN** the first is the watt range whose high bound is exactly 174.24/990 W, the second is exactly 0.025 W, and `volt("1") * ohm("1")` raises `TypeError`

### Requirement: One-sided range arithmetic
Arithmetic on a range with an unbounded side SHALL be allowed when the result keeps at least one bound: `+` and `-` combine bounds side by side, and `*` and `/` apply when both operands have a low bound of at least 0, an unbounded high staying unbounded. A signed one-sided product, a division by a range whose low bound is 0, and a result unbounded on both sides MUST raise `DslError`.

#### Scenario: A one-sided floor
- **WHEN** `volt("4.5").min() + volt("0.2")`, `amp("1").min() * ohm("2")` and `volt("4.5").min() - volt("1").min()` are computed
- **THEN** the first is 4.7 V and up, the second 2 V and up, and the third raises `DslError` naming the subtraction

## MODIFIED Requirements

### Requirement: Waivers in the DSL
`Design.waive(code, *items, reason, min_gap=None, digest=None, name=None)` SHALL record one waiver: the acceptance of one finding of `check`, of the copper guard or of the build's circuit hook, with a reason (`verification-loop`, "Waivers in the check"). The call MUST raise `DslError`, before anything is built, when:
- `code` is not `copper.short`, `copper.clearance`, `copper.zone-overlap`, a `circuit.*` code of `checks.codes.ISSUE_CODES` that has the severity `error` or `warning`, or `kicad.drc.<suffix>` with a suffix that matches `[a-z0-9]+(-[a-z0-9]+)*` and is not a member of `checks.drc_json.RESERVED_SUFFIXES` (`rules-not-loaded`, `rules-unchecked`, `parity-unchecked`), which are verdicts and not findings; a `kicad.erc.*` or `parity.*` code is refused by the same rule, with a hint that only copper, DRC and circuit findings are waived;
- `items` are not one or two, an item is neither a non-empty string without `", "` nor a `Part`, a `copper.*` code has other than two items, or a `circuit.*` code has other than one item or an item holding `*`, `?` or `[`: a circuit finding is waived by its exact row;
- `digest` is missing from a `circuit.*` waiver, is not 16 lowercase hexadecimal digits, or is given with any other code;
- the code is `copper.short` or `kicad.drc.shorting-items` and an item holds `*`, `?` or `[`: a short is waived by exact names only;
- `reason` is empty after stripping or holds a line break;
- `min_gap` is given with a code other than `copper.clearance`, is not a positive length, or is missing from a `copper.clearance` waiver whose items hold a glob character;
- `name` is empty or holds a line break, or a waiver of that name was already recorded. The default name is `<code>:<items joined by ",">`, so the same waiver declared twice also raises.

`to_model` MUST put the waivers into `Design.findings.waivers` sorted by name, a `Part` replaced by its reference.

#### Scenario: A waiver reaches the model
- **GIVEN** a design with part `J1` and the call `design.waive("copper.clearance", "J1-3", "J1-4", reason="fixed by the mating connector", name="pitch")`
- **WHEN** `uv run pytest tests/unit/dsl/test_waivers.py -k model` converts it with `to_model`
- **THEN** `findings.waivers` holds one `Waiver(name="pitch", code="copper.clearance", items=("J1-3", "J1-4"), reason="fixed by the mating connector", min_gap=None)`

#### Scenario: Refused waivers
- **WHEN** `design.waive` is called with code `copper.short` and items `R1-1`, `R2-*`; with code `copper.clearance`, items `J1-3`, `*` and no `min_gap`; with code `kicad.drc.rules-not-loaded`; with code `kicad.drc.parity-unchecked`; with code `parity.net-conflict`; with `min_gap=mm(0.1)` and code `kicad.drc.silk-overlap`; with `reason=" "`; and twice with the same code and items
- **THEN** each call raises `DslError` naming the rule it broke

#### Scenario: A circuit waiver with its digest
- **GIVEN** a design with part `C3` and `design.waive("circuit.rating-voltage", "C3:voltage", reason="bench is current-limited", digest="9f2c4a1b0d3e5f67")`
- **WHEN** `uv run pytest tests/unit/dsl/test_waivers.py -k circuit` converts it, and then calls `design.waive` with code `circuit.rating-voltage` and no digest, with item `C*:voltage`, with code `circuit.policy-missing`, and with code `copper.short` and a digest
- **THEN** `findings.waivers` holds the waiver named `circuit.rating-voltage:C3:voltage` with that digest, and each of the four other calls raises `DslError` naming its rule

#### Scenario: Default name and parts
- **GIVEN** part `TP1` and `design.waive("kicad.drc.via-dangling", "*", reason="test point")` and `design.waive("kicad.drc.courtyards-overlap", tp1, "U1", reason="stacked by design")`
- **WHEN** the design is converted
- **THEN** the waivers are named `kicad.drc.courtyards-overlap:TP1,U1` and `kicad.drc.via-dangling:*`, in that order
