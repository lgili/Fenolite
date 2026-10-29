## Context

- **Source.** `docs/research/component-library.md`, section 4.5 ("Passives from ordering-code grammars"),
  section 1 (what may be used) and the table of section 5 (c0263: depends on c0254 and c0259, size M).
- **What exists on `dev` (0.6.0).** No part number grammar of any kind. `fenolite.dsl.quantity` parses
  exact quantities (`farad("100n")`); the catalog ships symbols and footprints such as `Fenolite:Capacitor`
  and `Fenolite:Chip_0603`.
- **What the batch adds first.**
  - c0248: device records `fenolite.device.v0` (MPN, manufacturer, symbol, footprint, pins, ratings).
  - c0254: queries `resistor`/`capacitor`/`inductor`, the closed constraint keys per kind, matching and
    ranking, family rows `fenolite.family.v0` (generic, no MPN, device id `<family>@<IEC 60062 code>`),
    `pick.series.SERIES` (E6–E192 as integer mantissas), the lock's `[picks]`, `pick --propose`.
  - c0259: data records in TOML with stable ids derived from `(kind, canonical name)`, a semantic version,
    `licence`, `sources`, `evidence`, `reviewed_by`.
- **Licensing** (research section 1). An ordering code and its validity matrix are facts of a public
  datasheet; Fenolite authors its own description of them, one series per file, with the datasheet as
  source. Nothing is taken from a distributor or aggregator answer (EU database right, terms of use) or
  from another CAD library. The core package ships **no real series**; c0266's data repository does.

## Goals / Non-Goals

**Goals**

- One authored file describes a whole series; nothing stores millions of rows.
- Every MPN the grammar can produce decodes back to the same parameters, and every MPN decodes in at most
  one way (checked statically, not by enumeration).
- c0254's queries pick exact MPNs from grammar families with the same matching, ranking and lock rules.
- Deterministic: same files and query, same candidates in the same order, same bytes.

**Non-Goals**

- No pricing, stock or lifecycle. No grammar for non-passive parts (ICs use c0248 device records).
- No fuzzy decode: an MPN either parses or gets a finding that names the failing position.

## Today and proposed

**Today (after c0254):**

```python
c = design.part(device=capacitor(farad("100n"), rating=volt(25), case="0603", dielectric="X7R"))
# picks Fenolite:C_0603_X7R_25V@100n: generic, no MPN; the BOM says "100n X7R 0603"
```

**Proposed:** the same line, with a grammar family in `devices/families/` (or a family item vendored from `fenolite-library`, c0266),
picks `Example:EX_MLCC@EX03R104KAT`, an exact MPN with its manufacturer, recorded in the design lock:

```toml
[picks."C_in"]
query = "capacitor(100nF, rating>=25V, case=0603, dielectric=X7R)"
device = "Example:EX_MLCC@EX03R104KAT"
row = "Example:EX_MLCC"
catalog = "project:devices/families/example_mlcc.toml"
sha256 = "…"                     # SHA-256 of the candidate's canonical text (decision 8)
by = "query"
```

```
$ fenolite family decode EX05C471JBT --project examples/families --json --fields result.decoded
{"result": {"decoded": [{"mpn": "EX05C471JBT", "family": "Example:EX_MLCC", "value": "470pF",
  "case": "0805", "dielectric": "C0G", "tolerance": "5%", "rating": "50V", "packing": "reel",
  "suffix": null, "in_matrix": true}]}}
```

## Decisions

### 1. `fenolite.family.v1`: a grammar, not a table

Illustrative grammar, authored for Fenolite (no real series; codes chosen for the example):

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
datasheet = "https://example.invalid/ex-mlcc.pdf"
symbol = "Fenolite:Capacitor"
pattern = "EX{size}{dielectric}{value}{tolerance}{voltage}{packing}"
tail = "none"                              # or "opaque"

[fields.size]
codes."03" = { case = "0603", footprint = "Fenolite:Chip_0603" }
codes."05" = { case = "0805", footprint = "Fenolite:Chip_0805" }

[fields.dielectric]
codes.R = { dielectric = "X7R" }
codes.C = { dielectric = "C0G" }

[fields.value]
scheme = "eia3"                            # two significant digits and a multiplier: 104 = 100 nF
unit = "pF"
series = "E12"

[fields.tolerance]
codes.K = { tolerance = "10%" }
codes.J = { tolerance = "5%" }

[fields.voltage]
codes.A = { rating = "25V" }
codes.B = { rating = "50V" }

