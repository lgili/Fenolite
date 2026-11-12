# c0504: small fixes found editing an Altium board

Found on: editing a private two-layer power board with `fenolite.backends.altium.edit` and the CLI on 2026-11-11
(codes only; nothing from the board is in this change).

## Why

Five small defects, by failure id. One of them is dropped (below).

- **F33, a stale pour cannot be dropped.** After an edit that moves copper through a polygon, the polygon's
  saved pour is wrong until Altium repours it. The session removes a polygon's pour only inside `set_outline`
  (`ops._poured`). The script reached that through `s._queue(..., lambda st: [st.remove(k, v) for k, v in
  ops._poured(st, i).items()])`. c0463 makes the computed pour of a conversion right. It does not cover an edit
  session on a saved document.
- **F46, an inherited integrity finding blamed on the edit.** `session.verify` drops the integrity findings
  the source already had by comparing `(code, message)`. The message of `altium.integrity.subpoly-gap` holds
  the `Regions6` positions of the pieces (`integrity.subpoly_gaps`). Any edit that removes or inserts a region
  before them changes the message. The source's gap then comes back as a new `altium.edit.integrity` warning on
  a polygon the edit did not touch.
- **F47, a degree sign in a component description.** The description failed with a refusal that named the
  Windows-1252 code page. On dev, `ascii.text_problem` accepts `°` (U+00B0) in the binary form only, and only
  the comment and parameter values may use the binary form ("Text outside ASCII"). It refuses `℃` (U+2103, the
  one-character degree Celsius that datasheets often hold) in every form: "outside Windows-1252, which no form
  carries". `binary.frame_record` writes a description through `record_bytes` without that check, and writes
  `℃` as `?` with no warning (`errors="replace"`). An edit session's `records._encode` raises `RecordError` for
  it, outside `Refused`. So `Session.apply` does not catch it, and the commit fails with `FEN-1001`.
- **F41, no tidy findings for jogs, off-45° corners and collinear points.** The style report
  (`tidy.style`, capability copper-tidy, "Style report") counts jogs and `other` joints per class and layer. It
  gives a finding with a place only for an acute joint (`tidy.acute`). It does not count a joint of two collinear
  tracks, a redundant point. `fenolite tidy --report` reads a KiCad board only (`cmd_tidy` calls `resolve_board`),
  so the Altium board of the field could not be checked at all.

**Dropped: F45 (`--timestamp` and `--seed` after the subcommand).** It does not reproduce on dev at b4234f24a,
nor on `main`. `main._add_global_options` adds both options to every subparser (`top_level=False`). Each of these
runs exits 0:

- `fenolite inspect <doc> --timestamp 2026-01-01T00:00:00Z --seed 1 --json`;
- the same with `=` forms;
- `fenolite convert <doc> --to kicad --out <dir> --dry-run --seed 1 --timestamp 2026-01-01`;
- `fenolite check <doc> --stages altium.integrity --seed 1 --timestamp …`;
- `fenolite.api.run("inspect", <doc>, "--seed", "1", …)`.

`FEN-2001` comes only from a bad value, for example `--seed abc` ("argument --seed: invalid int value"). The
field run probably passed one. Nothing to change.

## What Changes

- **F33.** `Session.unpour(Polygon(name))` removes the polygon's poured primitives from every storage, as
  `set_outline` does. Gate `unpour`, on `H-A-EDIT-SHAPE`. `verify` gives `altium.edit.pour-stale` (warning) for
  each poured polygon of a layer whose copper the session changed inside the polygon's outline box, and the hint
  names `Session.unpour` (design D1).
- **F46.** `verify` and `integrity` compare findings by a key that an edit does not move: the code and the
  identity of the records named (the polygon's name and pour index, the missing sub-indices), not their positions.
  Findings the source already held go to a single `altium.edit.integrity-inherited` (info) with their count and
  codes. An inherited finding on a polygon the session edited stays inherited (design D2).
- **F47.**
  - A character outside Windows-1252 whose compatibility form (Unicode NFKC) fits the code page is written as
    that form, for example `℃` as `°C`, with `altium.text-folded` (warning) naming the field and both texts.
  - A component description joins the texts that may hold Windows-1252 characters in the binary form.
  - `record_bytes` no longer writes `?` silently: a character that neither fits nor folds is refused with the
    reason of `text_problem`.
  - The edit session's `records._encode` follows the same rule, and refuses with `altium.edit.assertion` instead
    of raising (design D3).
  - Task 1.1 first reproduces both strings on dev and records which path refused which. Any path that already
    passes is not changed.
- **F41.**
  - `tidy.style` gives `tidy.jog`, `tidy.off-45` and `tidy.collinear` (info) at their places, and counts
    `collinear` joints in the report.
  - `fenolite tidy --report` reads any board a `BoardFrame` backend reads, an Altium `.PcbDoc` included, through
    the resolver c0495 gives `_boardview.load_board`.
  - The tidy steps (prune, straighten, chamfer) stay KiCad-only (design D4).

## Impact

- F33, F46: `src/fenolite/backends/altium/edit/ops.py` (`unpour`, built on `_poured`), `edit/session.py`
  (`OPERATIONS`, `ROWS`, `GATES`, `unpour`, `verify`, `EDIT_ISSUE_CODES`) and `edit/integrity.py` (a `key` per
  finding). `docs/evidence/altium-edit.md` gets one Part J case for `unpour`.
- F47: `src/fenolite/backends/altium/ascii.py` (`text_problem`, `record_bytes`, a `fold` helper),
  `edit/records.py` (`_encode`) and the description writers (`schlib.component_record`, the drawn sheet).
- F41: `src/fenolite/tidy/style.py`, `tidy/codes.py`, `cli/cmd_tidy.py`. Depends on c0495 (b) for the board
  resolver.
- `cli/data/explain.toml`, the agent guide page that lists check and tidy codes, `CHANGELOG.md`.
