"""Launch picked entries with the OS default program (UI-agnostic)."""

import os
import subprocess
import sys
from pathlib import Path


def launch_path(entry: Path) -> None:
    """Open an entry with the OS default handler (non-blocking).

    Raises:
        OSError: If no handler is available or launching fails.
    """
    if sys.platform == "win32":
        os.startfile(str(entry))
        return
    if sys.platform == "darwin":
        cmd = ["open", str(entry)]
    else:
        cmd = ["xdg-open", str(entry)]
    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError as e:
        raise OSError(f"No program available to open files ({cmd[0]})") from e
