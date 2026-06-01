"""
system_apps.py — Reserved Windows system applications (high routing priority).

These names always launch the OS app unless the user explicitly requests
a file, folder, or extension (e.g. "open settings.json", "open file settings").
"""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass

# Explicit local target — skip system app short-circuit
_EXPLICIT_LOCAL_RE = re.compile(
    r"\bopen\s+(?:the\s+)?(file|folder)\s+",
    re.I,
)
_EXPLICIT_EXT_RE = re.compile(
    r"\.[a-z0-9]{2,5}\b",
    re.I,
)
_EXPLICIT_FOLDER_TAIL_RE = re.compile(
    r"\b(folder|directory)\s*$",
    re.I,
)


@dataclass(frozen=True)
class SystemApp:
    """One Windows system application entry."""

    app_id: str
    display_name: str
    command: str
    aliases: tuple[str, ...]


# command: URI (ms-settings:), bare exe, or full path
SYSTEM_APP_REGISTRY: tuple[SystemApp, ...] = (
    SystemApp(
        "settings",
        "Windows Settings",
        "ms-settings:",
        ("settings", "windows settings", "win settings", "system settings"),
    ),
    SystemApp(
        "notepad",
        "Notepad",
        os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "notepad.exe"),
        ("notepad", "text editor"),
    ),
    SystemApp(
        "calculator",
        "Calculator",
        "calc.exe",
        ("calculator", "calc"),
    ),
    SystemApp(
        "paint",
        "Paint",
        os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "mspaint.exe"),
        ("paint", "mspaint", "microsoft paint"),
    ),
    SystemApp(
        "cmd",
        "Command Prompt",
        os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "cmd.exe"),
        ("cmd", "command prompt", "command line"),
    ),
    SystemApp(
        "powershell",
        "PowerShell",
        os.path.join(
            os.environ.get("SystemRoot", r"C:\Windows"),
            "System32",
            "WindowsPowerShell",
            "v1.0",
            "powershell.exe",
        ),
        ("powershell", "pwsh", "windows powershell"),
    ),
    SystemApp(
        "taskmgr",
        "Task Manager",
        os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "Taskmgr.exe"),
        ("task manager", "taskmgr", "taskmgr.exe"),
    ),
)

_ALIAS_INDEX: dict[str, SystemApp] = {}


def _build_index() -> None:
    global _ALIAS_INDEX
    if _ALIAS_INDEX:
        return
    for app in SYSTEM_APP_REGISTRY:
        for alias in app.aliases:
            _ALIAS_INDEX[alias.lower().strip()] = app
        _ALIAS_INDEX[app.app_id] = app


def reserved_system_names() -> frozenset[str]:
    """All alias strings that map to a system app."""
    _build_index()
    return frozenset(_ALIAS_INDEX.keys())


def user_wants_explicit_local(user_text: str) -> bool:
    """
    True when the user clearly wants a file/folder, not the system app.
    Examples: open file settings, open settings.json, open settings folder
    """
    text = user_text.strip()
    if not text:
        return False
    if _EXPLICIT_LOCAL_RE.search(text):
        return True
    if _EXPLICIT_EXT_RE.search(text):
        return True
    if _EXPLICIT_FOLDER_TAIL_RE.search(text):
        return True
    return False


def resolve_system_app(target: str) -> SystemApp | None:
    """Match target text to a system app, or None."""
    _build_index()
    key = target.lower().strip()
    if not key:
        return None
    if key in _ALIAS_INDEX:
        return _ALIAS_INDEX[key]
    # First token only (e.g. "settings app" -> still settings if unambiguous)
    first = key.split(None, 1)[0]
    if first in _ALIAS_INDEX and len(key.split()) == 1:
        return _ALIAS_INDEX[first]
    return None


def launch_system_app(app: SystemApp) -> str:
    """Launch a system app by URI or executable."""
    cmd = app.command
    try:
        if cmd.endswith(":") and not cmd.lower().endswith(".exe"):
            os.startfile(cmd)
        elif os.path.isfile(cmd):
            os.startfile(cmd)
        else:
            subprocess.Popen(
                ["cmd", "/c", "start", "", cmd],
                close_fds=True,
            )
    except OSError as err:
        return f"Could not open {app.display_name}: {err}"
    return f"Opened system app: {app.display_name}"
