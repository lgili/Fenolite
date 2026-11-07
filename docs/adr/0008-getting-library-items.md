# ADR-0008: Getting library items

## Status
Accepted (2026-10-29, maintainer's decision recorded by change c0279)

## Context
Fenolite needs third-party material: boards to start from and to benchmark the generators against, and
symbols, footprints, devices and blocks beyond what can be authored by hand. ADR-0003 keeps the tool
repository Fenolite-authored, so that material cannot live in it. The maintainer decided on 2026-10-29
that one repository, `fenolite-library` (github.com/lgili/fenolite-library), holds all third-party-derived
material converted to Fenolite formats, each item with its upstream licence, a NOTICE and a
`PROVENANCE.json`, and that users pull items with one command.

ADR-0007 made `fenolite fetch` the only command that downloads, for external tools only. Pulling items is a
second kind of download: data and Python payloads, under many licences, some of them reciprocal.

The forces:

- A download nobody asked for is a request to a third party.
- An item copied into a project brings its licence with it; a share-alike or copyleft item brings
  obligations the user must see before the copy.
- Bytes from the network must be the bytes that were reviewed and released.
- A project must build offline, with exactly the items it pinned.
- Block and board payloads are Python; running them on download would run third-party code unasked.

## Decision
1. **A second downloading command.** `fenolite get` downloads library items. It downloads only data and
   payloads published as release assets of `lgili/fenolite-library` (`index.json`, the shard and board
   archives), nothing else, and no other command downloads items.
2. **Only with `--confirm`.** `--dry-run`, `--list`, `--search` and `--status` make no request. A request is
   made only under `--confirm`, one per missing asset, with only a `User-Agent: fenolite/<version>` header,
   a 60 s timeout, `https`-only redirects, at most the expected bytes plus one, and no retry.
3. **Only pinned digests.** The index is checked against the release table shipped with the core
   (`src/fenolite/cli/data/library.toml`), `--index-sha256`, or the `index` digest of a lock entry; each
   archive against its index row; each extracted item against its row's tree digest. A difference is
   `FEN-3006`, and nothing is written.
4. **Licences before the copy.** The plan lists each item's SPDX id, family, reciprocal flag and
   obligations. A licence other than `CC0-1.0` must be accepted by name with `--accept-licence`
   (`FEN-4003`); an id outside the shipped allow-list, or an item without `LICENSE` or `NOTICE`, is
   refused (`FEN-3021`).
5. **Never executed.** `get` never imports, runs or builds a payload; `executes` is shown in the plan.
6. **Nothing is sent.** No design data, no project name and no identifier leaves the machine.
7. **Pinned in the design lock.** Each vendored item is pinned in the lock's `[library]` section (version,
   release, index digest, tree digest, SPDX id, path), and a verified copy of each asset is kept in an
   offline cache (`FENOLITE_LIBRARY_DIR`, else the platform cache folder). `--offline` opens no connection.
   `--from DIR` reads a release (or a library checkout, or a `file://` git URL) from the local machine
   under the same digest checks.

## Alternatives
- **Extending `fenolite fetch`.** Rejected: `fetch` installs one pinned tool per table row; items come
  and go with each library release and carry licences and dependencies that `fetch` does not model.
- **A package index (Python entry points, a registry service).** Rejected: an index service needs
  accounts and uploads, and a Python package runs code on install.
- **Committing items into the tool repository.** Rejected by ADR-0003: the tool stays Fenolite-authored.
- **Copying items by hand.** Rejected: licence files, notices and pins get lost, and nothing checks the
  digests.

## Consequences
- A project gets an item in one reviewed act: plan, licences shown, confirm, digests checked, lock pinned,
  `fenolite_library/ATTRIBUTION.md` regenerated.
- A fresh clone restores its items with `fenolite get --locked <script>`, offline from the cache.
- A new library release reaches an older core through `--index-sha256` or a lock entry; the shipped
  release table grows with each core release.
- ADR-0007 gains a dated line pointing here; ADR-0003 gains a dated line naming `fenolite-library`.

## Evidence
`docs/library-repo.md`; S-1000 (release asset limits); hypothesis `H-G-LIBRARY-GET`; tests
`tests/unit/cli/test_get.py`, `tests/unit/cli/test_get_cache.py` and `tests/unit/cli/test_get_lock.py`
(no request without `--confirm`, digests checked before any write, licences accepted by name).
