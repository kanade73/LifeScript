"""Database client with Supabase backend and in-memory fallback."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from supabase import Client


class DatabaseClient:
    def __init__(self) -> None:
        self._client: Client | None = None
        # In-memory fallback (used when Supabase is not configured)
        self._rules: list[dict] = []
        self._logs: list[dict] = []
        self._connections: list[dict] = []
        self._id_counter = 1

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------
    def connect(self, url: str, key: str) -> None:
        from supabase import create_client
        self._client = create_client(url, key)

    @property
    def is_connected(self) -> bool:
        return self._client is not None

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _new_id(self) -> str:
        id_ = str(self._id_counter)
        self._id_counter += 1
        return id_

    # ------------------------------------------------------------------
    # Rules
    # ------------------------------------------------------------------
    def save_rule(
        self,
        title: str,
        lifescript_code: str,
        compiled_python: str,
        trigger_seconds: int = 60,
    ) -> dict:
        if self._client:
            result = self._client.table("rules").insert({
                "title": title,
                "lifescript_code": lifescript_code,
                "compiled_python": compiled_python,
                "trigger_seconds": trigger_seconds,
                "status": "active",
            }).execute()
            if not result.data:
                raise RuntimeError("Supabase insert returned no data")
            return result.data[0]

        rule = {
            "id": self._new_id(),
            "title": title,
            "lifescript_code": lifescript_code,
            "compiled_python": compiled_python,
            "trigger_seconds": trigger_seconds,
            "status": "active",
            "created_at": self._now(),
        }
        self._rules.append(rule)
        return rule

    def get_rules(self) -> list[dict]:
        if self._client:
            result = self._client.table("rules").select("*").eq("status", "active").execute()
            return result.data
        return [r for r in self._rules if r["status"] == "active"]

    def update_rule_python(self, rule_id: str, compiled_python: str) -> None:
        if self._client:
            self._client.table("rules").update(
                {"compiled_python": compiled_python}
            ).eq("id", rule_id).execute()
            return
        for r in self._rules:
            if str(r["id"]) == str(rule_id):
                r["compiled_python"] = compiled_python
                break

    def delete_rule(self, rule_id: str) -> None:
        if self._client:
            self._client.table("rules").update(
                {"status": "deleted"}
            ).eq("id", rule_id).execute()
            return
        for r in self._rules:
            if str(r["id"]) == str(rule_id):
                r["status"] = "deleted"
                break

    # ------------------------------------------------------------------
    # Logs
    # ------------------------------------------------------------------
    def save_log(
        self, rule_id: str, result: str, error_message: str | None = None
    ) -> None:
        if self._client:
            self._client.table("logs").insert({
                "rule_id": rule_id,
                "result": result,
                "error_message": error_message,
            }).execute()
            return
        self._logs.append({
            "id": str(uuid.uuid4()),
            "rule_id": rule_id,
            "executed_at": self._now(),
            "result": result,
            "error_message": error_message,
        })

    # ------------------------------------------------------------------
    # Connections
    # ------------------------------------------------------------------
    def get_connection(self, service_name: str) -> dict | None:
        if self._client:
            result = (
                self._client.table("connections")
                .select("*")
                .eq("service_name", service_name)
                .execute()
            )
            return result.data[0] if result.data else None
        for c in self._connections:
            if c["service_name"] == service_name:
                return c
        return None

    def save_connection(
        self, service_name: str, access_token: str, refresh_token: str = ""
    ) -> None:
        if self._client:
            existing = self.get_connection(service_name)
            if existing:
                self._client.table("connections").update({
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                }).eq("service_name", service_name).execute()
            else:
                self._client.table("connections").insert({
                    "service_name": service_name,
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                }).execute()
            return
        for c in self._connections:
            if c["service_name"] == service_name:
                c["access_token"] = access_token
                c["refresh_token"] = refresh_token
                return
        self._connections.append({
            "id": str(uuid.uuid4()),
            "service_name": service_name,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "connected_at": self._now(),
        })

    def delete_connection(self, service_name: str) -> None:
        if self._client:
            self._client.table("connections").delete().eq(
                "service_name", service_name
            ).execute()
            return
        self._connections = [
            c for c in self._connections if c["service_name"] != service_name
        ]


# Application-wide singleton
db_client = DatabaseClient()
