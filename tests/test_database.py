"""データベースクライアントのテスト。"""

import os
import pytest

from lifescript.database.client import DatabaseClient


@pytest.fixture
def db(tmp_path):
    from unittest.mock import patch
    old_url = os.environ.pop("SUPABASE_URL", None)
    old_key = os.environ.pop("SUPABASE_ANON_KEY", None)
    db_path = tmp_path / "test.db"
    client = DatabaseClient()
    with (
        patch("lifescript.database.client._DB_DIR", tmp_path),
        patch("lifescript.database.client._DB_PATH", db_path),
    ):
        client.connect()
        yield client
    if old_url:
        os.environ["SUPABASE_URL"] = old_url
    if old_key:
        os.environ["SUPABASE_ANON_KEY"] = old_key


class TestDatabaseClient:
    def test_connect(self, db):
        assert db.is_connected
        assert not db.is_supabase

    def test_script_crud(self, db):
        script = db.save_script(dsl_text="test dsl", compiled_python="x = 1")
        assert script["dsl_text"] == "test dsl"

        scripts = db.get_scripts()
        assert any(s["id"] == script["id"] for s in scripts)

        fetched = db.get_script_by_id(script["id"])
        assert fetched["compiled_python"] == "x = 1"

        db.update_script(script["id"], compiled_python="x = 2")
        fetched2 = db.get_script_by_id(script["id"])
        assert fetched2["compiled_python"] == "x = 2"

        db.delete_script(script["id"])
        scripts2 = db.get_scripts()
        assert not any(s["id"] == script["id"] for s in scripts2)

    def test_script_trigger_persistence(self, db):
        trigger = {"type": "after", "seconds": 10}
        script = db.save_script(dsl_text="test dsl", compiled_python='notify("x")', trigger=trigger)
        fetched = db.get_script_by_id(script["id"])
        assert fetched["trigger_json"]
        assert '"type": "after"' in fetched["trigger_json"]

        updated = {"type": "cron", "hour": 8, "minute": 30}
        import json

        db.update_script(script["id"], trigger_json=json.dumps(updated, ensure_ascii=False))
        fetched2 = db.get_script_by_id(script["id"])
        assert fetched2["trigger_json"] == json.dumps(updated, ensure_ascii=False)

    def test_event_crud(self, db):
        event = db.add_event(title="Meeting", start_at="2025-01-01T10:00:00+00:00")
        assert event["title"] == "Meeting"

        events = db.get_events()
        assert any(e["id"] == event["id"] for e in events)

        events_filtered = db.get_events(keyword="Meet")
        assert len(events_filtered) >= 1

        db.delete_event(event["id"])

    def test_machine_log(self, db):
        log_entry = db.add_machine_log(action_type="notify", content="test message")
        assert log_entry["action_type"] == "notify"

        logs = db.get_machine_logs()
        assert any(entry["id"] == log_entry["id"] for entry in logs)

    def test_streak(self, db):
        count = db.get_streak("exercise")
        assert count == 0

        db.update_streak("exercise", 5)
        assert db.get_streak("exercise") == 5

        db.update_streak("exercise", 10)
        assert db.get_streak("exercise") == 10
