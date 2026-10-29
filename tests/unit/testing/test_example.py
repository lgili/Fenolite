# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Run the documented example in every platform unit job, including its committed golden."""

import runpy
from pathlib import Path


def test_example_in_platform_suite():
    path = Path(__file__).resolve().parents[3] / "examples/testing/test_design.py"
    namespace = runpy.run_path(str(path))
    namespace["test_connections"]()
    namespace["test_ground_picture"]()
