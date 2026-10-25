## Context

- **Request.** P0-2 of the analysis of 2026-10-25.
- **Measured on 2026-10-25:** S-0174's board 0.7 s and 213 KiB; S-0187's board 12.7 s and 5 053 KiB
  (33 311 primitives). The Draftsman fabrication document of S-0785 gives 8.7 MB of page.

## Goals / Non-Goals

**Goals**
- See the proposal, "What Changes".

**Non-Goals**
- See the proposal.

## Decisions

1. **Cache key.** The SHA-256 of each input file (the document, and for an Altium sheet its project), the
   Fenolite version and the theme. The cache never holds a file's bytes, only scenes; it is written under the
   mutation protocol's rules for derived files (atomic replace) and is safe to delete.
2. **Where the time goes.** Task 0.1 profiles S-0187 and records the split (read, pads, scene). The change
   optimises the two largest parts first.
3. **v1 encoding.** Per layer: `kinds` (bytes as a string), `data` (one integer array), `nets` and `comps`
   (integer arrays), `labels` (indices into `strings`). The page builds the same caches as for v0.
4. **Export.** `--docs` selects documents; the default stays "every viewable document", with a warning in
   `result.export` when the page passes 20 MB.

## Risks / Trade-offs

- **Stale cache.** A cache keyed by input hashes and the version cannot serve a stale scene; a corrupt entry
  is deleted and rebuilt.
