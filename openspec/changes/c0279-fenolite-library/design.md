## Context

- **Source.** `docs/research/board-library.md` (2026-10-29): section 2 (sources), section 3 (licences),
  section 4.5 (the library repository) and section 5 (row c0279), with questions 1 to 4. The maintainer
  decided on 2026-10-29 that:
  - one repository, `fenolite-library` (github.com/lgili/fenolite-library), holds all third-party-derived
    material converted to Fenolite formats: symbols, footprints, devices, circuit blocks and boards;
  - copying from third parties is allowed there only, each item keeping its upstream licence, NOTICE and
    `PROVENANCE.json`, in one folder per kind and licence family;
  - the allow-list and deny-list of research section 3 apply;
  - users pull items with one command, `fenolite get <kind> <id>`, which shows the licence before
    confirm, copies the item into the project with LICENSE and NOTICE, and pins the version in the
    design lock;
  - boards are test and benchmark inputs, and any training use is a separate public decision.
- **What exists on `dev` (0.6.0).**
  - `fenolite fetch NAME` (ADR-0007): the only download. It fetches one pinned tool as a deferred write
    under `--confirm`, checked by size and SHA-256 (`FEN-3006`, `FEN-6003`).
  - `tree_hash` in the scheme `fenolite-tree-1` (`backends/kicad/libcache.py`) and safe extraction with
    the `tarfile` data filter.
  - `fenolite render` and the viewer (c0245), `fenolite equivalent` at five levels.
  - `corpus-policy`: public files are fetched by digest, never committed unless CC0 or authored.
- **What the batches add before or with this change.**
  - c0249: the design lock `<stem>.lock` and `LockSection(name, resolve)`, `--frozen` with `FEN-7004`.
  - c0259: record kinds `pins`, `package`, `device` and `part`, ids `<Namespace>:<name>`, `load_tree`,
    `origin`, `VERSIONS.toml`.
  - c0262: `fenolite library check`, review sheets.
  - c0268: block records, `describe`, `[blocks]` in the lock.
  - c0275 to c0278: `fenolite import --to python`, `fenolite.drawn-schematic.v0`, the DSL coverage and
    `fenolite verify-source` with levels 1 to 8 and S.

## Goals / Non-Goals

**Goals**

- One home for every third-party-derived item, with a licence, a notice and a provenance record per item.
- Licences checked by machine before a merge, and again by the client before a copy.
- Every converted item reproducible from a pinned upstream commit and pinned tool versions.
- Getting an item is one explicit, reviewed act: plan, licence shown, confirm, digest, lock pin.
- Projects build offline with exactly the items they pinned.
- The tool repository stays Fenolite-authored only.

**Non-Goals**

- See the proposal. Also: no signing beyond SHA-256 pins (open question 5), no mirror, no partial item.

## Decisions

### 1. One repository, five kinds

```
fenolite-library/
  README.md            # "each directory keeps its upstream licence"; use statement (decision 13)
  LICENSE              # CC0-1.0 for the repository's own files only (manifests, CI, README)
  library.toml         # schema fenolite.library.v0: name, version, requires.fenolite, tools pins
  licences.toml        # the allow-list and deny-list (decision 4)
  sources.toml         # D- source ids for authored items (c0266)
  symbols/<family>/<Namespace>/<name>/
  footprints/<family>/<Namespace>/<name>/
  devices/<family>/<Namespace>/<name>/
  blocks/<family>/<Namespace>/<name>/
  boards/<family>/<source>/<name>/
  CHANGELOG.md  CONTRIBUTING.md  CODEOWNERS
  .github/workflows/{check.yml,bench.yml,release.yml,gallery.yml}
```

- **Kinds.** On the command line a kind is singular: `symbol`, `footprint`, `device`, `block`, `board`.
  Its folder is the plural.
- **Ids.**
  - `symbol`, `footprint` and `device` items carry c0259 records, so their id is the record id
    `<Namespace>:<name>` (a `pins`, `package` or `device` record).
  - `block` ids are c0268 block ids, also `<Namespace>:<name>`.
  - `board` ids are `<source>/<name>`, lower case, each part matching `[a-z0-9][a-z0-9._-]*`
    (`kicad-demos/cm5_minima`).
  - The id path replaces `:` with `/`. An id is unique within its kind across all families.
- **Families.** The folder `<family>` is a function of the item's SPDX id, defined by `licences.toml`
  (decision 4). An item in the wrong family folder fails the audit.
- **The repository's own files** (manifests, workflows, README) are CC0-1.0. The README says that this
  licence does not cover items and that each directory keeps its upstream licence.
- **Contributions** come by pull request with DCO sign-off and a CODEOWNERS approval.
- **No tooling code.** The repository holds data, item payloads (block and board items contain Python, as
  their payload) and workflows. Its workflows install a pinned released `fenolite` and call the verbs of
  decision 6.
