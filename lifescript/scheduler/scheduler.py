"""APScheduler-based job manager for LifeScript rules."""

from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from ..sandbox.runner import run_sandboxed
from ..compiler.compiler import Compiler
from ..database.client import db_client
from ..exceptions import SandboxError, CompileError
from .. import log_queue


class LifeScriptScheduler:
    def __init__(self, compiler: Compiler) -> None:
        self._scheduler = BackgroundScheduler(timezone="UTC")
        self._compiler = compiler
        self._job_map: dict[str, str] = {}  # rule_id → apscheduler job_id

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def start(self) -> None:
        self._scheduler.start()

    def stop(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)

    @property
    def is_running(self) -> bool:
        return self._scheduler.running

    # ------------------------------------------------------------------
    # Rule management
    # ------------------------------------------------------------------
    def load_from_db(self) -> None:
        """Load all active rules from the database and register them."""
        try:
            rules = db_client.get_rules()
            for rule in rules:
                self.add_rule(rule)
            log_queue.log("Scheduler", f"Loaded {len(rules)} rule(s) from DB")
        except Exception as e:
            log_queue.log("Scheduler", f"Failed to load rules: {e}", "ERROR")

    def add_rule(self, rule: dict) -> None:
        rule_id = str(rule["id"])
        title = rule.get("title", rule_id)
        python_code = rule["compiled_python"]
        trigger_seconds = int(rule.get("trigger_seconds", 60))
        lifescript_code = rule.get("lifescript_code", "")

        job_id = f"rule_{rule_id}"

        def job(
            rid=rule_id,
            t=title,
            code=python_code,
            ls=lifescript_code,
        ) -> None:
            self._run_rule(rid, t, code, ls)

        self._scheduler.add_job(
            job,
            trigger=IntervalTrigger(seconds=trigger_seconds),
            id=job_id,
            replace_existing=True,
            misfire_grace_time=30,
        )
        self._job_map[rule_id] = job_id
        log_queue.log("Scheduler", f"Registered '{title}' (every {trigger_seconds}s)")

    def remove_rule(self, rule_id: str) -> None:
        job_id = self._job_map.pop(str(rule_id), None)
        if job_id:
            try:
                self._scheduler.remove_job(job_id)
            except Exception:
                pass

    def remove_all(self) -> None:
        self._scheduler.remove_all_jobs()
        self._job_map.clear()
        log_queue.log("Scheduler", "All jobs stopped")

    def get_active_ids(self) -> list[str]:
        return list(self._job_map.keys())

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------
    def _run_rule(self, rule_id: str, title: str, python_code: str, lifescript_code: str) -> None:
        try:
            run_sandboxed(python_code)
            log_queue.log(title, "OK")
            db_client.save_log(rule_id, "success")
        except SandboxError as e:
            error_msg = str(e)
            log_queue.log(title, f"Error: {error_msg}", "ERROR")
            db_client.save_log(rule_id, "error", error_msg)
            self._try_recompile(rule_id, title, lifescript_code, python_code, error_msg)

    def _try_recompile(
        self,
        rule_id: str,
        title: str,
        lifescript_code: str,
        old_python: str,
        error: str,
    ) -> None:
        if not lifescript_code:
            return
        try:
            log_queue.log(title, "Attempting LLM re-compilation…", "WARN")
            result = self._compiler.recompile_with_error(lifescript_code, old_python, error)
            new_python = result["code"]
            db_client.update_rule_python(rule_id, new_python)

            # Safe access — compiler already validates trigger structure
            trigger_seconds = int(result.get("trigger", {}).get("seconds", 60))

            rule = {
                "id": rule_id,
                "title": title,
                "compiled_python": new_python,
                "lifescript_code": lifescript_code,
                "trigger_seconds": trigger_seconds,
            }
            self.add_rule(rule)
            log_queue.log(title, "Re-compiled successfully", "INFO")
        except CompileError as e:
            log_queue.log(title, f"Re-compilation failed: {e}", "ERROR")
        except Exception as e:
            log_queue.log(title, f"Re-compilation error ({type(e).__name__}): {e}", "ERROR")
