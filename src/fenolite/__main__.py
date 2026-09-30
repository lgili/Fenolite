# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Allow ``python -m fenolite``; behaves exactly like the ``fenolite`` console script."""

from fenolite.cli.main import main

if __name__ == "__main__":
    raise SystemExit(main())
