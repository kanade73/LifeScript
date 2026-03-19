"""qr.*() --- QRコード関数。

qr_generate(data, size?) でQRコードのURLを生成する。
"""

from __future__ import annotations

import json
from urllib.parse import quote

from ..database.client import db_client
from .. import log_queue

_QR_API_BASE = "https://api.qrserver.com/v1/create-qr-code/"


def qr_generate(data: str, size: int = 200) -> str:
    """QRコードのURLを生成する。

    Args:
        data: QRコードに埋め込むデータ（URL、テキストなど）
        size: QRコード画像のサイズ（ピクセル、デフォルト: 200）

    Returns:
        QRコード画像のURL
    """
    encoded_data = quote(data, safe="")
    url = f"{_QR_API_BASE}?size={size}x{size}&data={encoded_data}"

    # machine_logsにQR情報を記録
    meta = json.dumps({"type": "qr_code", "data": data, "url": url}, ensure_ascii=False)
    content = f"QRコード生成: {data[:80]}\n<!--meta:{meta}-->"

    try:
        db_client.add_machine_log(
            action_type="qr_generate",
            content=content,
        )
    except Exception as e:
        log_queue.log("qr", f"machine_log書き込みエラー: {e}", "ERROR")

    log_queue.log("qr", f"QRコード生成: {data[:60]} ({size}x{size})")
    return url
