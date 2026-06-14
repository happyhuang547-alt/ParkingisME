#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LINE Bot Webhook Server — parking_bot 手機控制介面
===================================================
讓使用者透過 LINE 訊息觸發、查詢、停止停車搶位機器人。

必要環境變數：
    LINE_CHANNEL_SECRET        LINE Channel Secret
    LINE_CHANNEL_ACCESS_TOKEN  LINE Channel Access Token
    PARKING_USERNAME           員工編號
    PARKING_PASSWORD           密碼

選用環境變數（可在 LINE 指令中覆蓋）：
    PARKING_DATE               預設申請日期（YYYY/MM/DD，逗號分隔多日）
    PARKING_MODE               預設模式（temp / short_term）

指令說明（LINE 訊息傳送）：
    搶位                       → 使用 config 預設日期搶臨停
    搶位 2026/06/20            → 搶指定日期（臨停）
    搶位 2026/06/20,06/21      → 搶多個日期
    搶位 短期 2026/06/20       → 短期車位模式
    狀態                       → 查看目前執行狀態
    停止                       → 終止執行中任務
    說明                       → 顯示指令說明
"""

import asyncio
import os
import re
import subprocess
import sys
from datetime import datetime

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse
from linebot.v3 import WebhookParser
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    AsyncApiClient,
    AsyncMessagingApi,
    Configuration,
    PushMessageRequest,
    ReplyMessageRequest,
    TextMessage,
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent

# ═══════════════════════════════════════════════════════════════
#  LINE SDK 設定
# ═══════════════════════════════════════════════════════════════
CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET", "")
CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")

if not CHANNEL_SECRET or not CHANNEL_ACCESS_TOKEN:
    print("[WARN] LINE_CHANNEL_SECRET 或 LINE_CHANNEL_ACCESS_TOKEN 未設定", flush=True)

configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
parser = WebhookParser(CHANNEL_SECRET)

# ═══════════════════════════════════════════════════════════════
#  FastAPI 應用程式
# ═══════════════════════════════════════════════════════════════
app = FastAPI(title="Parking Bot LINE Interface")

# ── 全域狀態（單一 worker 下安全）──────────────────────────────
_running_process: subprocess.Popen | None = None
_running_user_id: str = ""
_running_started_at: str = ""

BOT_DIR = os.path.dirname(os.path.abspath(__file__))

# ═══════════════════════════════════════════════════════════════
#  工具函式
# ═══════════════════════════════════════════════════════════════

def _parse_dates(text: str) -> list[str]:
    """從訊息文字解析所有 YYYY/MM/DD 或 YYYY-MM-DD 日期。"""
    found = re.findall(r"\d{4}[/-]\d{1,2}[/-]\d{1,2}", text)
    return [d.replace("-", "/") for d in found]


def _build_env(dates: list[str], mode: str) -> dict:
    """組合執行 parking_bot 所需的環境變數。"""
    env = os.environ.copy()
    if dates:
        env["PARKING_DATE"] = ",".join(dates)
    env["PARKING_MODE"] = mode
    return env


async def _send_push(user_id: str, text: str) -> None:
    """主動推送訊息給指定使用者（不需要 reply token）。"""
    async with AsyncApiClient(configuration) as api_client:
        api = AsyncMessagingApi(api_client)
        await api.push_message(
            PushMessageRequest(
                to=user_id,
                messages=[TextMessage(text=text[:4999])],
            )
        )


async def _bot_task(user_id: str, dates: list[str], mode: str) -> None:
    """在背景執行 parking_bot.py，完成後推送結果給使用者。"""
    global _running_process, _running_user_id, _running_started_at

    dates_str = "、".join(dates) if dates else "config 預設日期"
    mode_label = "短期車位" if mode == "short_term" else "臨時車位"

    await _send_push(
        user_id,
        f"🤖 搶位任務啟動！\n"
        f"模式：{mode_label}\n"
        f"日期：{dates_str}\n\n"
        f"搶位進行中，完成後自動通知您…",
    )

    try:
        proc = subprocess.Popen(
            [
                sys.executable,
                "parking_bot.py",
                "--headless",
                "--non-interactive",
                f"--mode={mode}",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=_build_env(dates, mode),
            cwd=BOT_DIR,
        )
        _running_process = proc
        _running_user_id = user_id
        _running_started_at = datetime.now().strftime("%H:%M:%S")

        # 等待完成（在執行緒池中，不阻塞事件迴圈）
        loop = asyncio.get_event_loop()
        stdout, _ = await loop.run_in_executor(None, proc.communicate)

        _running_process = None
        _running_user_id = ""

        # 取最後 15 行有意義的輸出作為摘要
        lines = [ln for ln in stdout.splitlines() if ln.strip()]
        summary = "\n".join(lines[-15:]) if lines else "(無輸出)"

        if proc.returncode == 0:
            await _send_push(user_id, f"✅ 搶位完成！\n\n{summary}")
        else:
            await _send_push(user_id, f"⚠️ 搶位任務結束（請確認結果）\n\n{summary}")

    except Exception as exc:
        _running_process = None
        _running_user_id = ""
        await _send_push(user_id, f"❌ 執行錯誤：{exc}")


# ═══════════════════════════════════════════════════════════════
#  LINE Webhook 端點
# ═══════════════════════════════════════════════════════════════

HELP_TEXT = (
    "🤖 停車搶位機器人指令\n"
    "─────────────────────\n"
    "搶位\n"
    "  → 使用預設日期搶臨停\n\n"
    "搶位 2026/06/20\n"
    "  → 搶指定日期（臨停）\n\n"
    "搶位 2026/06/20,2026/06/21\n"
    "  → 搶多個日期\n\n"
    "搶位 短期 2026/06/20\n"
    "  → 短期車位模式\n\n"
    "狀態  → 查看執行狀態\n"
    "停止  → 終止執行中任務\n"
    "說明  → 顯示此畫面"
)


@app.post("/callback")
async def callback(request: Request) -> PlainTextResponse:
    """LINE Webhook 入口：驗證簽章並處理訊息事件。"""
    global _running_process

    signature = request.headers.get("X-Line-Signature", "")
    body_bytes = await request.body()

    try:
        events = parser.parse(body_bytes.decode("utf-8"), signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    for event in events:
        if not isinstance(event, MessageEvent):
            continue
        if not isinstance(event.message, TextMessageContent):
            continue

        user_id: str = event.source.user_id
        text: str = event.message.text.strip()

        async with AsyncApiClient(configuration) as api_client:
            api = AsyncMessagingApi(api_client)

            async def reply(msg: str) -> None:
                await api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text=msg)],
                    )
                )

            # ── 搶位 ───────────────────────────────────────────
            if text.startswith("搶位"):
                is_running = (
                    _running_process is not None
                    and _running_process.poll() is None
                )
                if is_running:
                    await reply(
                        f"⚠️ 搶位任務執行中（{_running_started_at} 開始）\n"
                        "請等待完成，或傳送「停止」終止。"
                    )
                    continue

                dates = _parse_dates(text)
                mode = "short_term" if "短期" in text else "temp"
                asyncio.create_task(_bot_task(user_id, dates, mode))

                dates_display = "、".join(dates) if dates else "config 預設日期"
                await reply(f"🚀 收到！準備搶位…\n日期：{dates_display}")

            # ── 狀態 ───────────────────────────────────────────
            elif text == "狀態":
                is_running = (
                    _running_process is not None
                    and _running_process.poll() is None
                )
                if is_running:
                    await reply(f"🟢 搶位任務執行中（{_running_started_at} 開始）")
                else:
                    await reply(
                        "⚪ 目前無執行中任務。\n\n"
                        "傳送「搶位 YYYY/MM/DD」開始搶位"
                    )

            # ── 停止 ───────────────────────────────────────────
            elif text == "停止":
                is_running = (
                    _running_process is not None
                    and _running_process.poll() is None
                )
                if is_running:
                    _running_process.terminate()
                    _running_process = None
                    await reply("🛑 已停止搶位任務。")
                else:
                    await reply("⚪ 目前沒有執行中的任務。")

            # ── 說明 ───────────────────────────────────────────
            elif text in ("說明", "help", "Help", "?", "？"):
                await reply(HELP_TEXT)

            # ── 未知指令 ───────────────────────────────────────
            else:
                await reply("傳送「說明」查看可用指令。")

    return PlainTextResponse("OK")


# ═══════════════════════════════════════════════════════════════
#  健康檢查（Render 用）
# ═══════════════════════════════════════════════════════════════

@app.get("/health")
async def health() -> dict:
    is_running = (
        _running_process is not None and _running_process.poll() is None
    )
    return {
        "status": "ok",
        "bot_running": is_running,
        "started_at": _running_started_at if is_running else None,
        "timestamp": datetime.now().isoformat(),
    }


# ═══════════════════════════════════════════════════════════════
#  本地啟動
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
