## MODIFIED Requirements

### Requirement: Review record
`fenolite library review TARGET --accept --reviewer NAME --sheet HEX` SHALL write, through plan and confirm, a `[[reviewed_by]]` table (who, date, digest, sheet_sha256, content_sha256, fenolite_version, previous_evidence, accepted_codes) into each target record and set `evidence` to `CORPUS-VERIFIED`. `content_sha256` MUST be the content digest of the sheet the reviewer named. `--revoke` MUST remove the table and restore `previous_evidence`. Without either flag the command MUST only report the review state.

#### Scenario: Accept a clean device
- **GIVEN** a device with no error finding and evidence `UNVERIFIED`
- **WHEN** `library review` runs with `--accept --reviewer jdoe --sheet <12 hex of its sheet> --timestamp 2026-11-02T00:00:00Z --confirm`
- **THEN** the record holds `evidence = "CORPUS-VERIFIED"` and a `[[reviewed_by]]` with `who = "jdoe"`, `date = "2026-11-02"`, `previous_evidence = "UNVERIFIED"` and the sheet's `content_sha256`, and the receipt lists the file

#### Scenario: Revoke
- **WHEN** `--revoke --confirm` runs on that record
- **THEN** the record equals its state before the review

### Requirement: Stale reviews
The review digest SHALL be the SHA-256 of the canonical JSON of the record without `evidence` and `reviewed_by`, of its generated definitions and, for a device, of its pin table and package digests. The content digest SHALL be the SHA-256 of the canonical JSON of what a sheet shows: its embedded scene data with every scene unpacked, and its review section (record id, metadata, findings, visual-diff payloads) with iframe `srcdoc` copies emptied; the viewer page, styles and script MUST NOT be part of it. `library.review-stale` (error) MUST fire when the review digest differs, or when the review holds `content_sha256` and the content digest differs, or when the review holds `sheet_sha256` and no `content_sha256` and the sheet digest differs. Reformatting MUST NOT change either digest, and a change of the viewer assets alone MUST NOT make a review with `content_sha256` stale.

#### Scenario: Edit after review
- **GIVEN** a reviewed pin table
- **WHEN** one pin name is changed and the table is checked
- **THEN** one `library.review-stale` is reported and `effective_evidence` is the review's `previous_evidence`

#### Scenario: Reformatting is not an edit
- **WHEN** the reviewed table is rewritten with other whitespace and key order and checked
- **THEN** no `library.review-stale` is reported

#### Scenario: A viewer change is not an edit
- **GIVEN** a record accepted with `content_sha256`
- **WHEN** the packaged viewer page, `viewer.css` or `viewer.js` changes and the record is checked
- **THEN** the sheet digest differs, the content digest is equal and no `library.review-stale` is reported

#### Scenario: An acceptance written before content digests
- **GIVEN** a record accepted with `sheet_sha256` and no `content_sha256`
- **WHEN** it is checked with an unchanged sheet, and again after its sheet bytes change
- **THEN** the first check reports it accepted and the second reports `library.review-stale`

## ADDED Requirements

### Requirement: Pinning the content of an older acceptance
`fenolite library review TARGET --pin-content [--viewer DIR]` SHALL, through plan and confirm, add `content_sha256` (the current content digest) to the latest `[[reviewed_by]]` table of each target whose latest review has `sheet_sha256` and no `content_sha256`, and only while its review digest equals the current one and its sheet digest equals the current sheet's, built with the packaged viewer or, with `--viewer DIR`, with the `page.html`, `viewer.css` and `viewer.js` held in DIR; every other key and the evidence MUST stay unchanged. A record whose latest review already has `content_sha256`, or that has no review, MUST be left unchanged. A record whose older acceptance is stale or holds no `sheet_sha256` MUST make the command exit 4 with `FEN-4002` and write nothing. `--pin-content` MUST be exclusive with `--accept` and `--revoke`; `--viewer` without `--pin-content` MUST exit 2 with `FEN-2001`, and a DIR without the three files MUST exit 3 with `FEN-3001`.

#### Scenario: Pin a fresh older acceptance
- **GIVEN** a record accepted with `sheet_sha256` and no `content_sha256`, whose sheet is unchanged
- **WHEN** `library review RECORD --pin-content --confirm` runs
- **THEN** the review gains the current `content_sha256`, its other keys and the record's evidence are unchanged, and a later viewer-only change does not make it stale

#### Scenario: Pin an acceptance written by an older viewer
- **GIVEN** a record accepted with `sheet_sha256` by a Fenolite whose viewer files differ from the packaged ones, and unchanged since
- **WHEN** `library review RECORD --pin-content --viewer <that Fenolite's src/fenolite/view/static> --confirm` runs
- **THEN** the sheet built with those files has the recorded `sheet_sha256`, and the review gains the current `content_sha256`

#### Scenario: A stale older acceptance is not pinned
- **GIVEN** a record accepted with `sheet_sha256` whose sheet bytes changed since
- **WHEN** `library review RECORD --pin-content --confirm` runs
- **THEN** it exits 4 with `FEN-4002` naming the record and writes nothing
