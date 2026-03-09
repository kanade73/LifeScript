"""Integration tests for the LifeScript scheduler."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from lifescript.compiler.compiler import Compiler
from lifescript.scheduler.scheduler import LifeScriptScheduler
from lifescript.database.client import DatabaseClient


@pytest.fixture()
def db(tmp_path):
    """Create a temporary database for testing."""
    db_path = tmp_path / "test.db"
    client = DatabaseClient()
    # Monkeypatch the module-level constants
    with (
        patch("lifescript.database.client._DB_DIR", tmp_path),
        patch("lifescript.database.client._DB_PATH", db_path),
    ):
        client.connect()
        yield client


@pytest.fixture()
def compiler():
    return Compiler(model="test-model")


@pytest.fixture()
def scheduler(compiler, db):
    with patch("lifescript.scheduler.scheduler.db_client", db):
        sched = LifeScriptScheduler(compiler=compiler)
        yield sched
        if sched.is_running:
            sched.stop()


class TestSchedulerLifecycle:
    def test_start_stop(self, scheduler):
        assert not scheduler.is_running
        scheduler.start()
        assert scheduler.is_running
        scheduler.stop()
        assert not scheduler.is_running

    def test_double_start_safe(self, scheduler):
        scheduler.start()
        scheduler.start()  # Should not raise
        assert scheduler.is_running


class TestSchedulerRules:
    def test_add_rule(self, scheduler, db):
        scheduler.start()
        rule = db.save_rule(
            title="test",
            lifescript_code="every 1m { }",
            compiled_python="x = 1",
            trigger_seconds=60,
        )
        scheduler.add_rule(rule)
        assert str(rule["id"]) in scheduler.get_active_ids()

    def test_remove_rule(self, scheduler, db):
        scheduler.start()
        rule = db.save_rule(
            title="test",
            lifescript_code="every 1m { }",
            compiled_python="x = 1",
            trigger_seconds=60,
        )
        scheduler.add_rule(rule)
        scheduler.remove_rule(str(rule["id"]))
        assert str(rule["id"]) not in scheduler.get_active_ids()

    def test_remove_all(self, scheduler, db):
        scheduler.start()
        for i in range(3):
            rule = db.save_rule(
                title=f"test_{i}",
                lifescript_code="every 1m { }",
                compiled_python="x = 1",
                trigger_seconds=60,
            )
            scheduler.add_rule(rule)
        scheduler.remove_all()
        assert scheduler.get_active_ids() == []

    def test_load_from_db(self, scheduler, db):
        scheduler.start()
        for i in range(2):
            db.save_rule(
                title=f"rule_{i}",
                lifescript_code="every 1m { }",
                compiled_python="x = 1",
                trigger_seconds=60,
            )
        scheduler.load_from_db()
        assert len(scheduler.get_active_ids()) == 2

    def test_cron_trigger_rule(self, scheduler, db):
        scheduler.start()
        rule = db.save_rule(
            title="cron_test",
            lifescript_code='cron "0 8 * * *" { }',
            compiled_python="x = 1",
            trigger_seconds=60,
            trigger_type="cron",
            cron_fields={"minute": 0, "hour": 8},
        )
        scheduler.add_rule(rule)
        assert str(rule["id"]) in scheduler.get_active_ids()


class TestSchedulerPauseResume:
    def test_pause_rule(self, scheduler, db):
        scheduler.start()
        with patch("lifescript.scheduler.scheduler.db_client", db):
            rule = db.save_rule(
                title="pausable",
                lifescript_code="every 1m { }",
                compiled_python="x = 1",
                trigger_seconds=60,
            )
            scheduler.add_rule(rule)
            scheduler.pause_rule(str(rule["id"]))
            assert str(rule["id"]) not in scheduler.get_active_ids()
            # Check DB status
            updated = db.get_rule_by_id(rule["id"])
            assert updated["status"] == "paused"

    def test_resume_rule(self, scheduler, db):
        scheduler.start()
        with patch("lifescript.scheduler.scheduler.db_client", db):
            rule = db.save_rule(
                title="resumable",
                lifescript_code="every 1m { }",
                compiled_python="x = 1",
                trigger_seconds=60,
            )
            scheduler.add_rule(rule)
            scheduler.pause_rule(str(rule["id"]))
            scheduler.resume_rule(str(rule["id"]))
            assert str(rule["id"]) in scheduler.get_active_ids()


class TestSchedulerExecution:
    @patch("lifescript.scheduler.scheduler.run_sandboxed")
    def test_run_rule_success(self, mock_run, scheduler, db):
        with patch("lifescript.scheduler.scheduler.db_client", db):
            scheduler._run_rule("1", "test_rule", "x = 1", "every 1m { }")
            mock_run.assert_called_once_with("x = 1", rule_id="1")

    @patch("lifescript.scheduler.scheduler.run_sandboxed")
    def test_run_rule_error_logs(self, mock_run, scheduler, db):
        from lifescript.exceptions import SandboxError

        mock_run.side_effect = SandboxError("test error")
        with (
            patch("lifescript.scheduler.scheduler.db_client", db),
            patch.object(scheduler, "_try_recompile"),
        ):
            scheduler._run_rule("1", "test_rule", "x = 1/0", "every 1m { }")
            logs = db.get_logs("1")
            assert len(logs) == 1
            assert logs[0]["status"] == "error"
