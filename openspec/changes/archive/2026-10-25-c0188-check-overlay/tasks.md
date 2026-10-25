## 0. Entry check

- [x] 0.1 Record the position forms of `check` findings per stage. Proof: `openspec validate c0188-check-overlay --strict --no-interactive`.
  - 2026-10-25: an issue holds `code`, `severity`, `message`, `where`, `hint` and `retryable`. It has no position field and no stage. Positions come in three forms:
    - **`drc.kicad`:** `where` joins the items of a violation. An item is named when Fenolite knows its id: a part `R1`, a pad `R1-2`, or a locator such as `/kicad_pcb/segment[0]`, `/kicad_pcb/zone[0]` or `/kicad_pcb/gr_line[0]`. Otherwise it is `@x,y` in mm (`drc_json.format_position`).
    - **`erc.kicad`:** the tool's own location (a symbol reference, `#015` for a power symbol), else `<sheet path>@x,y`.
    - **`copper.clearance`:** `where` names the two items, and the message ends `on <layer> at (x, y) mm`.
    - **The other stages:** `model.validate` names nets, `parity` and `netlist.*` name pads, `placement.rules` names parts, `zone.fill` names a zone by its entity id, and `length.rules` names nets.
  - The design records the consequences in decisions 3 and 4.
  - Branch `c0188-check-overlay`, from `c0187-review-panels`. Proof passed.

## 1. Overlay

- [x] 1.1 Add `view/check_overlay.py` (scenario "Two findings"). Proof: `uv run pytest tests/unit/view/test_check_overlay.py -q`.
  - 2026-10-25: proof passed (4).
  - The tests cover the scenario, names, locators (a zone through the scene's new `zones` list), copper messages, sheet paths, ERC findings kept off boards, and a reply that is not a check reply.
- [x] 1.2 Add `--check` (scenario "Not a check reply") and the Messages panel. Proof: `uv run pytest tests/unit/cli/test_view_cmd.py tests/unit/view -q`.
  - 2026-10-25: proof passed (103).
  - An `analyze` reply is exit 3, `FEN-3004`; a missing file is `FEN-3001`.
  - `--check run` on the Altium `blink` project writes nothing.
  - The page draws markers (`E` toggles them) and the Messages panel grouped by code.

## 2. Closing

- [x] 2.1 Browser review with a KiCad DRC of a public board. Proof: the record under this task.
  - 2026-10-25, the agent. `kicad-cli` 10.0.7 was installed in the container from the KiCad PPA; CI runs 10.0.6.
  - **Input:** the public demo project `interf_u` (KiCad repository, tag 10.0.6; corpus `kicad-demo-10-0-6-pcb-05`, `-pro-05`, `-sch-013`) in a scratch folder.
  - **Check:** `fenolite check` took 11.8 s and gave 198 findings: 3 errors (2 `starved-thermal`, 1 `copper-edge-clearance`), 188 warnings and 7 info.
  - **Placement:** 118 were placed on the board and 82 on the root sheet.
  - **Board:** a click on a `starved-thermal` finding made B.Cu current and zoomed to pad U5-16, where the single spoke KiCad reports is visible.
    - The first version put the marker in the middle of the zone the finding also names. The innermost rule (design, decision 4) fixed it.
    - Evidence shown: `KICAD-VERIFIED(kicad-cli 10.0.7)`.
  - **Sheet:** ERC findings sit on their symbols.
  - **`--check run`:** gave the same counts in 11.7 s and changed no file of the folder.
- [x] 2.2 Docs, agent guide, fast gate. Proof: `make check-fast`.
  - 2026-10-25: proof passed (13 934 passed, 34 skipped).
  - Changed: `docs/viewer.md` ("Check findings"), the `view` section of `docs/cli-contract.md`, a line in `references/files.md`, the regenerated guide (148 996 bytes) and the LEGAL-ANNEX row.
