# Altium v0.3 acceptance

The authored acceptance tree is prepared and its local readback proofs passed on
2026-10-14. The complete KiCad-import acceptance test passed in CI 38504478797.
Aggregate verification of its newly registered probe and native acceptance of
this new project remain pending. No write kind graduates from these results. The register retains `INFERRED` until the new probe criterion is verified. Local
readback uses Fenolite's own writers and readers; the separate CI import result is
recorded below.

## Project and scope

`examples/acceptance_v03/design.py` declares six copper layers, a two-level module
tree, three via kinds, board text, a keep-out, a polygon and all eight exact rule
kinds. All dimensions are Fenolite choices. The CC0 drawing sheet is an unchanged
copy of the shipped generic template, retaining its public provenance S-0077 and
S-0078.

The runner adds an authored ranged bus, a free non-plated hole and explicit
extruded bodies through the neutral model and existing writers. These are model
preparation steps, not additional DSL features. KiCad stores its free hole in an
anonymous footprint; Altium stores it as a free pad. Both written holes must be
one non-plated 2 mm drill within the committed triangle tolerance before the triangle's existing unnamed-reference policy
can exclude unpairable references. The Altium scope inventory reads the generated
project and typed keep-out records; it does not rely solely on its model cache.

## Local result, 2026-10-14

| step | result |
|---|---|
| Build KiCad target 10 with reviewed plan | passed |
| Build Altium binary module sheets with reviewed plan | passed |
| Required written scope | passed, all twelve criteria |
| KiCad model validation and same-version roundtrip | passed |
| Altium model validation and RT-A1 | passed |
| Altium project RT-A3 | passed |
| KiCad board versus Altium PCB document, level 5 | passed |
| KiCad importer versus the KiCad board, level 5 | passed in CI 38504478797, KiCad 10.0.6 |
| Probe `acceptance-v03` and frozen outcome | registered as equal from the full CI acceptance; aggregate probe verification pending next batch |
| Native kit correspondence and publication | pending task 3.1 |

The focused acceptance tests passed (5 tests); fixture-manifest and hypothesis/provenance
checks passed (91 tests). The comparison uses the committed
`kicad-import` triangle profile; it adds no new tolerance or exclusion. The checks
above validate model and readback only: this intentionally sparse exercise board
is not a fully routed or DRC-clean production board. Copper short and clearance
acceptance are covered separately by the kit and the roadmap's planted controls.

Fenolite version: `0.5.0.dev0`. KiCad output target: `10`; no `kicad-cli` was
launched for the local proofs. Altium version and kit run id for this new project:
not measured. Existing native kit records are retained separately and are not
reported as a native run of this project.

## Reproduce and finish

Local preparation, into a new output folder:

```console
uv run python tools/acceptance_v03.py --out build/acceptance-v03-prepared --prepare-only
uv run pytest tests/unit/test_acceptance_v03.py -q
```

Full oracle acceptance runs in GitHub CI:

```console
uv run pytest tests/kicad/acceptance/test_v03_acceptance.py -q
```

`summary.json` records each stage, tool versions and an optional reported kit run
id. `acceptance_complete` remains false for preparation, a failed stage or an
exception. Raw command replies stay beside the generated files for diagnosis;
they are not committed, because receipts may contain local paths. An existing
output folder is refused so an earlier result cannot be overwritten. Task 2.1
remains open until the complete oracle proof, probe outcome and evidence update
pass. Archive still requires actual successful CI and the dependency order.

## Complete oracle result and native-kit reconciliation

The KiCad-10 job of [run 38504478797](https://github.com/lgili/Fenolite/actions/runs/38504478797)
passed on pinned KiCad 10.0.6 (3274 passed, 116 skipped, 3 expected failures).
It includes the complete acceptance test, including the import comparison. Its
result justifies adding the new `acceptance-v03: equal` probe criterion for
10.0.6; all 992 pre-existing outcomes remain unchanged. The test and probe now
share the same cached full acceptance. Registration tests passed 19 cases without
launching an external tool. Task 2.1 still waits for the new aggregate probe proof.

A fresh `kit status` on this tree confirms four records, no stale rows and no
problems. Completed run `2026-10-13-462b38ba` uses AD 26.5 and the current kit
digest `af3c911e0fc76db4bac6dabeb48c401f1ca12ac216b3951f9c99cace2ae15483`.
Its 32 passed steps remain valid; no failure is recorded. Its archive publication
and privacy review remain pending task 3.1. All 27 hypotheses settled by that run
currently retain their existing inferred/author-report levels; this reconciliation
changes no evidence label and does not claim native acceptance of the newly
authored acceptance project. Task 3.2 will apply eligible promotions after the
publication requirement is met.

## Archive publication review

CI completion on 2026-10-14: [run 38520443552](https://github.com/lgili/Fenolite/actions/runs/38520443552)
passed all 11 jobs on exact commit `d9d980d7046cb2254ca9bcb94f0ccdcd96555626`.
The pinned 10.0.6 job ran the full KiCad/corpus selection with heavy inputs:
3274 passed, 116 skipped, 3 expected failures. Neither the complete acceptance
nor the aggregate probe test appears in the reported skips. The new
`acceptance-v03: equal` outcome is confirmed, closing c0092 task 2.1 and making
`H-A-ACC-V03` `KICAD-VERIFIED (10.0.x)` within its established triangle profile.
This is not a native Altium run of the new acceptance project. The later
Clearance/archive batch has its own CI run and is outside this verdict.

The full-run ZIP matches its committed SHA-256 and its size of 1236513 bytes;
it contains 27 members. A fresh privacy scan reproduces the record's 43
home-folder findings across eight files: five native binary documents/libraries
and three reports. No personal value is reproduced here. A value-free local
review is saved under `build/c0092-publication-review.md`.

The original ZIP and immutable run record remain unchanged and unpublished.
Changing result bytes changes the archive digest, so a cleaned version cannot
be published as the original run. A new native save in a neutral folder, followed
by verification and a new record, is the proposed publication path. This review
changes no native verdict or evidence level.
