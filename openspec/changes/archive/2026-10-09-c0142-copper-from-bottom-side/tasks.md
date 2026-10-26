## 0. Entry check

- [x] 0.1 Find the comparison of pad positions of `--copper-from` and the recorded fact of how KiCad stores the pads of a bottom footprint. Proof: `design.md`, Context.
  - 2026-10-08: `lens.altium_copper.match_source`; `docs/formats/kicad/board.md`, `H-G-BOTTOM-STORE`, `KICAD-VERIFIED (9.0.x, 10.0.x)`.
- [x] 0.2 Reproduce with an authored board: the blink with `U1` on the bottom, written by Fenolite's own KiCad build. Proof: `uv run pytest tests/unit/cli/test_build_copper_from_bottom.py -q` on the old comparison.
  - 2026-10-08: 9 failed (exit 1), the negative control among them because the unmirrored board was accepted.

## 1. The fix

- [x] 1.1 `library_pad_positions` and its use in `match_source`. Proof: `uv run pytest tests/unit/cli/test_build_copper_from_bottom.py -q`.
  - 2026-10-08: 9 passed (exit 0).
- [x] 1.2 Top side and pinned bytes unchanged. Proof: `uv run pytest tests/unit/lens/test_altium_copper_source.py tests/unit/cli/test_build_copper_from.py tests/unit/lens/test_altium_pad_map_copper.py tests/unit/lens/test_altium_pin_map_copper.py tests/unit/lens/test_build_bytes_pinned.py tests/unit/cli/test_build_altium_script_copper.py tests/unit/lens/test_altium_determinism.py -q`.
  - 2026-10-08: 150 passed (exit 0).
- [x] 1.3 The KiCad oracle `tests/kicad/altium/test_copper_from_bottom_oracle.py`. Proof: collected and skipped here (no `kicad-cli`); 1 run on 10.x owed (3.2).

## 2. Documents

- [x] 2.1 `docs/altium.md` ("Checks of `--copper-from`"), `CHANGELOG.md`. Proof: `make check-fast`; every `uv run python tools/gen_*.py --check`; `uv run pytest tests/residue tests/corpus/test_manifest.py -q`; `openspec validate c0142-copper-from-bottom-side --strict`.
  - 2026-10-08: `make check-fast` 9795 passed, 18 skipped (exit 0); the three tools exit 0; 77 passed, 8 skipped (exit 0); the change is valid (exit 0), and `validate --all --strict` gives no error or warning for it (its 5 errors are those of c0084, c0085 and c0128).

## 3. Owed

- [x] 3.1 `make check` on the rebased branch before the merge.
  - 2026-10-09: closed by the full `make check` of 2026-10-08 on the release branch (c0154 task 4.3: exit 0, ruff clean, 1772 files formatted, pyright 0 errors, residue 0 hits with 11 waivers, `13828 passed, 2374 skipped` on Python 3.11.15; the residue and manifest tests are part of it) and the CI runs of `release-0.4.0` and its pull request #17, every job green (`unit` on Ubuntu with 3.11, 3.12 and 3.13, on macOS and on Windows, `kicad-9`, `kicad-10`, `routing` on KiCad 9 and 10, `wheel`, `dco`): 37836186018 (`32a19b3`), 37860490303 and 37860486308 (`acba81b`, whose tree is the released `591dc00` and `dev` at `a8732fc`); `openspec validate --all --strict --no-interactive` on 2026-10-09 reports only the known errors (c0084, c0085 twice, c0086, c0128) and long-requirement warnings, none for this change.
- [x] 3.2 `tests/kicad/altium/test_copper_from_bottom_oracle.py` on KiCad 10.x in CI.
  - 2026-10-09: ran in the `kicad-10` job (kicad-cli 10.0.6, `FENOLITE_REQUIRE=kicad,corpus`, so a skip there is a failure; the job selects `tests/kicad tests/corpus` with no marker filter) of CI runs 37860490303 and 37860486308 on `acba81b` (the tree of `0.4.0`) and 37836186018 on `32a19b3`, all green. The file is on that tree, marked `needs_kicad` only, and skips on major 9 alone.
