# Provenance of `fenolite.safety`

File safety uses three public facts: the name and place of KiCad's lock file, and the attributes by which
Windows and macOS mark a file that a sync client keeps only online. Each is recorded with its source; the
paths a project holds are the format facts already recorded in `docs/formats/kicad/` and
`docs/formats/altium/project.md`. Nothing is copied from any tool.

| fact-or-area | public source | licence of source | date | how used |
|---|---|---|---|---|
| KiCad's lock file: `~` + file name + `.lck`, in the folder of the open file | S-0828, S-0829 | GPL-3.0-or-later developer documentation; read for facts, nothing copied | 2026-10-26 | facts only |
| Windows online-only attributes: `FILE_ATTRIBUTE_OFFLINE`, `FILE_ATTRIBUTE_RECALL_ON_OPEN`, `FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS` and their values | S-0830, S-0831 | Microsoft Learn documentation; PSF License Version 2 | 2026-10-26 | facts only |
| macOS dataless files: `SF_DATALESS` in `st_flags` | S-0831 | PSF License Version 2 | 2026-10-26 | facts only |
