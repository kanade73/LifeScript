"""スケジューラの統合テスト。"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from lifescript.compiler.compiler import Compiler
from lifescript.scheduler.scheduler import LifeScriptScheduler
from lifescript.database.client import DatabaseClient


@pytest.fixture()
def db(tmp_path):
    import os
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
        scheduler.start()
        assert scheduler.is_running


class TestSchedulerScripts:
    def test_add_script(self, scheduler, db):
        scheduler.start()
        script = db.save_script(dsl_text="test dsl", compiled_python="x = 1")
        scheduler.add_script(script, trigger_seconds=60)
        assert str(script["id"]) in scheduler.get_active_ids()

    def test_remove_script(self, scheduler, db):
        scheduler.start()
        script = db.save_script(dsl_text="test dsl", compiled_python="x = 1")
        scheduler.add_script(script, trigger_seconds=60)
        scheduler.remove_script(str(script["id"]))
        assert str(script["id"]) not in scheduler.get_active_ids()

    def test_remove_all(self, scheduler, db):
        scheduler.start()
        for i in range(3):
            script = db.save_script(dsl_text=f"dsl_{i}", compiled_python="x = 1")
            scheduler.add_script(script, trigger_seconds=60)
        scheduler.remove_all()
        assert scheduler.get_active_ids() == []

    def test_load_from_db(self, scheduler, db):
        scheduler.start()
        for i in range(2):
            db.save_script(dsl_text=f"dsl_{i}", compiled_python="x = 1")
        scheduler.load_from_db()
        assert len(scheduler.get_active_ids()) == 2


class TestSchedulerExecution:
    @patch("lifescript.scheduler.scheduler.run_sandboxed")
    def test_run_script_success(self, mock_run, scheduler, db):
        with patch("lifescript.scheduler.scheduler.db_client", db):
            scheduler._run_script("1", "x = 1", "test dsl")
            mock_run.assert_called_once_with("x = 1", rule_id="1")

    @patch("lifescript.scheduler.scheduler.run_sandboxed")
    def test_run_script_error_logs(self, mock_run, scheduler, db):
        from lifescript.exceptions import SandboxError

        mock_run.side_effect = SandboxError("test error")
        with (
            patch("lifescript.scheduler.scheduler.db_client", db),
            patch.object(scheduler, "_try_recompile"),
        ):
            scheduler._run_script("1", "x = 1/0", "test dsl")
            logs = db.get_machine_logs()
            assert any("test error" in l.get("content", "") for l in logs)
