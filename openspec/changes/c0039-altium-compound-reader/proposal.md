## Why

v0.3 reads the second backend. Every binary Altium file (`.SchDoc`, `.SchLib`, `.PcbDoc`, `.PcbLib`) is an MS-CFB compound file (S-0145, S-0002), so c0040 to c0044 all need one container reader. Fenolite has only a test reader, `tests/_cfb_read.py`, which checks Fenolite's own output and refuses DIFAT sectors. A public 10 MB board uses a DIFAT sector (S-0188), so that reader cannot open it.

A census of 23 public Altium-written files from eight repositories (2026-10-03) shows what a product reader needs. All are version 3 with red and black entries. Most carry a root modified time, some a root CLSID, and storages carry times. One uses DIFAT. None breaks an MS-CFB rule. So the tolerance Altium needs is small and is stated fact by fact.

## What Changes

- `src/fenolite/backends/altium/read/cfb.py` (new package `backends/altium/read/`): `open_compound(data)` and `read_compound(path)` return a `CompoundFile`: storages and streams by path, stream bytes, entry metadata, the header and notes.
  - Versions 3 and 4, DIFAT sectors, the mini stream, empty streams.
  - Accepted silently: what MS-CFB allows and Altium writes. Notes (nine `cfb.note.*` issues): broken rules that leave the bytes unambiguous, such as high size bits, which MS-CFB recommends ignoring. `strict=True` raises them.
  - Errors are `CompoundError` (a `FormatError`): a rule code from a closed table, a locator (`stream:<path>`, `directory[<i>]`, …) and a byte offset.
  - Bounded: `Limits` (file size, entries, nesting), cycle detection in every walk, no sector shared by two chains. Work is linear, and the streams never exceed the file.
- `fenolite inspect FILE --streams`: the header facts, counts, and every storage and stream with its size and SHA-256. Notes are issues; an unreadable file exits 3 with `FEN-3004` and its location.
- Corpus: ten public Altium-written files (four PCB documents, two PCB libraries, four schematics; five repositories; MIT, Apache-2.0, LGPL-3.0), fetch-only, with a manifest rule for second-backend rows.
- `tests/_cfb_build.py` (test code): version 3 and 4 containers with DIFAT sectors, metadata and faults.
- `compound-file.md` gains the reading facts; hypotheses `H-A-RD-CFB-*`. No new source id is registered.
- Size: 4.75 design-days.

## Capabilities

### New Capabilities
- `altium-compound-reader`: "Compound file reading", "Compound file tolerances", "Located compound file errors", "Bounded reading of hostile files", "Compound reader on public files", "Compound reader is documented".

### Modified Capabilities
- `cli-contract`: MODIFIED "Inspect command" (two views); ADDED "Inspect stream tree".
- `corpus-policy`: ADDED "Second-backend corpus rows".

## Non-goals

- Interpreting any stream: records, property text, compression. That is c0040 and c0041.
- A registered Altium backend, or `inspect --summary`, `check` and `diff` on Altium files (c0043, c0044).
- Writing version 4 or DIFAT sectors; any change to `backends/altium/cfb.py`'s output.
- Repairing a broken container.
- A third-party reader as a dependency or as an oracle.

## Evidence level required

- Parsing, tolerances, errors, limits and the view are mechanical: authored containers, one mutation per rule, a fuzz test, the MS-CFB worked example, Fenolite's golden files.
- Version 3 reading, DIFAT included: `CORPUS-VERIFIED` when the ten rows read with no error, each allocated sector belongs to one owner, and the rows without DIFAT equal the independent test reader stream for stream. Until then `INFERRED`.
- Version 4: `INFERRED` (S-0145); no public version 4 file is known.

## Impact

- New: `backends/altium/read/`, tests, corpus rows. Extended: `cmd_inspect.py`, manifest and fact tests, the fact page, `docs/altium.md`, `docs/cli-contract.md`.
- No runtime dependency, model, schema or layering change.
- c0040 to c0044 consume `open_compound`, `CompoundFile`, `Node`, `CompoundError` and `Limits`.
- Archive order: after c0037 and c0038, which register S-0187, S-0188 and S-0199; before c0040 to c0044.
