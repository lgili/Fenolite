# Drawn schematic corpus census

The c0276 task-7.2 driver measures every demo schematic row in
`tests/corpus/manifest.toml` (source S-0058), with the source hierarchy selected
for the running KiCad major. The current inventory has 130 rows, including child
sheets; this is an inventory count, not a successful native measurement.

Current context selection measures a child in every declared native project
root that reaches it, retaining repeated-instance annotation paths. The case
records its owner/export-root ID, exact schematic/project hashes and an opaque
instance map, then compares the whole owner hierarchy without intersecting pin
universes. An unowned row remains an explicit standalone case; unavailable,
unreadable or conflicting owner contexts fail. Both native jobs fetch the
declared project inputs. The earlier file-as-root observations below remain
historical diagnostics, including artificial root-port/annotation failures;
they are not evidence that a child has that behavior in its real project.

The [owner-context measurements](drawn-context.md) retain the later source-bound
diagnostic and corrected runs, including unresolved formats, definitions and names.

It verifies cached input SHA-256 values, extracts/lower/resolves the drawing and
compares complete source/lowered/native pin partitions. Open singletons and
native-only nodes remain in the comparison. Naming is recorded separately for
drawn-named nets; a naming warning is not a connectivity pass for a differing
partition. Explicit source/lowering/native refusals and missing/incompatible
inputs have their own outcomes. No accepted differences or loss flag is used.

Each case writes a value-free `drawn-census.json` before the strict assertion;
the KiCad CI jobs retain these files even when the job fails. Copied and derived
CAD files remain temporary and are deleted; no component names, values, labels
or CAD fragments belong in the census. No third-party payload is committed.

The authored driver controls and the historical local KiCad 9.0.2 runs have
that exact scope; they cannot establish 9.0.9/10.0.6 CI, native KiCad 10 acceptance,
all-row equality or higher hypothesis levels. The later source-bound CI census
below completes task 7.2's measurement/reporting scope only. Required integration
and hypothesis gates remain separate; the whole CI run did not pass.

## Actual local census — 2026-11-02

Measured code: `9c44f7a224790b31ccbe017a0cce4c059b8c9b25`; manifest SHA-256:
`bdc796c64b61f1e0a0240f2c133e879cc367a1ed256ea006cf883320b2cb4dcc`. Native CLI: **9.0.2**, running the manifest's shared/tag-9
inputs. This is no 9.0.9, 10.0.6 or exact-head CI claim. The full machine-readable
[observation](drawn-schematic.json) contains each input SHA-256, declared/observed
formats, upstream ref/commit abbreviation, tool/code version, counts and timings.

Literal focused command: `uv run pytest tests/kicad/schematic/test_drawn_corpus.py -q -rA --tb=short`,
with the external cache and required `kicad,corpus` resources. Result: **76 failed,
16 passed, 38 skipped in 158.13 s**, exit 1. All 130 reports survived; no copied or
derived schematic remains. No internal harness error occurred.

| Outcome | Rows |
|---|---:|
| All three connectivity comparisons equal | 16 |
| Compared connectivity differs | 6 |
| Explicit refusal | 50 |
| Missing compatible cached input | 20 |
| Other manifest/native-major tag | 38 |

The 92 eligible rows have 72 cached inputs. Original-native comparisons exist
for 69 rows and lowered-native comparisons for 22; absent comparisons are not
zero differences. Fifty refusals comprise 47 stops at the post-lowering issue
guard, two source-symbol FormatErrors and one unsupported reader format. Per-stage
issue counters preserve the actual origin (485 unmatched-sheet-pin errors in
resolution and 98 unknown-part errors in lowering across refused rows). These
are unresolved outcomes, not accepted losses. Naming differences occur on 23 original
comparison rows and remain separate from partition equality.

The bus examples `kicad-demo-10-0-6-sch-041` (313 pins) and `...sch-077`
(2033 pins) retain equal original/lowered native partitions while their own
resolver groups differ. The raw counts are retained; no bus, name, pin-universe,
acceptance or ratchet rule was changed.

The external fetcher could not complete this sandbox's cache (EPERM; no new
permission was requested). The 20 eligible missing inputs remain explicit
failures. Altium and native 10/required CI proofs remain open. Task 7.2 is not
complete. Times below cover measured pipeline cases; an em dash means no native
pipeline ran, including the incompatible/missing rows' raw zero sentinel.
All 130 rows, full hashes and all three comparisons are in the JSON. The table lists the 72 pipeline cases; its hashes are prefixes. The 58 nonexecution rows have no native counts or timing.

