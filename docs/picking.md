# Picking parts by parameters

A passive can be written by what it must be instead of by which library entry it is. The build picks a
row of a **local, versioned catalog**, writes the pick to the design lock through the plan, and keeps it
until someone decides to change it (change c0254). Generators choose the values of small circuits with
exact arithmetic and report what they achieved. No network, no solver, no supplier database.

## Queries

```python
from fenolite.dsl import Design, capacitor, farad, ohm, pct, resistor, volt

design = Design("sensor")
r = design.part(device=resistor(ohm("10k"), tolerance=pct(1), case="0603"))
c = design.part(device=capacitor(farad("10u"), rating=volt(25), dielectric=("X7R", "X5R")))
```

| kind | value | constraints |
|---|---|---|
| `resistor` | ohms | `tolerance` (≤), `power` (W, ≥), `voltage` (V, ≥), `case`, `series`, `tempco` (ppm/K, ≤), `row` |
| `capacitor` | farads | `tolerance` (≤), `rating` (V, ≥), `case`, `dielectric` (one or a tuple), `series`, `row` |
| `inductor` | henries | `tolerance` (≤), `current` (A, ≥), `saturation` (A, ≥), `dcr` (Ω, ≤), `case`, `row` |

- **Value.** A quantity matches a row whose nominal equals it. A range (`ohm("10k").pct(5)`) matches a row
  whose worst-case span, nominal ± the row's tolerance, lies within it: 9.76 kΩ 1 % and 10.2 kΩ 1 % meet
  `10k ± 5 %`, 9.53 kΩ and 10.5 kΩ do not. A range with `tolerance=` is refused (two answers to one question).
- **Constraints.** Ratings compare with `>=`, maxima with `<=`, names by equality (a tuple: any of them).
  `case` is the EIA inch code (`0603`); metric codes are not read. `row=` names one row or device id.
- **Missing attributes.** A row that does not state a constrained attribute never matches: a missing
  rating is never assumed. When nothing matches, `pick.attribute-unknown` names the rows left out only
  for that reason.
- **Canonical text.** `r.query.text()` prints `resistor(10kΩ, tolerance<=1%, case=0603)`: the value, then
  the keys in the order of the table, defaults merged. The lock compares these texts, never script objects,
  so `farad("10u")` and `farad("10 uF")` are one query.

## Defaults

`design.defaults(resistor={"case": "0603", "tolerance": pct(1)})` and `b.defaults(...)` in a block body
give keys that apply to every query below them. The effective constraints are the design's, then each
enclosing block's from the outermost to the innermost, then the call's; a later level replaces a key and
`None` removes it. A range value ignores a default tolerance. Per-instance defaults are not offered: a
block parameter does the same explicitly.

## Rows

- **Families** (`fenolite.family.v0`): a case, a tolerance, an E series and a span of values, no MPN. A
  family expands to one row per series value of its span, with the device id `<family id>@<value code>`
  (IEC 60062 letter code: `Fenolite:R_0603_E96_1pct@61k9`). A picked part shows the family's symbol and
  footprint and the value; the BOM marks it as a generic part.
