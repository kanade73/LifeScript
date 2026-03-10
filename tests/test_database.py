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
        # get_rules only returns active
        assert len(db.get_rules()) == 0

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

    def test_update_rule_python(self, db):
        rule = db.save_rule(
            title="update test",
            lifescript_code="every 1m { }",
            compiled_python="x = 1",
        )
        db.update_rule_python(str(rule["id"]), "x = 2")
        updated = db.get_rule_by_id(rule["id"])
        assert updated["compiled_python"] == "x = 2"


class TestLogs:
    def test_save_and_get_logs(self, db):
        db.save_log(rule_id="1", message="hello", result="success")
        db.save_log(rule_id="1", message="fail", result="error", error_message="boom")
        logs = db.get_logs("1")
        assert len(logs) == 2

    def test_get_logs_all(self, db):
        db.save_log(rule_id="1", message="a", result="success")
        db.save_log(rule_id="2", message="b", result="success")
        logs = db.get_logs()
        assert len(logs) == 2

    def test_log_limit(self, db):
        for i in range(10):
            db.save_log(rule_id="1", message=f"run {i}", result="success")
        logs = db.get_logs("1", limit=5)
        assert len(logs) == 5
