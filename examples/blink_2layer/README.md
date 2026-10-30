# Blink, two layers

A mini MCU drives an LED through a resistor on a 50 mm × 30 mm two-layer board (`design.py`). The
libraries come from the authored CC0 mini library (`tests/data/libs`) through this folder's
`fp-lib-table` and `sym-lib-table`.

## Edits made in KiCad survive a rebuild

The script and the KiCad project are merged per property (`docs/lens.md`, "Three-way merge"): every build
writes `fenolite-base.json` beside the board, and the next build compares the script and the board with
it. One side changed: it wins. Both changed: `sync.conflict`, which `--take` resolves. The loop below is
run by `tests/unit/test_examples.py`; the two KiCad steps are token edits there.

```sh
fenolite build examples/blink_2layer/design.py --out build/blink --confirm
# in KiCad: give R1 the value 4k7 and save the board
fenolite build examples/blink_2layer/design.py --out build/blink --dry-run
# R1#value is kept from the board (edit.unrecorded); now change value="330" to value="470" in design.py
fenolite build examples/blink_2layer/design.py --out build/blink --dry-run
# exit 5: sync.conflict R1#value (both-changed); keep the KiCad value
fenolite build examples/blink_2layer/design.py --out build/blink --take cad:R1#value --confirm
fenolite sync examples/blink_2layer/design.py --out build/blink --to-source --confirm
# edits.toml beside design.py now holds value = "4k7" over "470"; commit it with the script
fenolite build examples/blink_2layer/design.py --out build/blink --confirm
```

`--take code:R1#value` would have written the script's `470` instead. `fenolite sync --to-source --check`
exits 5 while a conflict is open.