- **Alternatives considered:**
  - two repositories, permissive and copyleft (research question 2). Rejected: family folders give the
    same separation, and one release, one index and one command are simpler.
  - one repository per kind (`fenolite-devices`, `fenolite-blocks`, as c0266 and c0273 first proposed).
    Rejected by the maintainer's decision.

### 2. The item folder and `item.json`

```
devices/cc0/FenoliteDevices/EXB6202/
  item.json  PROVENANCE.json  LICENSE  NOTICE
  EXB6202.toml                       # the payload: c0259 records (c0266)
boards/cern-ohl-s/kicad-demos/cm5_minima/
  item.json  PROVENANCE.json  LICENSE  NOTICE  README.md
  design.py  schematic.toml  lib/     # the payload (c0275, c0276)
```

```json
{
  "schema": "fenolite.library-item.v0",
  "kind": "device",
  "id": "FenoliteDevices:EXB6202",
  "version": "1.2.0",
  "title": "Example step-down converter",
  "summary": "Device record with pins, package and parts",
  "spdx": "CC0-1.0",
  "tags": ["power", "buck"],
  "files": ["EXB6202.toml"],
  "depends": [
    {"kind": "symbol", "id": "FenoliteDevices:EXB6202", "version": "1.0.0"},
    {"kind": "footprint", "id": "FenoliteDevices:SOIC-8_3.9x4.9mm_P1.27mm", "version": "1.1.0"}
  ],
  "executes": false
}
```

- `item.json` is JSON so that c0259's `load_tree`, which reads every `*.toml` of a project tree, never
  reads it as a record.
- `files` lists the payload, relative, sorted. The four fixed files and `README.md` are always allowed.
  Any other file fails the audit (`library.item-extra-file`).
- `depends` pins exact versions of other items. `get` pulls the whole closure. A cycle fails the audit.
- `executes` is `true` for `block` and `board` items, whose payload is Python that runs when a design
  script imports or is built from it. `get` shows it in the plan and never runs it.
- **Item versions** are semantic, per item: c0259's rules for record kinds, c0268's for blocks. A board
  is `1.0.0` when added, MINOR when a regeneration changes its bytes, MAJOR when its upstream commit
  changes.

### 3. `PROVENANCE.json`

Schema `fenolite.provenance.v0`, canonical JSON (keys sorted, two-space indentation, final newline). This
change owns the schema and its library members. It embeds two members owned by other changes:

- `import`: the record that c0275's `fenolite import --to python` writes (`fenolite.import-provenance.v0`:
  inputs with digests, `kicad-cli` upgrades, findings, the self-check equivalence), copied verbatim;
- `fidelity`: c0278's member (tolerances, `accepted` entries, `proof` with a status per level), written by
  `verify-source --record`, which keeps every other member.

```json
{
  "schema": "fenolite.provenance.v0",
  "kind": "board",
  "id": "kicad-demos/cm5_minima",
  "version": "1.0.0",
  "origin": "converted",
  "upstream": {
    "url": "https://gitlab.com/kicad/code/kicad",
    "path": "demos/cm5_minima",
    "commit": "<40 hex>",
    "archive_sha256": null,
    "retrieved": "2026-10-30",
    "spdx_expression": "CERN-OHL-S-2.0",
    "source_location": "https://gitlab.com/kicad/code/kicad/-/tree/<40 hex>/demos/cm5_minima"
  },
  "authors": ["<as named upstream>"],
  "copyright": ["<upstream copyright lines, verbatim>"],
  "spdx": "CERN-OHL-S-2.0",
  "licence_text_sha256": "<normalised LICENSE digest>",
  "modification_notice": "2026-10-30: converted to the Fenolite DSL by Fenolite 0.8.0; format change only",
  "conversion": {
    "tools": [{"name": "fenolite", "version": "0.8.0"}, {"name": "kicad-cli", "version": "10.0.6"}],
    "steps": [
      {"tool": "fenolite", "argv": ["import", "upstream/demos/cm5_minima/cm5_minima.kicad_pro", "--to", "python", "--out", "out", "--upgrade", "--timestamp", "2026-10-30T00:00:00Z", "--confirm"]}
    ],
    "outputs_tree": "fenolite-tree-1:<hex>"
  },
  "import": {"schema": "fenolite.import-provenance.v0", "...": "c0275's record, verbatim"},
  "fidelity": {
    "accepted": [
      {"id": "A001", "level": 7, "kind": "text-field", "where": "board:Cmts.User:*", "field": "size",
       "reason": "<why it is harmless>", "attribution": "fenolite", "decided": "2026-10-30"}
    ],
    "proof": {"fenolite": "0.8.0", "date": "2026-10-30T00:00:00Z", "levels": {"1": "equal", "7": "accepted", "S": "equal"}}
  },
  "trademarks": {"marks": [], "restricted": false, "note": ""},
  "featured": null,
  "evidence": "UNVERIFIED"
}
```

