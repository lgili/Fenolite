## Why

c0032 and c0033 write generic bodies linked to schematic libraries that Fenolite does not write, so "Tools » Update From Libraries" has nothing to read. The maintainer needs the libraries to compile with real pins. A schematic library (`.SchLib`) is a compound file with one storage per component (S-0002, S-0131, S-0150). `kicad-cli sym upgrade` converts such a file into a KiCad library (S-0153), which gives a local oracle that c0032 and c0033 lacked.

## What Changes

- `fenolite build --target altium` also writes one `.SchLib` per library that the schematic links name. Each library holds one component per distinct symbol the design uses, and the project file lists every library it writes.
- Symbol source, chosen by the form of the lib id:
  - `<X>.SchLib:<name>` is an Altium link. Fenolite writes c0032's generic body with the union of the designators its parts use.
  - Any other `<nickname>:<name>` is a KiCad symbol, resolved as c0011 resolves it. Fenolite writes its pins (number, name, electrical type, position, orientation, length, shape, visibility), one part per unit with Part Zero for common pins, and a synthesised rectangle per part. They all go into `<name>.SchLib`, as c0035 puts KiCad footprints into `<name>.PcbLib`.
- The schematic draws each component from its library symbol, so "Update From Libraries" does not move pins. Stubs may now be vertical, and multi-unit symbols are placed one part per unit. A design whose lib ids all name `.SchLib` files keeps c0033's schematic bytes.
- `cfb.Storage`: nested storages in `write_compound`, a public API for c0035 (PcbLib, PcbDoc). Streams-only calls keep c0033's bytes.
- `schlib.py` and `altsym.py` (new): header keys, `Storage`, `SectionKeys` for names over 31 characters, binary pins, and text records for component, rectangle, designator, comment and footprint chain.
- New `altium.*` issue codes, the write kind `altium_schlib`, and the authored example `examples/altium_kicad/`, which has its own KiCad library.
- Oracle: `SymbolDef` → `.SchLib` → `kicad-cli sym upgrade` → Fenolite's `.kicad_sym` reader → compare, locally and in the `kicad-10` job; `kicad-9` is checked.
- Part L of `docs/evidence/altium-schematic.md` for Altium Designer. Sources S-0150 … S-0155 (AltiumSharp pinned to its 2023 version 1), hypotheses `H-A-SCHLIB-*`, and the fact page `docs/formats/altium/schematic-library.md`.
- Size: 6.25 design-days; the minimal scope is 4.0.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `altium-schematic-writer` (c0032): ADDED library, storage, pin, symbol and oracle rules; seven c0032 requirements MODIFIED (listed in design.md).
- `altium-build` (c0032): ADDED library build rules; MODIFIED "Altium build target", "Altium build outputs" (c0032) and "Altium schematic format option" (c0033).

## Non-goals

- PcbLib and PcbDoc (c0035), IntLib, DbLib, reading Altium files.
- Symbol graphics beyond one rectangle per part, alternate display modes (De Morgan), pin alternates, and `PinFrac`, `PinWideText` or other side streams.
- Copying a user's Altium library, or resolving `.SchLib` lib ids against real files.

## Evidence level required

- Container, records, pin bytes, mapping, refusals, determinism and CLI are checked mechanically: unit tests, the independent CFB reader and golden files.
- The facts that KiCad's importer reads (storages, header text, framing, pin layout, units, Part Zero, footprint name) must reach `ORACLE-VERIFIED(kicad-cli)` through the round trip on kicad-cli 10.0.6. KiCad 9.0 is recorded as observed.
- Altium-only facts stay `INFERRED` until the maintainer's report: `ALTIUM-VERIFIED(author-report; AD <x.y>; <date>; no artefact)` on the committed bytes, with a licence the maintainer may use (LEGAL.md block A). The build envelope stays `INFERRED` and experimental.

## Impact

- Extended: the `backends/altium` modules, `lens/altium.py`, `cmd_build.py` and both test readers.
- The sample's project file now lists `FenoliteSample.SchLib`; its schematic bytes do not change.
- Archive order: c0032 → c0033 → c0034.
