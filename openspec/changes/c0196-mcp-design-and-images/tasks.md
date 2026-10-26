## 0. Entry check

- [ ] 0.1 c0195 is archived, or this change waits for it: its `mcp-server` delta MODIFIES "Commands not exposed",
  which c0195 adds. Note the order under this task. Proof: `openspec validate c0196-mcp-design-and-images --strict --no-interactive`.

## 1. The edit command

- [ ] 1.1 `cmd_edit.py`: the two forms, the file kinds and size, the parse checks, the plan's `result` with the
  diff (scenarios "An exact edit planned and written", "An edit that breaks the script is refused", "An old
  text found twice"). Proof: `uv run pytest tests/unit/cli/test_edit_cmd.py tests/consistency -q`.
- [ ] 1.2 `docs/cli-contract.md` ("## edit"), the tested line of `edit` on the guide page `design-script`, and
  `tools/gen_agent_guide.py`. Proof: `uv run pytest tests/unit/agent -q`; `uv run python tools/gen_agent_guide.py --check`.

## 2. The server

- [ ] 2.1 `fenolite_edit`: `content` or `edits`, the input file in the state folder and its removal, the opt-in
  `--allow-edit` (scenarios "Edit through the server", "Edit listed only on request", "Edit not listed by
  default"). Proof: `uv run pytest tests/unit/mcp tests/unit/cli/test_mcp_cmd.py -q`.
- [ ] 2.2 Images: the PNG rows of a plan or a receipt as image content, the caps, the note of what was left out
  (scenario "A dry run of a render is seen"; skipped without `kicad-cli`, and run in the job `mcp` with it if the
  job installs it, else in `kicad-10`). Proof: `uv run pytest tests/unit/mcp/test_images.py -q`.
- [ ] 2.3 The official client reads a render's image in `test_sdk_oracle.py`. Proof: the job `mcp` passes in CI.

## 3. Documents and closing

- [ ] 3.1 `docs/mcp.md` (the edit option and its risk, the images and their caps), the guide page `recovery`,
  `README.md`, `openspec/README.md`. Proof: `uv run pytest tests/unit/agent tests/unit/test_agent_skill.py -q`.
- [ ] 3.2 `CHANGELOG.md` under `## [Unreleased]`. Proof: `uv run pytest tests/unit -k changelog -q`.
- [ ] 3.3 `make check-fast`. Proof: `make check-fast`.
