# The library repository `fenolite-library`

Third-party material lives only in [`fenolite-library`](https://github.com/lgili/fenolite-library): symbols,
footprints, devices, circuit blocks and boards derived from third-party sources, converted to Fenolite's
formats, each item with its upstream licence, NOTICE and `PROVENANCE.json` (change c0279, ADR-0008). This
repository holds none of it: its tests use the authored demo library `tests/data/library_repo/demo/`.

This page covers the repository's layout and records, the licence lists, its CI and releases, the gallery,
and `fenolite get`, which copies items into a project. The command contract is in
[`cli-contract.md`](cli-contract.md#get) ("get" and "Library repository verbs").

## Layout

```
fenolite-library/
  README.md  LICENSE (CC0-1.0, the repository's own files)  library.toml  licences.toml  sources.toml
  symbols/<family>/<Namespace>/<name>/
  footprints/<family>/<Namespace>/<name>/
  devices/<family>/<Namespace>/<name>/
  blocks/<family>/<Namespace>/<name>/
  boards/<family>/<source>/<name>/
```

- **Kinds.** The command line writes a kind singular (`symbol`, `footprint`, `device`, `block`, `board`);
  its folder is the plural.
- **Ids.** Symbols, footprints, devices and blocks have record ids `<Namespace>:<name>`; boards have
  `<source>/<name>` in lower case. The folder path of an id replaces `:` with `/`. An id is unique within its
  kind across all families.
- **Families.** The folder `<family>` follows from the item's SPDX id (the table below). An item in another
  family folder fails the audit.
- **README.** It states that each directory keeps its upstream licence, that the repository's own licence
  does not cover the items, that items are test and benchmark inputs and starting points for users, and
  that no item is used to train a machine-learning model unless a separate public decision says so.
  `library audit` checks these statements.

## The item folder

Each item folder holds `item.json`, its payload, `LICENSE` (the upstream text), `NOTICE` and
`PROVENANCE.json`, and may hold `README.md`. Any other file must be listed in `item.json` `files`.

`item.json` (schema `fenolite.library-item.v0`, JSON so that record loaders never read it):

| key | value |
|---|---|
| `kind`, `id`, `version` | the item, its semantic version |
| `title`, `summary`, `tags` | descriptive text |
| `spdx` | one allow-listed SPDX id |
| `files` | the payload, relative, sorted |
| `depends` | exact `{kind, id, version}` of other items; `get` pulls the closure; a cycle fails the audit |
| `executes` | `true` for blocks and boards, whose payload is Python; `get` shows it and never runs it |

## Provenance

`PROVENANCE.json` (schema `fenolite.provenance.v0`, canonical JSON: keys sorted, two-space indentation,
final newline) records:

- `origin`: `converted` (from an upstream: `upstream`, `conversion`, `import` and, for a board, `fidelity`
  are required), `authored` (written for the library: `upstream` null, `sources` names `D-` ids of
  `sources.toml`) or `seeded` (from a CC0 library: `upstream` with its URL and commit);
- `upstream`: URL, path, a full 40-hex commit (or `archive_sha256`), retrieval date, SPDX expression and
  source location; `vendor_bundled: true` marks an example bundled with commercial CAD software, which is
  refused;
- `authors`, `copyright` (verbatim), `spdx` (equal to `import.licence`), `licence_text_sha256` (the
  normalised digest of `LICENSE`) and, for a variant text, `licence_review` (`by`, `date`, `note`);
- `modification_notice`: dated, `YYYY-MM-DD: <what changed>`; `NOTICE` starts with the same text, followed
  by the upstream notices verbatim;
- `conversion`: `tools` (`fenolite`, `kicad-cli`, with versions), `steps` (replayable, paths relative to a
  work folder holding `upstream/` and `out/`) and `outputs_tree` (`fenolite-tree-1` of `out/` without its
  `PROVENANCE.json`, equal to the payload). A step never holds `--plan`: a plan id hashes its working
  folder, so a writing step is recorded with `--confirm` alone (change c0281);
- `import`: the record `fenolite import --to python` writes (`fenolite.import-provenance.v0`), verbatim;
- `fidelity`: c0278's member, with `accepted` differences and `proof` (a status per level, and
  `proof.skipped` with the reason of each skipped level);
- `trademarks` (`marks`, `restricted`, `note`), `featured` (null, or the authors' public permission for
  marketing use) and `evidence`.

## Licences

`licences.toml` (schema `fenolite.library-licences.v0`) is committed in the library; the core ships the same
file as `src/fenolite/cli/data/library-licences.toml`. The allow-list is closed (SPDX License List 3.29.0,
S-0982):

| family | SPDX ids | reciprocal | a copy carries |
|---|---|---|---|
| `cc0` | `CC0-1.0` | no | nothing required |
| `cc-by` | `CC-BY-3.0`, `CC-BY-4.0` | no | attribution, changes indicated |
| `cc-by-sa` | `CC-BY-SA-2.5`, `CC-BY-SA-3.0`, `CC-BY-SA-4.0` | yes | attribution, changes indicated, same licence |
| `cern-ohl-p` | `CERN-OHL-P-2.0` | no | notices, dated modification notice |
| `cern-ohl-w` | `CERN-OHL-W-2.0` | yes | notices, modification notice, same licence, Source Location |
| `cern-ohl-s` | `CERN-OHL-S-2.0` | yes | notices, modification notice, same licence, Source Location |
| `cern-ohl-1.2` | `CERN-OHL-1.2` | yes | notices, modification notice, same licence |
| `mit` | `MIT` | no | copyright and licence text |
| `bsd` | `BSD-2-Clause`, `BSD-3-Clause` | no | copyright and licence text |
| `apache` | `Apache-2.0` | no | licence, NOTICE, stated changes |
| `solderpad` | `SHL-0.5`, `SHL-0.51`, `SHL-2.0`, `SHL-2.1` | no | licence, NOTICE, stated changes |
| `gpl` | `GPL-2.0-or-later`, `GPL-3.0-only`, `GPL-3.0-or-later` | yes | source, notices, changes marked |
| `tapr` | `TAPR-OHL-1.0` | yes | notices, changes marked, same licence |

`SHL-2.0` and `SHL-2.1` are SPDX licence exceptions; `Apache-2.0 WITH SHL-2.x` maps to the same family.
Any other id is refused, with the reason `non-commercial` (`-NC`), `no-derivatives` (`-ND`), `no-licence`
(`NOASSERTION`, `NONE`, empty), `licence-ref` (`LicenseRef-*`) or `not-allowed`; an upstream on
`easyeda.com`, `oshwlab.com`, `oshwhub.com` or `lceda.cn` is `platform-restricted`.

The audit normalises `LICENSE` (lower case, whitespace runs collapsed to one space) and compares its SHA-256
with the digests listed for its id; a variant text needs `licence_review`. The shipped list holds the digest
of the `CC-BY-SA-4.0` text the KiCad demos carry; the library adds digests as it reviews texts.

## The library's CI

The library holds no tooling code: its workflows install a pinned released `fenolite` and call:

| job | command | fails on |
|---|---|---|
| audit | `fenolite library audit . --base <base ref> --json` | any `library.*` error |
| replay | `fenolite library replay <item> --json` per changed converted item | `library.replay-differs` |
| proof | `fenolite verify-source <item>/design.py --against <upstream> --provenance <item>/PROVENANCE.json --json`, then `fenolite library audit . --item <item> --proof <reply>` | `library.proof-failed` |
| release | `fenolite library release . --version <v> --out dist --confirm` | an audit error |
| gallery | `fenolite library gallery . --release dist --out site --confirm`, `fenolite render` per board | never |

- **Replay** fetches the upstream at the recorded commit (or uses `--upstream DIR`) in a temporary folder,
  checks the input digests of `import.inputs`, runs the steps with the recorded tool versions (`fenolite` in
  process when it is the running version or with `--with-current`, else `uvx --from fenolite==<version>`),
  and compares the tree of `out/` with `outputs_tree` and the payload. It writes nothing into the library.
- **Proof gate.** Every level must be `equal` or `accepted` (with `fidelity.accepted` as exclusions) and
  equal to `fidelity.proof.levels`. A level may be `skipped` only with its reason in `fidelity.proof.skipped`,
  never `build-failed`. The result is `pass`, `pass-with-accepted` or `fail`; a `fail` never merges, and the
  audit refuses a board whose recorded proof fails.
- **Benchmark** (weekly, and on each Fenolite release): every board replayed and proved with the newest
  Fenolite; the table (board, levels, time, differences, result) marks the newly failing boards for an
  issue and never blocks a merge.

## Releases

`fenolite library release` writes `index.json` (`fenolite.library-index.v0`: `name`, `version`, `commit`,
`requires`, one row per item with `kind`, `id`, `version`, `title`, `summary`, `spdx`, `family`,
`reciprocal`, `tags`, `authors`, `upstream`, `notice`, `path`, `tree`, `bytes`, `files` (path, size and
SHA-256 of each file), `archive`, `depends`, `executes`, `evidence`, `proof`, `gallery`, and an `archives`
list), one shard archive per kind and family (`devices-cc0.tar.gz`), one archive per board
(`board-<source>-<name>-<version>.tar.gz`) and `SHA256SUMS`. Archives are byte-reproducible: one top-level
folder, members sorted, mtime 0, uid and gid 0, mode 0644, no link, gzip with mtime 0 and no name. A release
holds at most 1000 assets, each under 2 GiB (S-0980). A release is never re-tagged; a removed item stays in
the older releases a lock may pin.

## Gallery

Each card shows Fenolite renders only, the title and the line "Converted from the open-source design
<title> by <authors> (<upstream link>), licence <SPDX>. Rendered by Fenolite <version>. Not endorsed by the
authors." (authored items: "Authored for fenolite-library"), the proof result, the `fenolite get` command
and a link to the item folder. An item with `trademarks.restricted` gets no card. Fenolite's README, site
and launch material show third-party items only as gallery images with that line, and an item by an
organisation needs `featured` first. The site stays within the Pages limits (S-0981).

## `fenolite get`

```
fenolite get device FenoliteDevices:EXB6202 --dry-run --json
fenolite get board kicad-demos/ecc83 --into ecc83 --accept-licence CC-BY-SA-4.0 --confirm
fenolite get --locked design.py --offline --confirm
fenolite get --search usb-c --licence cc0 --json
fenolite get --status --script design.py --json
fenolite get --refresh --release 1.0.0 --index-sha256 <hex> --confirm
fenolite get --remove device FenoliteDevices:EXB6202 --dry-run
```

- **Where items go.** `<script folder>/fenolite_library/<kind folder>/<id path>/` (the folder name is a
  Python identifier, so a vendored block imports as `fenolite_library.blocks.<Namespace>.<name>`); a board
  into `--into DIR`, whose own `design.lock` gets the pin. `fenolite_library/ATTRIBUTION.md` is regenerated
  in every plan: one section per vendored item with its title, kind and id, version, authors, licence,
  upstream URL and commit, and modification notice. Ship it with outputs made from the items.
- **Licences first.** The plan lists every item's licence, family, reciprocal flag and obligations; any id
  but `CC0-1.0` must be accepted by name with `--accept-licence` (`FEN-4003`). The client refuses an id
  outside its shipped allow-list, an index row and `PROVENANCE.json` that disagree, or a missing `LICENSE` or
  `NOTICE` (`FEN-3021`).
- **Trust.** Known releases are rows of `src/fenolite/cli/data/library.toml` (version, index size and
  SHA-256); a newer release needs `--index-sha256` or a lock entry's `index`. The index is checked first,
  then each archive against its index row, then each item against its tree (`FEN-3006`).
- **Network.** A download happens only under `--confirm`, one request per missing asset (ADR-0008);
  `--offline` opens no connection (`FEN-6006` when something is not cached). `--from DIR` reads a release
  folder, a library checkout or a `file://` git URL from this machine under the same checks.
- **Offline cache.** `FENOLITE_LIBRARY_DIR`, else `$XDG_CACHE_HOME/fenolite/library`, the platform cache
  folder or `~/.cache/fenolite/library`: `<version>/index.json`, `<version>/assets/<asset>` and a stamp
  `.fenolite-library.toml` of the verified digests. `--list` and `--search` read it only.
- **The lock.** `[library.items."<kind>/<id>"]` holds `index`, `path`, `release`, `spdx`, `tree` and
  `version`. Only `get` changes the section; `fenolite build` reads it and exits 6 with `FEN-6004` when a
  pinned folder is missing (restore with `fenolite get --locked <script>`). `--frozen` builds are unaffected.
- **Updates and removals.** Another version replaces the folder (`before`/`after`); a locally edited
  folder is protected (`FEN-7001`, `--allow-lossy` to replace it). `--remove` refuses an item another
  vendored item depends on.
- **Never** does `get` import, run or build a payload, or send anything about the project.

## Use

Items are test and benchmark inputs for Fenolite and starting points for users. No item is used to train a
machine-learning model; any such use would be a separate, public decision that respects machine-readable
opt-outs. Upstream authors may ask for removal through an issue of the library.
