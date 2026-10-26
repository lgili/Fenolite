## Context

- **Request.** P1-5 of the analysis of 2026-10-25.
- **What exists.** `read.project` reads the `.PrjPcb` INI sections; the S-0786 project lists a
  `.PrjPcbVariants` file.

## Goals / Non-Goals

**Goals**
- See the proposal, "What Changes".

**Non-Goals**
- See the proposal.

## Decisions

1. Variants are read from the `.PrjPcb` sections (`ProjectVariant<n>`, `Variation<k>`, `ParamVariation<k>` with
   `ParamDesignator<k>`). The six public project files hold their variants there; the `.PrjPcbVariants` file
   that one project lists is not in the corpus and is not read.
2. A part is matched by the last segment of its `UniqueId` path against the sheets' `UNIQUEID` (now in the
   sheet scenes as `uid`), then by its designator: a variation keeps the designator of when it was made (`X?`
   in the public variant `No Crystal`).
3. The scenes of the project's sheets and board carry every variant resolved (`variants`), so the page switches
   without a reload; `--variant` sets the first choice and counts the parts of the document shown.

## Risks / Trade-offs

- **Variant keys** may differ by Altium version; unknown keys are counted in a note.
