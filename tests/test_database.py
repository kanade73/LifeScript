"""Tests for the database client."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from lifescript.database.client import DatabaseClient


@pytest.fixture()
def db(tmp_path):
    db_path = tmp_path / "test.db"
    client = DatabaseClient()
    with (
        patch("lifescript.database.client._DB_DIR", tmp_path),
        patch("lifescript.database.client._DB_PATH", db_path),
    ):
        client.connect()
        yield client


class TestRules:
    def test_save_and_get_rule(self, db):
        rule = db.save_rule(
            title="test",
            lifescript_code="every 1m { }",
            compiled_python="x = 1",
            trigger_seconds=60,
        )
        assert rule["title"] == "test"
        assert rule["trigger_seconds"] == 60

        rules = db.get_rules()
        assert len(rules) == 1
        assert rules[0]["id"] == rule["id"]

    def test_save_cron_rule(self, db):
        rule = db.save_rule(
            title="cron test",
            lifescript_code='cron "0 8 * * *" { }',
            compiled_python="x = 1",
            trigger_type="cron",
            cron_fields={"minute": 0, "hour": 8, "day_of_week": "mon"},
        )
        assert rule["trigger_type"] == "cron"
        assert rule["cron_minute"] == "0"
        assert rule["cron_hour"] == "8"
        assert rule["cron_day_of_week"] == "mon"

    def test_delete_rule(self, db):
        rule = db.save_rule(
            title="to delete",
            lifescript_code="every 1m { }",
            compiled_python="x = 1",
        )
        db.delete_rule(str(rule["id"]))
        rules = db.get_rules()
        assert len(rules) == 0

    def test_update_rule_status(self, db):
        rule = db.save_rule(
            title="pausable",
            lifescript_code="every 1m { }",
            compiled_python="x = 1",
        )
        db.update_rule_status(str(rule["id"]), "paused")
        # Active only
        assert len(db.get_rules(include_paused=False)) == 0
        # Include paused
        assert len(db.get_rules(include_paused=True)) == 1

    def test_get_rule_by_id(self, db):
        rule = db.save_rule(
            title="findme",
            lifescript_code="every 1m { }",
            compiled_python="x = 1",
        )
        found = db.get_rule_by_id(rule["id"])
        assert found["title"] == "findme"

    def test_get_rule_by_id_not_found(self, db):
        with pytest.raises(RuntimeError, match="見つかりません"):
            db.get_rule_by_id(99999)


class TestConnections:
    def test_save_and_get_connection(self, db):
        db.save_connection("LINE", access_token="tok", refresh_token="uid")
        conn = db.get_connection("LINE")
        assert conn is not None
        assert conn["access_token"] == "tok"

    def test_upsert_connection(self, db):
        db.save_connection("LINE", access_token="old", refresh_token="uid")
        db.save_connection("LINE", access_token="new", refresh_token="uid")
        conn = db.get_connection("LINE")
        assert conn["access_token"] == "new"

    def test_delete_connection(self, db):
        db.save_connection("LINE", access_token="tok", refresh_token="uid")
        db.delete_connection("LINE")
        assert db.get_connection("LINE") is None

    def test_get_missing_connection(self, db):
        assert db.get_connection("NONEXISTENT") is None


class TestExecutionLogs:
    def test_save_and_get_logs(self, db):
        db.save_log("1", "success")
        db.save_log("1", "error", "test error")
        logs = db.get_logs("1")
        assert len(logs) == 2

    def test_get_logs_all(self, db):
        db.save_log("1", "success")
        db.save_log("2", "success")
        logs = db.get_logs()
        assert len(logs) == 2

    def test_get_last_execution(self, db):
        db.save_log("1", "success")
        db.save_log("1", "error", "boom")
        last = db.get_last_execution("1")
        assert last is not None
        assert last["status"] == "error"

    def test_get_last_execution_none(self, db):
        assert db.get_last_execution("999") is None

    def test_log_limit(self, db):
        for i in range(10):
            db.save_log("1", "success", f"run {i}")
        logs = db.get_logs("1", limit=5)
        assert len(logs) == 5
