## Context

- **Source.** `docs/research/component-library.md`, sections 1 (licences: ship only data authored from
  public facts or explicitly CC0), 4.9 ("Distribution") and 6 (questions 1 and 3). Maintainer decision of
  2026-10-29: the LibrePCB official libraries (CC0-1.0) may seed the data repository, openly, with origin
  recorded and `UNVERIFIED` until checked and reviewed.
- **What exists on `dev` (0.6.0).**
  - `fenolite fetch NAME` (`cli/cmd_fetch.py`, `cli/fetch.py`, `cli/data/fetch.toml`, ADR-0007): the only
    download, of one pinned tool, as a deferred write under `--confirm`, checked by size and SHA-256
    (`FEN-3006`, `FEN-6003`), into `fenolite.core.tools`' folder.
  - `tools/kicad_libs_fetch.py` and `backends/kicad/libcache.py`: pinned KiCad library trees in a cache,
    safe extraction with the `tarfile` data filter, a tree digest in the scheme `fenolite-tree-1`
    (`tree_hash`), stamps, `--verify`.
  - `fenolite library PATH --out|--diff` (c0223): a footprint library made from a board. Its first
    positional is a path.
  - `repo-layout`: `dependencies = []` and a closed list of extras.
- **What the batch adds before this change.** c0249: the design lock `<stem>.lock`, generic sections
  through `LockSection(name, resolve)`, `--frozen` with `FEN-7004`. c0259: record kinds, header, licences,
  `origin`, `reviewed_by`, `VERSIONS.toml`, `load_tree`, project-over-shipped precedence. c0262: `fenolite
  library check`, rule codes, rendered sheets, old/new visual diff, review records. c0260 and c0261:
  generators.

## Goals / Non-Goals

**Goals**

- Library data grows and is released apart from the code, under CC0, with checks and human review in its
  own CI.
- A design builds with exactly the pack version it was locked to, on any machine, offline.
- Getting a pack is an explicit, reviewed act (plan, confirm, digest), never a side effect of a build.
- The core keeps zero runtime dependencies and imports no code from a pack.
- LibrePCB's CC0 data can seed the pack, transparently and reproducibly.

**Non-Goals**

- See the proposal. In addition: no pack signing beyond SHA-256 pins (open question 4), no mirror, no
  partial download of a pack.

## Decisions

### 1. The data repository

`fenolite-devices`, a separate repository under the same owner as Fenolite (open question 1 for the
exact name), licensed **CC0-1.0**, contributions with DCO sign-off as in the main repository. It holds
data only: no Python, no scripts; its CI calls a pinned released `fenolite`.

```
fenolite-devices/
  pack.toml              # the manifest
  sources.toml           # the pack's source registry (D-0001, ...)
  VERSIONS.toml          # c0259's version file, for the pack's ids
  packages/<family>/<name>.toml
  pins/<maker>/<name>.toml
  devices/<maker>/<name>.toml
  parts/<maker>/<name>.toml
  families/<maker>/<series>.toml            # c0263
  seeded/librepcb/{packages,pins,devices}/  # decision 9; moved out once reviewed
  reviews/<id path>/<version>.toml, .svg    # c0262
  CHANGELOG.md, LICENSE (CC0 legal code), CONTRIBUTING.md, CODEOWNERS
  .github/workflows/{check.yml,release.yml}
```

```toml
# pack.toml
schema = "fenolite.pack.v0"
name = "fenolite-devices"
version = "1.4.0"
summary = "CC0 device data for Fenolite"
licence = "CC0-1.0"
namespaces = ["FenoliteDevices"]
requires = { fenolite = ">=0.8.0", schemas = ["fenolite.pins.v0", "fenolite.package.v0", "fenolite.device.v1", "fenolite.part.v0"] }
```

- Every record's `id` MUST be in a namespace of `namespaces`; `Fenolite` is reserved for the shipped
  catalog and refused. Every record's `licence` MUST be `CC0-1.0` (c0259 rule for pack records).
- `sources.toml` rows: `id` (`D-` and four digits), `title`, `url`, `licence` of the source document,
  `retrieved` (date), and what is used. Records' `sources` name these ids.