| Row | Input SHA-256 prefix | Declared format | Outcome / stop | Own/native groups | Source name differences | Pipeline s |
|---|---|---:|---|---|---:|---:|
| kicad-demo-10-0-6-sch-01 | 4344cf98eac9 | 20250114 | equal | 52/52 | 0 | 1.029482 |
| kicad-demo-10-0-6-sch-010 | ef6f503f39f7 | 20250114 | differs | 25/51 | 0 | 0.742746 |
| kicad-demo-10-0-6-sch-011 | 8a2d0359a0f3 | 20250114 | equal | 13/13 | 0 | 0.6142 |
| kicad-demo-10-0-6-sch-012 | 80576c542e9c | 20250114 | equal | 13/13 | 0 | 0.731915 |
| kicad-demo-10-0-6-sch-013 | b3b8c3b19938 | 20250114 | equal | 173/173 | 0 | 1.622079 |
| kicad-demo-10-0-6-sch-031 | b406e5f8d190 | 20250114 | refused / lower | 151/209 | 32 | 0.913349 |
| kicad-demo-10-0-6-sch-032 | a1109092165e | 20250114 | differs | 293/278 | 33 | 3.661368 |
| kicad-demo-10-0-6-sch-033 | 3750dc3866cc | 20250114 | refused / lower | 123/127 | 10 | 0.600353 |
| kicad-demo-10-0-6-sch-034 | 2c98b5d37f5b | 20250114 | refused / lower | 22/67 | 4 | 0.738709 |
| kicad-demo-10-0-6-sch-035 | e47aecee9416 | 20250114 | equal | 80/80 | 0 | 1.721934 |
| kicad-demo-10-0-6-sch-041 | 3636dcd5252a | 20250114 | differs | 127/95 | 61 | 3.630024 |
| kicad-demo-10-0-6-sch-042 | f9e17eb92e5a | 20250114 | equal | 1/1 | 0 | 0.410964 |
| kicad-demo-10-0-6-sch-043 | 7b78116155a9 | 20250114 | refused / lower | 28/28 | 0 | 0.338139 |
| kicad-demo-10-0-6-sch-044 | e6f3273cb98b | 20250114 | refused / lower | 47/62 | 0 | 0.971515 |
| kicad-demo-10-0-6-sch-045 | b53b9a766126 | 20250114 | refused / lower | 23/31 | 0 | 0.885671 |
| kicad-demo-10-0-6-sch-046 | d1c824ffcfe8 | 20250114 | refused / lower | 40/48 | 0 | 0.819814 |
| kicad-demo-10-0-6-sch-067 | 5271d5d1472d | 20250114 | equal | 42/42 | 0 | 1.078329 |
| kicad-demo-10-0-6-sch-068 | ee88a17d35fb | 20250114 | refused / lower | 50/55 | 5 | 0.558279 |
| kicad-demo-10-0-6-sch-069 | 232f8236bc89 | 20250114 | equal | 114/114 | 4 | 3.71628 |
| kicad-demo-10-0-6-sch-070 | 0110ee91bd8e | 20250114 | refused / lower | 182/185 | 24 | 1.06299 |
| kicad-demo-10-0-6-sch-071 | b736ce2d5a17 | 20250114 | refused / lower | 84/106 | 0 | 0.67711 |
| kicad-demo-10-0-6-sch-072 | c09706718277 | 20250114 | refused / lower | 166/168 | 18 | 0.913339 |
| kicad-demo-10-0-6-sch-073 | 59f6d8152af7 | 20250114 | refused / lower | 43/76 | 0 | 0.40849 |
| kicad-demo-10-0-6-sch-074 | 9b757497857c | 20250114 | refused / lower | 117/116 | 2 | 0.538082 |
| kicad-demo-10-0-6-sch-075 | 970c766b745d | 20250114 | refused / lower | 84/109 | 0 | 0.71578 |
| kicad-demo-10-0-6-sch-076 | 40a46f70b673 | 20250114 | refused / lower | 186/186 | 0 | 1.083047 |
| kicad-demo-10-0-6-sch-077 | 4d3ced775e49 | 20250114 | differs | 682/588 | 231 | 7.865115 |
| kicad-demo-10-0-6-sch-078 | 4942247e5508 | 20250114 | refused / lower | 99/127 | 0 | 2.541638 |
| kicad-demo-10-0-6-sch-079 | 000b342b036d | 20250114 | refused / lower | 84/86 | 0 | 2.701528 |
| kicad-demo-10-0-6-sch-080 | fb8f40e676e3 | 20250114 | refused / lower | 32/32 | 0 | 0.873549 |
| kicad-demo-10-0-6-sch-081 | 7f5d60fcebe3 | 20250114 | refused / lower | 41/41 | 0 | 0.674296 |
| kicad-demo-10-0-6-sch-082 | 387cf92f575f | 20250114 | refused / lower | 31/40 | 0 | 3.399703 |
| kicad-demo-10-0-6-sch-083 | afa21638aa44 | 20250114 | refused / lower | 97/97 | 0 | 3.076748 |
| kicad-demo-10-0-6-sch-084 | d8ff041ed298 | 20250114 | refused / lower | 203/210 | 0 | 3.52354 |
| kicad-demo-10-0-6-sch-085 | 2c7cab85da7c | 20250114 | differs | 6/7 | 0 | 1.872936 |
| kicad-demo-10-0-6-sch-086 | d391e2243f61 | 20250114 | refused / lower | 84/98 | 0 | 3.1961 |
| kicad-demo-10-0-6-sch-087 | c9bf69883fdc | 20250114 | refused / lower | 78/78 | 0 | 2.383973 |
| kicad-demo-10-0-6-sch-088 | 0543b36e5888 | 20250114 | equal | 2/2 | 0 | 1.762472 |
| kicad-demo-10-0-6-sch-089 | 3e1619fbf0f0 | 20250114 | equal | 12/12 | 0 | 6.113016 |
| kicad-demo-10-0-6-sch-090 | 845bfa141acd | 20250114 | refused / lower | 137/138 | 0 | 1.164608 |
| kicad-demo-10-0-6-sch-091 | 931ec5588e9b | 20250114 | refused / lower | 628/659 | 6 | 18.706409 |
| kicad-demo-10-0-6-sch-092 | 0e7b55b9ebe2 | 20230819 | refused / read | — | — | 0.406337 |
| kicad-demo-10-0-6-sch-093 | 22a6b1929bde | 20250114 | refused / lower | 23/99 | 13 | 1.327139 |
| kicad-demo-10-0-6-sch-094 | 52c56ff5652a | 20250114 | refused / lower | 32/199 | 18 | 2.843657 |
| kicad-demo-10-0-6-sch-095 | 201f060bfe9a | 20250114 | refused / lower | 30/195 | 19 | 1.984173 |
| kicad-demo-10-0-6-sch-096 | d1504d7659d6 | 20250114 | refused / lower | 41/41 | 0 | 0.639851 |
| kicad-demo-10-0-6-sch-097 | c201f38f7619 | 20250114 | refused / lower | 42/83 | 0 | 2.486385 |
| kicad-demo-10-0-6-sch-098 | 356ae56e243f | 20250114 | refused / lower | 32/59 | 0 | 1.422484 |
| kicad-demo-10-0-6-sch-099 | 3875c3e16e03 | 20250114 | refused / lower | 33/55 | 0 | 1.746944 |
| kicad-demo-10-0-6-sch-100 | 3c9b4de2c97d | 20250114 | refused / lower | 11/41 | 7 | 0.837858 |
| kicad-demo-10-0-6-sch-101 | 4616b90ca042 | 20250114 | refused / lower | 20/84 | 16 | 1.246755 |
| kicad-demo-10-0-6-sch-102 | 11569225b001 | 20250114 | refused / lower | 20/84 | 16 | 1.072596 |
| kicad-demo-10-0-6-sch-103 | e4cfcb9cff29 | 20250114 | refused / lower | 20/89 | 17 | 1.021529 |
| kicad-demo-10-0-6-sch-104 | 61d7229a38ee | 20250114 | refused / lower | 47/49 | 2 | 0.717372 |
| kicad-demo-10-0-6-sch-105 | 62a121ea4587 | 20250114 | refused / lower | 32/32 | 0 | 0.775726 |
| kicad-demo-10-0-6-sch-106 | 4cc3e74f2e47 | 20250114 | refused / source-symbols | — | — | 22.24283 |
| kicad-demo-10-0-6-sch-107 | 23e26501427c | 20250114 | refused / lower | 94/94 | 0 | 1.165565 |
| kicad-demo-10-0-6-sch-108 | db54a9ab8f1d | 20250114 | refused / lower | 54/56 | 2 | 1.004758 |
| kicad-demo-10-0-6-sch-109 | 81a8d975deb0 | 20250114 | refused / lower | 94/94 | 0 | 1.075677 |
| kicad-demo-10-0-6-sch-110 | 609845f4c591 | 20250114 | refused / lower | 102/134 | 0 | 1.430958 |
| kicad-demo-10-0-6-sch-111 | e1d4d19d3cdf | 20250114 | refused / lower | 75/75 | 0 | 0.599103 |
| kicad-demo-10-0-6-sch-112 | 6ad4226e2520 | 20250114 | refused / source-symbols | — | — | 4.287414 |
| kicad-demo-10-0-6-sch-113 | 9752e91a609c | 20250114 | refused / lower | 92/92 | 0 | 0.795951 |
| kicad-demo-10-0-6-sch-114 | 6f4886c6231b | 20250114 | refused / lower | 255/255 | 0 | 1.515219 |
| kicad-demo-9-0-9-1-sch-001 | 3e6436bd16ae | 20250114 | equal | 3/3 | 0 | 0.455925 |
| kicad-demo-9-0-9-1-sch-002 | f5149ad1285c | 20250114 | equal | 117/117 | 0 | 1.723421 |
| kicad-demo-9-0-9-1-sch-003 | 0714ab9909f1 | 20250114 | differs | 46/84 | 0 | 1.140965 |
| kicad-demo-9-0-9-1-sch-004 | 81603cf93062 | 20250114 | equal | 77/77 | 0 | 0.647019 |
| kicad-demo-9-0-9-1-sch-005 | 3da8e1a25050 | 20250114 | equal | 111/111 | 1 | 1.487522 |
| kicad-demo-9-0-9-1-sch-006 | 37c9b424b5dc | 20250114 | refused / lower | 76/76 | 0 | 0.395842 |
| kicad-demo-9-0-9-1-sch-015 | 970f9d58e9f3 | 20250114 | equal | 2/2 | 0 | 0.44096 |
| kicad-demo-9-0-9-1-sch-016 | a7fb63d6ee42 | 20250114 | equal | 100/100 | 11 | 1.763479 |