- **`origin`** is one of:
  - `converted`: from an upstream source. `upstream`, `conversion`, `import` and, for boards, `fidelity`
    are required.
  - `authored`: written for the library from public facts. `upstream` is null, the payload's `sources`
    name `D-` ids of `sources.toml`, and `spdx` is `CC0-1.0`, or `Apache-2.0` for a block.
  - `seeded`: from a CC0 library by c0266's seed. `upstream` names that library and commit, and each
    record keeps c0259's `origin.element`.
- **`upstream.commit`** is a full 40-hex commit. `archive_sha256` is set when the replay downloads an
  archive instead of a git fetch.
- **`spdx`** is one allow-listed id (decision 4). When the upstream offers an expression (`A OR B`), it is
  kept in `upstream.spdx_expression` and `spdx` names the allowed choice. It MUST equal `import.licence`.
- **`modification_notice`** is dated and states what changed. CERN-OHL v2 asks for it explicitly; CC asks
  to "indicate changes", Apache-2.0 and Solderpad to state changes. The same text heads `NOTICE`, followed
  by the upstream notices, verbatim. It matches the conversion line of c0275's file headers.
- **`conversion.steps`** are replayable. Each `tool` is `fenolite` or `kicad-cli`. Paths are relative to a
  work folder holding `upstream/` (the checkout at `commit`) and `out/`. Input digests and upgrades are in
  `import` (c0275). `outputs_tree` is the tree digest of `out/` without its `PROVENANCE.json`, which equals
  the item's payload; the `PROVENANCE.json` that c0275 writes into `out/` equals the `import` member.
- **Accepted differences** are `fidelity.accepted` (c0278's entries: id, level, kind, where, field, reason,
  attribution, date decided). They enter only through a reviewed pull request (c0278 open question 4).
- **The proof result** is `fidelity.proof`: a status per level. The library derives `result`: `pass` when
  every level is `equal`, `pass-with-accepted` when some are `accepted`, else `fail`. A `fail` never merges.
- **`trademarks`** lists upstream marks on the item (logos, names). `restricted: true` (for example, a
  licence or a trademark policy forbidding logos on derivatives) keeps the item out of the gallery until
  the marks are removed by a recorded step.
- **`featured`** is null, or `{"permission": "<public link>", "date": "..."}` when the authors agreed to
  marketing use (decision 9).
- **`evidence`**: the lowest label of the item. A converted item with a passing proof may be
  `CORPUS-VERIFIED`; others start at `UNVERIFIED`.

### 4. Licence lists

`licences.toml` (schema `fenolite.library-licences.v0`) is committed in the library. A copy ships in the
core as `src/fenolite/cli/data/library-licences.toml`, and a test keeps the two equal for each release.

| family folder | SPDX ids | reciprocal | what a copy must carry |
|---|---|---|---|
| `cc0` | `CC0-1.0` | no | nothing required; attribution kept as courtesy |
| `cc-by` | `CC-BY-3.0`, `CC-BY-4.0` | no | attribution, changes indicated |
| `cc-by-sa` | `CC-BY-SA-2.5`, `CC-BY-SA-3.0`, `CC-BY-SA-4.0` | yes | attribution, changes indicated, same licence |
| `cern-ohl-p` | `CERN-OHL-P-2.0` | no | notices, dated modification notice |
| `cern-ohl-w` | `CERN-OHL-W-2.0` | yes (weak) | notices, modification notice, same licence, Source Location |
| `cern-ohl-s` | `CERN-OHL-S-2.0` | yes | notices, modification notice, same licence, Source Location |
| `cern-ohl-1.2` | `CERN-OHL-1.2` | yes | notices, modification notice, same licence |
| `mit` | `MIT` | no | copyright and licence text |
| `bsd` | `BSD-2-Clause`, `BSD-3-Clause` | no | copyright and licence text |
| `apache` | `Apache-2.0` | no | licence, NOTICE, stated changes |
| `solderpad` | `SHL-0.5`, `SHL-0.51`, `SHL-2.0`, `SHL-2.1` | no | licence, NOTICE, stated changes |
| `gpl` | `GPL-2.0-or-later`, `GPL-3.0-only`, `GPL-3.0-or-later` | yes | source (the Python is the source), notices, changes marked |
| `tapr` | `TAPR-OHL-1.0` | yes | notices, changes marked, same licence |

- **The allow-list is closed.** Any other id is refused, which covers the deny-list by construction.
  The deny-list is still written out, so that the audit gives a precise reason:
  - any id with `-NC` (non-commercial) or `-ND` (no derivatives);
  - `NOASSERTION`, `NONE`, an empty licence, an upstream without a licence file at the pinned commit;
  - `LicenseRef-*`;
  - platform-restricted origins, by `upstream.url` host: `easyeda.com`, `oshwlab.com`, `oshwhub.com`,
    `lceda.cn`, and items marked `vendor-bundled` (examples bundled with commercial CAD software).
