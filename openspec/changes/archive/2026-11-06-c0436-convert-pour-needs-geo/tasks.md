# Tasks: c0436

- [x] 1.1 The KiCad-to-Altium direction asks for `computed` when no pour mode is given. Proof:
  `uv run pytest tests/unit/cli/test_convert_cmd.py -q -k pour`.
- [x] 1.2 `FEN-6001` names the default mode, the geo extra and `--altium-pour outline`. Proof: the same test.
- [x] 1.3 Docs, explain entry, help and agent guide. Proof: `uv run python tools/gen_agent_guide.py --check`,
  `uv run python tools/gen_cli_surface.py --check`.
- [x] 1.4 The KiCad oracle helpers pick `outline` without the extra. Proof: `uv run ruff check tests/kicad`.