## Complete native census, 2026-11-03

The [source-bound observations](drawn-native-census-20261103.json) record all130
manifest rows on clean source b50fd0f05a8d37125048d54fbf4754e3cd2b2e9c. Native9.0.9
completes92 tests with38 version-incompatible skips:87 connectivity-equal rows
and5 explicit read-floor refusals. Native10.0.6 completes114 tests with16
version-incompatible skips:113 connectivity-equal rows and1 explicit read-floor
refusal. Both commands exit0; neither changes its source checkout.

Every recorded original/lowered/native graph comparison remains complete. Naming
outcomes and refusal/version scopes are separate; equality of connectivity does
not claim that all names agree. The JSON retains each context's counts, name
differences and original/lowered findings, plus complete raw receipt/log hashes.
No CAD is retained in this report. This historical local proof does not replace
the required exact-current-head CI jobs or promote a global hypothesis.


## Source-bound CI census — 2026-11-03 (985f59a1)

Measured source: `985f59a1d01a612b2eac0219243199896c24075a`; manifest SHA-256:
`bdc796c64b61f1e0a0240f2c133e879cc367a1ed256ea006cf883320b2cb4dcc`.
The [portable per-row records](drawn-ci-census-985f59a1.json) reconcile the retained
census artifacts from run 41708879698. Both native jobs executed the census:
9.0.9 job 126171394740 completed successfully; 10.0.6 job 126171394674 failed
elsewhere in its selected geometry cases. The whole CI run remains **failure**.
The 10 job used quiet output, so no unretained PASSED/stdout content or literal
`-rA` invocation is invented. Its complete per-row JSON survives each assertion.

