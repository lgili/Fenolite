# Model folders and migrations

Fenolite writes six canonical JSON layers under a built project's `.fenolite/` folder. Its model
schema is `1.1`, independently of the package version and the CLI envelope contract. Lengths remain
integer nanometres and angles remain integer microdegrees.

Reading an older folder migrates it in memory and reports `model.migrated` with the steps. Reading
writes nothing. A current folder needs no migration. To save an older folder in the current form:

```sh
fenolite migrate build/.fenolite --dry-run --json
fenolite migrate build/.fenolite --confirm --plan PLAN_ID --json
```

Replace `PLAN_ID` with `result.plan_id` from the reviewed dry run. `result.from`, `result.to` and
`result.steps` describe the migration. Confirmation rewrites all six model layers atomically and
keeps each previous file as `.bak`, unless the global `--no-backup` option was requested. A changed
layer invalidates the plan. A folder already at `1.1` plans no writes and exits 0.

The `0 -> 1.0` step keeps every reviewed field, identifier, default, integer value and opaque backend
fragment. The `1.0 -> 1.1` step (change c0462: the selector ops `zone`, `hole` and `pad_type`) changes
nothing else, since a `1.0` folder holds none of the new ops. Each step changes the schema marker; canonical writing also records the current Fenolite package
version. The command leaves native CAD files and unrelated files in the model folder alone. It does
not execute a design script or a CAD program. Evidence stays `INFERRED` (`H-G-MODEL-OWN`), with no
new claim about a backend format.

A higher major or a higher minor of the current major is refused with `FEN-3002`, naming the folder
and reader versions. For example, this `1.1` reader refuses `1.2` before trying to decode unknown
content. A malformed version or missing migration path is `FEN-3004`. There is no downgrade path.

See [the version rule and history](design-model.md#model-schema-versions),
[the CLI contract](cli-contract.md#migrate) and `fenolite guide model-versions --text`.
