# Blocks and tests

All example data here is authored for Fenolite and released under CC0-1.0.
`design.py` remains the two-channel hierarchical block example. `divider.py` adds the shipped-test
convention for the project block `Example:divider` (change c0270):

- `usage/divider.py` builds a whole circuit with a connector and a bench supply.
- `tests/test_divider.py` uses plain assertions and `fenolite.testing`, without pytest.
- `golden/divider.json` pins its canonical circuit and rules at seed 0 and the fixed test timestamp.

From this folder, run `fenolite blocks test --json`; local modules with convention files are discovered.
From the repository root, run
`uv run fenolite blocks test Example:divider --from examples/blocks/divider.py --json`.
Regenerate only after reviewing `--golden --dry-run`, then confirm its `--plan` id and commit the diff.
The arbitrary resistor values and positions teach the API; they are not a product design.
