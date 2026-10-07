# Altium round trips: RT-A0, RT-A1, RT-A2 and RT-A3

Results of the four round-trip levels of Altium files (changes c0044 and c0090,
`fenolite.backends.altium.roundtrip` and `rta3`, and the stages `roundtrip.rta0`, `roundtrip.rta1`,
`roundtrip.rta2` and the opt-in `roundtrip.rta3` of `fenolite check`). The public files are the rows of `tests/corpus/manifest.toml`
with the use `rta`; they are fetched into the corpus cache by `tools/corpus_fetch.py` and never
committed. This page names rows by id and holds kinds, sizes, stream names and counts only.

## The levels

- **RT-A0, container copy.** A compound file is read, written again by Fenolite's compound writer and
  read again. The level holds when both readings have the same storage paths and stream paths and
  every stream has the same bytes. The sector layout, CLSIDs, state bits and times are not part of it.
- **RT-A1, records per stream.** A file is read, every stream the reader types is encoded from what
  was read, and the encoded streams are read again. The level holds when every stream gives equal
  records: the same count, and each record equal in every key spelling, key order, raw value and kept
  byte. `bytes_equal` counts the streams whose encoded bytes also equal the bytes read.
- **RT-A2, model → Altium → model.** The model that a build stored in `.fenolite/` is compared with
  the reading of the documents the build wrote, inside the written scope (`docs/altium.md`,
  "Round trips") and within 2 nm. It is judged on Fenolite's own builds only. Since change c0090 the
  stored model holds the board that was written, so footprints, pads and copper are compared.
- **RT-A3, Altium → model → Altium → model.** A document is read, its model is written as new
  documents, and those are read again. The level holds when the two models are equal inside the
  written scope within 2 nm, once the items that the write reports as not written are taken out of the
  first model. What the write leaves out is counted per kind and is not part of the verdict.

## Reasons for an unjudged level

A level that is not judged is neither a pass nor a failure; it is counted by reason.

| reason | level | meaning |
|---|---|---|
| `too-large` | RT-A0 | the file needs DIFAT sectors, which the compound writer does not write |
| `writer-refused` | RT-A0 | the compound writer refuses the tree (an empty storage, or a name it does not write) |
| `not-a-container` | RT-A0 | the file is text (an ASCII schematic or a project file), so there is no container to copy |
| `native-input` | RT-A2 | the files were not written by a Fenolite build; the level of such files is RT-A3 |
| `model-predates-board` | RT-A2 | the project was built before change c0090: its stored model holds no footprint, and its PCB document holds some |
| `no-document` | RT-A3 | the write gave no document of the kind that was read: the schematic writer refuses the circuit of the project |

## The run

run: 2026-10-05, commit `5fb8ba31`, macOS, local corpus cache, with the heavy row
(`FENOLITE_HEAVY=1`):
`FENOLITE_REQUIRE=corpus FENOLITE_CENSUS_OUT=… uv run pytest tests/corpus/test_altium_roundtrip.py tests/corpus/test_altium_documents.py`,
73 tests passed.

| level | rows | judged | passed | not judged | level label | hypothesis |
|---|---|---|---|---|---|---|
| RT-A0 | 65 | 57 | 57 | 8 (`too-large` 2, `not-a-container` 6, `writer-refused` 0) | `INFERRED` | `H-A-VER-RTA0` pending: the judged PCB libraries come from two repositories |
| RT-A1 | 65 | 65 | 65 | 0 | `INFERRED` | `H-A-VER-RTA1` pending, for the same reason |
| RT-A2 | 21 builds | 21 | 21 | 0 | `INFERRED` | `H-A-VER-RTA2-3` (run of 2026-10-06, section "RT-A2") |
| RT-A3 | 8 PCB documents, 5 project sets | 8 documents, 2 sets | 8 documents, 2 sets | 3 sets (`no-document`) | `INFERRED` (the stage) | `H-A-VER-RTA3` confirmed, `CORPUS-VERIFIED` since change c0127: the eight documents are equal; `H-A-VER-RTA3-PRJ` pending: three sets are not judged (run of 2026-10-06, section "RT-A3") |

- **Repositories per compound kind** (judged rows of RT-A0): PCB documents 5, PCB libraries
  2, schematic documents 5, schematic libraries 3. The criterion of
  `H-A-VER-RTA0` and `H-A-VER-RTA1` asks for three per kind, so both rows stay `INFERRED` although
  every judged row passes; `tests/corpus/test_altium_roundtrip.py` pins the count (`SHORT_OF_THREE`).
- **`H-A-VER-WRITER`** holds: no row is `writer-refused`. The only files the compound writer cannot
  copy are the two PCB documents that need DIFAT sectors.
- **`H-A-VER-BYTES`** holds: on every row the encoded bytes of every typed stream equal the bytes
  read (450 of 450 typed streams, 111628 records). No stream has
  `bytes_equal` false, so no `check.rta1-normalised` info is given on the corpus.
- **Read time of RT-A1** (two readings and one encoding per row): 10.7 s over the 65 rows, of
  which 4.4 s for the largest PCB document.
- No row is refused by a reader.

## RT-A0

