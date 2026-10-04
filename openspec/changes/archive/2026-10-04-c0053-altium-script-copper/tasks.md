## 1. Sources, hypotheses and the fact pages

- [x] 1.1 Confirm that the change needs no new source, hypothesis or format fact: the records are those of c0038 (`docs/formats/altium/pcb-copper.md`), and S-0161 and S-0166 are registered. Proof: `grep -cE '^\| S-016[16] ' docs/evidence/sources.md` prints `2`; `uv run pytest tests/unit/test_format_facts.py tests/unit/test_provenance.py tests/unit/test_altium_rows.py -q`.

## 2. The hand-over

- [x] 2.1 Add `lens.altium.refused_altium` and its test in `tests/unit/lens/test_altium_copper_source.py`. Proof: `uv run pytest tests/unit/lens/test_altium_copper_source.py -q`.
- [x] 2.2 In `cmd_build._run_altium`: run the in-memory KiCad build when the script has intents and `--copper-from` is absent, pass the script source, strip the zones, pass the copper issues through, refuse on an error, combine the evidence; with `--copper-from`, give the `altium.not-lowered` info. Write `tests/unit/cli/test_build_altium_script_copper.py` (records read back, both sources give the same bytes, refusal, staged part, zone, script without intents). Proof: `uv run pytest tests/unit/cli/test_build_altium_script_copper.py tests/unit/cli/test_build_altium.py tests/unit/cli/test_build_copper_from.py tests/unit/cli/test_build_zones_command.py -q`; covering every CLI scenario of "Script copper in an Altium build" and the new scenario of "Zones in a build".

## 3. The oracle

- [x] 3.1 Write `tests/kicad/altium/test_script_copper_oracle.py`. Proof: `uv run pytest tests/kicad/altium/test_script_copper_oracle.py -q` with `kicad-cli` 10.0.6; covering the scenario "Script to Altium and back".

## 4. Documentation and the sample

- [x] 4.1 Correct route 1 in `docs/altium.md` ("Copper") and the `result.copper` paragraph of `docs/cli-contract.md`; add step C7 to Part C of `docs/evidence/altium-pcb.md` with the SHA-256 of the fresh `blink_routed.PcbDoc`, and its check `-k protocol`. Proof: `uv run pytest tests/unit/cli/test_build_altium_script_copper.py -k protocol -q`; `grep -c "when it lands" docs/altium.md` prints `0`; `grep -c '^- \*\*C7\*\*' docs/evidence/altium-pcb.md` prints `1`.
- [x] 4.2 Build the sample for the maintainer in the ignored folder `build/` of the worktree. Proof: `uv run fenolite build examples/blink_routed/design.py --out build/c0053-sample --target altium --confirm --json` exits 0, and `git status --short` lists no sample file.

## 5. Closing

- [x] 5.1 Run the tests and the residue scan. Proof: `make check-fast`; `uv run pytest tests/residue -q`. The full `make check` runs once at the merge.
- [x] 5.2 Evidence labels: the build stays `INFERRED` and experimental, the envelope of a script-copper build names `H-G-FRAME-ROUTE`, and no page claims `ALTIUM-VERIFIED` for C7. Proof: `uv run pytest tests/unit/cli/test_build_altium_script_copper.py -k "evidence or protocol" -q`; `uv run pytest tests/unit/test_altium_rows.py tests/unit/test_hypotheses_register.py -q`.
- [x] 5.3 Update `CHANGELOG.md` under `## [Unreleased]`. Proof: `grep -c "c0053" CHANGELOG.md` prints `1`; `openspec validate c0053-altium-script-copper --strict`.
