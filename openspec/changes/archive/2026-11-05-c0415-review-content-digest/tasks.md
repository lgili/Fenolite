# Tasks: c0415

## 1. Content digest

- [x] 1.1 `library.review.content_digest(sheet)` and the freshness rule in `is_stale`; unit tests: a changed
  template keeps the content digest and changes the sheet digest; a changed metadata block, finding or scene
  changes it; a comparison sheet's iframe copy is ignored.

## 2. Records and reports

- [x] 2.1 `Review.content_sha256` (parsed, validated as a 64-hex digest, written); `library review --accept`
  writes it; rows and `sheets.json` report it.
- [x] 2.2 `library check` uses the content digest for reviews that have one and the sheet digest for older
  ones; tests: an accepted record stays accepted when the viewer template changes; a legacy acceptance
  still verifies and still goes stale on a sheet change.

## 3. Migration

- [x] 3.1 `library review --pin-content`: pins a byte-fresh legacy acceptance in place, leaves pinned ones,
  refuses stale ones with `FEN-4002`; tests.
- [x] 3.2 `--viewer DIR`: the sheet built with an older Fenolite's viewer files reproduces the recorded
  `sheet_sha256` before a pin; tests; proof on fenolite-library main's four accepted records.

## 4. Docs and generated files

- [x] 4.1 `docs/library-rules.md`, `docs/library-ci.md`, agent guide `library-review.md` with a tested
  `--pin-content` line; `tools/gen_schemas.py --check`, `tools/gen_cli_surface.py --check`,
  `tools/gen_agent_guide.py --check`; `CHANGELOG.md`.

## Proof (2026-11-05)

- Focused tests through `fenolite-heavy` (`-n 2`): library review CLI, review sheet, review freshness, agent
  guide pages, MCP, explain, library rules, build library records and the viewer tests: 728 passed, 1
  skipped (MCP SDK oracle extra). Catalog, library, CLI surface, file and result schemas, schema drift and
  tools tests: 1678 passed, 1 skipped (library checkout not set); the kit-manifest schema test needed the
  `geo` extra in the fresh venv and passes with it.
- `tools/gen_schemas.py --check` (frozen v0 receipt updated for the additive keys of
  `fenolite.library.v0` and `fenolite.device.v0`), `tools/gen_schemas.py --formats --check`,
  `tools/gen_cli_surface.py --check`, `tools/gen_agent_guide.py --check`: exit 0.
- fenolite-library main (4 records accepted under core e7673c81, copied to a scratch folder): `library check`
  with this change reports all four stale (viewer bytes); `--pin-content` without `--viewer` exits 4
  (`FEN-4002`); with e7673c81's `src/fenolite/view/static` it exits 0 and pins each review (who and date
  unchanged); `library check` then exits 0 with all four accepted under the lote-22 viewer.