| row id | kind | bytes | licence | judged | passed | streams | FAT sectors | DIFAT sectors | reason |
|---|---|---|---|---|---|---|---|---|---|
| `altium-third-party-pcbdoc-01` | `altium_pcbdoc` | 10078208 | LGPL-3.0 | no | — | 158 | 154 | 1 | `too-large` |
| `altium-third-party-pcbdoc-02` | `altium_pcbdoc` | 6730752 | Apache-2.0 | yes | yes | 122 | 103 | 0 |  |
| `altium-third-party-pcbdoc-03` | `altium_pcbdoc` | 2793984 | Apache-2.0 | yes | yes | 121 | 43 | 0 |  |
| `altium-third-party-pcbdoc-04` | `altium_pcbdoc` | 2471424 | MIT | yes | yes | 99 | 38 | 0 |  |
| `altium-third-party-pcbdoc-05` | `altium_pcbdoc` | 1696256 | BSD-2-Clause | yes | yes | 108 | 26 | 0 |  |
| `altium-third-party-pcbdoc-06` | `altium_pcbdoc` | 1421312 | MIT | yes | yes | 116 | 22 | 0 |  |
| `altium-third-party-pcbdoc-07` | `altium_pcbdoc` | 2900480 | MIT | yes | yes | 103 | 45 | 0 |  |
| `altium-third-party-pcbdoc-08` | `altium_pcbdoc` | 23181312 | MIT | no | — | 168 | 354 | 2 | `too-large` |
| `altium-third-party-pcblib-01` | `altium_pcblib` | 99840 | MIT | yes | yes | 22 | 2 | 0 |  |
| `altium-third-party-pcblib-02` | `altium_pcblib` | 119296 | MIT | yes | yes | 70 | 2 | 0 |  |
| `altium-third-party-pcblib-03` | `altium_pcblib` | 103936 | GPL-2.0 | yes | yes | 25 | 2 | 0 |  |
| `altium-third-party-pcblib-04` | `altium_pcblib` | 105984 | GPL-2.0 | yes | yes | 24 | 2 | 0 |  |
| `altium-third-party-schdoc-01` | `altium_schdoc_binary` | 23040 | LGPL-3.0 | yes | yes | 3 | 1 | 0 |  |
| `altium-third-party-schdoc-02` | `altium_schdoc_binary` | 210432 | LGPL-3.0 | yes | yes | 3 | 4 | 0 |  |
| `altium-third-party-schdoc-03` | `altium_schdoc_binary` | 131072 | MIT | yes | yes | 3 | 2 | 0 |  |
| `altium-third-party-schdoc-04` | `altium_schdoc_binary` | 750080 | MIT | yes | yes | 3 | 12 | 0 |  |
| `altium-third-party-schdoc-05` | `altium_schdoc_binary` | 23040 | LGPL-3.0 | yes | yes | 3 | 1 | 0 |  |
| `altium-third-party-schdoc-06` | `altium_schdoc_binary` | 23552 | LGPL-3.0 | yes | yes | 3 | 1 | 0 |  |
| `altium-third-party-schdoc-07` | `altium_schdoc_binary` | 52224 | LGPL-3.0 | yes | yes | 3 | 1 | 0 |  |
| `altium-third-party-schdoc-08` | `altium_schdoc_binary` | 17920 | LGPL-3.0 | yes | yes | 3 | 1 | 0 |  |
| `altium-third-party-schdoc-09` | `altium_schdoc_binary` | 134144 | MIT | yes | yes | 3 | 3 | 0 |  |
| `altium-third-party-schdoc-10` | `altium_schdoc_binary` | 230400 | MIT | yes | yes | 3 | 4 | 0 |  |
| `altium-third-party-schdoc-11` | `altium_schdoc_binary` | 142848 | MIT | yes | yes | 3 | 3 | 0 |  |
| `altium-third-party-schdoc-12` | `altium_schdoc_binary` | 344576 | MIT | yes | yes | 3 | 6 | 0 |  |
| `altium-third-party-schdoc-13` | `altium_schdoc_binary` | 214528 | Apache-2.0 | yes | yes | 3 | 4 | 0 |  |
| `altium-third-party-schdoc-14` | `altium_schdoc_binary` | 31744 | MIT | yes | yes | 3 | 1 | 0 |  |
| `altium-third-party-schdoc-15` | `altium_schdoc_binary` | 1899008 | MIT | yes | yes | 3 | 29 | 0 |  |
| `altium-third-party-schdoc-16` | `altium_schdoc_binary` | 481792 | MIT | yes | yes | 3 | 8 | 0 |  |
| `altium-third-party-schdoc-17` | `altium_schdoc_binary` | 225280 | MIT | yes | yes | 3 | 4 | 0 |  |
| `altium-third-party-schdoc-18` | `altium_schdoc_binary` | 220160 | MIT | yes | yes | 3 | 4 | 0 |  |
| `altium-third-party-schdoc-19` | `altium_schdoc_binary` | 479744 | MIT | yes | yes | 3 | 8 | 0 |  |
| `altium-third-party-schdoc-20` | `altium_schdoc_binary` | 479744 | MIT | yes | yes | 3 | 8 | 0 |  |
| `altium-third-party-schdoc-21` | `altium_schdoc_binary` | 630784 | MIT | yes | yes | 3 | 10 | 0 |  |
| `altium-third-party-schdoc-22` | `altium_schdoc_binary` | 596480 | MIT | yes | yes | 3 | 10 | 0 |  |
| `altium-third-party-schdoc-23` | `altium_schdoc_binary` | 591872 | MIT | yes | yes | 3 | 10 | 0 |  |
| `altium-third-party-schdoc-24` | `altium_schdoc_binary` | 390656 | MIT | yes | yes | 3 | 6 | 0 |  |
| `altium-third-party-schdoc-25` | `altium_schdoc_binary` | 325632 | MIT | yes | yes | 3 | 5 | 0 |  |
| `altium-third-party-schdoc-26` | `altium_schdoc_binary` | 151552 | LGPL-3.0 | yes | yes | 3 | 3 | 0 |  |
| `altium-third-party-schdoc-27` | `altium_schdoc_binary` | 37888 | LGPL-3.0 | yes | yes | 3 | 1 | 0 |  |
| `altium-third-party-schdoc-28` | `altium_schdoc_binary` | 118784 | LGPL-3.0 | yes | yes | 3 | 2 | 0 |  |
| `altium-third-party-schdoc-29` | `altium_schdoc_binary` | 87552 | LGPL-3.0 | yes | yes | 3 | 2 | 0 |  |
| `altium-third-party-schdoc-30` | `altium_schdoc_binary` | 212480 | LGPL-3.0 | yes | yes | 3 | 4 | 0 |  |
| `altium-third-party-schdoc-31` | `altium_schdoc_binary` | 28672 | LGPL-3.0 | yes | yes | 3 | 1 | 0 |  |
| `altium-third-party-schdoc-32` | `altium_schdoc_binary` | 25600 | LGPL-3.0 | yes | yes | 3 | 1 | 0 |  |
| `altium-third-party-schdoc-33` | `altium_schdoc_binary` | 19968 | LGPL-3.0 | yes | yes | 3 | 1 | 0 |  |
| `altium-third-party-schdoc-34` | `altium_schdoc_binary` | 288256 | BSD-2-Clause | yes | yes | 3 | 5 | 0 |  |
| `altium-third-party-schdoc-35` | `altium_schdoc_binary` | 79872 | MIT | yes | yes | 3 | 2 | 0 |  |
| `altium-third-party-schdoc-36` | `altium_schdoc_binary` | 48128 | MIT | yes | yes | 3 | 1 | 0 |  |
| `altium-third-party-schdoc-37` | `altium_schdoc_binary` | 24064 | MIT | yes | yes | 3 | 1 | 0 |  |
| `altium-third-party-schdoc-38` | `altium_schdoc_binary` | 62976 | MIT | yes | yes | 3 | 1 | 0 |  |
| `altium-third-party-schlib-01` | `altium_schlib` | 5120 | MIT | yes | yes | 6 | 1 | 0 |  |
| `altium-third-party-schlib-02` | `altium_schlib` | 5632 | MIT | yes | yes | 6 | 1 | 0 |  |
| `altium-third-party-schlib-03` | `altium_schlib` | 41984 | MIT | yes | yes | 11 | 1 | 0 |  |
| `altium-third-party-schlib-04` | `altium_schlib` | 58880 | MIT | yes | yes | 57 | 1 | 0 |  |
| `altium-third-party-schlib-05` | `altium_schlib` | 119808 | MIT | yes | yes | 43 | 2 | 0 |  |
| `altium-third-party-schlib-06` | `altium_schlib` | 163328 | MIT | yes | yes | 155 | 3 | 0 |  |
| `altium-third-party-schlib-07` | `altium_schlib` | 17408 | MIT | yes | yes | 5 | 1 | 0 |  |
| `altium-third-party-schlib-08` | `altium_schlib` | 69632 | MIT | yes | yes | 51 | 2 | 0 |  |
| `altium-third-party-schlib-09` | `altium_schlib` | 171008 | Apache-2.0 | yes | yes | 77 | 3 | 0 |  |
| `altium-third-party-prjpcb-01` | `altium_prjpcb` | 58425 | MIT | no | — | — | — | — | `not-a-container` |
| `altium-third-party-prjpcb-02` | `altium_prjpcb` | 60907 | LGPL-3.0 | no | — | — | — | — | `not-a-container` |
| `altium-third-party-prjpcb-03` | `altium_prjpcb` | 275609 | MIT | no | — | — | — | — | `not-a-container` |
| `altium-third-party-prjpcb-04` | `altium_prjpcb` | 42994 | BSD-2-Clause | no | — | — | — | — | `not-a-container` |
| `altium-third-party-prjpcb-05` | `altium_prjpcb` | 49883 | Apache-2.0 | no | — | — | — | — | `not-a-container` |
| `altium-third-party-prjpcb-06` | `altium_prjpcb` | 43022 | MIT | no | — | — | — | — | `not-a-container` |

