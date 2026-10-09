## Why

The output job that an Altium build writes (change c0087) holds its outputs, their source documents and their containers, and no output setting: c0087 decided that a settings record with a few of its fields would be a guess about the others, wrote none, and left every output to Altium's defaults (`outjob.MAPPED_OPTIONS` is empty).

On 2026-10-07 the maintainer ran that job in Altium Designer 26 (`docs/evidence/altium-pcb.md`, "Returned folders of 2026-10-07"). NC drill, pick and place, the bill of materials and the two prints were produced. **No Gerber layer file was produced**: the report of the Gerber output names no layer and its aperture files are empty, with no error message. For a Gerber output without a settings record, Altium's default plots nothing. A fabrication set without its copper is not a fabrication set, so the job fails at the one thing it is for.

The decision of c0087 was right about a partial record and wrong about no record. The two public output jobs of the corpus that hold a Gerber output hold the whole record: 44 fields in one order, measured for this proposal with Fenolite's own reader (design, "Measured on 2026-10-07").

Decided by the coordinator on the maintainer's behalf on 2026-10-07: the change writes the complete record, never a part of it; the plotted layers come from the board; the decimals come from the export preset; the fact rows are `INFERRED` until the next Altium run; the proposal comes first, and the implementation before c0092.

Decided on 2026-10-07 on the first form of this proposal (design, "Decisions (2026-10-07)"):

1. No Gerber file of the board outline in this change. The limit is said in the changelog and reported in `result.outjob.gerber.outline`; step O6 of Part O asks what Altium offers for the board shape. Drawing the outline on a mechanical layer is its own proposal after session 2.
2. Mechanical 13 to 16 are plotted (the KiCad export plots none of them); the preset's `gerbers.layers` does not choose the plotted layers; 4 decimals without a preset.
3. `OutputDefault<i>=0` is written on every output of the job, as all 24 outputs of the three public jobs hold it. This changes the bytes of every written job and of every output kind.
4. In the kit's step table this change edits one hypothesis id, at step K7.2, and nothing else.

## What Changes

- **Fact rows first.** `docs/formats/altium/output-job.md` gains a section with one row per field of the Gerber record (name, position, the values seen in the two public files, the value Fenolite writes and why), the rows of the layer list, and the row of the observed behaviour (a Gerber output without a record plots no layer). All are `INFERRED`, each with a hypothesis that names the one observation that settles it.
- **Every output of a written job gains `OutputDefault<i>=0`**, after its last `OutputEnabled<i>_OutputMedium<j>` key: the key, its value and its place are the same in all 24 outputs of the three public jobs (three repositories). Its meaning is not stated by a source.
- **The Gerber output of a written job carries the complete record**: `Configuration<i>_Name1=OutputConfigurationParameter1` and `Configuration<i>_Item1=<44 fields>`, after `OutputDefault<i>`. 28 field names hold the value both public files hold; the plotted layers (`Plot.Set`) are the board's layers; the unit is millimetres and the decimals are `gerbers.precision` of the export preset (4 without one); six further names take a stated choice between the two values that occur. A record with a missing or an extra field is refused by the writer.
- **`outjob.from_preset` takes the board's copper stack**, and `outjob.MAPPED_OPTIONS` becomes `{"gerbers.precision"}`. **This changes `result.outjob` of `build --target altium`**: it gains `gerber` (unit, decimals, the plotted layers by name and id, and `outline`, which says that the set holds no outline and why), and `result.outjob.defaults` no longer lists `gerbers.precision`.
- **The output-job reader types the settings**: `JobOutput.settings` holds the `Configuration<i>_Name<k>` / `Configuration<i>_Item<k>` pairs of an output, and `read.outjob.record_fields` splits a record into its fields, so that the written record is read back by Fenolite's reader and compared with the public files.
- **No other output kind gains a record.** NC drill, pick and place, the bill of materials and the two prints ran without one in Altium Designer 26; the public jobs do hold records for them (design, "The other output kinds"), and they stay out of this change.
- **Bytes.** Every written job changes, with or without a Gerber output: each output gains one line, and a Gerber output two more. So do the one committed sample, `tests/data/altium/outjob/blink.OutJob`, and the job of every build with a PCB document. Every other file of a build keeps its bytes.
- **No outline file.** The Gerber set of the written job holds no plot of the board outline: the written PCB document holds the outline as the board shape and on no layer, and no public file shows how a saved job names the board shape among its plotted layers.
- **Part O again**, short, for the maintainer's session 2 in Altium Designer 26: open the job, generate the container `fab`, report which Gerber files appear, and read units, format and plotted layers in the setup of the output.

