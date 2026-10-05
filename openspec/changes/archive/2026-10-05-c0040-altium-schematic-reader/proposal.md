## Why

Fenolite writes Altium schematics and schematic libraries, but it reads none. The v0.3 goal is to
read the second backend: import (c0043), verification (c0044) and sheet templates (c0046) all need
the records of files that Altium saved. The only readers today are test helpers
(`tests/_altium_read.py`). They accept only Fenolite's own output.

## What Changes

- **Product reader.** `fenolite.backends.altium.read.sch.read_schematic(data)` reads a `.SchDoc` or
  `.SchDot` in the binary or the ASCII form. `fenolite.backends.altium.read.schlib.read_schlib(data)`
  reads a `.SchLib`. Both take bytes and return frozen records. They write nothing.
- **Nothing is lost.** Every record keeps its exact payload. A property list keeps every key, in
  file order, with its spelling and its raw value bytes. A record id with no typed class is an
  `UnknownRecord`. Unknown streams and bytes after the last known field are kept. Encoding what was
  read gives the bytes that were read, stream by stream.
- **Typed records.** 43 record ids get a class: component, pin, graphics, wire, bus, label, port,
  power port, sheet symbol and entry, sheet, designator, parameter, template, image, the footprint
  chain and the harness records. Each class names the keys it models; the others are its
  `unknown_keys`.
- **Owner tree.** `OWNERINDEX` in `FileHeader`, the separate index of the `Additional` stream
  (`OWNERINDEXADDITIONALLIST`), and the rule of a library's `Data` stream. A child whose owner cannot
  be found is kept at the root with a warning.
- **Units.** A length is an exact count of 1/100 000 of a 10-mil unit, from the integer key and its
  `_FRAC` key, with a conversion to nanometres that says when it rounds.
- **Libraries.** The header, `SectionKeys`, one component per storage, binary pin records, and the
  pin side streams.
- **Parts and display modes.** `PARTCOUNT`, `OWNERPARTID` with Part Zero, `DISPLAYMODECOUNT` and
  `OWNERPARTDISPLAYMODE`, with queries per part and per mode.
- **Text.** Values are bytes. The text view uses the `%UTF8%` twin when there is one, else a
  Windows code page (default `cp1252`), or UTF-8 for an ASCII file that is valid UTF-8.
- **Corpus.** 18 new rows of public Altium-saved schematics and libraries, fetched at pinned
  commits and never committed.

## Capabilities

### New Capabilities

- `altium-schematic-reader`: 23 ADDED requirements.

### Modified Capabilities

- `corpus-policy`: ADDED "Altium schematic corpus rows".

## Non-goals

- No compound-file parsing: c0039 owns the container.
- No nets, no neutral model, no registered backend: c0043 builds connectivity and the `Design`.
- No CLI command: `inspect`, `check` and `diff` on Altium files are c0044.
- No drawing-sheet model: c0046 maps the template records.
- No PcbDoc, PcbLib or project files (c0041, c0042).
- No change to the writers or to `tests/_altium_read.py`.

## Evidence level required

- Framing, header, property lists, the owner tree and the read-then-encode identity:
  `CORPUS-VERIFIED`, on fetched files of three repositories (S-0187, S-0188, S-0277 to S-0279).
- Library pins, parts and display modes: `ORACLE-VERIFIED(kicad-cli)` where
  `kicad-cli sym upgrade` gives a second reading of the same library (S-0153); `INFERRED` for the
  fields it does not read.
- The meaning of each typed key: the label of its fact row (S-0130, S-0131, S-0150 version 1 at
  `afe7964` only), `INFERRED` unless the oracle reads it.
- The ASCII form: `INFERRED`. No public Altium-saved ASCII schematic was found. It is tested on
  Fenolite's own output and on corpus records rewritten one per line under `tmp_path`.

## Impact

- Code: `src/fenolite/backends/altium/read/sch/`, `read/schlib.py`; tests; a new format page.
- Depends on c0039 (`read.cfb`). Consumed by c0043, c0044 and c0046.
- Size: 9 design-days.
