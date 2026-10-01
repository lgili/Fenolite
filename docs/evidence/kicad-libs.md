# KiCad library census

Counts from `tests/libs/` (`needs_libs`, `slow`) over the official KiCad libraries of the local
KiCad 10.0.6 install (macOS; source `install-10`). The run took place on 2026-10-01, with
`FENOLITE_CENSUS_OUT` naming a temporary file. Only counts are recorded here, never library content.
The libraries are CC-BY-SA 4.0 as a collection (S-0048) and are never committed. Three sampled install
files were byte-identical to tag 10.0.6 of the source repository (S-0018), but whole-tree identity is
not claimed.

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

## Not measured here

- The 9.0.9 libraries and a fetched 10.0.6 tree belong to the follow-up change, which adds a fetched
  library cache.
- The `env` source (folders named by `KICAD10_*` variables) uses the same tests. It was not run,
  because only the install is available locally.
