"""capability-bridge entry point.

Default (no args)      -> run the MCP stdio server.
setup ...              -> one-shot installer (see capability_bridge/setup.py).
"""

from __future__ import annotations

import sys


def main() -> None:
    if sys.argv[1:] and sys.argv[1] == "setup":
        from capability_bridge.setup import setup_main

        setup_main(sys.argv[2:])
        return
    from capability_bridge.transports.mcp.server import main as server_main

    server_main()


if __name__ == "__main__":
    main()
