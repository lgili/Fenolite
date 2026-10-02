# Altium binary schematic (`.SchDoc`)

This page states, in Fenolite's own words, what `fenolite.backends.altium.binary` (change c0033) relies
on to write a schematic in Altium Designer's binary form. The container is described in
`compound-file.md`; the records themselves are those of `schematic-ascii.md`. The same rules apply: sources
in `docs/evidence/sources.md`, code written from these pages only, GPL sources (S-0131, S-0148) read for
facts only, every row `INFERRED` until the maintainer reports (`docs/evidence/altium-schematic.md`).

The Altium 365 Viewer rendered the binary sample on 2026-10-02 (step V1), which confirmed
`H-A-SCHBIN-CFB`, `H-A-SCHBIN-FRAME` and `H-A-SCHBIN-STORAGE`. Rows of those hypotheses that the sample
exercises carry that author-report label. The row about another writer's container version stays
`INFERRED`: the Viewer says nothing about that writer. `H-A-SCHBIN-VIEWER` (V2) and `H-A-SCHBIN-AD` (A7)
are pending.

## Facts

| fact | source | label | hypothesis |
|---|---|---|---|
| Binary ("SCH Binary 5.0") is Altium Designer's recommended save format for schematics; both forms use the `.SchDoc` extension | S-0133 | INFERRED | H-A-SCHBIN-AD |
| A binary schematic is a compound file; readers tell it from the ASCII form by the compound-file signature | S-0002, S-0131 | ALTIUM-VERIFIED(author-report) (A365 Viewer; 2026-10-02; no artefact) | H-A-SCHBIN-CFB |
| An open-source writer writes schematic containers as compound files of version 3 | S-0142 | INFERRED | H-A-SCHBIN-CFB |
| The root storage holds the streams `FileHeader`, `Storage` and, optionally, `Additional`. One reader requires `FileHeader`; another opens `FileHeader` and `Storage` unconditionally and `Additional` only when present, and warns about any other stream; an open-source writer always writes `Storage` | S-0002, S-0130, S-0131, S-0142 (confirmed in S-0150), S-0147 | ALTIUM-VERIFIED(author-report) (A365 Viewer; 2026-10-02; no artefact) | H-A-SCHBIN-STORAGE |
| A stream is a plain sequence of records. Each record is a 4-byte little-endian word, then the payload: the low 24 bits of the word are the payload length and the top byte is the record type (0 a property list, non-zero binary data). Sources that describe the word as a 2-byte length agree with this for payloads under 65 536 bytes | S-0130, S-0142 (confirmed in S-0150), S-0147, S-0148 | ALTIUM-VERIFIED(author-report) (A365 Viewer; 2026-10-02; no artefact) | H-A-SCHBIN-FRAME |
| A property-list payload is the record's text, `\|KEY=VALUE\|KEY=VALUE…` as one line of the ASCII form without its line end, followed by one NUL byte; the length counts the NUL, and readers check it | S-0130, S-0147, S-0148 | ALTIUM-VERIFIED(author-report) (A365 Viewer; 2026-10-02; no artefact) | H-A-SCHBIN-FRAME |
| The ASCII form is the binary payloads written one per line: a converter writes each payload, without its NUL, as one text line | S-0130 | ALTIUM-VERIFIED(author-report) (A365 Viewer; 2026-10-02; no artefact) | H-A-SCHBIN-FRAME |
| The first record of `FileHeader` is the header record `HEADER=Protel for Windows - Schematic Capture Binary File Version 5.0` with `WEIGHT=<n>`; a reader compares the header text and refuses another version | S-0130, S-0131 | ALTIUM-VERIFIED(author-report) (A365 Viewer; 2026-10-02; no artefact) | H-A-SCHBIN-FRAME |
| In a schematic document, pins are property-list records (`RECORD=2`), as in the ASCII form; binary pin records belong to schematic libraries, and a schematic-document reader drops binary records | S-0131, S-0142 | ALTIUM-VERIFIED(author-report) (A365 Viewer; 2026-10-02; no artefact) | H-A-SCHBIN-FRAME |
| Without images, `Storage` holds one property-list record, `\|HEADER=Icon storage`, with no weight key; images would follow as binary records | S-0130, S-0131, S-0142 | ALTIUM-VERIFIED(author-report) (A365 Viewer; 2026-10-02; no artefact) | H-A-SCHBIN-STORAGE |
| Payload text is 8-bit text in a Windows code page; 7-bit printable ASCII is the same in every one of them | S-0130, S-0142 (confirmed in S-0150) | ALTIUM-VERIFIED(author-report) (A365 Viewer; 2026-10-02; no artefact) | H-A-SCHBIN-FRAME |
| The Altium 365 Viewer lists Altium schematics (`*.SchDoc`) among its inputs, takes a single file or one project in an archive, up to 200 MB, and says nothing about the ASCII form | S-0149 | INFERRED | H-A-SCHBIN-VIEWER |
| A third-party writer reports checking its native binary output in the Viewer | S-0143 | INFERRED | H-A-SCHBIN-VIEWER |

## Fenolite's choices

- The binary schematic has two streams, `FileHeader` and then `Storage`; no `Additional` stream.
- `FileHeader` holds the binary header record with the exact record count, then the records of
  `schematic-ascii.md` in the same order with the same keys and values, each framed with type 0.
- No CR or LF is written; payloads stay under 65 536 bytes; texts stay 7-bit, as in the ASCII form.
- `Storage` is the single 25-byte record `|HEADER=Icon storage` (4-byte word 21, 20 text bytes, NUL).
