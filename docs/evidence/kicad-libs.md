# KiCad library census

Counts from `tests/libs/` (`needs_libs`, `slow`) over the official KiCad libraries of the local
KiCad 10.0.6 install (macOS; source `install-10`). The run took place on 2026-10-01, with
`FENOLITE_CENSUS_OUT` naming a temporary file. Only counts are recorded here, never library content.
The libraries are CC-BY-SA 4.0 as a collection (S-0048) and are never committed. Three sampled install
files were byte-identical to tag 10.0.6 of the source repository (S-0018); the whole-tree comparison of
change c0021 is recorded below ("Install against its pin").

These numbers are supporting data for `H-K-LIB-READ`. They are not a round trip: the readers stay
`INFERRED` until a writer change can re-emit what they read.

## Reading (`test_official_read.py`)

| count | footprints | symbols |
|---|---|---|
| libraries | 155 `.pretty` folders | 223 `.kicad_sym` files |
| items | 15 450 | 22 860 (12 318 derived) |
| read errors | 0 | 0 |
| pads / pins equal to the `pad` / `pin` nodes of the tree | yes (386 597 pads) | yes (541 758 pins as written, 806 385 after flattening) |
| ids unique within each library | yes | yes |
| every `extends` parent found | — | yes |
| graphics modelled | 650 491 | — |
| `kicad.lib.kept-opaque` infos | 1 059 | 0 |
| other reader issues | 0 | 0 |
| 3D model references | 14 849 | — |
| power symbols | — | 102 `global`, 0 `local` |
| units with body style 0 | — | 2 000 |
| alternate pin functions | — | 876 223 |
| time | 78 s | 63 s |

Further observations:

- **Arcs inside `pts`.** 3 footprints have an `arc` inside the `pts` of an `fp_poly` or of a custom
  pad's `gr_poly`. This is supporting data for `H-G-PTS-ARC`.
- **Repeated uuids.** 22 footprints in 13 libraries carry the same uuid on more than one graphic
  of one file. The id rule therefore gives a repeated uuid an occurrence suffix (`docs/design-model.md`).

## Resolution (`test_official_resolve.py`)

The resolver used an empty configuration folder, so the template tables of the install apply.

| count | value |
|---|---|
| footprint / symbol rows (origin `template`) | 155 / 223 |
| table issues | 0 |
| `Device:R` and `Resistor_SMD:R_0603_1608Metric` | resolved |
| symbols whose `Footprint` property was resolved | 18 103 |
| symbols with an empty `Footprint` property | 4 725 |
| `Footprint` properties that fail, by code | `kicad.lib.missing-entry` 32; no `unknown-nickname`, no `invalid-id` |
| 3D model references / `kicad.lib.missing-3d-model` warnings | 14 849 / 7 324 (none from an unresolved variable) |

The 7 324 missing models agree with the design's observation that nearly half of the official model
references do not resolve on a local install (S-0018).

## Fetched trees (change c0021)

`tools/kicad_libs_fetch.py` fetched the four pinned trees on 2026-10-03 from the commit archives of
`gitlab.com/kicad/libraries` (S-0042, S-0043, S-0096). A second fetch of each commit gave the pinned tree
hash again. Numbers only; no library file is in the repository.

| tag | repository | commit | archive bytes | files | tree bytes |
|---|---|---|---|---|---|
| 10.0.6 | `kicad-footprints` | `819223b66f96` | 12 112 124 | 15 514 | 155 992 317 |
| 10.0.6 | `kicad-symbols` | `7800d91437ce` | 11 928 106 | 22 871 | 232 951 542 |
| 9.0.9 | `kicad-footprints` | `2b941bf1d978` | 12 007 795 | 15 479 | 153 378 380 |
| 9.0.9 | `kicad-symbols` | `ad36cd14bcd1` | 10 807 671 | 233 | 222 167 510 |

The archive sizes are those GitLab served on that day; only the commit, the tree hash and the file count
are pinned, because the archive is generated on request. The 10.0.6 symbol tree holds 22 871 files
because it stores each library as a `.kicad_symdir` folder; the 9.0.9 tree holds one file per library.

## Census of the fetched trees (change c0021)

The same tests ran on 2026-10-03 over three sources: the local install (`install-10`) and the two verified
caches, `cache-10` (tag 10.0.6) and `cache-9` (tag 9.0.9). The cache sources have no table, so their rows
come from the directory scan (origin `scan`). `install-10` and `cache-10` give the same counts in every
row.

| count | `install-10` | `cache-10` | `cache-9` |
|---|---|---|---|
| footprint libraries / footprints | 155 / 15 450 | 155 / 15 450 | 155 / 15 415 |
| symbol libraries / symbols | 223 / 22 860 | 223 / 22 860 | 223 / 22 583 |
| symbol files read | 223 | 22 860 (one per symbol, in `.kicad_symdir` folders) | 223 |
| read errors, footprints / symbols | 0 / 0 | 0 / 0 | 0 / 0 |
| pads | 386 597 | 386 597 | 385 640 |
| pins as written / after flattening | 541 758 / 806 385 | 541 758 / 806 385 | 540 381 / 803 236 |
| derived symbols | 12 318 | 12 318 | 12 127 |
| graphics modelled | 650 491 | 650 491 | 649 677 |
| `kicad.lib.kept-opaque` infos (footprints) | 1 059 | 1 059 | 1 043 |
| 3D model references | 14 849 | 14 849 | 14 816 |
| footprints with an arc inside `pts` | 3 | 3 | 2 |
| footprints / libraries with a repeated uuid | 22 / 13 | 22 / 13 | 22 / 13 |
| power symbols `global` / `local` | 102 / 0 | 102 / 0 | 102 / 0 |
| units with body style 0 | 2 000 | 2 000 | 1 969 |
| alternate pin functions | 876 223 | 876 223 | 876 081 |
| row origin (footprint / symbol rows) | `template` (155 / 223) | `scan` (155 / 223) | `scan` (155 / 223) |
| table issues | 0 | 0 | 0 |
| `Footprint` properties resolved / empty | 18 103 / 4 725 | 18 103 / 4 725 | 17 844 / 4 706 |
| `Footprint` properties that fail (`kicad.lib.missing-entry`) | 32 | 32 | 33 |
| `kicad.lib.missing-3d-model` warnings | 7 324 | 14 849 | 14 816 |

