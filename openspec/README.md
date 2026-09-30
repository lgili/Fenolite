# openspec

Spec-driven development with [OpenSpec](https://github.com/Fission-AI/OpenSpec).

- `specs/<capability>/spec.md` — the current, normative requirements (SHALL/MUST + scenarios).
- `changes/<id>/` — one proposed change: `proposal.md` (why), `design.md` (how), `specs/` (deltas),
  `tasks.md` (≤ 1-day tasks, each with the command that proves it).
- `config.yaml` — project context and artefact rules injected into every change.

No code lands without a change. Archive a change with `openspec archive <id>` once all tasks are done.
