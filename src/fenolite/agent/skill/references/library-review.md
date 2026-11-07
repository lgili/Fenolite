---
topic: library-review
title: Checking library records and human reviews
summary: Check library records, compare revisions and prepare deterministic sheets for a person's review.
---

# Checking library records and human reviews

Check records, record folders and plain KiCad or Altium libraries. Each item lists `rules_run`,
findings, `effective_evidence` and its review state. Rules and generic geometry are `INFERRED`.

```fenolite-cmd
fenolite library check data --json
fenolite library check data --fail-on warning --rules library.pin-grid,library.pad-count --skip library.pin1-marker --json
fenolite library check data --compare base/data --sheets review --dry-run --json
fenolite library review data/record.toml --json
```

Error findings exit 5; `--fail-on warning` also fails on warnings. Correct the source record and check
again. An unusual item may use `[[waiver]]` with `code` and a reason; the waived finding stays visible
as info. Unused waivers warn. Evidence claims, malformed records and stale reviews cannot be waived.
`library.pin-order` means the land is the part's mirror image: mirror the record, do not waive it, unless
the reason names the S- or D- source that numbers the part clockwise.

```fenolite-cmd
fenolite explain library.pin-order --json
```
Device evidence is the weakest current label of the device, pin table and package.

Review `result.plan`, then confirm its `plan_id`. `review/index.html` links standalone sheets and
`review/sheets.json` holds their hashes. A comparison sheet shows the old/new visual overlay and field
paths. Its `review_sha256` is the base content hash; its `sha256` covers the complete artefact.
The sheet shows prepared content. `library review` reports live reviewer, date and freshness.

Acceptance and revocation are human steps. An agent never runs them unless the person names themselves
as reviewer and has opened the base sheet. They are excluded from MCP and rejected at runtime.

```fenolite-cmd
fenolite library review data/record.toml --accept --reviewer reviewer-name --sheet 0123456789ab --timestamp 2026-11-01T00:00:00Z --dry-run --json
fenolite library review data/record.toml --revoke --dry-run --json
```

A person accepts records individually using at least 12 hex digits of the current sheet hash, and
confirms the reviewed plan. Errors block acceptance; a changed sheet gives `FEN-4002`. The record gains
a scoped `CORPUS-VERIFIED` review. A later content edit makes it stale and restores its previous
effective evidence; reformatting alone does not. Revocation restores the prior evidence label.
CI checks and publishes sheets; it never accepts a review.

The review pins `content_sha256`: the drawings, data and findings the sheet shows, not the viewer code.
A Fenolite upgrade that only changes the viewer keeps it accepted. An older review without
`content_sha256` stays bound to the sheet bytes; while those still match, `--pin-content` adds the
content digest to it without a new human review. For a review written by an older Fenolite, pass its
viewer files (`src/fenolite/view/static` of that version) with `--viewer`. A stale one gives `FEN-4002`:
ask the person again.

```fenolite-cmd
fenolite library review data/record.toml --pin-content --dry-run --json
fenolite library review data/record.toml --pin-content --viewer old/src/fenolite/view/static --dry-run --json
```

Read next: `footprints`, `library-items`, `checks`.
