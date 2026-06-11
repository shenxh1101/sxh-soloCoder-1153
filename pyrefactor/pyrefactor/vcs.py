import os
import subprocess
from typing import Set


def get_untracked_files(directory: str) -> Set[str]:
    try:
        result = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            capture_output=True,
            text=True,
            cwd=directory,
            timeout=10,
        )
        if result.returncode == 0:
            untracked = set()
            for line in result.stdout.strip().split("\n"):
                if line:
                    untracked.add(os.path.normpath(os.path.join(directory, line)))
            return untracked
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return set()


def is_git_repository(directory: str) -> bool:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            capture_output=True,
            text=True,
            cwd=directory,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


def get_tracked_files(directory: str) -> Set[str]:
    try:
        result = subprocess.run(
            ["git", "ls-files"],
            capture_output=True,
            text=True,
            cwd=directory,
            timeout=10,
        )
        if result.returncode == 0:
            tracked = set()
            for line in result.stdout.strip().split("\n"):
                if line:
                    tracked.add(os.path.normpath(os.path.join(directory, line)))
            return tracked
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return set()