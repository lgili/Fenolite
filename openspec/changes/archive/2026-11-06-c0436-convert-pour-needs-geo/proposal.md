# c0436: a conversion to Altium refuses the default pour without the geo extra

## Why

`convert --to altium` pours the polygons by default (`--altium-pour computed`, change c0215). Without the
`geo` extra it fell back to writing them unpoured with one `altium.pour-unavailable` warning and exit 0, so
a conversion could silently produce a PcbDoc with no poured copper. An explicit `--altium-pour computed`
already exits 6 (`FEN-6001`).

## What Changes

- `convert --to altium` and `fenolite.convert.convert_project(..., to="altium")`: the default pour mode is
  asked for explicitly, so without the `geo` extra the conversion raises `BackendUnavailable` and the CLI
  exits 6 (`FEN-6001`, `where` `--altium-pour`), plans nothing, and its hint names the extra
  (`pip install 'fenolite[geo]'`, `uv sync --extra geo`) and `--altium-pour outline`. `--altium-pour outline`
  converts as before.
- `fenolite build --target altium` is unchanged: its default still writes the outline with the warning
  (capability altium-build).
- Docs: `docs/cli-contract.md` (the option row and an exit 6 row), `docs/conversion.md`, the
  `altium.pour-unavailable` explain entry, the option's help and the agent guide page generated from it.

## Impact

- `src/fenolite/convert/to_altium.py`, `src/fenolite/convert/__init__.py`, `src/fenolite/cli/cmd_convert.py`,
  `src/fenolite/cli/data/explain.toml`.
- A caller of the API without the `geo` extra that converted boards with polygons now gets
  `BackendUnavailable`: pass `pour="outline"`. The KiCad oracle helpers `tests/kicad/_convcases.py` and
  `_slotsconv.py` choose `outline` when the extra is missing, as the fallback gave them before.
