---
topic: block-layouts
title: Block layout assets
summary: Exact versioned layouts, mirrored block poses, and capturing a laid-out block under plan and confirm.
---

# Block layout assets

A block can carry exact part positions and copper in `layouts/name.toml`:
`b.layout(reuse="layouts/name.toml", copper=True)`; the instance's `inst.layout(...)` wins over the
body's choice. Layout positions follow locked placements, the board, `edits.toml` and unlocked
`place()`, and precede staging. A part-set mismatch stages the children (`reuse.layout-stale`);
a net mismatch places the parts and copies no copper (`reuse.layout-nets`). Another block id or major
version refuses the build (`reuse.layout-block`). Review each instance's layout path, SHA-256 and status
in `result.placement.blocks`.

## Mirrored poses

```fenolite-design
from fenolite.dsl import Design, block, mm

design = Design("mirrored_blocks")
design.board(mm(35), mm(20))


@block
def cell(b):
    r = b.part("R", "Fenolite:Resistor", footprint="Fenolite:Chip_0603", value="1k")
    r.place(mm(2), mm(0))


a = design.use(cell, "a")
a.place(mm(10), mm(8))
b = design.use(cell, "b")
b.place(mm(25), mm(8), side="bottom")
```

## Capture a bench instance

Build a bench with one laid-out instance whose external nets all bind to its ports. Copper joining
outside pads stays out (`blocks.capture-copper-left`). Capture checks every pad within 1 µm before it
plans a write, stores only zone outlines, and leaves the block's Python for you to edit.

```fenolite-cmd
fenolite blocks capture bench/build --instance dut -o layouts/divider.toml --dry-run --json
fenolite blocks capture bench/build --instance dut -o layouts/divider.toml --origin anchor --anchor top --no-copper --confirm --json
```

Review `result.plan` and confirm with its `result.plan_id` through `--confirm --plan`. Without `-o`,
the block's source folder must lie under the working directory. `--origin pose` inverts the recorded
pose, mirror included; `--origin anchor` uses the named local part (smallest path by default).
Add `b.layout(reuse="layouts/divider.toml", copper=True)` after reviewing the captured asset.

Keep `fenolite-layout-base.json` with the board and `fenolite-base.json`; the cache may be removed.
Saved copy geometry and deletions survive rebuilds. If both CAD and the asset change differently,
`reuse.layout-conflict` blocks writes. Recapture the chosen CAD layout, restore the chosen geometry,
or review a discard; part `--take` does not choose copper.

```fenolite-cmd
fenolite build bench/design.py --out bench/build --discard-layout --dry-run --json
```

Read next: `placement`, `parts`, `recovery`.