- **Licence text.** The audit normalises `LICENSE` (lower case, whitespace collapsed) and compares its
  SHA-256 with the digests listed for that id. A variant text (an older revision, a project preamble)
  needs `licence_review = {"by": "...", "date": "...", "note": "..."}` in `PROVENANCE.json`, approved by a
  CODEOWNER.
- **Reciprocal families** are flagged in `get`'s plan, so that a user sees that a copy into a project
  brings share-alike or copyleft terms for that item.

### 5. The library's CI

`check.yml` runs on every pull request with `uv tool install fenolite==<library.toml tools.fenolite>`:

| job | what it runs | fails on |
|---|---|---|
| `audit` | `fenolite library audit . --base <base ref> --json` | layout, schema, licence, notice, provenance, id or version-rule errors |
| `records` | `fenolite library check` (c0262) over `symbols/`, `footprints/`, `devices/` | any error finding |
| `blocks` | `fenolite blocks index <item> --check` (c0273) and `fenolite blocks test` (c0270) for changed block items | any difference or failed test |
| `replay` | `fenolite library replay <item> --json` for each changed converted item | an outputs tree that differs from the payload |
| `proof` | c0278's `verify-source` for each changed board, with `fidelity.accepted` | a new difference, a failing level, or statuses that differ from `fidelity.proof` |
| `renders` | gallery images of changed items, uploaded as an artefact | never: evidence for the reviewer |

- **Replay** (`fenolite library replay ITEM`): it fetches the upstream at `commit` (a shallow git fetch of
  that commit, or the archive checked against `archive_sha256`) into a temporary work folder. It runs the
  steps with the tool versions of `conversion.tools`: `fenolite` through `uvx fenolite==<version>`,
  `kicad-cli` from a pinned image. It refuses any tool outside the two. It checks `inputs`, then compares
  the tree digest of `out/` with `outputs_tree` and with the payload. It writes nothing into the
  repository.
- **Proof rule.** The job runs `verify-source <item>/design.py --against <upstream> --provenance
  <item>/PROVENANCE.json` with the pinned Fenolite. c0278 applies `fidelity.accepted` as exclusions. Every
  level MUST be `equal` or `accepted`, and the statuses MUST equal `fidelity.proof.levels`; a new difference
  fails (`library.proof-failed`). c0278's `fidelity.accepted-unused` (warning) asks for unused entries to
  be removed.
- **Benchmark** (`bench.yml`): weekly and on each Fenolite release, every board is replayed with the
  **newest** Fenolite instead of its pinned one, and every proof rerun. It publishes a table (board, levels,
  time, differences) as a workflow artefact and on the gallery's benchmark page, and opens one issue per
  newly failing board. It never blocks a merge. A regression in a reader, the DSL or a writer shows up
  here as a failed board.
- **Fenolite's own CI** gains an optional scheduled job `library-bench` that runs the benchmark on a few
  boards from the newest release with the head of `dev`. It is not required for merge.

### 6. Verbs for the library's tooling

`fenolite library` gains four reserved verbs, beside c0266's `seed` and the other changes' verbs:

| verb | kind | what it does |
|---|---|---|
| `audit ROOT [--item PATH] [--base REF]` | read-only | decision 1 to 4 rules; with `--base`, version rules against the base tree |
| `replay ITEM [--upstream DIR] [--keep DIR]` | read-only for the tree (temporary work folder) | decision 5 replay; `--upstream` uses a given checkout |
| `release ROOT --version V --out DIR` | mutating, plan and confirm | decision 7 assets |
| `gallery ROOT --release DIR --out DIR` | mutating, plan and confirm | decision 9 site |

They live in `src/fenolite/library/` (which may import `core`, `model`, `catalog` and `dsl`, and is added
to the layering table) and `cli/cmd_library.py`. `capabilities` lists them as `library <verb>`.

### 7. Releases with digests

- **Version.** `library.toml` `version` is semantic: MINOR when items are added or get new versions,
  PATCH for metadata only, MAJOR when an item is removed or `requires.fenolite` rises. A release is never
  re-tagged.
- **`release.yml`** on a tag `v<version>` runs `fenolite library release . --version <version> --out
  dist --confirm` and uploads:
  - `index.json` (schema `fenolite.library-index.v0`): `name`, `version`, `commit`, `requires`, and one row
    per item with `kind`, `id`, `version`, `title`, `summary`, `spdx`, `family`, `reciprocal`, `tags`,
    `path`, `tree` (`fenolite-tree-1` of the item folder), `bytes`, `archive`, `depends`, `executes`,
    `evidence`, `proof` (result) and `gallery` (page path, or null). A final `archives` list gives each
    archive's `name`, `bytes` and `sha256`.
  - **shard archives** `<kind>-<family>.tar.gz` for `symbols`, `footprints`, `devices` and `blocks`, and
    one archive per board, `board-<source>-<name>-<version>.tar.gz`. The board archives stay small and
    the asset count stays within the host's per-release limit.
  - `SHA256SUMS` of every asset.
