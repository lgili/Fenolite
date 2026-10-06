# Altium round trips: RT-A0, RT-A1 and RT-A2

Results of the three round-trip levels of Altium files (change c0044,
`fenolite.backends.altium.roundtrip` and the stages `roundtrip.rta0`, `roundtrip.rta1` and
`roundtrip.rta2` of `fenolite check`). The public files are the rows of `tests/corpus/manifest.toml`
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
  "Round trips") and within 2 nm. It is judged on Fenolite's own builds only, and only for what the
  built model holds.

## Reasons for an unjudged level

A level that is not judged is neither a pass nor a failure; it is counted by reason.

| reason | level | meaning |
|---|---|---|
| `too-large` | RT-A0 | the file needs DIFAT sectors, which the compound writer does not write |
| `writer-refused` | RT-A0 | the compound writer refuses the tree (an empty storage, or a name it does not write) |
| `not-a-container` | RT-A0 | the file is text (an ASCII schematic or a project file), so there is no container to copy |
| `native-input` | RT-A2 | the files were not written by a Fenolite build; writing an imported model waits for v0.4 |

## The run

run: 2026-10-05, commit `5fb8ba31`, macOS, local corpus cache, with the heavy row
(`FENOLITE_HEAVY=1`):
`FENOLITE_REQUIRE=corpus FENOLITE_CENSUS_OUT=… uv run pytest tests/corpus/test_altium_roundtrip.py tests/corpus/test_altium_documents.py`,
73 tests passed.

| level | rows | judged | passed | not judged | level label | hypothesis |
|---|---|---|---|---|---|---|
| RT-A0 | 65 | 57 | 57 | 8 (`too-large` 2, `not-a-container` 6, `writer-refused` 0) | `INFERRED` | `H-A-VER-RTA0` pending: the judged PCB libraries come from two repositories |
| RT-A1 | 65 | 65 | 65 | 0 | `INFERRED` | `H-A-VER-RTA1` pending, for the same reason |
| RT-A2 | 21 builds | 21 | 21 | 0 | `INFERRED` | `H-A-VER-RTA2-2` |

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
binary and in the ASCII schematic form, and one build with module sheets. `not in the model` counts the
entities of a board kind that the PCB document reads and that the built model does not hold: they are not
compared (`docs/altium.md`, "Round trips").

| build | schematic form | holds | differences | kinds compared | not in the model |
|---|---|---|---|---|---|
| `examples/altium_hier/design.py` | binary | yes | 0 | schematic: component, net, no_connect | — |
| `examples/altium_hier/design.py` | ascii | yes | 0 | schematic: component, net, no_connect | — |
| `examples/altium_hier/partial.py` | binary | yes | 0 | schematic: component, net, no_connect | — |
| `examples/altium_hier/partial.py` | ascii | yes | 0 | schematic: component, net, no_connect | — |
| `examples/altium_hier_board/design.py` | binary | yes | 0 | schematic: component, net, no_connect; pcb: netclass | footprint 3; pad 36 |
| `examples/altium_hier_board/design.py` | ascii | yes | 0 | schematic: component, net, no_connect; pcb: netclass | footprint 3; pad 36 |
| `examples/altium_kicad/design.py` | binary | yes | 0 | schematic: component, net, no_connect | — |
| `examples/altium_kicad/design.py` | ascii | yes | 0 | schematic: component, net, no_connect | — |
| `examples/altium_kicad/no_connect.py` | binary | yes | 0 | schematic: component, net, no_connect | — |
| `examples/altium_kicad/no_connect.py` | ascii | yes | 0 | schematic: component, net, no_connect | — |
| `examples/altium_sample/design.py` | binary | yes | 0 | schematic: component, net, no_connect | — |
| `examples/altium_sample/design.py` | ascii | yes | 0 | schematic: component, net, no_connect | — |
| `examples/blink_2layer/design.py` | binary | yes | 0 | schematic: component, net, no_connect; pcb: netclass | footprint 3; pad 36 |
| `examples/blink_2layer/design.py` | ascii | yes | 0 | schematic: component, net, no_connect; pcb: netclass | footprint 3; pad 36 |
| `examples/blink_official/design.py` | binary | yes | 0 | schematic: component, net, no_connect; pcb: netclass | footprint 3; pad 36 |
| `examples/blink_official/design.py` | ascii | yes | 0 | schematic: component, net, no_connect; pcb: netclass | footprint 3; pad 36 |
| `examples/blink_routed/design.py` | binary | yes | 0 | schematic: component, net, no_connect; pcb: netclass | footprint 3; pad 36; track 11; via 7 |
| `examples/blink_routed/design.py` | ascii | yes | 0 | schematic: component, net, no_connect; pcb: netclass | footprint 3; pad 36; track 11; via 7 |
| `examples/board_40parts/design.py` | binary | yes | 0 | schematic: component, net, no_connect; pcb: netclass | footprint 40; pad 140; via 2; zone 2 |
| `examples/board_40parts/design.py` | ascii | yes | 0 | schematic: component, net, no_connect; pcb: netclass | footprint 40; pad 140; via 2; zone 2 |
| `examples/altium_hier/design.py` | binary (module sheets) | yes | 0 | schematic: component, net, no_connect | — |

