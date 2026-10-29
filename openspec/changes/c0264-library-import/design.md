## Context

- **Source.** `docs/research/component-library.md`, section 1 (licences: model sites and manufacturer
  CAD are use **(d)**, "the user downloads and Fenolite imports locally") and section 4.6. Table of
  section 5: c0264 depends on c0259 and c0260.
- **What exists on `dev` (0.6.0).**
  - KiCad readers: `backends.kicad.mod.read_footprint` and the symbol reader of `kicad-library-read`,
    both with `Provenance(file_sha256, locator)`, and the writers `write_footprint` and
    `sym.write_symbol_library`. A footprint read and written again is equal in the model ("Footprint
    files written by Fenolite read back equal").
  - Altium readers: `read_schlib` (c0040) and `read_pcblib` (c0041), mapped to `SymbolDef` and
    `FootprintDef` by `import_symbols` and `import_footprints` (`altium-import`, "Symbol libraries",
    "Footprint libraries"). Symbol body graphics are counted as unmapped. `.IntLib` is only a file kind
    in the project reader (`backends/altium/read/project.py`); there is no reader.
  - `fenolite library PATH --out LIB.pretty` (c0223) already exists: it makes a footprint library from a
    board. The package `fenolite.library` may import `model`, `geometry` and `backends`.
  - `fenolite models --vendor` copies model files into the project's `3dmodels/`, and a STEP export reads
    that folder first.
  - No zip is read anywhere in the core today (`zipfile` is used to write the kit and to look into a jar).
- **What the batch proposes.** c0248: device records, `catalog import` with a provenance stamp, the
  `edited` detection and the `FEN-7001` no-clobber rule. c0259: the record files (`package`, `pins`,
  `device`, `part`), the project device tree and stable ids from `(kind, canonical name)`. c0260: per
  family generators and a land calculator. c0261: symbol from a pin table. c0262: `library check`,
  `library review`. c0266: device kinds of `fenolite-library` (c0279), vendored by `fenolite get`.

## Goals / Non-Goals

**Goals**

- One command turns a downloaded archive into a project device that a design can place with
  `design.part(ref, device=...)`, with no hand wiring.
- Every imported byte is traceable: source name, member path, SHA-256, date, tool.
- Imported data can never reach the shipped catalog or `fenolite-library`, by construction and by a check.
- A hostile or broken archive cannot write outside `--into`, exhaust memory or hide a file.
- A broken download is caught at import by comparison with the generator, not at the assembly house.
- Same sources, same flags, same `--timestamp` give the same bytes.

**Non-Goals**

- See the proposal. In addition: no merge of two imports into one device, no multi-footprint devices
  (one footprint per device, as c0248), no edit of the imported geometry.

## Decisions

### 1. Command surface and the `library` subcommands

```
fenolite library import ~/Downloads/EXB6202.zip --into devices/ --dry-run --json
fenolite library import ~/Downloads/EXB6202.zip --into devices/ --confirm --plan <plan_id>
fenolite library import EXB6202.kicad_sym EXB6202.kicad_mod exb6202.step --into devices/ \
    --id Proj:EXB6202 --symbol EXB6202 --footprint SOIC-8_3.9x4.9mm --package SOIC-8_3.9x4.9mm_P1.27mm
fenolite library import --symbol Fenolite:Resistor --footprint Fenolite:Chip_0603 --id Proj:R0603 \
    --into devices/                                   # lib-id form (was `catalog import`)
```

- `library` already takes a board path (c0223). The first positional word picks a subcommand when it is
  one of the reserved words `import`, `propose` (c0265), `check`, `review` (c0262) and `seed` (c0266);
  anything else keeps the c0223 form unchanged. A board path that is literally one of those words is
  written `./import`. Whichever library change lands first adds this dispatch; the others add their word.
  *Alternative:* a new top-level command `devices`. Rejected: the research and every change of the
  batch say `fenolite library ...`, and one noun for the library is easier to teach.
- Options:

  | option | meaning |
  |---|---|
  | `SOURCE...` | files or `.zip` archives; paths may be absolute (they are the user's downloads) |
  | `--into DIR` | required; a relative folder inside the project (decision 6) |
  | `--id NS:NAME` | the device id; default `Imported:<name>` from the symbol name |
  | `--symbol NAME`, `--footprint NAME` | pick an item inside the sources when there are several; without a source they are lib ids (lib-id form) |
  | `--prefer kicad\|altium` | which source wins when both kinds are present (default `kicad`); the other is cross-checked |
  | `--package NAME` | a package record (c0259) to compare with, instead of the classifier's guess |
  | `--pin FUNCTION=PIN[:PAD[+PAD]]` | as c0248's `catalog import` |
  | `--manufacturer`, `--mpn`, `--datasheet URL` | identity fields of the device |
  | `--no-crosscheck` | skip decision 7 (reported as `library.import-crosscheck-skipped`, info) |

- It is `mutates=True`; the MCP server exposes it by c0195's rule. Its `example_args` use authored
  files of `tests/data/library_import/`, so the consistency suite runs offline.

### 2. Sources and what is read from each

| input | reader | what the device takes |
|---|---|---|
| `.kicad_sym` | KiCad symbol reader, `resolve_extends` | the symbol as read, its pins |
| `.kicad_mod` | `read_footprint` | the footprint as read, its pads, its `model` entries |
| `.SchLib` | `read_schlib` + `import_symbols` | the pins only; the symbol is drawn by c0261 (`library.import-symbol-regenerated`, info) |
| `.PcbLib` | `read_pcblib` + `import_footprints` | the footprint (pads, graphics, bodies) |
| `.step`, `.stp` | header check only | the body file, copied byte for byte |
| `.zip` | decision 5 | each member above, by extension |
| `.IntLib` | none | refused: `FEN-2001`, hint "export the .SchLib and .PcbLib from Altium, or wait for the IntLib reader" |
| anything else in a zip | none | `library.import-skipped` (info) with the member path and the reason (`legacy KiCad 5 library`, `unsupported format`, `nested archive`) |

- **Choosing the items.** A source with several symbols or footprints needs `--symbol`/`--footprint`;
  without it the command exits 2 (`FEN-2001`) and the hint lists the names (sorted, at most 24). With
  exactly one symbol and one footprint nothing needs to be named.
- **Several kinds of the same item.** A zip from a model site usually holds the part for several tools.
  The preferred kind (`--prefer`) is imported; a footprint of the other kind is compared with it
  (decision 7, `library.import-sources-disagree`).
- **STEP.** The file must start with `ISO-10303-21;` and hold `FILE_SCHEMA`; otherwise `FEN-3004`
  naming the member. No geometry is read (`library.import-step-unchecked`, info, says so). When the
  footprint names a model, the imported footprint's model entry is rewritten to the copied file; when
  it names none and one STEP is given, one entry with offset 0 and rotation 0 is added and
  `library.import-step-placement` (info) asks to check the render of c0262.
- *Why no `.IntLib` now.* An integrated library is a compound file that holds compiled library streams.
  Its layout is not in `docs/formats/altium/`, and the clean-room rule asks for public facts and an
  evidence label before a reader. Open question 1.

### 3. What is written

```
devices/Proj/EXB6202/
  device.toml          # fenolite.device.v0 (c0248, as extended by c0259) + [origin]
  pins.toml            # fenolite.pins.v0 (c0259), from the symbol pins
  package.toml         # fenolite.package.v0 (c0259), family "imported" or the classified family
  EXB6202.kicad_sym    # canonical, written by sym.write_symbol_library
  EXB6202.kicad_mod    # canonical, written by write_footprint
  EXB6202.step         # the source bytes, unchanged
```

```toml
# device.toml (illustrative; authored for Fenolite)
schema = "fenolite.device.v0"
id = "Proj:EXB6202"
summary = "imported from EXB6202.zip"
manufacturer = "Example Semi"
mpn = "EXB6202"
symbol = "Proj:EXB6202"
footprint = "Proj:EXB6202"
pins = "pins.toml"
package = "package.toml"
evidence = "UNVERIFIED"
licence = "see source terms"

[origin]
tool = "fenolite library import"
date = "2026-10-29"
shippable = false
[[origin.source]]
file = "EXB6202.zip"                     # a base name, never a path
member = "KiCad/EXB6202.kicad_mod"
sha256 = "<64 hex>"                      # of the member bytes
[[origin.source]]
file = "EXB6202.zip"
sha256 = "<64 hex>"                      # of the archive

[provenance]                             # c0248's stamp: digest of this record
tool = "fenolite library import"
source = "EXB6202.zip"
date = "2026-10-29"
sha256 = "<64 hex>"
```

- `licence = "see source terms"` is a fixed text: Fenolite cannot know the terms of a download, and the
  user accepted them. `library.import-terms` (info, once per import) says that sharing the project may be
  limited by those terms.
- `package.toml` has `family = "imported"` and `footprint = "<name>.kicad_mod"` when no family matched.
  When the classifier matched a family (decision 7), it also holds the derived nominal parameters with
  `derived = "imported footprint"`; the footprint used by builds is still the imported file, never the
  generated one.
- The symbol and footprint files are written by Fenolite's KiCad writers at the build target. They
  resolve as `<namespace>:<name>` through c0259's project device loading, so no lib table is needed.
  An Altium build writes them into `.SchLib`/`.PcbLib` through the existing writers, like any other
  definition.
- **Stable ids.** The record ids follow c0259: derived from `(kind, canonical name)`, so the same import
  gives the same ids.
- **Byte identity.** Same sources and flags and the same `--timestamp` give the same plan and bytes.

### 4. Pins and pads

- Function names, the identity pin-to-pad map, `--pin` and the codes `catalog.pin-without-pad` and
  `catalog.pad-unmapped` are c0248's `catalog import` rules, moved into the importer and shared. This
  change renames nothing.
- The pin `type` of `pins.toml` comes from the symbol's electrical type; `group` is left empty (c0261's
  layout rule reads it when present, and falls back to the type).

### 5. Zip safety

Archives are read with `zipfile` from the standard library, **in memory**, never extracted:

| rule | limit or behaviour | on failure |
|---|---|---|
| entries | at most 2 000 | `FEN-3004` |
| one member, uncompressed | at most 64 MiB, counted while reading (header sizes are not trusted) | `FEN-3004` |
| all members read | at most 256 MiB | `FEN-3004` |
| ratio | at most 200:1 per member once 1 MiB has been read | `FEN-3004` |
| names | no absolute path, no drive letter, no `..` segment, no NUL; `\` read as `/` | `FEN-3004` |
| duplicates | two names equal under `str.casefold` after normalisation | `FEN-3004` |
| links | a member whose Unix mode is a symbolic link | `FEN-3004` |
| encryption | an encrypted member | `FEN-3004` |
| nested archives | not opened | `library.import-skipped` |
| unknown members | not read past their header | `library.import-skipped` |

- Only members with a known extension are read; the others are listed and never decompressed.
- The message of `FEN-3004` names the archive, the member and the rule. Nothing is planned.
- The limits are constants of `fenolite.library.importer.zipsafe`, documented in
  `docs/library-import.md`. They are Fenolite's choices (`INFERRED`), sized from the archives the
  research names (tens of files, a few MiB).
- Output paths never come from member names: they are built from the device id (decision 3), so a member
  name cannot steer a write.

### 6. Never into the shipped catalog or the library

- `--into` must be relative, resolve inside the working directory, and contain no `..` after
  normalisation. It must not be inside the installed `fenolite` package, a vendored library folder
  (`fenolite_library/`, c0279) or the library cache, or any folder whose
  `device.toml` files carry `licence = "CC0-1.0"` and no `[origin]`. Each case exits 2 with `FEN-2001`.
- `origin.shippable = false` is written on every imported record. `fenolite.library.importer.shippable(
  record) -> bool` is false for it, and for any record with `licence = "see source terms"`. c0262's check
  and `fenolite library audit` (c0266, c0279) call it and refuse the record (`library.not-shippable`, error, defined
  here).
- Nothing is uploaded; no subprocess runs; no network module is imported.

### 7. Cross-check against the family generator

```
imported footprint ─▶ classify ─▶ family + nominal parameters ─▶ c0260 generator ─▶ reference footprint
          └──────────────────────────── compare pads ◀────────────────────────────────────┘
```

- **Classify.** `classify(footprint) -> Match | None` reads only the pads: count, rows or a grid, pitch,
  row spacing, the exposed pad, the numbering order. It recognises the families of c0260 (`chip`,
  `molded`, `gullwing`, `nolead`, `grid`, `to`, `dip`, `header`; a `connector` series only with
  `--package`). It returns the
  family and nominal parameters, or `None` (`library.import-family-unknown`, info: no cross-check).
  With `--package NAME` the package record is used instead, and a family that disagrees with it is
  `library.import-package-mismatch` (error).
- **Compare.** The reference footprint is drawn by c0260's `generate(package)` for those parameters (the manufacturer land of
  the package, when the record has one, wins as in c0260). Pads are matched by number.

  | finding | severity | when |
  |---|---|---|
  | `library.import-pad-count` | error with `--package`, else warning | pad counts differ (exposed pads counted apart) |
  | `library.import-numbering` | error with `--package`, else warning | the same pad positions carry other numbers (for example clockwise numbering) |
  | `library.import-pin1` | error with `--package`, else warning | pad 1 is not at the family's pin-1 position |
  | `library.import-pitch` | warning | pitch differs by more than the tolerance |
  | `library.import-land` | warning | a pad centre or size differs by more than the tolerance |
  | `library.import-sources-disagree` | warning | the KiCad and Altium footprints of one archive differ by the same rules |

- **Tolerances** are Fenolite-authored constants in `docs/formats/library/import-crosscheck.md`,
  labelled `INFERRED`, never taken from IPC tables: pitch 0.01 mm, pad centre 0.10 mm, pad size 20 % of
  the reference size or 0.10 mm, whichever is larger. A warning names the pad, the measured and the
  reference value in nm.
- Errors stop the plan (the contract: no write beside an error finding). Warnings are reported and the
  import proceeds: a manufacturer land may differ from the calculator on purpose.
- **Used later.** `crosscheck(footprint, package=None)` is public in `fenolite.library.importer`, so
  c0262's `library check` runs it on any device whose package family is `imported`.

### 8. Re-import

- A device folder that exists and whose `[origin]` sources have the same SHA-256 values: nothing is
  planned, and `result.unchanged` is true (exit 0).
- An unedited record (c0248's `edited` is false) with other sources: the folder is replaced as one plan.
- An edited record: exit 7 with `FEN-7001`, hint "keep the folder, import under another --id, or pass
  `--allow-lossy`". A hand review that raised the evidence is such an edit, so a reviewed device is
  never overwritten silently.

### 9. `catalog import` (c0248): superseded, one implementation

- *Decision:* **supersede, keep one release as an alias.** `fenolite library import --symbol LIB:SYM
  --footprint LIB:FP --id NS:NAME --into DIR` is c0248's command with the device written into the c0259
  tree. `fenolite catalog import ...` keeps its arguments and calls the same importer, which writes
  c0248's single-file record to `--out` with the same bytes as before, and adds
  `catalog.import-deprecated` (info) naming `library import`.
  The alias is removed by the release after the one that ships this change.
- *Alternatives considered:* (a) **merge into `catalog import`** with file sources. Rejected: `catalog`
  is the read-only shipped catalog, and an import writes into the project; the name would mislead. (b)
  **keep both apart.** Rejected: two implementations of the pin template, the stamp and the no-clobber
  rule would drift.
- If c0248 has not been archived when this change is implemented, task 0.1 moves the shared code into
  `fenolite.library.importer` in c0248's own implementation instead.

### 10. Result

`result` (schema `fenolite.library-import.v0`): `device` (id), `folder`, `sources` (one row per read
source: `file`, `member`, `kind`, `sha256`), `skipped` (`file`, `member`, `reason`), `symbol`,
`footprint`, `step`, `family` (or `null`), `crosscheck` (`reference`, `tolerances`, `rows`), `unchanged`,
and the usual `plan`. The envelope evidence is `INFERRED` (`H-L-IMPORT`); the device's own label,
`UNVERIFIED`, is a field of the result.

## Codes introduced

| code | severity / exit | when |
|---|---|---|
| `library.import-skipped` | info | a source member is not read (format, nesting) |
| `library.import-symbol-regenerated` | info | an Altium symbol is drawn from its pins |
| `library.import-step-unchecked` | info | a STEP body is copied without reading its geometry |
| `library.import-step-placement` | info | a STEP body without a placement in the footprint |
| `library.import-terms` | info | once per import: the source terms limit sharing |
| `library.import-family-unknown` | info | no family matched; no cross-check |
| `library.import-crosscheck-skipped` | info | `--no-crosscheck` |
| `library.import-package-mismatch` | error | `--package` names a package of another family |
| `library.import-pad-count`, `-numbering`, `-pin1` | error / warning | decision 7 |
| `library.import-pitch`, `-land`, `-sources-disagree` | warning | decision 7 |
| `library.not-shippable` | error | an imported record met by a library check (c0262, c0279) |
| `catalog.import-deprecated` | info | the alias was used |
| `FEN-2001` | exit 2 | `.IntLib`, ambiguous item, `--into` outside the project or inside a vendored library folder |
| `FEN-3004` | exit 3 | an unsafe archive, a malformed source, a STEP without its header |
| `FEN-7001` | exit 7 | re-import over an edited device |

No new `FEN-` code. Each `library.*` code joins `fenolite.library.codes` and `explain.toml`.

## Risks / Trade-offs

- **The classifier guesses.** A wrong family gives warnings, not errors, unless the user named the
  package. The finding text says which family was assumed.
- **Imported files sit in git.** The user's repository then holds derivatives of downloaded files. That
  is the user's own use; `library.import-terms` and `docs/library-import.md` say that publishing the
  repository may break the source terms.
- **Fixed limits may refuse a large legitimate archive** (a connector series with many STEP files).
  The message names the limit; a later change can add a flag if real archives need it.
- **Subcommand words on `library`.** A board folder named `import` needs `./import`. It is unlikely and
  documented.

## Open questions

1. *Read `.IntLib`?* Recommended: yes, in its own change, after its layout is recorded with public
   sources in `docs/formats/altium/` and its streams are shown to be the `.SchLib`/`.PcbLib` streams
   the existing readers read.
2. *Keep a copy of the original archive in the device folder?* Recommended: no. The SHA-256 and the
   name identify it, and a copy would put a third-party file in the user's repository twice.
3. *Should the default namespace be `Imported:` or the project name?* Recommended: `Imported:`, so an
   imported device is recognisable in a script and in the BOM.
4. *How long does the `catalog import` alias live?* Recommended: one minor release.

## Relation to the batch

- **c0248** gives the device record, the stamp, `edited` and the no-clobber rule; this change moves its
  `catalog import` code into one importer (decision 9).
- **c0259** gives the record files, the device tree and the stable ids; `origin`, `licence` and
  `shippable` are fields it defines for every record, filled here.
- **c0260** gives the generators and the land calculator that the cross-check draws with; the classifier
  lives here and recognises its families.
- **c0261** draws the symbol of an Altium import from its pins.
- **c0262** runs `crosscheck` on imported devices and refuses them in library mode; its review can raise an
  imported device's label like any other.
- **c0265** writes devices the same way (records, origin, generator, checks) from a datasheet proposal
  instead of a download.
- **c0266 / c0279**: `fenolite-library` refuses records that are not shippable.
- **c0267** may fill identity fields later; it never feeds an import.