- **Byte-reproducible recipe**, as c0266 first wrote it: one top-level folder, members sorted by path,
  mtime 0, uid and gid 0, mode 0644 or 0755, no link, gzip with mtime 0 and no name. The release job builds
  twice and compares bytes.
- **Old items stay available.** A removed item is absent from newer indexes but stays in the older
  releases that a lock may pin.

### 8. `fenolite get`

```
fenolite get device FenoliteDevices:EXB6202 --dry-run --json
fenolite get device FenoliteDevices:EXB6202 --confirm --plan <plan_id>
fenolite get board kicad-demos/cm5_minima --into cm5 --dry-run --json
fenolite get board kicad-demos/cm5_minima --into cm5 --accept-licence CERN-OHL-S-2.0 --confirm --plan <plan_id>
fenolite get block FenoliteBlocks:buck_6v --version 1.1.0 --script design.py --dry-run
fenolite get --locked design.py --offline --confirm
fenolite get --list --kind board --json
fenolite get --search "usb-c" --licence cc0 --json
fenolite get --status --script design.py --json
fenolite get --refresh --release 1.4.0 --index-sha256 <hex> --confirm
fenolite get --remove device FenoliteDevices:EXB6202 --script design.py --dry-run
```

- **Arguments.** `get KIND ID [--version V] [--release R] [--script FILE] [--into DIR] [--from DIR]
  [--offline] [--index-sha256 HEX] [--accept-licence SPDX[,SPDX...]] [--allow-lossy]` with the mutation
  options. The other forms are exclusive with `KIND ID`.
- **Which release.** `--release R`, else the newest release in `cli/data/library.toml` that holds the item
  (at `--version V` when given), else the newest cached index. `--version` without a release that holds it
  exits 2 (`FEN-2001`) and lists the versions found.
- **Where it copies.**
  - `symbol`, `footprint`, `device` and `block`: into `<script folder>/fenolite_library/<kind folder>/<id path>/`.
    `--script` defaults to `design.py` in the working directory; without a script the command exits 2
    (`FEN-2001`, "name the design script with --script"). c0266 reads `fenolite_library/symbols`,
    `fenolite_library/footprints` and `fenolite_library/devices` as project records, and c0273 reads
    `fenolite_library/blocks`. The folder name is a valid Python identifier, so vendored blocks import as
    `fenolite_library.blocks.<Namespace>.<name>`, and it is unlikely to clash with an installed module.
    `get` writes no `__init__.py` above an item folder.
  - `board`: the item's payload and fixed files go into `--into DIR` (default `./<name>`), which must be
    missing or empty. The board's own lock `<into>/design.lock` gets the pin.
  - Every copied folder holds the item's `LICENSE`, `NOTICE`, `PROVENANCE.json` and `item.json`
    unchanged.
- **Closure.** `depends` is followed. An item already vendored at the same version and tree is reused. One
  at another version gives `library.depends-conflict` (error, exit 5) naming both versions; nothing is
  planned.
- **`fenolite_library/ATTRIBUTION.md`** is regenerated in every plan from the vendored items. Each item gets a row
  with title, kind and id, version, authors, SPDX id, upstream URL and commit, and the modification
  notice. The rows are sorted by kind and id. The file is plain text that a project can ship with its
  outputs.
