## Why

Change c0125 left a Clearance record whose object matrix holds differing clearances unmapped (its form C: four records on the public documents `-02`, `-06` and `-08`), because one neutral rule holds one value. The maintainer decided on 2026-10-06 that such a record is to be lifted as one neutral clearance rule per matrix cell with `item_kind` conditions, where the neutral rule says the cell exactly, and that a cell without a counterpart is named, not dropped.

## Outcome in one paragraph

**One of the four records is lifted, on the heavy document `-08`; the documents `-02` and `-06` are not moved by this change.** Measured before proposing (design, "Measured before"): of the four matrices, two tell object kinds apart that the copper check holds as one item kind (a through-hole pad from a surface pad on `-02`; an arc from a track on `-06`), and the same two records also carry the option that ignores the pads of one footprint, which is not in v0.3 (decision 2 of c0125). The two matrices of `-08` are exact in item kinds; one of those records has a scope outside the grammar, the other is for all objects and is lifted: a rule of 4 mil and a cell rule of 3.5 mil between vias. `-08` thereby gets a clearance in force for every pair and stays `UNVERIFIED` (three Clearance records unread).

## What Changes

- **A matrix is read in the item kinds of the copper check.** `Arc` and `Track` are `track`, `SMDPad` and `THPad` are `pad`, `Via` is `via`, `Poly` is `zone` (the fill of a poured polygon). A pair of item kinds whose object kinds all hold one value that differs from `GAP` is a cell: one more `clearance` rule, `<name>/<kind>-<kind>`, with `item_kind` on both sides (joined with the record's scopes), at the record's priority, governing above the rule of `GAP` of the same record.
- **A cell without a counterpart keeps the whole record unmapped, and the reason names it.** When the object kinds of one item kind disagree, no neutral rule says the pair; judging part of such a record would judge the rest of it with a value the record does not hold. The reason (`keys`) names the pairs of item kinds, for example `track to pad`. The stage then says its rules are incomplete for the document, as c0088 specifies; it cannot scope that to pairs (design, decision 5).
- **Entries the check holds no item for are named.** A cell for a fill, a region, text or a hole changes no rule; the rule of `GAP` carries those entries in its bag (`cells_not_lifted`).
- **The stage counts the cells.** `summary.clearance_cells` = `{judged, unjudged}` on document input: the entries of the document's clearance matrices that a rule holds, and those that none holds (`DesignRules.clearance_cells`, a new field with a default).
- **Read only.** `rulemap.lower` writes no matrix; a cell rule has an `item_kind` selector, which the writer reports as `scope-unsupported`.
- **Measured after** on `-02`, `-06` and `-08` (the heavy row with `FENOLITE_HEAVY=1`), with every finding class of `-08` explained.

Size: 1 design-day (a size, not time).

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `altium-project-reader`: ADDED "Cells of an object matrix"; MODIFIED "More forms of a Clearance record" and "Rules onto the neutral model".
- `altium-import`: MODIFIED "Rules where they map" (the bag and the native id of a cell rule).
- `altium-verification`: MODIFIED "Copper check on Altium boards" and "Clearance rules of a PCB document" (the cell counts).
- `backend-protocol`: MODIFIED "Design rules source" (`DesignRules.clearance_cells`).

## Non-goals

- No change of `checks/copper.py` or `checks/clearance.py`, and none of the neutral rule model: `copper.clearance` on a KiCad board is judged exactly as in 0.2.0. `checks/documents.py` gains one summary key on document input.
- No partial lifting of a record with a cell that has no counterpart, and no rule of severity `ignore` to leave its pairs unjudged: that would put rules into the model that the document does not hold (design, decision 5).
- No `IGNOREPADTOPADCLEARANCEINFOOTPRINT=TRUE` (not in v0.3), no scope function beyond c0125's, no hole clearance from the `Hole` cells (another neutral kind; "Out of scope").
- No matrix for `BoardOutlineClearance`.
- No committed Altium sample changes and no writer writes a matrix.
- No code or constant from any private project or organisation; test records are authored for Fenolite, and corpus files are read from the cache with Fenolite's own readers.
- No format fact from a decompiled tool or a transcribed parser: every fact has a row in `docs/formats/altium/rule-file.md` with a public source and a label.

## Evidence level required

`INFERRED` under the new row `H-A-RULE-CLEARANCE-CELLS` (which object kinds of the matrix are which copper items of the model). The entries and their kinds are measured on public documents (`CORPUS-VERIFIED`); only Altium's rule check can confirm the pairs a cell governs (a kit request; no step is run here).

## Impact

- Changed: `backends/altium/read/rules.py`, `adapter/rules.py`, `adapter/ids.py`, `backend.py`, `rulemap.py` (evidence), `backends/base.py` (`DesignRules.clearance_cells`), `checks/documents.py` (one summary key).
- Pages: `docs/formats/altium/rule-file.md` and `import.md`, `docs/altium.md`, `docs/cli-contract.md`, `docs/evidence/altium-roundtrip.md`, `docs/hypotheses.md`.
- Behaviour: the import of a PCB document with such a matrix holds more clearance rules; `fenolite check` on it judges clearance where it judged shorts only; the stage summary of a document check has one more key; the text of the `keys` reason of a matrix changes again (it names pairs of item kinds).
- Depends on: c0125 (this branch), c0084, c0088. Archive after them.