Unjudged files: `altium-third-party-pcbdoc-01` (`too-large`), `altium-third-party-pcbdoc-08` (`too-large`), `altium-third-party-prjpcb-01` (`not-a-container`), `altium-third-party-prjpcb-02` (`not-a-container`), `altium-third-party-prjpcb-03` (`not-a-container`), `altium-third-party-prjpcb-04` (`not-a-container`), `altium-third-party-prjpcb-05` (`not-a-container`), `altium-third-party-prjpcb-06` (`not-a-container`).

## RT-A1

| row id | kind | judged | passed | streams | records | bytes equal | opaque | read ms |
|---|---|---|---|---|---|---|---|---|
| `altium-third-party-pcbdoc-01` | `altium_pcbdoc` | yes | yes | 16 | 8328 | 16 | 142 | 1128 |
| `altium-third-party-pcbdoc-02` | `altium_pcbdoc` | yes | yes | 16 | 1843 | 16 | 106 | 917 |
| `altium-third-party-pcbdoc-03` | `altium_pcbdoc` | yes | yes | 16 | 2643 | 16 | 105 | 277 |
| `altium-third-party-pcbdoc-04` | `altium_pcbdoc` | yes | yes | 16 | 819 | 16 | 83 | 321 |
| `altium-third-party-pcbdoc-05` | `altium_pcbdoc` | yes | yes | 16 | 973 | 16 | 92 | 283 |
| `altium-third-party-pcbdoc-06` | `altium_pcbdoc` | yes | yes | 16 | 1769 | 16 | 100 | 288 |
| `altium-third-party-pcbdoc-07` | `altium_pcbdoc` | yes | yes | 16 | 1307 | 16 | 87 | 335 |
| `altium-third-party-pcbdoc-08` | `altium_pcbdoc` | yes | yes | 16 | 29666 | 16 | 152 | 4413 |
| `altium-third-party-pcblib-01` | `altium_pcblib` | yes | yes | 1 | 10 | 1 | 21 | 182 |
| `altium-third-party-pcblib-02` | `altium_pcblib` | yes | yes | 9 | 18 | 9 | 61 | 183 |
| `altium-third-party-pcblib-03` | `altium_pcblib` | yes | yes | 1 | 25 | 1 | 25 | 172 |
| `altium-third-party-pcblib-04` | `altium_pcblib` | yes | yes | 1 | 7 | 1 | 23 | 183 |
| `altium-third-party-schdoc-01` | `altium_schdoc_binary` | yes | yes | 3 | 128 | 3 | 0 | 5 |
| `altium-third-party-schdoc-02` | `altium_schdoc_binary` | yes | yes | 3 | 1184 | 3 | 0 | 44 |
| `altium-third-party-schdoc-03` | `altium_schdoc_binary` | yes | yes | 3 | 682 | 3 | 0 | 24 |
| `altium-third-party-schdoc-04` | `altium_schdoc_binary` | yes | yes | 3 | 3905 | 3 | 6 | 141 |
| `altium-third-party-schdoc-05` | `altium_schdoc_binary` | yes | yes | 3 | 130 | 3 | 0 | 4 |
| `altium-third-party-schdoc-06` | `altium_schdoc_binary` | yes | yes | 3 | 132 | 3 | 0 | 4 |
| `altium-third-party-schdoc-07` | `altium_schdoc_binary` | yes | yes | 3 | 298 | 3 | 0 | 10 |
| `altium-third-party-schdoc-08` | `altium_schdoc_binary` | yes | yes | 3 | 98 | 3 | 0 | 3 |
| `altium-third-party-schdoc-09` | `altium_schdoc_binary` | yes | yes | 3 | 704 | 3 | 0 | 24 |
| `altium-third-party-schdoc-10` | `altium_schdoc_binary` | yes | yes | 3 | 1098 | 3 | 4 | 38 |
| `altium-third-party-schdoc-11` | `altium_schdoc_binary` | yes | yes | 3 | 774 | 3 | 4 | 27 |
| `altium-third-party-schdoc-12` | `altium_schdoc_binary` | yes | yes | 3 | 1736 | 3 | 0 | 63 |
| `altium-third-party-schdoc-13` | `altium_schdoc_binary` | yes | yes | 3 | 1180 | 3 | 1 | 47 |
| `altium-third-party-schdoc-14` | `altium_schdoc_binary` | yes | yes | 3 | 112 | 3 | 0 | 4 |
| `altium-third-party-schdoc-15` | `altium_schdoc_binary` | yes | yes | 3 | 6459 | 3 | 0 | 260 |
| `altium-third-party-schdoc-16` | `altium_schdoc_binary` | yes | yes | 3 | 2515 | 3 | 7 | 90 |
| `altium-third-party-schdoc-17` | `altium_schdoc_binary` | yes | yes | 3 | 1193 | 3 | 6 | 43 |
| `altium-third-party-schdoc-18` | `altium_schdoc_binary` | yes | yes | 3 | 1213 | 3 | 1 | 42 |
| `altium-third-party-schdoc-19` | `altium_schdoc_binary` | yes | yes | 3 | 2597 | 3 | 1 | 107 |
| `altium-third-party-schdoc-20` | `altium_schdoc_binary` | yes | yes | 3 | 2597 | 3 | 1 | 98 |
| `altium-third-party-schdoc-21` | `altium_schdoc_binary` | yes | yes | 3 | 2684 | 3 | 1 | 113 |
| `altium-third-party-schdoc-22` | `altium_schdoc_binary` | yes | yes | 3 | 3164 | 3 | 0 | 116 |
| `altium-third-party-schdoc-23` | `altium_schdoc_binary` | yes | yes | 3 | 3088 | 3 | 1 | 131 |
| `altium-third-party-schdoc-24` | `altium_schdoc_binary` | yes | yes | 3 | 2033 | 3 | 0 | 75 |
| `altium-third-party-schdoc-25` | `altium_schdoc_binary` | yes | yes | 3 | 1776 | 3 | 1 | 63 |
| `altium-third-party-schdoc-26` | `altium_schdoc_binary` | yes | yes | 3 | 818 | 3 | 0 | 37 |
| `altium-third-party-schdoc-27` | `altium_schdoc_binary` | yes | yes | 3 | 215 | 3 | 0 | 10 |
| `altium-third-party-schdoc-28` | `altium_schdoc_binary` | yes | yes | 3 | 708 | 3 | 0 | 28 |
| `altium-third-party-schdoc-29` | `altium_schdoc_binary` | yes | yes | 3 | 525 | 3 | 0 | 21 |
| `altium-third-party-schdoc-30` | `altium_schdoc_binary` | yes | yes | 3 | 1266 | 3 | 0 | 52 |
| `altium-third-party-schdoc-31` | `altium_schdoc_binary` | yes | yes | 3 | 173 | 3 | 0 | 7 |
| `altium-third-party-schdoc-32` | `altium_schdoc_binary` | yes | yes | 3 | 149 | 3 | 0 | 5 |
| `altium-third-party-schdoc-33` | `altium_schdoc_binary` | yes | yes | 3 | 112 | 3 | 0 | 4 |
| `altium-third-party-schdoc-34` | `altium_schdoc_binary` | yes | yes | 3 | 1012 | 3 | 1 | 42 |
| `altium-third-party-schdoc-35` | `altium_schdoc_binary` | yes | yes | 3 | 432 | 3 | 0 | 17 |
| `altium-third-party-schdoc-36` | `altium_schdoc_binary` | yes | yes | 3 | 255 | 3 | 0 | 9 |
| `altium-third-party-schdoc-37` | `altium_schdoc_binary` | yes | yes | 3 | 126 | 3 | 0 | 5 |
| `altium-third-party-schdoc-38` | `altium_schdoc_binary` | yes | yes | 3 | 331 | 3 | 0 | 13 |
| `altium-third-party-schlib-01` | `altium_schlib` | yes | yes | 3 | 14 | 3 | 3 | 0 |
| `altium-third-party-schlib-02` | `altium_schlib` | yes | yes | 4 | 17 | 4 | 2 | 0 |
| `altium-third-party-schlib-03` | `altium_schlib` | yes | yes | 5 | 255 | 5 | 6 | 8 |
| `altium-third-party-schlib-04` | `altium_schlib` | yes | yes | 21 | 262 | 21 | 36 | 9 |
| `altium-third-party-schlib-05` | `altium_schlib` | yes | yes | 13 | 675 | 13 | 30 | 24 |
| `altium-third-party-schlib-06` | `altium_schlib` | yes | yes | 52 | 796 | 52 | 103 | 33 |
| `altium-third-party-schlib-07` | `altium_schlib` | yes | yes | 5 | 82 | 5 | 0 | 3 |
| `altium-third-party-schlib-08` | `altium_schlib` | yes | yes | 18 | 349 | 18 | 33 | 12 |
| `altium-third-party-schlib-09` | `altium_schlib` | yes | yes | 69 | 1196 | 69 | 8 | 41 |
| `altium-third-party-prjpcb-01` | `altium_prjpcb` | yes | yes | 1 | 1999 | 1 | 0 | 4 |
| `altium-third-party-prjpcb-02` | `altium_prjpcb` | yes | yes | 1 | 1592 | 1 | 0 | 3 |
| `altium-third-party-prjpcb-03` | `altium_prjpcb` | yes | yes | 1 | 5355 | 1 | 0 | 21 |
| `altium-third-party-prjpcb-04` | `altium_prjpcb` | yes | yes | 1 | 1389 | 1 | 0 | 3 |
| `altium-third-party-prjpcb-05` | `altium_prjpcb` | yes | yes | 1 | 1302 | 1 | 0 | 3 |
| `altium-third-party-prjpcb-06` | `altium_prjpcb` | yes | yes | 1 | 1335 | 1 | 0 | 2 |