- **Device rows**: a device record of `docs/devices.md` that states `kind` and a `value` of the kind's
  unit, with `case`, `tolerance`, `dielectric` and ratings (`voltage` is a capacitor's `rating`).
- Every row maps exactly the symbol pins `1` and `2`; another pin map is refused when the row is read.
- **Shipped families** (`fenolite catalog list --kind family`, `catalog show <id>`): chip resistors E24 5 %
  and E96 1 % from 10 Ω to 1 MΩ, and C0G 5 % and X7R 10 % chip capacitors at 50 V, each in 0402, 0603, 0805
  and 1206. Every number names its public source (S-0315, S-0940, S-0942, S-0943, S-0944) and is `INFERRED`;
  an attribute without a source is left out. No inductor family is shipped: inductors come from project rows.
  `fenolite.catalog.FAMILIES_VERSION` names the data; `families/VERSIONS.toml` records each family's digest,
  and a test asks for a new version when a family changes.
- **Project rows** live in `devices/` beside the script (families and devices side by side), unreviewed
  proposals in `devices/proposed/`. A malformed file is `FEN-3004`, naming the file and the key.

## Ranking

Among the matches the pick is the first by: the distance of the row's nominal to the query's nominal; the
larger tolerance (the least demanding part that meets the query); the smaller case; a project row before a
shipped row; the device id in code-point order.

## Picks in the lock

```toml
[picks."C_in"]
"query" = "capacitor(10uF, rating>=25V, case=0805, dielectric=X7R)"
"device" = "Example:C_0805_X7R_25V@10u"
"row" = "Example:C_0805_X7R_25V"
"catalog" = "project:devices/caps.toml"
"sha256" = "…"
"by" = "query"
```

`catalog` is `fenolite-catalog <FAMILIES_VERSION>` for a shipped row, `project:<path>` for a project row;
`sha256` is the SHA-256 of the row's canonical text; a generator's part adds `achieved`, its range in integer
micro-units rounded outward (`VOUT 3224694uV..3399373uV`).

## Resolution in a build

| lock entry | query text | locked row | still meets | result |
|---|---|---|---|---|
| none | — | — | — | the best match, `pick.new` |
| present | equal | same hash | — | the locked device |
| present | equal | changed hash | yes | the row as it is now, `pick.row-changed` (warning) |
| present | any | missing | — | `pick.row-missing` (error) |
| present | changed | present | yes | the device kept, `pick.query-changed` |
| present | changed | present | no | `pick.stale` (error, hint `fenolite pick --update PATH`) |
| any | — | — | no row matches | `pick.no-match` (error) |

Lock changes are planned writes of the build; `--frozen` refuses any (exit 7). A locked pick is never
replaced by a better match. An `UNVERIFIED` row is picked only when `row=` names it, otherwise it is ranked
out with `pick.row-unverified`. An error finding builds nothing. `result.picks` lists every pick with its
state, `result.generators` what each generator achieved.

## `fenolite pick`

```text
fenolite pick examples/picks                            # each pick and its state; exit 5 on an error state
fenolite pick examples/picks --candidates C_in          # the ranked rows, and why each other row is out
fenolite pick examples/picks --update C_in --dry-run    # re-pick through the plan (then --confirm --plan)
```

`docs/cli-contract.md`, "pick", has the arguments, the result keys and the codes.

## Proposals

`fenolite pick PATH --propose QUERY --from rows.csv` turns rows the user exported (CSV with a header line,
or JSON: a list of objects; columns `id`, `kind`, `value`, `footprint`, and optionally `summary`, `symbol`,
`case`, `tolerance`, `dielectric`, `voltage`, `power`, `current`, `manufacturer`, `mpn`, `datasheet`) into
device records under `devices/proposed/`, each `UNVERIFIED` with the line it came from; only the rows that
meet `QUERY` are written. `--supplier NAME` calls a plugin of the entry-point group `fenolite.suppliers`
(protocol `fenolite.pick.propose.Supplier`); a plugin that sends data offsite needs `--allow-offsite`.
Fenolite ships no plugin and no `suppliers` extra. A proposal never writes the lock: read the datasheet,
move the record out of `proposed/` and raise its label.

## Generators

A generator creates its parts as queries carrying a request; the build solves it with exact `Fraction`
arithmetic, each irrational constant replaced by a 12-digit rational enclosure, a bounded search in a fixed
order and explicit tie rules. It reports `gen.achieved` (the achieved range, a guaranteed enclosure) or
`gen.unachievable` (the combination that leaves the target least, and by how much). A locked generator is
judged with its new inputs and never searches again: still within the target gives `pick.query-changed`,
otherwise `pick.stale`.

- **`voltage_divider(b, hi, mid, lo, *, target, ref=None, vin=None, current, series=None, name=None)`.**
  With `ref`: `VOUT = VREF · (1 + Rt / Rb)` at `hi`; with `vin`: `VMID = VIN · Rb / (Rt + Rb)` at `mid`. Every
  bottom row whose nominal current lies in `current` (a range: the search window must be stated), and the
  values that bracket the ideal top. Choice: the nominal output closest to the target's, the narrowest
  range, the smaller `Rb`, the smaller `Rt`. Parts `<name>_top` and `<name>_bot`. With VREF 0.6 V ± 1 %,
  3.3 V ± 5 % and E96 1 %: 61.9 kΩ over 13.7 kΩ, VOUT 3.224694–3.399373 V; at ± 3 % the same pair is 373 µV
  above 3.399 V and nothing is accepted; a 0.1 % E96 family gives 3.272477–3.34954 V.
- **`rc_lowpass(b, inp, out, gnd, *, corner, r=None, c=None)`.** `f = 1 / (2πRC)` with π enclosed; a fixed
  `r=` or `c=` query limits that part. Choice: the nominal corner closest to the target's, the smaller C.
- **`led_resistor(b, supply, led, *, current, vf, vs)`.** `I = (VS − VF) / R` worst case within `current`, and
  a power rating that covers `(VS,max − VF,min)² / Rmin`. Choice: the nominal current closest to the range's,
  the larger R. `vs` and `vf` are ranges until rails (c0252) and LED records carry a voltage; the derating
  factor is 1 until c0253 gives `design.derating`.
- **`i2c_pull_ups(b, bus, supply, *, bus_capacitance, vdd, mode=None)`.** The window of the I2C
  specification (S-0941): `Rp,min = (VDD,max − VOL) / IOL`, `Rp,max = tr / (ln(7/3) · Cb,max)` with `VOL`
  0.4 V, `IOL` 3 mA (20 mA in fast-mode plus) and `tr` 1000, 300 or 120 ns for `standard`, `fast` (default)
  and `fast-plus`. The largest value whose span lies in the window, one value for both lines.
- **`shunt(b, hi, lo, *, current, full_scale)`.** The largest value whose worst-case drop at the largest
  current stays within the smallest full-scale input, with a power rating that covers `I,max² · R,max`. The
  part gets the class `shunt` for net roles.

## Families with ordering codes

A grammar family (`fenolite.family.v1`, change c0263) describes a whole manufacturer series once, from its
public datasheet: the fields of its ordering code, the codes of each field, the value code and the validity
matrix. It is a row source beside generic families and device records, read from the same `devices/` and
`devices/proposed/` folders beside the script; its candidates are exact MPNs with their manufacturer. The
core package ships no real series: Fenolite's own grammars are illustrative (`examples/families/`), and real
series grammars belong to the data repository of change c0266, one file per series, each cited to its
datasheet.

```toml
schema = "fenolite.family.v1"
id = "Example:EX_MLCC"
kind = "capacitor"
summary = "Multilayer ceramic chip capacitors, EX series (illustrative)"
manufacturer = "Example Passive"
version = "1.0.0"
licence = "CC0-1.0"
evidence = "INFERRED"
sources = ["EX series datasheet rev A, ordering code table (illustrative)"]
symbol = "Fenolite:Capacitor"
pattern = "EX{size}{dielectric}{value}{tolerance}{voltage}{packing}"

[fields.size]
codes."03" = { case = "0603", footprint = "Fenolite:Chip_0603" }
[fields.value]
scheme = "eia3"   # 104 = 100 nF in pF
unit = "pF"
series = "E12"
[fields.packing]
role = "ordering"  # does not change what the part is; encode uses prefer
prefer = "T"
codes.T = { packing = "reel" }
# ... dielectric, tolerance, voltage

[[valid]]          # the validity matrix, row by row
size = "03"
voltage = ["A", "B"]
value = { min = "100pF", max = "100nF" }

[[exclude]]        # removes combinations a valid row admitted
size = "03"
voltage = "B"
value = { min = "47nF", max = "100nF" }
```

- **Keys.** `schema`, `id`, `kind`, `summary`, `manufacturer`, `version`, `licence`, `evidence`, `sources`,
  `pattern`, `fields` and at least one `[[valid]]` row are required; `datasheet` (an http(s) URL), `symbol`,
  `footprint`, `pins` (`{ "1" = pad, "2" = pad }`), `tail`, `exclude` and `reviewed_by` are optional. Any
  other key or a float is `FEN-3004` naming the file and the key; a newer schema `FEN-3002`. `sources` is a
  list for every attribute, or a table `attribute → list`. The stable id of the record is c0259's
  `record_uid("family", id)`, computed, never stored.
- **Pattern and fields.** Literal text `[A-Z0-9-]` and `{field}` placeholders; every placeholder names one
  field, every field appears once, exactly one field has a `scheme` (the value field). A code's attributes are
  the constraint keys of the family's kind (`tolerance`, `rating`, `case`, `dielectric`, `series` for a
  capacitor; `tolerance`, `power`, `voltage`, `case`, `series`, `tempco` for a resistor; `tolerance`, `current`,
  `saturation`, `dcr`, `case` for an inductor) plus `footprint`, `symbol` and `packing`. An `ordering` field
  names `prefer`, the code encode uses, so one query gives one MPN per electrical combination.
