## Why

c0032 writes Altium's ASCII schematic. On 2026-10-02 KiCad 10.0.6's schematic import read the ASCII sample with the correct nets, but the free Altium 365 Viewer refused it. The Viewer documents `.SchDoc` support (S-0149) and says nothing about the ASCII form; binary is Altium's default and recommended save format (S-0133). The binary schematic is a Compound File Binary container (MS-CFB, S-0145, covered by the Open Specification Promise, S-0146) whose `FileHeader` stream holds the same records as the ASCII file, length-prefixed (S-0130, S-0131, S-0147, S-0148). A small stdlib writer adds the form Altium writes by default and lets the maintainer check the files in the free Viewer, without a licence.

## What Changes

- `fenolite build DESIGN.py --out DIR --target altium` writes the binary `<name>.SchDoc` by default. `--altium-format ascii` writes c0032's ASCII form byte for byte. `--altium-format` with `--target kicad` is a usage error.
- `src/fenolite/backends/altium/cfb.py` (new): a stdlib MS-CFB version 3 writer of root-level streams: 512-byte sectors, mini stream for streams under 4096 bytes, regular sectors otherwise, an all-black directory tree, zero CLSIDs and timestamps, deterministic bytes. Output beyond the header's 109 FAT sectors (about 7 MB) is refused with `altium.schematic-too-large`.
- `src/fenolite/backends/altium/binary.py` (new): `FileHeader` holds c0032's record list with the binary header text, each record a 32-bit length word, the `|KEY=VALUE` text and a NUL. `Storage` holds only the icon-storage header record.
- Write kind `altium_schdoc_binary`, `result.schematic_format`, and the third kind in the `capabilities` entry.
- `tests/_cfb_read.py` (new, test code): an independent stdlib reader that checks every MS-CFB rule the writer relies on. A round trip through it and the record de-framing gives back exactly c0032's record list.
- A golden binary sample in `tests/data/altium/sample/binary/`, next to c0032's ASCII files. The protocol page `docs/evidence/altium-schematic.md` gets Part V, "Altium 365 Viewer opens the binary sample", and step A7 for Altium Designer.
- Sources S-0145 to S-0149; hypotheses `H-A-SCHBIN-*`; fact pages `docs/formats/altium/compound-file.md` and `schematic-binary.md`.
- Size: 3.25 design-days. The binary sample comes first, for the maintainer's Viewer check.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `altium-schematic-writer` (created by c0032): ADDED "Compound file container", "Binary schematic form", "Compound files read back".
- `altium-build` (created by c0032): ADDED "Altium schematic format option", "Binary sample and Viewer check", "Binary schematic is documented". Each names the c0032 requirement it extends.

## Non-goals

- The `Additional` stream, embedded images, binary pin records, DIFAT sectors and CFB version 4.
- Reading any Altium file; SchLib, PcbLib and PcbDoc writers; `%UTF8%` keys.
- A `kicad-cli` or `olefile` oracle. `kicad-cli` cannot read a schematic in either form, and a third-party reader is a dependency.
- Any change to c0032's records, layout, links, unique ids, project file or ASCII bytes.

## Evidence level required

- Container rules, framing, round trip, determinism, the size refusal and the CLI are mechanical: unit tests, the independent test reader with negative controls, the MS-CFB worked example rebuilt from its tables, and golden files. Format facts are `INFERRED` (S-0145, S-0130, S-0131, S-0142, S-0147, S-0148).
- The Viewer renders the binary sample: `ALTIUM-VERIFIED(author-report; A365 Viewer; <date>; no artefact)`. Altium Designer opens and compiles it: `ALTIUM-VERIFIED(author-report; AD <x.y>; <date>; no artefact)`. Both apply to the committed bytes only.
- The `build --target altium` envelope stays `INFERRED` and experimental.

## Impact

- Extended: `schdoc.py`, `project.py`, `lens/altium.py`, `cmd_build.py`, c0032's tests that read the schematic as text (now `form="ascii"`), `test_altium_rows.py`, `test_format_facts.py`, `docs/altium.md`, `docs/cli-contract.md`.
- No runtime dependency, model, schema, layering or FEN-code change.
- Archive order: c0032 first, then this change.