Streams with unequal bytes: none. `opaque` is the number of records kept without a typed class plus the
number of streams kept whole.

## RT-A2

Every script under `examples/` built for the Altium target (`tests/unit/lens/test_altium_rta2.py`), in the
binary and in the ASCII schematic form, and one build with module sheets, run again on 2026-10-06 for
change c0090. Since that change the stored model holds the board that was written, so every kind of the
scope is compared with the PCB reading (`pcb: board` stands for `arc`, `footprint`, `netclass`, `pad`,
`track`, `via` and `zone`), and no kind is only counted. `board entities compared` gives the entities
that the stored board and the PCB document both hold (`docs/altium.md`, "Round trips").

| build | schematic form | holds | differences | kinds compared | board entities compared |
|---|---|---|---|---|---|
| `examples/altium_hier/design.py` | binary | yes | 0 | schematic: component, net, no_connect | — |
| `examples/altium_hier/design.py` | ascii | yes | 0 | schematic: component, net, no_connect | — |
| `examples/altium_hier/partial.py` | binary | yes | 0 | schematic: component, net, no_connect | — |
| `examples/altium_hier/partial.py` | ascii | yes | 0 | schematic: component, net, no_connect | — |
| `examples/altium_hier_board/design.py` | binary | yes | 0 | schematic: component, net, no_connect; pcb: board | footprint 3; pad 36 |
| `examples/altium_hier_board/design.py` | ascii | yes | 0 | schematic: component, net, no_connect; pcb: board | footprint 3; pad 36 |
| `examples/altium_kicad/design.py` | binary | yes | 0 | schematic: component, net, no_connect | — |
| `examples/altium_kicad/design.py` | ascii | yes | 0 | schematic: component, net, no_connect | — |
| `examples/altium_kicad/no_connect.py` | binary | yes | 0 | schematic: component, net, no_connect | — |
| `examples/altium_kicad/no_connect.py` | ascii | yes | 0 | schematic: component, net, no_connect | — |
| `examples/altium_sample/design.py` | binary | yes | 0 | schematic: component, net, no_connect | — |
| `examples/altium_sample/design.py` | ascii | yes | 0 | schematic: component, net, no_connect | — |
| `examples/blink_2layer/design.py` | binary | yes | 0 | schematic: component, net, no_connect; pcb: board | footprint 3; pad 36 |
| `examples/blink_2layer/design.py` | ascii | yes | 0 | schematic: component, net, no_connect; pcb: board | footprint 3; pad 36 |
| `examples/blink_official/design.py` | binary | yes | 0 | schematic: component, net, no_connect; pcb: board | footprint 3; pad 36 |
| `examples/blink_official/design.py` | ascii | yes | 0 | schematic: component, net, no_connect; pcb: board | footprint 3; pad 36 |
| `examples/blink_routed/design.py` | binary | yes | 0 | schematic: component, net, no_connect; pcb: board | footprint 3; pad 36; track 11; via 7 |
| `examples/blink_routed/design.py` | ascii | yes | 0 | schematic: component, net, no_connect; pcb: board | footprint 3; pad 36; track 11; via 7 |
| `examples/board_40parts/design.py` | binary | yes | 0 | schematic: component, net, no_connect; pcb: board | footprint 40; pad 140; via 2; zone 2 |
| `examples/board_40parts/design.py` | ascii | yes | 0 | schematic: component, net, no_connect; pcb: board | footprint 40; pad 140; via 2; zone 2 |
| `examples/altium_hier/design.py` | binary (module sheets) | yes | 0 | schematic: component, net, no_connect | — |

What RT-A2 proves today: the schematic writers and the schematic import agree on every component
(reference and value), every net (name and members) and every no-connect mark of the 21 builds, and
the PCB document writer and its import agree on the net class names and, since change c0090, on every
footprint (position, rotation, side), pad (number, net, position, size), track, arc, via and zone of
the eleven builds with a PCB document. `H-A-VER-RTA2`, which claimed this when no built model held a
footprint, and `H-A-VER-RTA2-2`, which bounded the claim to what the built model held, are refuted rows;
`H-A-VER-RTA2-3` is their successor. What it does not prove: anything about a field outside the scope,
about arcs beyond the examples (section "RT-A3": the points of an arc that is derived from three points,
as a build derives it, can come back more than 2 nm away),
and nothing about Altium Designer, which reads none of these files here. The first probe found one difference
inside the scope, which was fixed in the build: a component whose value is empty in the script was
written with its symbol's name as the comment, and the built model now stores that value.

## RT-A3

A document is read, its model is written as new Altium documents under a temporary folder, and those
are read again (change c0090; `fenolite.backends.altium.rta3`, the stage `roundtrip.rta3` and
`fenolite roundtrip PATH --level rta3`). The two models are compared inside the written scope
(`docs/altium.md`, "Written scope") within 2 nm, after the items that the write reports as not written
are taken out of the first model. What a rewrite does not hold is counted and is not part of the
verdict: **a rewrite is not a copy of the document**.

