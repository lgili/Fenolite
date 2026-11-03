---
topic: model-versions
title: Reading and migrating model folders
summary: Read and migrate canonical model folders.
---

# Reading and migrating model folders

A build stores six JSON model layers in `out/.fenolite`. The model's `schema_version` is `1.0`;
it is independent of the package and CLI versions. Coordinates stay integer nanometres and angles
stay integer microdegrees.

Reading a version `0` folder migrates it in memory, reports `model.migrated` and writes nothing.
The `0 -> 1.0` step keeps existing fields, ids, defaults and opaque backend fragments.
`migrate` saves that folder in the current form:

```fenolite-cmd
fenolite migrate out/.fenolite --dry-run --json
fenolite migrate out/.fenolite --confirm --plan PLAN_ID --json
fenolite explain model.migrated --json
```

Read `result.from`, `result.to`, `result.steps` and all six writes of `result.plan`. Replace `PLAN_ID`
with the returned `result.plan_id`. Confirmation writes every model layer or none, with a `.bak`
for each previous file. A changed layer invalidates the reviewed plan. Native CAD files stay as they
are. The command executes no script or CAD tool; evidence is `INFERRED`.

A current folder plans no writes and exits 0, as this recipe shows:

```fenolite-recipe starter
fenolite build blink/design.py --out blink/build --confirm --json  # exit 0
fenolite migrate blink/build/.fenolite --dry-run --json  # exit 0
fenolite migrate blink/build/.fenolite --confirm --json  # exit 0
```

A future version, including `1.1`, gives `FEN-3002` (exit 3). Use a reader that supports that version;
do not change the marker by hand. Malformed versions and missing migration paths give `FEN-3004`.
There is no downgrade.

Read next: `files`, `recovery`.
