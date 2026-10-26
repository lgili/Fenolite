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

1. **Cache key.** The SHA-256 of the input (the document, or every file of a library folder), the theme, and a
   digest of Fenolite's modules and page (so a development build never serves a scene of another build). The
   cache never holds a file's bytes, only scenes, gzipped; entries are replaced atomically and are safe to
   delete. The default folder is the user's cache, because the command contract says `view` writes nothing
   into the project without `--serve` or `--export`; `FENOLITE_CACHE_DIR` moves it (the tests use it).
2. **Where the time goes.** Task 0.1 profiles S-0187 and records the split (read, pads, scene). The change
   optimises the two largest parts first.
3. **v1 encoding** (`view/compact.py`). Columns in primitive order: `L` layer index, `K` kinds, `N`, `C`, `S`
   (label template) and `SN` (label number, as the difference from the last number of its template), and `D`,
   the geometry as offsets. Python's `expand` and the page's `decodeV1` give back the v0 primitives exactly; a
   scene that v1 cannot hold stays v0. The board scene stays v0 inside Python; v1 is written where a scene
   leaves the process (the server and the exported page).
4. **Export.** `--docs` selects documents; the default stays "every viewable document", with a warning in
   `result.export` when the page passes 20 MB.

## Risks / Trade-offs

- **Stale cache.** A cache keyed by input hashes and the version cannot serve a stale scene; a corrupt entry
  is deleted and rebuilt.
