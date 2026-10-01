## Why

c0009 reads boards; nothing writes them. `build` (c0011), fill (c0015), routing (c0016) and layout preservation (c0019) need a `.kicad_pcb` for KiCad 9.0 or 10.0, and the targets differ: 9.0.9 rejects nets referenced by name, and 10.0 no longer writes the numbered net table (`H-K-TOK-NETNAME`, `H-K-TOK-OBSOLETE`; S-0030). Library footprints must be placed on either side, yet bottom storage, flip and pad angles are still `INFERRED` from one footprint (`H-G-BOTTOM-STORE`, `H-G-FLIP`, `H-G-PAD-ANGLE-ABS`; S-0019). KiCad 9.0 renumbered board layers (S-0030), so KiCad 8 boards cannot be rewritten safely. A DRC verdict needs the JSON report, whose schema exists only in KiCad's tree (S-0055, S-0056).

## What Changes

- `pcb.py`: `write_board(design, *, target, allow_lossy)` returns `WriteResult(text, issues)`. It applies the target policy, writes the header with `generator_version "<target>.0"`, rewrites every net reference into the target's form, drops rows 10.0 no longer writes, inserts created content in the order KiCad 10.0.6 writes it, assigns KiCad uuids, lowers `Board.outline`, reconciles Reference and Value, and ends with `check_emittable`.
- `versions.py`: `LossyWriteError` (`FEN-7001`) and `LegacyEditRefusedError` (new `FEN-7003`). KiCad 8 boards become read-only.
- `backends/kicad/embed.py` (new): `place_footprint` places a library definition on the top or bottom side, with uuids and ids derived from a caller key. `footprint_extent` gives its courtyard or pad box.
- `backends/kicad/drc.py` (new): `read_drc_report` into neutral `DrcItem`, `DrcViolation` and `DrcReport` (`backends/base.py`), plus `KicadCli.drc`.
- Global flags `--kicad-version 9|10` and `--allow-lossy`. The KiCad capability report gains its write fields and the `write` operation (`KicadBackend.write`).
- Authored CC0 9.0-format copies of `Mini_LED_THT_3mm` and `Mini_QFP-32_7x7mm_P0.8mm`.
- Oracle tests in `tests/kicad/board/`; probe results pinned per `kicad-cli` version.
- `docs/formats/kicad/drc.md`, writer facts in `board.md`, sources S-0055 … S-0058, hypotheses `H-K-PCB-WRITE`, `H-K-GENVER` and `H-K-DRC-JSON`.

Estimated at 7.75 days (design, "Budget").

## Capabilities

### New Capabilities
- (none)

### Modified Capabilities
- `kicad-file-backend`: board writing per target, net forms, lossy writes, read-only KiCad 8 boards, projections, uuids, outline lowering, footprint embedding and DRC report reading (ADDED).
- `backend-protocol`: write capability fields, `WriteResult` and the neutral DRC report (ADDED).
- `cli-contract`: `--kicad-version`, `--allow-lossy` and `FEN-7003` (ADDED).
- `kicad-oracle`: written boards on both majors, library parity of placements, DRC verdicts from JSON, content kept on write, probe results per version (ADDED).
- `kicad-slots`: slot source for read and created entities (ADDED).
- `design-model`: placed copies (ADDED); MODIFIED `Slots for lossless round-trip` and `Identifier derivation` (full text copied).

## Non-goals

- `.kicad_mod` and `.kicad_dru` writers (c0018), `.kicad_pro` synthesis (c0010), `.kicad_wks` (c0012).
- Downgrade from 10 to 9, and writing KiCad 8 sources (capability resolver, v0.5a).
- Commands that write boards: `build` (c0011) and `fmt` (v0.2a).
- DRC findings as issues, RT2 and byte identity (c0020); zone fills (c0015); `inspect` (c0013).
- Editing projected fields other than Reference and Value (v0.2a), and imitating KiCad's save-time sort.

## Evidence level required

- Written boards load and count: `KICAD-VERIFIED` on 10.0.6 (local and `kicad-10`) and 9.0.9 (`kicad-9`) for the triad (`H-K-PCB-WRITE`). Writing arbitrary designs stays `INFERRED`.
- Bottom placement and pad angles: `KICAD-VERIFIED (10.0.x)` from DRC library parity; `(9.0.x)` only if `H-K-LIB-DRC` holds on 9.0.9. A refuted row gets a `-2` successor.
- DRC report reading: `KICAD-VERIFIED` on both majors (`H-K-DRC-JSON`).
- Flags, error codes, uuid and id derivation: mechanical (unit tests).

## Impact

- New modules `embed.py` and `drc.py`. Extended `pcb.py`, `layers.py`, `_fpmap.py`, `cli.py`, `versions.py`, `backend.py`, `backends/base.py` and `cli/`. Model and schemas unchanged.
- Rows in `sources.md`, `hypotheses.md`, `PROVENANCE.md`, `LEGAL-ANNEX.md`, `MANIFEST.toml` and `docs/cli-contract.md`. No runtime dependency.
- Depends on c0009 (`read_board`, `rebuild_board`, `ModelSource`, `KicadCli`, `layers.py`, `_fpmap.py`, the pad-angle pair, `backends/base.py`) and c0014 (the `H-K-LIB-DRC` row and the register guard).
