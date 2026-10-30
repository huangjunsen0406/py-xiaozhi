"""Source and PyInstaller launcher; the installed command uses src.cli."""

import sys

# A frozen executable is a bootloader, not a Python interpreter. Dispatch its
# private worker mode before importing CLI/configuration or any GUI runtime.
# The static import also makes PyInstaller collect the bundled worker module.
if __name__ == "__main__" and sys.argv[1:] == ["--mcp-plugin-worker"]:
    from src.mcp.plugins.subprocess_worker import main as worker_main

    raise SystemExit(worker_main())

from src.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