A cache holds no 3D models and defines no `KICAD<M>_3DMODEL_DIR`, so every model reference of a cache
source is a warning from an unresolved variable. On the install, none is.

### Install against its pin (`test_install_pin.py`)

| compared | equal | different | only in the install | only in the cache |
|---|---|---|---|---|
| footprint files (`<X>.pretty/<Y>.kicad_mod`), by bytes | 15 450 | 0 | 0 | 0 |
| symbol libraries, by the multiset of flattened definitions | 223 | 0 | 0 | 0 |

Every count other than "equal" is 0, so the footprints and symbols of the local 10.0.6 install equal tag
10.0.6 of the source repositories at the pinned commits. The install packs each `.kicad_symdir` folder
into one file; in 42 libraries the packed file lists the symbols in another order than the sorted file
names of the folder, which is why the comparison ignores order.

### Directory scan against the template tables (`test_scan_matches_template`)

| source | kind | template rows | scanned rows | only in template | only in scan | nickname differs from stem | `disabled` or `hidden` |
|---|---|---|---|---|---|---|---|
| `install-10` | footprint | 155 | 155 | 0 | 0 | 0 | 0 |
| `install-10` | symbol | 223 | 223 | 0 | 0 | 0 | 0 |
| `cache-10` | footprint | 155 | 155 | 0 | 0 | 0 | 0 |
| `cache-10` | symbol | 223 | 223 | 0 | 0 | 0 | 0 |
| `cache-9` | footprint | 155 | 155 | 0 | 0 | 0 | 0 |
| `cache-9` | symbol | 223 | 223 | 0 | 0 | 0 | 0 |

The template tables compared are the install's `template/` tables and, for a fetched tree, the
`fp-lib-table` and `sym-lib-table` at its top. These
counts are supporting data for `H-K-LIB-SCAN`, which stays `INFERRED`: the official libraries are one
origin.

## Fetched 3D models (change c0116)

The first real fetch of official 3D models, made on 2026-10-08 with the maintainer's consent, given in his
own chat on 2026-10-08 (task 6.3 of c0116). `examples/blink_official/design.py` was built for targets 9 and
10 against the verified library caches of tags 9.0.9 and 10.0.6 (`FENOLITE_LIBS_CACHE`, fetched the same
day with `tools/kicad_libs_fetch.py`), and `uv run python tools/kicad_libs_fetch.py --models
<board>.kicad_pcb` fetched the models each board names, one file at a time, from `kicad-packages3D` at the
pinned commits of `data/libraries.toml` (S-0700, S-0701). Both runs exit 0 with every line `fetched`; a
second run of each gives every line `cached`. `fenolite models` on the board of target 10 then locates the
three paths with source `cache` and none `missing`. Only names, sizes and digests are recorded here; the
models are CC-BY-SA 4.0 with the library exception (S-0048) and stay in the cache.

| tag | file under `kicad-packages3D/` | bytes | SHA-256 |
|---|---|---|---|
| 9.0.9 | `LED_THT.3dshapes/LED_D3.0mm.step` | 24 358 | `e83c2186ad887c36d869f44e28c7b80646ea10cb388697b4380f5a2777268371` |
| 9.0.9 | `Package_QFP.3dshapes/LQFP-32_7x7mm_P0.8mm.step` | 422 757 | `be0e412f1c66fee70039b0e109e0cc7c823161dda97593718afa97569bc61ce3` |
| 9.0.9 | `Resistor_SMD.3dshapes/R_0603_1608Metric.step` | 40 618 | `1875571c326d0d9e96f36b4efeb8094068ef7619f0a449c781caf0b49c2e5861` |
| 10.0.6 | `LED_THT.3dshapes/LED_D3.0mm.step` | 24 358 | `e83c2186ad887c36d869f44e28c7b80646ea10cb388697b4380f5a2777268371` |
| 10.0.6 | `Package_QFP.3dshapes/LQFP-32_7x7mm_P0.8mm.step` | 422 757 | `be0e412f1c66fee70039b0e109e0cc7c823161dda97593718afa97569bc61ce3` |
| 10.0.6 | `Resistor_SMD.3dshapes/R_0603_1608Metric.step` | 40 618 | `1875571c326d0d9e96f36b4efeb8094068ef7619f0a449c781caf0b49c2e5861` |

The three files are byte-equal at the two commits. The board of target 9 names them under
`${KICAD9_3DMODEL_DIR}` and that of target 10 under `${KICAD10_3DMODEL_DIR}`, as the official footprints of
each tag write them. Each file kept its size and its SHA-256 from the `HEAD` request of the files API, which
is what `H-G-MODELS-FETCH` states.

## Not measured here

- The `env` source (folders named by `KICAD10_*` variables) uses the same tests. It was not run: the
  cache sources read the same trees.
- No KiCad 9 install was compared with its pin: only a 10.0.6 install is available locally. The `kicad-9`
  image is not compared either, because the census does not run in CI.
- 3D model files are not fetched (`kicad-packages3D` is not pinned), so model resolution is measured on
  the install only.
