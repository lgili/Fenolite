# c0415: review acceptances pin the reviewed content, not the viewer

## Why

A `[[reviewed_by]]` acceptance holds `digest` (the record's content digest) and `sheet_sha256`, the SHA-256
of the whole review sheet. `library check` reports `library.review-stale` when either differs.

The sheet is a standalone viewer page: `page.html` with `viewer.css` and `viewer.js` inlined, plus the
embedded scene data, the record metadata and the findings. So any change to the viewer assets changes
every sheet's bytes and makes every acceptance stale, even when the reviewed records are byte-identical.

This happened in fenolite-library PR 3: after the core moved from e7673c81 to 3675515a, four accepted
records went stale and had to be renewed by hand, although nothing the reviewer saw had changed.

## What

- **Content digest.** `library.review.content_digest(sheet)` hashes what a sheet shows: the scene data it
  embeds (unpacked, so independent of the packing and of the page code), the review section (title,
  metadata, findings) and the visual-diff payloads. Viewer assets and iframe `srcdoc` copies of the page
  are not part of it. It is computed from the sheet bytes, so it always describes the file the reviewer
  opened, and anyone holding a sheet file can recompute it.
- **Acceptance.** `library review --accept` also writes `content_sha256` into the new `[[reviewed_by]]`
  table. `--sheet HEX` still names the sheet file (its SHA-256 prefix) that the person opened.
- **Freshness.** A review with `content_sha256` is stale when the record digest or the content digest
  differs; its `sheet_sha256` stays as a record of the file that was opened, and no longer counts.
  A review without `content_sha256` (written before c0415) keeps today's rule: stale when the record digest
  or the sheet bytes differ. So every existing acceptance verifies exactly as before.
- **Migration.** `library review TARGET... --pin-content` adds `content_sha256` to an existing acceptance
  in place, and only while that acceptance still verifies byte for byte (record digest and sheet SHA-256
  equal). At that moment the current sheet is the file the person accepted, so its content digest is what
  they reviewed. Who, date, evidence and every other key stay as they are. A stale legacy acceptance is
  refused (`FEN-4002`) and needs a new human review.
- **Older viewers.** An acceptance written by an earlier Fenolite binds that version's viewer bytes, so the
  packaged viewer no longer reproduces its sheet. `--viewer DIR` names the three viewer files of the
  Fenolite that wrote it (its `src/fenolite/view/static`): the sheet is built again with them, and the pin is
  added only when that sheet has the recorded `sheet_sha256`. Equal bytes prove that the content shown now
  is the content that was accepted.
- **Reports.** `library check` / `library review` rows give `sheet.content_sha256`; `sheets.json` items
  give `content_sha256`.

All additions are optional keys and one new flag; no existing key changes meaning for existing records.

## Impact

- `src/fenolite/library/review.py`, `src/fenolite/cli/_library_check.py`, `src/fenolite/catalog/records.py`,
  `src/fenolite/cli/file_formats.py`; regenerated schemas, CLI surface and agent guide.
- Docs: `docs/library-rules.md`, `docs/library-ci.md`, agent guide page `library-review.md`.
- fenolite-library: once its pinned core includes c0415, `library review ... --pin-content` upgrades the
  current acceptances; no human re-review is needed while their sheets still match.