run: 2026-10-06, the commit of change c0090 on `0e1a6f4e` (run again after the rebase), macOS, local corpus cache, with
the heavy rows (`FENOLITE_HEAVY=1`):
`FENOLITE_REQUIRE=corpus FENOLITE_CENSUS_OUT=… uv run pytest tests/corpus/test_altium_rta3.py`, 15 tests
passed.
Run again on 2026-10-06 with change c0127 (arcs keep their record), with the heavy rows:
`FENOLITE_HEAVY=1 uv run pytest tests/corpus/test_altium_rta3.py -q`, 15 tests passed.
Run again on 2026-10-07 with change c0128 (the trip writes with `rewrite=True`), with the heavy rows:
the same command, 16 tests passed (one more test, on the vias of one document); the table holds that run.

**PCB documents** (every row with the use `rta` that is a PCB document, read alone). `written` counts
model items; the last three columns are what the rewrite does not hold: model items by kind, records
of the document that the import maps to no model entity (by the category of its census), and the
number of storages that the import keeps as bytes (a rewrite holds Fenolite's own content there).

| document | inside the scope | footprints | pads | tracks | arcs | vias | zones | model items not written | records without a model entity | storages kept as bytes |
|---|---|---|---|---|---|---|---|---|---|---|
| `altium-third-party-pcbdoc-01` | equal | 252 | 735 | 1346 | 0 | 646 | 5 | body 247; copper-shape 47; footprint 8; graphic 20; outline 8; pad 10; plane 2; zone-fill 5 | footprint-graphics 3469; shape-based-regions 90; plane-cuts 74; pour-primitives 40; polygons 8; classes 38 | 15 |
| `altium-third-party-pcbdoc-02` | equal | 41 | 141 | 191 | 0 | 242 | 10 | body 42; copper-shape 17; graphic 16; outline 8; pad 2; text 1; zone 2; zone-fill 9 | footprint-graphics 602; shape-based-regions 91; plane-cuts 43; pour-primitives 35; polygons 6; classes 14 | 17 |
| `altium-third-party-pcbdoc-03` | equal | 55 | 377 | 604 | 0 | 47 | 1 | body 50; graphic 1; pad 8; rule 1; zone-fill 1 | footprint-graphics 846; shape-based-regions 23; classes 20 | 18 |
| `altium-third-party-pcbdoc-04` | equal | 17 | 53 | 149 | 0 | 67 | 9 | body 33; copper-shape 2; graphic 12; outline 4; zone-fill 9 | footprint-graphics 315; shape-based-regions 27; classes 16; bad-geometry 1 | 19 |
| `altium-third-party-pcbdoc-05` | equal | 27 | 68 | 194 | 0 | 59 | 2 | body 23; copper-shape 1; graphic 4; pad 32; rule 1; zone-fill 2 | footprint-graphics 271; shape-based-regions 24; classes 14; region-holes 9 | 17 |
| `altium-third-party-pcbdoc-06` | equal | 27 | 102 | 111 | 3 | 42 | 10 | body 27; copper-shape 20; graphic 23; outline 1; pad 4; text 2; zone-fill 10 | footprint-graphics 1074; shape-based-regions 42; classes 18 | 18 |
| `altium-third-party-pcbdoc-07` | equal | 14 | 97 | 475 | 20 | 60 | 5 | body 24; copper-shape 6; graphic 12; outline 2; pad 19; zone 4; zone-fill 5 | footprint-graphics 307; shape-based-regions 31; classes 16; bad-geometry 1 | 20 |
| `altium-third-party-pcbdoc-08` | equal | 544 | 2115 | 8355 | 529 | 1770 | 27 | body 1298; copper-shape 33; graphic 1069; outline 1; pad 21; text 311; zone 6; zone-fill 27 | footprint-graphics 9763; shape-based-regions 292; classes 33; region-holes 6; bodies 4 | 26 |

- **The 8 documents are equal** inside the scope since change c0127; the seven that are not heavy come
  from six repositories, and the criterion of `H-A-VER-RTA3` asks for three. The row is confirmed and
  `CORPUS-VERIFIED` (decision of the maintainer, 2026-10-07); the eighth document is heavy and runs only
  with `FENOLITE_HEAVY=1`.
- **What `CORPUS-VERIFIED` means here, and what it does not.** It means: Fenolite reads its own rewrite
  of a public Altium PCB document back to an equal model inside the written scope, on every listed
  document; and KiCad's importer reads the rewrite as Fenolite does at the levels 1 to 5 of `equivalent`
  (`H-A-VER-RTA3-KICAD`, below, on the seven documents that are not heavy). It says **nothing about
  Altium opening a written file**: that stays `INFERRED` until the kit run (changes c0091 and c0092).
  The scope leaves out the graphics of footprints (until c0126), component bodies (until c0121) and
  the model items that are not written, which the table above counts per kind. No `roundtrip_exact`
  cell is set and no write kind leaves `experimental` by this level. The stage `roundtrip.rta3`, a
  verdict and an envelope stay `INFERRED`: the constant `roundtrip.EVIDENCE_RT_A3` carries the row's
  level, and it is combined with the import's evidence, which is `INFERRED`.
- **Arcs** (change c0127). Before it, the heavy row `altium-third-party-pcbdoc-08` differed: 7 of its
  517 written arcs came back with a point moved by 3 nm or more (14 changes: each arc once per side),
  12 more arcs were not written because their three points lie on one line, and nothing else differed.
  The cause is the form of an arc: its record holds a centre, a radius and two angles, and the model
  holds three points. A record that is derived from the points has a centre and a radius that are each
  rounded to a unit of 2.54 nm, and for a short arc (a radius near 100 nm is among them) it is another
  circle. An arc that was read now keeps the centre, the radius and the angles of its record in its
  `altium` bag, and the write gives that record back while it still says the arc's three points within
  2 nm. Measured after: the 529 copper arcs of the document are written, all from their record, and
  each point comes back at 0 nm; the same holds for the 23 copper arcs and the 8 written arc graphics
  of the two other documents with arcs (2 nm and 1 nm at most before). An arc that was moved in the
  model, and an arc of a script, is still derived from its three points, so this limit still bounds
  RT-A2 for a script with short arcs.
- **What is not written, and why** (the seven documents that are not heavy, counted by reason): 446
  component bodies (no body record is written); 93 shapes on copper (fills and regions, which the
  model holds as graphics); 88 graphics and 2 texts on layers without a layer in the written document
  (mechanical layers, the keep-out layer, the drill drawing), and 1 text with a line break; 75 pads (59
  with a per-layer pad stack, 10 on a layer that is no outer copper layer, 4 without a number, 2 with a
  custom shape), and with them 8 free pads; no via since change c0128 (see below);
  6 zones whose outline has an arc (the model holds no outline for them); 41 poured fills (a polygon
  is written unpoured); 22 arcs of board outlines, written as two straight edges, and one board without
  a closed outline; 2 planes without a net of the document, written as signal layers; 2 rules (one of
  them since change c0125: the clearance rule with layers that the import now reads on
  `altium-third-party-pcbdoc-03`, which no rule record is written for; that row was run again on
  2026-10-06 and is still equal).
- **Lines on internal planes are no model items** (change c0124, measured again on 2026-10-06 with
  the heavy rows, 15 tests passed). The two documents with planes hold 74 and 43 free tracks without a
  net on their plane layers: the lines that cut the planes. The import read them as tracks until change
  c0124. On `-01`, whose planes are written as signal layers (`plane 2`), a rewrite then held those 74
  lines as copper tracks on two signal layers, which is the opposite of the board that was read; on
  `-02` the 43 were refused by the writer (`track 43`). Both rows now count them as records without a
  model entity (`plane-cuts`), `-01` writes 1 346 tracks instead of 1 420, and `-02` writes the same
  191. No other count of the table moved, both rows stay equal inside the scope, and RT-A0 and RT-A1
  are untouched: they compare the records, which the readers keep.
- **Vias whose drill equals their diameter** (change c0128; `H-A-PCBX-VIA-FULL`). 48 of the 242 via
  records of `altium-third-party-pcbdoc-02` hold a hole equal to the diameter: ordinary through vias
  on a net, with nothing else that marks them; no via record of the eight documents (2 933) holds a
  hole above its diameter. The via writer refuses such a via (c0038), and until c0128 the rewrite left
  the 48 out and counted them. The trip of RT-A3 is the rewrite of a document that was read and now
  says so (`rewrite=True`): the 242 vias are written and equal, and `via` left the column. A write of
  the same model that is not a rewrite still leaves the 48 out, and a build from a script refuses
  such a via as before. The 43 lines on the internal planes of the same document are another matter:
  they are no model items since change c0124 (above).
- **Footprint graphics are the largest count**: the lines, arcs and texts of the footprints are records
  that the import maps to no model entity, because a footprint instance of the model holds pads only.
  A rewritten board has its pads and no silkscreen of its footprints. Decision of 2026-10-06: change
  c0126 gives a footprint of the model its graphics, corner ratio and library.

**Project sets** (c0043's sets, read through the project file, so the circuit comes from the
schematics; `H-A-VER-RTA3-PRJ`). A set is judged when the schematic writer takes the circuit: the
schematic of a rewrite is generated from the circuit, with generic symbols on one sheet.

| set | inside the scope | what was compared, or why not | `netlist.assignment_compare` |
|---|---|---|---|
| `altium-set:01` | not judged (`no-document`) | the PCB document is written; a comment starts with `=`, which Altium reads as a reference to another parameter; the schematic writer refuses it | — |
| `altium-set:02` | not judged (`no-document`) | the PCB document is written; the import puts one pin on two nets, and the schematic writer refuses that circuit | — |
| `altium-set:03` | equal | circuit and board | original: none; rewrite: netlist.uncovered (info) |
| `altium-set:04` | not judged (`no-document`) | the PCB document is written; a comment holds characters outside Windows-1252, which no form of the schematic holds | — |
| `altium-set:05` | equal | circuit and board | original: none; rewrite: netlist.uncovered (info) |

Two of five sets are equal; three are not judged, each for a text or a circuit that the schematic
writer of the build refuses. `H-A-VER-RTA3-PRJ` therefore stays `INFERRED` and pending: its criterion
asks for the five sets. Decision of the maintainer, 2026-10-06: v0.3 records the sets 01, 02 and 04 as
not judged; a tolerant schematic write for circuits that were read belongs to v0.5a, with `convert`.

Measured again on 2026-10-06 after the rebase onto the changes c0083 (repeated sheets, pin-to-pad maps)
and c0088: no verdict and no count of the tables above moved. The three sets are refused for the same
three reasons; in particular the import of `altium-set:02` still puts one pin on two nets. What the
rebase adds is counted as not written, because the generated schematic is one sheet of generic
symbols: 17 modules of `altium-set:01`, 23 modules and one pin-to-pad map of `altium-set:02`; no
module of these sets carries a channel index. The sets 03 and 05 hold no module and no map. On the two equal sets the rewrite gets one `netlist.uncovered` info that the
original does not have: the pins of the pads that were not written have no pad on the rewrite.

**KiCad's importer on the rewrites** (`H-A-VER-RTA3-KICAD`; `tests/kicad/altium/test_rta3_oracle.py` on
`kicad-cli` 10.0.6, probe `altium-rta3-kicad` `equal`). `kicad-cli pcb import` reads each rewrite, and its
read is compared with Fenolite's read of the same rewrite at the levels 1 to 5 of `equivalent` under the
profile `kicad-import`. The columns give what each level compared.

