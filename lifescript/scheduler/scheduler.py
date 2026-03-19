"""APScheduler ベースのジョブ管理 — コンパイル済み Python をスケジュール実行する。

実行時は LLM を使用しない。エラー時のみ LLM で再コンパイルを試みる。
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from ..sandbox.runner import run_sandboxed, reset_rate_limits
from ..compiler.compiler import Compiler
from ..context_analyzer import ContextAnalyzer
from ..database.client import db_client
from ..exceptions import SandboxError, CompileError
from .. import log_queue


class LifeScriptScheduler:
    def __init__(self, compiler: Compiler) -> None:
        self._scheduler = BackgroundScheduler(timezone="UTC")
        self._compiler = compiler
        self._analyzer = ContextAnalyzer(model=compiler.model)
        self._job_map: dict[str, str] = {}  # script_id → apscheduler job_id
        self._trigger_map: dict[str, dict] = {}  # script_id → trigger dict
        self._paused: set[str] = set()  # paused script IDs

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def start(self) -> None:
        if not self._scheduler.running:
            self._scheduler.start()
            self._scheduler.add_job(
                reset_rate_limits,
                trigger=IntervalTrigger(seconds=60),
                id="_rate_limit_reset",
                replace_existing=True,
            )
            # コンテキスト分析ジョブ（3時間ごと + 起動30秒後に初回実行）
            self._scheduler.add_job(
                self._run_analysis,
                trigger=IntervalTrigger(hours=3),
                id="_context_analyzer",
                replace_existing=True,
            )
            from datetime import datetime, timedelta
            self._scheduler.add_job(
                self._run_analysis,
                trigger="date",
                run_date=datetime.now() + timedelta(seconds=30),
                id="_context_analyzer_initial",
            )

    def stop(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)

    @property
    def is_running(self) -> bool:
        return self._scheduler.running

    # ------------------------------------------------------------------
    # Script management
    # ------------------------------------------------------------------
    def load_from_db(self) -> None:
        """DB から全アクティブスクリプトを読み込み、スケジューラに登録する。"""
        try:
            scripts = db_client.get_scripts()
            for script in scripts:
                if script.get("compiled_python"):
                    self.add_script(script, trigger=self._load_trigger(script))
            log_queue.log("Scheduler", f"DBから{len(scripts)}件のスクリプトを読み込みました")
        except Exception as e:
            log_queue.log("Scheduler", f"スクリプトの読み込みに失敗しました: {e}", "ERROR")

    def add_script(self, script: dict, trigger_seconds: int = 3600, trigger: dict | None = None) -> None:
        """スクリプトをスケジューラに登録する。"""
        script_id = str(script["id"])
        python_code = script["compiled_python"]
        dsl_text = script.get("dsl_text", "")

        job_id = f"script_{script_id}"

        def job(sid=script_id, code=python_code, dsl=dsl_text) -> None:
            self._run_script(sid, code, dsl)

        if trigger and trigger.get("type") == "cron":
            ap_trigger = CronTrigger(hour=trigger["hour"], minute=trigger["minute"])
            desc = f"毎日 {trigger['hour']:02d}:{trigger['minute']:02d}"
        elif trigger and trigger.get("type") == "after":
            seconds = trigger["seconds"]
            run_at = datetime.now(timezone.utc) + timedelta(seconds=seconds)

            def one_shot_job(sid=script_id, code=python_code, dsl=dsl_text) -> None:
                try:
                    self._run_script(sid, code, dsl)
                finally:
                    self._job_map.pop(sid, None)

            job = one_shot_job
            ap_trigger = DateTrigger(run_date=run_at)
            desc = f"{seconds}秒後に1回"
        else:
            seconds = trigger["seconds"] if trigger and "seconds" in trigger else trigger_seconds
            ap_trigger = IntervalTrigger(seconds=seconds)
            desc = self._describe_interval(seconds)

        self._scheduler.add_job(
            job,
            trigger=ap_trigger,
            id=job_id,
            replace_existing=True,
            misfire_grace_time=30,
        )
        self._job_map[script_id] = job_id
        # Store trigger info for later retrieval
        if trigger:
            self._trigger_map[script_id] = trigger
        else:
            self._trigger_map[script_id] = {"type": "interval", "seconds": trigger_seconds}
        self._paused.discard(script_id)

        log_queue.log("Scheduler", f"スクリプト#{script_id} を登録 ({desc})")

    @staticmethod
    def _describe_interval(seconds: int) -> str:
        if seconds >= 86400:
            return f"{seconds // 86400}日ごと"
        if seconds >= 3600:
            return f"{seconds // 3600}時間ごと"
        if seconds >= 60:
            return f"{seconds // 60}分ごと"
        return f"{seconds}秒ごと"

    def remove_script(self, script_id: str) -> None:
        script_id = str(script_id)
        job_id = self._job_map.pop(script_id, None)
        if job_id:
            try:
                self._scheduler.remove_job(job_id)
            except Exception:
                pass
        self._trigger_map.pop(script_id, None)
        self._paused.discard(script_id)

    def remove_all(self) -> None:
        self._scheduler.remove_all_jobs()
        self._job_map.clear()
        self._trigger_map.clear()
        self._paused.clear()
        log_queue.log("Scheduler", "全ジョブを停止しました")
        if self._scheduler.running:
            self._scheduler.add_job(
                reset_rate_limits,
                trigger=IntervalTrigger(seconds=60),
                id="_rate_limit_reset",
                replace_existing=True,
            )

    def get_active_ids(self) -> list[str]:
        return list(self._job_map.keys())

    def get_trigger_info(self, script_id: str) -> dict:
        """スクリプトのトリガー情報を返す。"""
        return self._trigger_map.get(str(script_id), {"type": "interval", "seconds": 3600})

    @staticmethod
    def _load_trigger(script: dict) -> dict | None:
        raw = script.get("trigger_json")
        if not raw:
            return None
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, str):
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                return None
            return parsed if isinstance(parsed, dict) else None
        return None

    def is_paused(self, script_id: str) -> bool:
        return str(script_id) in self._paused

    def pause_script(self, script_id: str) -> None:
        """スクリプトを一時停止（スケジューラから外すがトリガー情報は保持）。"""
        script_id = str(script_id)
        job_id = self._job_map.pop(script_id, None)
        if job_id:
            try:
                self._scheduler.remove_job(job_id)
            except Exception:
                pass
        self._paused.add(script_id)
        log_queue.log("Scheduler", f"スクリプト#{script_id} を一時停止しました")

    def resume_script(self, script_id: str, script: dict) -> None:
        """一時停止中のスクリプトを再開する。"""
        script_id = str(script_id)
        trigger = self._trigger_map.get(script_id, {"type": "interval", "seconds": 3600})
        self.add_script(script, trigger=trigger)
        self._paused.discard(script_id)
        log_queue.log("Scheduler", f"スクリプト#{script_id} を再開しました")

    def update_trigger(self, script_id: str, script: dict, trigger: dict) -> None:
        """スクリプトのトリガーを更新する。"""
        script_id = str(script_id)
        self._trigger_map[script_id] = trigger
        try:
            db_client.update_script(int(script_id), trigger_json=json.dumps(trigger, ensure_ascii=False))
        except Exception as e:
            log_queue.log("Scheduler", f"トリガー保存に失敗しました: {e}", "WARN")
        if script_id not in self._paused:
            self.add_script(script, trigger=trigger)

    def describe_trigger(self, trigger: dict) -> str:
        """トリガーの説明文を返す。"""
        if trigger.get("type") == "cron":
            return f"毎日 {trigger.get('hour', 0):02d}:{trigger.get('minute', 0):02d}"
        if trigger.get("type") == "after":
            return f"{trigger.get('seconds', 0)}秒後に1回"
        seconds = trigger.get("seconds", 3600)
        return self._describe_interval(seconds)

    # ------------------------------------------------------------------
    # Context Analysis
    # ------------------------------------------------------------------
    def _run_analysis(self) -> None:
        """コンテキスト分析を実行して提案を生成する。"""
        try:
            self._analyzer.analyze()
        except Exception as e:
            log_queue.log("Analyzer", f"分析ジョブエラー: {e}", "ERROR")

    def run_analysis_now(self) -> list[dict]:
        """手動で即時分析を実行する（UIから呼ぶ用）。"""
        try:
            return self._analyzer.analyze()
        except Exception as e:
            log_queue.log("Analyzer", f"分析エラー: {e}", "ERROR")
            return []

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------
    def _run_script(self, script_id: str, python_code: str, dsl_text: str) -> None:
        try:
            run_sandboxed(python_code, rule_id=script_id)
            log_queue.log(f"Script#{script_id}", "OK")
        except SandboxError as e:
            error_msg = str(e)
            log_queue.log(f"Script#{script_id}", f"エラー: {error_msg}", "ERROR")
            db_client.add_machine_log(
                action_type="script_error",
                content=f"Script#{script_id}: {error_msg}",
            )
            self._try_recompile(script_id, dsl_text, python_code, error_msg)

    def _try_recompile(
        self, script_id: str, dsl_text: str, old_python: str, error: str
    ) -> None:
        if not dsl_text:
            return
        try:
            log_queue.log(f"Script#{script_id}", "LLMによる再コンパイルを試行中…", "WARN")
            result = self._compiler.recompile_with_error(dsl_text, old_python, error)
            new_python = result["code"]
            trigger_dict = result.get("trigger", {"type": "interval", "seconds": 3600})
            db_client.update_script(
                int(script_id),
                compiled_python=new_python,
                trigger_json=json.dumps(trigger_dict, ensure_ascii=False),
            )
            script = {"id": script_id, "compiled_python": new_python, "dsl_text": dsl_text}
            self.add_script(script, trigger=trigger_dict)
            log_queue.log(f"Script#{script_id}", "再コンパイルに成功しました")
        except CompileError as e:
            log_queue.log(f"Script#{script_id}", f"再コンパイルに失敗: {e}", "ERROR")
        except Exception as e:
            log_queue.log(f"Script#{script_id}", f"再コンパイルエラー: {e}", "ERROR")
