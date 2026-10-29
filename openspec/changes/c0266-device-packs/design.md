## Context

- **Source.** `docs/research/component-library.md`, sections 1 (licences), 4.9 ("Distribution") and 6
  (questions 1 and 3). Maintainer decisions of 2026-10-29:
  - the LibrePCB official libraries (CC0-1.0) may seed the data repository, openly, with origin recorded
    and `UNVERIFIED` until checked and reviewed;
  - the data repository is `fenolite-library` (github.com/lgili/fenolite-library), the single repository
    for all third-party-derived material (c0279), not a separate `fenolite-devices`; items keep their
    upstream licence and provenance, and users pull them with `fenolite get`.
- **History.** The first version of this change proposed a CC0 repository `fenolite-devices` with
  `pack.toml`, `fenolite library fetch`, `library packs`, a pack cache, a data-only wheel behind the extra
  `fenolite[devices]`, a lock section per pack and `FEN-6004` for a missing pack. c0279 now owns the
  repository, the download (`get`), the cache, the lock section, ADR-0008 and `FEN-6004`. What this change
  keeps: the device kinds and their CI, project-side resolution, the version in the lock (through c0279),
  discovery that imports nothing, and the LibrePCB seed, which now lands in `fenolite-library`.
- **What exists on `dev` (0.6.0).** `fenolite library PATH --out|--diff` (c0223), whose first positional is a
  path. The shipped catalog and c0248's project `devices/` folder.
- **What the batches add before this change.** c0249: the lock and `LockSection`. c0259: record kinds,
  header, licences, `origin`, `reviewed_by`, `VERSIONS.toml`, `load_tree`, project-over-shipped
  precedence. c0262: `fenolite library check`, rule codes, sheets, old/new visual diff, review records.
  c0260 and c0261: generators. c0279 phase A: the repository, `item.json`, `PROVENANCE.json`, licence
  lists, releases, `fenolite get`, `[library.items]`, `FEN-6004`.

## Goals / Non-Goals

**Goals**

- Device data grows and is released apart from the code, in `fenolite-library`, with checks and human
  review in its CI.
- A design builds with exactly the item versions it vendored and pinned, on any machine, offline.
- Reading device data never imports code.
- LibrePCB's CC0 data can seed the library, transparently and reproducibly.

**Non-Goals**

- See the proposal. Also: no build-time lookup in a cache or an installed distribution; vendored files are
  the only source beside the shipped catalog.

## Decisions

### 1. The device kinds

| kind (folder) | payload | id | depends |
|---|---|---|---|
| `symbol` (`symbols/`) | one `fenolite.pins.v0` record with `[symbol]` (c0259, c0261) | the record id | none |
| `footprint` (`footprints/`) | one `fenolite.package.v0` record, its generated outputs when it keeps both (c0260) | the record id | none |
| `device` (`devices/`) | one `fenolite.device.v1` record with `[[part]]` rows | the record id | its `symbol` and `footprint` items, exact versions |

```
fenolite-library/
  devices/cc0/FenoliteDevices/EXB6202/{item.json,PROVENANCE.json,LICENSE,NOTICE,EXB6202.toml}
  symbols/cc0/FenoliteDevices/EXB6202/{...,EXB6202.toml}
  footprints/cc0/FenoliteDevices/SOT-23-6/{...,SOT-23-6.toml}
  devices/cc0/FenoliteDevices/families/<series>/...      # c0263 family items, kind device
  reviews/<kind>/<id path>/<version>.toml, .svg           # c0262 review records
```

- **Authored items** (`origin: authored`) use the namespace `FenoliteDevices`, `spdx = "CC0-1.0"`, and
  `sources` naming `D-` ids of the library's `sources.toml`. Each `sources.toml` row has `id` (`D-` and four
  digits), `title`, `url`, `licence` of the source document, `retrieved` and `used`.
- **Converted items** (`origin: converted`), for example a footprint from a CC BY-SA library, keep that
  licence and family (c0279 decision 4), with `PROVENANCE.json` and the replay of c0279 decision 5. Their
  records' `licence` equals the item's SPDX id.
- **Seeded items** (`origin: seeded`): decision 6.
- A record's `licence` MUST equal its item's `spdx`, and its id MUST equal the item id. A record in the
  namespace `Fenolite` is refused (`library.provenance-invalid`). User imports (c0264) never enter:
  `library audit` calls `shippable()` and refuses them with `library.not-shippable`.
- **What may enter** as authored data: records from public facts (datasheets, JEDEC outlines, cited per
  record) and contributions a manufacturer makes under CC0. Never supplier API answers or IPC tables.

### 2. The library's CI for these kinds

These jobs are added to c0279's `check.yml` and run only on changed items of these kinds:

