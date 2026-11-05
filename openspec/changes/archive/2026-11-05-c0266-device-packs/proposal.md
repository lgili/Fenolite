## Why

A large library (tens of thousands of packages, devices and parts, research section 4.10) cannot live in
the core package: it would grow every install, tie data fixes to code releases, and mix data under several
licences with Apache-2.0 code. Research section 4.9 of `docs/research/component-library.md` proposes a
separate, versioned data repository with its own CI, pinned by the design lock (c0249).

The maintainer decided on 2026-10-29 that this repository is **`fenolite-library`**
(github.com/lgili/fenolite-library, c0279), the single home of all third-party-derived material, not a
separate `fenolite-devices` repository. Device data becomes its kinds `symbols`, `footprints` and
`devices`, pulled by `fenolite get` (c0279). He also decided that the LibrePCB official libraries
(CC0-1.0) may seed it openly, with each element's origin recorded, which needs a deterministic converter
whose output stays `UNVERIFIED` until checked (c0262) and reviewed.

## What Changes

- **Three device kinds of `fenolite-library`** (layout, provenance, licences, releases: c0279):
  `symbol` (a c0259 `pins` record with its `[symbol]`), `footprint` (a `package` record) and `device` (a
  `device` record with parts, whose `depends` names its symbol and footprint items).
- **Fenolite-authored items** use the namespace `FenoliteDevices`, `CC0-1.0`, the family `cc0` and the
  library's `sources.toml` (`D-` ids). Converted third-party items keep their upstream licence and
  provenance. `Fenolite` stays reserved for the shipped catalog.
- **The library's CI for these kinds:** `fenolite library check` (c0262); regeneration of generated
  footprints, symbols and bodies (c0260, c0261) compared with the committed outputs; c0259's version rules;
  the origin rule for seeded records; previews with an old/new visual diff.
- **Vendored records.** `fenolite get` copies items into `fenolite_library/symbols`, `fenolite_library/footprints` and
  `fenolite_library/devices` beside the script. The runner reads them as TOML project records, importing nothing.
  Precedence per id: authored project records (`devices/`) > vendored records > shipped catalog. The build
  labels their origin `library` with item and version.
- **Pinned in the lock** by c0279's `[library.items]` (version, release, tree digest). A c0254 pick of a
  vendored row names that item and version.
- **Offline.** Builds read only project files and the shipped catalog. A missing vendored folder exits 6
  with c0279's `FEN-6004`. An unknown id in a namespace of the cached library index gets the hint
  `fenolite get device <id> --dry-run`.
- **LibrePCB seed.** `fenolite library seed --from-librepcb DIR --commit SHA --into DIR` converts LibrePCB
  packages, components with symbols, and devices into `cc0` library items, each with `PROVENANCE.json`
  (`origin: seeded`, library, commit) and records keeping their element UUID, `CC0-1.0` and `UNVERIFIED`.
  Deterministic, under plan and confirm, run by a maintainer or the library's CI, never by a build.
- **Removed from the first version:** the `fenolite-devices` repository, `pack.toml`, `library fetch`,
  `library packs`, the `fenolite[devices]` extra and wheel, the pack cache, its ADR and its own `FEN-6004`.
  c0279 provides repository, `get`, cache, ADR-0008 and `FEN-6004`.

## Non-goals

- No record content is authored here; the first items are decided in the library.
- No supplier data in the library, ever (c0267).
- No automatic update: a newer item comes only through `fenolite get --version`.
- No 3D models from LibrePCB in the first seed (c0260's concern).
- No seed from another CAD library here; converted third-party items enter one by one under c0279's rules.

## Evidence level required

- Vendored records, precedence and origin labels: `INFERRED`, unit-tested with records vendored from a
  local release, no network (`H-G-DEVICE-PACKS`).
- Seeded records: `UNVERIFIED` by rule (c0259); the converter `INFERRED` against authored fixtures written
  for Fenolite in LibrePCB's public format.

## Impact

- New: `catalog/vendored.py`, `catalog/seed/librepcb.py`, `backends/librepcb/`, the `library seed` verb,
  `docs/library-devices.md`, `docs/formats/librepcb/library.md`, `examples/library-devices/`, tests.
  Outside: the device jobs of `lgili/fenolite-library`'s CI and its first device items.
- Changed: `cli/_script.py`, `cli/cmd_build.py` (origin `library`), `docs/cli-contract.md`, the guide page
  `parts.md`, `CHANGELOG.md`.
- Depends on: c0279 phase A, c0259, c0262. c0260 and c0261 make regeneration meaningful. c0254 picks may
  name vendored rows.
- Size: about 6 design-days (M).
