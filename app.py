"""LifeScript デスクトップアプリ — flet pack 用エントリポイント。"""

import os
import sys

# パッケージ化時にlifescriptモジュールを見つけられるようにする
if getattr(sys, "frozen", False):
    base = sys._MEIPASS
else:
    base = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, base)

from dotenv import load_dotenv
load_dotenv()

from lifescript.compiler.compiler import Compiler
from lifescript.scheduler.scheduler import LifeScriptScheduler
from lifescript.api import start_api_server
import flet as ft
from lifescript.ui.app import create_app

# --- LLM compiler ---
model = os.getenv("LIFESCRIPT_MODEL", os.getenv("LITELLM_MODEL", "gemini/gemini-2.5-flash"))
api_base = os.getenv("LITELLM_API_BASE", "")
compiler = Compiler(model=model, api_base=api_base if api_base else None)

# --- Scheduler ---
scheduler = LifeScriptScheduler(compiler=compiler)

# --- REST API (iOS向け) ---
api_port = int(os.getenv("API_PORT", "8000"))
start_api_server(compiler, port=api_port)

# --- Run UI ---
ft.run(create_app(compiler=compiler, scheduler=scheduler))
