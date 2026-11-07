# Design: c0415

Base: `origin/cac/lote-22` (6817d7b1).

## What the reviewer saw

`library check` builds one sheet per item (`view/review_sheet.py`):

1. `catalog_page(entries)` (with `_all_units`) is `export.page(project, scenes)`: the packaged template
   (`page.html` with `viewer.css` and `viewer.js` inlined) with `const EMBED = {...}` holding the project
   tree and the packed scenes (`compact.pack`).
2. A `<section id="review-content">` before `</body>`: the record id, one `<pre>` per metadata block
   (record and dimension sources, pin table, pin-to-pad map, referenced records, cited proposals), the
   findings.
3. On a comparison sheet only: one `application/json` script per visual diff and an iframe whose `srcdoc`
   is a whole second viewer page.

What a person checks is 1's data and 2 (and 3's payload on a comparison sheet). The template bytes are code.

## Content digest

`content_digest(sheet: bytes) -> str` = SHA-256 of the canonical JSON (sorted keys, compact separators,
UTF-8) of

```json
{"schema": "fenolite.review-content.v1", "embedded": <export.embedded(page) or null>, "review": "<text>"}
```

- `embedded` is the embedded data with each scene unpacked, so neither the viewer code nor the packing
  format is hashed.
- `review` is the sheet text from `<section id="review-content">` to the last `</body>`, with each
  `srcdoc="..."` attribute value emptied (the diff payload script keeps the scene; the iframe copy is a
  page with the template inside). A sheet without the section (impossible for sheets Fenolite writes)
  gives `""`.

Computing it from the bytes, not from the inputs of `review_sheet`, keeps one source of truth: the digest
describes exactly the file the reviewer opened, and a sheet file kept from an earlier run can be checked
later.

What still changes it, on purpose: any record, definition, dependency or finding change (as today), and a
change of the Python rendering of scenes (`symbol_scene`, catalog scenes, themes), because that changes the
drawing the person looked at. What no longer changes it: `viewer.js`, `viewer.css`, `page.html`, the scene
packing.

## Freshness rule

```text
stale = digest != current record digest
        or (content_sha256 and content_sha256 != current content digest)
        or (not content_sha256 and sheet_sha256 and sheet_sha256 != current sheet SHA-256)
```

A review with neither sheet key keeps the record-digest rule (`records.stale_reviews`), as today.

## Migration rule

`--pin-content` (mutually exclusive with `--accept` and `--revoke`; plan and confirm like them):

- latest review already has `content_sha256`: no write for that record;
- latest review has `sheet_sha256`, the record digest equals the current one, and the sheet SHA-256 equals
  the current sheet's, built with the packaged viewer or with the files of `--viewer DIR`:
  the latest `[[reviewed_by]]` gains `content_sha256` = the current content digest; nothing else changes
  (who, date, version, digest, evidence, sheet_sha256, accepted_codes, fenolite_version, record_sha256);
- any other record with a review (stale, or no `sheet_sha256`): `FEN-4002` naming the record, nothing is
  written; a person reviews it again;
- a record without a review: no write.

`--viewer DIR` reads `page.html`, `viewer.css` and `viewer.js` from DIR and builds the sheet again with
them (`view.export.other_viewer`, a context that swaps the page template; nothing else in the sheet comes
from those files). The scenes, metadata and findings come from the current Fenolite, so a recorded
`sheet_sha256` reproduced this way proves the current content equals the accepted content. Proof on
fenolite-library main (accepted under core e7673c81), with this change on lote-22: with e7673c81's three
viewer files each of the four accepted records reproduces its recorded `sheet_sha256`; the packaged lote-22
viewer gives other sheet bytes, and the content digest is the same under both viewers for all four.

The flag records no human judgement: it narrows an existing acceptance to the content of the file that
acceptance bound byte for byte. So it is not a human step and is not excluded from MCP.

## Decisions

- 2026-11-05: `--sheet HEX` keeps matching the sheet SHA-256 (the file opened); the content digest is not
  typed by people.
- 2026-11-05: `sheet_sha256` is still written on new acceptances, for the record of which file was opened.
- 2026-11-05: no source ids are needed: the change rests on Fenolite's own sheet format.
