#!/usr/bin/env python3
"""
每日檢查兆豐-新莊對健亞(4130)的買賣紀錄，透過 Telegram 通知。
排程建議：每天 19:00 執行
"""

import os
import requests
import urllib3
import re
import subprocess
from datetime import datetime
from pathlib import Path

urllib3.disable_warnings()

# === 設定 ===
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8660780420:AAFNMvmtStreFDXn_iL0diSi_6vpFQcNohs")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "-1003631115396")

STOCK_ID = "4130"
STOCK_NAME = "健亞"
BROKER_B = "0037003000300077"
BROKER_BHID = "7000"
BROKER_NAME = "兆豐-新莊"

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}


def fetch_latest_data():
    """從 MoneyDJ 抓取券商分點最近一個交易日的買賣資料"""
    url = (
        f"https://fubon-ebrokerdj.fbs.com.tw/z/zc/zco/zco0.djhtm"
        f"?a={STOCK_ID}&b={BROKER_B}&BHID={BROKER_BHID}&c=1"
    )
    r = requests.get(url, headers=HEADERS, timeout=15, verify=False)
    r.encoding = "big5"
    text = r.text

    pattern = (
        r'<TD class="t4n0">(20\d{2}/\d{2}/\d{2})</TD>\s*'
        r'<TD class="t3[nr]1">([\d,\-]+)</TD>\s*'
        r'<TD class="t3[nr]1">([\d,\-]+)</TD>\s*'
        r'<TD class="t3[nr]1">([\d,\-]+)</TD>\s*'
        r'<TD class="t3[nr]1">([\d,\-]+)</TD>'
    )
    matches = re.findall(pattern, text)

    if not matches:
        return None

    # 取最新一筆（第一筆即為最近交易日）
    m = matches[0]
    buy = int(m[1].replace(",", ""))
    sell = int(m[2].replace(",", ""))
    net = int(m[4].replace(",", ""))
    return {"date": m[0], "buy": buy, "sell": sell, "net": net}


def fetch_stock_price():
    """從 Yahoo Finance 取得當日收盤價"""
    p1 = int(datetime.now().timestamp()) - 86400
    p2 = int(datetime.now().timestamp()) + 86400
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{STOCK_ID}.TWO"
        f"?period1={p1}&period2={p2}&interval=1d"
    )
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        j = r.json()
        closes = j["chart"]["result"][0]["indicators"]["quote"][0]["close"]
        return round(closes[-1], 2) if closes and closes[-1] else None
    except Exception:
        return None


def send_telegram(message):
    """發送 Telegram 文字訊息"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
    }
    r = requests.post(url, json=payload, timeout=10)
    return r.json()


def send_telegram_file(file_path, caption=""):
    """發送檔案到 Telegram"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument"
    with open(file_path, "rb") as f:
        r = requests.post(
            url,
            data={"chat_id": TELEGRAM_CHAT_ID, "caption": caption, "parse_mode": "HTML"},
            files={"document": f},
            timeout=30,
        )
    return r.json()


def update_excel():
    """執行 fetch_history.py 更新 Excel"""
    script = Path(__file__).parent / "fetch_history.py"
    result = subprocess.run(
        ["python3", str(script)],
        capture_output=True, text=True, timeout=60,
    )
    print(result.stdout)
    if result.returncode != 0:
        print(f"Excel 更新失敗: {result.stderr}")
    return result.returncode == 0


EXCEL_PATH = Path(__file__).parent / "兆豐新莊_健亞4130_交易明細.xlsx"


def main():
    data = fetch_latest_data()

    if data is None:
        msg = (
            f"📊 <b>{STOCK_NAME}({STOCK_ID}) 券商追蹤</b>\n"
            f"🏢 {BROKER_NAME}\n\n"
            f"查無交易紀錄"
        )
    else:
        price = fetch_stock_price()
        buy_amt = round(data["buy"] * 1000 * price / 1000) if price else "N/A"
        sell_amt = round(data["sell"] * 1000 * price / 1000) if price else "N/A"

        if data["net"] > 0:
            action = "🟢 買超"
        elif data["net"] < 0:
            action = "🔴 賣超"
        else:
            action = "⚪ 持平"

        msg = (
            f"📊 <b>{STOCK_NAME}({STOCK_ID}) 券商追蹤</b>\n"
            f"📅 {data['date']}\n"
            f"🏢 {BROKER_NAME}  {action}\n\n"
            f"買進：{data['buy']:,} 張"
        )
        if isinstance(buy_amt, int):
            msg += f"（約 {buy_amt:,} 千元）"
        msg += (
            f"\n賣出：{data['sell']:,} 張"
        )
        if isinstance(sell_amt, int):
            msg += f"（約 {sell_amt:,} 千元）"
        msg += (
            f"\n買賣超：{data['net']:+,} 張\n"
        )
        if price:
            msg += f"\n收盤價：{price}"

    print(msg)
    result = send_telegram(msg)
    if result.get("ok"):
        print("✅ Telegram 通知已發送")
    else:
        print(f"❌ 發送失敗: {result}")

    # 有買進時，更新 Excel 並傳送到 Telegram
    if data and data["buy"] > 0:
        print("\n有買進紀錄，更新 Excel...")
        if update_excel():
            res = send_telegram_file(
                EXCEL_PATH,
                caption=f"📎 {BROKER_NAME} - {STOCK_NAME}({STOCK_ID}) 交易明細（2025/11 至 {data['date']}）",
            )
            if res.get("ok"):
                print("✅ Excel 已傳送到 Telegram")
            else:
                print(f"❌ Excel 傳送失敗: {res}")


if __name__ == "__main__":
    main()
