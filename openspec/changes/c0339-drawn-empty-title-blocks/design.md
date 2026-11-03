## Diagnosis and review
2026-11-02 coordinator reviewed this approach before code. `DrawnSheet.block()` returns None for empty tuples (inherit board). `title_pairs(None)` in extraction currently returns an empty tuple, collapsing native blank into authored inherit. The writer then falls back to `board_block`, inserting a date on RoyalBlue child sheets. Source-bound diagnostic proof reports two S date additions and two footer pixel findings; no acceptance is involved.

## Existing representation
Use `(("title", ""),)` when extracted native title metadata is empty. This already expresses a truthy explicit TitleBlock with empty visible text; it is not an invented date or a new carrier. Authored empty tuples retain their documented inheritance semantics. Effective native readback normalizes empty blocks to the same explicit blank intent. Nonempty pairs remain unchanged. Test source and built native pages with real drawing sheets, not excluded frames.

## Validation
Before-fix dated-parent/blank-child controls must fail at S/8, then strict all-nine proofs pass with unchanged source. Actual CLI10 export must display the date on the parent only, for original and generated pages. Default22 scene maps and default build maps stay unchanged. Complete validation is coordinator batch CI; no full or parallel fast suite locally.

### Freeze compatibility
Explicit blank intent is resolved before writing the native sheet: it suppresses
board inheritance. A wholly empty resolved TitleBlock is then emitted as native
absence, so generated drawings without title metadata retain their exact bytes
after freezing. This does not replace the explicit blank marker with inheritance
in the drawn model and does not change nonempty parent metadata.
