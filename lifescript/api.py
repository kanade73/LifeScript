"""REST API — iOS から叩くエンドポイント。

POST /compile で DSL テキストを受け取り、コンパイル結果を返す。
"""

from __future__ import annotations

import threading
import os

from dotenv import load_dotenv


def start_api_server(compiler, port: int = 8000) -> threading.Thread:
    """API サーバーをバックグラウンドスレッドで起動する。"""
    from http.server import HTTPServer, BaseHTTPRequestHandler
    import json

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            if self.path == "/compile":
                content_length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_length).decode("utf-8")
                try:
                    data = json.loads(body)
                    dsl_text = data.get("dsl_text", "")
                    if not dsl_text:
                        self._send_json(400, {"error": "dsl_text is required"})
                        return

                    result = compiler.compile(dsl_text)
                    self._send_json(200, {
                        "compiled_python": result["code"],
                        "title": result.get("title", ""),
                        "trigger": result.get("trigger", {}),
                    })
                except Exception as e:
                    self._send_json(500, {"error": str(e)})
            else:
                self._send_json(404, {"error": "Not found"})

        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/health":
                self._send_json(200, {"status": "ok"})
            else:
                self._send_json(404, {"error": "Not found"})

        def _send_json(self, status: int, data: dict) -> None:
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

        def log_message(self, format: str, *args: object) -> None:
            pass  # Suppress default logging

    for p in (port, port + 1, port + 2):
        try:
            server = HTTPServer(("0.0.0.0", p), Handler)
            break
        except OSError:
            if p == port + 2:
                print(f"[API] ポート {port}-{port+2} が全て使用中です。APIサーバーを起動できません。")
                return None
            continue

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"[API] http://localhost:{p} で起動しました")

    return thread