### Comparison subjects (retained producer)

The field names identify three different comparisons in
`tests/_drawn_corpus.py::measure`; all retain complete pin partitions and record
naming separately for `drawn-named-nets`:

| Field | Left subject | Right subject |
|---|---|---|
| `partition` | Resolver output extracted from the original drawing | Original native netlist export |
| `lowered_partition` | Resolver output after lowering, writing and reading back | Original native netlist export |
| `lowered_native_partition` | Netlist constructed from the original native export's names and groups | Native netlist export of the rewritten drawing |

For the third field the producer constructs `original_netlist` from
`original_groups`, which came from the original native export. It does **not**
pass `lowered_own`, the readback resolver, to this comparison. Thus equal naming
in `lowered_native_partition` proves preservation between the two native
exports; it does not prove that the lowered resolver's names match either one.

The source985 resolver/original and lowered-resolver/original naming differences
remain in 57 of 87 contexts on 9 and 82 of 113 on 10. The native-original versus
native-rewritten naming comparison is equal in all 87/113 successful contexts.
These are the existing retained measurements, not new exports. Their different
subjects must not be combined into universal resolver naming equality.
`H-K-DRAWN-NAMES` retains its original statement and `INFERRED` label; no pending
c0276 task, experimental writer or CI gate is closed by this clarification.

| Native | Real declared rows | Equal complete partitions | Original reader-floor negatives | Incompatible tag, not executed | Raw JSONs | Byte-identical aliases |
|---|---:|---:|---:|---:|---:|---:|
| 9.0.9 | 130 | 87 | 5 | 38 | 262 | 132 |
| 10.0.6 | 130 | 113 | 1 | 16 | 131 | 1 |

Aliases were consolidated by row ID only after the complete raw bytes/hashes
matched; no differing report was discarded. Each row's member hashes remain
in the JSON. A child row's complete owner graph is retained independently:
these counts are row contexts, not unique owners, physical boards or nets.

Every compatible cached row, materialized input and declared owner/project
input matches its manifest SHA-256. The 9 job has 28 absent observed input hashes
only among incompatible-tag records; those rows never entered the pipeline.
Their declared hashes remain present. These are not missing-cache passes. The
10 job retained observed hashes for all 130 rows, including its 16 incompatible
rows. There is no missing/invalid-cache, internal error, unexpected refusal or
partition mismatch in this census. All three complete comparisons retain open
singletons and native-only/unlisted nodes; the latter counts are zero.

All successful contexts retain per-kind counts for sheets, symbols, wires,
labels, powers, buses, bus entries, sheet references, opaque records and
junctions; the 36 owner-definition contexts additionally count contextual
definitions. The JSON retains all row IDs, declared formats, owner/instance
hashes, input hashes, counts, five stage timings and total row times. Repeated
owner/input metadata is stored once by canonical hash; each row's measured
comparisons, counts and timings remain separate.

| Native | Sum of recorded row seconds | Sum of successful context seconds |
|---|---:|---:|
| 9.0.9 | 4728.628369 | 4696.791247 |
| 10.0.6 | 5504.690357 | 5469.765935 |

These sums include repeated child-owner contexts and parallel jobs; they are
not wall time or unique-owner performance. The five per-context stages are
extract, lower, resolve, native-original and native-lowered. An incompatible
tag's zero is a nonexecution sentinel, displayed as an em dash below. A floor
negative's row time measures the original reader refusal, not a lower/native
pipeline. Copied/derived CAD stayed under temporary per-case source folders,
removed in the source985 harness's `finally`; only value-free JSON was retained.
The manifest and census/context helper bytes still match that measured source,
which does not assert equivalence of every later runtime dependency.

