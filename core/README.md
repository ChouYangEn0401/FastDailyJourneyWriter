# core/ — 共用的 JavaScript 輸出核心

把日記變成看得到的東西：這一層是 `backend/render/` 的 JavaScript 版本。

存在的理由只有一個：**手機上沒有 Python。**
桌機版可以把整個直譯器塞進 `.exe`，手機不行。
所以同一套邏輯要有第二份實作——這個資料夾。

細節與整體規劃見 [docs/roadmap.md](../docs/roadmap.md)。

## 目前進度

| 檔案 | 對應的 Python | 狀態 |
|---|---|---|
| `richtext.js` | `backend/richtext.py` | ✅ 完成，與 Python 逐案對照通過 |
| `themes.js` | `backend/render/themes.py` | ✅ 完成 |
| `document.js` | `backend/render/document.py` | ✅ 完成 |
| `artifact_html.js` | `backend/render/artifact_html.py` | ◐ 只搬了 `runsToHtml`，樣板引擎還沒接 |
| — | `backend/render/card_svg.py` | ⬜ 還沒開始（最難的一塊） |
| — | `backend/render/textlayout.py` | ⬜ 還沒開始 |
| — | `backend/storage.py` | ⬜ 還沒開始 |

> **這一層全部都還沒有在真的手機上跑過。**
> 通過的是 Node 上的對照測試，不是裝置測試。

### `artifact_html.js` 為什麼只搬一半

`content/layouts/*.j2` 是 Jinja2 樣板。Nunjucks 的語法幾乎一樣，
計畫是**把同一批 `.j2` 檔直接交給 Nunjucks**，而不是維護第二套版型——
版型是這個工具最有價值的部分，分成兩份就等著走鐘。

但接 Nunjucks 需要一個相依套件和一個 build 步驟，這個 repo 現在兩者都沒有。
與其半吊子接上去，不如先把**唯一那個自訂 filter**（`runsToHtml`）搬過來測好，
剩下的等真的要做 PWA 時一次處理。

## 三條規矩

**一、不准 import 後端。**
這一層不知道 FastAPI、SQLite、檔案系統的存在。輸入是普通物件，輸出是字串。
一旦 `core/` 需要伺服器才能跑，它就失去存在的意義了。

**二、屬性名維持 snake_case。**
`doc.date_display`、`f.is_empty`、`doc.has_closing` 看起來不像 JavaScript，
但 `content/layouts/*.j2` 就是這樣讀的，而那些檔案要跟 Python 端**共用同一份**。
改成 camelCase 等於把版型拆成兩套。函式名則照 JavaScript 慣例（`buildDocument`）,
因為樣板不會呼叫函式。

**三、改了 `backend/`，就要重跑對照測試。**
見下。

## 測試

```bash
cd core
node --test "test/*.test.js"      # 不需要裝任何東西
```

只要有 Node 18 以上就能跑，零相依套件（用 Node 內建的 `node:test`）。

測試分兩種：

**對照測試**（`test/parity.test.js`）——
預期值不是手寫的，是從 Python **錄下來的**：

```bash
python core/test/tools/dump_parity.py    # 重新產生 fixtures/parity.json
```

那支腳本把 40 組富文字、13 組顏色、5 組主題、3 篇日記餵進 `backend/`，
把答案存成 JSON。JavaScript 這邊再跑一次同樣的輸入，逐字比對。

**這代表「兩份實作真的一樣」，而不是「有人寫下他希望的結果」。**

改過 `backend/richtext.py` 或 `backend/render/` 之後請重跑那支腳本。
fixture 的 diff 就是訊號：要嘛 `core/` 得跟上，要嘛那個改動是個 bug。

`test/tools/dump_parity.py` 是 `backend/` 以外唯一的 Python 檔。
它是測試工具，不是核心的一部分——`core/` 底下沒有東西 import 它，
而它產生的 fixture 有進 repo，所以跑 JavaScript 測試不需要 Python。

**單元測試**（`test/richtext.test.js`、`test/document.test.js`）——
補對照測試搆不到的地方：時區、壞掉的輸入、會不會跑不完。

### 為什麼自己寫 tokenizer 而不用 DOMParser

`core/` 要能在沒有 DOM 的地方跑（Node、worker、將來的原生橋接）。

安全性不靠 tokenizer 寫得完美：**清理過程不會把輸入原樣吐回去**。
標籤名來自固定白名單，顏色是驗證過的 hex 重新組出來的，每一段文字都跳脫過。
所以就算 tokenizer 解析錯了，結果會是「不好看」，不會是「不安全」。
