# Altium output job (`.OutJob`)

This page states, in Fenolite's own words, what the output-job reader
`fenolite.backends.altium.read.outjob` (change c0042) relies on. The sources are Altium's public
documentation (S-0293) and three public output jobs saved by Altium Designer (S-0187, S-0297, S-0299;
corpus rows `altium-third-party-outjob-01` to `-03`), fetched to the corpus cache and never committed.
No parser code of another project was read. The reader lists the outputs of a job; it runs none.

## Facts

| fact | source | label | hypothesis |
|---|---|---|---|
| An output job is an ASCII file of the project that holds the outputs to generate, the output containers (media) they go to, and hard copy settings; each output names its source document, its variant and whether it is enabled for a container | S-0293 | INFERRED | H-A-RD-PRJ-OUTJOB |
| A saved output job is INI text with LF line ends, 7-bit ASCII without a byte-order mark, and ends with an empty line | S-0187, S-0297, S-0299 | CORPUS-VERIFIED (2026-10-05; 3 rows, 3 repositories) | H-A-RD-PRJ-INI |
| It holds the sections `[OutputJobFile]`, `[OutputGroup1]`, `[PublishSettings]` and `[GeneratedFilesSettings]`; the order of the sections differs between files | S-0187, S-0297, S-0299 | CORPUS-VERIFIED (2026-10-05; 3 rows, 3 repositories) | H-A-RD-PRJ-OUTJOB |
| `[OutputJobFile]` holds `Version=1.0` | S-0187, S-0297, S-0299 | CORPUS-VERIFIED (2026-10-05; 3 rows, 3 repositories) | H-A-RD-PRJ-OUTJOB |
| Newer files add to `[OutputJobFile]` a caption, a description and vault keys | S-0187, S-0299 | INFERRED | H-A-RD-PRJ-OUTJOB |
| A group section holds `Name`, `Description`, `TargetOutputMedium`, `VariantName`, `VariantScope`, `CurrentConfigurationName`, `TargetPrinter` and `PrinterOptions` | S-0187, S-0297, S-0299 | CORPUS-VERIFIED (2026-10-05; 3 rows, 3 repositories) | H-A-RD-PRJ-OUTJOB |
| A container (medium) `j` of a group is the key `OutputMedium<j>` (its name) with `OutputMedium<j>_Type` (`Printer`, `Publish`, `GeneratedFiles` or `Multimedia` in the files read); a printer adds `OutputMedium<j>_Printer` and `OutputMedium<j>_PrinterOptions` | S-0187, S-0297, S-0299 | CORPUS-VERIFIED (2026-10-05; 3 rows, 3 repositories) | H-A-RD-PRJ-OUTJOB |
| An output `i` of a group is the set of keys `OutputType<i>`, `OutputName<i>`, `OutputCategory<i>`, `OutputDocumentPath<i>`, `OutputVariantName<i>`, `OutputEnabled<i>` and `OutputDefault<i>`, numbered from 1; outputs can add `PageOptions<i>` and `Configuration<i>_Name<k>` / `Configuration<i>_Item<k>` | S-0187, S-0297, S-0299 | CORPUS-VERIFIED (2026-10-05; 3 rows, 3 repositories) | H-A-RD-PRJ-OUTJOB |
| `OutputEnabled<i>_OutputMedium<j>` is written for every output `i` and every container `j` of the group; it is `0` for most pairs and `1`, `2` or `3` for the others | S-0187, S-0297, S-0299 | CORPUS-VERIFIED (2026-10-05; 3 rows, 3 repositories) | H-A-RD-PRJ-OUTJOB |
| That a value of `OutputEnabled<i>_OutputMedium<j>` other than `0` means the output is sent to that container is inferred from the documentation's enabled state per container | S-0293 | INFERRED | H-A-RD-PRJ-OUTJOB |
| `[PublishSettings]` and `[GeneratedFilesSettings]` hold one numbered set of keys per container (paths, file names, open and reload options) | S-0187, S-0297, S-0299 | INFERRED | H-A-RD-PRJ-OUTJOB |

## Fenolite's choices

- `OutJobFile.to_bytes()` gives the input back. The section `OutputJobFile` is required: without it the
  data is not an output job and `FormatError` is raised.
- An output is listed for each index `i` that has any of the six keys `OutputType<i>`, `OutputName<i>`,
  `OutputCategory<i>`, `OutputDocumentPath<i>`, `OutputVariantName<i>` or `OutputEnabled<i>`, in
  ascending `i`. One without `OutputType<i>` is still listed, with an empty type and the warning
  `altium.outjob.output-incomplete`.
- `enabled` is true only for `OutputEnabled<i>=1`; `enabled_media` holds each `j` whose
  `OutputEnabled<i>_OutputMedium<j>` is not `0`.
- `[PublishSettings]`, `[GeneratedFilesSettings]`, `PageOptions<i>`, `Configuration<i>_…` and every
  other key stay in `OutJobFile.ini` and are not typed.
