# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Boards to Fenolite code: ``fenolite import PATH --to python --out DIR`` (change c0275; capability
board-to-code; ``docs/import.md``).

``source`` reads the inputs, ``emit`` writes the project folder (``design.py``, ``copper.py``, the vendored
``lib/``, the lock), ``provenance`` the header and ``PROVENANCE.json``, ``coverage`` what the DSL cannot
say, ``check`` compares the rebuilt design with the source, ``upgrade`` brings old KiCad files to the read
floor on private copies and ``adopt`` writes the source board with the identities a build derives.
"""

from __future__ import annotations

from fenolite.core.evidence import Evidence, Level
from fenolite.importer.codes import ISSUE_CODES, issue

EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-G-IMPORT-CODE",))
"""``INFERRED``: unit-tested on boards authored for Fenolite."""

__all__ = ["EVIDENCE", "ISSUE_CODES", "issue"]
