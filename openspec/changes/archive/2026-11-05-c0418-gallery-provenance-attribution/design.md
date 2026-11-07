# c0418 design

## Attribution by origin

`PROVENANCE.json` (schema `fenolite.provenance.v0`, `fenolite.library.provenance`) has three origins. The
gallery derives its text only from the record and the release index row:

| origin | attribution line | "Source" fact |
|---|---|---|
| `authored` | `Authored for fenolite-library, licence <SPDX>. Rendered by Fenolite <v>.` | `Authored for fenolite-library` |
| `converted` | c0279's line: `Converted from the open-source design <title> by <authors> (<link>), licence <SPDX>. Rendered by Fenolite <v>. Not endorsed by the authors.` | upstream link at commit |
| `seeded` | `Derived from <authors> (<link>) at commit <commit12>, licence <SPDX>; converted to Fenolite's formats, changes in its PROVENANCE.json. Rendered by Fenolite <v>. Not endorsed by the authors.` | upstream link at commit |

`<link>` is `upstream.source_location` or `upstream.url`. The seeded line carries the four elements CC BY-SA 4.0
section 3(a)(1) asks for (creator, a link to the material, the licence, an indication of modification), and
section 3(a)(2) lets the modification details live in a linked resource: the item page links the item
folder, which holds `PROVENANCE.json` with its dated `modification_notice` (S-1770). CC0 needs no attribution
(S-1771), but the line still names the upstream so a CC0 item is never shown as the library's own work.
LibrePCB Base states CC0-1.0 (S-1772), which is what its items record.

## Problems instead of fallbacks

`attribution_problems(row, record)` lists every reason the gallery cannot attribute an item:

- `origin` missing or not one of `authored`, `converted`, `seeded`;
- `spdx` missing, or different from the index row's `spdx`, or from `upstream.spdx_expression` when that is
  given;
- `authored` with a non-null `upstream`;
- `converted` or `seeded` without an `upstream` object, without a non-empty `authors` list, without an
  `https://` link, or without a 40-hex `upstream.commit`.

`library gallery` runs it for every visible row before it plans pages. Any problem becomes a
`library.provenance-invalid` error (`where` = the item path, the message names the item id and the field);
the result keeps `cards`, `hidden` and `placeholders` empty, holds `provenance` (the problems) and plans no
write, so the command exits 5 (cli-contract: error findings plan no write). `attribution_line` and the
"Source" fact raise `ValueError` for a record with problems instead of falling back, so a caller of `site`
that skips the check still cannot print "Authored" for a third-party item.

The audit (`library audit`) keeps its own schema rules; the gallery check is narrower and only about what a
page may claim. Reusing `library.provenance-invalid` avoids a new code: the explanation gains the gallery case.

## Tests

`tests/unit/library/test_gallery.py` uses the demo library: the authored device `Demo:EXB` keeps "Authored
for fenolite-library"; the seeded CC-BY-SA-4.0 footprint `Demo:SA_PAD` (authored for the tests, recorded as
seeded from `https://example.org/demo-pads`) gets the derived-from line with its authors, link, commit and
licence and no "Authored" text. Contradictions (an index licence that differs, a seeded record without an
upstream, a missing origin) make the gallery exit 5 with `library.provenance-invalid` and write nothing.
