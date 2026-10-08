# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The Altium verification kit: its steps, its files, the kit script, the check of a run's results and
the run record (capability altium-verification; ``docs/altium-kit.md``).

The package imports the standard library, ``fenolite.core`` and ``fenolite.verify`` only. What needs the
DSL, the lens or the checks (building a sample, judging a saved document) is an argument, and
``fenolite.cli._kit`` holds the functions that the ``kit`` command passes.
"""

from fenolite.verify.kit.manifest import (
    KIT_SCHEMA,
    Kit,
    KitSources,
    SampleFiles,
    build_kit,
    kit_digest,
    kit_files,
    load_kit,
)
from fenolite.verify.kit.script import SCRIPT_CALLS, script_text
from fenolite.verify.kit.steps import STEPS, Step, steps_markdown

__all__ = [
    "KIT_SCHEMA",
    "SCRIPT_CALLS",
    "STEPS",
    "Kit",
    "KitSources",
    "SampleFiles",
    "Step",
    "build_kit",
    "kit_digest",
    "kit_files",
    "load_kit",
    "script_text",
    "steps_markdown",
]
