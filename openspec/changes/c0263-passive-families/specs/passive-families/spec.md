## ADDED Requirements

### Requirement: Grammar family records
A record of schema `fenolite.family.v1` SHALL state `id`, `kind`, `summary`, `manufacturer`, `version`, `licence`, `evidence`, `sources`, `pattern`, `fields` and at least one `[[valid]]` row, and MAY state `datasheet`, `symbol`, `footprint`, `pins`, `tail`, `exclude` and `reviewed_by`. Any other key, or a float, MUST raise `FormatError` (`FEN-3004`) naming the file and the key; a higher schema MUST give `FEN-3002`.

#### Scenario: An unknown key
- **GIVEN** a copy of `examples/families/example_mlcc.toml` with the top-level key `price = "0.01"`
- **WHEN** `uv run pytest tests/unit/pick/grammar/test_schema.py -k unknown_key` reads it
- **THEN** `FormatError` is raised with `FEN-3004` naming the file and `price`

### Requirement: Fields and code attributes
Every `{name}` placeholder of `pattern` SHALL name one field and every field SHALL appear once; exactly one field MUST have a `scheme`. Code attributes MUST be the c0254 constraint keys of the family's kind plus `footprint`, `symbol` and `packing`. A field of role `ordering` MUST name `prefer`, one of its codes.

#### Scenario: A field without a placeholder
- **GIVEN** a grammar with a field `grade` that `pattern` does not name
- **WHEN** `fenolite family lint` reads it
- **THEN** the exit code is 5 and `issues` hold `family.pattern-field` naming `grade`

### Requirement: Value-code schemes
`pick.grammar.valuecodes` SHALL encode and decode the schemes `eia3`, `eia4`, `eia96` and `rkm` with integers only, one canonical spelling per value; decode MUST refuse any other spelling, and `eia96` MUST index the E96 mantissas of `pick.series.SERIES`. Each scheme's rule MUST be recorded in `docs/formats/library/value-codes.md` with a registered source and `INFERRED`.

#### Scenario: Codes round-trip
- **WHEN** `uv run pytest tests/unit/pick/grammar/test_valuecodes.py` runs
- **THEN** `104` in `eia3` with unit pF is 100 nF, `4K7` in `rkm` with unit Ω is 4.7 kΩ, and for every value each scheme can spell, decoding its encoding gives the value back

### Requirement: Prefix-free fields
The lint SHALL report `family.ambiguous-code` (error) for every code that is a proper prefix of another code of the same field, and for an `rkm` value field whose spellings over the family's domain are not prefix-free. A family without lint errors MUST decode every string in at most one way.

#### Scenario: An ambiguous field
- **GIVEN** a grammar whose field `size` has the codes `0` and `03`
- **WHEN** `fenolite family lint` reads it
- **THEN** the exit code is 5 and `family.ambiguous-code` names `size`, `0` and `03`

### Requirement: Validity matrix
A combination SHALL be valid when some `[[valid]]` row admits it and no `[[exclude]]` row removes it. A row admits a combination when each field it names holds one of the row's codes and the value lies in its `min`..`max` (both included) and in its series or `values`; a field it omits is free. A row naming a missing code MUST give `family.matrix-unknown-code`.

#### Scenario: An excluded combination
- **GIVEN** `examples/families/example_mlcc.toml`
- **WHEN** `fenolite family decode EX03R104KBT --project examples/families --json` runs
- **THEN** the exit code is 0, the decoded entry has `in_matrix: false`, and `issues` hold `family.decode-outside-matrix`

### Requirement: Lazy expansion
`expand(family, query)` SHALL yield candidates in canonical order (fields in pattern order, codes in code-point order, values ascending) without building the full product: each field is first cut to the codes and values the query admits, ordering fields to `prefer`. A cut product above `EXPANSION_LIMIT` (100 000) MUST be refused with `family.expansion-limit` before the first step.

