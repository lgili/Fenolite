## Why
Native child sheets with no title block become the board’s dated title block after strict import. This produces real levelS and level8 differences in RoyalBlue. Empty drawn metadata currently means authored inheritance; extraction loses native blank intent.

## What Changes
- Preserve native empty sheet metadata with the existing explicit blank-title representation.
- Keep authored omission meaning board inheritance, with unchanged default writer bytes.
- Add authored dated-parent/blank-child full proofs and native drawing-sheet controls.

## Impact
KiCad extraction only and focused regression/evidence docs. No new public model, DSL key, command, code or mask tolerance. c0337 style rendering remains separately scoped.
