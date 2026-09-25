# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Configuration for the database layer.

Loads settings from environment variables (with optional ``.env`` file
support via *python-dotenv*).
"""

from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    # Walk up from this file to find .env at project root
    _project_root = Path(__file__).resolve().parent.parent.parent
    load_dotenv(_project_root / ".env")
except ImportError:
    pass  # python-dotenv not installed — rely on real env vars


class Settings:
    """Application settings drawn from the environment."""

    def __init__(self) -> None:
        self.SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
        self.SUPABASE_ANON_KEY: str = os.getenv("SUPABASE_ANON_KEY", "")
        self.SUPABASE_SERVICE_ROLE_KEY: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
        self.SUPABASE_JWT_SECRET: str = os.getenv("SUPABASE_JWT_SECRET", "")
        self.ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")

    @property
    def allow_remote_supabase(self) -> bool:
        """Return True when this process may open a client to the configured Supabase."""
        return remote_supabase_allowed()

    @property
    def use_supabase(self) -> bool:
        """Return True when the environment requests Supabase persistence."""
        return (
            self.ENVIRONMENT == "production"
            and self.allow_remote_supabase
            and bool(self.SUPABASE_URL)
            and bool(self.SUPABASE_ANON_KEY)
        )


def remote_supabase_allowed() -> bool:
    """Return True only when remote Supabase access was explicitly opted into.

    ``.env`` is loaded at import time and usually holds the production
    project's URL and service-role key, so the presence of credentials is
    not evidence that a process should use them: a local script, test or
    MCP session would otherwise read and write production data. The
    deployed app opts in through ``ALLOW_REMOTE_SUPABASE=1`` in
    ``fly.toml``; anything else must set it explicitly.

    Read at call time (not cached) so tests and long-lived processes see
    the current environment.
    """
    return os.getenv("ALLOW_REMOTE_SUPABASE", "") == "1"


settings = Settings()