| job | what it runs | fails on |
|---|---|---|
| `records` | `fenolite library check <items> --json` (c0262) | any error finding; a record that does not parse |
| `regenerate` | c0260/c0261 generators over every package and pins record with a generator; compared with committed explicit outputs where a record keeps both | any difference |
| `versions` | c0259's version rules between the base branch and the head | a digest change without the version step; an interface change under an id; a removed id reused |
| `origin` | every seeded record is `UNVERIFIED` or holds a current review | otherwise |
| `renders` | c0262 sheets and an old/new visual diff per changed record, uploaded and summarised in a pull-request comment | never (evidence for the reviewer) |

A pull request merges after the jobs pass and a CODEOWNERS reviewer approves. The review of a record's
digest (c0262's `fenolite library review`) is committed in the same pull request when it raises a label.

### 3. Vendored records in a project

- `fenolite get` (c0279) copies items to `<script folder>/fenolite_library/symbols/<id path>/`,
  `fenolite_library/footprints/...` and `fenolite_library/devices/...`.
- **Reading.** `fenolite.catalog.vendored.load_vendored(script_dir) -> VendoredTree` reads those three
  folders with c0259's `load_tree`, which ignores `item.json` and `PROVENANCE.json` (not TOML). It pairs
  each record with its item (kind, id, version, SPDX from `item.json`). No module is imported, and nothing
  outside the project is read.
- **Precedence** for each id: authored project records (c0248/c0259 `devices/` and `design.devices`) >
  vendored records > the shipped catalog. A vendored record never overrides a `Fenolite:` id (it cannot
  hold one).
  - An authored record overriding a vendored one gives `library.overrides-item` (info).
  - Two vendored items holding one record id give `library.item-conflict` (error) naming both folders.
    The library's audit prevents this inside one release; it can happen across hand copies.
- **Origin.** The build result labels each definition `authored`, `library` (with kind, id and version) or
  `builtin` (the MODIFIED "Build resolves built-in definitions").
- **Unused items change nothing.** Only definitions that the design uses reach the outputs, so a vendored
  item that the design does not use leaves every output byte unchanged.
- **Hint.** A design that names an unknown device id gets c0248's `DslError` with the closest ids. When
  the id's namespace appears in the newest cached library index (c0279 decision 11), the message adds
  `fenolite get device <id> --dry-run`.

### 4. The version in the lock

- c0279's `[library.items."device/<id>"]` (and `symbol/`, `footprint/`) pin version, release, index
  digest and tree digest, written only by `get`.
- A missing vendored folder stops the build with c0279's `library.item-missing` and `FEN-6004`.
- **c0254 picks** of a vendored row record `catalog = "library:device/<id>@<version>"`, so a pick and
  the item pin move together. `fenolite get --version` of a picked item makes c0254's pick re-check report
  the change.

### 5. Builds stay offline

No build, check, `capabilities` or `doctor` run opens a connection or reads device data from anywhere but
the project, the shipped catalog and, for the hint only, the cached index.

### 6. LibrePCB seed

```
fenolite library seed --from-librepcb ../librepcb-base --commit 1a2b…40hex \
    --library "LibrePCB Base" --into ../fenolite-library --namespace FenoliteDevices --dry-run
```

- **Reading.** `fenolite.backends.librepcb` reads LibrePCB library elements (symbols, packages with their
  footprints and pads, components with signals and gates, devices with pad-to-signal maps and parts) from
  their published file format. The format is recorded in `docs/formats/librepcb/library.md` from public
  documentation only, each fact with its source and label; no LibrePCB parser code is read or
  transcribed. The reader has its own small S-expression tokenizer written from that page (a backend may
  not import another backend). It reads library elements only, no board or schematic.
- **Licence gate.** The checkout's licence file MUST be the CC0 1.0 legal code (its normalised text's
  SHA-256 is pinned in the reader), else exit 3 with `FEN-3004` ("not a CC0-1.0 library"). When a `.git`
  folder exists, its `HEAD` commit MUST equal `--commit`. The library is registered as a source.
- **Mapping.**
  - a package → one `footprint` item per footprint (`generator = "explicit"`); the first footprint takes the
    package name, others `<name>_<footprint name>`;
  - a component with its symbols → one `symbol` item (one unit per gate); signal roles map to pin types by
    a table in the format page, and an unknown role gives `unspecified`;
  - a device → one `device` item joining those, functions named after the signals, pads from the device's
    map, parts as `[[part]]` with `mpn` and `manufacturer`, `depends` on its symbol and footprint items.