- **The plan.** It contains:
  - every file (kind `library-item`), `fenolite_library/ATTRIBUTION.md` (kind `attribution`) and the lock (kind
    `lock`, c0249);
  - the cache writes (kind `library-cache`) when assets must be downloaded.

  `result.items[]` gives per item `kind`, `id`, `version`, `release`, `spdx`, `family`, `reciprocal`,
  `obligations` (decision 4's last column), `authors`, `upstream`, `path`, `tree`, `bytes`, `executes`,
  `required_by`, `proof` and `evidence`. `result.licences[]` gives each distinct SPDX id with
  `accept_required`.
- **Licence before confirm.** The dry run always shows the licences. `--confirm` of a plan that holds any
  licence other than `CC0-1.0` needs `--accept-licence` naming each such id. Otherwise it exits 4 with
  `FEN-4003`, lists the missing ids and writes nothing. The accepted ids are echoed in the receipt.
- **The client checks licences too.** An item whose `spdx` is not in the shipped
  `library-licences.toml`, whose index row and `PROVENANCE.json` disagree, or that lacks `LICENSE` or
  `NOTICE`, is refused with `FEN-3021` (exit 3).
- **Update.** A request for a vendored item at another version replaces its folder. `result.items[]` then
  shows `before` and `after`. A folder whose tree differs from its pin (a local edit) is refused with
  `FEN-7001` (`library.item-modified`) unless `--allow-lossy` is given.
- **Remove.** `--remove KIND ID` plans the folder's deletion, the lock entry's removal and the new
  attribution file. An item that another vendored item depends on is refused (`FEN-2001`, naming it). A
  modified folder needs `--allow-lossy`.
- **Restore.** `--locked SCRIPT` plans every lock entry whose folder is missing, from the pinned release
  and tree. It changes nothing else.
- **Status.** `--status [--script FILE]` is read-only. Per entry it shows `present`, `modified` and
  `newer` (a higher version in the newest cached index). It exits 5 with `library.item-missing` when a
  folder is missing.
- **Never** does `get` import, run or build a payload, send anything about the project, or touch files
  outside the planned ones.

### 9. The gallery

- `gallery.yml` runs on each release: `fenolite library gallery . --release dist --out site --confirm`,
  then publishes `site/` to GitHub Pages of the library repository.
- **Images** are made by Fenolite only, never upstream images:
  - boards: `fenolite render` top and bottom views, and the drawn schematic's first sheet;
  - symbols, footprints and devices: c0262 sheets;
  - blocks: the c0269 schematic of the block's usage example.
- **Every card** shows the image, the title and this attribution line: "Converted from the open-source
  design <title> by <authors> (<upstream link>), licence <SPDX>. Rendered by Fenolite <version>. Not
  endorsed by the authors." It also shows the proof result, the `fenolite get` command, and a link to
  the item folder. Authored items read "Authored for fenolite-library".
- **Names and marks.** Card text uses descriptive wording ("compatible with X", never "an X board"). An
  item with `trademarks.restricted` is not shown.
- **Marketing** (Fenolite's README, site, launch copy) may show third-party material only as gallery
  images with their attribution line. An item by an organisation needs `featured` first (research
  question 4). The `public-presentation` delta states this rule.
- The benchmark page (decision 5) is part of the site.

### 10. Trust and network rules

- **Known releases.** `src/fenolite/cli/data/library.toml` lists, per release, `version`, `index_url`,
  `index_bytes` and `index_sha256`, plus `url_template` for assets:
  `https://github.com/lgili/fenolite-library/releases/download/v{version}/{asset}`. Each released core
  carries the rows known at its release. A newer release needs `--index-sha256 HEX` (shown on the
  library's release page), or the `index` digest of a lock entry.
- **Chain.** The index digest is checked first (`FEN-3006` on a mismatch). Each archive is then checked
  against the index's `archives` row, and each extracted item folder against its row's `tree`.
- **Requests.** One `https` request per needed asset, with only `User-Agent: fenolite/<version>`, a 60 s
  timeout, `https`-only redirects, at most the expected bytes plus one, and no retry. A failure exits 6
  with `FEN-6003`. The requests are deferred writes made only under `--confirm`, as in `fetch`.
- **`--from DIR`** reads a release's assets from a local folder (copied by hand), under the same digest
  checks.
- **ADR-0008** "Getting library items" records that `get` is the second downloading command. It
  downloads only data and payloads from `lgili/fenolite-library` releases, only pinned digests, only under
  `--confirm`, and never executes them. ADR-0007 gains a dated line pointing to it.

### 11. The offline cache

- `<library dir>` is `FENOLITE_LIBRARY_DIR` (absolute), else `$XDG_CACHE_HOME/fenolite/library`, the macOS
  and Windows cache folders, or `~/.cache/fenolite/library` (the rules of `fenolite.core.tools`).
- It holds `<library dir>/<version>/index.json` and `<library dir>/<version>/assets/<asset>`, each written
  by `os.replace` after its digest check, and a stamp `.fenolite-library.toml` per version listing the
  verified digests.
- `get` reuses a cached asset whose digest matches, and opens no connection then. `--offline` forbids
  any request. A needed asset or index missing from the cache exits 6 with `FEN-6006`, whose hint names
  the same command without `--offline`, or `--from DIR`.
- `--list` and `--search` read only the cache (the newest cached index, or `--release`). With no cached
  index they exit 6 with `FEN-6006` and the hint `fenolite get --refresh --dry-run`. `--refresh` is the
  mutating form that downloads one index into the cache.

### 12. The lock pins

c0249's lock gains the section `library`, registered through `LockSection`:

```toml
[library.items."device/FenoliteDevices:EXB6202"]
index = "sha256:5d0e…"
path = "fenolite_library/devices/FenoliteDevices/EXB6202"
release = "1.4.0"
spdx = "CC0-1.0"
tree = "fenolite-tree-1:9c1e…"
version = "1.2.0"
```

- The key is `<kind>/<id>`. `path` is relative to the script's folder. `index` lets `--locked` verify a
  release that the running core does not list.
- **Only `get` changes the section.** A build reads it: an entry whose folder is missing gives
  `library.item-missing` (error) and exits 6 with `FEN-6004`. The hint is `fenolite get --locked <script>
  --dry-run`, and nothing is written. A build does not hash vendored folders; `--status` and `get` do.
- `fenolite build --frozen` is unaffected, since a build never changes the section. `get` refuses
  `--frozen` (exit 2).
- c0266 and c0273 rely on this section ("pack version in the lock"). c0273 also keeps c0268's `[blocks]`
  instance versions.

### 13. Use statement, AGENTS.md and the corpus

- **The library README** states: items are test and benchmark inputs for Fenolite and starting points
  for users. No item is used to train a machine-learning model. Any such use would be a separate, public,
  announced decision that respects machine-readable opt-outs. Upstream authors may ask for removal
  through an issue.
- **AGENTS.md** gains, under "Hard rules", the sentence: "**Third-party material lives only in
  `fenolite-library`** (github.com/lgili/fenolite-library): symbols, footprints, devices, blocks and
  boards derived from third-party sources go there, never into this repository, each item with its
  upstream licence, NOTICE and `PROVENANCE.json`." The clean-room rule keeps applying to the tool
  repository. Private and employer material stays forbidden in both.
- **ADR-0003** gains a dated line saying the same.
- **corpus-policy.** A test of the tool repository that needs a library item uses a manifest row: `url`
  is the release asset, `ref` the release tag, `sha256` the archive digest, `license` the item's SPDX id,
  and `uses` holds `origin:third-party` and `library:<kind>/<id>@<version>`. Such a row is
  `embeddable = false` unless the item is `CC0-1.0`. No item, `PROVENANCE.json` or vendored `fenolite_library/`
  folder from the library is committed under `tests/`, `examples/` or `src/`.

### 14. Codes

| code | severity / exit | when |
|---|---|---|
| `library.item-missing` | error → exit 6 `FEN-6004` | a lock entry's folder is missing (build, `--status`) |
| `library.item-modified` | error → exit 7 `FEN-7001` without `--allow-lossy` | an update or remove meets a locally edited folder |
| `library.depends-conflict` | error → exit 5 | the closure needs another version of a vendored item |
| `library.licence-denied` | error (audit) / exit 3 `FEN-3021` (get) | an SPDX id outside the allow-list, or a denied origin |
| `library.licence-text` | error | `LICENSE` does not match its id and has no `licence_review` |
| `library.notice-missing` | error | `NOTICE` absent or without the dated modification notice |
| `library.provenance-invalid` | error | `PROVENANCE.json` fails its schema or disagrees with `item.json` |
| `library.family-mismatch` | error | an item is in a family folder that its SPDX id does not map to |
| `library.item-extra-file` | error | a file not listed in `files` |
| `library.duplicate-id` | error | one id twice in a kind |
| `library.version-rule` | error | a changed item without the version step (`--base`) |
| `library.replay-differs` | error | the replay's outputs tree differs from the payload |
| `library.proof-failed` | error | a proof level fails or meets a new difference |
| `FEN-6004` | exit 6, not retryable | "a library item pinned by the design lock is missing"; hint names `get --locked` |
| `FEN-6006` | exit 6, not retryable | "the library index or asset is not in the offline cache" |
| `FEN-4003` | exit 4 | "the item licences must be accepted by name"; hint names `--accept-licence` |
| `FEN-3021` | exit 3 | "the item's licence is not allowed or its licence files are missing" |
| `FEN-3006` | exit 3 | existing: index, archive or tree digest mismatch |
| `FEN-6003` | exit 6, retryable | existing: download failed |

`FEN-6004` was first proposed by c0266 for a missing device pack; c0266 now uses this definition.
`FEN-6006` was first proposed by c0273 for a missing block package; c0273 no longer needs it.
`FEN-6005` stays c0267's.

### 15. Phases

- **Phase A** (needs c0249, c0259): the repository with its families, schemas, licence lists, `audit`,
  `release`, `get` with cache and lock, ADR-0008, AGENTS.md. Its first content is the authored and seeded
  items of c0266 and c0273.
- **Phase B** (needs c0275 to c0278): the `boards` kind, `replay` of conversions, the `proof` and
  `bench` jobs, the gallery, and the first boards of research section 4.6 (the KiCad demos with a usable
  licence, then a few permissive professional boards, then one CERN-OHL board from each of three
  sources), each with a passing proof or recorded accepted differences.

## Risks / Trade-offs

- **Licence mistakes upstream.** A project may carry a licence it cannot grant. Mitigation: the licence
  is read from the pinned commit, the reviewer checks it, and removal on request is promised in the
  README.
- **Reciprocal terms reaching user projects.** A CC BY-SA footprint copied into a project brings
  share-alike terms for that footprint. Mitigation: `reciprocal` in the plan, explicit acceptance, and
  `ATTRIBUTION.md`.
- **Code in items.** Block and board payloads are Python. Mitigation: `executes` in the plan, review in the
  library's CI, and `get` never runs them.
- **A second downloading command** widens ADR-0007. Mitigation: the same rules (confirm, pins, digests,
  nothing sent) and a separate ADR.
- **Release asset limits** of the host. Mitigation: shards per kind and family, one archive per board.
- **Benchmark noise.** The newest Fenolite may legitimately change output. Mitigation: `bench` reports
  and never blocks, and the PR-time proof uses the pinned version.

## Open questions

1. *Repository name and owner.* Decided: `lgili/fenolite-library`.
2. *Licence of the repository's own files.* Recommended: CC0-1.0, with the README stating that items keep
   their own licences.
   Decided 2026-10-29: CC0-1.0 for the repository's own files; the README states that items keep their own licences (`library audit` checks it).
3. *Project licence compatibility.* Should `get` compare an item's licence with a licence the project
   declares? Recommended: later. Flag `reciprocal` now.
   Decided 2026-10-29: later; `get` flags `reciprocal` and lists the obligations now.
4. *Fabrication outputs.* Should `export` copy `fenolite_library/ATTRIBUTION.md` into the fabrication package?
   Recommended: yes, in a follow-up change.
   Decided 2026-10-29: yes, in a follow-up change; `get` already writes `fenolite_library/ATTRIBUTION.md`.
5. *Signed releases (Sigstore) besides SHA-256 pins?* Recommended: later. Pins already make a tampered
   asset fail.
   Decided 2026-10-29: later; the index, archive and tree digests make a tampered asset fail (`FEN-3006`).
6. *Proof of converted non-board items* (a footprint from a CC BY-SA library). Recommended: c0278's pad
   and geometry levels on a one-item board built by the replay. Revisit when c0278 lands.
   Decided 2026-10-29: c0278's pad and geometry levels on a one-item board built by the replay, revisited when the first converted non-board item is proposed; not in this change.
7. *Private libraries in the same format* (a company's own items). Recommended: later, as `get --source
   <url>` with its own `library.toml` row. Not in this change.
   Decided 2026-10-29: later, as `get --source <url>` with its own `library.toml` row; not in this change (`--from DIR` reads a local checkout meanwhile).

## Relation to other changes

- **c0249**: the `library` lock section.
- **c0259**: record ids and `load_tree`. `item.json` is JSON so that `load_tree` ignores it.
- **c0262**: `library check` in the `records` job, and the sheets in the gallery.
- **c0266**: the `devices`, `symbols` and `footprints` kinds, the LibrePCB CC0 seed landing in
  `devices/cc0/` (with `origin: seeded`), and project records read from `fenolite_library/`. It no longer has its
  own repository, `library fetch` or extra.
- **c0273**: the `blocks` kind, discovery of vendored blocks without import, and `blocks index` per item.
  It no longer has the `fenolite-blocks` repository or entry points.
- **c0264**: user imports never enter the library. `library audit` refuses a record that
  `shippable()` rejects.
- **c0267**: supplier answers never enter the library.
- **c0275 to c0278**: the conversion, drawn schematic, DSL coverage and proof that board items need.
  c0275's `fenolite.import-provenance.v0` record becomes the `import` member and c0278's `fidelity` member
  is kept as written; this change owns `fenolite.provenance.v0` and its other members. c0278 calls the file
  `fenolite.provenance.v0` created by c0275, while c0275 writes `fenolite.import-provenance.v0` into `out/`;
  task 0.1 records which change writes which schema once both are implemented.

## State at the end of the first implementation session (2026-10-30)

Done in Fenolite: ADR-0008, the AGENTS.md rule, items, provenance, licence lists, `library audit` (with
`--base` and `--proof`), `library release`, `replay`, `gallery`, the proof gate and benchmark table, `fenolite
get` with cache, trust chain, lock section, `--locked`, `--status`, `--remove`, `--list`, `--search`,
`--refresh`, the four `FEN-` codes, docs, agent guide and CHANGELOG.

Left:

- 0.1: `openspec validate c0279-fenolite-library --strict`.
- 5.6: a complete `make check-fast` (the last one was cut off by the session limit; the failures of the
  first run are fixed), then CI on the working branch.
- 3.1, 3.2, 4.4, 4.5: work in the `fenolite-library` repository (licences.toml copy, LICENSE, README
  statements, workflows calling the `library` verbs, `verify-source --record` again for the four boards so
  that `fidelity.proof.skipped` names the reason of level S).
- 3.3: the first library release and its row in `src/fenolite/cli/data/library.toml`.
- 5.3: the example waits for c0266 (reading `fenolite_library/devices` as project records).

