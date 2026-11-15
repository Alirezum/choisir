"""Cross-process advisory locking for choosier state files.

The lock is a sibling ``<name>.lock`` file. It is coordination metadata only:
it carries no user data, is never read as application state, and is safe to
leave behind. It is zero bytes on POSIX and contains a single NUL byte on
Windows, where ``msvcrt`` needs a lockable byte. This module never creates the
parent directory; callers that own their directory create it first.
"""

import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

if sys.platform == "win32":
    import msvcrt
else:
    import fcntl


@contextmanager
def exclusive_lock(file: Path) -> Iterator[None]:
    """Hold the exclusive sibling lock for the duration of the block.

    Raises:
        OSError: If the lock file cannot be opened. A missing parent
            directory is not created here and surfaces as ``FileNotFoundError``.
    """
    lock_path = file.with_name(f"{file.name}.lock")
    handle = open(lock_path, "a+b")
    try:
        if sys.platform == "win32":
            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(b"\0")
                handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
        else:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        try:
            if sys.platform == "win32":
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()
