# 系統架構說明

追蹤兆豐證券-新莊分點對 健亞(4130) 的每日買賣動向，自動發送 Telegram 通知與 Excel 明細。

---

## 整體流程圖

```
┌──────────────┐  cron 0 19 * * 1-5   ┌──────────────┐
│  n8n         │ ───────────────────► │  Zeabur      │
│ (排程觸發)   │   POST /run?key=...  │  HTTP Server │
└──────────────┘                      │  (server.py) │
       ▲                              └──────┬───────┘
       │ 失敗時通知                          │ 呼叫
       │                                     ▼
       │                              ┌──────────────────┐
       │                              │ check_broker.py  │
       │                              │  ┌────────────┐  │
       │                              │  │ MoneyDJ    │◄─┼── 抓最新一日券商分點
       │                              │  └────────────┘  │
       │                              │  ┌────────────┐  │
       │                              │  │ Yahoo API  │◄─┼── 收盤價
       │                              │  └────────────┘  │
       │                              │  ┌────────────┐  │
       │                              │  │ Telegram   │──┼─► 發文字訊息
       │                              │  └────────────┘  │
       │                              │  有交易時：       │
       │                              │  ┌──────────────┐│
       │                              │  │fetch_history ││── 重抓 2025/11→今天
       │                              │  │   .py        ││── 寫 Excel
       │                              │  └──────────────┘│
       │                              │  ┌────────────┐  │
       │                              │  │ Telegram   │──┼─► 寄 Excel 附件
       │                              │  └────────────┘  │
       │                              └──────────────────┘
       │                                     │
       └─────────────────────────────────────┴──► T健亞(4130) 頻道
```

---

## 元件總覽

| 元件 | 角色 | 位置 |
| --- | --- | --- |
| **n8n** | 排程觸發器（週一到週五 19:00） | `https://albowu.zeabur.app` |
| **HTTP Server** (`server.py`) | 接 webhook，包裝主邏輯 | Zeabur 服務 `broker-checker` |
| **主邏輯** (`check_broker.py`) | 抓券商資料、發 Telegram、判斷是否要寄 Excel | 同上 container |
| **歷史更新** (`fetch_history.py`) | 重新抓 2025/11 至今的完整明細，輸出 Excel | 同上 container（被 subprocess 呼叫） |
| **MoneyDJ** | 券商分點資料來源 | `fubon-ebrokerdj.fbs.com.tw` |
| **Yahoo Finance** | 收盤價資料來源 | `query1.finance.yahoo.com` |
| **Telegram Bot** | 通知發送通道 | Bot `@stock4130_bot`，頻道 `T健亞(4130)` |
| **GitHub Repo** | 程式碼儲存（Zeabur 自動建構來源） | `wuahe/stock-4130-tracker` |

---

## 資料來源細節

### 1. 券商分點資料（MoneyDJ）

- **最新一日**（給 `check_broker.py` 用）
  ```
  https://fubon-ebrokerdj.fbs.com.tw/z/zc/zco/zco0.djhtm
    ?a=4130
    &b=0037003000300077    ← 兆豐券商代碼
    &BHID=7000             ← 新莊分點代碼
    &c=1
  ```
- **歷史區間**（給 `fetch_history.py` 用）
  ```
  https://fubon-ebrokerdj.fbs.com.tw/z/zc/zco/zco0/zco0.djhtm
    ?A=4130&b=0037003000300077&BHID=7000
    &C=1&D=2025-11-01&E={today}&ver=V3
  ```
- 回傳 HTML 編碼為 `big5`，用 regex 解析 `<TD class="t4n0">日期</TD>` 等欄位。

### 2. 收盤價（Yahoo Finance）

```
https://query1.finance.yahoo.com/v8/finance/chart/4130.TWO
  ?period1=...&period2=...&interval=1d
```
- 健亞為櫃買中心(OTC)，所以 ticker 是 `4130.TWO`，不是 `4130.TW`。

---

## HTTP 端點

| Method | Path | 用途 | 驗證 |
| --- | --- | --- | --- |
| `GET` | `/` 或 `/health` | 健康檢查 | 不需 |
| `POST` | `/run?key=PASSWORD` | 觸發 `check_broker.main()` | `?key=` 或 `X-Auth-Key` header 需等於 `PASSWORD` 環境變數 |

服務網址：`https://broker-checker-4130.zeabur.app`

回應 JSON：
- 成功：`{"status": "ok"}`
- 失敗：`{"status": "error", "message": "..."}`
- 未授權：`{"error": "unauthorized"}` (HTTP 401)

