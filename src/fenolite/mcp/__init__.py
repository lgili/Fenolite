# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The MCP server of ``fenolite mcp`` (capability mcp-server, change c0195; ``docs/mcp.md``).

``protocol`` speaks the Model Context Protocol over standard input and output, for modern clients
(revision ``2026-07-28``) and for clients of the ``initialize`` handshake (``2025-11-25``, ``2025-06-18`` and
``2025-03-26``); ``tools`` turns the public commands into tools and runs each call as the command line;
``resources`` serves the agent guide. Standard library only.
"""
