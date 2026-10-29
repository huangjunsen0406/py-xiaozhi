"""Source and PyInstaller launcher; the installed command uses src.cli."""

from src.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
