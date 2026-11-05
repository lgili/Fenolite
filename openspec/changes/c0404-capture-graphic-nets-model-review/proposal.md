# c0404: copper graphic nets in block capture, and a model review check that catches real staleness

## Why

Two small defects found on 2026-11-05:

- `fenolite blocks capture` reads the user's board and maps the net ids of its pads, tracks, arcs, vias and
  zones to the recorded circuit (`cli/_blocks_capture.py`, `current_model`). Copper graphics carry a net id
  since c0277, but `current_model` left them with the ids of the read board, which name no net of the
  recorded circuit.
- `uv run python tools/model_review.py --check` reports "inventory is stale" on `dev` 1169f10d although no
  model class, field, type, default or extension key changed. The inventory compares its reader index too,
  which lists every source file that spells a field name, so almost any source edit makes it stale; and no
  test runs the check, so the stale state went unnoticed.

## What

- `current_model` maps the net id of each graphic that has one, as it does for the other copper items.
- `tools/model_review.py --check` compares what a review decides on: classes, fields, types, defaults,
  extension keys and decisions. Moved reader locations print a note and do not fail. The stored inventory is
  written again with today's reader index.
- A unit test runs the check against the stored inventory, so a model change without a new inventory fails
  `make check-fast`.

## Impact

`src/fenolite/cli/_blocks_capture.py`, `tools/model_review.py`, the stored inventory
`openspec/changes/archive/2026-11-04-c0218-model-schema-1-0/review.json`, two test files. No public name,
model field or evidence level changes.
