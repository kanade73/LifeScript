"""APScheduler-based job manager for LifeScript rules."""

from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from ..sandbox.runner import run_sandboxed, reset_rate_limits
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
        if not self._scheduler.running:
            self._scheduler.start()
            # Reset rate limits every 60 seconds
            self._scheduler.add_job(
                reset_rate_limits,
                trigger=IntervalTrigger(seconds=60),
                id="_rate_limit_reset",
                replace_existing=True,
            )

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
            log_queue.log("Scheduler", f"DBから{len(rules)}件のルールを読み込みました")
        except Exception as e:
            log_queue.log("Scheduler", f"ルールの読み込みに失敗しました: {e}", "ERROR")

    def add_rule(self, rule: dict) -> None:
        rule_id = str(rule["id"])
        title = rule.get("title", rule_id)
        python_code = rule["compiled_python"]
        lifescript_code = rule.get("lifescript_code", "")

        job_id = f"rule_{rule_id}"

        # Build trigger from rule data
        trigger = self._build_trigger(rule)
        trigger_desc = self._describe_trigger(rule)

        def job(
            rid=rule_id,
            t=title,
            code=python_code,
            ls=lifescript_code,
        ) -> None:
            self._run_rule(rid, t, code, ls)

        self._scheduler.add_job(
            job,
            trigger=trigger,
            id=job_id,
            replace_existing=True,
            misfire_grace_time=30,
        )
        self._job_map[rule_id] = job_id
        log_queue.log("Scheduler", f"'{title}' を登録しました ({trigger_desc})")

    def _build_trigger(self, rule: dict) -> IntervalTrigger | CronTrigger:
        """Build an APScheduler trigger from a rule dict."""
        trigger_type = rule.get("trigger_type", "interval")

        if trigger_type == "cron":
            cron_kwargs: dict = {}
            for key in ("minute", "hour", "day_of_week", "day", "month"):
                val = rule.get(f"cron_{key}")
                if val is not None and val != "":
                    cron_kwargs[key] = val
            # Defaults
            cron_kwargs.setdefault("minute", 0)
            cron_kwargs.setdefault("hour", 0)
            return CronTrigger(**cron_kwargs)

        # Default: interval trigger
        trigger_seconds = int(rule.get("trigger_seconds", 60))
        return IntervalTrigger(seconds=trigger_seconds)

    @staticmethod
    def _describe_trigger(rule: dict) -> str:
        trigger_type = rule.get("trigger_type", "interval")
        if trigger_type == "cron":
            parts = []
            for key in ("minute", "hour", "day_of_week", "day", "month"):
                val = rule.get(f"cron_{key}")
                if val is not None and val != "":
                    parts.append(f"{key}={val}")
            return "cron: " + ", ".join(parts) if parts else "cron"

        secs = int(rule.get("trigger_seconds", 60))
        if secs >= 86400:
            return f"{secs // 86400}日ごと"
        if secs >= 3600:
            return f"{secs // 3600}時間ごと"
        if secs >= 60:
            return f"{secs // 60}分ごと"
        return f"{secs}秒ごと"

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
        log_queue.log("Scheduler", "全ジョブを停止しました")
        # Re-add rate limit reset if scheduler is running
        if self._scheduler.running:
            self._scheduler.add_job(
                reset_rate_limits,
                trigger=IntervalTrigger(seconds=60),
                id="_rate_limit_reset",
                replace_existing=True,
            )

    def get_active_ids(self) -> list[str]:
        return list(self._job_map.keys())

    # ------------------------------------------------------------------
    # Rule enable/disable
    # ------------------------------------------------------------------
    def pause_rule(self, rule_id: str) -> None:
        """Pause a rule (remove from scheduler, set DB status to 'paused')."""
        self.remove_rule(rule_id)
        db_client.update_rule_status(str(rule_id), "paused")
        log_queue.log("Scheduler", f"ルール {rule_id} を一時停止しました")

    def resume_rule(self, rule_id: str) -> None:
        """Resume a paused rule."""
        db_client.update_rule_status(str(rule_id), "active")
        rule = db_client.get_rule_by_id(int(rule_id))
        if rule:
            self.add_rule(rule)
            log_queue.log("Scheduler", f"ルール {rule_id} を再開しました")

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------
    def _run_rule(self, rule_id: str, title: str, python_code: str, lifescript_code: str) -> None:
        try:
            run_sandboxed(python_code, rule_id=rule_id)
            log_queue.log(title, "OK")
            db_client.save_log(rule_id, "success")
        except SandboxError as e:
            error_msg = str(e)
            log_queue.log(title, f"エラー: {error_msg}", "ERROR")
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
            log_queue.log(title, "LLMによる再コンパイルを試行中…", "WARN")
            result = self._compiler.recompile_with_error(lifescript_code, old_python, error)
            new_python = result["code"]
            db_client.update_rule_python(rule_id, new_python)

            trigger_seconds = int(result.get("trigger", {}).get("seconds", 60))

            rule = {
                "id": rule_id,
                "title": title,
                "compiled_python": new_python,
                "lifescript_code": lifescript_code,
                "trigger_seconds": trigger_seconds,
            }
            self.add_rule(rule)
            log_queue.log(title, "再コンパイルに成功しました")
        except CompileError as e:
            log_queue.log(title, f"再コンパイルに失敗しました: {e}", "ERROR")
        except Exception as e:
            log_queue.log(title, f"再コンパイルエラー ({type(e).__name__}): {e}", "ERROR")
