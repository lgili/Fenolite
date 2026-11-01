## 0. Entry check

- [x] 0.1 Read `openspec list`, the living specs this change touches (`design-dsl`, `design-model`) and the state of c0246, c0248, c0249 and c0252. Write under this task the date, the base commit, and:
  - whether c0246's range type and its canonical text are archived, and under which name (`BlockParam` type `range`);
  - whether c0248's `design.part(device=...)` and its prefix field are archived, and how `b.part` should call them;
  - whether c0249's lock and allocator are archived, the allocator's call, and whether it takes paths with `/`;
  - which open change holds a delta of "Design structure and names", "Connections and pin designators" or "Identifier derivation". If one was archived, regenerate the MODIFIED block from the living text;
  - whether the prefix `prt` is still free in `core/ids.py`;
  - the maintainer's answers to the open questions of `design.md`.

  Proof: `npx -y @fission-ai/openspec validate c0251-circuit-blocks --strict`; `make check-fast`.
  2026-10-29: base `f6c0754d` (circuits-as-code with c0247 and c0249), then `a170bc55` merged in (c0246,
  dev at 0.7.0.dev0). c0246 is merged, not archived: `Range` with `Range.text()`, recorded as type `range`.
  c0248 is not merged: `b.part(device=...)` and the device's `ref_prefix` wait for it. c0249 is merged, not
  archived: `lock.assign_refs(design, lock, *, moves)` keys refs by path, `/` included; a block part is a
  c0249 part without a ref and with `name=`. Deltas of the three requirements are held by the open changes
  c0248, c0249, c0275 and c0277; none is archived, so no MODIFIED block was regenerated. `prt` was free.
  The open questions took the recommended answers (design.md, "Decided 2026-10-29"). openspec validate
  --strict passed; `make check-fast` passes except two tests that
  fail on circuits-as-code as well: the row of c0269's proposal (since renamed `H-A-BLOCK-ENTRIES`) breaks
  `test_altium_build.py::test_evidence` and `test_altium_rows.py::test_rows_are_well_formed`.

## 1. Model

- [x] 1.1 Add `BlockParam`, the fields `Module.block` and `Module.params`, `Port` and `Circuit.ports` to `model/circuit.py`, the prefix `prt` to `core/ids.py`, regenerate the schemas, and describe them in `docs/design-model.md` (scenarios "Block instance round trip", "Older circuit files", "Refused port values", "Refused params"). Proof: `uv run pytest tests/unit/model/test_circuit.py -k "block or port" -q`; `uv run python tools/gen_schemas.py --check`.
  2026-10-29: done; `Circuit.ports` sits after `modules` so `no_connects` stays the last field. Proof passed.

## 2. Blocks and parameters in the DSL

- [x] 2.1 Add `dsl/block.py` with `block`, `BlockDef`, `Block(Module)`, the builder methods `part`, `net`, `use` and `add`, `BlockInstance`, `Design.use`, and the re-exports from `fenolite.dsl` (scenarios "Bad signature", "Variadic keywords refused", "Direct call refused", "Duplicate local name", "Two functions named buck", "Local net of a nested block"). Proof: `uv run pytest tests/unit/dsl/test_blocks.py -q`.
- [x] 2.2 Bind and record the parameters (decision 3; scenarios "Defaults recorded", "Recorded forms", "Unrecordable parameter"). Proof: `uv run pytest tests/unit/dsl/test_block_params.py -q`.
- [x] 2.3 Allocate board refs of block parts through c0249's allocator and lock, with `ref=` winning (decision 8; scenarios "Two instances, no collision", "Allocated and explicit refs"). Proof: `uv run pytest tests/unit/dsl/test_blocks.py -k "instances or refs" -q`.
  2026-10-29: done (`Design.use`, `fenolite.dsl.block`); `b.part(device=...)` waits for c0248. Proof passed.
  2026-10-29: `b.part(device=...)` added with the merge of c0248 (the device's `ref_prefix` feeds the
  allocator); `tests/unit/dsl/test_device_hooks.py::test_block_part_from_a_device` passed.
  2026-10-29: done, with `Range` of c0246 recorded as `range`. Proof passed.
  2026-10-29: done through c0249's `assign_refs`; a `Part` added by ref takes it as its local name. Proof passed.

## 3. Ports and port nets

