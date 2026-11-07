## Why

Passives are 80–90 % of the rows of a typical BOM (`docs/research/component-library.md`, section 4.10),
and each manufacturer series is sold as thousands of exact part numbers. c0254 lets a script ask for
`capacitor(farad("100n"), rating=volt(25), case="0603")`, but its `fenolite.family.v0` rows are generic:
a case, a tolerance, an E-series and a span, never an orderable part. The research (section 4.5) proposes
describing each series **once**, from its public datasheet: the fields of its ordering code, the codes of
each field, the value code, and the validity matrix (which value exists at which size and voltage). Parts
are then expanded **lazily** into exact MPNs, and an MPN read anywhere (a BOM, a supplier answer, an
imported file) can be decoded back into its parameters.

## What Changes

- **Grammar families** (`fenolite.family.v1`, TOML): `pattern`, `fields` (each code mapping to closed
  attributes: case, footprint, dielectric, tolerance, ratings, packing), a value field with a value-code
  scheme (`eia3`, `eia4`, `eia96`, `rkm`), the validity matrix (`[[valid]]` and `[[exclude]]` rows),
  an optional opaque tail, and the common record keys of c0259 (stable id, version, licence, sources,
  evidence). `fenolite.family.v0` stays as c0254 defines it.
- **Engine** `fenolite.pick.grammar`: a static lint (every field's codes are prefix-free, so every MPN
  parses one way), lazy expansion in a canonical order with per-field pruning by a c0254 query, **encode**
  (query → ranked MPNs) and **decode** (MPN → parameters, unknown tails kept opaque).
- **Picks.** A grammar family is a c0254 row source: its candidates are c0248 devices with
  `id = "<family id>@<MPN>"`, an MPN and a manufacturer, and a pick records them in the design lock.
- **Command** `fenolite family list|show|lint|decode|encode|expand`, read-only.
- **Data.** The core ships the engine and one **illustrative** grammar (`Example Passive`, authored for
  Fenolite, `example.invalid`) in `examples/families/` and the tests. Real series grammars go to the data
  repository of c0266, one file per series, each cited to its public datasheet.

## Capabilities

### New Capabilities

- `passive-families`: the v1 schema, value codes, lint, expansion, encode, decode and their codes.

### Modified Capabilities

- `part-selection` (c0254): ADDED "Grammar family rows" and "Picks of grammar candidates".
- `cli-contract`: ADDED "Family command".

## Dependencies

c0254 (queries, matching, ranking, rows, E-series, the lock's `[picks]`), c0259 (record keys and stable
ids), c0248 (device records a candidate becomes). Used by c0266 (series grammars shipped as data), c0264
and c0267 (decode an imported or proposed MPN). Implemented after c0254 and c0259.

## Non-goals

- No real manufacturer table in the core package; no table copied from a distributor, an aggregator or
  another CAD library.
- No price, stock or lifecycle; no generic family is replaced.
- No inductor value grammar beyond the same schemes; no polarised parts (c0254 scope).

## Evidence level required

- Lint, expansion, encode and decode: `INFERRED`, proven by property tests (decode ∘ encode is the
  identity on every expanded MPN of the authored grammars), hypothesis `H-G-FAMILY-ROUNDTRIP`.
- Value-code facts: `INFERRED` from registered public pages (`docs/formats/library/value-codes.md`).
- A family's attributes: the label of their source, never above it.

## Impact

- New: `src/fenolite/pick/grammar/` (`schema.py`, `valuecodes.py`, `lint.py`, `expand.py`, `decode.py`,
  `codes.py`), `src/fenolite/cli/cmd_family.py`, `examples/families/`, `tests/unit/pick/grammar/`,
  `docs/formats/library/value-codes.md`.
- Changed: `pick/rows.py`, `pick/match.py`, `docs/picking.md`, `docs/cli-contract.md`, guide pages
  `commands`, `parts` and `recovery`, `explain.toml`.
- Size: about 6 design-days.
