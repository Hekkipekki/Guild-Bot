from __future__ import annotations

import os


def _read_local_secret(name: str) -> str | None:
    try:
        import secrets_local
    except ImportError:
        return None
    value = getattr(secrets_local, name, None)
    if value is None:
        return None
    clean = str(value).strip()
    return clean or None


def get_warcraftlogs_credentials() -> tuple[str | None, str | None]:
    """Load application credentials without storing them in guild data.

    Environment variables take precedence so hosted deployments do not need to
    place secrets in tracked files. Local development can use secrets_local.py.
    """
    client_id = (
        str(os.getenv("WARCRAFTLOGS_CLIENT_ID", "")).strip()
        or _read_local_secret("WARCRAFTLOGS_CLIENT_ID")
    )
    client_secret = (
        str(os.getenv("WARCRAFTLOGS_CLIENT_SECRET", "")).strip()
        or _read_local_secret("WARCRAFTLOGS_CLIENT_SECRET")
    )
    return client_id or None, client_secret or None
