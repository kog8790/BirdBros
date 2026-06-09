""" ### SEGMENT: FILE OVERVIEW ###
PURPOSE:
Stores and retrieves the user's OpenAI API key for BirdBros Recycle Co.

MACOS BEHAVIOR:
- Prefer OPENAI_API_KEY environment variable when present.
- Otherwise read/write the key through macOS Keychain using the built-in
  `security` command.

DESIGN INTENT:
Keep API keys out of the app bundle and out of project source files.
"""

import os
import platform
import subprocess


SERVICE_NAME = "BirdBros Recycle Co"
ACCOUNT_NAME = "OpenAI API Key"
ENV_VAR_NAME = "OPENAI_API_KEY"


class api_key_store_error(Exception):
    pass


def get_openai_api_key():
    """Return the API key from environment first, then macOS Keychain."""
    env_key = os.getenv(ENV_VAR_NAME, "").strip()

    if env_key:
        return env_key

    return get_openai_api_key_from_keychain()


def get_openai_api_key_from_keychain():
    if platform.system() != "Darwin":
        return ""

    result = _run_security([
        "find-generic-password",
        "-s", SERVICE_NAME,
        "-a", ACCOUNT_NAME,
        "-w"
    ])

    if result.returncode != 0:
        return ""

    return (result.stdout or "").strip()


def save_openai_api_key(api_key):
    api_key = (api_key or "").strip()

    if not api_key:
        raise api_key_store_error("OpenAI API key cannot be blank.")

    if platform.system() != "Darwin":
        raise api_key_store_error("macOS Keychain is only available on macOS.")

    result = _run_security([
        "add-generic-password",
        "-U",
        "-s", SERVICE_NAME,
        "-a", ACCOUNT_NAME,
        "-w", api_key
    ])

    if result.returncode != 0:
        error_text = (result.stderr or result.stdout or "Unknown Keychain error").strip()
        raise api_key_store_error(error_text)

    return True


def delete_openai_api_key():
    if platform.system() != "Darwin":
        return False

    result = _run_security([
        "delete-generic-password",
        "-s", SERVICE_NAME,
        "-a", ACCOUNT_NAME
    ])

    return result.returncode == 0


def looks_like_openai_api_key(api_key):
    api_key = (api_key or "").strip()
    return api_key.startswith("sk-") and len(api_key) >= 20


def describe_key_source():
    if os.getenv(ENV_VAR_NAME, "").strip():
        return "environment"

    if get_openai_api_key_from_keychain():
        return "keychain"

    return "missing"


def _run_security(args):
    return subprocess.run(
        ["security"] + args,
        capture_output=True,
        text=True,
        check=False
    )

