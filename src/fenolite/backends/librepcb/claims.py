# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The seed reader's evidence is declared in reader; it exposes no generic board backend operations."""

from fenolite.backends.base import MatrixRow

MATRIX: tuple[MatrixRow, ...] = ()
