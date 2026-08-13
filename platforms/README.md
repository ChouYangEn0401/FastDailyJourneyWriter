# platforms/ — 怎麼把程式包成給人用的東西

這一層放**打包與上架**，不放功能。一種通路一個資料夾。

## 唯一的規矩

> **`platforms/` 底下不寫商業邏輯。**

只放這些：打包腳本、圖示、啟動畫面、簽章設定、權限宣告、商店文案。

任何「這個功能怎麼運作」的程式碼都屬於上面幾層：

| 放哪裡 | 是什麼 |
|---|---|
| `content/` | 題組、版型。純資料，零 Python |
| `backend/` | Python 後端。**桌機端共用同一份** |
| `web/` | 瀏覽器介面。桌機三欄、手機四個畫面，**同一份檔案** |
| `core/` | JS 輸出核心（[做了三塊](../core/README.md)） |

**為什麼要有這條規矩**：一旦某個功能被寫進 `platforms/ios/`，
Android 那邊就得抄一份，兩份立刻開始分岔。半年後你會有兩個不一樣的 app
而不是一個 app 的兩個版本。

## 四個資料夾

| 資料夾 | 狀態 | 產出 | 需要什麼 |
|---|---|---|---|
| [`desktop/`](desktop/) | ✅ 可用 | `.exe`（Windows）、`.app`（macOS） | 只要 Python |
| [`pwa/`](pwa/) | ◐ 寫好了，**沒實機測過** | 加到手機主畫面 | 什麼都不用 |
| [`android/`](android/) | ⬜ 規劃中 | `.aab` / `.apk` | Android Studio |
| [`ios/`](ios/) | ⬜ 規劃中 | App Store 上架包 | **一台 Mac** ＋ Xcode |

### `pwa/` 為什麼只有一支腳本

manifest 和 service worker 在 `web/`，不在這裡——
它們是**伺服器送出去的檔案**，不是打包產物，路由在 `backend/main.py`。
`platforms/pwa/` 只放圖示產生器，那才是這一層該有的東西。

## 為什麼 Windows 和 macOS 是同一個資料夾

因為**它們跑的是同一份程式碼**。`backend/` 裡沒有任何一行 `sys.platform`
或 `os.name`，Python 的路徑一律走 `pathlib`。

分成 `windows/` 和 `mac/` 兩個資料夾的話，`backend/` 那 31 個檔案就要維護兩份，
改一個 bug 要改兩個地方——遲早會漏掉一邊。

實際的差異只有「在哪台機器上按下 build」：在 Windows 上跑 `build_desktop.bat`
得到 `.exe`，在 Mac 上跑 `build_desktop.sh` 得到 `.app`。**同一份 spec 檔。**

> 判準：資料夾按「**這段程式碼會不會不一樣**」分，
> 不是按「**它會在哪台電腦上跑**」分。

## 手機為什麼不能比照辦理

桌機版能直接打包，是因為 `.exe` 裡面可以塞一份 Python。
**手機不行**——所以 `ios/` 和 `android/` 在 `core/`（JS 版的輸出核心）
做完之前是空的。那是一次移植，不是打包工作。

`core/` 現在做了三塊（富文字、主題、文件組裝），
最難的卡片排版和存檔還沒動。細節與工作量估算見
[docs/roadmap.md](../docs/roadmap.md)。

在那之前，手機上要用這個 app 有一條現成的路：
**開著電腦上的伺服器，用手機的瀏覽器連過去**。
介面已經為手機重新排過了——四個畫面、底部分頁列，見
[docs/mobile-ui.md](../docs/mobile-ui.md)。做法在 [pwa/](pwa/README.md)。
