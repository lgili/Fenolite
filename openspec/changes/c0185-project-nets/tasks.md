## 0. Entry check

- [x] 0.1 Read the adapter's connectivity and `connectivity.md`; record the scopes it handles. Proof: `openspec validate c0185-project-nets --strict --no-interactive`.
  - 2026-10-25: the Altium backend's read of a `.PrjPcb` gives a `Design` whose nets already cross the sheets; `build` and `check` use the same design.
    - On `tests/data/altium/hier`, `SPI_CS` holds `U1-3` and `U2-1` from two sheets.
    - Each sheet's scene holds the sheet's own nets, with pins written `REF-PIN` as in the project.
    - A component's path names its module (`flash/U2`), not its sheet file, so the sheets of a net come from the sheets' scenes.
  - The branch is `c0185-project-nets`, from `c0184-visual-diff`. Proof passed.

## 1. Nets

- [x] 1.1 Add `view/project_nets.py` (scenario "A net through a port"). Proof: `uv run pytest tests/unit/view/test_project_nets.py -q`.
  - 2026-10-25: proof passed (2). A local net takes its project net by its pins, else by its own name. `cmd_view` compiles the project once per run, when a sheet of an Altium project is shown.
- [x] 1.2 Cross highlight between sheets and board in the page. Proof: `uv run pytest tests/unit/view -q`.
  - 2026-10-25: proof passed.
    - **Navigator:** each net shows its project net when it differs, and the number of sheets it reaches.
    - **Selection:** a net chosen on a sheet or the board is selected on the next document opened. Pages of other tabs follow through `BroadcastChannel`, and `Esc` clears the selection.

## 2. Closing

- [x] 2.1 Browser review on a public hierarchical project. Proof: the record under this task.
  - 2026-10-25, the agent, in the Chromium of the container (Playwright, headless). The public project set `altium-set:05` (S-0175: `cobra.PrjPcb`, four sheets and a board) was fetched and laid out as the project names it.
    - **Nets across sheets:** 3V3 reaches 3 sheets and GND 4. SDA, SCL, VBUS, USB_DP and USB_DN reach 2 each.
    - **Different names:** the label `USB_DP` is the project net `NetD301_4`, the name the board that Altium saved also uses. The Navigator shows `USB_DP → NetD301_4`.
    - **Following a net:** `USB_DP` chosen on `ch341.SchDoc` is selected on `type-c.SchDoc`, with a link back. On the board, the net's track is highlighted.
    - **Fixtures:** the same was checked on `tests/data/altium/hier` (SPI_CS from the MCU sheet to the flash sheet) and on `blink` (LED_A from the sheet to the board).
- [x] 2.2 Docs, fast gate. Proof: `make check-fast`.
  - 2026-10-25: proof passed (13 918 passed, 34 skipped). `docs/viewer.md` gained "Nets across sheets and the board".