[fields.packing]
role = "ordering"                          # does not change what the part is
prefer = "T"
codes.T = { packing = "reel" }
codes.B = { packing = "bulk" }

[[valid]]                                  # the validity matrix, row by row
size = "03"
dielectric = "R"
tolerance = ["K", "J"]
voltage = ["A", "B"]
value = { min = "100pF", max = "100nF" }

[[valid]]
size = "05"
dielectric = "C"
tolerance = "J"
voltage = "B"
value = { min = "10pF", max = "1nF" }

[[exclude]]                                # removes combinations a valid row admitted
size = "03"
voltage = "B"
value = { min = "47nF", max = "100nF" }
```

- **Keys.** `schema`, `id`, `kind` (`resistor`, `capacitor`, `inductor`), `summary`, `manufacturer`,
  `version`, `licence`, `evidence`, `sources`, `pattern`, `fields`, `valid` are required; `datasheet`,
  `symbol`, `footprint`, `pins`, `tail`, `exclude`, `reviewed_by` are optional; `symbol` and `footprint`
  may come from a family key or a code's attributes, and every candidate must end with both. Any other
  key is `FEN-3004` naming the file and the key, as c0254 does for v0. A higher schema is `FEN-3002`.
- **Pattern.** Literal text and `{field}` placeholders; literals are `[A-Z0-9-]`. Every placeholder names
  one field and every field appears once. Exactly one field has `scheme` (the value field).
- **Code attributes** are closed: the constraint keys of the family's kind in c0254 (decision 3 of c0254:
  `tolerance`, `power`, `voltage`, `case`, `series`, `tempco` for resistors; `tolerance`, `rating`,
  `case`, `dielectric`, `series` for capacitors; `tolerance`, `current`, `saturation`, `dcr`, `case` for
  inductors), plus `footprint`, `symbol` and `packing` (text). Quantities parse exactly with the
  `Quantity` grammar; a float never appears (`tomllib` with `parse_float=Decimal`, then refused).
- **Roles.** A field is `electrical` (default) or `ordering`. An ordering field names `prefer`, the code
  that encode uses, so one query gives one MPN per electrical combination; decode reads every code.
- **Alternatives considered.** A row table per series (what distributors publish): millions of rows,
  copied rather than authored, and no decode of unseen MPNs. A regular expression per series: no
  attributes, no static ambiguity check, no pruning. Rejected.

### 2. Relation to `fenolite.family.v0`

v0 (c0254) stays unchanged and readable: a generic family with a span and an E-series, no MPN. v1 is a
second schema read by the same row loader (`pick/rows.py` dispatches on `schema`). Both are pickable
rows; both cite sources per attribute.

- **Why not fold v0 into v1** (a grammar whose pattern is the IEC 60062 code): it would rewrite c0254's
  shipped files and their `CATALOG_VERSION` for no new behaviour, and a v0 device id is not an MPN.
  Rejected; a v0 family can still be written as a v1 grammar by a project if it wants one.
- **c0259.** A v1 file is a c0259 record of kind `family`: its stable id is c0259's id function over
  `("family", id)`, it carries `version`, `licence`, `sources`, `evidence` and `reviewed_by`. A candidate's
  stable id is computed on expansion over `("part", "<manufacturer>:<MPN>")` and never stored.

### 3. Value codes

`pick/grammar/valuecodes.py` encodes and decodes a value field, exactly, with integers:

| scheme | form | example (unit) |
|---|---|---|
| `eia3` | two significant digits, then a multiplier digit (power of ten); `R` marks the decimal point below 10 units | `104` = 100 nF (pF), `4R7` = 4.7 pF |
| `eia4` | three significant digits, then a multiplier digit; `R` as above | `1002` = 10 kΩ (Ω), `49R9` = 49.9 Ω |
| `eia96` | two-digit index into E96, then a multiplier letter | index into `pick.series.SERIES["E96"]` |
| `rkm` | the letter `R`, `K`, `M` or `G` as decimal point and multiplier | `4K7` = 4.7 kΩ, `100R` = 100 Ω |

- Each scheme has **one canonical spelling** per value; decode accepts only that spelling, so encode and
  decode are inverse on the domain. A value a scheme cannot spell is outside the field's domain.
- `eia96` takes the E96 mantissas from c0254's table; its multiplier letters are recorded in
  `docs/formats/library/value-codes.md` from a public page registered at task 0.2, label `INFERRED`.
  No table is transcribed from a paywalled standard.
- The value domain of a family is the union of its `[[valid]]` rows: the values of the field's `series`
  (or the row's own `series`, or an explicit `values` list) within the row's `min`..`max`, both included.

### 4. One parse per MPN: prefix-free fields

The lint checks, per field, that no code is a proper prefix of another (value codes of a scheme are
prefix-free by construction: fixed width for `eia3`, `eia4` and `eia96`; `rkm` is checked over the
family's domain). A concatenation of prefix-free codes with fixed literals decodes in exactly one way,
left to right, without backtracking. So ambiguity is a lint error on the file, never a runtime surprise,
and no enumeration of the family is needed to prove it.

- **Opaque tail.** With `tail = "opaque"`, characters left after the last field (`[A-Z0-9#/-]+`) are kept as
  `suffix`, unread. With `tail = "none"` they make the decode fail. An opaque tail may change what the
  known fields mean (a grade, a test level), so a decode with a tail is labelled `UNVERIFIED` and gives
  `family.suffix-opaque`.
- **Several families.** A decode tries every family in canonical id order; two full parses of one MPN
  from different families give `family.decode-ambiguous` (error) naming both.

### 5. Lazy expansion with pruning

`expand(family, query=None)` yields candidates in the **canonical order**: fields in pattern order, codes in
code-point order, values ascending. With a query, each electrical field's codes are first filtered by the
query's constraints on their attributes (c0254's matching rules), the value domain is cut to the values
the query admits (an exact `Quantity`: that value; a c0246 range: the values whose worst-case span lies
inside), and ordering fields are fixed to `prefer`. The product of the pruned domains is visited in order;
each combination is kept when some `[[valid]]` row admits it and no `[[exclude]]` row removes it.

