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
| Compound files of version 3 (512-byte sectors) are a form the compound-file specification defines; that Altium reads a schematic in that form is a hypothesis. No permitted source states which version an Altium writer uses | S-0145 (version 3); the writer's version: no permitted source (S-0142 removed by the audit of 2026-10-02; S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) does not give it) | INFERRED | H-A-SCHBIN-CFB |
| The root storage holds the streams `FileHeader`, `Storage` and, optionally, `Additional`. One reader requires `FileHeader`; another opens `FileHeader` and `Storage` unconditionally and `Additional` only when present, and warns about any other stream; an open-source writer always writes `Storage` | S-0002, S-0130, S-0131, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca), S-0147 | ALTIUM-VERIFIED(author-report) (A365 Viewer; 2026-10-02; no artefact) | H-A-SCHBIN-STORAGE |
| A stream is a plain sequence of records. Each record is a 4-byte little-endian word, then the payload: the low 24 bits of the word are the payload length and the top byte is the record type (0 a property list, non-zero binary data). Sources that describe the word as a 2-byte length agree with this for payloads under 65 536 bytes | S-0130, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca), S-0147, S-0148 | ALTIUM-VERIFIED(author-report) (A365 Viewer; 2026-10-02; no artefact) | H-A-SCHBIN-FRAME |
| A property-list payload is the record's text, `\|KEY=VALUE\|KEY=VALUE…` as one line of the ASCII form without its line end, followed by one NUL byte; the length counts the NUL, and readers check it | S-0130, S-0147, S-0148 | ALTIUM-VERIFIED(author-report) (A365 Viewer; 2026-10-02; no artefact) | H-A-SCHBIN-FRAME |
| The ASCII form is the binary payloads written one per line: a converter writes each payload, without its NUL, as one text line | S-0130 | ALTIUM-VERIFIED(author-report) (A365 Viewer; 2026-10-02; no artefact) | H-A-SCHBIN-FRAME |
| The first record of `FileHeader` is the header record `HEADER=Protel for Windows - Schematic Capture Binary File Version 5.0` with `WEIGHT=<n>`; a reader compares the header text and refuses another version | S-0130, S-0131 | ALTIUM-VERIFIED(author-report) (A365 Viewer; 2026-10-02; no artefact) | H-A-SCHBIN-FRAME |
| In a schematic document, pins are property-list records (`RECORD=2`), as in the ASCII form; binary pin records belong to schematic libraries, and a schematic-document reader drops binary records | S-0131 | ALTIUM-VERIFIED(author-report) (A365 Viewer; 2026-10-02; no artefact) | H-A-SCHBIN-FRAME |
| Without images, `Storage` holds one property-list record, `\|HEADER=Icon storage`, with no weight key; images would follow as binary records. Contradiction: S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) writes a `WEIGHT` key holding the image count, 0 without images; Fenolite keeps the form without the key, which the Viewer opened (step V1) | S-0130, S-0131; contradicted in part by S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | ALTIUM-VERIFIED(author-report) (A365 Viewer; 2026-10-02; no artefact) | H-A-SCHBIN-STORAGE |
| Payload text is 8-bit text in a Windows code page; 7-bit printable ASCII is the same in every one of them | S-0130, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | ALTIUM-VERIFIED(author-report) (A365 Viewer; 2026-10-02; no artefact) | H-A-SCHBIN-FRAME |
| The Altium 365 Viewer lists Altium schematics (`*.SchDoc`) among its inputs, takes a single file or one project in an archive, up to 200 MB, and says nothing about the ASCII form | S-0149 | INFERRED | H-A-SCHBIN-VIEWER |
| A third-party writer reports checking its native binary output in the Viewer | S-0143 | INFERRED | H-A-SCHBIN-VIEWER |

## Additional stream and harness records

