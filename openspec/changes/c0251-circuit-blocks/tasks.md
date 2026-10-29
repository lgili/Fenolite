## 0. Entry check

- [ ] 0.1 Read `openspec list`, the living specs this change touches (`design-dsl`, `design-model`) and the state of c0246, c0248, c0249 and c0252. Write under this task the date, the base commit, and:
  - whether c0246's range type and its canonical text are archived, and under which name (`BlockParam` type `range`);
  - whether c0248's `design.part(device=...)` and its prefix field are archived, and how `b.part` should call them;
  - whether c0249's lock and allocator are archived, the allocator's call, and whether it takes paths with `/`;
  - which open change holds a delta of "Design structure and names", "Connections and pin designators" or "Identifier derivation". If one was archived, regenerate the MODIFIED block from the living text;
  - whether the prefix `prt` is still free in `core/ids.py`;
  - the maintainer's answers to the open questions of `design.md`.

  Proof: `npx -y @fission-ai/openspec validate c0251-circuit-blocks --strict`; `make check-fast`.

## 1. Model

- [ ] 1.1 Add `BlockParam`, the fields `Module.block` and `Module.params`, `Port` and `Circuit.ports` to `model/circuit.py`, the prefix `prt` to `core/ids.py`, regenerate the schemas, and describe them in `docs/design-model.md` (scenarios "Block instance round trip", "Older circuit files", "Refused port values", "Refused params"). Proof: `uv run pytest tests/unit/model/test_circuit.py -k "block or port" -q`; `uv run python tools/gen_schemas.py --check`.

## 2. Blocks and parameters in the DSL

- [ ] 2.1 Add `dsl/block.py` with `block`, `BlockDef`, `Block(Module)`, the builder methods `part`, `net`, `use` and `add`, `BlockInstance`, `Design.use`, and the re-exports from `fenolite.dsl` (scenarios "Bad signature", "Variadic keywords refused", "Direct call refused", "Duplicate local name", "Two functions named buck", "Local net of a nested block"). Proof: `uv run pytest tests/unit/dsl/test_blocks.py -q`.
- [ ] 2.2 Bind and record the parameters (decision 3; scenarios "Defaults recorded", "Recorded forms", "Unrecordable parameter"). Proof: `uv run pytest tests/unit/dsl/test_block_params.py -q`.
- [ ] 2.3 Allocate board refs of block parts through c0249's allocator and lock, with `ref=` winning (decision 8; scenarios "Two instances, no collision", "Allocated and explicit refs"). Proof: `uv run pytest tests/unit/dsl/test_blocks.py -k "instances or refs" -q`.

## 3. Ports and port nets

- [ ] 3.1 Add `dsl/portnets.py`: port nets, groups, the naming rule and the refusal of two named nets. Extend `connect` to take port nets and net-like port handles (scenarios "Port net takes the outside name", "Unnamed group named by its source port", "Two named nets through a port"; the existing scenarios of "Connections and pin designators" keep passing). Proof: `uv run pytest tests/unit/dsl/test_block_ports.py -k nets tests/unit/dsl/test_connect.py -q`.
- [ ] 3.2 Add `b.port` with the closed member table, member access, net-like handles and the shadowing check (scenarios "Interface port", "Bad direction", "Port as a net", "Shadowing name refused"). Proof: `uv run pytest tests/unit/dsl/test_block_ports.py -q`.
- [ ] 3.3 In `to_model`, give `Module.block` and `params`, one `Port` per port with bound member net ids, the `KEYS` row `port`, and the port-net names (scenarios "Port ids from the owner path and the name", "Module scripts unchanged"). Proof: `uv run pytest tests/unit/dsl/test_ids.py -k ports tests/unit/dsl/test_convert.py -q`.

## 4. Build checks and schematic groups

- [ ] 4.1 Add `build.port-unused` and `build.block-net-escape` to `lens/build.py`, their `explain.toml` entries, and the closed-set test (scenarios "Port nobody wired", "Optional port", "Global net closed over"). Proof: `uv run pytest tests/unit/lens/test_build_blocks.py tests/unit/lens/test_build_issues.py -k "closed_set or block" -q`.
- [ ] 4.2 Name the KiCad sheet of a block instance `<name> (<block name>)`, and give implicit Altium `schematic_block`s from block paths (scenarios "Sheet named after the block", "Implicit Altium groups", "No mode, no implicit intent"). Proof: `uv run pytest tests/unit/dsl/test_blocks.py -k schematic -q`; `uv run pytest tests/unit/lens/test_build_hierarchy.py tests/unit/test_composition_blocks.py -q`.

## 5. Example, docs and guide

- [ ] 5.1 Add `examples/blocks/design.py` (CC0, authored for Fenolite): the channel block, two instances and one nested block, placed. Add its build test, and its read-back test through `kicad-cli` in the KiCad CI job ("Built boards read back with the same connectivity"). Proof: `uv run pytest tests/unit/lens/test_build_blocks.py -k example -q` locally; the read-back test in CI (task 6.2).
- [ ] 5.2 `docs/dsl.md`: section "Blocks" (decorator, `use`, parameters, ports, port nets and their naming rule, local nets, refs, the two codes, when to keep `Module`). `docs/schematic-composition.md`: implicit groups. Proof: `uv run pytest tests/consistency -q`.
- [ ] 5.3 Agent guide (AGENTS.md rule 6): a tested line for `block`, `Design.use` and the two codes on the page `design-script`. Regenerate the generated pages. Proof: `uv run python tools/gen_agent_guide.py`; `uv run pytest tests/unit/agent/test_pages.py -q`.

## 6. Changelog and CI

- [ ] 6.1 `CHANGELOG.md`: one entry under `## [Unreleased]`. This waits until `dev` is at `0.7.0.dev0`: at `0.6.0` the v0.6 guard requires `[Unreleased]` to be empty. Proof: `uv run pytest tests/unit/test_release_record_v06.py tests/consistency -q` on the `0.7.0.dev0` base.
- [ ] 6.2 Push the batch to the working branch and confirm that the required unit and KiCad jobs pass on that exact commit. Run only `make check-fast` and the focused tests locally (AGENTS.md, workflow 4). Proof: the run of the commit on GitHub CI is green; `make check-fast` passes locally.
