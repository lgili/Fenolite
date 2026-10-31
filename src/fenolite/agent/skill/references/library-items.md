---
topic: library-items
title: Getting licensed library items
summary: Review licences, fetch pinned library items, restore offline copies and audit library releases.
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

Read next: `footprints`, `files`, `recovery`.