#### Scenario: A query prunes before it expands
- **GIVEN** a generated grammar of 10⁹ combinations and a query fixing case, dielectric, rating and an exact value
- **WHEN** `uv run pytest tests/unit/pick/grammar/test_expand.py -k prune` expands it
- **THEN** the candidates equal those of a brute-force filter over a small copy, and fewer than 100 combinations are visited

### Requirement: Encode
Encode SHALL expand every family of the query's kind under the query and rank the candidates with c0254's ranking; `fenolite family encode QUERY` MUST list them with `mpn`, `family`, `device` and the attributes, at most `--limit` (default 20), and exit 5 with `pick.no-match` when none matches.

#### Scenario: A query gives an exact MPN
- **WHEN** `fenolite family encode "capacitor(100nF, rating>=25V, case=0603, dielectric=X7R)" --project examples/families --json` runs
- **THEN** the exit code is 0 and the first entry is `EX03R104KAT` with the device `Example:EX_MLCC@EX03R104KAT`

### Requirement: Decode
Decode SHALL parse an MPN left to right against every family in id order and give, per full parse, the family, every attribute, the value, `suffix` and `in_matrix`. No parse MUST give `family.decode-no-match` naming the position and the field that failed; two parses from different families MUST give `family.decode-ambiguous`.

#### Scenario: A decode names where it failed
- **WHEN** `fenolite family decode EX07C471JBT --project examples/families --json` runs
- **THEN** the exit code is 5 and `family.decode-no-match` names `Example:EX_MLCC`, position 2 and the field `size`

### Requirement: Opaque tails
With `tail = "opaque"`, characters left after the last field SHALL be returned unread as `suffix`, the decoded entry MUST be labelled `UNVERIFIED` and give `family.suffix-opaque`; with `tail = "none"` they MUST make the parse fail. Encode MUST never produce a tail.

#### Scenario: A tail is kept, not read
- **GIVEN** `examples/families/example_chip_r.toml` with `tail = "opaque"`
- **WHEN** an MPN of that family followed by `-Q1` is decoded
- **THEN** the entry has `suffix: "-Q1"`, its evidence is `UNVERIFIED`, and `issues` hold `family.suffix-opaque`

### Requirement: Round-trip property
For every authored grammar under `examples/families/` and `tests/fixtures/families/`, decoding each expanded MPN SHALL give back its codes and attributes, and encoding each decoded combination SHALL give back the MPN; the hypothesis `H-G-FAMILY-ROUNDTRIP` MUST name this test.

#### Scenario: Every expanded MPN decodes to itself
- **WHEN** `uv run pytest tests/unit/pick/grammar/test_roundtrip.py` runs
- **THEN** every MPN expanded from the authored grammars decodes to one parse whose re-encoding is that MPN

### Requirement: Family codes
`family.ambiguous-code`, `family.pattern-field`, `family.matrix-unknown-code`, `family.value-unencodable`, `family.prefer-missing`, `family.source-missing`, `family.decode-no-match`, `family.decode-ambiguous`, `family.expansion-limit` (error), `family.matrix-empty-row`, `family.decode-outside-matrix` (warning) and `family.suffix-opaque` (info) SHALL be `pick.grammar.codes.ISSUE_CODES`, each explained by `fenolite explain`.

#### Scenario: Every family code is explained
- **WHEN** `uv run pytest tests/unit/cli/test_explain_cmd.py` runs
- **THEN** every `family.*` code has an entry whose `see` is the heading `family`

### Requirement: Illustrative grammars only in the core
The core package SHALL ship the grammar engine and no family that names a real manufacturer or MPN; the authored grammars of `examples/families/` and the tests MUST name an illustrative manufacturer, use `example.invalid` URLs and carry the authored-for-Fenolite line, and every numeric attribute MUST name a source.

#### Scenario: No real series in the package
- **WHEN** `uv run pytest tests/unit/pick/grammar/test_shipped.py` runs
- **THEN** no file under `src/fenolite/` has the schema `fenolite.family.v1`, and every grammar under `examples/families/` names `Example Passive` and only `example.invalid` URLs