- [x] 3.1 Add `dsl/portnets.py`: port nets, groups, the naming rule and the refusal of two named nets. Extend `connect` to take port nets and net-like port handles (scenarios "Port net takes the outside name", "Unnamed group named by its source port", "Two named nets through a port"; the existing scenarios of "Connections and pin designators" keep passing). Proof: `uv run pytest tests/unit/dsl/test_block_ports.py -k nets tests/unit/dsl/test_connect.py -q`.
- [x] 3.2 Add `b.port` with the closed member table, member access, net-like handles and the shadowing check (scenarios "Interface port", "Bad direction", "Port as a net", "Shadowing name refused"). Proof: `uv run pytest tests/unit/dsl/test_block_ports.py -q`.
- [x] 3.3 In `to_model`, give `Module.block` and `params`, one `Port` per port with bound member net ids, the `KEYS` row `port`, and the port-net names (scenarios "Port ids from the owner path and the name", "Module scripts unchanged"). Proof: `uv run pytest tests/unit/dsl/test_ids.py -k ports tests/unit/dsl/test_convert.py -q`.
  2026-10-29: done; `same_net` also used by c0247's helpers, so they take port nets. Proof passed.
  2026-10-29: done; `MAIN_MEMBERS` is empty until c0252 names main members. Proof passed.
  2026-10-29: done; `tests/unit/dsl/test_convert.py` does not exist, the proof ran `tests/unit/dsl/test_to_model.py`.
  Passed.

## 4. Build checks and schematic groups

- [x] 4.1 Add `build.port-unused` and `build.block-net-escape` to `lens/build.py`, their `explain.toml` entries, and the closed-set test (scenarios "Port nobody wired", "Optional port", "Global net closed over"). Proof: `uv run pytest tests/unit/lens/test_build_blocks.py tests/unit/lens/test_build_issues.py -k "closed_set or block" -q`.
- [x] 4.2 Name the KiCad sheet of a block instance `<name> (<block name>)`, and give implicit Altium `schematic_block`s from block paths (scenarios "Sheet named after the block", "Implicit Altium groups", "No mode, no implicit intent"). Proof: `uv run pytest tests/unit/dsl/test_blocks.py -k schematic -q`; `uv run pytest tests/unit/lens/test_build_hierarchy.py tests/unit/test_composition_blocks.py -q`.
  2026-10-29: done; both checks read the model only (ports, block modules, net names). Proof passed.
  2026-10-29: done; `tests/unit/test_composition_blocks.py` does not exist, the proof ran
  `tests/unit/cli/test_schematic_composition.py` and `tests/unit/dsl/test_schematic_composition.py`. Passed.

## 5. Example, docs and guide

- [x] 5.1 Add `examples/blocks/design.py` (CC0, authored for Fenolite): the channel block, two instances and one nested block, placed. Add its build test, and its read-back test through `kicad-cli` in the KiCad CI job ("Built boards read back with the same connectivity"). Proof: `uv run pytest tests/unit/lens/test_build_blocks.py -k example -q` locally; the read-back test in CI (task 6.2).
- [x] 5.2 `docs/dsl.md`: section "Blocks" (decorator, `use`, parameters, ports, port nets and their naming rule, local nets, refs, the two codes, when to keep `Module`). `docs/schematic-composition.md`: implicit groups. Proof: `uv run pytest tests/consistency -q`.
- [x] 5.3 Agent guide (AGENTS.md rule 6): a tested line for `block`, `Design.use` and the two codes on the page `design-script`. Regenerate the generated pages. Proof: `uv run python tools/gen_agent_guide.py`; `uv run pytest tests/unit/agent/test_pages.py -q`.
  2026-10-29: done; `tests/kicad/build/test_blocks_build.py` passed locally on kicad-cli 10.0.6 and 9.0.9
  (docker), netlist groups as scripted and no parity finding.
  2026-10-29: done. Proof passed.
  2026-10-29: done on the page `parts` ("Blocks"), not `design-script`, whose 11985 bytes leave no room
  under 12000. Proof passed.

## 6. Changelog and CI

- [x] 6.1 `CHANGELOG.md`: one entry under `## [Unreleased]`. This waits until `dev` is at `0.7.0.dev0`: at `0.6.0` the v0.6 guard requires `[Unreleased]` to be empty. Proof: `uv run pytest tests/unit/test_release_record_v06.py tests/consistency -q` on the `0.7.0.dev0` base.
- [ ] 6.2 Push the batch to the working branch and confirm that the required unit and KiCad jobs pass on that exact commit. Run only `make check-fast` and the focused tests locally (AGENTS.md, workflow 4). Proof: the run of the commit on GitHub CI is green; `make check-fast` passes locally.
  2026-10-29: CI runs with the batch. `make check-fast` passes except two tests that
  fail on circuits-as-code as well: the row of c0269's proposal (since renamed `H-A-BLOCK-ENTRIES`) breaks
  `test_altium_build.py::test_evidence` and `test_altium_rows.py::test_rows_are_well_formed`.

  2026-10-29: open; dev is now at 0.7.0.dev0, but the coordinator writes the entries of the batch in
  circuits-as-code. Proposed entry: "**Blocks** (c0251): `@block` functions with typed ports, local nets,
  recorded parameters and allocated refs; `design.use`; `build.port-unused` and `build.block-net-escape`."
  2026-10-29: done: that entry under `## [Unreleased]` › `### Added` on `circuits-as-code`;
  `uv run pytest tests/unit/test_release_record_v06.py tests/consistency -q` passed.