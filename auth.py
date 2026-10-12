"""Fail-closed verification of Supabase access tokens for the API."""

import json
import os
import re
from functools import lru_cache
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fastapi import Header, HTTPException


@lru_cache(maxsize=1)
def _supabase_settings():
    """Read server overrides, falling back to the public browser config."""
    url = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
    key = os.environ.get("SUPABASE_ANON_KEY", "").strip()

    if not url or not key:
        config_path = Path(__file__).parent / "frontend" / "supabase-config.js"
        try:
            config = config_path.read_text(encoding="utf-8")
        except OSError:
            config = ""
        if not url:
            match = re.search(r'const\s+SUPABASE_URL\s*=\s*["\']([^"\']+)', config)
            url = match.group(1).rstrip("/") if match else ""
        if not key:
            match = re.search(r'const\s+SUPABASE_ANON_KEY\s*=\s*["\']([^"\']+)', config)
            key = match.group(1) if match else ""

    if not url.startswith("https://") or not key:
        raise HTTPException(
            status_code=503,
            detail="Authentication is not configured on the API.",
        )
    return url, key


def get_current_user(authorization: str | None = Header(default=None)) -> dict:
    """Validate the bearer token with Supabase Auth and return its user record."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Sign in to continue.")

    token = authorization[7:].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Sign in to continue.")

    url, key = _supabase_settings()
    request = Request(
        f"{url}/auth/v1/user",
        headers={
            "apikey": key,
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=6) as response:
            user = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        if error.code in (401, 403):
            raise HTTPException(status_code=401, detail="Your session is invalid or expired.") from error
        raise HTTPException(status_code=503, detail="Could not verify your session.") from error
    except (URLError, TimeoutError, OSError, ValueError) as error:
        raise HTTPException(status_code=503, detail="Could not verify your session.") from error

    if not isinstance(user, dict) or not user.get("id"):
        raise HTTPException(status_code=401, detail="Your session is invalid or expired.")
    return user