The 9 negatives are `kicad-demo-10-0-6-sch-092` and
`kicad-demo-9-0-9-1-sch-008`, `-012`, `-013`, `-014`; the 10 primary census
negative is `kicad-demo-10-0-6-sch-092`. Each is the original, explicit
`FEN-3003`/`UnsupportedFormatError` at read, below the reader floor. They remain
refusals, with no generic-refusal allowance or accepted loss. Separate c0347
upgraded-original qualification does not overwrite these original outcomes.

Resolver/source and lowered/source naming warnings remain in **57/87** contexts
on 9 and **82/113** on 10. Original-native/rewritten-native names agree in all 87/113
successful contexts. The raw warning sums 18,515/18,586 repeat owner graphs and
are not unique net/defect counts. This is no universal H-K-DRAWN-NAMES claim.
No comparator, pin domain, writer loss flag, baseline or hypothesis level was
changed. Task **7.2 only** is complete for measurement/reporting on source985;
7.1 and 9.2, integration CI and hypothesis promotion remain open.

### Complete row inventory for this CI observation

All entries have kind `schematic`. Counts below are complete owner-context
pins/groups, preserving the selected owner scope. Detailed entity-kind counts,
input/owner hashes, comparisons and stage timings are in the linked JSON.

| Row ID | Declared format | Native9 status; pins/groups | Row s | Native10 status; pins/groups | Row s |
|---|---:|---|---:|---|---:|
| kicad-demo-10-0-6-sch-002 | 20250610 | tag incompatible; — | — | equal; 603/221 | 5.760051 |
| kicad-demo-10-0-6-sch-003 | 20250610 | tag incompatible; — | — | equal; 603/221 | 5.945813 |
| kicad-demo-10-0-6-sch-004 | 20250610 | tag incompatible; — | — | equal; 603/221 | 4.075777 |
| kicad-demo-10-0-6-sch-005 | 20250610 | tag incompatible; — | — | equal; 603/221 | 5.79126 |
| kicad-demo-10-0-6-sch-006 | 20250610 | tag incompatible; — | — | equal; 603/221 | 5.822652 |
| kicad-demo-10-0-6-sch-007 | 20250610 | tag incompatible; — | — | equal; 603/221 | 3.738767 |
| kicad-demo-10-0-6-sch-008 | 20250610 | tag incompatible; — | — | equal; 603/221 | 5.938798 |
| kicad-demo-10-0-6-sch-009 | 20250610 | tag incompatible; — | — | equal; 603/221 | 5.990549 |
| kicad-demo-10-0-6-sch-01 | 20250114 | equal; 164/52 | 13.017461 | equal; 164/52 | 13.027868 |
| kicad-demo-10-0-6-sch-010 | 20250114 | equal; 164/52 | 1.486267 | equal; 164/52 | 1.808806 |
| kicad-demo-10-0-6-sch-011 | 20250114 | equal; 33/13 | 0.985889 | equal; 33/13 | 1.196413 |
| kicad-demo-10-0-6-sch-012 | 20250114 | equal; 33/13 | 1.107694 | equal; 33/13 | 1.169073 |
| kicad-demo-10-0-6-sch-013 | 20250114 | equal; 373/173 | 4.20229 | equal; 373/173 | 2.298129 |
| kicad-demo-10-0-6-sch-014 | 20250114 | tag incompatible; — | — | equal; 4712/1355 | 42.362716 |
| kicad-demo-10-0-6-sch-015 | 20250114 | tag incompatible; — | — | equal; 4712/1355 | 42.209454 |
| kicad-demo-10-0-6-sch-016 | 20250114 | tag incompatible; — | — | equal; 4712/1355 | 40.389287 |
| kicad-demo-10-0-6-sch-017 | 20250114 | tag incompatible; — | — | equal; 4712/1355 | 43.902467 |
| kicad-demo-10-0-6-sch-018 | 20250114 | tag incompatible; — | — | equal; 38/23 | 1.314016 |
| kicad-demo-10-0-6-sch-019 | 20250114 | tag incompatible; — | — | equal; 4712/1355 | 44.69803 |
| kicad-demo-10-0-6-sch-020 | 20250114 | tag incompatible; — | — | equal; 4712/1355 | 44.745371 |
| kicad-demo-10-0-6-sch-021 | 20250114 | tag incompatible; — | — | equal; 4712/1355 | 42.127528 |
| kicad-demo-10-0-6-sch-022 | 20250114 | tag incompatible; — | — | equal; 4712/1355 | 43.215607 |
| kicad-demo-10-0-6-sch-023 | 20250114 | tag incompatible; — | — | equal; 4712/1355 | 43.873926 |
| kicad-demo-10-0-6-sch-024 | 20250114 | tag incompatible; — | — | equal; 4712/1355 | 43.168527 |
| kicad-demo-10-0-6-sch-025 | 20250114 | tag incompatible; — | — | equal; 4712/1355 | 43.474167 |
| kicad-demo-10-0-6-sch-026 | 20250114 | tag incompatible; — | — | equal; 4712/1355 | 43.133252 |
| kicad-demo-10-0-6-sch-027 | 20250114 | tag incompatible; — | — | equal; 465/155 | 3.337832 |
| kicad-demo-10-0-6-sch-028 | 20250114 | tag incompatible; — | — | equal; 4712/1355 | 43.134032 |
| kicad-demo-10-0-6-sch-029 | 20250114 | tag incompatible; — | — | equal; 4712/1355 | 43.247405 |
| kicad-demo-10-0-6-sch-030 | 20250114 | tag incompatible; — | — | equal; 4712/1355 | 43.221379 |
| kicad-demo-10-0-6-sch-031 | 20250114 | equal; 803/278 | 7.516433 | equal; 803/278 | 4.135965 |
| kicad-demo-10-0-6-sch-032 | 20250114 | equal; 803/278 | 7.272085 | equal; 803/278 | 6.699076 |
| kicad-demo-10-0-6-sch-033 | 20250114 | equal; 803/278 | 7.4651 | equal; 803/278 | 6.217925 |
| kicad-demo-10-0-6-sch-034 | 20250114 | equal; 280/80 | 3.089216 | equal; 280/80 | 2.410003 |
| kicad-demo-10-0-6-sch-035 | 20250114 | equal; 280/80 | 3.063971 | equal; 280/80 | 2.589009 |
| kicad-demo-10-0-6-sch-036 | 20250114 | tag incompatible; — | — | equal; 647/155 | 6.499175 |
| kicad-demo-10-0-6-sch-037 | 20250114 | tag incompatible; — | — | equal; 647/155 | 6.344772 |
| kicad-demo-10-0-6-sch-038 | 20250114 | tag incompatible; — | — | equal; 647/155 | 6.456493 |
| kicad-demo-10-0-6-sch-039 | 20260101 | tag incompatible; — | — | equal; 236/111 | 2.291971 |
| kicad-demo-10-0-6-sch-040 | 20260101 | tag incompatible; — | — | equal; 236/111 | 2.110477 |
| kicad-demo-10-0-6-sch-041 | 20250114 | equal; 313/95 | 9.136305 | equal; 313/95 | 5.90465 |
| kicad-demo-10-0-6-sch-042 | 20250114 | equal; 2/1 | 0.730381 | equal; 2/1 | 0.985228 |
| kicad-demo-10-0-6-sch-043 | 20250114 | equal; 313/95 | 7.757394 | equal; 313/95 | 6.116625 |
| kicad-demo-10-0-6-sch-044 | 20250114 | equal; 313/95 | 7.510377 | equal; 313/95 | 6.317221 |
| kicad-demo-10-0-6-sch-045 | 20250114 | equal; 313/95 | 7.578118 | equal; 313/95 | 6.074331 |
| kicad-demo-10-0-6-sch-046 | 20250114 | equal; 313/95 | 7.663573 | equal; 313/95 | 6.5568 |
| kicad-demo-10-0-6-sch-047 | 20250114 | tag incompatible; — | — | equal; 49/13 | 1.139894 |
| kicad-demo-10-0-6-sch-048 | 20231120 | equal; 9/4 | 0.851259 | equal; 9/4 | 0.908961 |
| kicad-demo-10-0-6-sch-049 | 20241209 | equal; 87/23 | 1.47028 | equal; 87/23 | 1.268084 |
| kicad-demo-10-0-6-sch-050 | 20231120 | equal; 16/7 | 0.947421 | equal; 16/7 | 1.003539 |
| kicad-demo-10-0-6-sch-051 | 20250114 | tag incompatible; — | — | equal; 32/10 | 1.229256 |
| kicad-demo-10-0-6-sch-052 | 20231120 | equal; 38/9 | 1.182863 | equal; 38/9 | 1.127359 |
| kicad-demo-10-0-6-sch-053 | 20250114 | tag incompatible; — | — | equal; 30/9 | 1.084266 |
| kicad-demo-10-0-6-sch-054 | 20250114 | tag incompatible; — | — | equal; 33/9 | 1.024534 |
| kicad-demo-10-0-6-sch-055 | 20231120 | equal; 48/15 | 1.20814 | equal; 48/15 | 1.127127 |
| kicad-demo-10-0-6-sch-056 | 20250114 | tag incompatible; — | — | equal; 17/6 | 1.177283 |
| kicad-demo-10-0-6-sch-057 | 20250114 | tag incompatible; — | — | equal; 51/14 | 1.135892 |
| kicad-demo-10-0-6-sch-058 | 20231120 | equal; 36/10 | 1.114202 | equal; 36/10 | 1.079506 |
| kicad-demo-10-0-6-sch-059 | 20231120 | equal; 189/49 | 3.628942 | equal; 189/49 | 1.926979 |
| kicad-demo-10-0-6-sch-060 | 20250114 | tag incompatible; — | — | equal; 10/4 | 0.914604 |
| kicad-demo-10-0-6-sch-061 | 20250114 | tag incompatible; — | — | equal; 19/7 | 1.16472 |
| kicad-demo-10-0-6-sch-062 | 20241209 | equal; 26/8 | 1.057094 | equal; 26/8 | 1.054737 |
| kicad-demo-10-0-6-sch-063 | 20241209 | equal; 26/8 | 1.013595 | equal; 26/8 | 1.049237 |
| kicad-demo-10-0-6-sch-064 | 20241209 | equal; 26/8 | 1.050204 | equal; 26/8 | 1.069293 |
| kicad-demo-10-0-6-sch-065 | 20231120 | equal; 9/6 | 0.80558 | equal; 9/6 | 0.924433 |
| kicad-demo-10-0-6-sch-066 | 20240602 | equal; 72/19 | 1.705902 | equal; 72/19 | 3.468875 |
| kicad-demo-10-0-6-sch-067 | 20250114 | equal; 108/42 | 1.754615 | equal; 108/42 | 1.484292 |
| kicad-demo-10-0-6-sch-068 | 20250114 | equal; 584/114 | 7.910877 | equal; 584/114 | 4.482278 |
| kicad-demo-10-0-6-sch-069 | 20250114 | equal; 584/114 | 7.842729 | equal; 584/114 | 6.394938 |
| kicad-demo-10-0-6-sch-070 | 20250114 | equal; 2033/588 | 15.504796 | equal; 2033/588 | 11.983253 |
| kicad-demo-10-0-6-sch-071 | 20250114 | equal; 2033/588 | 15.920471 | equal; 2033/588 | 9.754827 |
| kicad-demo-10-0-6-sch-072 | 20250114 | equal; 2033/588 | 15.54283 | equal; 2033/588 | 12.484848 |
| kicad-demo-10-0-6-sch-073 | 20250114 | equal; 2033/588 | 16.159072 | equal; 2033/588 | 10.407811 |
| kicad-demo-10-0-6-sch-074 | 20250114 | equal; 2033/588 | 15.087905 | equal; 2033/588 | 11.676604 |
| kicad-demo-10-0-6-sch-075 | 20250114 | equal; 2033/588 | 15.285498 | equal; 2033/588 | 11.664997 |
| kicad-demo-10-0-6-sch-076 | 20250114 | equal; 2033/588 | 15.154948 | equal; 2033/588 | 10.30942 |
| kicad-demo-10-0-6-sch-077 | 20250114 | equal; 2033/588 | 14.499381 | equal; 2033/588 | 12.504402 |
| kicad-demo-10-0-6-sch-078 | 20250114 | equal; 6811/1800 | 180.582143 | equal; 6811/1800 | 125.520735 |
| kicad-demo-10-0-6-sch-079 | 20250114 | equal; 6811/1800 | 187.096103 | equal; 6811/1800 | 126.664343 |
| kicad-demo-10-0-6-sch-080 | 20250114 | equal; 6811/1800 | 183.106865 | equal; 6811/1800 | 125.2 |
| kicad-demo-10-0-6-sch-081 | 20250114 | equal; 6811/1800 | 180.644458 | equal; 6811/1800 | 125.751989 |
| kicad-demo-10-0-6-sch-082 | 20250114 | equal; 6811/1800 | 175.917081 | equal; 6811/1800 | 121.509634 |
| kicad-demo-10-0-6-sch-083 | 20250114 | equal; 6811/1800 | 136.91321 | equal; 6811/1800 | 120.534542 |
| kicad-demo-10-0-6-sch-084 | 20250114 | equal; 6811/1800 | 116.819327 | equal; 6811/1800 | 123.917912 |
| kicad-demo-10-0-6-sch-085 | 20250114 | equal; 6811/1800 | 116.62294 | equal; 6811/1800 | 128.529845 |
| kicad-demo-10-0-6-sch-086 | 20250114 | equal; 6811/1800 | 114.95538 | equal; 6811/1800 | 130.312397 |
| kicad-demo-10-0-6-sch-087 | 20250114 | equal; 6811/1800 | 114.17446 | equal; 6811/1800 | 124.930606 |
| kicad-demo-10-0-6-sch-088 | 20250114 | equal; 6811/1800 | 112.555541 | equal; 6811/1800 | 133.032521 |
| kicad-demo-10-0-6-sch-089 | 20250114 | equal; 6811/1800 | 114.417045 | equal; 6811/1800 | 127.820968 |
| kicad-demo-10-0-6-sch-090 | 20250114 | equal; 6811/1800 | 114.665765 | equal; 6811/1800 | 129.970675 |
| kicad-demo-10-0-6-sch-091 | 20250114 | equal; 6811/1800 | 115.348368 | equal; 6811/1800 | 131.834081 |
| kicad-demo-10-0-6-sch-092 | 20230819 | original read-floor; — | 0.821528 | original read-floor; — | 1.085773 |
| kicad-demo-10-0-6-sch-093 | 20250114 | equal; 6811/1800 | 114.769765 | equal; 6811/1800 | 130.562067 |
| kicad-demo-10-0-6-sch-094 | 20250114 | equal; 6811/1800 | 112.228106 | equal; 6811/1800 | 131.433307 |
| kicad-demo-10-0-6-sch-095 | 20250114 | equal; 6811/1800 | 113.480192 | equal; 6811/1800 | 130.862635 |
| kicad-demo-10-0-6-sch-096 | 20250114 | equal; 6811/1800 | 113.188995 | equal; 6811/1800 | 128.371261 |
| kicad-demo-10-0-6-sch-097 | 20250114 | equal; 6811/1800 | 115.439195 | equal; 6811/1800 | 126.55085 |
| kicad-demo-10-0-6-sch-098 | 20250114 | equal; 6811/1800 | 113.219153 | equal; 6811/1800 | 127.9339 |
| kicad-demo-10-0-6-sch-099 | 20250114 | equal; 6811/1800 | 114.465988 | equal; 6811/1800 | 128.742204 |
| kicad-demo-10-0-6-sch-100 | 20250114 | equal; 6811/1800 | 113.000047 | equal; 6811/1800 | 129.798594 |
| kicad-demo-10-0-6-sch-101 | 20250114 | equal; 6811/1800 | 113.679053 | equal; 6811/1800 | 129.333003 |
| kicad-demo-10-0-6-sch-102 | 20250114 | equal; 6811/1800 | 112.167648 | equal; 6811/1800 | 126.715147 |
| kicad-demo-10-0-6-sch-103 | 20250114 | equal; 6811/1800 | 115.484706 | equal; 6811/1800 | 128.184349 |
| kicad-demo-10-0-6-sch-104 | 20250114 | equal; 6811/1800 | 112.654169 | equal; 6811/1800 | 123.945922 |
| kicad-demo-10-0-6-sch-105 | 20250114 | equal; 6811/1800 | 113.651955 | equal; 6811/1800 | 127.429755 |
| kicad-demo-10-0-6-sch-106 | 20250114 | equal; 6811/1800 | 114.280494 | equal; 6811/1800 | 123.947626 |
| kicad-demo-10-0-6-sch-107 | 20250114 | equal; 6811/1800 | 112.400226 | equal; 6811/1800 | 130.057357 |
| kicad-demo-10-0-6-sch-108 | 20250114 | equal; 6811/1800 | 113.826105 | equal; 6811/1800 | 125.231463 |
| kicad-demo-10-0-6-sch-109 | 20250114 | equal; 6811/1800 | 114.200989 | equal; 6811/1800 | 122.462454 |
| kicad-demo-10-0-6-sch-110 | 20250114 | equal; 6811/1800 | 114.529132 | equal; 6811/1800 | 127.521589 |
| kicad-demo-10-0-6-sch-111 | 20250114 | equal; 6811/1800 | 113.113067 | equal; 6811/1800 | 128.781773 |
| kicad-demo-10-0-6-sch-112 | 20250114 | equal; 6811/1800 | 114.416024 | equal; 6811/1800 | 129.054058 |
| kicad-demo-10-0-6-sch-113 | 20250114 | equal; 6811/1800 | 113.031254 | equal; 6811/1800 | 124.105606 |
| kicad-demo-10-0-6-sch-114 | 20250114 | equal; 6811/1800 | 114.597383 | equal; 6811/1800 | 127.194494 |
| kicad-demo-9-0-9-1-sch-001 | 20250114 | equal; 6/3 | 0.533249 | tag incompatible; — | — |
| kicad-demo-9-0-9-1-sch-002 | 20250114 | equal; 244/117 | 1.619688 | tag incompatible; — | — |
| kicad-demo-9-0-9-1-sch-003 | 20250114 | equal; 244/117 | 1.647093 | tag incompatible; — | — |
| kicad-demo-9-0-9-1-sch-004 | 20250114 | equal; 244/117 | 2.728243 | tag incompatible; — | — |
| kicad-demo-9-0-9-1-sch-005 | 20250114 | equal; 236/111 | 1.630101 | tag incompatible; — | — |
| kicad-demo-9-0-9-1-sch-006 | 20250114 | equal; 236/111 | 1.608498 | tag incompatible; — | — |
| kicad-demo-9-0-9-1-sch-007 | 20241209 | equal; 32/10 | 0.689461 | tag incompatible; — | — |
| kicad-demo-9-0-9-1-sch-008 | 20230121 | original read-floor; — | 0.055235 | tag incompatible; — | — |
| kicad-demo-9-0-9-1-sch-009 | 20231120 | equal; 33/9 | 0.657365 | tag incompatible; — | — |
| kicad-demo-9-0-9-1-sch-010 | 20231120 | equal; 17/6 | 0.6152 | tag incompatible; — | — |
| kicad-demo-9-0-9-1-sch-011 | 20231120 | equal; 51/14 | 0.76992 | tag incompatible; — | — |
| kicad-demo-9-0-9-1-sch-012 | 20230221 | original read-floor; — | 0.059436 | tag incompatible; — | — |
| kicad-demo-9-0-9-1-sch-013 | 20230121 | original read-floor; — | 0.038408 | tag incompatible; — | — |
| kicad-demo-9-0-9-1-sch-014 | 20230121 | original read-floor; — | 0.04668 | tag incompatible; — | — |
| kicad-demo-9-0-9-1-sch-015 | 20250114 | equal; 4/2 | 0.479066 | tag incompatible; — | — |
| kicad-demo-9-0-9-1-sch-016 | 20250114 | equal; 259/100 | 2.705708 | tag incompatible; — | — |
