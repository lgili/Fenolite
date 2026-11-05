# Imported native rules

## ADDED Requirements

### Requirement: Import preserves native rule origin semantics

A supported KiCad project import SHALL preserve modeled Default and named netclasses through the existing DSL, preserve native hard floors through the declared digest-bound project carrier, and emit custom-rule DSL rows only for actual source custom rules. It SHALL preserve both native Pro floors and DRU overrides when both are present. Existing authored DSL minimum lowering SHALL remain unchanged.

#### Scenario: Project floor below named class

- GIVEN native min_clearance 0.0762 mm and a named class clearance 0.2032 mm
- WHEN importing and rebuilding
- THEN no invented unconditional clearance override replaces the native class/floor precedence

### Requirement: Native-context floor comparisons are explicit and traced

Path-based level6 comparisons with supported native project contexts SHALL compare the five supported floor values without removing existing canonical differences, and SHALL bind every consumed context input into hashes and write-plan dependencies. Pure Design comparisons SHALL make no independent native-floor equality claim.

#### Scenario: Tampered floor below every class

- GIVEN two otherwise equal supported projects whose hard floor values differ below every netclass value
- WHEN path-based level6 comparison runs
- THEN it reports the exact floor difference even though effective canonical class values remain equal

### Requirement: Native class comparison names its supported scope

After option B approval, path-based level6 SHALL additionally compare the seven supported modeled class length fields and effective class assignments using verified native numbered-pad partitions, without comparing raw escaped JSON strings or claiming unknown native class properties. Relevant ambiguity, malformed/inexact values, duplicate identity or unsupported aggregation SHALL not yield full native-context equality.

#### Scenario: Native class field changes below an unchanged floor

- GIVEN equal native projects with Default clearance 0.15 mm versus 0.2 mm and the same lower floor
- WHEN native-context level6 compares the projects
- THEN it reports a supported native netclass field difference