Change c0037. Signal harnesses group nets with different names. The keys below come from sheets that
Altium saved in two public repositories (S-0187, S-0188), read in a scratch folder and never committed;
the public descriptions (S-0130, S-0131) give little beyond the record numbers. Every row waits for
Part H of `docs/evidence/altium-schematic.md`.

| fact | source | label | hypothesis |
|---|---|---|---|
| Records 215 (harness connector), 216 (harness entry), 217 (harness type) and 218 (signal harness) are not in `FileHeader`: they are in the stream `Additional` of the binary schematic | S-0130, S-0131, S-0187, S-0188 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-SCH-HARN-OPEN |
| `Additional` starts with its own header record: the header text of `FileHeader`, then `WEIGHT=<records after it>`. An empty `Additional` holds the header alone, without `WEIGHT` | S-0187, S-0188 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-SCH-HARN-OPEN |
| A second reader skips a missing `Additional` stream and refuses one with no bytes. Fenolite's verified sheets have no `Additional` stream and Altium Designer opens them | S-0131, S-0147 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-SCH-HARN-OPEN |
| A harness connector is `RECORD=215` with `OWNERPARTID=-1`, `LOCATION.X`, `LOCATION.Y` (its top-left corner, as a sheet symbol), `XSIZE`, `YSIZE`, `LINEWIDTH=1`, `COLOR=13213327`, `AREACOLOR=16511725`, `PRIMARYCONNECTIONPOSITION` and, when its connection side is not the left, `HARNESSCONNECTORSIDE` (1 right) | S-0130, S-0187, S-0188 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-SCH-HARN-OPEN |
| The connector's connection point lies on the side `HARNESSCONNECTORSIDE` names, `PRIMARYCONNECTIONPOSITION` units of 10 mil (not steps of ten units) below the top-left corner | S-0187, S-0188 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-SCH-HARN-OPEN |
| One reader takes the connector's side from a key `SIDE`, which saved files do not hold; they hold `HARNESSCONNECTORSIDE`. The files are the fact; the reader's default (left) hides the difference | S-0131, S-0187, S-0188 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-SCH-HARN-OPEN |
| A harness entry is `RECORD=216` with `OWNERINDEXADDITIONALLIST=T`, `OWNERPARTID=-1`, `SIDE`, `DISTANCEFROMTOP` (steps of 10 units, as a sheet entry), `COLOR=7354880`, `AREACOLOR=8454143`, `TEXTCOLOR=7354880`, `TEXTFONTID=1`, `TEXTSTYLE=Full` and `NAME` | S-0131, S-0187, S-0188 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-SCH-HARN-OPEN |
| A harness type is `RECORD=217` with `OWNERINDEXADDITIONALLIST=T`, `OWNERPARTID=-1`, `LOCATION.X`, `LOCATION.Y`, `COLOR=8388608`, `FONTID=1` and `TEXT=<type name>`; one per connector, after its entries | S-0130, S-0131, S-0187, S-0188 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-SCH-HARN-OPEN |
| `OWNERINDEX` of records 216 and 217 is the index of their connector inside `Additional`, counted from 0 after the header; `OWNERINDEXADDITIONALLIST=T` says so. An owner index of 0 is left out, so the children of the first connector carry no `OWNERINDEX` | S-0131, S-0187, S-0188 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-SCH-HARN-OPEN |
| A harness entry's connection point lies on the connector's edge that the entry's `SIDE` names, `DISTANCEFROMTOP` × 10 units below the top-left corner; entries sit on the side opposite the connector's connection point | S-0131, S-0187 | INFERRED | H-A-SCH-HARN-NETS |
| A signal harness line is `RECORD=218` with `OWNERPARTID=-1`, `LINEWIDTH=2`, `COLOR=15187117`, `LOCATIONCOUNT`, `X1`, `Y1`, …: a polyline, as a wire | S-0130, S-0131, S-0187, S-0188 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-SCH-HARN-OPEN |
| On a child sheet the connector meets its port by touching it, or through a two-point harness line from the connector's connection point to the port | S-0187, S-0188 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-SCH-HARN-OPEN |
| A harness line may connect to ports, sheet entries, connectors and other harnesses. On the saved top sheets harness lines run between sheet entries that hold `HARNESSTYPE`, without a connector | S-0186, S-0187, S-0188 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-SCH-HARN-OPEN |
| A wire on a harness entry may carry an ordinary net label, which names the net; without one the net is named from the harness and the entry | S-0131, S-0186, S-0187 | INFERRED | H-A-SCH-HARN-NETS |
| The sheet defines a harness type by drawing it: a connector, its entries and the type record. Whether a connector may hold an entry without a wire is not stated | S-0186 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-SCH-HARN-UNUSED |
| A sheet that Altium saves starts, right after the sheet record, with some 27 hidden sheet parameters: `RECORD=41` without `OWNERINDEX`, with `OWNERPARTID=-1`, `COLOR=8388608`, `FONTID=1`, `ISHIDDEN=T`, `TEXT` and `NAME` (a record 41 without an owner is a parameter of the sheet). With them, the `FileHeader` stream of every saved sheet read is 14 929 bytes or more, so a sheet that Altium saved never has `FileHeader` in the compound file's mini stream (streams under 4096 bytes, `compound-file.md`). This is an observation about saved files, not a condition that Altium sets (next row) | S-0130, S-0187, S-0188 | INFERRED | H-A-SCHBIN-CFB |
| Altium Designer 26.5 reads a sheet whose `FileHeader` stream lies in the mini stream: a module sheet of 2303 bytes was a child of the top sheet when the project file listed it as the first module sheet, and the top sheet of 1837 bytes gave its sheet symbols. Padding such sheets to 4096 bytes with a hidden sheet parameter changed nothing: the module sheet that stayed outside the hierarchy was the second one listed in the project file, small or large (`project.md`). The first reading, that the stream's size was the cause (`H-A-SCHBIN-MINI`), is refuted (maintainer's second report of step H7, 2026-10-03) | S-0145 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-SCH-HIER-ORDER |
| The top sheet needs no connector for a type that a child sheet or a harness definition file defines: the saved top sheets hold signal harness lines only | S-0186, S-0187, S-0188 | INFERRED | H-A-SCH-HARN-FILE |
| On a top sheet that joins a harness sheet entry to a harness connector whose entries have labelled wires, Altium Designer 26.5 compiles the project and warns once per member that the net has multiple names: the net label, and the name that each sheet entry gives it from the harness and its entry (`<sheet>-<harness>.<entry>`). On the module sheets, where a port has the same block beside it, it gives no such warning (maintainer's report of step H3, 2026-10-03) | S-0186 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-SCH-HIER-COMPILE |
| Altium Designer 26.5 reports a harness entry without a wire as the warning "Unconnected Harness Entry", once per connector that holds it, and still compiles the project without an error (maintainer's report of step H6, 2026-10-03) | S-0186 | ALTIUM-VERIFIED(author-report) (AD 26.5; 2026-10-03; no artefact) | H-A-SCH-HARN-UNUSED |

## Fenolite's choices

- The binary schematic has two streams, `FileHeader` and then `Storage`, and a third, `Additional`, only
  when the sheet holds a harness block or a signal harness line (change c0037); a sheet without one
  keeps the two streams and its bytes.
- `FileHeader` holds the binary header record with the exact record count, then the records of
  `schematic-ascii.md` in the same order with the same keys and values, each framed with type 0.
- No CR or LF is written; payloads stay under 65 536 bytes; texts stay 7-bit, as in the ASCII form.
- `Storage` is the single 25-byte record `|HEADER=Icon storage` (4-byte word 21, 20 text bytes, NUL).
- A small sheet is written as it is: a `FileHeader` stream under 4096 bytes lies in the compound file's
  mini stream, as `compound-file.md` states, and Altium Designer 26.5 reads it. The hidden sheet parameter
  that padded such a sheet to 4096 bytes after the first report of step H7 is removed: the claim behind
  it, `H-A-SCHBIN-MINI`, is refuted, and the cause was the order of the documents in the project file
  (`H-A-SCH-HIER-ORDER`, `project.md`).
- The No ERC directive (record 22, change c0036, `schematic-ascii.md`) is framed as any other property
  list: type 0, the same keys and values as its ASCII line, and a closing NUL.
- Harness lines between sheet symbols (change c0037, after the report of step H3). When a harness
  leaves exactly two modules, those two are neighbours in module-name order, both wire the same entries
  to the same nets and every pin of those nets is on one of the two module sheets, the top sheet draws
  one two-point signal harness line and nothing else for it: from the sheet entry on the right side of
  the first module's symbol to the sheet entry of the same name on the left side of the second one, in
  the same `DISTANCEFROMTOP` slot, so the line is horizontal. The top sheet then holds no connector, no
  wire and no net label for that harness, and each of its nets keeps the one name its labels give it on
  the module sheets. If the two symbols do not land side by side in one row of the sheet, or one of the
  conditions fails, the harness keeps the block below beside each sheet entry, with its labels; Altium
  Designer then warns of multiple net names (fact table above).
- Harness blocks (change c0037). A harness that leaves a module is drawn as a block on the module
  sheet and, unless a line joins its two sheet entries, on the top sheet: a two-point signal harness
  line of 200 mil from the port's right end, or from the sheet entry's connection point, to the
  connection point on the connector's left edge;
  the connector with one entry per entry of the type, on its right side, in code-point order of their
  names; the type record at the connector's top-left corner. A connector of `m` entries is
  `(m + 1) · 100` mil high, at least 500 mil wide, with the entries at `DISTANCEFROMTOP` 1 … `m` and
  `PRIMARYCONNECTIONPOSITION = 10 · ⌊(m + 1) / 2⌋`.
- `Additional` holds the binary header record with `WEIGHT=<records after it>`, then per block: the
  connector, its entries, the type, the line; then one record 218 per line between two sheet symbols.
  Keys, in this order:
  - `RECORD=215`, `OWNERPARTID=-1`, `LOCATION.X`, `LOCATION.Y`, `XSIZE`, `YSIZE`, `LINEWIDTH=1`,
    `COLOR=13213327`, `AREACOLOR=16511725`, `PRIMARYCONNECTIONPOSITION`; no `HARNESSCONNECTORSIDE`
    (the connection point is on the left);
  - `RECORD=216`, `OWNERINDEX` (left out when 0), `OWNERINDEXADDITIONALLIST=T`, `OWNERPARTID=-1`,
    `SIDE=1`, `DISTANCEFROMTOP`, `COLOR=7354880`, `AREACOLOR=8454143`, `TEXTCOLOR=7354880`,
    `TEXTFONTID=1`, `TEXTSTYLE=Full`, `NAME`;
  - `RECORD=217`, `OWNERINDEX` (as the entries), `OWNERINDEXADDITIONALLIST=T`, `OWNERPARTID=-1`,
    `LOCATION.X`, `LOCATION.Y`, `COLOR=8388608`, `FONTID=1`, `TEXT`;
  - `RECORD=218`, `OWNERPARTID=-1`, `LINEWIDTH=2`, `COLOR=15187117`, `LOCATIONCOUNT=2`, `X1`, `Y1`,
    `X2`, `Y2`.
- Every block of a type holds all the type's entries, so the drawn definitions never differ. An entry
  whose net leaves the block's module gets a wire stub rightwards and a net label with the **net**
  name, written in `FileHeader` as any wire and label; an entry whose net does not leave it gets
  neither, on every sheet (`H-A-SCH-HARN-UNUSED`).
- The ASCII form writes no harness record; `write_schdoc` refuses a plan that holds a block.
