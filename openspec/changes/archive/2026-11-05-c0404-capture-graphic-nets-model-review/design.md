# Design: c0404

## Capture

`current_model` keeps the recorded circuit's ids and maps each read item's net id by net name
(`net_id(ident)`). Graphics take the same mapping; a graphic without a net (off copper, or copper on no net)
keeps `None`, so a silk line is not given a net. The test builds the bench board, renames every net id of
the "read" design and checks that a copper polygon comes back with the recorded id and a silk line with
none. Without the fix the polygon keeps the read id.

## Model review check

The reader index is described in the tool itself as "review leads, not a runtime coverage claim". Making it
part of `--check` would make the archived inventory a file every change must rewrite. The check therefore
compares `reviewed(data)`, which drops `readers`, `generic_readers` and each extension key's `readers`.
Everything a maintainer decides on stays compared: a new, renamed or retyped field, a changed default, a new
or removed extension key, or a changed decision fails with exit 1. The stored file is still written whole
by the tool, so its reader lists are fresh at this commit.

`test_stored_inventory_is_current` runs `main(["--check"])` against the stored file; it needs no KiCad and
runs in `make check-fast`. `test_check_fails_on_shape_and_passes_on_moved_readers` proves both sides on an
authored inventory.
