# Untracked Files

未進入 git 追蹤但對專案運作重要的檔案。

## 檔案清單

| 檔案 | 用途 | 如何取得/重建 |
|------|------|--------------|
| `.env` | Telegram API 憑證與設定 | 複製 `.env.example`，填入 API credentials（從 [my.telegram.org/apps](https://my.telegram.org/apps) 取得） |
| `*.session` | Telethon 登入 session | 首次執行 `telegram-dl` 時自動建立（需手機驗證） |
| `*.session-journal` | Session WAL | 自動產生 |
| `telegram_downloader.db` | 下載紀錄資料庫 | 自動建立，可刪除重建（會失去歷史紀錄） |
| `downloads/` | 下載的媒體檔案 | 執行下載後產生 |
| `logs/` | 日誌檔案 | 自動產生 |
