## Why

Every KiCad file Fenolite will read or write (board, footprint, symbol library, schematic, worksheet, library table) is an S-expression. Before any typed reader exists, the project needs one syntax layer that reads real files without losing a byte of meaning, writes text `kicad-cli` accepts, and lets typed readers keep what they do not model (the design-model "slots" rule). Public documentation covers only the basic syntax (S-0001); escapes, number spelling and the pretty-printer are observed behaviour (S-0020) and must be pinned down by tests against the corpus and the oracle now, while the layer is small.

## What Changes

- New package `fenolite.backends` and `fenolite.backends.kicad` with `PROVENANCE.md`.
- `backends/kicad/sexpr.py`: validated `Atom` (text as written + kind), `Node` (head + ordered children), `parse`, `parse_bytes`, `parse_fragment`, `load`, `dumps` (KiCad-style TAB printer or compact), `tree_equal`, `first_difference`, `walk`; string and exact integer-nanometre number helpers; `FormatError`s with byte offset and locator.
- `backends/kicad/slots.py`: split a node's children into `Modeled`/`Opaque` (from `fenolite.model.base`), with per-child minimum versions; rebuild them in original order with canonical insertion of new fields; carry slot lists, per relative locator, in the `kicad` extension bag (no model or schema change).
- Corpus: manifest rows for the KiCad demo boards at tags 10.0.6 and 9.0.9.1 (S-0023–S-0026), one file of each other S-expression kind, and three Apache-2.0 third-party boards (S-0027, S-0028), with neutral ids; `tools/corpus_fetch.py --uses/--exclude-uses`.
- RT0 test over the corpus, a slot-identity test, and oracle tests against recorded per-tool expectations: fixture outcomes, escapes, re-dump loads, re-save equality.
- CI job `kicad-10` in the official Docker image (S-0029), pinned by digest; required-resource mode so oracle tests fail instead of skipping there.
- `docs/formats/kicad/sexpr.md`, `docs/formats/kicad/corpus.md`; source rows S-0020–S-0029; hypotheses `H-K-SEXPR-*`, `H-K-FMT-*`.

## Capabilities

### New Capabilities
- `kicad-sexpr`: lexical grammar, atoms and nodes, rejections, fragment codec, string and number rules, KiCad-style and compact serialisation, tree equality, RT0 and oracle expectations.
- `kicad-slots`: splitting children into modelled and opaque slots, order-preserving rebuild, canonical insertion, persistence in extension bags.

### Modified Capabilities
- `corpus-policy`: KiCad demo and third-party rows (licence reading, origins, neutral ids, heavy files), selective fetch, derived-file detection.
- `ci-baseline`: the `kicad-10` Docker job and required-resource mode.

## Non-goals

- Typed readers or writers (board, footprint, symbol, schematic, project): changes c0008 and later. RT1/RT2 are not claimed here.
- Version detection, token inventory, gating, FUTURE_FORMAT: change c0007. The `kicad-9` job: c0007.
- The custom-rules file dialect (single quotes, comments anywhere, unit suffixes).
- Measuring byte identity with KiCad's formatter, and a throughput benchmark: moved to the typed board writer change.
- Streaming parse of very large boards; CLI commands (`fmt`, `roundtrip`); `backends/base.py`.
- Typed round-trips of old third-party boards: they are KiCad 7 or older and serve RT0 and the load checks only.

## Evidence level required

- Parser on well-formed files and slot identity: `CORPUS-VERIFIED` (RT0 on manifest files from two origins: KiCad demos and third-party boards).
- Mirrored rejections, number reading and writing, escapes and "kicad-cli loads what we wrote": `KICAD-VERIFIED` on `kicad-cli` 10.0.6 in the `kicad-10` job; 9.0 stays `INFERRED` until the `kicad-9` job (c0007).
- Pretty-printer byte identity: `INFERRED` (`H-K-FMT-*`), not measured here.

## Impact

- New code under `src/fenolite/backends/`; tests under `tests/unit/backends/kicad/`, `tests/corpus/`, `tests/kicad/`, `tests/residue/`; `.github/workflows/ci.yml`; `tests/conftest.py`; `tools/corpus_fetch.py`; `tests/corpus/manifest.toml`; `tests/data/`. No runtime dependency; no model or schema change. The budget is re-estimated at about one week (design, Budget).
