## 1. Fabrication read-back

- [x] 1.1 Add the Gerber, Excellon and position readers of the `kicad-cli` subset, refusing anything else (scenarios of "Read-back readers"). Proof: `uv run pytest tests/unit/exports/test_readback_readers.py -q`.
  - 2026-10-27: proof passed (11 tests). A drill coordinate without a decimal point is refused (zero suppression is ambiguous); `20.` and `20.0` are read.
- [x] 1.2 Add `export --readback` with the outline, drill, position and layer checks (scenario "A missing slot"). Proof: `uv run pytest tests/kicad/export/test_readback.py -rA` on `kicad-cli`.
  - 2026-10-27: proof passed on local `kicad-cli` 10.0.7 (2 tests): the bench reads back clean, and a slot dropped from its drill file is `export.readback-drill` naming `H1`, exit 5, nothing written.
- [x] 1.3 Record the subset in `docs/formats/kicad/drill.md` and `gerber.md`, register `H-K-READBACK-SUBSET`, add the six codes to `explain.toml`, document `--readback` and teach it on the `fabrication` page. Proof: `uv run pytest tests/unit/test_format_facts.py tests/unit/test_hypotheses_register.py tests/unit/cli/test_explain_cmd.py tests/unit/agent -q`.
  - 2026-10-27: proof passed (171 tests with the provenance test).
- [x] 1.4 `make check-fast`, CHANGELOG, and CI on the pushed commit (the jobs `kicad-9` and `kicad-10` run the read-back test). Proof: `make check-fast` and the required jobs green on the head of `c0203-fabrication-readback`.
  - 2026-10-27: `make check-fast` passed (14,121 passed, 38 skipped) after `tests/unit/exports/test_plan.py` learnt the six codes. CI on the pushed head is recorded below.
  - 2026-10-27: CI run 40430916418 on `020a46c` failed in `kicad-9` only: the test ran `export` without the job's `kicad-cli` and wrote the bench for major 10. It now passes `--kicad-cli` from `runner()` and writes for `major()`.
  - 2026-10-27: CI run 40436505283 on `caa4c6c`: every job green; the read-back test passed in `kicad-9` and `kicad-10`, so `H-K-READBACK-SUBSET` and the facts are `KICAD-VERIFIED (9.0.x, 10.0.x)`.