- **What may enter:** records authored from public facts (datasheets, JEDEC outlines, cited per record),
  contributions a manufacturer makes under CC0, and records converted from a CC0 library (decision 9).
  Never: CC-BY-SA or other CAD libraries, supplier API answers, IPC tables, manufacturer CAD files.

### 2. The repository's CI

`check.yml` on every pull request, with `fenolite==<pinned>` installed by `uv tool install`:

| job | what it runs | fails on |
|---|---|---|
| `records` | `fenolite library check . --all --json` (c0262) | any error finding; a record that does not parse; a licence other than CC0-1.0; a namespace not in `pack.toml`; an unregistered `D-` id |
| `regenerate` | c0260/c0261 generators over every package and pins record with a generator; compares with committed explicit outputs where a record keeps both | any difference |
| `versions` | c0259's version rules between the base branch and the head, with `VERSIONS.toml` | a digest change without the version step; an interface change under an id; a removed id reused |
| `origin` | every record under `seeded/` has `origin` and is `UNVERIFIED` or holds a current review | otherwise |
| `renders` | c0262 sheets for each changed record and an old/new visual diff; uploaded as an artefact and summarised in a pull-request comment | never (evidence for the reviewer) |
| `pack` | builds the release archive and wheel as `release.yml` would, twice, and compares bytes | any difference |

