# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The emitter of ``fenolite import`` (change c0275, design decision 4): a pure function from the source
model to the files of a Fenolite project folder, written by ``printer``."""

from __future__ import annotations

from fenolite.importer.emit.design import Emission, Options, emit

__all__ = ["Emission", "Options", "emit"]
