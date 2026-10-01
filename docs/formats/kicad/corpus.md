# KiCad test corpus

`tests/corpus/manifest.toml` lists the public files that the corpus tests read.

- `uv run python tools/corpus_fetch.py --uses rt0 --exclude-uses heavy` fetches them into
  `~/.cache/fenolite/corpus` (override with `FENOLITE_CORPUS_CACHE`).
- Every file is pinned by tag or commit and by SHA-256.
- Nothing from the corpus is committed. Copies derived from it (re-dumped, upgraded or cut out) are
  written only under pytest's temporary directory. `tests/residue/test_derived_corpus.py` flags
  committed copies.

## Origins

| origin | rows | source | licence reading |
|---|---|---|---|
| `kicad-demos` | 18 boards at tag 10.0.6, 6 boards that differ from or are absent at 10.0.6 at tag 9.0.9.1, and one schematic, symbol library, footprint, footprint-library table and worksheet at 10.0.6 | S-0024, S-0026 | see "Licence reading" below |
| `third-party` | 3 boards (formats 20221018 ×2 and 20171130) | S-0027, S-0028 | `license = "Apache-2.0"` from each repository's `LICENSE` file |

Licence reading for the `kicad-demos` rows:

- `license = "CC-BY-SA-4.0"` comes from the repository notice (S-0023).
- A folder licence file, where one exists, is recorded in `license_variant` (S-0025): Apache-2.0,
  CERN-OHL-S-2.0, CERN-OHL-P-2.0 or CC-BY-SA-4.0.
- The folder whose licence has a non-commercial clause is not listed, at either tag.

Every row is `embeddable = false`, so these files are measurement material only.

## Uses

| use | meaning |
|---|---|
| `rt0` | parsed and re-dumped by `tests/corpus/test_rt0.py` |
| `oracle` | a board that `tests/kicad/test_rt0_oracle.py` loads and upgrades with `kicad-cli` |
| `heavy` | a file over 20 MB; excluded from CI and from local runs unless `FENOLITE_HEAVY=1` |
| `malformed` | published malformed; the parser must keep rejecting it with the rule named in `notes` |

## Format versions

These are the versions of the cached files, as of 2026-10-01:

| origin, tag | format versions (`version` of the root list) |
|---|---|
| `kicad-demos` 10.0.6 boards | `20241229` (13 boards), `20260206` (1), `20250513` (1, a 9.99 development write), `20241030` (1, an 8.99 development write), two heavy boards not counted |
| `kicad-demos` 9.0.9.1 boards | `20241229` (6) |
| `kicad-demos` 10.0.6 other kinds | schematic `20250114`, symbol library `20241209`, footprint `20241229`, footprint-library table `7`, worksheet without a version list |
| `third-party` | `20221018` (2), `20171130` (1) |

## Notes on the content

- Only one demo board is in 10.0 format. Typed 10.0 measurements therefore use copies upgraded with
  `kicad-cli pcb upgrade --force` inside the test's temporary directory.
- The `20171130` third-party board is a KiCad 5 file. It is for RT0 only: typed readers accept 8.0
  and newer (c0007, c0008).
- One demo board at tag 9.0.9.1 (`kicad-demo-9-0-9-1-pcb-04`) is published malformed:
  - A spliced line closes the root list at byte 14111.
  - The parser rejects it with `content after the root list`.
  - `kicad-cli` 10.0.6 loads it (exit 0) and silently ignores the remaining 3.5 MB.
  - It is listed as `malformed`, and it is the reason the rule exists (`H-K-SEXPR-STRICT`).
- Number census (`H-K-SEXPR-NUM-CORPUS`, `tests/corpus/test_rt0.py::test_number_census`):
  - Exponent atoms appear only in the `20171130` third-party board (7).
  - Atoms with more than 6 decimals appear in `20241229` demo boards (11), the `20250513` board (2),
    the worksheet (27) and the `20171130` board (1).
- Naming rule: vendor, product and project names appear only inside manifest URLs and in
  `docs/evidence/sources.md`. Ids follow
  `kicad-demo-<tag>-<kind>-NN` / `third-party-<kind>-NN`. Notes, this page and test output name rows
  by id, tag, format version and licence only.
- Local fetches: some macOS Python installs cannot verify HTTPS certificates; the `uv` Python can.
  CI runs on Ubuntu.

## CI

- The `kicad-10` job in `.github/workflows/ci.yml` runs the oracle and corpus tests inside
  `kicad/kicad:10.0.6`, pinned by digest (S-0029), with `FENOLITE_REQUIRE=kicad,corpus`.
- First green run: pending; the job has not run on GitHub yet.
