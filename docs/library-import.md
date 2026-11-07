# Import a local component model

`fenolite library import SOURCE... --into devices` turns files already on your machine into a local
project device. It starts no subprocess and makes no network request. Read the source's terms before
sharing the project: every import carries `licence = "see source terms"`, `evidence = "UNVERIFIED"`
and `origin.shippable = false`, even when its input happens to be an authored Fenolite example.
`library.not-shippable` refuses an imported device in a shipped library item.

Review the plan, then confirm its ID with the same arguments:

```sh
fenolite library import part.zip --into devices --timestamp 2026-11-01T00:00:00Z --dry-run --json
fenolite library import part.zip --into devices --timestamp 2026-11-01T00:00:00Z --confirm --plan <plan_id> --json
```

A dry run exits 0. Omitting both writing flags asks for confirmation (exit 4). The ID binds the working
directory, arguments, source digests and existing targets. Changing any input invalidates it. The same
source, flags and timestamp give the same file bytes across projects; plan IDs repeat inside the same
unchanged project and differ across projects.

## Sources and selection

| source | imported data |
|---|---|
| `.kicad_sym` | selected symbol, resolving its `extends` chain |
| `.kicad_mod` | footprint pads, graphics and preserved KiCad constructs |
| `.SchLib` | pin facts through the existing Altium adapter; symbol redrawn with Fenolite's pin-table generator |
| `.PcbLib` | footprint through the existing Altium adapter |
| `.step`, `.stp` | unchanged bytes; only `ISO-10303-21;` and `FILE_SCHEMA` are checked |
| `.zip` | supported members read in memory, without extraction |

`.IntLib` exits 2 (`FEN-2001`): export separate `.SchLib` and `.PcbLib` files. Unknown archive members,
legacy `.lib`/`.mod` files and nested archives are listed as `library.import-skipped` and never inflated.
Multiple symbols or footprints require `--symbol NAME` or `--footprint NAME`; the hint lists up to 24
names in code-point order. `--prefer kicad|altium` defaults to KiCad. The other tool's selected footprint
is compared too (`library.import-sources-disagree`). Give at most one STEP body per device.

Without sources, `--symbol LIB:SYM --footprint LIB:FP` resolves library IDs as the build does. These
origins identify the resolved canonical source bytes. `catalog import` retains its legacy `--out FILE`
form and exact single-file bytes for one minor release, with `catalog.import-deprecated`. Its destination
uses the same project restrictions; its legacy import stamp also makes the record not shippable.

## Records and project use

The default ID is `Imported:<symbol name>`; `--id NS:NAME` selects a project namespace. `--manufacturer`,
`--mpn`, `--datasheet https://...`, `--ref-prefix` and repeatable `--pin FUNCTION=PIN[:PAD[+PAD]]` set its
identity and pin map. Pin names supply function names; identity pin numbers supply pad numbers. Missing
pads are `catalog.pin-without-pad` errors; additional unmapped pads give `catalog.pad-unmapped` warnings.

For `Imported:EXB6202`, the plan writes only under `devices/Imported/EXB6202/`:

- `device.toml` (the c0259 v1 device), `pins.toml` and `package.toml`;
- `EXB6202.kicad_sym` and `EXB6202.kicad_mod`, written by Fenolite's KiCad writers;
- `EXB6202.step` when supplied, copied byte for byte.

Every record holds `[origin]` with the tool, UTC date and `[[origin.source]]` rows: each source basename,
archive-relative member and SHA-256, including the archive itself. No source path is stored. A
`content_sha256` protects each canonical record; `[[origin.output]]` protects the associated files.
Stable IDs follow `(kind, canonical name)` in the [record format](library-records.md).

The pins and package include normalized geometry. Altium physical volumes remain in optional
`[[component_body]]` rows (integer lengths written with units, outline and projection status), so builds
retain them even though a KiCad footprint file has no intrinsic volume record. `symbol_file` and `footprint` reference the canonical
native files beside the records, retaining constructs outside the normalized subset. The build reads
those files, requires no library table, and copies the STEP under `lib/<NS>.3dshapes/` while keeping its
model transform. With no model entry, import adds one at offset and rotation zero and reports
`library.import-step-placement`; verify its render. STEP geometry remains unchecked.

```python
from fenolite.dsl import Design, mm

design = Design("local")
design.board(mm(24), mm(18))
design.part("U1", device="Imported:EXB6202").place(mm(12), mm(9))
```

`--into` must be relative and resolve inside the working directory. The installed package, library
cache, vendored `fenolite_library/` and trees containing shipped CC0 devices without an origin are
refused, including symlink aliases. The original archive is not copied into the device folder.

## Crosscheck and re-import

The classifier estimates a package from numbered copper pads, draws the existing family generator and
compares lands. `--package FILE|ID` uses an explicit family or catalog package. Counts, numbering and
pin 1 differences are errors with an explicit package and warnings for a guess. Pitch and land-size
findings remain warnings. An unknown family is informational; `--no-crosscheck` reports that it skipped
the comparison. Errors produce no plan. [Classifier facts and tolerances](formats/library/import-crosscheck.md)
are Fenolite-authored, `INFERRED` choices: 0.01 mm pitch, 0.10 mm centres, and the larger of 20 percent
or 0.10 mm for pad sizes. A match does not raise the device's evidence.

An unchanged import plans nothing. Identity or flag changes still take effect. Same-file replacements
are allowed for an unedited folder; a hand edit, including a review, gives `FEN-7001` unless
`--allow-lossy` explicitly permits replacement. A re-import that would remove an old output, such as
omitting a previously imported STEP, is refused even with that flag: use another `--id`. The shared
mutation protocol currently supports file writes, not file deletion.

## Archive limits

`fenolite.library.importer.zipsafe` enforces at most 2 000 entries, 64 MiB inflated per member and
256 MiB inflated in total, counting while reading. After 1 MiB, a member may not exceed 200:1
compression. Absolute names, drive letters, `..`, NUL, symbolic links, encryption and duplicate
case-folded names (after normalizing `\` to `/`) are refused with `FEN-3004`, naming the rule and
member. Every header is checked before supported members inflate. Output names come from the device
ID and never from archive members.

See the authored [example](../examples/library_import/README.md), [devices](devices.md) and
[CLI contract](cli-contract.md#library-import).

For parameters read from a PDF rather than downloaded CAD geometry, use [datasheet proposals](datasheet-proposals.md). Both workflows use the same project target boundary and canonical native/record writer; proposal provenance and review gates remain distinct.