What RT-A2 proves today: the schematic writers and the schematic import agree on every component
(reference and value), every net (name and members) and every no-connect mark of the 21 builds, and
the PCB document writer and its import agree on the net class names. What it does not prove: anything
about footprints, pads, tracks, vias and zones, because the built model of an Altium build does not
hold them (`H-A-VER-RTA2` is refuted on this point and superseded by `H-A-VER-RTA2-2`); and nothing
about Altium Designer, which reads none of these files here. The first probe found one difference
inside the scope, which was fixed in the build: a component whose value is empty in the script was
written with its symbol's name as the comment, and the built model now stores that value.

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
set (change c0088; `tests/corpus/test_altium_copper.py`, run on 2026-10-06 on macOS without any tool; 13
passed, `altium-set:01` skipped as heavy). Counts only. A third-party board may hold real findings: the test
asserts what the stage promises, not that a board is clean.

| document | fills, pads, tracks, arcs, vias | pairs judged | shorts | clearance | mapped and opaque Clearance rules | unpoured | zones without a clearance | planes | findings the unit's slack removes | level |
|---|---|---|---|---|---|---|---|---|---|---|
| `altium-third-party-pcbdoc-01` | 40, 735, 1 346, 0, 646 | 10 482 | 0 | 2 | 1, 0 | 0 | 0 | 2 | 626 | `UNVERIFIED` |
| `altium-third-party-pcbdoc-02` | 11, 143, 191, 0, 242 | 553 | 0 | 0 | 0, 1 | 1 | 11 | 2 | 0 | `UNVERIFIED` |
| `altium-third-party-pcbdoc-03` | 6, 383, 604, 0, 47 | 1 087 | 0 | 0 | 0, 3 | 0 | 1 | 0 | 0 | `UNVERIFIED` |
| `altium-third-party-pcbdoc-04` | 11, 53, 149, 0, 67 | 990 | 0 | 8 | 1, 1 | 0 | 0 | 0 | 118 | `UNVERIFIED` |
| `altium-third-party-pcbdoc-05` | 5, 96, 194, 0, 59 | 1 156 | 0 | 0 | 1, 0 | 0 | 0 | 0 | 232 | `INFERRED` |
| `altium-third-party-pcbdoc-06` | 11, 106, 111, 3, 42 | 250 | 0 | 0 | 0, 2 | 0 | 10 | 0 | 0 | `UNVERIFIED` |
| `altium-third-party-pcbdoc-07` | 16, 112, 475, 20, 60 | 2 528 | 0 | 0 | 2, 1 | 0 | 0 | 0 | 112 | `UNVERIFIED` |

- **No pour is judged against a default.** c0122 measured 266 clearance findings on
  `altium-third-party-pcbdoc-03`, all against the model's default zone clearance of 0.5 mm. They are gone:
  the document's three Clearance records (two scoped by layer, one with a matrix key) are outside the rule
  table, so no clearance is in force. The stage reports `copper.rules-incomplete` for the three records and
  for the one pour, judges 954 pairs for shorts only (`copper.clearance-unset`), and carries `UNVERIFIED`.
- **The 10 findings that remain.** On `-01`, two pad-to-track pairs 9 nm and 20 nm short of the 0.1524 mm
  rule. On `-04`, six fill-to-pad and two pad-to-track pairs up to 50 µm short of the 0.15 mm rule; that
  document holds one more Clearance rule whose scope is outside the grammar, which the stage reports, so
  these pairs may be governed by it.
- **Internal planes.** Before the lines of a plane were taken out, `-01` gave 66 shorts and 48 clearance
  findings and `-02` gave 5 shorts, every one between a line without a net on a plane layer and a via or a
  pad. Those lines cut the plane: they are no copper.
- **The unit's slack.** With the rule values as the documents write them, 1 088 more clearance findings
  appear, every one 1 to 4 nm short (the last column). The check lowers a clearance rule by 5 nm.
- **Not compared with KiCad's import.** `kicad-cli pcb import` writes no rules for an imported document,
  so the clearance findings of the two readings cannot be compared; `H-A-DRC-SAME` rests on the samples
  built for both targets (`tests/kicad/altium/test_copper_same.py`: equal findings on the routed blink as
  built, with a planted short, with a planted clearance fault and with both).

| set | components, footprints | missing, extra | value or footprint name | net conflicts (all implied by the pad-net comparison) | pins without a pad, pads without a pin | footprints that differ in the library alone | pads that differ in the net name alone |
|---|---|---|---|---|---|---|---|
| `altium-set:02` | 248, 260 | 2, 2 | 10 | 26 | 6, 4 | 241 | 189 |
| `altium-set:03` | 23, 27 | 0, 0 | 0 | 0 | 0, 0 | 23 | 0 |
| `altium-set:04` | 41, 41 | 0, 0 | 0 | 2 | 0, 2 | 41 | 0 |
| `altium-set:05` | 27, 27 | 0, 0 | 0 | 0 | 0, 0 | 27 | 0 |

- The last two columns are why two spellings are read as one (`docs/formats/altium/import.md`, "Schematic
  side of the parity comparison"): without that, every placed component and 189 pads of the hierarchical set
  would be findings of spelling.
- Every net conflict names a pad that `netlist.assignment_compare` flags too. The two of `altium-set:04`
  are pads of one pin that the footprint model maps to several pads: the import of a schematic component
  holds no pin-to-pad map yet (the rest of c0083), and the side uses `Component.pin_pad_map` once it does.
- The component findings of `altium-set:02` come from its repeated sheets and from components without a
  designator; they are recorded here and not compared with `equivalent` level 1.