---

## 環境變數

| 變數 | 說明 | 來源 |
| --- | --- | --- |
| `TELEGRAM_BOT_TOKEN` | Bot Token（必填） | BotFather |
| `TELEGRAM_CHAT_ID` | 預設發送頻道 ID（`-100...`） | Telegram 頻道資訊 |
| `PASSWORD` | `/run` 端點驗證用 | Zeabur 自動產生 |
| `PORT` | HTTP server 監聽埠（Zeabur 注入 `${WEB_PORT}` = 8080） | Zeabur |
| `TZ` | `Asia/Taipei`（讓 log 時間正確） | 自訂 |
| `PYTHONUNBUFFERED` | `1`（讓 print 即時輸出） | 自訂 |

本地開發：複製 `.env.example` → `.env`，填入實際值（已被 `.gitignore` 排除）。

---

## 通知邏輯

`check_broker.main()` 流程：

1. 抓最新一日券商資料
2. 抓收盤價
3. **一定**會發文字訊息到頻道（買、賣、買超、收盤價）
4. **若 買 > 0 或 賣 > 0** → 跑 `fetch_history.py` 重新產生 Excel → 把 Excel 寄到頻道
5. **若無交易**（buy=0 sell=0）→ 只發文字，不更新也不寄 Excel

---

## 部署架構

```
GitHub (wuahe/stock-4130-tracker)
       │ git push main
       ▼
Zeabur Auto Build  (Dockerfile → image)
       │
       ▼
broker-checker service (Tokyo Tencent Cloud)
  - port: 8080 (HTTP, name="web")
  - domain: broker-checker-4130.zeabur.app
  - 啟動指令: python3 server.py
```

`Dockerfile` 重點：
- `python:3.11-slim` 基底
- `TZ=Asia/Taipei`（在 image 內就設定 timezone）
- `EXPOSE 8080`
- `CMD ["python3", "server.py"]`

---

## n8n Workflow

定義檔：`n8n_workflow.json`

| 節點 | 設定 |
| --- | --- |
| **Schedule Trigger** | cron `0 19 * * 1-5`（週一到週五 19:00 Taipei） |
| **HTTP Request** | `POST https://broker-checker-4130.zeabur.app/run?key=...`，timeout 120 秒 |
| **錯誤通知** | 上面節點失敗時，發 Telegram 訊息到頻道 |

匯入步驟詳見 `README` / 對話紀錄。

---

## 失敗排查 (Runbook)

| 症狀 | 先看哪裡 | 常見原因 |
| --- | --- | --- |
| 完全沒收到訊息 | n8n 執行紀錄 | n8n workflow 沒 active，或 cron timezone 錯 |
| 收到 401 | n8n HTTP 節點 | `key=` query param 跟 Zeabur `PASSWORD` 不一致 |
| 收到文字但**沒 Excel** | Zeabur runtime log | `fetch_history.py` 失敗（網路、路徑、解析），或 60 秒 timeout |
| 文字內容是「查無交易紀錄」 | MoneyDJ 網頁 | 該日真的沒交易，或 MoneyDJ HTML 結構變了 → 改 regex |
| Telegram 回 `chat not found` | Telegram | Bot 沒被加入頻道，或 `TELEGRAM_CHAT_ID` 錯 |
| 服務 502 | Zeabur deployment status | Image 尚未跑起來，或 `PORT` 不是監聽 `${WEB_PORT}` |

實用指令：
```bash
# 健康檢查
curl https://broker-checker-4130.zeabur.app/

# 手動觸發
curl -X POST "https://broker-checker-4130.zeabur.app/run?key=$PASSWORD"

# 本地跑一次
set -a && . ./.env && set +a && python3 check_broker.py
```

---

## 檔案清單

| 檔案 | 內容 |
| --- | --- |
| `server.py` | HTTP server（webhook 入口） |
| `check_broker.py` | 主邏輯（每日檢查 + Telegram 通知） |
| `fetch_history.py` | 重新抓歷史並輸出 Excel |
| `Dockerfile` | Zeabur 建構腳本 |
| `requirements.txt` | Python 相依（requests, pandas, openpyxl） |
| `n8n_workflow.json` | n8n 排程匯入檔 |
| `.env` / `.env.example` | 環境變數（實際值 / 範本） |
| `note.md` | Telegram 頻道與 Bot 的設定備忘 |
| `兆豐新莊_健亞4130_交易明細.xlsx` | 由 `fetch_history.py` 動態生成（已 gitignore） |