- **Bound.** The size of the pruned product is known before the first step. Above
  `grammar.EXPANSION_LIMIT` (100 000) the expansion is refused with `family.expansion-limit` (error),
  naming the domain sizes, so a pick never depends on where an iteration stopped.
- Without a query (`fenolite family expand`), `--limit N` (default 50) lists the first N candidates and
  reports `truncated`.

### 6. Encode and decode

- **Encode** = expansion under a query, then c0254's ranking over the candidates (distance to the nominal,
  larger tolerance, smaller case, project before shipped, then the device id). `fenolite family encode
  QUERY` lists them; a pick takes the first.
- **Decode** = the left-to-right parse of decision 4, giving the attributes of every code, the value, the
  `suffix`, and `in_matrix`: whether the validity matrix admits the combination. A parse outside the matrix
  gives `family.decode-outside-matrix` (warning): the grammar may be incomplete, or the part may not exist.
  A failed parse gives `family.decode-no-match` (error) with the character position and the field that
  failed, per family whose literal prefix matched.

### 7. Candidates are c0248 devices

A candidate is built in memory as a `DeviceDef` of c0248, never written: `id = "<family id>@<MPN>"`,
`manufacturer`, `mpn`, `datasheet`, `symbol` and `footprint` (family or code attributes), the pin map
(`pins`, default symbol pins `1` and `2` on pads `1` and `2`, the rule c0254 states for pickable rows),
`kind`, `value`, the ratings (`rating`/`voltage` → `voltage.max`, `power` → `power.max`, `current` →
`current.max`) in c0248's integer units, `evidence` the family's (or `UNVERIFIED` with a tail), `sources`
the family's. The BOM thus carries the manufacturer and the exact MPN.

### 8. Picks and the lock

A grammar family is a row source of c0254 beside v0 families and discrete devices, read from the same
places (`devices/` beside the script, and `fenolite_library/devices`, vendored by `fenolite get`, c0266). The lock entry is c0254's, with:
`device` the candidate id, `row` the family id, `catalog` the source label c0254 (or `library:device/<id>@<version>`, c0266, for a vendored item)
defines, and `sha256` the SHA-256 of the **candidate's canonical text**: the family id and version, the MPN
and the sorted attributes. An edit of the grammar that leaves a locked candidate unchanged therefore keeps
its hash; one that changes it gives c0254's `pick.row-changed`; one that removes it, `pick.row-missing`.

### 9. Command `fenolite family`

`fenolite family {list|show ID|lint PATH...|decode MPN...|encode QUERY|expand ID} [--project PATH]
[--families DIR]... [--limit N]`, `mutates=False`, no subprocess, no network. Families come from the
project (`devices/` beside the script that `--project` names), every `--families DIR`, and family items vendored from `fenolite-library` (c0266).
`lint` exits 5 on an error finding; `decode` exits 5 when an MPN does not decode; `encode` exits 5 with
`pick.no-match` when nothing matches. The MCP server gets the tool by c0195's rule.

