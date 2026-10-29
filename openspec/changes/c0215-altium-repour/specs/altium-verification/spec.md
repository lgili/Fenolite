## ADDED Requirements

### Requirement: Kit group K6 for computed pours
The kit SHALL hold the samples `pour` (two copper layers) and `pour4` (four copper layers with blind and buried vias and through-hole pads with inner shapes), built from `examples/kit/pour/design.py` and `examples/kit/pour4/design.py`, each written twice from one computation: `<sample>/computed/<sample>.PcbDoc` with the pour mode `computed`, and `<sample>/reference/<sample>.PcbDoc`, the same document without the regions of its polygons (`pour_regions=False`). Each probe of the design of change c0215 (P0 to P10) MUST be its own polygon on its own net and MUST declare its points where copper must stay or must be gone. `fenolite.verify.kit.steps.STEPS` SHALL gain these steps in group 6, after K6.1, which stays as it is; the kit MUST build `routed` with the pour mode `outline`, so that K6.1 still repours an unpoured board:

| step | sample | what | kind | checks or expected value |
|---|---|---|---|---|
| K6.2 | pour | rebuild every polygon of `reference/` in the Polygon Manager and save | file | `repoured`, `pour-match` |
| K6.3 | pour | Tools » Polygon Pours » Repour All on `reference/` by hand and save | file | `repoured`, `pour-same` with K6.2 |
| K6.4 | pour | open `computed/` and save it without a repour | file | `resave`, `pour-kept` |
| K6.5 | pour | the number of polygons of `computed/` that the Polygon Pour Manager lists as needing a repour | form, int | 0 |
| K6.6 | pour | the number of violations of Design » Design Rule Check on `computed/` that name a polygon | form, int | 0 |
| K6.7 | pour | Force Repour All on `computed/` and save | file | `repoured`, `pour-match`, `pour-same` with K6.2 |
| K6.8 | pour | whether `PCB.Polygon.AdvancedPour` is off | form, bool | true |
| K6.9 | pour4 | as K6.2 | file | `repoured`, `pour-match` |
| K6.10 | pour4 | as K6.4 | file | `resave`, `pour-kept` |
| K6.11 | pour4 | as K6.7 | file | `repoured`, `pour-match`, `pour-same` with K6.9 |

- Every K6 step is manual: each that leaves a board ends in a save under a new name, which no public page names a call for (`script.NOT_SCRIPTED`). The pour samples are free documents (no project), so no step of theirs runs `parity`; `resave` is not a check of K6.2 and K6.9, whose saved board joins nets through the pour that the unpoured `reference/` leaves apart.
- `repoured`: every polygon that its probe declares non-empty holds regions, the sentinel P0 among them; otherwise the step fails with "the repour did not run".
- `pour-match`: `pourcompare.compare_pours` of the saved board against Fenolite's computed pour of the same sample passes M1 to M5 for every polygon.
- `pour-same`: the saved board against the board of the named step passes M1 to M4.
- `pour-kept`: the regions of every polygon of the saved board equal those Fenolite wrote within one unit.
- The steps MUST name the hypotheses of the design of change c0215 that they settle: K6.2, K6.7, K6.9 and K6.11 `H-A-POUR-KIT`; K6.3 `H-A-POUR-SCRIPT`; K6.4, K6.5, K6.6 and K6.10 `H-A-POUR-OPEN` and `H-A-POUR-REGION`; K6.8 `H-A-POUR-ENGINE`.
- The verdict of `pour-match` MUST name each failing probe. An input row of a probe (`H-A-POUR-CLEARANCE` to `H-A-POUR-VIAPAD`) MUST be settled by the probes that name it (the column "settled by" of the design of change c0215), not by whole steps: it passes when every `pour-match` passes for each of those probes, so that one failing probe fails only the rows it names.

#### Scenario: A simulated run of the pour steps passes
- **GIVEN** a kit whose `results/` for `pour` and `pour4` were filled by `tests/unit/verify/kit/_simulate.py`, with Fenolite's own pour standing in for Altium's repour
- **WHEN** `uv run pytest tests/unit/verify/kit/test_results.py -k pour` verifies it
- **THEN** every step of group 6 passes, and the verdict is marked synthetic

#### Scenario: A repour that did not run
- **GIVEN** the same run where the saved board of K6.2 is the reference input saved again without regions
- **WHEN** it is verified
- **THEN** K6.2 fails with "the repour did not run", and `H-A-POUR-KIT` fails

#### Scenario: A neck removed differently
- **GIVEN** the same run where the saved board of K6.2 keeps the 4.5-mil neck of probe P3
- **WHEN** it is verified
- **THEN** K6.2 fails on `pour-match` naming probe P3 and M2 at the neck's place, `H-A-POUR-KIT` and `H-A-POUR-NECK` fail, and `H-A-POUR-CLEARANCE` passes

### Requirement: Pour census of the public corpus
`tests/corpus/test_altium_pour_census.py` SHALL pour, with `pour.pour_reading`, every polygon of the public PCB documents of the corpus manifest (`altium-third-party-pcbdoc-01` to `-08`) and SHALL compare each polygon that is not refused with the regions the document holds, by M1 to M4 of `pourcompare.compare_pours`. `docs/evidence/altium-pour.md` SHALL hold, per document: the polygons, the refused ones by reason, the compared ones, those that pass, and the worst M1 ratio and M2 difference. A failed comparison MUST be listed with its polygon and its place and MUST NOT fail the test: a saved pour may be stale, or poured by another version or with AdvancedPour. A pass supports `H-A-POUR-CORPUS` for that polygon only, at `CORPUS-VERIFIED`.

#### Scenario: Census counts are pinned
- **WHEN** `uv run pytest tests/corpus/test_altium_pour_census.py -rA` runs with the corpus fetched
- **THEN** the counts per document equal those of `docs/evidence/altium-pour.md`, and every refused polygon has a reason of `pour.REASONS`
