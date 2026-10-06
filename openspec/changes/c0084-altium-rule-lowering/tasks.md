## 0. Entry check

- [ ] 0.1 Read `openspec list` and the living `altium-pcb-writer`, `altium-build`, `altium-project-reader` and `manufacturing-exports` specs. Write under this task, with the date: which of the changes this one depends on are archived (a missing one stops the tasks that name it, and say which); whether another change modified a requirement that this change supersedes ("Spec deltas and archive order" in the design lists them): then write the MODIFIED text from the living one before any code. Proof: `openspec validate c0084-altium-rule-lowering --strict --no-interactive` passes.

## 1. Facts and registers

- [ ] 1.1 For each neutral rule kind, record in `docs/formats/altium/pcb-copper.md` the Altium kind, its constraint fields and its record or text fields, each with a public source and a label; set each row of the proposed mapping to `exact` or to a reason, and write under this task which rows changed from the design. Register the sources and add the five rows to `docs/hypotheses.md`. Proof: `uv run pytest tests/unit/test_format_facts.py tests/unit/test_hypotheses_register.py tests/unit/test_provenance.py`.

## 2. Rule map and records

- [ ] 2.1 Write `rulemap.py` with `TABLE`, `lower` and `lift` for single scopes (scenarios of "Rule lowering table"). Proof: `uv run pytest tests/unit/backends/altium/test_rulemap.py tests/unit/test_import_graph.py`; `uv run pyright src`.
- [ ] 2.2 Add layer and pair scopes and the priorities (scenario "Class rule above the general rule"). Proof: `uv run pytest tests/unit/backends/altium/test_rulemap.py -k "scope or priority"`.
- [ ] 2.3 Map the same kinds in `read/rules.py` and empty `PENDING_KINDS` (scenario "Board outline clearance"). Proof: `uv run pytest tests/unit/backends/altium/read tests/corpus -k "altium and rule"`.

## 3. Build and export

- [ ] 3.1 Write the lowered rules in the build and report the others per kind (scenarios of "Rules in an Altium build"). Proof: `uv run pytest tests/unit/lens/test_altium_rules.py tests/unit/lens -k altium`.
- [ ] 3.2 Write `write_rule_file` and the export kind `altium-rul` (scenarios "Written file reads back" and "Rule file from a built project"). Proof: `uv run pytest tests/unit/exports/test_altium_rul.py tests/consistency`.

## 4. Oracle, sample and report

- [ ] 4.1 Write `tests/kicad/altium/test_rules_oracle.py`: KiCad's import of the built PcbDoc shows the kinds its importer reads; record which kinds it reads in `docs/evidence/altium-pcb.md`. Proof: `uv run pytest tests/kicad/altium/test_rules_oracle.py -rA` on KiCad 10.0.6.
- [ ] 4.2 Build the files of Part U into a folder outside the repository, write their SHA-256 beside the steps in `docs/evidence/altium-pcb.md`, and hand them to the maintainer with the steps of the design ("Author report"). Record his report in the "Reports" section of `docs/evidence/altium-pcb.md` (tool as `AD <major>.<minor>`, date, one generic outcome per step, no artefact) and in `docs/hypotheses.md`; fix any fault the report names, and give a refuted row a registered successor. Proof: `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_provenance.py`.
- [ ] 4.3 Document the table, the scopes and the export in `docs/altium.md` ("Rules") and `docs/exports.md`; update `explain.toml` for the new `where` of `altium.not-lowered`. Proof: `uv run pytest tests/consistency tests/unit/cli/test_explain_cmd.py tests/unit/test_repo_layout.py`.

## 5. Closing

- [ ] 5.1 Run the residue and full test suites. Proof: `uv run pytest tests/residue tests/corpus/test_manifest.py` and `uv run python tools/residue/scan.py` exit 0; `make check` passes; `openspec validate c0084-altium-rule-lowering --strict --no-interactive` passes; `gh pr checks` shows `unit`, `kicad-9` and `kicad-10` passing.
- [ ] 5.2 Update the evidence: every row of this change holds its measured level and result in `docs/hypotheses.md`, the cells of `backends/altium/claims.py` say what is written and at which level, and `uv run python tools/gen_evidence_matrix.py` regenerates `docs/evidence/matrix.md`. Proof: `uv run pytest tests/unit/test_provenance.py tests/unit/test_hypotheses_register.py tests/unit/backends/test_evidence_declared.py`.
- [ ] 5.3 Add to `CHANGELOG.md` under Unreleased: "An Altium build writes the script's rules by kind and scope, names every rule it cannot lower with its reason, and `export --kinds altium-rul` writes them as a rule file". Update `docs/roadmap.md`. Proof: `git diff --stat CHANGELOG.md docs/roadmap.md` lists both files.