### 10. Codes

| code | severity | when |
|---|---|---|
| `family.ambiguous-code` | error | a code is a proper prefix of another code of the same field |
| `family.pattern-field` | error | a placeholder without a field, a field without a placeholder, or not one value field |
| `family.matrix-unknown-code` | error | a `[[valid]]` or `[[exclude]]` row names a code its field lacks |
| `family.value-unencodable` | error | a value of a row's domain the scheme cannot spell |
| `family.prefer-missing` | error | an ordering field without `prefer`, or `prefer` not among its codes |
| `family.source-missing` | error | a numeric attribute without a source |
| `family.matrix-empty-row` | warning | a `[[valid]]` row that admits no combination |
| `family.decode-no-match` | error | an MPN that no family parses |
| `family.decode-ambiguous` | error | an MPN that two families parse |
| `family.expansion-limit` | error | a pruned product above `EXPANSION_LIMIT` |
| `family.decode-outside-matrix` | warning | an MPN that parses outside the validity matrix |
| `family.suffix-opaque` | info | an MPN decoded with an opaque tail |

They are `fenolite.pick.grammar.codes.ISSUE_CODES`, explained by `fenolite explain` (heading `family`).
No new `FEN-` code: a malformed file is `FEN-3004`, a newer schema `FEN-3002`, an unknown family id
`FEN-2001`.

### 11. Evidence

`grammar.EVIDENCE` is `INFERRED` with `H-G-FAMILY-ROUNDTRIP`: on every expanded MPN of the authored
grammars, decode gives back the code combination and attributes, and on every canonical value of each
scheme, decode ∘ encode is the identity (property tests). A reply combines it with the family's label
(lowest wins); a decode with an opaque tail is `UNVERIFIED`.

## Files and public API

- `src/fenolite/pick/grammar/schema.py`: `GrammarFamily`, `Field`, `Code`, `MatrixRow`, `read_family(path)`.
- `valuecodes.py`: `encode_value(scheme, value, unit)`, `decode_value(scheme, text, unit)`.
- `lint.py`: `lint_family(family) -> list[Issue]`.
- `expand.py`: `expand(family, query=None) -> Iterator[Candidate]`, `EXPANSION_LIMIT`.
- `decode.py`: `decode(mpn, families) -> DecodeResult`; `encode(query, families)` lives in `pick/match.py`.
- `codes.py`: `ISSUE_CODES`, `EVIDENCE`.
- `src/fenolite/cli/cmd_family.py`. `examples/families/example_mlcc.toml` and
  `examples/families/example_chip_r.toml` (an `eia4` and an `rkm` resistor grammar, illustrative).

## Relation to the other changes of the batch

- **c0254** gives the queries, matching, ranking, the lock and the E-series; this change adds a row source.
- **c0259** gives the record keys and stable ids; a v1 family is one of its records.
- **c0248** gives the device a candidate becomes.
- **c0262** (`library check`) runs `lint_family` over the `families/` of a data tree.
- **c0264** and **c0267** decode the MPN of an imported or proposed part to fill its parameters from a
  Fenolite-authored grammar instead of a third-party file or answer.
- **c0266** ships the real series grammars as data, each cited and reviewed; the core ships none.

## Risks / Trade-offs

- **An incomplete grammar proposes a part that does not exist.** Mitigation: the validity matrix is
  required, encode never leaves it, decode outside it warns, and every candidate carries the family's
  evidence (`INFERRED` at best), so a reviewed pick is a human decision.
- **Prefix-free codes are too strict** for a series with variable-width codes that are not prefix-free.
  Then the series is split into two families, or the field is written as two fields; the lint names it.
- **Large families.** Pruning keeps a query's work proportional to what it admits; the limit is explicit.

## Open questions

1. **Real series in the data repository.** Is an authored description of a manufacturer's public
   ordering-code table acceptable as CC0 data in c0266? Recommended: yes, one series per file, authored
   from the datasheet and cited, never from a distributor's data; the maintainer confirms once.
2. **Ordering fields in queries.** Should a query or `design.defaults` choose packing (`packing="bulk"`)?
   Recommended: not now; `prefer` decides, and a pinned MPN covers the rest.
3. **Metric case codes** (c0254 question 5). Recommended: follow c0254 (inch codes only); a grammar maps its
   own size codes to inch cases.
4. **Expansion limit.** Recommended: 100 000, revisited with the first real packs.
