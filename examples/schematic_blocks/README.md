# Functional block composition

These synthetic circuits were authored for Fenolite. Both scripts describe the same electrical
circuit; `design.py` adds presentation intent. They use generated symbols and need no vendor library.

Review the before/after builds in separate folders:

```console
fenolite build examples/schematic_blocks/grid.py --target altium --out build/blocks-before --dry-run --json
fenolite build examples/schematic_blocks/design.py --target altium --out build/blocks-after --dry-run --json
```

Confirm each reviewed `plan_id` with `--confirm --plan ID`. The second output includes
`.fenolite/schematic-composition.json` and `.fenolite/schematic-preview/signal_chain.SchDoc.svg`.
Compare the three ordered blocks and the passive branch near the core. Native acceptance and
exact font metrics remain unmeasured; review the actual `.SchDoc` in Altium.