- **Item files.** Each item goes to `--into/<kind folder>/cc0/<namespace>/<name>/` with `item.json`
  (version `1.0.0`), the CC0 legal code as `LICENSE`, a `NOTICE` ("<date>: converted from <library> at
  <commit> by Fenolite <version>; format change only"), and `PROVENANCE.json` with `origin: seeded`,
  `upstream` (URL, commit, `spdx_expression = "CC0-1.0"`), `conversion` (the seed command and versions)
  and `evidence = "UNVERIFIED"`.
- **Every record** gets `origin = { library, version = <commit>, element = <element UUID>, licence =
  "CC0-1.0" }`, `licence = "CC0-1.0"`, `evidence = "UNVERIFIED"`, `version = "1.0.0"`, and `sources`
  naming the library's `D-` id.
- **Ids.** `<namespace>:<name>` with characters outside `[A-Za-z0-9_.+-]` replaced by `_`. A collision in
  the run or with an existing item of `--into` appends `_` and the first 8 hex digits of the element UUID
  (`library.seed-renamed`, info). Re-running on the same commit gives the same ids, files and bytes.
- **Skipped elements.** A feature the records cannot carry (a custom pad outline, a length that is not a
  whole number of nm, an unknown element version) skips that element with `library.seed-skipped`
  (warning, naming the UUID and the reason). Its dependants are skipped too.
- **Writes** go through plan and confirm into `--into`, all or nothing. A run onto existing seeded items
  replaces only records whose `origin.element` matches and whose `reviewed_by` is empty. A reviewed record
  is never overwritten (`FEN-7001`, as c0248's import).
- **Not at build time.** No build, check or `get` calls the converter. Its output enters the library through
  a pull request and the CI of decision 2 and of c0279. c0262's cross-check against the family generators
  (c0260) is the first filter.
- **Risk stated in the library README and in `docs/library-devices.md`:** LibrePCB contributors may have
  taken data from elsewhere. The CC0 licence covers the library, not the accuracy or history of each
  element. Hence `UNVERIFIED`, the checks, and a human review before any label rises.

### 7. The `library seed` verb

`fenolite library` keeps `PATH --out|--diff` (c0223). `seed` is one of the reserved verbs, beside c0260's
`generate`, c0261's `symbol`, c0262's `check` and `review`, c0264's `import`, c0265's `propose` and c0279's
`audit`, `replay`, `release` and `gallery`. A board or folder named like a verb is written `./seed`.
`capabilities` lists it as `library seed`.

### 8. Codes

| code | severity / exit | when |
|---|---|---|
| `library.overrides-item` | info | an authored project record overrides a vendored record |
| `library.item-conflict` | error | one record id in two vendored items |
| `library.seed-skipped` | warning | `library seed`: an element cannot be converted |
| `library.seed-renamed` | info | `library seed`: an id collision was resolved |
| `library.item-missing` / `FEN-6004` | error, exit 6 | c0279: a pinned vendored folder is missing |
| `FEN-3004` | exit 3 | existing: not a CC0 library, commit mismatch |
| `FEN-7001` | exit 7 | existing: a reviewed seeded record would be overwritten |

## Risks / Trade-offs

- **Many small folders in a project.** A design using fifty devices vendors about a hundred folders.
  Accepted: they are plain, reviewable files, the closure is shared, and `ATTRIBUTION.md` lists them.
- **No build-time cache lookup.** A design cannot name a library id without `get` first. This is
  deliberate: every third-party item in a project is visible, licensed and pinned.
- **Seeded data quality.** Handled by `UNVERIFIED`, c0262's checks and reviews. The seed is optional; the
  library is useful without it.
- **Verb words in `library`.** A path literally named `seed` changes meaning; documented.

## Open questions

1. *Namespace of authored items.* Recommended: one namespace, `FenoliteDevices`; converted items keep a
   namespace naming their source library.
2. *Keep seeded items marked after review?* Recommended: the `origin` stays `seeded`. Only the record's
   evidence label rises after review, and the item gets a new version.
3. *LibrePCB attribution.* CC0 needs none. Recommended anyway: name the library and commit in the item's
   `NOTICE`, in `PROVENANCE.json` and in `sources.toml`.
4. *Vendor whole families?* Recommended: a c0263 family is one `device` item whose payload is the family
   file; `get` copies it like any device.

## Relation to the batch

- **c0279**: the repository, `item.json`, `PROVENANCE.json`, licence lists, releases, `get`, the cache,
  `[library.items]`, `FEN-6004`, ADR-0008. This change adds the device kinds and the project-side reading.
- **c0249**: the lock that c0279's section lives in.
- **c0254**: picks of vendored rows name the item and version.
- **c0259**: the record format, licences, `origin`, review rules and `load_tree`.
- **c0260 / c0261**: the generators the `regenerate` job runs.
- **c0262**: `library check`, sheets, visual diff and `library review`, all used by the library's CI.
- **c0263**: family items shipped in the library.
- **c0264**: user imports stay in the project, never in the library.
- **c0265**: datasheet proposals reach the library only through a reviewed pull request.
- **c0267**: supplier answers never enter the library.
- **c0273**: the same project-side pattern for blocks.