A pull request is merged after the jobs pass and a CODEOWNERS reviewer approved; the review of a record's
digest (c0262's `fenolite library review`) is committed in the same pull request when it raises a label.

### 3. Releases

- **Versions.** The pack's `version` is semantic: PATCH for metadata-only record changes; MINOR for new
  records, new parts, or record changes allowed by c0259 (no interface change); MAJOR when a deprecated
  record is removed or `requires.fenolite` rises. Records keep their own versions (c0259).
- `release.yml` on a tag `v<version>` equal to `pack.toml`'s version:
  - `fenolite-devices-<version>.tar.gz`: one top-level folder `fenolite-devices-<version>/`, members
    sorted by path, mtime 0, uid and gid 0, mode 0644/0755, no symlink, gzip with mtime 0 and no name, so
    it is byte-reproducible;
  - `SHA256SUMS`, `index.json` (each record's kind, id, uid, version, digest, evidence, licence), and the
    tree digest of the unpacked folder in the scheme `fenolite-tree-1`;
  - a **data-only wheel** `fenolite_devices-<version>-py3-none-any.whl` on PyPI: the same tree under
    `fenolite_devices_data/`, no Python module, no entry point that runs code, licence `CC0-1.0`.
- A release is never re-tagged; a fix is a new version.

### 4. Where the core finds packs

`fenolite.catalog.packs.find_packs(*, paths=()) -> tuple[Pack, ...]`, offline and read-only, in this order
(a later source of the same name and version is a duplicate and ignored):

1. **Paths** given by `--pack DIR` (repeatable, on `build` and `library packs`) or by
   `FENOLITE_PACKS_PATH` (an `os.pathsep` list): a checkout of the data repository, for pack authors.
2. **The extra**: `importlib.metadata.distribution("fenolite-devices")` when installed; the tree is
   located with `locate_file("fenolite_devices_data")`. No module of the distribution is imported.
3. **The cache**: `<packs dir>/<name>/<version>/`, where `<packs dir>` is `FENOLITE_PACKS_DIR` (absolute),
   else `$XDG_CACHE_HOME/fenolite/packs`, the macOS and Windows cache folders, or `~/.cache/fenolite/packs`
   (the rules of `fenolite.core.tools`). A cached folder counts only when its stamp
   `.fenolite-pack.toml` holds the tree digest it was unpacked with.

A `Pack` holds `name`, `version`, `source` (`path`, `extra`, `cache`), `root` and `tree` (its digest).
Reading a pack is `load_tree(root)` of c0259 plus the manifest checks; it is done lazily, on the first
lookup of an id that the project and the shipped catalog do not hold. `tree_hash` moves from
`backends/kicad/libcache.py` to `fenolite.core.treehash` (re-exported where it was), so `catalog` can use
it.

### 5. Precedence

For each id: **project records** (c0248/c0259 `devices/` folder and `design.devices`) **> packs > the
shipped catalog**. Packs never override `Fenolite:` ids (they cannot hold them). Two packs that both hold
an id give `library.pack-conflict` (error) naming both, unless a project record of that id exists. A
project record overriding a pack record gives `library.overrides-pack` (info). The build result labels
each definition's origin `authored`, `pack` or `builtin` (the MODIFIED "Build resolves built-in
definitions").

### 6. The lock pins the pack

c0249's lock gains the section `library`, registered through `LockSection`:

```toml
[library."fenolite-devices"]
version = "1.4.0"
tree = "fenolite-tree-1:9c1e…"
```

- **Only packs that are used are pinned.** The runner records which pack served each looked-up id; after
  the script ran, each pack that served at least one id has an entry. A design that uses no pack record
  gets no entry, so existing designs and locks are unchanged.
- **First use.** With no entry, the highest version available of that pack (by semantic version) is used,
  and the entry is planned with the build's lock write: `library.pack-locked` (info).
- **Locked.** With an entry, only a pack of that name, version and tree digest is used. None available
  gives `library.pack-missing` (error), exit 6 with `FEN-6004`, message naming the pack and version, hint
  `fenolite library fetch <version> --pin <script>` (or `pip install "fenolite[devices]==…"`). A source
  with that version and another tree digest is ignored with `library.pack-tree-differs` (warning).
- **Released.** An entry whose pack no longer serves any id is dropped: `library.pack-released` (info).
- **Frozen.** Every change of the section (locked, released, a version change) is a lock change that
  `--frozen` refuses with `FEN-7004` (c0249).
- **c0254 picks** of a pack row record `catalog = "pack:fenolite-devices 1.4.0"`, so a pick and the pack pin
  move together.
- **Updating** is explicit: `fenolite library fetch 1.5.0 --pin design.py` (decision 7) or editing the lock.

### 7. `fenolite library fetch`

```
fenolite library fetch --dry-run --json                   # newest row of packs.toml
fenolite library fetch 1.5.0 --pin design.py --dry-run    # fetch and re-pin in one plan
fenolite library fetch --locked design.py --confirm       # whatever the lock names
fenolite library fetch 1.5.0 --from ./fenolite-devices-1.5.0.tar.gz --confirm
```

- **Which bytes.** `src/fenolite/cli/data/packs.toml` lists known releases: `name`, `version`, `url`
  (an `https` release asset address), `bytes`, `sha256` (of the archive), `tree`, `source` (a registered
  `S-` id). With `--locked SCRIPT`, the lock's version and tree digest decide: a release not in the table
  may be fetched by the URL template of the table's `url_template`, and is accepted only if its unpacked
  tree has the locked digest. A version that is neither in the table nor locked needs `--sha256 HEX`.
- **The plan** lists the target folder `<packs dir>/<name>/<version>/` (kind `device-pack`) with the
  archive size and digest, and with `--pin` the lock file write (kind `lock`, c0249). All or nothing.
- **Confirm.** The archive is a deferred write: one request as in `fetch` (User-Agent only, 60 s timeout,
  `https` redirects only, at most `bytes + 1` bytes, no retry), or `--from FILE`. The archive digest is
  checked (`FEN-3006`), then it is extracted with the `data` filter into a temporary folder of the cache,
  one top-level folder is required, its tree digest is checked (`FEN-3006`), the stamp is written, and the
  folder is moved in place with `os.replace`. Any failure leaves the cache as it was.
- A target that already holds that version with the right stamp plans nothing (`installed: true`).
- Nothing about the design is sent. **ADR-0008** "Fetching device packs" records the decision: a second
  command downloads, only data, only pinned rows or locked digests, only with `--confirm`; ADR-0007 gains
  a dated line pointing to it.
- `result`: `name`, `version`, `path`, `bytes`, `sha256`, `tree`, `url`, `licence`, `origin` (`network`,
  `file`), `installed`, `pinned` (the script whose lock is rewritten, or null).

### 8. The `library` verbs

`fenolite library` keeps `PATH --out|--diff` (c0223). A first positional that is one of the reserved verbs
`fetch`, `packs`, `seed`, `check`, `review`, `import`, `propose` selects that verb (the last four belong to
c0262, c0264 and c0265). A board or folder actually named like a verb is written `./fetch`. `capabilities`
lists each verb as `library <verb>` with its own arguments, so agents see them as commands.

- **`library packs [--pack DIR] [--script FILE] [--verify]`** (read-only, offline): every pack found, with
  name, version, source, tree, record counts and `requires`; with `--script`, the lock's pin and whether it
  is satisfied; with `--verify`, every cached pack's tree is hashed again and a difference exits 5 with
  `library.pack-tree-differs`. `capabilities` and `doctor` show the same list in short.

### 9. LibrePCB seed

```
fenolite library seed --from-librepcb ../librepcb-base --commit 1a2b…40hex \
    --library "LibrePCB Base" --into seeded/librepcb --namespace FenoliteDevices --dry-run
```

- **Reading.** `fenolite.backends.librepcb` reads LibrePCB library elements (symbols, packages with their
  footprints and pads, components with signals and gates, devices with pad-to-signal maps and parts)
  from their published file format. The format is recorded in `docs/formats/librepcb/library.md` from
  public documentation only, each fact with its source and label; no LibrePCB parser code is read or
  transcribed. The reader has its own small S-expression tokenizer written from that page (a backend may
  not import another backend). It is a library-element reader only: no board or schematic.
- **Licence gate.** The checkout's licence file MUST be the CC0 1.0 legal code (its normalised text's
  SHA-256 is pinned in the reader) or the command exits 3 (`FEN-3004`, "not a CC0-1.0 library"). When a
  `.git` folder exists, its `HEAD` commit MUST equal `--commit`. The library is registered as a source.
- **Mapping.**
  - a package → one `fenolite.package.v0` per footprint (`generator = "explicit"`); the first footprint
    takes the package name, others `<name>_<footprint name>`;
  - a component with its symbols → one `fenolite.pins.v0` with an explicit `[symbol]` (one unit per gate);
    signal roles map to pin types by a table in the format page, and an unknown role gives `unspecified`;
  - a device → `fenolite.device.v1` joining that pins record and package record, functions named after
    the signals, pads from the device's map; its parts → `[[part]]` with `mpn` and `manufacturer`.
- **Every record** gets `origin = { library, version = <commit>, element = <element UUID>, licence =
  "CC0-1.0" }`, `licence = "CC0-1.0"`, `evidence = "UNVERIFIED"`, `version = "1.0.0"`, and `sources` naming
  the library's `D-` id.
- **Ids.** `<namespace>:<name>` with characters outside `[A-Za-z0-9_.+-]` replaced by `_`; a collision in
  the run or with an existing record of `--into` appends `_` and the first 8 hex digits of the element UUID
  (`library.seed-renamed`, info). Re-running on the same commit gives the same ids, files and bytes.
- **Skipped elements.** A feature the records cannot carry (a custom pad outline, a length that is not a
  whole number of nm, an unknown element version) skips that element with `library.seed-skipped`
  (warning, naming the UUID and the reason); its dependants are skipped too.
- **Writes** go through plan and confirm into `--into`, one file per record, all or nothing. A run onto
  existing seeded files replaces only records whose `origin.element` matches and whose `reviewed_by` is
  empty; a reviewed record is never overwritten (`FEN-7001`, as c0248's import).
- **Not at build time.** No build, check or fetch calls the converter. It is run by a maintainer or by a
  job of the data repository, and its output enters the pack through a pull request and the CI of
  decision 2. c0262's cross-check against the family generators (c0260) is the first filter.
- **Risk stated in the pack's README and in `docs/packs.md`:** LibrePCB contributors may have taken data
  from elsewhere; the CC0 licence covers the library, not the accuracy or the history of each element.
  Hence `UNVERIFIED`, the checks, and a human review before any label rises.

### 10. No runtime dependency in the core

- `pyproject.toml` gains the extra `devices = ["fenolite-devices==<version tested>"]`; `dependencies`
  stays `[]` and the invariant test's closed list gains `devices`. The extra's package is data-only and
  CC0, so it brings no code and no licence obligation.
- Without the extra and without a fetched pack, everything works as before; a design that names a pack id
  fails like any unknown device (`DslError` with closest ids), and the message adds the fetch hint when the
  id's namespace is one of `packs.toml`'s declared namespaces.

### 11. Codes

| code | severity / exit | when |
|---|---|---|
| `library.pack-missing` | error → exit 6 `FEN-6004` | the lock pins a pack that no source holds |
| `library.pack-locked` | info | a pack is pinned for the first time |
| `library.pack-released` | info | a pinned pack serves no id any more; its entry is dropped |
| `library.pack-tree-differs` | warning (error under `--verify`) | a source has the pinned version with another tree digest |
| `library.pack-conflict` | error | one id in two packs and no project override |
| `library.pack-incompatible` | error | `requires` names a newer Fenolite or an unknown schema |
| `library.overrides-pack` | info | a project record overrides a pack record |
| `library.seed-skipped` | warning | `library seed`: an element cannot be converted |
| `library.seed-renamed` | info | `library seed`: an id collision was resolved |
| `FEN-6004` | exit 6 | new: "a device pack pinned by the design lock is not available" (not retryable; hint names `library fetch`) |
| `FEN-3006` | exit 3 | existing: archive or tree digest mismatch |
| `FEN-6003` | exit 6 | existing: download failed (retryable) |
| `FEN-7004` | exit 7 | existing (c0249): the lock would change under `--frozen` |

## Risks / Trade-offs

- **Two repositories to keep in step.** `requires` in the manifest and the extra's exact pin make the
  pairing explicit; the CI job `packs` of the main repository fetches the pinned release on every run.
- **A second downloading command** widens ADR-0007. Mitigated by the same rules (confirm, pins, digest,
  nothing sent) and a separate ADR.
- **Seeded data quality.** Handled by `UNVERIFIED`, `seeded/` as a visible quarantine, c0262's checks and
  reviews. The seed is optional: the pack is useful without it.
- **Verb words in `library`.** A path literally named `fetch` changes meaning; documented, and the
  board-path form is rare for such names.
- **Tree digests and Windows.** `fenolite-tree-1` already ignores times, permissions and listing order;
  line ends are preserved by the archive and by the wheel, so the digest is equal on every platform.

## Open questions

1. *Repository name and owner.* Recommended: `fenolite-devices` next to the main repository, CC0-1.0, DCO.
2. *Namespace of pack records.* Recommended: one namespace `FenoliteDevices` for the official pack; other
   packs (a company's own) declare theirs.
3. *Should the extra pin an exact pack version?* Recommended: yes (`==`), updated with each core release,
   so `pip install fenolite[devices]` is reproducible; newer packs come by `library fetch --pin`.
4. *Signed releases (Sigstore) in addition to SHA-256 pins?* Recommended: later; pins in `packs.toml` and
   in the lock already make a tampered archive fail.
5. *Keep seeded records in `seeded/` after review?* Recommended: move them into the main tree in the
   review pull request (the id and uid do not change), so `seeded/` lists only what is still unreviewed.
6. *LibrePCB attribution.* CC0 needs none; recommended anyway: name the library and commit in the pack's
   README and `sources.toml`.

## Relation to the batch

- **c0249**: the `library` lock section and `--frozen`.
- **c0254**: picks of pack rows name the pack version; family rows in packs come with c0263.
- **c0259**: the record format, licences, `origin` and review rules this change relies on.
- **c0260 / c0261**: the generators the CI's `regenerate` job runs.
- **c0262**: `library check`, sheets, visual diff and `library review`, all used by the pack CI.
- **c0263**: passive families shipped in the pack.
- **c0264**: user imports stay in the project, never in the pack.
- **c0265**: datasheet proposals reach the pack only through a reviewed pull request.
- **c0267**: supplier answers never enter the pack.
