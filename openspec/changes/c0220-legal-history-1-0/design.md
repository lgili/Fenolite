## Context

- `tools/residue/scan.py`: modes working tree (default), `--staged` (the hook) and `--history`
  (`history_files`: every blob of `git rev-list --all`). The private gate is on when
  `FENOLITE_RESIDUE_TOKENS(_FILE)` or `FENOLITE_RESIDUE_BLOBS_FILE` give entries; the `Makefile` exports
  both from `private/`, which is never committed.
- CI runs the default mode in `unit` (`ci.yml`), in `wheel` and in `release.yml`; no job runs `--history`.
- Measured on 2026-10-27 on the local `dev` of that day (before the work of c0195 to c0203 was merged): `--history` scanned 10 820 blobs in 10 min 41 s, 0 hits,
  11 waivers, private gate skipped; run again with the private lists of the maintainer's checkout, 0 hits
  with the private gate on.
- `LEGAL.md` (blocks A and B), `LEGAL-ANNEX.md` (the session log), `NOTICE`, `LICENSE`; checked by
  `tests/unit/test_legal_docs.py` (`licensing-and-notices`).
- Extras (`pyproject.toml`): `geo` (shapely, pyclipper), `kicad-ipc` (kicad-python), `oracles` (gerbonara,
  pygerber, and the MCP SDK `mcp` that checks `fenolite mcp`; the `mcp` extra was removed by c0195), `dev`
  (pytest, pytest-xdist, hypothesis, ruff, pyright). Fetched: KiCad
  libraries (`tools/kicad_libs_fetch.py`), the Freerouting jar (`fenolite fetch`), the corpus
  (`tools/corpus_fetch.py`, a licence per manifest row).

## Goals / Non-Goals

**Goals:** a release that cannot publish with a history hit on the public patterns; the maintainer's
private run recorded; an inventory of licences; a review record.

**Non-Goals:** history rewrites; new patterns; legal advice.

## Decisions

1. **Where `--history` runs.** In `release.yml` before the build of the distribution, and in `nightly.yml`
   as a job of its own. In both, the summary line is printed and a hit fails the job. It does not run on
   every push, because 11 minutes is about the time of the `unit` job.
2. **The private run.** `make residue-history` is `uv run python tools/residue/scan.py --history` with the
   two exported variables. The release record of `1.0.0` gets the summary line, which holds only counts, and
   the commit. The release change of `1.0.0` makes this a step of its gate.
3. **The inventory.** `tools/gen_licences.py` reads `uv.lock` (packages by extra) and, for each package,
   the `License-Expression` or `License` field of its distribution metadata from an environment synced with
   every extra. It writes `docs/licences.md` with one table per extra. Packages that are not installed are
   listed with their lock entry and "not inspected". `--check` compares the result with the committed file.
   The copyleft rule reads the table: a GPL, AGPL or LGPL licence in `runtime`, `geo`, `kicad-ipc` or
   `oracles` fails. MPL-2.0 is file-level copyleft and is allowed in `dev` only, where Hypothesis sits;
   it is named in the review.
4. **The review record** is a table: claim, where it is stated, what shows it (a test, a file, a public
   source), and the reviewer's answer. The rows are each numbered statement and each forbidden practice of `LEGAL.md`, the content of
   `NOTICE`, the SPDX rule, the DCO, each fetched asset with its licence and how it is kept out of the
   repository, and the inventory. `tests/unit/test_legal_docs.py` checks that every row has a "shown by"
   that exists.

## Files and public API

| file | content |
|---|---|
| `tools/gen_licences.py` (new) | `inventory(lock, environment) -> Inventory`; writes `docs/licences.md`; `--check` |
| `docs/licences.md` (new) | generated |
| `docs/release/v1.0-legal-review.md` (new) | the review record |
| `Makefile` | `residue-history` |
| `.github/workflows/release.yml`, `nightly.yml` | the `--history` steps |

## Evidence level per behaviour (before merge)

| behaviour | level |
|---|---|
| history scanned in the release and the nightly | mechanical (workflow tests); the first runs show it |
| inventory current, no copyleft in-process | mechanical (`gen_licences.py --check`, a unit test) |
| review recorded | the maintainer's record |

## Risks / Trade-offs

- Package metadata may misstate a licence; the inventory says what the metadata says, and the review row
  names the packages the maintainer checked by hand.

## Open questions

The maintainer accepted every recommended answer below on 2026-10-27 (roadmap, "Open decisions", row 49).

1. Does a lawyer read the review before `1.0.0`? The maintainer's decision; recommended: the project's
   record is enough for an Apache-2.0 project that copies no third-party code, and the decision is recorded. Decided by the maintainer on 2026-10-27: as recommended. No lawyer's
   review is a condition of `1.0.0`; the record says so.
2. A hit of the private gate in history: waiver or rewrite? Recommended: decide per hit, with the rewrite
   reserved for a token of a private project, as `residue-scan` already says for the working tree. Decided by the maintainer on 2026-10-27: as recommended.