| rewrite of | components | pad nets | pads | placements | routed nets | differences | excluded |
|---|---|---|---|---|---|---|---|
| `tests/data/altium/routed/routed.PcbDoc` | 3 | 36 | 36 | 3 | 4 | 0 | 0 |
| `tests/data/altium/board6/board6.PcbDoc` | 3 | 36 | 36 | 3 | 4 | 0 | 0 |
| `altium-third-party-pcbdoc-01` | 247 | 719 | 729 | 247 | 153 | 0 | 0 |
| `altium-third-party-pcbdoc-02` | 41 | 141 | 141 | 41 | 32 | 0 | 0 |
| `altium-third-party-pcbdoc-03` | 52 | 204 | 209 | 52 | 54 | 0 | 0 |
| `altium-third-party-pcbdoc-04` | 15 | 50 | 51 | 15 | 10 | 0 | 0 |
| `altium-third-party-pcbdoc-05` | 23 | 64 | 64 | 23 | 30 | 0 | 0 |
| `altium-third-party-pcbdoc-06` | 27 | 102 | 102 | 27 | 17 | 0 | 0 |
| `altium-third-party-pcbdoc-07` | 12 | 95 | 95 | 12 | 21 | 0 | 0 |

No difference and no exclusion on the two own documents and on the seven public documents that are
not heavy. Run again on 2026-10-07 with change c0128: the rewrites are written with `rewrite=True`, so the
rewrite of `altium-third-party-pcbdoc-02` holds its 48 vias with a hole equal to the diameter; the table is
unchanged (11 tests passed), and level 5, which compares the vias of each net, finds no difference. This says that a second reader, which shares no code with Fenolite, reads a rewritten
document as Fenolite does. It does not say that Altium Designer opens one: no rewrite was opened in
Altium.

## Project sets

