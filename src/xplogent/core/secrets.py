"""Encrypted secrets at rest.

Provider API keys are stored **Fernet-encrypted** in ``data_dir()/secrets.enc``
instead of as plaintext in ``.env``. The symmetric key lives in the OS keyring
when ``keyring`` is installed, otherwise in a ``0600`` key file beside the store.
A one-time migration lifts any existing plaintext ``.env`` secrets into the
encrypted store.

Everything degrades gracefully: if ``cryptography`` is unavailable, the helpers
become no-ops and the caller falls back to the plaintext ``.env`` path.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from xplogent.core.config import data_dir

_KEYRING_SERVICE = "xplogent"
_KEYRING_USER = "fernet-key"


def available() -> bool:
    """True when Fernet encryption is usable.

    Catches ``BaseException`` because a broken native build of ``cryptography``
    (e.g. missing ``_cffi_backend``) raises a pyo3 ``PanicException`` — a
    ``BaseException`` — on import. Such a machine must degrade to the plaintext
    ``.env`` path rather than crash.
    """
    try:
        import cryptography.fernet  # noqa: F401
        return True
    except BaseException:  # noqa: B036 - degrade gracefully on any import failure
        return False


def _store_path() -> Path:
    return data_dir() / "secrets.enc"


def _key_file() -> Path:
    return data_dir() / "secret.key"


def _load_or_create_key() -> bytes:
    """Return the Fernet key, preferring the OS keyring, else a 0600 key file."""
    from cryptography.fernet import Fernet

    # 1) OS keyring (best — the key never touches disk in our control).
    try:
        import keyring

        existing = keyring.get_password(_KEYRING_SERVICE, _KEYRING_USER)
        if existing:
            return existing.encode("ascii")
        key = Fernet.generate_key()
        keyring.set_password(_KEYRING_SERVICE, _KEYRING_USER, key.decode("ascii"))
        return key
    except Exception:  # noqa: BLE001 - no keyring backend; fall through to a key file
        pass

    # 2) 0600 key file in the data dir.
    path = _key_file()
    if path.exists():
        return path.read_bytes().strip()
    key = Fernet.generate_key()
    path.write_bytes(key)
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return key


def _fernet():
    from cryptography.fernet import Fernet

    return Fernet(_load_or_create_key())


def read_secrets() -> dict[str, str]:
    """Decrypt and return the stored secrets (``{}`` if none / unavailable)."""
    if not available():
        return {}
    path = _store_path()
    if not path.exists():
        return {}
    try:
        raw = _fernet().decrypt(path.read_bytes())
        data = json.loads(raw.decode("utf-8"))
        return {str(k): str(v) for k, v in data.items()}
    except BaseException:  # noqa: B036 - corrupt/rotated key or broken crypto → empty
        return {}


def write_secrets(updates: dict[str, str]) -> bool:
    """Merge ``updates`` into the encrypted store. Returns False if unavailable."""
    if not available():
        return False
    try:
        current = read_secrets()
        for k, v in updates.items():
            if v:
                current[k] = v
        blob = _fernet().encrypt(json.dumps(current).encode("utf-8"))
        path = _store_path()
        path.write_bytes(blob)
        try:
            path.chmod(0o600)
        except OSError:
            pass
    except BaseException:  # noqa: B036 - never let a crypto failure lose the caller's keys
        return False
    # Reflect immediately in-process so the running server sees new keys.
    for k, v in updates.items():
        if v:
            os.environ[k] = v
    return True


def load_into_env(keys: list[str]) -> None:
    """Load stored secrets into ``os.environ`` (without clobbering real env vars)."""
    if not available():
        return
    stored = read_secrets()
    for k in keys:
        if k in stored and not os.environ.get(k):
            os.environ[k] = stored[k]
