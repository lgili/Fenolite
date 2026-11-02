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

The authored driver controls are local proof only. A local KiCad 9.0.2 run has
that exact scope; it cannot establish 9.0.9/10.0.6 CI, native KiCad 10 acceptance,
all-row equality or higher hypothesis levels. Task 7.2 stays open until its
literal required-job proof passes. Actual measurements will be appended with
their code/input hashes, tool version, statuses and timings.

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
