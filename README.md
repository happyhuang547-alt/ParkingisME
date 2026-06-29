# ParkingisME 🅿️

> 車位是我的 — SHL 內部停車位自動預約機器人

自動登入 SHL 員工入口網站，持續監控臨時停車位空位，一有釋出立即送出申請。支援多日期同時搶位、Google Calendar 紀錄確認車位、LINE Bot 手機遠端操控。

---

## 功能

- **自動登入** — Playwright 瀏覽器自動化登入 SHL 內部系統
- **多日期同時搶位** — `asyncio.gather` 多 context 平行監控不同日期
- **智慧偵測** — 每 5 秒檢查車位，找到即自動送出申請
- **LINE Bot 遠端操控** — FastAPI webhook，可用 LINE 下指令搶位、查狀態、停止
- **Google Calendar 整合** — 搶到車位後自動建立日曆事件
- **防偵測機制** — 覆寫 `navigator.webdriver`、自訂 User-Agent、request header 處理
- **多重認證來源** — 環境變數 → GUI 輸入 → CLI 提示
- **CI/CD 自動執行** — GitHub Actions 定時 + Render cron job 上班前自動開搶
- **Windows 可直接執行** — PyInstaller 打包 `.exe`，免裝 Python

---

## 技術棧

| 層 | 技術 |
|---|---|
| 語言 | Python 3.10+ |
| 瀏覽器自動化 | Playwright (async API, Chromium) |
| Web Server | FastAPI + Uvicorn |
| LINE Bot | line-bot-sdk v3 |
| Google Calendar | google-auth-oauthlib + google-api-python-client |
| 打包 | PyInstaller |
| CI/CD | GitHub Actions |
| 部署 | Render (web service + cron job) |

---

## 快速開始

### 前置需求

- Python 3.10+
- Chrome / Chromium

### 安裝

```bash
# clone
git clone https://github.com/<your-username>/ParkingisME.git
cd ParkingisME

# Python 依賴
pip install -r requirements.txt

# Playwright Chromium
python -m playwright install chromium
```

### 設定環境變數

```bash
set PARKING_USERNAME=your_employee_id
set PARKING_PASSWORD=your_password
```

或直接修改 `parking_bot.py` 裡面的 `CONFIG` dict。

### 執行

```bash
# 一般模式（看瀏覽器）
python parking_bot.py

# 背景靜音模式
python parking_bot.py --headless

# Debug 模式（逐步暫停）
python parking_bot.py --debug

# CI 模式（僅環境變數，無 UI）
python parking_bot.py --headless --non-interactive
```

Windows 使用者也可以直接點兩下 `runparking.bat`。

---

## LINE Bot 設定

1. 到 [LINE Developers Console](https://developers.line.biz/) 建立 Messaging API Channel
2. 取得 Channel Secret 與 Channel Access Token
3. 設定環境變數：

```bash
set LINE_CHANNEL_SECRET=your_channel_secret
set LINE_CHANNEL_ACCESS_TOKEN=your_channel_access_token
```

4. 啟動 Server：

```bash
python line_bot_server.py
```

5. 將 Webhook URL 設為 `https://your-domain/callback`

### LINE 指令

| 指令 | 說明 |
|---|---|
| `搶位` | 使用預設日期清單開始搶位 |
| `搶位 2025/07/15` | 指定日期搶位 |
| `搶位 短期 2025/07/15` | 單日短期搶位 |
| `狀態` | 查詢目前執行狀態 |
| `停止` | 停止執行 |
| `說明` | 顯示所有可用指令 |

---

## Google Calendar 整合（選用）

1. 到 [Google Cloud Console](https://console.cloud.google.com/) 啟用 Google Calendar API
2. 下載 OAuth 2.0 憑證，存為 `credentials.json`
3. 第一次執行 `gcal.py` 會引導瀏覽器授權，產生 `token.json`

---

## 專案結構

```
ParkingisME/
├── parking_bot.py          # 主程式 — 瀏覽器自動化搶位
├── line_bot_server.py      # LINE Bot Webhook Server (FastAPI)
├── gcal.py                 # Google Calendar 事件建立模組
├── diagnose.py             # DOM 診斷工具（反查 selector）
├── requirements.txt        # Python 依賴
├── render.yaml             # Render 部署設定
├── parking_bot.spec        # PyInstaller 打包設定
├── runparking.bat          # Windows 批次檔（背景執行）
├── getparing.bat           # 同上（名字打錯🤷）
└── .github/workflows/run.yml  # GitHub Actions CI/CD
```

---

## 部署

### GitHub Actions

已設定 `.github/workflows/run.yml`：
- **定時**：週一至五 06:30 (UTC+8) 自動執行
- **手動**：GitHub 頁面可手動觸發
- 需設定 Repository secrets：`PARKING_USERNAME`、`PARKING_PASSWORD`

### Render

`render.yaml` 已定義兩種服務：
- **Web Service**：`parking-bot-line` — LINE Bot 伺服器
- **Cron Job**：`parking-bot-cron` — 週一至五 07:50 (UTC+8) 執行搶位

---

## 認證來源優先順序

1. 環境變數（`PARKING_USERNAME` + `PARKING_PASSWORD`）
2. tkinter GUI 對話框（本機互動用）
3. CLI 提示輸入

---

## 免責聲明

本專案僅供個人學習與自動化研究使用。使用前請確認符合所屬公司資訊安全政策。作者不對因使用本專案產生的任何後果負責。

---

## License

MIT
