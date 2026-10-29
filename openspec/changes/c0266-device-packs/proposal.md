## Why

A large library (tens of thousands of packages, devices and parts, research section 4.10) cannot live in
the core package: it would grow every install, tie data fixes to code releases, and mix data licensed for
reuse with Apache-2.0 code. Research section 4.9 of `docs/research/component-library.md` proposes a
separate, versioned **CC0 data repository**, `fenolite-devices`, holding only records in c0259's format,
checked by its own CI, published as releases, and pinned by the design lock (c0249) so that a build is
byte-identical on every machine.

The maintainer decided on 2026-10-29 that the LibrePCB official libraries, licensed CC0-1.0, may seed the
repository, openly and with each element's origin recorded. That needs a deterministic converter whose
output is labelled `UNVERIFIED` until it is checked (c0262) and reviewed.

## What Changes

- **The data repository `fenolite-devices`** (separate, CC0-1.0, DCO sign-off, no code): `pack.toml`
  (schema `fenolite.pack.v0`: name, version, namespaces, the Fenolite version it needs, licence),
  `sources.toml` (its own source registry), the record tree of c0259 (`packages/`, `pins/`, `devices/`,
  `parts/`, `families/`), `reviews/`, `VERSIONS.toml`, `CHANGELOG.md`.
- **Its CI**, on every pull request: regenerate every generated footprint, symbol and body (c0260,
  c0261) and compare with the committed outputs; run `fenolite library check` (c0262); check licences,
  sources, origins and the version rules of c0259 against the previous release; render previews and an
  old/new visual diff of every changed record (c0262), attached to the pull request.
- **Versioned releases.** A tag `vX.Y.Z` publishes a deterministic archive, its `SHA256SUMS`, an
  `index.json`, and a data-only wheel `fenolite-devices` on PyPI.
- **How the core gets a pack, never at build time.**
  - `fenolite library fetch [VERSION] [--from FILE] [--pin SCRIPT]` downloads a release archive under the
    mutation protocol, checks it against a pinned digest, and unpacks it into the user's pack cache.
  - The extra `fenolite[devices]` installs the wheel; the core finds it through `importlib.metadata`
    without importing any code. `pyproject.toml` `dependencies` stays empty.
  - `fenolite library packs` lists what is installed, cached and locked (read-only, offline).
- **The lock pins the pack.** A build that uses a pack record records `[library."<pack>"]` (version and
  tree digest) in c0249's design lock; later builds use exactly that version, `--frozen` refuses a change,
  and a missing pinned pack exits 6 with the new `FEN-6004` and the fetch command as hint.
- **Precedence per id:** project records > packs > shipped catalog. A pack may not use the `Fenolite:`
  namespace; one id in two packs is an error.
- **Offline.** Builds never open a connection; the cache is verified by tree digest; `--from FILE`
  installs from a copied archive.
- **LibrePCB seed.** `fenolite library seed --from-librepcb DIR --commit SHA --into DIR` converts
  LibrePCB packages, symbols, components and devices into c0259 records with `origin` (library, commit,
  element UUID), `licence = "CC0-1.0"` and `UNVERIFIED`, deterministically, under plan and confirm. It is run
  by a maintainer or by the data repository's CI, never by a build.
- **ADR-0008** records that a second command (`library fetch`) downloads, and only data.

## Non-goals

- No record in the pack is authored here; the first release content is decided in the data repository.
- No supplier data in the pack, ever (c0267 is per user and never persistent).
- No automatic update: a newer pack is used only after `library fetch --pin` or a lock edit.
- No 3D models from LibrePCB in the first seed (STEP files are c0260's concern).
- No other seed source: CC-BY-SA libraries (KiCad, Horizon EDA) and other CAD libraries stay out.

## Evidence level required

- Pack reading, precedence, lock section, fetch plan and cache: `INFERRED`, unit-tested
  (`H-G-DEVICE-PACKS`), with a local archive and no network.
- The fetch of a real release: `UNVERIFIED` as for `fetch`; the CI job `packs` installs the pinned release
  with the command and builds the pack example (`H-G-PACK-FETCH`).
- Seeded records: `UNVERIFIED` by rule (c0259); the converter itself `INFERRED` against authored fixtures
  written for Fenolite in LibrePCB's public format.

## Impact

- New: `src/fenolite/catalog/packs.py`, `src/fenolite/catalog/seed/librepcb.py`, `cli/cmd_library.py` verbs
  `fetch`, `packs`, `seed`, `src/fenolite/cli/data/packs.toml`, `docs/packs.md`,
  `docs/formats/librepcb/library.md`, `docs/adr/0008-fetching-device-packs.md`, `examples/packs/`, tests.
  Outside this repository: the `fenolite-devices` repository with its CI workflows.
- Changed: `cli/cmd_library.py` (verbs before the board path), `cli/_script.py` (pack lookup),
  `cli/cmd_build.py` (lock section, `result.library`), `cli/errors.py` and `explain.toml` (`FEN-6004`),
  `cli/cmd_capabilities.py` and `doctor` (packs), `pyproject.toml` (extra `devices`),
  `tests/unit/test_pyproject_invariants.py`, `docs/cli-contract.md`, the guide page `parts.md`,
  `CHANGELOG.md`.
- Depends on: c0249 (lock sections), c0259 (records), c0262 (`library check`, reviews, visual diff, used by
  the data repository's CI). c0260 and c0261 make "regenerate" meaningful; before them the CI checks
  explicit records only. c0254 picks may name pack rows.
- Size: about 8 design-days (M), plus the data repository set-up.
