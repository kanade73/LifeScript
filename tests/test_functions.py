"""関数ライブラリのテスト。"""

import os
from unittest.mock import patch

import pytest

from lifescript.database.client import DatabaseClient


@pytest.fixture
def db(tmp_path):
    old_url = os.environ.pop("SUPABASE_URL", None)
    old_key = os.environ.pop("SUPABASE_ANON_KEY", None)
    db_path = tmp_path / "test.db"
    client = DatabaseClient()
    with (
        patch("lifescript.database.client._DB_DIR", tmp_path),
        patch("lifescript.database.client._DB_PATH", db_path),
    ):
        client.connect()
        # Patch the global db_client used by functions
        with patch("lifescript.functions.notify.db_client", client), \
             patch("lifescript.functions.calendar.db_client", client):
            yield client
    if old_url:
        os.environ["SUPABASE_URL"] = old_url
    if old_key:
        os.environ["SUPABASE_ANON_KEY"] = old_key


class TestNotify:
    def test_notify_immediate(self, db):
        from lifescript.functions.notify import notify
        notify("テスト通知")
        logs = db.get_machine_logs()
        assert any("テスト通知" in l["content"] for l in logs)

    def test_notify_scheduled(self, db):
        from lifescript.functions.notify import notify
        notify("予約通知", at="2025-01-01T08:00:00")
        logs = db.get_machine_logs()
        assert any("予約通知" in l["content"] for l in logs)
        assert any(l["action_type"] == "notify_scheduled" for l in logs)


class TestCalendar:
    def test_calendar_add(self, db):
        from lifescript.functions.calendar import calendar_add
        event = calendar_add("ミーティング", "2025-01-01T10:00:00+00:00")
        assert event["title"] == "ミーティング"
        assert event["source"] == "machine"

    def test_calendar_read(self, db):
        from lifescript.functions.calendar import calendar_add, calendar_read
        calendar_add("テスト", "2025-06-15T10:00:00+00:00")
        events = calendar_read()
        assert isinstance(events, list)

    def test_calendar_suggest(self, db):
        from lifescript.functions.calendar import calendar_suggest
        calendar_suggest("回復タイム", on="next_free_morning")
        logs = db.get_machine_logs()
        assert any(l["action_type"] == "calendar_suggest" for l in logs)
        assert any("回復タイム" in l["content"] for l in logs)
