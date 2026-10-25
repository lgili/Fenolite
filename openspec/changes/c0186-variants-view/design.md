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

1. Variants are read from the `.PrjPcb` sections (`ProjectVariant<n>`, `Variation<k>`, `ParamVariation<k>`)
   and, when present, the `.PrjPcbVariants` file; the design records which keys appear in which.
2. A part is matched by its unique id, then its designator.

## Risks / Trade-offs

- **Variant keys** may differ by Altium version; unknown keys are counted in a note.