`fenolite check` on each public project set (c0043's "Altium project sets"), laid out as its project
folder under pytest's temporary directory. The pair is (`schematic`, `pcb`) of
`netlist.assignment_compare`; c0043's own comparison, which gives a pin every pad of its map, judges the
sets (`H-A-IMP-NETLIST`), so a difference here does not fail the test. Since change c0083 the imported
components carry the pin-to-pad map of their footprint model, one pad per pin, and this stage applies it.

| set | documents | listed and missing | common | only schematic | only PCB | differences | floating pins | undriven power nets | No ERC marks | exit |
|---|---|---|---|---|---|---|---|---|---|---|
| `altium-set:01` | 20 | 6 | 2016 | 6 | 33 | 0 | 50 | 12 | 90 | 5 |
| `altium-set:02` | 15 | 2 | 694 | 7 | 31 | 2 | 20 | 12 | 5 | 5 |
| `altium-set:03` | 3 | 0 | 96 | 0 | 0 | 0 | 0 | 4 | 1 | 5 |
| `altium-set:04` | 3 | 2 | 139 | 0 | 4 | 0 | 0 | 6 | 0 | 5 |
| `altium-set:05` | 6 | 1 | 106 | 0 | 0 | 0 | 0 | 0 | 10 | 5 |

- Every set exits 5: `model.validate` reports `model.*` error findings of the PCB reading on each of
  them (`model.body-height` on the four sets without a heavy row, and `model.duplicate-ref` on
  `altium-set:02`, whose PCB document holds twelve components without a designator: the empty
  reference is counted twelve times, which is a finding about the validation rule, not about channels; it waits for the follow-up that gives a component without a reference a finding of its own), which the check passes on unchanged. The container stages pass on every set: no
  `check.rta0-failed` and no `check.rta1-failed`.
- `altium-set:02` shows 694 common elements, 2 differing, 7 that only the schematic covers and 31
  that only the PCB document covers (measured again on 2026-10-06, change c0083, with the channels
  named and the pin-to-pad map applied). The row read 508, 4, 26 and 217 before the change, and 688,
  2, 13 and 37 after its first part: one sheet of the set is named by twelve sheet symbols, and the
  schematic reading gave its 84 components the designators of the sheet, twelve times each, where
  the board has one designator per channel. The schematic reading now names a channel's components
  with the project's designator format, as the board does (`H-A-IMP-RPT-FORMAT`), which accounts for
  180 of the 217. The pin-to-pad map (`H-A-IMP-PINMAP`) accounts for 6 more on each side: six pins of
  one connector whose pads have names of their own. What remains, by cause:
  - **7 only in the schematic and 7 only in the PCB document:** two components (2 and 5 pins) that
    the board shows under another designator than their sheet; the comparison is by designator. The
    project import links them by their unique-id path.
  - **18 only in the PCB document:** pads that no pin of the sheets stands for (mounting and
    thermal pads, and further pads of one pin whose map names none of them), the count c0043's
    comparison reports as "pads without a pin".
  - **4 only in the PCB document:** the further pads of two pins whose map lists several pads (two
    and four). The model's map gives a pin one pad, so one pad of each is compared;
    `altium.import.pin-map` counts the two records.
  - **2 only in the PCB document:** the pads of the twelve components that the board holds without
    a designator, which fall onto two elements.
  - **2 differing:** two pins that are unwired on their sheet and carry a net in the PCB document,
    the known difference of c0043.
  None of these is a pin of the repeated sheet: of the pins of its 84 channel components none is on
  one side only and none differs (`H-A-IMP-RPT-NETS`,
  `tests/corpus/test_altium_channels.py::test_nets_of_the_channels_agree_with_the_board`). The other
  four rows did not change with the map, set 01 included (measured with `FENOLITE_HEAVY=1`): their
  sheets hold no map record that names another pad (set 01 holds 55 records with an empty pin,
  which are left out). It is the set that c0043 lists as a known difference
  (`altium-import:known-diff`); c0043's count is in groups of pads, not in elements. Its row was measured again on 2026-10-05 after the
  rebase onto c0045, which gives a board component the designator text the board shows: before that
  change the row read 528 common, 6, 30 and 17 differences. The other four rows did not change.
- **`H-A-VER-ERC`** holds on the five sets: no `erc.lite.floating-pin` warning names a pin that
  carries a No ERC mark or that a net lists.
- The envelope level of every set is `INFERRED`.

## Light DRC over the corpus

The stage `copper.clearance` on each public PCB document, and the parity comparison on each public project
set (change c0088, with the Clearance forms of change c0125; `tests/corpus/test_altium_copper.py`, run on
2026-10-06 on macOS without any tool, with `FENOLITE_HEAVY=1` so that `altium-set:01` and the heavy
document are included). The parity table was measured again on the tree that holds the channel net names
and the pin-to-pad map of c0083. Counts only. A third-party board may hold real findings: the test
asserts what the stage promises, not that a board is clean.

| document | fills, pads, tracks, arcs, vias | pairs judged | shorts | clearance | mapped and opaque Clearance rules | unpoured | zones without a clearance | planes | findings the unit's slack removes | level |
|---|---|---|---|---|---|---|---|---|---|---|
| `altium-third-party-pcbdoc-01` | 40, 735, 1 346, 0, 646 | 10 482 | 0 | 2 | 1, 0 | 0 | 0 | 2 | 626 | `UNVERIFIED` |
| `altium-third-party-pcbdoc-02` | 11, 143, 191, 0, 242 | 553 | 0 | 0 | 0, 1 | 1 | 11 | 2 | 0 | `UNVERIFIED` |
| `altium-third-party-pcbdoc-03` | 6, 383, 604, 0, 47 | 3 204 | 0 | 7 | 2, 0 | 0 | 0 | 0 | 359 | `INFERRED` |
| `altium-third-party-pcbdoc-04` | 11, 53, 149, 0, 67 | 990 | 0 | 8 | 1, 1 | 0 | 0 | 0 | 118 | `UNVERIFIED` |
| `altium-third-party-pcbdoc-05` | 5, 96, 194, 0, 59 | 1 156 | 0 | 0 | 1, 0 | 0 | 0 | 0 | 232 | `INFERRED` |
| `altium-third-party-pcbdoc-06` | 11, 106, 111, 3, 42 | 250 | 0 | 0 | 0, 2 | 0 | 10 | 0 | 0 | `UNVERIFIED` |
| `altium-third-party-pcbdoc-07` | 16, 112, 475, 20, 60 | 2 528 | 0 | 0 | 2, 1 | 0 | 0 | 0 | 112 | `UNVERIFIED` |
| `altium-third-party-pcbdoc-08` (heavy) | 128, 2 126, 8 355, 529, 1 770 | 60 253 | 28 | 17 | 2, 3 | 0 | 0 | 0 | 4 628 | `UNVERIFIED` |

- **No pour is judged against a default.** c0122 measured 266 clearance findings on
  `altium-third-party-pcbdoc-03`, all against the model's default zone clearance of 0.5 mm. They are gone.
  With the rule table of c0084 the document's three Clearance records were outside the table (two scoped
  by layer, one with a matrix key), so no clearance was in force: the stage judged 954 pairs for shorts
  only and carried `UNVERIFIED`.
- **The clearance matrix of `-03` is read (change c0125).** The three records are a clearance matrix
  between all net classes: 5 mil on the inner layers, 5 mil on the outer layers, 10 mil elsewhere. The
  board has two copper layers, so the outer-layer record governs every copper pair (a rule with both
  layers), the inner-layer record applies to nothing and is no unread rule, and the 10 mil record is
  mapped and governs no copper pair. Mapped, applying to nothing, unread: 2, 1, 0 (before: 0, 0, 3). No
  pair is judged for shorts only, the pour is judged, and the stage carries `INFERRED`.
- **Counted plainly.** Of the seven documents, five hold a clearance in force (`-01`, `-03`, `-04`, `-05`,
  `-07`; four before c0125), three have no unread Clearance record (`-01`, `-03`, `-05`), and two carry
  `INFERRED` (`-03`, `-05`; one before). c0125 lifts one of the three documents that had no clearance in
  force, not three.
- **Known false findings on `-08`.** `fenolite check` reports 29 FALSE findings on `altium-third-party-pcbdoc-08` (28 `copper.short` and 1 `copper.clearance`): seven vias have no pad on the four inner layers, the pours of other nets were made around their holes, and the import draws each via's one diameter on every layer of its span, so the pad it invents meets the pour. They are a defect of the import, not of the board; the follow-up change c0132 is to read the fact that makes a via padless on a layer. The row of `-08` above counts them (28 of its shorts, 1 of
  its 17 clearance findings); no other row holds a finding of this class.
