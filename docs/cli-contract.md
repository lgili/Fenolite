# The `fenolite` CLI contract (v0)

Normative text: `openspec/changes/c0002-cli-contract/specs/cli-contract/spec.md` (archived into
`openspec/specs/cli-contract/` when the change is done). This page is the short human version.
The contract is frozen at 1.0; before that, a breaking change bumps the schema id.

## Output

- **JSON when stdout is not a terminal**, text when it is. `--json` / `--text` override.
- One JSON document per invocation on stdout, followed by a newline.
- `--fields a,b.c` keeps only those dotted paths of `result` (the rest of the envelope stays).

## Envelope — `schemas/fenolite.envelope.v0.json`

```json
{
  "ok": true,
  "command": "capabilities",
  "schema": "fenolite.capabilities.v0",
  "input": null,
  "result": {"...": "..."},
  "issues": [{"code": "kicad.drc.clearance", "severity": "error", "message": "...",
              "where": "...", "hint": "...", "retryable": false}],
  "evidence": {"level": "UNVERIFIED", "oracle": null, "hypotheses": []},
  "receipt": null,
  "elapsed_ms": 12
}
```

`input` is `{path, sha256, kind, format_version}` when the command read a design file.
`receipt` is `{written: [{path, sha256}], backup: [path]}` when the command wrote files.

## Errors — `schemas/fenolite.error.v0.json`

Whenever the exit code is not 0, stderr carries exactly one error object
`{code, message, hint, retryable, where}` (JSON mode) or one line `error FEN-NNNN: message (hint)`
(text mode). The first digit of the code equals the exit code.

## Exit codes

| Code | Meaning | Error family |
|---|---|---|
| 0 | success | — |
| 1 | internal failure (a bug) | `FEN-1xxx` |
| 2 | usage error | `FEN-2xxx` |
| 3 | input unreadable or from a future format version | `FEN-3xxx` |
| 4 | confirmation required (nothing was written) | `FEN-4xxx` |
| 5 | verification produced findings of severity `error` (same code as `kicad-cli`) | `FEN-5xxx` |
| 6 | external tool missing or incompatible | `FEN-6xxx` |
| 7 | operation not representable without loss | `FEN-7xxx` |

## Writing files

Commands that write are **mutating**. They never write unless asked:

| Invocation | Effect | Exit |
|---|---|---|
| `fenolite <cmd> … --dry-run` | `result.plan` lists every file that would be written; nothing is written | 0 |
| `fenolite <cmd> …` | same plan, error `FEN-4001`, nothing is written | 4 |
| `fenolite <cmd> … --confirm` | atomic writes (temporary file + rename), `.bak` of overwritten files unless `--no-backup`, `receipt` with SHA-256 | 0 |

## Determinism

`--seed INT` and `--timestamp ISO8601` fix every generated id and date: the same inputs and flags
produce byte-identical outputs.

## Discovery

`fenolite capabilities` lists commands (`name`, `mutates`, `schema`, `hidden`), backends, installed
extras, detected external tools (`kicad-cli`, `java`, `docker`) with versions, and whether any
enabled feature sends data off the machine. Agents should call it first.
