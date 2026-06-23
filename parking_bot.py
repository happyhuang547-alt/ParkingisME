#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════╗
║          SHL 停車位自動搶位機器人  v1.0                       ║
║  Target : https://parking.shl-external.com/                  ║
║  Tool   : Python 3.10+ + Playwright (async)                  ║
╚══════════════════════════════════════════════════════════════╝

安裝依賴:
    pip install playwright
    playwright install chromium

執行:
    python parking_bot.py
    python parking_bot.py --debug          # 除錯模式（會在關鍵步驟暫停）
    python parking_bot.py --headless       # 無頭模式（背景執行）

Colab 執行（建議）:
    !pip install -r requirements.txt
    !playwright install --with-deps chromium
    # 可先設定環境變數避免互動輸入
    # %env PARKING_USERNAME=你的員工編號
    # %env PARKING_PASSWORD=你的密碼
    # %env PARKING_DATE=2026/06/15
    !python parking_bot.py --colab --headless
"""

import asyncio
import sys
import argparse
import os
import getpass
from datetime import datetime
from playwright.async_api import (
    async_playwright,
    Page,
    Browser,
    TimeoutError as PlaywrightTimeoutError,
)

try:
    import tkinter as tk
    from tkinter import messagebox
except Exception:
    tk = None
    messagebox = None

# ═══════════════════════════════════════════════════════════════
#  ① 全域設定  —— 修改這裡來調整行為
# ═══════════════════════════════════════════════════════════════
CONFIG = {
    # ── 登入資訊（啟動時會彈出視窗詢問）────────────────────────────────────
    "username": "",
    "password": "",

    # ── 網站 URL ──────────────────────────────────────────────
    "base_url": "https://parking.shl-external.com/",

    # ── 申請資料 ──────────────────────────────────────────────
    "car_number": "BPP-9715",       # 車號（下拉選單顯示文字）
    "reason":     "申請臨停",        # 申請事由
    "parking_lot": "LF-B3",         # 停車場代碼
    "time_slot":   "早上 08:00~20:00",  # 時段顯示文字
    "parking_dates": ["2026/06/29","2026/07/01","2026/07/02"],  # 申請停車日期列表，格式 YYYY/MM/DD；空列表 = 今天

    # ── 搶位行為 ──────────────────────────────────────────────
    # 每次「檢查車位」之間的等待時間（秒）；調低可加快速度，但太低可能被伺服器擋
    "check_interval_sec": 5,

    # 最多嘗試搶位次數（999 = 幾乎無限）
    "max_check_attempts": 999,

    # 發現有車位後，等待頁面反應的超時（秒）
    "apply_wait_sec": 10,

    # 網路請求超時（毫秒）
    "network_timeout_ms": 20_000,

    # 遇到崩潰/逾時時，最多重新啟動幾次
    "max_crash_retries": 5,

    # 崩潰後等待幾秒再重啟
    "crash_wait_sec": 5,

    # 瀏覽器是否顯示視窗（False = headless 背景；True = 顯示）
    "headless": False,

    # 是否在 Colab 執行（自動偵測，可用 --colab 強制開啟）
    "colab_mode": False,
}

# ═══════════════════════════════════════════════════════════════
#  ② CSS / XPath 選擇器  —— 如網站更新，只改這一段即可
#
#  Playwright 支援以下格式：
#    CSS  : "button.submit"  /  "#id"  /  ".class"
#    XPath: "xpath=//button[@id='submit']"
#    文字 : "text=員工登入"  （最穩健，適合中文按鈕）
#    混合 : "button:has-text('確定')"
#
#  調試技巧：在瀏覽器 DevTools Console 輸入
#    document.querySelector('YOUR_SELECTOR')
#  確認選擇器有效後再填入下方
# ═══════════════════════════════════════════════════════════════
SEL = {
    # ── 登入頁 ───────────────────────────────────────────────
    # 「員工登入」分頁按鈕（切換到員工登入表單）
    # 若為 Tab 元素，可能是 <a> 或 <button>，text= 最通用
    "tab_employee_login":   "text=員工登入",

    # 帳號欄位 —— name="username"
    # 備用: "xpath=//input[@name='username']"
    "input_username":       "input[name='username']",

    # 密碼欄位 —— name="password"
    # 備用: "xpath=//input[@name='password']"
    "input_password":       "input[name='password']",

    # 員工登入送出按鈕（表單內的「員工登入」按鈕，排除 Tab 按鈕）
    # 備用: "xpath=//button[normalize-space()='員工登入']"
    "btn_submit_login":     "button:has-text('員工登入')",

    # ── 員工專區導覽選單 ──────────────────────────────────────
    # 「員工專區」主入口按鈕（登入後需先點此才展開子選單）
    "menu_employee_area":   "button:has-text('員工專區')",

    # 「車位申請作業」主選單（點完員工專區後出現）
    # 真實元素是 button，使用更精準的 has-text 定位
    "menu_parking_apply":   "button:has-text('車位申請作業')",

    # 「臨時車位申請」子選單 / 按鈕
    # 備用: "xpath=//*[contains(text(),'臨時車位申請')]"
    "menu_temp_parking":    "button:has-text('臨時車位申請')",

    # ── 臨時車位申請表單 ──────────────────────────────────────
    # 申請日期輸入框（格式 YYYY/MM/DD）
    "input_date":           "input[name='temp_date']",

    # 申請事由輸入框 —— name="temp_apply_reason"
    "input_reason":         "input[name='temp_apply_reason']",

    # 車號下拉選單 —— name="car_sid"  BPP-9715 的 value="68210"
    # 備用: "xpath=//select[@name='car_sid']"
    "select_car":           "select[name='car_sid']",

    # 「選擇時段」按鈕（開啟時段 Modal）
    "btn_open_schedule":    "button:has-text('選擇時段')",

    # Modal 內：停車場下拉 —— f="site_sids"  （開啟 Modal 後才 visible）
    # 備用: "xpath=//select[@f='site_sids']"
    "select_parking_lot":   "select[f='site_sids']",

    # Modal 內：時段選項（radio button）
    # 先嘗試文字匹配，找不到則點第一個可用的 radio
    # label 的 for 屬性格式為: p_schedule_sid_<N>
    "option_time_slot":     "label[for^='p_schedule_sid_']",  # 點 radio 對應的 label

    # Modal 確定按鈕
    "btn_confirm":          "button:has-text('確定')",

    # ── 搶位區域 ──────────────────────────────────────────────
    # 「檢查車位」按鈕
    "btn_check":            "button:has-text('檢查車位')",

    # 顯示「無車位」錯誤的容器
    # 可能是 <div class="error">、<span class="alert"> 等
    # 備用: "xpath=//*[contains(@class,'error') or contains(@class,'alert') or contains(@class,'swal')]"
    "error_container":      ".error-message, .alert, [class*='error'], [class*='alert']",

    # 「送出申請」按鈕（最終送出）—— 實際上為「送出申請」而非「申請」
    "btn_apply":            "button:has-text('送出申請')",

    # 成功訊息（可選）—— 用來確認申請成功
    "success_msg":          "text=申請成功, text=成功, .swal2-title:has-text('成功')",
}

# ═══════════════════════════════════════════════════════════════
#  ③ 工具函式
# ═══════════════════════════════════════════════════════════════

def log(msg: str, level: str = "INFO") -> None:
    """帶時間戳與 emoji 前綴的即時狀態輸出"""
    now = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    icons = {
        "INFO":    "ℹ️ ",
        "SUCCESS": "✅",
        "WARN":    "⚠️ ",
        "ERROR":   "❌",
        "RETRY":   "🔄",
        "HUNT":    "🎯",
        "DEBUG":   "🔍",
    }
    icon = icons.get(level, "   ")
    print(f"[{now}] {icon}  {msg}", flush=True)


def is_colab_runtime() -> bool:
    """判斷是否在 Google Colab 環境執行。"""
    if "COLAB_RELEASE_TAG" in os.environ:
        return True
    if "google.colab" in sys.modules:
        return True
    try:
        import google.colab  # type: ignore  # noqa: F401
        return True
    except Exception:
        return False


def resolve_parking_dates() -> list[str]:
    """解析停車日期，優先使用環境變數 PARKING_DATE。"""
    env_parking_date = os.environ.get("PARKING_DATE", "").strip()
    if env_parking_date:
        # 支援單日或多日，例如: 2026/06/08,2026-06-09
        raw_dates = [d.strip() for d in env_parking_date.replace(";", ",").split(",") if d.strip()]
        normalized_dates = [d.replace("-", "/") for d in raw_dates]
        if normalized_dates:
            log(f"從環境變數 PARKING_DATE 讀取日期: {', '.join(normalized_dates)}", "DEBUG")
            return normalized_dates

    parking_dates = CONFIG.get("parking_dates", [])
    if parking_dates:
        return [str(d).strip().replace("-", "/") for d in parking_dates if str(d).strip()]

    return [datetime.now().strftime("%Y/%m/%d")]


async def diagnose_selector(page: Page, selector: str, desc: str = "") -> None:
    """診斷選擇器是否存在於頁面上（用於調試）"""
    desc = desc or selector
    try:
        # 嘗試查找所有符合的元素
        count = await page.locator(selector).count()
        log(f"[DIAG] 選擇器 '{selector}' 找到 {count} 個元素", "DEBUG")
        
        if count > 0:
            # 顯示第一個元素的狀態
            first_elem = page.locator(selector).first
            is_visible = await first_elem.is_visible()
            text = await first_elem.text_content()
            log(f"[DIAG] 第1個元素 - 可見: {is_visible}, 文本: '{text}'", "DEBUG")
    except Exception as e:
        log(f"[DIAG] 診斷選擇器 '{selector}' 時出錯: {e}", "DEBUG")


async def safe_click(page: Page, selector: str, desc: str = "",
                     timeout: int = None) -> None:
    """等待元素可見後點擊；逾時時拋出帶描述的例外"""
    t = timeout or CONFIG["network_timeout_ms"]
    desc = desc or selector
    log(f"點擊 ▶ {desc}")
    
    # 🔴 [修復] 在點擊前先診斷選擇器
    await diagnose_selector(page, selector, desc)
    
    await page.wait_for_selector(selector, state="visible", timeout=t)
    await page.click(selector)


async def safe_fill(page: Page, selector: str, value: str,
                    desc: str = "", timeout: int = None) -> None:
    """等待輸入框出現後清空並填入值；增加診斷和重試機制"""
    t = timeout or CONFIG["network_timeout_ms"]
    desc = desc or selector
    log(f"填入 ▶ {desc} = {value}")
    
    # 🔴 [修復] 在填入前先診斷選擇器
    await diagnose_selector(page, selector, desc)
    
    # 多個選擇器備用清單
    selectors_to_try = [selector]
    
    # 針對常見欄位，添加備用選擇器
    if "reason" in selector:
        selectors_to_try.extend([
            "input[name='temp_apply_reason']",
            "input[placeholder*='事由']",
            "input[placeholder*='原因']",
            "textarea[name='temp_apply_reason']",
        ])
    
    last_error = None
    for sel in selectors_to_try:
        try:
            log(f"嘗試填入選擇器: {sel}", "DEBUG")
            await page.wait_for_selector(sel, state="visible", timeout=min(t, 10_000))
            await page.fill(sel, value)
            log(f"✓ 成功填入『{desc}』", "SUCCESS")
            return
        except Exception as e:
            last_error = e
            log(f"✗ 選擇器 {sel} 失敗: {str(e)[:50]}...", "DEBUG")
            continue
    
    # 所有選擇器都失敗
    log(f"❌ 無法填入『{desc}』，嘗試頁面診斷...", "ERROR")
    await page.screenshot(path="screenshot_fill_error.png")
    raise PlaywrightTimeoutError(f"無法填入『{desc}』: {last_error}")


async def debug_pause(page: Page, msg: str, debug: bool) -> None:
    """除錯模式下暫停，讓你在瀏覽器 DevTools 檢查 DOM"""
    if debug:
        log(f"[DEBUG] {msg} — 按 Enter 繼續...", "DEBUG")
        await asyncio.get_event_loop().run_in_executor(None, input)


def ask_credentials(non_interactive: bool = False) -> None:
    """
    詢問員工編號與密碼，填入 CONFIG
    優先順序：環境變數 > tkinter GUI > 手動輸入
    """

    # 🔴 [修復] 首先嘗試從環境變數讀取
    username = os.environ.get("PARKING_USERNAME", "").strip()
    password = os.environ.get("PARKING_PASSWORD", "")
    
    if username and password:
        log(f"從環境變數讀取凭证: 員工編號={username}", "DEBUG")
        CONFIG["username"] = username
        CONFIG["password"] = password
        return
    
    # 非互動模式（如 Render Cron）必須由環境變數提供憑證
    if non_interactive:
        if not username or not password:
            log(
                "非互動模式缺少環境變數，請設定 PARKING_USERNAME 與 PARKING_PASSWORD",
                "ERROR",
            )
            sys.exit(2)

        CONFIG["username"] = username
        CONFIG["password"] = password
        return

    # Colab / headless 環境直接使用 CLI 輸入，避免 tkinter 失敗
    if CONFIG["colab_mode"]:
        if not username:
            username = input("請輸入員工編號: ").strip()
        if not password:
            password = getpass.getpass("請輸入密碼: ")

        if not username:
            print("未輸入員工編號，程式結束。")
            sys.exit(0)

        CONFIG["username"] = username
        CONFIG["password"] = password
        return

    # tkinter 不可用時，直接改用 CLI 輸入
    if tk is None or messagebox is None:
        if not sys.stdin.isatty():
            log("無可用終端機且缺少環境變數憑證，無法繼續", "ERROR")
            sys.exit(2)
        username = username or input("請輸入員工編號: ").strip()
        if not username:
            print("未輸入員工編號，程式結束。")
            sys.exit(0)
        password = password or getpass.getpass("請輸入密碼: ")
        CONFIG["username"] = username
        CONFIG["password"] = password
        return

    # 嘗試彈出 tkinter 視窗（如果在 GUI 環境下）
    try:
        root = tk.Tk()
        root.withdraw()  # 隱藏空白主視窗

        dialog = tk.Toplevel(root)
        dialog.title("SHL 停車搶位機器人 — 登入")
        dialog.resizable(False, False)
        dialog.grab_set()

        # ── 置中螢幕 ──
        dialog.update_idletasks()
        w, h = 280, 140
        sx = (dialog.winfo_screenwidth() - w) // 2
        sy = (dialog.winfo_screenheight() - h) // 2
        dialog.geometry(f"{w}x{h}+{sx}+{sy}")

        tk.Label(dialog, text="員工編號:").grid(row=0, column=0, padx=12, pady=10, sticky="e")
        username_var = tk.StringVar()
        username_entry = tk.Entry(dialog, textvariable=username_var, width=18)
        username_entry.grid(row=0, column=1, padx=12, pady=10)

        tk.Label(dialog, text="密碼:").grid(row=1, column=0, padx=12, pady=4, sticky="e")
        password_var = tk.StringVar()
        password_entry = tk.Entry(dialog, textvariable=password_var, show="●", width=18)
        password_entry.grid(row=1, column=1, padx=12, pady=4)

        confirmed = {"ok": False}

        def on_ok(event=None):
            if not username_var.get().strip():
                messagebox.showwarning("缺少資料", "請輸入員工編號", parent=dialog)
                return
            confirmed["ok"] = True
            dialog.destroy()

        def on_cancel(event=None):
            dialog.destroy()

        btn_frame = tk.Frame(dialog)
        btn_frame.grid(row=2, column=0, columnspan=2, pady=12)
        tk.Button(btn_frame, text="確定", width=8, command=on_ok).pack(side="left", padx=6)
        tk.Button(btn_frame, text="取消", width=8, command=on_cancel).pack(side="left", padx=6)

        username_entry.focus_set()
        dialog.bind("<Return>", on_ok)
        dialog.bind("<Escape>", on_cancel)
        dialog.protocol("WM_DELETE_WINDOW", on_cancel)

        root.wait_window(dialog)
        root.destroy()

        if not confirmed["ok"]:
            print("使用者取消登入，程式結束。")
            sys.exit(0)

        CONFIG["username"] = username_var.get().strip()
        CONFIG["password"] = password_var.get()
        
    except Exception as e:
        log(f"GUI 初始化失敗 ({e})，改用控制台輸入", "WARN")
        if not sys.stdin.isatty():
            log("無可用終端機且缺少環境變數憑證，無法繼續", "ERROR")
            sys.exit(2)
        username = username or input("請輸入員工編號: ").strip()
        if not username:
            print("未輸入員工編號，程式結束。")
            sys.exit(0)
        password = password or getpass.getpass("請輸入密碼: ")
        CONFIG["username"] = username
        CONFIG["password"] = password


# ═══════════════════════════════════════════════════════════════
#  ④ 各步驟函式
# ═══════════════════════════════════════════════════════════════

async def step_login(page: Page, debug: bool = False) -> None:
    """
    步驟 1：員工登入
    ─────────────────
    1. 前往首頁
    2. 點選「員工登入」Tab（切換到員工登入區）
    3. 輸入員工編號 & 密碼
    4. 按下登入送出按鈕
    """
    log("═══ 步驟 1：登入 ═══")
    await page.goto(CONFIG["base_url"], timeout=CONFIG["network_timeout_ms"])
    await page.wait_for_load_state("domcontentloaded")

    await debug_pause(page, "首頁已載入，即將點選員工登入 Tab", debug)

    # 點選「員工登入」分頁
    await safe_click(page, SEL["tab_employee_login"], "員工登入 Tab")
    await asyncio.sleep(0.5)  # 等待 Tab 切換動畫

    await debug_pause(page, "已切換到員工登入表單，即將填入帳密", debug)

    # 輸入帳號
    await safe_fill(page, SEL["input_username"], CONFIG["username"], "員工編號")

    # 輸入密碼
    await safe_fill(page, SEL["input_password"], CONFIG["password"], "密碼")

    await debug_pause(page, "帳密已填入，即將按下員工登入", debug)

    # 送出登入
    await safe_click(page, SEL["btn_submit_login"], "員工登入送出")

    # 等待登入後頁面穩定
    await page.wait_for_load_state("networkidle", timeout=CONFIG["network_timeout_ms"])

    # 只使用精準的員工專區 selector，避免誤點首頁上的相似文字
    log("等待選單初始化...", "DEBUG")
    await asyncio.sleep(3)  # 給 JS 額外的執行時間

    await safe_click(page, SEL["menu_employee_area"], "員工專區")
    log("登入成功，進入員工專區", "SUCCESS")


async def step_navigate_to_temp_parking(page: Page, debug: bool = False) -> None:
    """
    步驟 2：導覽至臨時車位申請
    ──────────────────────────
    1. 已在登入完成後進入員工專區
    2. 點選「車位申請作業」進入申請頁
    3. 若找不到主選單，改直接點選「臨時車位申請」
    """
    log("═══ 步驟 2：導覽至臨時車位申請 ═══")

    await debug_pause(page, "準備點選車位申請作業選單", debug)

    try:
        await safe_click(page, SEL["menu_parking_apply"], "車位申請作業")
        await asyncio.sleep(3)  # 等待頁面載入
        await page.wait_for_load_state("networkidle", timeout=CONFIG["network_timeout_ms"])
        log("已進入車位申請作業頁面，接著點選臨時車位申請", "SUCCESS")
        await safe_click(page, SEL["menu_temp_parking"], "臨時車位申請")
        await asyncio.sleep(3)
        await page.wait_for_load_state("networkidle", timeout=CONFIG["network_timeout_ms"])
        log("已進入臨時車位申請頁面", "SUCCESS")
    except PlaywrightTimeoutError:
        log("找不到『車位申請作業』，嘗試直接點選臨時車位申請", "WARN")
        await safe_click(page, SEL["menu_temp_parking"], "臨時車位申請")
        await page.wait_for_load_state("networkidle", timeout=CONFIG["network_timeout_ms"])
        log("已進入臨時車位申請頁面", "SUCCESS")


async def step_fill_form(page: Page, parking_date: str = "", debug: bool = False) -> None:
    """
    步驟 3：填寫申請表單
    ────────────────────
    1. 申請事由  input[name='temp_apply_reason']
    2. 車號      select[name='car_sid']  BPP-9715 = value 68210
    3. 點「選擇時段」開啟 Modal
    4. Modal 內：選停車場 LF-B3（select[f='site_sids']）+ 時段
    5. Modal 按「確定」
    """
    log("═══ 步驟 3：填寫申請表單 ═══")

    # 🔴 [修復] 在填表前確保表單完全加載
    log("等待表單元素加載...", "DEBUG")
    await asyncio.sleep(3)
    
    # 嘗試找到任何表單欄位以確認已進入表單頁
    form_selectors = [
        SEL["input_reason"],
        SEL["select_car"],
        SEL["input_date"],
        "form",
        "[class*='form']",
    ]
    
    form_found = False
    for form_sel in form_selectors:
        try:
            count = await page.locator(form_sel).count()
            if count > 0:
                await page.locator(form_sel).first.wait_for(state="visible", timeout=5_000)
                log(f"✓ 找到表單元素: {form_sel}", "DEBUG")
                form_found = True
                break
        except:
            continue
    
    if not form_found:
        log("⚠️  未找到表單元素，嘗試截圖診斷...", "WARN")
        await page.screenshot(path="screenshot_form_not_found.png")
        await asyncio.sleep(2)

    await debug_pause(page, "表單頁已就緒，準備填入申請事由", debug)

    if not parking_date:
        parking_date = (
            os.environ.get("PARKING_DATE", "").strip()
            or datetime.now().strftime("%Y/%m/%d")
        )
    date_input_value = parking_date.replace("/", "-")  # input[type=date] 需要 YYYY-MM-DD
    await safe_fill(page, SEL["input_date"], date_input_value, "申請日期", timeout=30_000)
    log(f"申請停車日期: {parking_date}")

    # ── 點「選擇時段」開啟 Modal ──
    await debug_pause(page, "準備開啟時段 Modal", debug)
    await page.wait_for_selector(SEL["btn_open_schedule"], state="visible", timeout=CONFIG["network_timeout_ms"])
    await safe_click(page, SEL["btn_open_schedule"], "選擇時段")
    await asyncio.sleep(3)  # 等待 Modal 動畫完成

    # ── Modal 內填寫申請資料 ──
    await debug_pause(page, "Modal 已開啟，準備填寫資料", debug)
    await safe_fill(page, SEL["input_date"], date_input_value, "申請日期", timeout=30_000)
    await safe_fill(page, SEL["input_reason"], CONFIG["reason"], "申請事由", timeout=30_000)

    # ── 車號下拉 select[name='car_sid'] ──
    log(f"選擇車號: {CONFIG['car_number']}")
    try:
        await page.select_option(
            SEL["select_car"],
            label=CONFIG["car_number"],
            timeout=CONFIG["network_timeout_ms"],
        )
        log(f"車號 {CONFIG['car_number']} 選擇成功", "SUCCESS")
    except Exception as e:
        log(f"select_option 失敗 ({e})，尚未選到車號", "WARN")

    await asyncio.sleep(1)

    # ── Modal 內：選停車場 LF-B3 ──
    await debug_pause(page, "Modal 已開啟，準備選停車場 LF-B3", debug)
    log(f"選擇停車場: {CONFIG['parking_lot']}")
    try:
        lot_option_count = await page.locator(f"{SEL['select_parking_lot']} option").count()
        if lot_option_count <= 1:
            log("停車場下拉無可選選項，略過選擇", "WARN")
        else:
            await page.select_option(
                SEL["select_parking_lot"],
                label=CONFIG["parking_lot"],
                timeout=CONFIG["network_timeout_ms"],
            )
            log(f"停車場 {CONFIG['parking_lot']} 選擇成功", "SUCCESS")
    except Exception as e:
        log(f"停車場 select_option 失敗 ({e})，嘗試文字點擊", "WARN")
        await safe_click(page, f"text={CONFIG['parking_lot']}", f"停車場 {CONFIG['parking_lot']}")
    await asyncio.sleep(0.5)

    # ── Modal 內：選時段 radio（重試迴圈，直到出現目標時段）──
    # 條件：label 文字包含 "09:00 - 18:00" 或 "08:00 - 20:00"（可在下方 TIME_PREFIXES 調整）
    TIME_PREFIXES = ["09:00 - 18:00", "08:00 - 20:00"]

    await debug_pause(page, "準備選時段（重試直到出現 09:00-18:00 或 08:00-20:00）", debug)
    schedule_attempt = 0

    while True:
        schedule_attempt += 1
        time_clicked = False

        # 1️⃣ 優先：精確比對 CONFIG["time_slot"] 的完整文字
        for sel in [
            f"label:has-text('{CONFIG['time_slot']}')",
            f"text={CONFIG['time_slot']}",
        ]:
            try:
                cnt = await page.locator(sel).count()
                if cnt > 0:
                    await page.locator(sel).first.click()
                    time_clicked = True
                    log(f"[時段#{schedule_attempt}] 精確比對成功: '{CONFIG['time_slot']}'", "SUCCESS")
                    break
            except Exception:
                pass

        # 2️⃣ 備用：掃描所有 radio label，找含 08:00 或 09:00 的選項
        if not time_clicked:
            radio_labels = page.locator(SEL["option_time_slot"])
            cnt = await radio_labels.count()
            for i in range(cnt):
                try:
                    label_text = await radio_labels.nth(i).inner_text()
                    if any(prefix in label_text for prefix in TIME_PREFIXES):
                        await radio_labels.nth(i).click()
                        time_clicked = True
                        log(f"[時段#{schedule_attempt}] 找到符合時段，已選: {label_text.strip()!r}", "SUCCESS")
                        break
                except Exception:
                    pass

        if time_clicked:
            break  # 選到時段，離開重試迴圈

        # ── 找不到符合時段 → 重新整理頁面（Modal 內 option 不會自動更新）──
        log(f"[時段#{schedule_attempt}] 無「09:00 - 18:00」或「08:00 - 20:00」時段，重新整理頁面以取得最新時段...", "RETRY")

        # 先嘗試關閉 Modal，避免 reload 前有殘留 DOM
        for close_sel in ["button:has-text('×')", "button:has-text('取消')"]:
            try:
                close_btn = page.locator(close_sel).first
                if await close_btn.is_visible():
                    await close_btn.click()
                    break
            except Exception:
                pass

        await asyncio.sleep(CONFIG["check_interval_sec"])

        # 重新整理頁面（讓伺服器重新產生時段選項）
        await page.reload()
        await page.wait_for_load_state("networkidle", timeout=CONFIG["network_timeout_ms"])
        await asyncio.sleep(0.8)

        # 重新填申請日期
        try:
            await page.fill(SEL["input_date"], date_input_value)
            await page.evaluate(
                """([sel, val]) => {
                    const el = document.querySelector(sel);
                    if (!el) return;
                    const setter = Object.getOwnPropertyDescriptor(
                        window.HTMLInputElement.prototype, 'value').set;
                    setter.call(el, val);
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                }""",
                ["input[name='temp_date']", date_input_value]
            )
        except Exception:
            pass

        # 重新填申請事由
        try:
            await safe_fill(page, SEL["input_reason"], CONFIG["reason"], "申請事由（重整後）")
        except Exception:
            pass

        # 重新選車號
        try:
            await page.select_option(
                SEL["select_car"],
                label=CONFIG["car_number"],
                timeout=5_000,
            )
        except Exception:
            pass
        await asyncio.sleep(0.3)

        # 重新開啟 Modal 並重選停車場
        await safe_click(page, SEL["btn_open_schedule"], f"重新選擇時段（第 {schedule_attempt} 次，頁面已重整）")
        await asyncio.sleep(0.8)
        try:
            lot_option_count = await page.locator(f"{SEL['select_parking_lot']} option").count()
            if lot_option_count > 1:
                await page.select_option(
                    SEL["select_parking_lot"],
                    label=CONFIG["parking_lot"],
                    timeout=5_000,
                )
        except Exception:
            pass
        await asyncio.sleep(0.5)

    await asyncio.sleep(0.3)

    # ── Modal 確定 ──
    await debug_pause(page, "準備按確定確認時段", debug)
    await safe_click(page, SEL["btn_confirm"], "確定")
    await asyncio.sleep(0.5)
    log("表單填寫完成，準備搶位", "SUCCESS")


async def step_hunt_parking(page: Page, debug: bool = False) -> bool:
    """
    步驟 4：搶位核心迴圈
    ────────────────────
    策略：
      • 持續點擊「檢查車位」
      • 讀取錯誤容器文字
      • 若不含「無車位」→ 有車位，立即申請
      • 若含「無車位」→ 等待 check_interval_sec 再試

    返回:
      True  = 已成功送出申請
      False = 達到最大次數仍失敗
    """
    log("═══ 步驟 4：開始搶位迴圈 ═══", "HUNT")
    max_tries = CONFIG["max_check_attempts"]
    interval  = CONFIG["check_interval_sec"]

    for attempt in range(1, max_tries + 1):
        try:
            # ── 點擊「檢查車位」──
            # 使用較短的逾時（3 秒），避免卡住搶位速度
            await page.click(SEL["btn_check"], timeout=3_000)

            # 短暫等待伺服器回應
            await asyncio.sleep(interval)

            # ── 讀取錯誤訊息 ──
            # 嘗試各可能的錯誤容器選擇器
            error_text = ""
            for sel in SEL["error_container"].split(", "):
                sel = sel.strip()
                locator = page.locator(sel)
                cnt = await locator.count()
                if cnt > 0:
                    error_text = await locator.first.inner_text()
                    break

            # ── 判斷是否仍顯示「無車位」──
            if "無車位" in error_text:
                # 每 20 次輸出一次，避免刷屏
                if attempt % 20 == 0 or attempt == 1:
                    log(f"[第 {attempt:04d} 次] 仍無車位，繼續搶...", "RETRY")
                continue

            # ── 有車位！立即申請 ──
            log(f"[第 {attempt:04d} 次] 偵測到車位！錯誤訊息='{error_text}'", "SUCCESS")
            await debug_pause(page, "即將按下申請，確認後按 Enter", debug)
            return await _do_apply(page)

        except PlaywrightTimeoutError:
            # 點擊超時（伺服器忙），跳過本輪
            if attempt % 20 == 0:
                log(f"[第 {attempt:04d} 次] 點擊逾時，繼續搶...", "WARN")

        except Exception as e:
            log(f"[第 {attempt:04d} 次] 例外: {e}", "ERROR")
            await asyncio.sleep(1)

    log(f"已達最大嘗試次數 {max_tries}，搶位失敗", "ERROR")
    return False


async def _do_apply(page: Page) -> bool:
    """點擊「申請」按鈕並等待確認結果（內部函式）"""
    try:
        apply_btn = page.locator(SEL["btn_apply"])
        if await apply_btn.count() == 0:
            log("找不到「申請」按鈕", "WARN")
            return False

        if not await apply_btn.is_enabled():
            log("「申請」按鈕已停用，等待 1 秒後重試...", "WARN")
            await asyncio.sleep(1)

        await apply_btn.click()
        log("已按下「申請」，等待確認回應...", "SUCCESS")

        # 等待成功訊息（如頁面有 SweetAlert2 等彈窗）
        try:
            await page.wait_for_selector(
                SEL["success_msg"],
                timeout=CONFIG["apply_wait_sec"] * 1_000,
            )
            log("🎉  收到成功確認訊息！申請完成！", "SUCCESS")
        except PlaywrightTimeoutError:
            # 沒有成功彈窗也不代表失敗，可能頁面直接跳轉
            log("未偵測到成功彈窗，請手動確認瀏覽器畫面", "WARN")

        return True

    except Exception as e:
        log(f"申請過程發生錯誤: {e}", "ERROR")
        return False


# ═══════════════════════════════════════════════════════════════
#  ⑤ 主程式 — 含崩潰自動重啟機制
# ═══════════════════════════════════════════════════════════════

async def run_bot(debug: bool = False, headless_override: bool = None) -> None:
    """
    主控流程：
    1. 登入
    2. 導覽至臨時車位申請
    3. 填寫表單
    4. 搶位迴圈
    若任一步驟崩潰/網路逾時，自動重啟最多 max_crash_retries 次
    """
    headless = headless_override if headless_override is not None else CONFIG["headless"]
    colab_mode = CONFIG["colab_mode"]
    
    # 準備日期列表（環境變數 PARKING_DATE 優先）
    parking_dates = resolve_parking_dates()
    
    log(f"準備搶位 {len(parking_dates)} 個日期: {', '.join(parking_dates)}", "INFO")
    
    completed_dates = []
    
    async with async_playwright() as pw:
        for date_idx, target_date in enumerate(parking_dates, 1):
            log(f"================================", "INFO")
            log(f"第 {date_idx}/{len(parking_dates)} 個日期: {target_date}", "HUNT")
            log(f"================================", "INFO")

            crash_count = 0
            max_crash = CONFIG["max_crash_retries"]

            while crash_count <= max_crash:
                browser: Browser = None
                try:
                    log(f"啟動 Chromium（第 {crash_count + 1} 次）...")
                    launch_args = [
                        # 避免部分網站偵測到 Playwright 自動化旗標
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                        "--disable-dev-shm-usage",
                    ]
                    if colab_mode:
                        # Colab 容器常見穩定性參數
                        launch_args.extend([
                            "--disable-gpu",
                            "--no-zygote",
                            "--single-process",
                        ])

                    browser = await pw.chromium.launch(
                        headless=headless,
                        args=launch_args,
                    )

                    # 建立新頁面，偽裝成一般 Chrome
                    page: Page = await browser.new_page(
                        viewport={"width": 1366, "height": 768},
                        user_agent=(
                            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/124.0.0.0 Safari/537.36"
                        ),
                    )

                    async def mask_request_headers(route) -> None:
                        headers = dict(route.request.headers)
                        headers["sec-ch-ua"] = '"Not/A)Brand";v="99", "Chromium";v="148"'
                        headers["sec-ch-ua-mobile"] = "?0"
                        headers["sec-ch-ua-platform"] = '"Linux"' if colab_mode else '"Windows"'
                        headers["accept-language"] = "zh-TW"
                        await route.continue_(headers=headers)

                    await page.route("**/*", mask_request_headers)

                    await page.add_init_script(
                        """
                        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                        Object.defineProperty(window, 'chrome', {
                            value: { runtime: {} },
                            configurable: true,
                            writable: true,
                        });
                        Object.defineProperty(navigator, 'languages', {
                            get: () => ['zh-TW', 'zh', 'en-US'],
                        });
                        Object.defineProperty(navigator, 'plugins', {
                            get: () => [
                                {
                                    0: {type: 'application/x-google-chrome-pdf', suffix: 'pdf', description: 'Portable Document Format'},
                                    name: 'Chrome PDF Plugin',
                                    filename: 'internal-pdf-viewer',
                                    description: 'Portable Document Format',
                                    length: 1,
                                },
                            ],
                        });
                        Object.defineProperty(navigator, 'hardwareConcurrency', {
                            get: () => 8,
                        });
                        Object.defineProperty(navigator, 'deviceMemory', {
                            get: () => 8,
                        });
                        """
                    )
                    # 設定全域預設逾時
                    page.set_default_timeout(CONFIG["network_timeout_ms"])

                    # ── 執行各步驟 ──
                    await step_login(page, debug)
                    await step_navigate_to_temp_parking(page, debug)
                    await step_fill_form(page, target_date, debug)
                    success = await step_hunt_parking(page, debug)

                    if success:
                        log("=" * 55, "SUCCESS")
                        log(f"  🎉  日期 {target_date} 搶位成功！", "SUCCESS")
                        log("=" * 55, "SUCCESS")
                        completed_dates.append(target_date)
                    else:
                        log("搶位結束（未搶到或已達上限）", "WARN")

                    break  # 正常結束，跳出重啟迴圈進入下一日期

                except PlaywrightTimeoutError as e:
                    crash_count += 1
                    log(f"網路逾時（第 {crash_count}/{max_crash} 次）: {e}", "ERROR")
                    if crash_count <= max_crash:
                        log(f"{CONFIG['crash_wait_sec']} 秒後重新啟動...", "RETRY")
                        await asyncio.sleep(CONFIG["crash_wait_sec"])

                except KeyboardInterrupt:
                    log("使用者中止程式", "WARN")
                    return

                except Exception as e:
                    crash_count += 1
                    log(f"程式異常崩潰（第 {crash_count}/{max_crash} 次）: {type(e).__name__}: {e}", "ERROR")
                    if crash_count <= max_crash:
                        log(f"{CONFIG['crash_wait_sec']} 秒後重新啟動...", "RETRY")
                        await asyncio.sleep(CONFIG["crash_wait_sec"])

                finally:
                    if browser:
                        try:
                            await browser.close()
                        except Exception:
                            pass  # 瀏覽器已崩潰，忽略關閉錯誤

            if crash_count > max_crash:
                log(f"日期 {target_date} 已達最大崩潰重啟次數（{max_crash}），跳過此日期", "ERROR")
    
    # ── 總結 ──
    log("=" * 60, "SUCCESS")
    log(f"搶位結束！成功搶到 {len(completed_dates)}/{len(parking_dates)} 個日期", "SUCCESS")
    if completed_dates:
        log(f"成功日期: {', '.join(completed_dates)}", "SUCCESS")
    log("=" * 60, "SUCCESS")


# ═══════════════════════════════════════════════════════════════
#  ⑥ 命令列入口
# ═══════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(
        description="SHL 停車位自動搶位機器人",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="除錯模式：每個關鍵步驟暫停，讓你用 DevTools 確認選擇器",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="強制無頭模式（背景執行，不顯示瀏覽器視窗）",
    )
    parser.add_argument(
        "--colab",
        action="store_true",
        help="Colab 模式：停用 GUI 輸入並套用 Colab 瀏覽器參數",
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="非互動模式：僅從環境變數讀取帳密，缺少時直接結束",
    )
    args = parser.parse_args()

    detected_colab = is_colab_runtime()
    CONFIG["colab_mode"] = bool(args.colab or detected_colab)
    if CONFIG["colab_mode"]:
        CONFIG["headless"] = True
        log("偵測到 Colab 執行環境，已啟用 Colab 模式（預設 headless）", "INFO")

    # ── 取得帳號密碼 ──
    ask_credentials(non_interactive=args.non_interactive)

    print("=" * 60)
    print("  SHL 停車位自動搶位機器人 v1.0")
    print(f"  目標  : {CONFIG['base_url']}")
    print(f"  帳號  : {CONFIG['username']}")
    print(f"  車號  : {CONFIG['car_number']}")
    print(f"  停車場: {CONFIG['parking_lot']}  時段: {CONFIG['time_slot']}")
    parking_dates = resolve_parking_dates()
    print(f"  日期  : {', '.join(parking_dates)}")
    print(f"  間隔  : {CONFIG['check_interval_sec']} 秒  最大嘗試: {CONFIG['max_check_attempts']}")
    print(f"  除錯  : {'開啟' if args.debug else '關閉'}  "
          f"無頭: {'開啟' if args.headless else '依設定'}")
    print("=" * 60)

    asyncio.run(run_bot(
        debug=args.debug,
        headless_override=True if args.headless else None,
    ))


if __name__ == "__main__":
    main()
