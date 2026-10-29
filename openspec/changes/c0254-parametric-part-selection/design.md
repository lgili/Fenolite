## Context

- **Source.** `docs/research/circuit-as-code.md`, sections 8 ("Choosing parts by parameters, offline and
  locked") and 9 ("Generators that return what they achieved"), core change H. Clean-room: only the
  concepts are taken (parametric choice, design-wide defaults that cascade, generators that return the
  tolerance they achieve). No code, schema, query syntax, library element name, constant or table of
  JITX, atopile or tscircuit is used.
- **What exists on `dev` (0.6.0, `da300adf`).**
  - `fenolite.dsl.quantity`: exact `Quantity` values (`ohm("4k7")`), held as `Fraction`, never in the
    model. `Part(value=Quantity)` stores `text()`.
  - `fenolite.catalog`: the offline, Fenolite-authored symbol and footprint catalog (`Fenolite:Resistor`,
    `Fenolite:Chip_0603`), with evidence and source ids per entry; `fenolite catalog list|show`.
  - The DSL records plain data that the build resolves later (generated copper, c0224; net roles, c0222).
  - The mutation protocol (`--dry-run`, `--confirm --plan ID`, receipts) and the guide coverage rule.
  - `package-layering`: `dsl` → `model` only; `catalog` → `model`.
- **What this batch adds before this change** (implementation order, `docs/research`, "Proposed order"):
  - c0246: `Range` with exact bounds, `pct()`, `between()`, worst-case arithmetic, `within()`.
  - c0248: device records (MPN, symbol, footprint, pin map, ratings, evidence), `Part(device=)`.
  - c0249: the design lock, `<script stem>.lock` beside the script (`design.py` → `design.lock`; the
    research called it `fenolite.lock`), `schema = "fenolite.lock.v0"`, `[refs]`, reserved `[picks]` and
    `[pins]`, a generic `LockSection(name, resolve)` protocol,
    written through plan/confirm, and `build --frozen` (any lock change refused, exit 7).
  - c0251: blocks with ports, parameters, local nets and paths (`buck1/FB`); `design.use`.
  - c0252: `Rail` interfaces that carry a voltage range.
  - c0253: the `circuit.*` check stage, ratings against rails, `design.derating(...)`.

## Goals / Non-Goals

**Goals**

- Write a passive by what it must be, not by which library entry it is, and get the same part on every
  build until someone decides to change it.
- Every choice is reviewable text: the query, the row, the catalog version and a hash, in
  the design lock, changed only through plan/confirm.
- A generator says what it achieved, with real tolerances, in numbers that are a guaranteed enclosure.
- Zero runtime dependencies, no network in the core, byte-identical outputs.

**Non-Goals**

- See the proposal. In addition: no optimisation across several parts at once (each query and each
  generator is resolved on its own), no cost model, no automatic footprint change of a placed part.

## Today and proposed

**Today (0.6.0):**

```python
r1 = Part("R1", "Fenolite:Resistor", footprint="Fenolite:Chip_0603", value="61k9")  # why 61.9k?
r2 = Part("R2", "Fenolite:Resistor", footprint="Fenolite:Chip_0603", value="13k7")
c1 = Part("C1", "Fenolite:Capacitor", footprint="Fenolite:Chip_0805", value="10uF")  # 25 V? X7R?
connect(fb, u1["FB"], r1[2], r2[1])
```

**Proposed:**

```python
from fenolite.dsl import Design, resistor, capacitor, voltage_divider, between, ohm, farad, volt, ua, pct

design = Design("sensor")
design.defaults(
    resistor={"case": "0603", "tolerance": pct(1)}, capacitor={"case": "0603", "dielectric": "X7R"}
)

r = design.part(device=resistor(ohm("10k")))  # 0603, 1 % from the defaults
c = design.part(device=capacitor(farad("10u"), rating=volt(25), case="0805"))  # the call wins


@block
def buck(b, *, vout=volt("3.3").pct(5)):
    b.defaults(resistor={"series": "E96"})  # block level: between design and call
    out, fb, gnd = b.port("VOUT", Rail, provides=True), b.net("FB"), b.port("GND", Ground)
    top, bot = voltage_divider(
        b, out, fb, gnd, target=vout, ref=volt("0.6").pct(1), current=between(ua(40), ua(100))
    )
    ...
```

The build resolves both queries and the divider, writes the picks to the design lock and reports:

```text
gen.achieved  buck1/FB: voltage_divider top 61.9kΩ, bottom 13.7kΩ (E96, 1 %):
              VOUT 3.224694–3.399373 V within 3.135–3.465 V; divider current 42.92–44.69 µA
```

With `vout=volt("3.3").pct(3)` the same divider fails, by a hair, and says so:

```text
gen.unachievable  buck1/FB: no E96 1 % pair keeps VOUT within 3.201–3.399 V; the best,
                  top 61.9kΩ / bottom 13.7kΩ, reaches 3.224694–3.399373 V (373 µV above);
                  hint: a 0.1 % family, a wider target, or a tighter reference
```

## Decisions

### 1. Queries are recorded by the script and resolved by the build

`resistor(...)` returns a `PartQuery`, plain data. `design.part(device=query)` creates a part whose device is
not known yet; `cmd_build` resolves every query after the script ran and before `to_model`, with the
lock and the catalog in hand, exactly where c0248 resolves `device=` ids.

- **Why.** The script stays a pure description: it does not read the design lock, it does not depend on
  which catalog is installed, and the same script gives the same model on every machine that holds the
  same lock. It is also the pattern of generated copper (c0224) and net roles (c0222).
- **Cost.** A script cannot branch on the value a query will get. It can still read what it asked for
  (`r.query`), and tests (c0256) read the resolved model.
- **Alternative considered:** resolve in the DSL at the call, as c0248 resolves a `device=` id (c0248 adds
  the `dsl` → `catalog` edge). The catalog would be reachable, but the lock would not: resolving at the
  call needs either hidden global state (the lock loaded into the interpreter by the runner) or picks that
  ignore the lock. Rejected.

### 2. A new package `fenolite.pick`

`pick` → `model`, `catalog` (and `core`). It holds the query model, the row model, the series values,
matching, ranking, the lock's `[picks]` table, resolution, proposals and the generators. `dsl/query.py`
only builds `PartQuery` and `GeneratorRequest` records (no import of `pick`); `cli` (build, pick) and
`api` call `pick`.

- **Alternatives:** inside `catalog` (it would gain I/O, lock handling and generator arithmetic, and
  `catalog` is data); inside `cli` (not reusable by `fenolite.api` or the MCP server). Rejected.
- The MODIFIED "Allowed import edges" is written on top of c0248's delta (`dsl` → `model`, `catalog`),
  which lands first; task 0.1 regenerates it from whichever text is living then.
- The range arithmetic is c0246's model-level range type. If c0246 keeps `Range` in `dsl` only, task 0.1
  records it and moves the exact-bound core of it to `model`, without changing its DSL surface.

### 3. Query vocabulary and matching

| kind | value | constraints (all optional; from the call or the defaults) |
|---|---|---|
| `resistor` | ohms | `tolerance`, `power` (W, rating ≥), `voltage` (V, rating ≥), `case`, `series`, `tempco` (ppm/K, ≤) |
| `capacitor` | farads | `tolerance`, `rating` (V, ≥), `case`, `dielectric` (one or a tuple of names), `series` |
| `inductor` | henries | `tolerance`, `current` (A, rated current ≥), `saturation` (A, ≥), `dcr` (Ω, ≤), `case` |

- **Value.** A `Quantity` matches a row whose nominal equals it exactly. A c0246 `Range` matches a row
  whose worst-case span (nominal ± the row's tolerance) lies within the range: `resistor(ohm("10k").pct(5))`
  accepts a 10 kΩ 1 % row and a 9.76 kΩ 1 % row. A value with a tolerance and a `tolerance=` key is a
  `DslError` (two answers to one question).
- **Ratings** compare with `>=`, maxima (`tempco`, `dcr`, `tolerance`) with `<=`, `case`, `series` and
  `dielectric` by equality (a tuple means any of). `case` is the EIA inch code (`"0603"`).
- **Missing attribute.** A row that does not state an attribute the query constrains does not match.
  When no row matches, the finding lists, per excluded candidate, the first failed constraint, and
  `pick.attribute-unknown` names rows excluded only for lack of an attribute. A missing rating is never
  assumed.
- **Ranking** among matches, fully deterministic: (1) distance of the row's nominal to the query's
  nominal (a `Range`'s nominal), (2) the larger tolerance (the least demanding part that meets the query),
  (3) the smaller case (inch code order of a closed table), (4) project rows before shipped rows, (5) the
  device id in code-point order.

### 4. Defaults cascade design → block → call

`design.defaults(**kinds)` and `b.defaults(**kinds)` (c0251 block body) take, per kind, a mapping of
constraint keys. For a query, the effective constraints are: the design's, then each enclosing block's
from outermost to innermost, then the call's; a later level replaces a key, and `None` removes it. An
unknown kind or key, or a value of the wrong unit, is a `DslError` at the `defaults` call. The
effective query is printed in its **canonical text** (decision 8) and that text, not the script, is what
the lock compares.

- **Why three levels.** They are the ones the research names and the ones a reader can see in the
  script. Per-instance overrides (`design.use(..., defaults=...)`) are left for later (open question 3).

### 5. Pickable rows: families and discrete rows

- **Family** (`fenolite.family.v0`, a TOML file under `catalog/families/` of the package or of the
  `devices/` folder beside the script that c0248 reads):

```toml
schema = "fenolite.family.v0"
id = "Fenolite:R_0603_E96_1pct"
kind = "resistor"
summary = "Thick-film chip resistor, 0603, 1 %, E96"
symbol = "Fenolite:Resistor"
footprint = "Fenolite:Chip_0603"
case = "0603"
series = "E96"
values = { min = "10", max = "1M" }          # ohms, both ends included
tolerance = "1%"
power = "0.1W"                               # each attribute names its sources
evidence = "INFERRED"
sources = { power = ["S-xxxx"], case = ["S-xxxx"] }
```

  A family row expands to one candidate per series value in its span. The device id of a pick is
  `<family id>@<value code>` (`Fenolite:R_0603_E96_1pct@61k9`, IEC 60062 letter code). It has no MPN; the
  BOM shows the family summary and the value.
- **Discrete row**: a c0248 device record that states `kind` and `value` (and any ratings).
- **Pins of a query part.** c0248 checks pin access at the call; a query part has no device yet, so it
  exposes the generic pins of its kind (`1` and `2`), and every pickable row of a kind MUST map those two
  pins (a row with another pin map is refused when the catalog is read). A polarised kind is out of scope. If c0248's
  schema lacks `kind`, `value`, `case`, `dielectric` or `tolerance`, this change adds them as optional keys
  in a minor revision of that schema (task 0.1 checks).
- **Shipped families.** Resistors E24 5 % and E96 1 % in 0402, 0603, 0805 and 1206; capacitors C0G and
  X7R in the same cases with the values and ratings that the registered public datasheets state. No
  inductor family is shipped: inductors depend on the maker, so they come from project rows. Every number
  carries a source and its label; an attribute without a source is left out (and so never matches a
  query that constrains it).

### 6. Series values from a registered source

`pick.series.SERIES` holds E6, E12, E24, E48, E96 and E192 as integer mantissas, transcribed from the
public source registered at task 0.1 (IEC 60063 values as published), with a test that checks E48 to
E192 against the rounding rule that source states and names each listed exception. A family's span and
a generator's search use the same table. A row's `series` is a name of this table or absent.

### 7. Picks in the lock

c0249 owns the design lock; this change fills its `[picks]` table and registers its `LockSection`
(`resolve` is decision 9), which lifts c0249's refusal of a non-empty `[picks]`:

```toml
[picks."buck1/C_in"]
query = "capacitor(10uF, rating>=25V, case=0805, dielectric=X7R)"
device = "Fenolite:C_0805_X7R_25V@10u"
row = "Fenolite:C_0805_X7R_25V"
catalog = "fenolite-catalog 2026.10"
sha256 = "9f2c…"                    # SHA-256 of the row's canonical text
by = "query"

[picks."buck1/FB_top"]
query = "voltage_divider(target=3.3V±5%, ref=0.6V±1%, current=40uA..100uA, series=E96, role=top)"
device = "Fenolite:R_0603_E96_1pct@61k9"
row = "Fenolite:R_0603_E96_1pct"
catalog = "fenolite-catalog 2026.10"
sha256 = "41ab…"
by = "voltage_divider"
achieved = "VOUT 3224694uV..3399373uV"
```

- Keys and their order are fixed; values are strings; entries in path order (c0249's canonical form).
- `catalog` is `fenolite-catalog <CATALOG_VERSION>` for shipped rows (a version of the catalog data,
  independent of the package version) or `project:<path relative to the script>` for project rows.
- `achieved` is the generator's enclosure in integer micro-units, rounded outward (minimum down, maximum
  up), so the lock never claims more than the arithmetic proved.

### 8. Canonical query text

A query prints as `<kind>(<value text>, <key><op><value>, ...)` with keys in a fixed order per kind,
quantities in `Quantity.text()`, ranges in c0246's canonical text, and defaults already merged. Two
scripts that ask for the same thing give the same text; the lock compares texts, never Python objects.

### 9. Resolution in a build

For each query part, in path order:

| lock entry | query text | locked row | locked row meets the query | action | finding |
|---|---|---|---|---|---|
| none | — | — | — | resolve, plan the new entry | `pick.new` (info) |
| present | equal | same SHA-256 | — | use the locked device | none |
| present | equal | changed SHA-256 | yes | use the row as it is now, plan the new hash | `pick.row-changed` (warning) |
| present | equal or not | missing | — | nothing is built | `pick.row-missing` (error) |
| present | changed | present | yes | keep the device, plan the new query text | `pick.query-changed` (info) |
| present | changed | present | no | nothing is built | `pick.stale` (error, hint `fenolite pick --update PATH`) |
| none / any | — | — | no row matches | nothing is built | `pick.no-match` (error) |

- Lock changes are planned writes of the design lock in the build's plan; with c0249's `--frozen` any of
  them refuses the build (exit 7) as c0249 specifies.
- A locked pick is never replaced by a better match: improvement is a decision, made with
  `fenolite pick --update`.
- A row whose evidence is `UNVERIFIED` (a proposal not reviewed yet, decision 11) can be picked only
  when the query is pinned to it; otherwise it is ranked out with `pick.row-unverified` (info).
- `result.picks` lists every pick with its state; `.fenolite/build.json` records the lock's SHA-256.

### 10. `fenolite pick PATH`

- Without options: read-only; lists every query part with its lock entry and its state (`ok`, `new`,
  `stale`, `row-changed`, `row-missing`, `no-match`), exit 5 when any state is an error.
- `--candidates PATH`: the ranked candidates of one query (top 20, `--limit N`), with the failed
  constraint of each excluded row; read-only.
- `--update PATH...` or `--update-all`: re-resolve those entries against the current catalog and plan
  the lock write (old → new device per path). Under the mutation protocol (`--dry-run`, then
  `--confirm --plan ID`); it writes the design lock only.
- No subprocess, no network. The MCP server gets the tool by c0195's rule (one tool per public command).

### 11. Supplier proposals

`fenolite pick PATH --propose QUERY_OR_PATH (--from FILE | --supplier NAME --allow-offsite)` writes
candidate rows to `devices/proposed/<row id>.toml` beside the script under the mutation protocol.

- `--from FILE` reads rows the user exported (CSV or JSON with documented columns); offline.
- `--supplier NAME` calls a plugin registered under the entry-point group `fenolite.suppliers` (protocol
  `pick.propose.Supplier`). Fenolite ships no plugin in this change; a plugin's network use is declared
  `sends_data_offsite: true` in `capabilities`, and the command exits 2 without `--allow-offsite`, as
  `route` does for an offsite router.
- Proposed rows carry `evidence = "UNVERIFIED"` and the source line of the plugin or file. The user moves a
  row out of `proposed/` and raises its label after reading the datasheet. Proposals never write the lock.
- **Why no supplier extra in `pyproject.toml`.** Proposals need no third-party package (the standard
  library reads CSV and JSON, and a plugin brings its own dependencies). An empty extra would only be a
  name. Open question 4.

### 12. Generators: pure, exact, recorded

A generator is a DSL call that creates its parts as queries with a `GeneratorRequest` attached, and a
build function `pick.generators.<name>.solve(request, rows) -> Solution` that is pure: same request and
rows, same solution.

- **Exact arithmetic.** Fractions throughout. A constant that is not rational (π in an RC corner, a
  logarithm in the I2C rise-time window) is replaced by a rational **enclosure** (two decimal fractions
  of 12 digits around it), and the arithmetic carries intervals, so the reported range contains the true
  one.
- **Search** is bounded and enumerated in a fixed order; ties are broken by explicit rules (each
  generator below). No solver.
- **Recording.** `gen.achieved` (info) carries the achieved range and the inputs; the same text goes to
  `result.generators`, the build evidence and `achieved` in each pick. A generator's lock `query` is its
  canonical input text plus the role of the part (`role=top`).
- **Locked generator picks.** When the inputs change, the locked values are re-evaluated with the new
  inputs: still within the target → `pick.query-changed` (info) and the new achieved text; otherwise
  `pick.stale`. A generator never re-searches by itself.

### 13. `voltage_divider`

`voltage_divider(b, hi, mid, lo, *, target, ref=None, vin=None, current, series=None, name=None)`.

- **Feedback mode** (`ref` given): `target` is the range of `hi`; `VOUT = VREF · (1 + Rt / Rb)`.
- **Divider mode** (`ref` absent): `target` is the range of `mid`; `vin` is a range, or taken from `hi`
  when `hi` is a c0252 `Rail` with a voltage; `VMID = VIN · Rb / (Rt + Rb)`.
- `current` is a c0246 range of the divider current (a bare quantity is a `DslError`: the search window
  must be stated). `series`, `case`, `tolerance` come from the resistor defaults and the call.
- **Search.** Every series value `Rb` of the family whose nominal current (`VREF.nominal / Rb`, or
  `VIN.nominal / (Rt + Rb)` in divider mode) lies in `current`; for each, the two series values that
  bracket the ideal `Rt` (one when exact). Worst case over the reference (or input) range and both
  resistor tolerances; a pair is accepted when its range lies within `target`.
- **Choice.** Among accepted pairs: smallest distance of the nominal output to the target's nominal,
  then the narrowest achieved range, then the smaller `Rb`, then the smaller `Rt`.
- **Failure.** `gen.unachievable` (error) names the pair whose range overshoots the target least, by how
  much, and hints at a tighter family, a wider target or a tighter reference.
- Parts: `<name>_top` and `<name>_bot` in the caller's block (`name` defaults to the name of `mid`).
- **Worked numbers** (they are the scenarios of the spec): VREF 0.6 V ± 1 %, target 3.3 V ± 5 %, E96 1 %,
  current 40–100 µA → 61.9 kΩ over 13.7 kΩ, VOUT 3.224694–3.399373 V; with ± 3 % the same pair overshoots
  3.399 V by 373 µV and no pair is accepted; with a 0.1 % E96 family it gives 3.272477–3.349540 V.

### 14. The other generators

| generator | inputs | formula and search | choice |
|---|---|---|---|
| `rc_lowpass(b, inp, out, gnd, *, corner, r=None, c=None)` | corner range (Hz); one of `r`/`c` may be fixed | `f = 1 / (2πRC)` with π enclosed; for each capacitor candidate, the resistor values bracketing the ideal | nominal closest to the target, then fewer parts changed from given values, then smaller C |
| `led_resistor(b, supply, led, *, current, vf=None)` | current range, forward voltage range from the c0248 LED record or `vf` | `I = (VS − VF) / R`, worst case; the resistor's power rating ≥ the worst `I²R` times c0253's derating | nominal current closest to the range's nominal, then the larger R |
| `i2c_pull_ups(b, bus, supply, *, bus_capacitance, mode=None)` | the bus of c0252 (its speed mode), the capacitance range | the window `Rp,min = (VDD,max − VOL) / IOL`, `Rp,max = tr / (k · Cb)` with the constants and `k` of the I2C specification (public, registered; `k` enclosed) | the largest series value inside the window (least current), one value for both lines |
| `shunt(b, hi, lo, *, current, full_scale)` | load current range, the amplifier's full-scale input range | the largest row value with `I,max · R,max ≤ VFS,min`; power rating ≥ `I,max² · R,max` times the derating | largest R (resolution), then the smaller case; the part gets c0222's `part_class(..., "shunt")` |

Each one records `gen.achieved` with its own quantity (corner range; LED current range and resistor
power; the pull-up window and the chosen value; the full-scale use and the dissipation).

### 15. Codes

Findings (`pick.codes.ISSUE_CODES`, each explained by `fenolite explain`, listed in
`docs/cli-contract.md`, "Picks"):

| code | severity | when |
|---|---|---|
| `pick.no-match` | error | no row meets a query |
| `pick.stale` | error | a changed query, or a generator's new inputs, no longer met by the locked part |
| `pick.row-missing` | error | the locked row is not in the catalog |
| `pick.row-changed` | warning | the locked row's text changed but still meets the query |
| `pick.query-changed` | info | the query text changed and the locked part still meets it |
| `pick.new` | info | a pick that the lock did not hold |
| `pick.attribute-unknown` | info | a row left out only because it lacks a constrained attribute |
| `pick.row-unverified` | info | an `UNVERIFIED` proposed row ranked out |
| `gen.unachievable` | error | a generator found no accepted combination |
| `gen.achieved` | info | what a generator achieved |
| `pick.overridden` | info | a picked part edited in CAD (only if open question 2 is accepted; then added to the spec) |

No new `FEN-` code: a malformed family or proposal file is `FEN-3004`, an unknown `--update` path is
`FEN-2001`, a frozen lock refusal is c0249's.

### 16. Evidence

- `pick.EVIDENCE` is `INFERRED` with the hypothesis `H-G-PICK-DETERMINISTIC` (same lock and catalog, same
  picks and bytes) proven by unit tests; generator results are `INFERRED` with `H-G-GEN-ENCLOSURE`
  (the achieved range encloses the exact one), proven by property tests against brute-force evaluation.
- The envelope combines it with the evidence of each picked row (lowest wins), so a pick of an
  `UNVERIFIED` row lowers the reply.

## Relation to the other changes of the batch

- **c0246** gives the ranges; **c0248** the device records and their resolution step; **c0249** the lock
  file, its writer and `--frozen`; **c0251** the block paths and `b.defaults`. Task 0.1 records the final
  names of each.
- **c0247** helpers accept a query anywhere they accept a part (`decouple(v33, gnd, capacitor(...))`).
- **c0250** (manual edits): a value or footprint edited in KiCad on a picked part is c0250's per-property
  merge; the edit wins and the lock marks it (open question 2, which follows c0250's open question 5).
- **c0252**: a `Rail`'s voltage range feeds `voltage_divider` (divider mode) and `led_resistor`.
- **c0253** checks the ratings of picked parts against rails with derating; generators use the same
  `design.derating` values for their power checks.
- **c0255** is the other half of step 6; it does not depend on this change.
- **c0256** asserts achieved ranges in tests (`assert design.generated("buck1/FB").vout.within(...)`).

## Risks / Trade-offs

- **Shipped families can mislead** if a typical rating is read as a guarantee. Mitigation: every number has
  a source and a label, the BOM marks family picks as generic, and contract checks (c0253) still apply.
- **Lock churn.** A query edited for cosmetics changes its canonical text and plans a lock write. The
  canonical text removes spelling differences, and an unchanged meaning keeps the device.
- **Search size.** E192 over six decades is 1 152 values; a divider search is at most a few thousand
  exact evaluations, well under a second. Bounded by the `current` window.

## Open questions

1. **Ranking: larger tolerance first?** Rule (2) prefers the least demanding part that meets the query.
   Recommended: yes, it is the cheaper and more available part in practice and the query already states
   what is required.
2. **A picked part edited in KiCad** (value or footprint, c0250). Recommended, as c0250's open question 5
   proposes: the edit wins over the pick, the lock entry keeps its query and gets `by = "edit"` with the
   edited device or value, this change reports `pick.overridden` (info), and c0253 judges the edited
   part. `fenolite pick --update` returns the part to a query pick.
3. **Per-instance defaults** (`design.use(buck, "b1", defaults=...)`). Recommended: not now; a block
   parameter does the same explicitly.
4. **A named `suppliers` extra.** Recommended: no extra until a shipped plugin needs a package; the entry
   point group is enough.
5. **Case codes.** Inch codes only (`0603`), or also metric (`1608M`)? Recommended: inch only, metric
   accepted later as an alias with a distinct suffix, so `0603` never means two things.
