# 桌機版打包 — Windows `.exe` / macOS `.app`

把程式包成一個資料夾，使用者**不用先裝 Python**，按兩下就能開。

以推廣來說這是 CP 值最高的一步：現在就能讓不會用終端機的人用到，
而且跟手機版的計畫沒有衝突。

## 怎麼打包

第一次要先裝打包用的套件：

```bash
.venv\Scripts\pip install -r requirements-dev.txt     # Windows
.venv/bin/pip install -r requirements-dev.txt         # macOS / Linux
```

然後在**專案根目錄**執行：

| 在哪台機器 | 執行 | 產出 |
|---|---|---|
| Windows | `build_desktop.bat` | `dist\FastDailyJourneyWriter\`（約 32 MB） |
| macOS | `./build_desktop.sh` | `dist/FastDailyJourneyWriter.app` |
| Linux | `./build_desktop.sh` | `dist/FastDailyJourneyWriter/` |

**兩邊用的是同一份 `journal.spec`。** 沒有 Windows 版和 Mac 版之分——
`backend/` 是同一份程式碼，差別只在你在哪台機器上按下 build。

打包好的資料夾整包壓縮就可以給人。Windows 使用者解壓縮後按
`FastDailyJourneyWriter.exe`；Mac 使用者按 `.app`。

## 這個資料夾裡有什麼

| 檔案 | 做什麼 |
|---|---|
| `journal.spec` | PyInstaller 設定：要打包哪些檔案、哪些 import 要手動指定 |
| `launcher.py` | 打包版的進入點。**所有作業系統差異都關在這一個檔案裡** |

從原始碼跑的時候用的是根目錄的 `run.py`，不會經過 `launcher.py`。

## `launcher.py` 為什麼存在

打包版有兩件事跟開發時不一樣，而這兩件事都跟作業系統有關：

1. **`content/` 和 `web/` 被解壓到別的地方**（PyInstaller 的 `sys._MEIPASS`），
   不再是專案根目錄底下。
2. **日記不能存在程式旁邊**。安裝目錄常常是唯讀的，
   而 onefile 模式的解壓目錄關掉程式就被刪掉了。

`launcher.py` 把這兩件事算出來，寫進兩個環境變數
（`JOURNAL_BUNDLE_DIR`、`JOURNAL_DATA_DIR`），**然後才** import 後端。

這樣一來 `backend/config.py` 只要讀那兩個變數就好，
**不需要知道自己是不是被打包過，也不需要任何 `sys.platform` 判斷**——
所有 OS 差異都留在 `platforms/` 這一層，符合
[platforms/README.md](../README.md) 的規矩。

日記實際會存在這裡：

| 作業系統 | 位置 |
|---|---|
| Windows | `%APPDATA%\FastDailyJourneyWriter\` |
| macOS | `~/Library/Application Support/FastDailyJourneyWriter/` |
| Linux | `~/.local/share/FastDailyJourneyWriter/` |

程式啟動時會把這個路徑印在視窗上，使用者要備份就照著找。
想改的話，設 `JOURNAL_DATA_DIR` 環境變數可以蓋掉。

## 為什麼保留黑色的終端機視窗

`console=True` 是刻意的。那個視窗是：

- 日記存放位置顯示的地方
- 出錯時訊息會出現的地方
- **關掉它就是關掉程式**——不然使用者不知道怎麼停

之後如果做了系統列圖示，再考慮改成 `console=False`。

## 還沒做的

- [ ] **圖示**。現在用 PyInstaller 的預設圖示。做好 `.ico`／`.icns` 之後，
      在 `journal.spec` 的 `EXE(...)` 加 `icon=`
- [ ] **程式碼簽章**。沒簽章的話，Windows SmartScreen 和 macOS Gatekeeper
      會跳警告。Windows 要買憑證，macOS 要 Apple 開發者帳號
- [ ] **安裝檔**（Inno Setup / `.dmg`）。目前是「解壓縮就能用」的資料夾
- [ ] **自動更新**。目前要重新下載
