# Altium Draftsman documents: census and kit Part F

Evidence of change c0172 (native Altium Draftsman documents, `.PCBDwf`). The facts these measurements
support are rows of `docs/formats/altium/draftsman.md`; the hypotheses are the `H-A-DWF-*` rows of
`docs/hypotheses.md`. The public documents of S-0785 and S-0786 are fetched to the corpus cache by
`tools/corpus_fetch.py --uses altium-draftsman` and are never committed. Only counts, lengths, container
bytes and element names are recorded here, never a value of a document's content. No fact comes from
Altium's program code or from a third-party parser.

## Census

### Container (task 1.2, 2026-10-16)

Measured by `uv run python tools/draftsman_census.py` and pinned by
`FENOLITE_HEAVY=1 uv run pytest tests/corpus/test_altium_draftsman_census.py -k container`.

| row | source | bytes | first eight bytes | chunks (LZ4, stored) | last chunk decodes to | decoded bytes | XML elements | LZ4 sequences | largest offset |
|---|---|---|---|---|---|---|---|---|---|
| `altium-third-party-pcbdwf-01` | S-0785 | 4455680 | `01 80 80 40 8d 75 f2 5a` | 73 (73, 0) | 783065 | 76280537 | 2662429 | 925955 | 65535 |
| `altium-third-party-pcbdwf-02` | S-0785 | 4903885 | `01 80 80 40 f5 e0 02 f2` | 26 (24, 2) | 349325 | 26563725 | 1089079 | 361900 | 65535 |
| `altium-third-party-pcbdwf-03` | S-0786 | 458794 | `01 80 80 40 be a0 02 f2` | 6 (6, 0) | 719643 | 5962523 | 243822 | 98773 | 65531 |
| `altium-third-party-pcbdwf-04` | S-0786 | 328671 | `01 80 80 40 d6 92 05 f2` | 4 (4, 0) | 645697 | 3791425 | 172161 | 69663 | 65487 |

What the rows show:

- Every chunk but the last decodes to 1048576 bytes. An LZ4 chunk's header is 6 or 7 bytes (flag, the
  3-byte decoded length `80 80 40`, a stored length of 2 or 3 bytes); a stored chunk's is 4 bytes.
- The "four-byte field" of the first look (S-0785, S-0786) is not a field: in row 01 it is the stored length
  `8d 75` (14989) and the token `f2` with its first extra length byte `5a`; in rows 02 to 04 it is a
  three-byte stored length (45173, 36926, 84310) and the token `f2`. The token `f2` starts a literal run
  of 15 + 90 = 105 bytes, the length of `<Document xmlns="…V1"`; the first match follows.
- Literal runs are short: 1.2 %, 5.7 %, 1.6 % and 1.8 % of the decoded bytes are literals. The longest run
  is 3062, 337437 (a run of base64 text in an LZ4 block of row 02), 1850 and 1850 bytes.
- The compressed file is 5.84 %, 18.46 %, 7.69 % and 8.67 % of the decoded text.
- All four texts are well-formed XML of the Draftsman namespace (`xml.etree.ElementTree`, streamed), UTF-8,
  with no declaration.

### Candidates (task 1.2, 2026-10-16)

Each candidate of design Decision 1 was tried at the offsets 0 to 8 and at every chunk's payload start. A
decoder "decodes" when it returns at least 16 bytes of printable text; a framed format is "present" when its
leading bytes occur there.

| candidate | specification | how it was tried | result on the four rows |
|---|---|---|---|
| raw deflate | S-0806 | Python `zlib`, window −15 | decodes nothing |
| zlib | S-0805 | Python `zlib`, window 15; leading byte `78` | decodes nothing; not present |
| gzip | S-0807 | Python `zlib`, window 31; leading bytes `1F 8B` | decodes nothing; not present |
| `.xz` and legacy LZMA | S-0809 | Python `lzma`, automatic and legacy forms; leading bytes `FD 37 7A 58 5A 00` | decodes nothing; not present |
| bzip2 | Python's `bz2` (no public format specification beyond the reference program) | Python `bz2` | decodes nothing |
| LZ4 frame | S-0804 | leading bytes `04 22 4D 18` | not present |
| Zstandard frame | S-0808 | leading bytes `28 B5 2F FD` | not present |
| framed Snappy | S-0811 | leading bytes `FF 06 00 00 73 4E 61 50 70 59` | not present |
| LZ4 block | S-0803 | Fenolite's own decoder, written from the block description, one block per chunk of flag 1 | decodes every block of the four rows: 107 blocks |
| Brotli, raw Snappy, MS-XCA | design Decision 1 | not tried: the LZ4 block form decoded every chunk first | none |

No codec package was installed: the LZ4 block decoder is about forty lines of Fenolite's own code, and
the other candidates are in Python's standard library or were recognised by their leading bytes only.

### Phase 1 budget

Phase 1 has a budget of 2 design-days (design Decision 1). The container of the public documents was
established on 2026-10-16 in under half a design-day. Gate G1 also needs every F0 file of the maintainer
(tasks 1.4 and 1.5) and is decided there.
