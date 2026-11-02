# Drawn corpus: native owner context

The c0276 follow-up uses S-0058 and the pinned corpus manifest. It retains every
declared demo row while exporting its real
registered project hierarchy. Child ports and repeated annotations keep their
parent context. Native pin universes remain complete; no accepted difference,
loss flag, reader-floor change or conflict exception is used.

The [machine-readable observations](drawn-context.json) retain all 130 row reports
for each run, with code/input hashes and actual native **9.0.2**. The original
[9c44 measurement](drawn-schematic.json) remains byte-identical. Neither local
run establishes 9.0.9/10.0.6 CI or closes task 7.2.

| Source | Scope | Passed | Failed | Other-tag skips | Seconds |
|---|---|---:|---:|---:|---:|
| `695dee0f1bdf2cff066edad0220c63cf064ae0a2` | diagnostic file-as-root | 33 | 59 | 38 | 192.71 |
| `ce3b999244af8e6a246f9457289ef6b5023bba05` | actual owner hierarchy | 51 | 41 | 38 | 1276.45 |

The diagnostic run had complete schematic inputs but not all declared project
files. All 49 post-lowering issue guards were artificial leaf-root cases.
The corrected run verified all 132 schematic and 54 project manifest hashes
before parsing. It retains every child and all owners, plus an explicit
standalone case for the one row no registered root reaches. Context records
bind owner/export-root IDs, projects and opaque instance paths.

| Corrected outcome | Rows |
|---|---:|
| `equal` | 51 |
| `native-version-incompatible` | 38 |
| `refused` | 41 |

There are 36 distinct owner/standalone contexts across 92 eligible row
contexts. Original/native comparisons exist for 51 row contexts;
lowered/native comparisons for 51. Missing comparisons are
not zero differences. Naming differs on 21 row contexts and remains
a separate warning result, even when all three connectivity comparisons agree.

| Owner or standalone row | Target rows | Result | Source pins / groups | Refusal |
|---|---:|---|---|---|
| `kicad-demo-10-0-6-sch-01` | 2 | `equal` | 164 / 52 | — |
| `kicad-demo-10-0-6-sch-011` | 1 | `equal` | 33 / 13 | — |
| `kicad-demo-10-0-6-sch-012` | 1 | `equal` | 33 / 13 | — |
| `kicad-demo-10-0-6-sch-013` | 1 | `equal` | 373 / 173 | — |
| `kicad-demo-10-0-6-sch-032` | 3 | `equal` | 803 / 278 | — |
| `kicad-demo-10-0-6-sch-035` | 2 | `equal` | 280 / 80 | — |
| `kicad-demo-10-0-6-sch-041` | 5 | `equal` | 313 / 95 | — |
| `kicad-demo-10-0-6-sch-042` | 1 | `equal` | 2 / 1 | — |
| `kicad-demo-10-0-6-sch-048` | 1 | `equal` | 9 / 4 | — |
| `kicad-demo-10-0-6-sch-049` | 1 | `equal` | 87 / 23 | — |
| `kicad-demo-10-0-6-sch-050` | 1 | `equal` | 16 / 7 | — |
| `kicad-demo-10-0-6-sch-052` | 1 | `equal` | 38 / 9 | — |
| `kicad-demo-10-0-6-sch-055` | 1 | `equal` | 48 / 15 | — |
| `kicad-demo-10-0-6-sch-058` | 1 | `equal` | 36 / 10 | — |
| `kicad-demo-10-0-6-sch-059` | 1 | `equal` | 189 / 49 | — |
| `kicad-demo-10-0-6-sch-062` | 3 | `equal` | 26 / 8 | — |
| `kicad-demo-10-0-6-sch-065` | 1 | `equal` | 9 / 6 | — |
| `kicad-demo-10-0-6-sch-066` | 1 | `equal` | 72 / 19 | — |
| `kicad-demo-10-0-6-sch-067` | 1 | `equal` | 108 / 42 | — |
| `kicad-demo-10-0-6-sch-069` | 2 | `equal` | 584 / 114 | — |
| `kicad-demo-10-0-6-sch-077` | 8 | `equal` | 2033 / 588 | — |
| `kicad-demo-10-0-6-sch-092` | 1 | `refused` | — | read: UnsupportedFormatError |
| `kicad-demo-10-0-6-sch-106` | 36 | `refused` | — | source-symbols: FormatError |
| `kicad-demo-9-0-9-1-sch-001` | 1 | `equal` | 6 / 3 | — |
| `kicad-demo-9-0-9-1-sch-002` | 3 | `equal` | 244 / 117 | — |
| `kicad-demo-9-0-9-1-sch-005` | 2 | `equal` | 236 / 111 | — |
| `kicad-demo-9-0-9-1-sch-007` | 1 | `equal` | 32 / 10 | — |
| `kicad-demo-9-0-9-1-sch-008` | 1 | `refused` | — | read: UnsupportedFormatError |
| `kicad-demo-9-0-9-1-sch-009` | 1 | `equal` | 33 / 9 | — |
| `kicad-demo-9-0-9-1-sch-010` | 1 | `equal` | 17 / 6 | — |
| `kicad-demo-9-0-9-1-sch-011` | 1 | `equal` | 51 / 14 | — |
| `kicad-demo-9-0-9-1-sch-012` | 1 | `refused` | — | read: UnsupportedFormatError |
| `kicad-demo-9-0-9-1-sch-013` | 1 | `refused` | — | read: UnsupportedFormatError |
| `kicad-demo-9-0-9-1-sch-014` | 1 | `refused` | — | read: UnsupportedFormatError |
| `kicad-demo-9-0-9-1-sch-015` | 1 | `equal` | 4 / 2 | — |
| `kicad-demo-9-0-9-1-sch-016` | 1 | `equal` | 259 / 100 | — |

Counts in this table are for the whole owner, not an isolated child. The JSON
maps every target row to all of its physical instances. Repeated roots retain
all annotations rather than treating saved child references as standalone parts.

Existing source-definition conflict and unsupported-format refusals remain
visible. A child whose real owner refuses is not declared equivalent because
a different standalone interpretation might load. Four authored strict-guard
regressions still pass; no finding or comparison rule was normalized away.

| Naming owner | Row contexts | Drawn names compared | Different names |
|---|---:|---:|---:|
| `kicad-demo-10-0-6-sch-032` | 3 | 135 | 3 |
| `kicad-demo-10-0-6-sch-041` | 5 | 47 | 1 |
| `kicad-demo-10-0-6-sch-069` | 2 | 71 | 4 |
| `kicad-demo-10-0-6-sch-077` | 8 | 300 | 123 |
| `kicad-demo-9-0-9-1-sch-005` | 2 | 11 | 1 |
| `kicad-demo-9-0-9-1-sch-016` | 1 | 69 | 11 |

Literal measurement: `uv run pytest tests/kicad/schematic/test_drawn_corpus.py -q -rA --tb=short`,
with the external cache, required `kicad,corpus` and the recorded source commit.
All reports survive and no copied or derived CAD file remains. Required native
CI jobs, naming validation, Altium acceptance and task 7.2 remain open.
