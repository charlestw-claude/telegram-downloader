# Telegram Downloader 使用指南

> 版本：0.1.0 | 最後更新：2026-04-10

## 目錄

1. [簡介](#簡介)
2. [快速開始](#快速開始)
3. [功能說明](#功能說明)
4. [設定說明](#設定說明)
5. [常見問題](#常見問題)
6. [疑難排解](#疑難排解)

---

## 簡介

Telegram Downloader 是一個命令列工具，用於自動下載、訂閱及管理 Telegram 頻道和對話中的影片與圖片。

### 主要功能

- **一鍵下載**：從指定頻道或對話下載所有影片和圖片
- **訂閱監控**：訂閱頻道，自動偵測並下載新內容
- **智慧管理**：自動去重、並發下載、失敗重試
- **分類儲存**：依發送者 ID 分資料夾，影片與圖片分開存放

---

## 快速開始

### 第一步：取得 Telegram API 憑證

1. 前往 [my.telegram.org/apps](https://my.telegram.org/apps)
2. 登入你的 Telegram 帳號
3. 建立一個 Application
4. 記下 `api_id` 和 `api_hash`

### 第二步：安裝

```bash
git clone https://github.com/charlestw-claude/telegram-downloader.git
cd telegram-downloader
pip install -e .
```

### 第三步：設定

```bash
cp .env.example .env
```

編輯 `.env` 檔案，填入你的 API 憑證：

```
TELEGRAM_API_ID=你的api_id
TELEGRAM_API_HASH=你的api_hash
TELEGRAM_PHONE=+886912345678  # 可選
```

### 第四步：首次使用

```bash
# 從頻道下載媒體
telegram-dl download @channel_name
```

首次執行會要求你輸入手機號碼和驗證碼，完成後會建立 session 檔案，之後不需要重新登入。

---

## 功能說明

### 下載媒體 (`download`)

從指定的頻道或對話一次性下載所有媒體。

```bash
# 基本用法（下載影片+圖片）
telegram-dl download @channel_name

# 使用 chat ID
telegram-dl download -1001234567890

# 限制掃描訊息數量
telegram-dl download @channel_name --limit 100

# 只下載影片
telegram-dl download @channel_name --no-images

# 只下載圖片
telegram-dl download @channel_name --no-videos
```

### 訂閱頻道 (`subscribe`)

訂閱頻道後，可透過排程自動下載新內容。

```bash
# 訂閱頻道
telegram-dl subscribe @channel_name

# 只訂閱影片
telegram-dl subscribe @channel_name --no-images
```

### 取消訂閱 (`unsubscribe`)

```bash
telegram-dl unsubscribe @channel_name
```

### 查看訂閱清單 (`list`)

```bash
telegram-dl list
```

### 啟動自動下載 (`run`)

啟動排程器，定期檢查訂閱的頻道並自動下載新內容。

```bash
telegram-dl run
```

按 `Ctrl+C` 停止。

### 查看狀態 (`status`)

顯示下載統計資訊。

```bash
telegram-dl status
```

### 查看設定 (`config`)

顯示目前的設定值。

```bash
telegram-dl config
```

---

## 設定說明

所有設定透過 `.env` 檔案管理：

| 設定項 | 預設值 | 說明 |
|--------|--------|------|
| `TELEGRAM_API_ID` | （必填） | Telegram API ID |
| `TELEGRAM_API_HASH` | （必填） | Telegram API Hash |
| `TELEGRAM_PHONE` | （可選） | 手機號碼，用於自動登入 |
| `DOWNLOAD_PATH` | `./downloads` | 下載檔案儲存路徑 |
| `DB_PATH` | `./telegram_downloader.db` | 資料庫檔案路徑 |
| `MAX_CONCURRENT_DOWNLOADS` | `3` | 最大並發下載數 |
| `LOG_LEVEL` | `INFO` | 日誌等級（DEBUG/INFO/WARNING/ERROR） |
| `LOG_DIR` | `./logs` | 日誌檔案目錄 |

### 下載目錄結構

```
downloads/
├── 123456789/          # 發送者 ID
│   ├── videos/         # 影片
│   │   ├── video1.mp4
│   │   └── video2.mp4
│   └── images/         # 圖片
│       ├── photo1.jpg
│       └── photo2.png
├── 987654321/
│   ├── videos/
│   └── images/
└── unknown/            # 無法識別發送者
    ├── videos/
    └── images/
```

---

## 常見問題

### Q: 需要 Telegram Premium 嗎？
不需要。此工具使用 Telegram User API，只需要一般的 Telegram 帳號。

### Q: 可以下載私人頻道的內容嗎？
可以，只要你的帳號已加入該私人頻道。

### Q: 下載會佔用多少空間？
取決於頻道的媒體數量和品質。影片檔案通常較大，建議確保有足夠的磁碟空間。

### Q: 支援哪些媒體格式？
- **影片**：MP4、MOV、MKV、WebM、AVI
- **圖片**：JPG、PNG、WebP
- **動畫**：GIF

### Q: 重複的檔案會怎麼處理？
工具會自動檢查資料庫記錄和檔案大小，跳過已下載的內容。

---

## 疑難排解

### 登入失敗
- 確認 `TELEGRAM_API_ID` 和 `TELEGRAM_API_HASH` 正確
- 確認手機號碼格式正確（含國碼，如 `+886`）
- 刪除 `.session` 檔案後重試

### 下載速度慢
- Telegram API 有速率限制，這是正常的
- 降低 `MAX_CONCURRENT_DOWNLOADS` 可減少被限速的機會

### 找不到頻道
- 確認你的帳號已加入該頻道
- 使用 `@username` 格式而非頻道名稱
- 私人頻道需使用 chat ID（數字格式）

### 資料庫錯誤
- 刪除 `.db` 檔案重新開始（會失去下載歷史記錄）
- 確認磁碟空間充足
