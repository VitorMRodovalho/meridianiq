# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Supabase client singleton.

Lazily initialises a single ``supabase.Client`` so the connection is
shared across the application lifetime.
"""
from __future__ import annotations

from typing import Any

_client: Any | None = None


def get_supabase_client() -> Any:
    """Return the Supabase client singleton.

    Raises:
        RuntimeError: If supabase-py is not installed or credentials are
            missing.
    """
    global _client
    if _client is not None:
        return _client

    try:
        from supabase import create_client
    except ImportError as exc:
        raise RuntimeError(
            "supabase-py is required for production mode. "
            "Install it with: pip install supabase"
        ) from exc

    from .config import settings

    # Use service_role_key for backend operations (bypasses RLS)
    key = settings.SUPABASE_SERVICE_ROLE_KEY or settings.SUPABASE_ANON_KEY
    if not settings.SUPABASE_URL or not key:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY (or SUPABASE_ANON_KEY) "
            "must be set in the environment or in a .env file."
        )

    _client = create_client(settings.SUPABASE_URL, key)
    return _client
