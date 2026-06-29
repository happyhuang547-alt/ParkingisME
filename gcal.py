"""
Google Calendar 整合模組 — 停車位事件寫入
========================================
使用前須先完成：
  1. 前往 https://console.cloud.google.com 建立專案
  2. 啟用 Google Calendar API
  3. 建立 OAuth 2.0 桌面應用程式憑證 → 下載 credentials.json
  4. 將 credentials.json 放在本檔案同層目錄
  5. 第一次執行會彈出瀏覽器授權，之後自動使用 token.json
"""

import os
import re
from datetime import datetime

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
CALENDAR_ID = "primary"
CREDENTIALS_FILE = os.path.join(os.path.dirname(__file__), "credentials.json")
TOKEN_FILE = os.path.join(os.path.dirname(__file__), "token.json")


def _now() -> str:
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


def _log(msg: str) -> None:
    print(f"[{_now()}] 📅  {msg}", flush=True)


def _ensure_files() -> None:
    """若檔案不存在但環境變數有提供，從環境變數寫入。"""
    if not os.path.exists(CREDENTIALS_FILE):
        env_val = os.environ.get("GOOGLE_CREDENTIALS_JSON", "").strip()
        if env_val:
            with open(CREDENTIALS_FILE, "w", encoding="utf-8") as f:
                f.write(env_val)
            _log("從 GOOGLE_CREDENTIALS_JSON 寫入 credentials.json")
    if not os.path.exists(TOKEN_FILE):
        env_val = os.environ.get("GOOGLE_TOKEN_JSON", "").strip()
        if env_val:
            with open(TOKEN_FILE, "w", encoding="utf-8") as f:
                f.write(env_val)
            _log("從 GOOGLE_TOKEN_JSON 寫入 token.json")


def _get_service():
    """認證並回傳 Google Calendar API service 物件。"""
    _ensure_files()
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            _log("重新整理 Google 憑證...")
            creds.refresh(Request())
        else:
            _log("需要 Google 授權，正在開啟瀏覽器...")
            if not os.path.exists(CREDENTIALS_FILE):
                _log("缺少 credentials.json，且未設定 GOOGLE_CREDENTIALS_JSON", "ERROR")
                raise FileNotFoundError("credentials.json not found")
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())
        _log("Google 憑證已儲存")
    return build("calendar", "v3", credentials=creds)


def _parse_time_range(time_slot: str) -> tuple[str, str]:
    """從 '早上 08:00~20:00' 解析出開始與結束時間。
    
    返回:
      (start_time, end_time) 格式皆為 'HH:MM'
    """
    m = re.search(r"(\d{2}:\d{2})~(\d{2}:\d{2})", time_slot)
    if m:
        return m.group(1), m.group(2)
    return "08:00", "20:00"


def add_parking_event(date_str: str, slot_id: str, lot: str, time_slot: str) -> bool:
    """在 Google Calendar 新增一筆停車位事件。
    
    參數:
      date_str: 日期，格式 YYYY/MM/DD
      slot_id:  車位編號（如 A12）
      lot:      停車場代碼（如 LF-B3）
      time_slot: 時段文字（如 '早上 08:00~20:00'）
    
    回傳:
      True 成功 / False 失敗
    """
    try:
        service = _get_service()
    except Exception as e:
        _log(f"無法取得 Calendar 服務: {e}")
        _log("請確認 credentials.json 存在且有效，並先在本機執行一次授權")
        return False

    try:
        date_iso = date_str.replace("/", "-")
        start_time, end_time = _parse_time_range(time_slot)

        summary = f"停車 {lot} - {slot_id}"
        description = (
            f"車位  : {slot_id}\n"
            f"停車場: {lot}\n"
            f"時段  : {time_slot}"
        )

        event = {
            "summary": summary,
            "description": description,
            "start": {
                "dateTime": f"{date_iso}T{start_time}:00",
                "timeZone": "Asia/Taipei",
            },
            "end": {
                "dateTime": f"{date_iso}T{end_time}:00",
                "timeZone": "Asia/Taipei",
            },
        }

        service.events().insert(calendarId=CALENDAR_ID, body=event).execute()
        _log(f"已加入 Google 日曆: {summary} ({date_str} {start_time}~{end_time})")
        return True

    except Exception as e:
        _log(f"建立 Calendar 事件失敗: {e}")
        return False
