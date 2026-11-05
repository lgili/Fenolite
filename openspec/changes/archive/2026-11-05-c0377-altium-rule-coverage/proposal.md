# Map more Altium design rules

## Why

The Altium rule mapper (`backends/altium/adapter/rules.py:103`) leaves 36 rule kinds unmapped in the
maintainer's boards, among them Clearance and Width with scopes the mapper does not support, PlaneConnect,
PolygonConnect, SolderMaskExpansion and PasteMaskExpansion; the Python import also leaves custom rules
without a DSL form (`importer/emit/design.py:640`). Each loss is declared, but the checks then run with
incomplete rules.

## What Changes

- An inventory of the unmapped kinds and scope forms, ranked by their effect on checks.
- Mapping, kind by kind, of the ones the model can hold, with public format evidence; the rest stay
  declared losses with a precise reason.

## Impact

Altium rule adapter, rules model, importer rule emission, docs/formats/altium.
