## 0. Entry check

- [ ] 0.1 Read `pcb-records.md` ("Pad"), `read.pcbstack`, `read.rules` and `read.scope`. Note under this task which rule scopes `read.scope` evaluates and how many pads of the public boards use each mask mode. Proof: `openspec validate c0181-altium-native-layers --strict --no-interactive`.

## 1. Reader and labels

- [ ] 1.1 Type the pad record's paste and mask expansions and modes in `read.pcb`. Proof: `uv run pytest tests/unit/backends/altium -k pad -q`.
- [ ] 1.2 Add `view/altium_layers.py` with the names and the order (scenario "A board with renamed layers"). Proof: `uv run pytest tests/unit/view/test_altium_layers.py -k names -q`.

## 2. Openings and page

- [ ] 2.1 Draw the mask and paste openings from the expansions (scenario "Manual and rule expansions"). Proof: `uv run pytest tests/unit/view/test_altium_layers.py -q`.
- [ ] 2.2 Use the names in the page and add the Properties rows. Proof: `uv run pytest tests/unit/view tests/unit/cli/test_view_cmd.py -q`.
- [ ] 2.3 Run the public boards (scenario "Public boards"). Proof: `uv run pytest tests/corpus/test_altium_layer_names.py -q`.

## 3. Review and closing

- [ ] 3.1 Review in a browser two public Altium boards: layer names and order, and the openings of three pads. Record the date and what was checked. Proof: the record under this task.
- [ ] 3.2 Docs (`docs/viewer.md`, `pcb-records.md` rows), `LEGAL-ANNEX.md` row and the fast gate. Proof: `make check-fast`.
- [ ] 3.3 The maintainer compares a board of their own with Altium: the layer tabs and the mask openings. Proof: the record under this task.