- **The heavy document `-08` and the cells of a matrix (change c0130; measured on 2026-10-07 with
  `FENOLITE_HEAVY=1`).** Its row is new: the document was in no copper test before. One of its four
  Clearance records, for all objects with one cell (via to via, 3.5 mil in a rule of 4 mil), is read as a
  rule and a cell rule; before, no clearance was in force (26 240 pairs judged, 22 413 of them for shorts
  only, 33 pours without a clearance). Three records of a higher priority stay unread. `summary.clearance_cells`
  is 1 judged and 8 unjudged. c0130 lifts this one record of the four matrices of differing clearances;
  the matrices of `-02` and `-06` tell a through-hole pad from a surface pad, or an arc from a track,
  which the check cannot, and carry the option that ignores the pads of one footprint: both documents
  are as before (27 and 8 cells unjudged).
- **The findings of `-08`.** 16 clearance findings are 8 to 13 nm short of the rule's value (6 track to
  track, 8 track to via, 1 pad to track, 1 via to via against the cell): the class of `-03` and `-01`
  below. **28 shorts and one clearance finding of 33.9 µm are a limit of the import, not of the board:** 7
  vias meet the pour of another net on each of the four inner layers, and a track passes one such via.
  The pour stands at the via's drill radius plus the generic clearance from its centre (to 4 nm), so it
  was poured around the hole: the via has no pad there, and the import draws its one diameter on every
  layer. All 7 have the long form of the via record (335 bytes, 123 of 1 770 vias), whose further bytes
  no fact explains. Listed for the follow-up change c0132; pinned by
  `test_known_false_findings_of_padless_vias_c0132`.
- **What still has no clearance in force.** `-02` holds one Clearance record, a matrix of differing
  clearances (27 entries of 5 values) with the option that ignores the pads of one footprint. `-06` holds
  two: one for a net with a matrix of differing clearances, and one for all objects with that option.
  A neutral rule holds one value and no selector says "two pads of one component", so these stay unread
  and reported (`docs/formats/altium/rule-file.md`, "Clearance forms that map").
- **The 17 findings that remain.** On `-03`, seven pad-to-track pairs on the bottom layer, each 8 to 9 nm
  short of the 0.127 mm rule: one square through-hole pad 637 795 units wide, whose edge lies on half a
  unit of the document, and seven segments of one track net that runs around it, with a track edge about
  49 996.5 units away where the rule asks for 50 000 (Altium's own check on this pad is a required step
  of the maintainer's Altium session 2: c0088's design, "Session 2"). They are
  short by the document's own numbers, beyond what the unit's rounding explains (below); whether Altium's
  check tolerates them is not known. On `-01`, two pad-to-track pairs 9 nm and 20 nm short of the 0.1524 mm
  rule, the same class. On `-04`, six fill-to-pad and two pad-to-track pairs up to 50 µm short of the 0.15 mm rule; that
  document holds one more Clearance rule whose scope is outside the grammar, which the stage reports, so
  these pairs may be governed by it.
- **Internal planes.** Before the lines of a plane were taken out, `-01` gave 66 shorts and 48 clearance
  findings and `-02` gave 5 shorts, every one between a line without a net on a plane layer and a via or a
  pad. Those lines cut the plane: they are no copper. Change c0088 took them out of the view of the check;
  since change c0124 the import makes no track of them (74 on `-01`, 43 on `-02`, counted as `plane-cuts`
  and on the layer of each plane), and the check filters nothing. Measured again on 2026-10-06 (13 passed,
  one heavy set skipped): every number of the table above is the same, the 71 shorts and the 48 clearance
  findings stay gone, and the test asserts that the board that is checked holds every track and arc of the
  board that was read and none on a plane layer. The column `planes` still counts the plane layers, whose
  own copper no reading holds: one `copper.item-unsupported` at `plane`, level `UNVERIFIED`.
- **The unit's slack.** With the rule values as the documents write them, 1 447 more clearance findings
  appear on the seven documents (1 088 before `-03` had a clearance in force) and 4 628 on `-08`, every one 1 to 4 nm short (the last column). The check lowers a clearance rule by 5 nm.
- **The rule of the slack (change c0131).** The 5 nm are now a stated rule, one file unit (2.54 nm) per
  item of the pair, 5.08 nm held as 5 whole nanometres: the same number, so every count of this section
  is unchanged. Measured again on the eight documents on 2026-10-07 (`FENOLITE_HEAVY=1`): the slack
  removes 6 075 findings (626, 0, 359, 118, 232, 0, 112 and 4 628; by shortfall 4 262 at 1 nm, 1 538 at
  2 nm, 234 at 3 nm, 41 at 4 nm, none at 5 nm). **The 25 findings of the other class all stay errors**:
  2 on `-01` (9 and 20 nm short), 7 on `-03` (8 and 9 nm) and 16 on `-08` (8 to 13 nm), that is 3.1 to
  7.9 file units for the pair where the rule gives 2. Nothing lies between 4 and 8 nm: the conversion
  explains the first group and not the second. The design of c0131 holds the bound per kind of item
  and two open decisions (these 25 findings; a pad against a rectangular pad, whose worst case of 6.36 nm
  is above the rule and which no document shows).
- **Not compared with KiCad's import.** `kicad-cli pcb import` writes no rules for an imported document,
  so the clearance findings of the two readings cannot be compared; `H-A-DRC-SAME` rests on the samples
  built for both targets (`tests/kicad/altium/test_copper_same.py`: equal findings on the routed blink as
  built, with a planted short, with a planted clearance fault and with both).

| set | components, footprints | missing, extra | value or footprint name | net conflicts (all implied by the pad-net comparison) | pins without a pad, pads without a pin | footprints that differ in the library alone | pads that differ in the net name alone |
|---|---|---|---|---|---|---|---|
| `altium-set:01` | 540, 544 | 0, 0 | 27 | 8 | 6, 22 | 171 | 10 |
| `altium-set:02` | 248, 260 | 2, 2 | 10 | 21 | 0, 3 | 241 | 129 |
| `altium-set:03` | 23, 27 | 0, 0 | 0 | 0 | 0, 0 | 23 | 0 |
| `altium-set:04` | 41, 41 | 0, 0 | 0 | 2 | 0, 2 | 41 | 0 |
| `altium-set:05` | 27, 27 | 0, 0 | 0 | 0 | 0, 0 | 27 | 0 |

- The last two columns are why two spellings are read as one (`docs/formats/altium/import.md`, "Schematic
  side of the parity comparison"): without that, 503 placed footprints of the five sets and 139 pads (129
  on `altium-set:02`, 10 on `altium-set:01`) would be findings of spelling. `tests/corpus/test_altium_copper.py`
  holds every count of the table (`PARITY`), so a change of the import that moves one fails there.
- Every net conflict names a pad that `netlist.assignment_compare` flags too, and every one is a pad
  that the board puts on a net and that no pin of the schematic component names (the schematic gives it
  no net). The import holds a pin-to-pad map for one component of the five sets (on `altium-set:02`);
  the component of the two conflicts of `altium-set:04` holds none in its sheet, so the map does not
  explain them.
- Before the channel net names and the pin-to-pad map of c0083, `altium-set:02` gave 26 net conflicts,
  6 pins without a pad, 4 pads without a pin and 189 pads that differed in the net name alone; the other
  cells of the four sets measured then are unchanged.
- The 27 value differences of `altium-set:01` and the component findings of `altium-set:02` (2 missing
  and 2 extra footprints, 5 values, 5 footprint names; its PCB document holds 12 components without a
  designator) are recorded here and not compared with `equivalent` level 1.
