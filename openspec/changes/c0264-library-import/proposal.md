## Why

A user who needs a real part today downloads a model from a manufacturer or a model site (a `.zip` with
a `.kicad_sym`, a `.kicad_mod`, an Altium `.SchLib`/`.PcbLib` and a STEP file) and then wires it into a
Fenolite design by hand: a lib table, a `pad_map`, an MPN property, a model path. Nothing records where
the files came from, under which terms, or whether the download is even right. Broken downloads are
common (pads numbered differently from the symbol, pin 1 on the wrong corner, a body that does not sit
on the land).

Research section 4.6 of `docs/research/component-library.md` proposes a **local import**: Fenolite reads
what the user downloaded and writes a project device (c0248, in the record format of c0259) with its
origin, the SHA-256 of each source file, the licence `see source terms` and the evidence `UNVERIFIED`.
Section 1 explains why it must be local: the terms of those sites allow the user's own use and forbid
redistribution, so the import may never feed the shipped catalog or a device pack (c0266). The family
generators of c0260 give a cheap check of the download: the imported footprint is compared with what the
generator draws for the same package.

## What Changes

- **`fenolite library import SOURCE... --into DIR`** under the mutation protocol (`--dry-run`, then
  `--confirm --plan ID`). A source is a `.kicad_sym`, `.kicad_mod`, `.SchLib`, `.PcbLib`, `.step`/`.stp`
  file or a `.zip` holding them. `.IntLib` is refused with a hint until a later change documents and
  reads it (the Altium readers of c0040 and c0041 read `.SchLib` and `.PcbLib`; `.IntLib` is only
  classified by the project reader).
- **Output** in the project device tree of c0259 (`devices/<namespace>/<name>/`): `device.toml`,
  `pins.toml`, `package.toml`, the symbol and the footprint as canonical KiCad files written by
  Fenolite's own writers, and the STEP body copied byte for byte. Each record carries an `[origin]`
  table (tool, source file names, member paths, SHA-256 of every source, date), `licence = "see source
  terms"` and `evidence = "UNVERIFIED"`.
- **Never shipped.** `--into` must lie inside the project; the shipped catalog, an installed device pack
  and its cache are refused. A record with this origin is marked not shippable, and the pack checks of
  c0262/c0266 refuse it.
- **Zip safety.** Archives are read in memory with the standard library under fixed limits (entries,
  sizes, ratio), and entries with absolute paths, `..`, links, encryption or duplicate names are refused.
  Nothing is extracted to disk; nested archives are not opened.
- **Cross-check against the family generator** (c0260). The importer classifies the footprint into a
  family, derives its nominal parameters, draws the generator's footprint for them (or for the package
  given with `--package`) and reports differences in pad count, numbering, pin-1 corner, pitch, pad
  position and pad size as `library.import-*` findings, with tolerances authored for Fenolite
  (`INFERRED`). When a zip holds both a KiCad and an Altium footprint, the two are compared too.
- **Symbols.** A KiCad symbol is kept as read. An Altium symbol gives only its pins (the reader does not
  map body graphics), so the symbol is drawn from the pin table by c0261's generator.
- **Re-import** keeps the c0248 rules: an unchanged source plans nothing, an unedited record is replaced,
  a hand-edited record is refused with `FEN-7001`.
- **`catalog import` is superseded.** c0248's `fenolite catalog import --symbol LIB:SYM --footprint LIB:FP`
  becomes the lib-id form of the same importer (`library import --symbol LIB:SYM --footprint LIB:FP`),
  with the same record bytes; `catalog import` stays one release as an alias that reports
  `catalog.import-deprecated`.

## Non-goals

- No network: nothing is downloaded or uploaded. No supplier lookup (c0267).
- No `.IntLib`, legacy KiCad 5 (`.lib`, `.mod`), Eagle `.lbr` or proprietary exchange formats; they are
  listed as skipped.
- No geometry repair: a mismatch is a finding, never a silent fix.
- No STEP geometry parsing beyond a header check (no CAD kernel in the core).
- No raise of evidence: review is c0262's.

## Evidence level required

- Zip limits, record writing and cross-check: `INFERRED`, unit-tested on archives and files authored for
  Fenolite (hypothesis `H-L-IMPORT`).
- Imported devices: `UNVERIFIED` always. The KiCad job builds the example that uses an imported device
  and runs ERC and DRC with no new finding.

## Impact

- New: `src/fenolite/library/importer/` (sources, zip reader, records, cross-check), the `import`
  subcommand of `cli/cmd_library.py`, `docs/library-import.md`,
  `docs/formats/library/import-crosscheck.md`, `examples/library_import/`, authored test archives under
  `tests/data/library_import/`, tests.
- Changed: `cli/cmd_library.py` (subcommand dispatch), `cli/cmd_catalog.py` (alias), the guide page
  `parts.md`, `docs/cli-contract.md`, `CHANGELOG.md`.
- Depends on: c0248 (device records, provenance, `FEN-7001` rule), c0259 (record format, device tree,
  stable ids), c0260 (family generators and classifier), c0261 (symbol from pins). Used by c0262 (its
  checks run the cross-check on imported devices) and c0266 (refuses imported records).
- Size: about 6 design-days.
