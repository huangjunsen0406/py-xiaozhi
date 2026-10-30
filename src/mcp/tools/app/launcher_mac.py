"""macOS launch helpers; observe open's result without waiting for the GUI."""

import os
import subprocess

from src.logging import get_logger

logger = get_logger()


def _open(arguments: list[str]) -> bool:
    try:
        result = subprocess.run(
            ["open", *arguments],
            capture_output=True,
            text=True,
            timeout=5,
            start_new_session=True,
        )
        return result.returncode == 0
    except (OSError, subprocess.SubprocessError) as error:
        logger.debug("[MacLauncher] open failed: %s", error)
        return False


def launch_application(app_name: str) -> bool:
    """Launch using checked LaunchServices helpers, then executable fallback."""
    if _open(["-a", app_name]):
        return True

    # A directly executable name is still supported. This is the GUI process,
    # not a short-lived launcher, so successful spawn is the handoff boundary.
    try:
        subprocess.Popen([app_name], start_new_session=True)
        return True
    except (OSError, subprocess.SubprocessError):
        pass

    app_path = f"/Applications/{app_name}.app"
    if os.path.exists(app_path) and _open([app_path]):
        return True

    return _open(["-a", app_name, "--background"])