- **Value codes.** `eia3`, `eia4`, `eia96` and `rkm`, one canonical spelling per value, exact integers
  (`docs/formats/library/value-codes.md`). A row's value domain is its series (or the field's) within
  `min`..`max`, both included, or its explicit `values`.
- **Matrix.** A combination is valid when some `[[valid]]` row admits it (each field it names holds one of its
  codes, the value lies in its span; a field it omits is free) and no `[[exclude]]` row removes it.
- **Lint.** `fenolite family lint FILE` proves without enumerating that every MPN parses one way: no code of
  a field is a proper prefix of another (an `rkm` field is checked over the family's domain). It also checks
  the pattern, the matrix codes, values the scheme cannot spell, `prefer` and the sources of the numeric
  attributes. A family with a lint error is never used to pick or decode (`FEN-3004`).
- **Encode.** The expansion is lazy, in canonical order (fields in pattern order, codes in code-point order,
  values rising): a query first cuts each electrical field to the codes whose attributes meet it, ordering
  fields to `prefer` and the values to those it admits; a cut product above 100 000 is refused
  (`family.expansion-limit`) before the first step. The candidates are then matched and ranked by the rules
  above. `fenolite family encode QUERY` lists them; a build picks the first.
- **Decode.** `fenolite family decode MPN` parses left to right against each family in id order and gives
  every attribute, the value and `in_matrix` (`family.decode-outside-matrix` when the matrix does not admit
  it); a failed parse names the position and the field (`family.decode-no-match`), two full parses
  `family.decode-ambiguous`. With `tail = "opaque"` characters after the last field are kept as `suffix`,
  unread, and the decode is `UNVERIFIED` (`family.suffix-opaque`); encode never produces a tail.
- **Picks and the lock.** A candidate is an in-memory device: `id = "<family id>@<MPN>"`, the manufacturer
  and the MPN, the symbol and footprint (family or code), pins `1` and `2`, the value and its ratings
  (`rating` and `voltage` → `voltage`, `power`, `current`) as `abs_max`. The lock entry holds that `device`,
  `row` = the family id, `catalog` = `project:devices/<file>` and `sha256` = the SHA-256 of the candidate's
  canonical text (family id and version, MPN, manufacturer, value and sorted attributes). An edit of the
  grammar that leaves a locked candidate unchanged keeps its hash; one that changes it gives
  `pick.row-changed`; one that removes it from the matrix, `pick.row-missing`. A generator's parts pick from
  generic families and devices only.

## Evidence

Picks are `INFERRED` (`H-G-PICK-DETERMINISTIC`: the same lock and catalog give the same picks and bytes),
generator results `INFERRED` (`H-G-GEN-ENCLOSURE`: the achieved range encloses the exact one), both proven
by unit tests; `fenolite pick` combines them with the label of each picked row (lowest wins). Grammar
families are `INFERRED` (`H-G-FAMILY-ROUNDTRIP`: every expanded MPN of the authored grammars decodes to
itself), combined with each family's own label. A built board
with picked parts is read back like any build.
