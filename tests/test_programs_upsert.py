# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Tests for ``SupabaseStore.get_or_create_program`` — now backed by the
Postgres ``upsert_program`` RPC (migration 022, ADR-0009 Wave 0 #5).

The race-prone select-then-insert pattern is gone; the method now calls
an atomic upsert. These tests verify the Python wrapper calls the RPC
with the expected args and correctly unpacks the scalar UUID response
shape across the variants PostgREST may return.
"""

from __future__ import annotations

import os
from typing import Any

import pytest

os.environ["ENVIRONMENT"] = "development"

from src.database.store import SupabaseStore  # noqa: E402


class _FakeRpcCall:
    """Mimics the supabase-py rpc(...).execute() chain."""

    def __init__(self, response_data: Any) -> None:
        self._data = response_data

    def execute(self) -> Any:
        class _Resp:
            pass

        r = _Resp()
        r.data = self._data
        return r


class _RpcRecordingClient:
    """Captures rpc() calls and returns a pre-programmed response."""

    def __init__(self, response_data: Any) -> None:
        self._response = response_data
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def rpc(self, name: str, params: dict[str, Any]) -> _FakeRpcCall:
        self.calls.append((name, params))
        return _FakeRpcCall(self._response)


def _make_store_with_client(client: _RpcRecordingClient) -> SupabaseStore:
    store = SupabaseStore.__new__(SupabaseStore)
    store._client = client  # type: ignore[assignment]
    store._analyses = {}
    store._comparisons = {}
    return store


class TestGetOrCreateProgramUpsert:
    def test_calls_upsert_program_rpc_with_expected_args(self) -> None:
        client = _RpcRecordingClient(response_data="11111111-1111-1111-1111-111111111111")
        store = _make_store_with_client(client)

        result = store.get_or_create_program(
            user_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            project_name="Project Alpha",
        )

        assert result == "11111111-1111-1111-1111-111111111111"
        assert client.calls == [
            (
                "upsert_program",
                {
                    "p_user_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                    "p_name": "Project Alpha",
                },
            )
        ]

    def test_handles_bare_uuid_scalar_response(self) -> None:
        client = _RpcRecordingClient(response_data="uuid-scalar-response")
        store = _make_store_with_client(client)
        assert store.get_or_create_program("u", "n") == "uuid-scalar-response"

    def test_handles_list_of_scalar_response(self) -> None:
        """Some PostgREST versions wrap scalar returns in a list."""
        client = _RpcRecordingClient(response_data=["uuid-in-list"])
        store = _make_store_with_client(client)
        assert store.get_or_create_program("u", "n") == "uuid-in-list"

    def test_handles_dict_with_rpc_name_key(self) -> None:
        client = _RpcRecordingClient(response_data={"upsert_program": "uuid-from-dict"})
        store = _make_store_with_client(client)
        assert store.get_or_create_program("u", "n") == "uuid-from-dict"

    def test_handles_list_of_dict_response(self) -> None:
        client = _RpcRecordingClient(response_data=[{"upsert_program": "uuid-in-list-dict"}])
        store = _make_store_with_client(client)
        assert store.get_or_create_program("u", "n") == "uuid-in-list-dict"

    def test_empty_payload_raises(self) -> None:
        client = _RpcRecordingClient(response_data=None)
        store = _make_store_with_client(client)
        with pytest.raises(RuntimeError, match="upsert_program returned empty payload"):
            store.get_or_create_program("u", "n")

    def test_empty_list_raises(self) -> None:
        client = _RpcRecordingClient(response_data=[])
        store = _make_store_with_client(client)
        with pytest.raises(RuntimeError, match="upsert_program returned empty payload"):
            store.get_or_create_program("u", "n")


class TestMigration022SchemaGuards:
    """Static guards that migration 022 declares the invariants the code
    depends on. Prevents a future "clean-up the migrations" pass from
    dropping the unique index or the RPC without updating the Python side."""

    def _read_migration(self) -> str:
        from pathlib import Path

        path = (
            Path(__file__).resolve().parent.parent
            / "supabase"
            / "migrations"
            / "022_programs_unique_upsert.sql"
        )
        return path.read_text(encoding="utf-8")

    def test_unique_index_on_lower_name_present(self) -> None:
        sql = self._read_migration()
        assert "CREATE UNIQUE INDEX" in sql
        assert "idx_programs_user_name_unique" in sql
        assert "lower(name)" in sql.lower() or "LOWER(name)" in sql

    def test_upsert_rpc_function_present(self) -> None:
        sql = self._read_migration()
        assert "CREATE OR REPLACE FUNCTION public.upsert_program" in sql
        assert "ON CONFLICT" in sql
        assert "RETURNING id" in sql

    def test_rpc_granted_to_authenticated_and_service_role(self) -> None:
        sql = self._read_migration()
        assert "GRANT EXECUTE ON FUNCTION public.upsert_program" in sql
        assert "authenticated" in sql
        assert "service_role" in sql