Size: 2.25 design-days (a size, not time); cut order in the design.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `altium-project-reader`: MODIFIED "Output job read" (the living requirement: `JobOutput.settings`) and "Output job written" (the delta of c0087: the Gerber record).
- `altium-build`: MODIFIED "Output job in an Altium build" (the delta of c0087: the copper stack, `result.outjob.gerber`, the evidence) and, decided on 2026-10-07 after the rebuild measurement, MODIFIED "Edited Altium outputs are not overwritten" (the living requirement: a project file that is as a build wrote it and does not list the job is written again with the job listed).

"Output job written" and "Output job in an Altium build" are added by change c0087, which is implemented and not archived; the design says from which text each delta starts.

## Non-goals

- No settings record for NC drill, pick and place, the bill of materials or a print; no `PageOptions<i>`, no key of `[PublishSettings]` or `[GeneratedFilesSettings]`.
- No plot of the board outline, no drill drawing, no drill guide and no pad master plot: no public file gives the layer list entry of the outline, and the three others are settings whose effect no source states (design, "What the two files do not show").
- No outline drawn on a mechanical layer by the PCB writer: it would change every written PCB document and every committed sample of one, so it is its own proposal, after session 2 has said what Altium offers for the board shape.
- No option of the export preset besides `gerbers.precision`: `gerbers.layers` and the other keys of `[gerbers]` stay in `result.outjob.defaults`.
- No claim about what a field means beyond what its fact row says, and no claim that Altium accepts the record until Part O is reported.
- Fenolite still runs no output job and writes no Gerber for Altium.
- No code, constant or value from any private project or organisation: the record's values are those of the two public files of the corpus manifest, read with Fenolite's reader, or Fenolite's own choice between them.
- No file that Altium wrote is committed.

## Evidence level required

- The form of the record and every field row: `INFERRED` (two public files of two repositories; the `CORPUS-VERIFIED` rows of the page cite three).
- `OutputDefault<i>`: its presence, its value `0` and its place are `CORPUS-VERIFIED` (three public jobs of three repositories, 24 outputs, asserted by a corpus test); its meaning is `INFERRED`.
- "A Gerber output without a record plots no layer": `INFERRED` from the returned files, until the maintainer states the outcome with his minor version; then the author-report level, by the living rule "Author-report rows".
- That Altium Designer 26 takes the written record and plots the layers of `Plot.Set`: `INFERRED` until Part O of session 2 is reported.
- Own read-back of the written record: supporting data; it raises no label.

## Impact

- Changed: `backends/altium/outjob.py`, `backends/altium/read/outjob.py`, `lens/altium.py` (the call and `outjob_summary`), `cli/_kit.py` only through the lens; tests `tests/unit/backends/altium/test_outjob_write.py`, `read/test_outjob.py`, `tests/unit/lens/test_altium_outjob.py`, `tests/unit/cli/test_build_altium.py`, `tests/corpus/test_altium_text.py`; the sample `tests/data/altium/outjob/blink.OutJob`.
- Pages: `docs/formats/altium/output-job.md`, `docs/evidence/sources.md` (S-0605), `docs/hypotheses.md`, `docs/evidence/altium-schematic.md` (Part O), `docs/altium.md` ("Output job"), `docs/cli-contract.md`.
- Depends on: c0087 (the job writer), c0042 (the reader), c0085 (the copper stack of the PCB document). Before c0092, which graduates the write on evidence that includes this job.
