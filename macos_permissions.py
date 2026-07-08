""" ### SEGMENT: FILE OVERVIEW ###
PURPOSE:
Small macOS permission helpers for BirdBros runtime permissions.

RESPONSIBILITIES:
- Check whether the current process is trusted for Accessibility control
- Trigger the macOS Accessibility trust prompt when available
- Open the macOS Accessibility settings pane

DESIGN INTENT:
Keep platform-specific permission checks isolated from the main app and UI logic.
"""

import ctypes
import ctypes.util
import subprocess
import sys


ACCESSIBILITY_SETTINGS_URL = (
    "x-apple.systempreferences:"
    "com.apple.preference.security?Privacy_Accessibility"
)


def is_macos():
    return sys.platform == "darwin"


def accessibility_trusted():
    if not is_macos():
        return True

    app_services_path = ctypes.util.find_library("ApplicationServices")

    if not app_services_path:
        return False

    app_services = ctypes.cdll.LoadLibrary(app_services_path)

    try:
        ax_is_process_trusted = app_services.AXIsProcessTrusted
        ax_is_process_trusted.restype = ctypes.c_bool
        return bool(ax_is_process_trusted())
    except Exception:
        return False


def request_accessibility_trust(prompt=True):
    if not is_macos():
        return True

    if accessibility_trusted():
        return True

    app_services_path = ctypes.util.find_library("ApplicationServices")
    core_foundation_path = ctypes.util.find_library("CoreFoundation")

    if not app_services_path or not core_foundation_path:
        return False

    app_services = ctypes.cdll.LoadLibrary(app_services_path)
    core_foundation = ctypes.cdll.LoadLibrary(core_foundation_path)

    try:
        ax_is_process_trusted_with_options = app_services.AXIsProcessTrustedWithOptions
        ax_is_process_trusted_with_options.argtypes = [ctypes.c_void_p]
        ax_is_process_trusted_with_options.restype = ctypes.c_bool

        if not prompt:
            return bool(ax_is_process_trusted_with_options(None))

        key_ref = ctypes.c_void_p.in_dll(
            app_services,
            "kAXTrustedCheckOptionPrompt"
        )
        true_ref = ctypes.c_void_p.in_dll(
            core_foundation,
            "kCFBooleanTrue"
        )

        keys = (ctypes.c_void_p * 1)(key_ref.value)
        values = (ctypes.c_void_p * 1)(true_ref.value)

        cf_dictionary_create = core_foundation.CFDictionaryCreate
        cf_dictionary_create.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.c_long,
            ctypes.c_void_p,
            ctypes.c_void_p,
        ]
        cf_dictionary_create.restype = ctypes.c_void_p

        cf_release = core_foundation.CFRelease
        cf_release.argtypes = [ctypes.c_void_p]

        options = cf_dictionary_create(
            None,
            keys,
            values,
            1,
            None,
            None
        )

        try:
            return bool(ax_is_process_trusted_with_options(options))
        finally:
            if options:
                cf_release(options)

    except Exception:
        return False


def open_accessibility_settings():
    if not is_macos():
        return

    subprocess.run(
        ["open", ACCESSIBILITY_SETTINGS_URL],
        check=False
    )

