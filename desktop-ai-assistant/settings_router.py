"""
settings_router.py — Windows Settings deep links (ms-settings:).

Maps semantic setting IDs to URIs. No API or embeddings required.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

# setting_id -> ms-settings URI
SETTINGS_URIS: dict[str, str] = {
    "bluetooth": "ms-settings:bluetooth",
    "wifi": "ms-settings:network",
    "network": "ms-settings:network",
    "display": "ms-settings:display",
    "sound": "ms-settings:sound",
    "volume": "ms-settings:sound",
    "battery": "ms-settings:batterysaver",
    "night_light": "ms-settings:nightlight",
    "nightlight": "ms-settings:nightlight",
    "storage": "ms-settings:storagesense",
    "windows_update": "ms-settings:windowsupdate",
    "update": "ms-settings:windowsupdate",
    "privacy": "ms-settings:privacy",
    "apps": "ms-settings:appsfeatures",
    "notifications": "ms-settings:notifications",
    "focus": "ms-settings:quiethours",
    "accessibility": "ms-settings:easeofaccess",
    "language": "ms-settings:regionlanguage",
    "accounts": "ms-settings:yourinfo",
    "personalization": "ms-settings:personalization",
    "background": "ms-settings:personalization-background",
    "lock_screen": "ms-settings:lockscreen",
    "mouse": "ms-settings:mousetouchpad",
    "keyboard": "ms-settings:keyboard",
    "printers": "ms-settings:printers",
    "camera": "ms-settings:privacy-webcam",
    "microphone": "ms-settings:privacy-microphone",
}

SETTINGS_DISPLAY_NAMES: dict[str, str] = {
    "bluetooth": "Bluetooth",
    "wifi": "Wi‑Fi & network",
    "network": "Network",
    "display": "Display",
    "sound": "Sound",
    "volume": "Volume",
    "battery": "Battery saver",
    "night_light": "Night light",
    "nightlight": "Night light",
    "storage": "Storage",
    "windows_update": "Windows Update",
    "update": "Windows Update",
    "privacy": "Privacy",
    "apps": "Apps",
    "notifications": "Notifications",
    "focus": "Focus assist",
    "accessibility": "Accessibility",
    "language": "Language",
    "accounts": "Accounts",
    "personalization": "Personalization",
    "background": "Background",
    "lock_screen": "Lock screen",
    "mouse": "Mouse",
    "keyboard": "Keyboard",
    "printers": "Printers",
    "camera": "Camera",
    "microphone": "Microphone",
}


@dataclass(frozen=True)
class SettingsTarget:
    setting_id: str
    uri: str
    display_name: str


def resolve_settings(setting_id: str) -> SettingsTarget | None:
    """Resolve a canonical setting id to a launch target."""
    key = setting_id.lower().strip().replace(" ", "_")
    uri = SETTINGS_URIS.get(key)
    if not uri:
        return None
    name = SETTINGS_DISPLAY_NAMES.get(key, key.replace("_", " ").title())
    return SettingsTarget(setting_id=key, uri=uri, display_name=name)


def launch_settings(target: SettingsTarget) -> str:
    """Open a Windows Settings page."""
    try:
        os.startfile(target.uri)
    except OSError as err:
        return f"Could not open {target.display_name} settings: {err}"
    return f"Opened Windows Settings: {target.display_name}"
