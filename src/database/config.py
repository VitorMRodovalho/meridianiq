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
        self.ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")

    @property
    def use_supabase(self) -> bool:
        """Return True when the environment requests Supabase persistence."""
        return (
            self.ENVIRONMENT == "production"
            and bool(self.SUPABASE_URL)
            and bool(self.SUPABASE_ANON_KEY)
        )


settings = Settings()
