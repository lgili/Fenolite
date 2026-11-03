---
topic: library-items
title: Getting licensed library items
summary: Review licensed items, offline pins, device migrations and block package tests, indexing and upgrades.
---

# Getting licensed library items


Third-party symbols, footprints, devices, blocks and boards come from the library repository
`fenolite-library`, each with its licence. `get` copies an item and what it depends on into
`fenolite_library/` beside the script, with `LICENSE`, `NOTICE` and `PROVENANCE.json`, writes
`fenolite_library/ATTRIBUTION.md` and pins the item in the design lock. It never runs a payload.

```fenolite-cmd
fenolite get --search buck --licence cc0 --json
fenolite get device Demo:EXB --from release --dry-run --json
fenolite get footprint Demo:SA_PAD --from release --accept-licence CC-BY-SA-4.0 --confirm --json
fenolite get board demo-src/blink --into blink --accept-licence CERN-OHL-S-2.0 --dry-run --json
fenolite get --locked design.py --offline --dry-run --json
fenolite get --status --json
```

- Read `result.licences` before confirming: an id other than `CC0-1.0` must be named in
  `--accept-licence` (`FEN-4003`). A `reciprocal` item brings share-alike terms with it; tell the user.
- A download happens only with `--confirm`; `--offline` uses the cache. A build whose pinned folder is
  missing exits 6 (`FEN-6004`): restore it with `get --locked`.
- The library's own CI runs `library audit`, `replay`, `release` and `gallery`:

  ```fenolite-cmd
  fenolite library audit . --json
  fenolite library release . --version 1.0.0 --out dist --dry-run --json
  fenolite library gallery . --release dist --out site --dry-run --json
  fenolite library replay boards/cc-by-sa/kicad-demos/ecc83 --upstream upstream --json
  ```

## Migrating a device record

```fenolite-cmd
fenolite fmt devices/regulator.toml --dry-run --json
```

On a `fenolite.device.v0` record, `fmt` plans its rewrite as `fenolite.device.v1` with the same device
(`result.schema` names what it read): version `1.0.0`, the licence of a leading
`# SPDX-License-Identifier:` line or `NOASSERTION`. A v1 file is left unchanged; a comment after the
first key is refused (`FEN-7001`, exit 7).

## Library block packages

Blocks have three homes: starter blocks in `fenolite.blocks`, licensed items in `fenolite-library`, and
project modules. `Fenolite` is reserved for the starter library; authored library items use
`FenoliteBlocks`. `Demo:led` below is the authored test item; substitute an available release item.

```fenolite-cmd
fenolite get block Demo:led --from release --dry-run --json
fenolite blocks list --script design.py --json
fenolite blocks show Demo:led --script design.py --json
fenolite blocks test Demo:led --script design.py --only tests --json
fenolite blocks index item --out item/block.json --dry-run --json
fenolite blocks index item --check --json
fenolite blocks upgrade design.py --out build --block Demo:led --dry-run --json
fenolite blocks upgrade design.py --allow-major --dry-run --json
```

Listing, showing and documenting library blocks read `block.json` without importing their code.
Indexing explicitly executes the package and describes its one `__all__` block. `--check` writes
nothing and fails on a stale record; a build warns about a local edit and uses the code.

Getting a new item reviews its files, licence and `[library.items]` pin. `blocks upgrade` separately
reviews changed instance versions in `[blocks]`, the new records, deprecations and build issues.
With `--out`, read each row's `circuit` before/after part values and ids against the previous build.
Confirm the reviewed plan to write only the lock; existing refs, picks, pins and item pins stay.
Confirmation with `--plan` does not run the script again. `--block` selects ids; `--allow-major` needs
an explicit review, and `--frozen` is not accepted. See `docs/blocks.md` for authoring and version rules.

Imported native footprint aliases retain the source instance declaration, with exact local
board geometry and explicit `footprint_definition` variants for edits. Conflicting definition lookups
or genuine basename mismatches refuse before staging; do not remove the explicit lookup or substitute
an arbitrary Footprint text override to silence a level3/S/8 difference.

Read next: `footprints`, `files`, `recovery`.
