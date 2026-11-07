# c0418: gallery attribution from each item's provenance

## Why

The deployed gallery (https://lgili.github.io/fenolite-library/, library main `7ebbd960`, 2026-11-05) labels
the LibrePCB-derived symbol, footprint and device "Authored for fenolite-library, licence CC0-1.0". Their
`PROVENANCE.json` says `origin = "seeded"`, authors "LibrePCB Base" and an upstream repository and commit.
`attribution_line` and the "Source" fact only recognise `origin = "converted"` and print "Authored for
fenolite-library" for every other record, so a third-party item is credited to the library. That is a
licensing defect, not cosmetics: a CC-BY-SA-4.0 item must identify its creator, link the material, name the
licence and indicate modifications (S-1770), and even a CC0 item must not be presented as the library's own
work.

## What

- The gallery takes each item's attribution and licence from its `PROVENANCE.json`, cross-checked with the
  release index row (`item.json`): `authored` items alone say "Authored for fenolite-library"; `converted`
  items keep c0279's line; `seeded` items say "Derived from <authors> (<upstream link>) at commit <commit>,
  licence <SPDX>; converted to Fenolite's formats, changes in its PROVENANCE.json. Rendered by Fenolite
  <version>. Not endorsed by the authors." The "Source" fact links the upstream for both third-party origins.
- A provenance the gallery cannot attribute (unknown or missing `origin`, an `authored` record with an
  upstream, a third-party record without authors, an `https` upstream link or a 40-hex commit, or a licence
  that disagrees between `PROVENANCE.json`, `upstream.spdx_expression` and the release index) fails the
  command: exit 5, one `library.provenance-invalid` error per problem naming the item and the field, and no
  write. Nothing falls back to "Authored" or to CC0.
- Library side: once c0418 is on `dev`, the library pin moves to it and the gallery is redeployed.

## Impact

- `fenolite library gallery` can now exit 5 with `library.provenance-invalid` (an existing code; its
  explanation names the gallery too). The pages of `authored` and `converted` items do not change; `seeded`
  items get the derived-from line and an upstream "Source" link.
- No new FEN code, no new dependency, no model change.
