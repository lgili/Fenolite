## Why

The build change (c0011) needs two writers that plan item 0009 still owes: footprint libraries and custom rules. Rules are the risky half. KiCad reads a `.kicad_dru` file only next to a project file, and any error disables every custom rule with exit 0 (`H-K-TOK-RULES-SILENT`). KiCad 9.0.9 also drops the whole file when one rule uses a 10.0-only construct (`H-K-TOK-RULES-DRIFT`). Real files use `#` comment lines and single-quoted names, which c0007's common-subset helper refuses. Unit suffixes and `'…'` literals inside conditions parse there, but nothing reads values exactly, lifts conditions into the model or keeps comments (S-0010, S-0038). Rule precedence and condition semantics are documented but unproved, so lowering the model's `RuleSet` needs proofs first.

## What Changes

- `backends/kicad/mod.py`: `write_footprint` and `write_pretty` write `.kicad_mod` files for target 9 or 10 through c0017's footprint emitter, in the definition's child order. `footprint_from` also reads footprints placed in boards, for a corpus round trip.
- `backends/kicad/dru.py` (new): the rules dialect front end (comment lines kept in place, units parsed exactly, single-quoted rule names refused with their line), `read_rules` and `write_rules`. Rules outside the model stay ordered opaque slots.
- `backends/kicad/rulemap.py` (new): the closed grammar shared by reader and writer: kind map, limits, selector table per KiCad major, exact mm values.
- `backends/kicad/lowering.py` (new, rules part): `lower_rules` emits the user's `RuleSet` in descending priority, with generated names and one rule per layer, and returns `LoweredRules(text, issues)`.
- Every rules text is self-checked before it is returned. Target 9 refuses the seven 10.0-only constructs, also inside preserved rules (`LossyWriteError`, FEN-7001); `--allow-lossy` drops them with a warning.
- Authored CC0 fixtures `tests/data/kicad/rules/*.kicad_dru` and an escapes footprint. Rules benches are built by the tests with c0017's writer and carry the 3 mm canary.
- `docs/formats/kicad/rules.md`; extended rows S-0010, S-0034 and S-0038; hypotheses `H-K-DRU-*`.

Estimated at 5.75 days (design, "Budget").

## Capabilities

### New Capabilities
- `rules-model`: lowering the neutral `RuleSet` to KiCad custom rules: order, kinds, selectors, layers, names, refusals and issue codes.

### Modified Capabilities
- `kicad-file-backend`: footprint files are written; custom rules files are read and written.
- `kicad-library-read`: board footprints read as definitions; written footprint files read back equal.
- `kicad-oracle`: rules proofs carry a canary.

## Non-goals

- Net classes in `.kicad_pro` and `rule_severities` (c0010).
- Differential pairs, length tuning, creepage and other rule kinds (v0.3). `assign_component_class` stays opaque.
- DRC findings as issues (c0020); `.kicad_wks` (c0012).
- Footprint generation from scratch, and imitating KiCad's save-time sort of pads and graphics.
- Changes to `wrap_rules` and `rules_text`, which keep their common-subset contract.

## Evidence level required

- Footprint codec round trip: `CORPUS-VERIFIED` over demo boards and upgraded third-party copies, which settles the footprint half of `H-K-LIB-READ`. Written mini library: `KICAD-VERIFIED` on 10.0.6 (`kicad-10`) and 9.0.9 (`kicad-9`) by load, re-save and re-read. The 9.0 half of `H-K-SEXPR-ESCAPES` becomes `KICAD-VERIFIED`.
- Rule order, each selector op, each kind, the dialect and the single-quote drop: `KICAD-VERIFIED` per major (`H-K-DRU-*`). Every proof is judged by the canary. A selector op is written for a target only after its proof passed there.
- The rules header `(version 1)` stays `INFERRED` (`H-K-TOK-CONSTANTS`).

## Impact

- New modules `dru.py`, `rulemap.py` and `lowering.py`; `mod.py` extended. Tests under `tests/unit/`, `tests/corpus/` and `tests/kicad/`. Rows in `PROVENANCE.md`, `LEGAL-ANNEX.md`, both registers and the per-version probe files.
- No runtime dependency, no model or schema change, and no new CLI code (FEN-7001 exists). The KiCad capability report lists `kicad_mod` and `kicad_dru` as written kinds, and `lower` as an operation.
- Depends on c0017 (board writer, footprint emitter, `LossyWriteError`, DRC reader, `_probes`), and through it on c0009 and c0014.
