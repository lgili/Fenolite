# Preserve TAB in native custom-property values

## Why
The public pinned CM5 source now reaches the existing deliberate native-value TAB refusal after its mirror defect is repaired. Dropping the value or relaxing printable Part.properties would break ownership and validation contracts.

## Approved bounded change
Support ASCII TAB only inside the value of an otherwise valid, uniquely named native custom footprint property, using existing FootprintDef properties/slots just as for LF. Preserve original TAB/LF bytes, name, pose, styles and per-instance variants. Never emit a nonprintable Part.properties value. Native names remain printable; NUL, CR and all other nonprintable controls remain refused. No new API, model field, dependency, comparator, acceptance or waiver.

Authored native9/10 observations must precede implementation. Actual source data remains external. Successful writer representation is not a passing importer: the unchanged importer was recorded RED before its bounded fix was approved. Required full CI remains open.
