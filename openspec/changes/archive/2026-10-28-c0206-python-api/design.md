## Context

`fenolite.cli.main.main` parses the command line, builds a `Context` (`cwd=Path.cwd()`), installs signal
handlers and calls `_dispatch` → `_perform`, which ran the command, applied the mutation protocol and
printed the envelope and the error object on the streams it was given. Commands already resolve relative
paths against `ctx.cwd` and return their writes as `PlannedWrite`s; only `restore -` reads stdin and only
`view --serve` blocks and writes on stderr. `tests/_cliexamples.py` and `tests/consistency/` run every
command's examples in process.

## Decisions

1. **One dispatcher, two printers.** `_perform`, `_dispatch` and `_failed` return a frozen `_Reply` (exit
   code, `Envelope | None`, `ErrorInfo | None`, `Result.text`) instead of writing. `main` prints it with
   `_print` (envelope, then error object, the order of before); `invoke(argv, *, cwd)` returns it as the
   JSON values `--json` prints (`json.loads(render_json(...))`, so the values are exactly the printed
   ones). A `CliError` raised before the reply (`--fields`, `--dry-run --confirm`) still reaches the top
   as before, where both map it, and an interrupt or a bug, with the shared `_failure`.
2. **`run` is JSON mode with an explicit working folder.** `invoke` builds the context with `mode="json"`,
   `cwd` given (resolved, so a plan id equals the one `fenolite` makes in the same folder: the id binds
   `str(cwd)` and `Path.cwd()` is resolved), progress records into a discarded buffer, and no signal
   handler (a host may run `run` off the main thread, and its handlers are its own). The keywords `seed`
   and `timestamp` become the flags `--seed` and `--timestamp` right after the command name; both a keyword
   and its flag raise `ValueError`.
3. **The edge `api → cli` is lazy and explicit.** `run` must reach the command registry, which lives in
   `cli`, and `cli` imports `api` at the top (`equivalent`, `convert`), so a top-level edge back would make
   a cycle. `run` imports `fenolite.cli.main` inside its body; `import fenolite.api` loads no command
   module. The layering test gains a `LAZY` table, `{"api": {"cli"}}`: such an edge passes only inside a
   function body, and the message of a top-level one says so. The `ALLOWED` row of `api` is unchanged, and
   `_allowed("api", "cli")` stays false. Moving `run` to a root module (allowed to import anything, and
   importable by `api`) would hide the same edge instead of declaring it.
4. **Terminal-only forms are usage errors.** The parser built for `run` (`in_process`) overrides argparse's
   `_print_message` and `exit`, so `--help`, including its abbreviations, prints nothing and is `FEN-2001`.
   `--text` is `FEN-2001` (the reply is the JSON envelope). `Context.in_process` lets `restore -` refuse
   before reading stdin and `view --serve` refuse before serving; both name the command-line form in the
   hint. `--version` is a top-level flag, which `run` never reaches: the command comes first.
5. **`Reply` holds JSON values, not the CLI's dataclasses.** `Envelope` and `ErrorInfo` live in
   `fenolite.cli.output`; freezing them as API types would freeze the CLI's internals. The envelope's
   contract is its schema `fenolite.envelope.v0`, which already holds for the mappings. `Reply` adds `ok`
   and `result`. Python faults (`command` that is not a name, a non-`str` argument, a `cwd` that is not a
   folder) raise; every other fault is in the reply with the exit code the command line gives.
6. **A short typed list.** `read_design` returns the `ReadSide` that `equivalent` compares (the reading is
   `api.sides.read_side`); `read_board` returns a new frozen `Board` (name, digest, backend, design,
   board-frame pads, the reader's warnings, evidence), because connectivity and distances need the pads
   and a `Design` alone does not carry them. `connectivity`, `analyze_current` and `analyze_distances` take
   a `Board` or a path and call `fenolite.analysis` with the defaults of `fenolite analyze`; a test compares
   their rows with the command's. The other kinds of `analyze` take many inputs: `run("analyze", ...)`
   serves them. Read errors reuse the `SideError` family; `ExtraMissingError` (`FEN-6001`) is new, for
   overlapping cut-outs without the `geo` extra, as the command reports it.
7. **The page is the freeze list.** `docs/api.md` lists every name of `fenolite.api.__all__` with its
   signature; a test fails when a public name is missing from it.

## Risks / Trade-offs

- `run` builds the parser on each call (about 45 commands); a caller in a tight loop pays it each time.
  Caching the parser would share mutable argparse state between calls, so it is not cached.
- A command that writes on `sys.stderr` itself would break "nothing printed": only `view --serve` does,
  and it refuses. The consistency test checks every command's examples with `capsys`.
- A design script run by `build` or `sync` redirects `sys.stdout` while it runs (`_script.py`), as on the
  command line; the redirection is restored before `run` returns.

## Open Questions

None.
