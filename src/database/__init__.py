# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Database layer for MeridianIQ.

Provides a unified store interface with InMemory and Supabase backends.
Use ``get_store()`` to obtain the appropriate implementation based on
the ``ENVIRONMENT`` setting.
"""
from .store import InMemoryStore, SupabaseStore, get_store

__all__ = ["InMemoryStore", "SupabaseStore", "get_store"]
