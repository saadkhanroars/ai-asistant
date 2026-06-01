"""
browser_registry.py — Detect installed browsers and launch with URLs.

Detection: common paths, Start Menu shortcuts, registry (Windows).
"""

from __future__ import annotations

import os
import subprocess
import webbrowser
from pathlib import Path

BROWSER_ALIASES: dict[str, str] = {
    "msedge": "edge",
    "microsoft edge": "edge",
    "google chrome": "chrome",
    "chromium": "chrome",
}

BROWSER_EXE_NAMES: dict[str, list[str]] = {
    "brave": ["brave.exe"],
    "chrome": ["chrome.exe"],
    "edge": ["msedge.exe"],
    "firefox": ["firefox.exe"],
    "opera": ["opera.exe", "launcher.exe"],
}

BROWSER_PATHS: dict[str, list[str]] = {
    "brave": [
    r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe",
    r"%ProgramFiles%\BraveSoftware\Brave-Browser\Application\brave.exe",
    r"%ProgramFiles(x86)%\BraveSoftware\Brave-Browser\Application\brave.exe",
],
    "chrome": [
        r"%ProgramFiles%\Google\Chrome\Application\chrome.exe",
        r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe",
    ],
    "edge": [
        r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe",
        r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe",
    ],
    "firefox": [
        r"%ProgramFiles%\Mozilla Firefox\firefox.exe",
        r"%ProgramFiles(x86)%\Mozilla Firefox\firefox.exe",
    ],
    "opera": [
        r"%ProgramFiles%\Opera\opera.exe",
        r"%ProgramFiles(x86)%\Opera\opera.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Opera\opera.exe"),
    ],
}

_cache: dict[str, str] | None = None


def normalize_browser(name: str) -> str:
    key = name.lower().strip()
    return BROWSER_ALIASES.get(key, key)


def is_browser_name(word: str) -> bool:
    return normalize_browser(word) in BROWSER_EXE_NAMES


def detect_browsers() -> dict[str, str]:
    """Return {browser_id: exe_path}."""
    global _cache
    if _cache is not None:
        return dict(_cache)

    found: dict[str, str] = {}
    for browser_id, paths in BROWSER_PATHS.items():
        for pattern in paths:
            path = os.path.expandvars(pattern)
            if path and os.path.isfile(path):
                found[browser_id] = path
                break

    _scan_start_menu_shortcuts(found)
    _scan_registry(found)

    _cache = found
    return dict(found)


def _scan_start_menu_shortcuts(found: dict[str, str]) -> None:
    roots = [
        os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs"),
        os.path.join(os.environ.get("PROGRAMDATA", ""), r"Microsoft\Windows\Start Menu\Programs"),
    ]
    for root in roots:
        if not os.path.isdir(root):
            continue
        for dirpath, _, files in os.walk(root):
            for fn in files:
                lower = fn.lower()
                for browser_id, exes in BROWSER_EXE_NAMES.items():
                    if browser_id in found:
                        continue
                    if any(exe in lower for exe in exes):
                        found[browser_id] = os.path.join(dirpath, fn)


def _scan_registry(found: dict[str, str]) -> None:
    try:
        import winreg
    except ImportError:
        return
    key_path = r"SOFTWARE\Clients\StartMenuInternet"
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
            i = 0
            while True:
                try:
                    sub = winreg.EnumKey(key, i)
                    i += 1
                    _read_browser_registry(sub, found)
                except OSError:
                    break
    except OSError:
        pass


def _read_browser_registry(name: str, found: dict[str, str]) -> None:
    import winreg

    for browser_id in BROWSER_EXE_NAMES:
        if browser_id in name.lower() and browser_id not in found:
            try:
                path_key = winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE,
                    rf"SOFTWARE\Clients\StartMenuInternet\{name}\shell\open\command",
                )
                cmd, _ = winreg.QueryValueEx(path_key, "")
                exe = cmd.strip('"').split('"')[0] if '"' in cmd else cmd.split()[0]
                if os.path.isfile(exe):
                    found[browser_id] = exe
            except OSError:
                pass


def list_available_browsers() -> list[str]:
    return list(detect_browsers().keys())


def _resolve_browser_exe(path: str) -> str | None:
    """Resolve .lnk shortcuts to executable paths (Windows)."""
    if not path:
        return None
    if path.lower().endswith(".exe") and os.path.isfile(path):
        return path
    if not path.lower().endswith(".lnk"):
        return None
    try:
        result = subprocess.run(
            [
                "powershell", "-NoProfile", "-Command",
                f'(New-Object -ComObject WScript.Shell).CreateShortcut("{path}").TargetPath',
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        target = result.stdout.strip()
        if target and os.path.isfile(target):
            return target
    except (OSError, subprocess.TimeoutExpired):
        pass
    return None


def launch_url(url: str, browser: str | None = None) -> str:
    """Launch browser with URL; never falls through to local file search."""
    if not url:
        return "No URL to open."

    if browser:
        key = normalize_browser(browser)
        exe = detect_browsers().get(key)
        resolved = _resolve_browser_exe(exe) if exe else None
        launch_exe = resolved or exe
        if launch_exe and (launch_exe.lower().endswith(".exe") or launch_exe.lower().endswith(".lnk")):
            try:
                if launch_exe.lower().endswith(".lnk"):
                    subprocess.Popen(
                        ["cmd", "/c", "start", "", launch_exe, url],
                        close_fds=True,
                    )
                else:
                    subprocess.Popen([launch_exe, url], close_fds=True)
                return f"Opened in {key}."
            except OSError as err:
                available = ", ".join(list_available_browsers()) or "none"
                return (
                    f"Could not start {key}: {err}. "
                    f"Available: {available}. Using default browser."
                )
        available = ", ".join(list_available_browsers()) or "none"
        try:
            webbrowser.open(url)
            return (
                f"Browser '{key}' not installed (available: {available}). "
                "Opened in default browser."
            )
        except Exception as err:
            return f"Browser error: {err}"

    try:
        webbrowser.open(url)
        return "Opened in default browser."
    except Exception as err:
        return f"Browser error: {err}"
