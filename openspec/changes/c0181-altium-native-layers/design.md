## Context

- **Request.** P0-1 of the analysis of 2026-10-25: "o usuário de Altium nota na hora".
- **What exists.**
  - `read.pcbstack.read_board` gives the numbered layers with their names (`LAYER<i>NAME`) and Altium's default
    names (`_layer_names`).
  - `pcbrecords.LAYER_MAP` maps model names to Altium layer ids (`F.SilkS` to 33, `F.Mask` to 37 …).
  - The pad record holds the paste and solder-mask expansions at offsets 86 and 90 and their modes at 101 and
    102 (`pcb-records.md`, "Pad", `INFERRED`); `read.pcb` does not type them.
  - `read.rules` reads `Rules6`; `read.scope` evaluates a subset of rule scopes.
  - The scene (c0176) derives mask and paste openings from the pads when the model has no mask layer.

## Goals / Non-Goals

**Goals**
- See the proposal, "What Changes".

**Non-Goals**
- See the proposal.

## Decisions

1. **Labels, not ids.** A scene layer keeps `id` (the model name) and gains `name`, the native name.
   `view/altium_layers.py` gives `layer_labels(pcbdoc) -> dict[str, str]` and `layer_order(...)`. The scene
   builder takes an optional mapping; the KiCad path passes none.
2. **Names.** A numbered layer's `LAYER<i>NAME`, when present and not empty, wins over the default name; a
   mechanical layer that is not enabled keeps its default name and is still drawn if it holds primitives.
3. **Openings.** For each pad: the opening is the copper shape grown by the expansion (a negative expansion
   shrinks it, never below zero). Mode 0 is no opening for paste and no expansion for mask; mode 2 the pad
   value; mode 1 the first rule by priority whose scope `read.scope` evaluates to true for that pad, else the
   rule of scope `All`, else the Altium default of 4 mil for mask and 0 for paste (`INFERRED`, named in a
   note). A through-hole pad opens the mask on both sides, a surface pad on its side.
4. **Properties.** Rows "Solder mask expansion", "Paste expansion", "Source" and "Opening".
5. **Fallback.** A board whose pad records do not hold the fields (version 1, 110-byte form) keeps today's
   derivation, with a note.

## Risks / Trade-offs

- **Rule scopes.** A board whose mask rules use queries outside `read.scope` gets the `All` rule for those
  pads; the note counts them so the reviewer knows.
