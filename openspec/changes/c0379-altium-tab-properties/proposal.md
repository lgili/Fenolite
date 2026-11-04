# Import Altium parameters that hold a TAB

## Why

Since c0363 (`importer/emit/design.py:1368`), `import --to python` refuses a whole Altium project when
any component property value holds a TAB: "native TAB preservation requires a KiCad source" (exit 3).
Before c0363 such projects imported. A real board in progress hits it on one parameter, so its import is
blocked even though the TAB carries no electrical meaning.

## What Changes

- An Altium source with a TAB in a property value imports again: the value is emitted with an escaped
  TAB in the `properties` mapping, or, if the DSL cannot print it, kept as a declared loss of that one
  property, never a refusal of the whole import.
- The KiCad native TAB ownership of c0363 is unchanged.

## Impact

`importer/emit/design.py`, the importer coverage kinds, docs, authored tests.
