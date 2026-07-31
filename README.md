# FastDailyJourneyWriter

一個寫靈修日記的小工具。挑一個題組、挑一個版型，多半用勾的就寫完了；寫完直接輸出成
一頁做好的 HTML，或一張像筆記本紙的卡片（PNG／SVG，手機 LINE 可以直接傳）。

**輸出不需要 API key。** 版型是事先設計好的完成品，寫完就是最後的樣子——不用等、不用
連線、每個人都一樣。

## 啟動

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
python run.py                   # 或 python app/main.py
```

打開 <http://127.0.0.1:8000>。（也可以 `uvicorn app.main:app --reload`。）

環境變數：`JOURNAL_PORT`、`JOURNAL_HOST`、`JOURNAL_RELOAD=0`。

## 兩個可以挑的東西

**題組（範本）** — 今天要回答哪些問題。
**版型** — 這一天印出來長什麼樣子。

兩個各自獨立，可以隨意搭配。選了範本會自動帶一個建議版型，但隨時可以換。

### 內建題組

| id | 名稱 | 適合 |
|---|---|---|
| `quick-checkin` | 快速打卡 | 全部用勾的，兩分鐘 |
| `three-part` | 三段式（反省・靈修・代禱） | 一段一個顏色，手寫本常見分法 |
| `walk-with-jesus` | 同行日記（完整版） | 逐項自省的長版本 |
| `scripture-fill` | 填空式靈修 | 句子寫好了，填空格就行 |
| `free-bullets` | 星號隨筆 | 想到什麼寫什麼 |

### 內建版型

| id | 名稱 | 樣子 |
|---|---|---|
| `letter` | 信箋 Letter | 單欄、寬邊界、襯線標題 |
| `ledger` | 對帳 Ledger | 左欄整理勾選答案，右欄放文字 |
| `manuscript` | 稿紙 Manuscript | 整頁方格稿紙、字大、留白多 |
| `postcard` | 明信片 Postcard | 郵戳日期＋雙欄密排，適合截圖 |

## 全部都是 `data/` 裡的檔案

程式裡沒有寫死任何題目或版型。第一次啟動時，內建的預設會被複製到 `data/`：

```
data/
  templates/*.json        題組
  layouts/<id>.html.j2    版型（Jinja2 模板）
  layouts/<id>.json       版型的名字、說明、標籤
  journal.sqlite3         你的日記
  exports/                匯出的檔案
```

從此它們就是普通檔案：可以改、可以刪、可以複製一份改成自己的、可以傳給別人。
改壞了要還原內建版本：

```
POST /api/templates/{id}/restore
POST /api/layouts/{id}/restore
```

`.seeded.json` 記錄哪些預設安裝過了，所以刪掉的東西不會自己跑回來。

## 自己做一個版型

版型就是一個 Jinja2 模板。收到的變數：

- `doc` — `.date_display .weekday .entry_date .title .template_name .word_count`
  `.palette .sections .closing_lines .has_closing`
- `doc.sections[]` — `.title .color .icon .fields`
- 每個 field — `.label`、`.chips`（勾選題，每個 chip 有 `.label` `.selected`）、
  `.numbered`、`.lines`
- `t` — 主題色（`t.paper t.ink t.accent …`）
- `gift_cover`、`gift_message`

唯一一條硬規定：**文字一律用 `{{ line | runs }}` 輸出**，那是保留顏色的地方。

最快的做法是複製 `data/layouts/letter.html.j2` 改。

## 換色

編輯區上方有一排墨水色。**先選取文字，再點顏色**，跟換筆一樣。
段落預設顏色跟著題組的段落色，也可以逐欄覆寫。顏色會一路帶到 HTML 與卡片。

寫進資料庫前會白名單清理（只留 `b/i/u/s/br` 和帶 `color` 的 `span`），
`<script>` 之類的標籤連同內容一起丟掉。

## 輸出

1. **頁面（HTML）** — 單一檔案，沒有外部資源，深淺色都有，可以直接印。
   勾「加上可翻開的封面」會多一張要點一下才翻開的封面——把日記送給別人的那個想法。
2. **卡片（SVG／PNG）** — 橫線／方格／點陣／空白四種紙，預設跟著版型。
   文字真的坐在橫線上：排版節奏跟橫線間距是同一個格線。PNG 由瀏覽器轉，×1／×2／×3。
3. **繪圖 prompt** — 從今天的內容生出中英各一段 prompt，忠實反映當天的事情與心情。

## 選配的 AI（不影響上面任何一項）

複製 `.env.example` 成 `.env`，填入 `ANTHROPIC_API_KEY` 才會啟用。兩個功能：

- **設計新版型** — Claude 設計一個新版型，**存成檔案**。之後你跟拿到檔案的人都可以直接
  用，不會再呼叫 API。一次設計，永久使用。
- **AI 取名** — 從內容取一個標題。

繪圖 prompt 有 key 會由 Claude 產生，沒有 key 則用內建規則，兩者都能用。

## 隱私

**這個 repo 不會、也不應該包含任何人的日記內容。**

- 日記、匯出檔、你改過的題組與版型都在 `data/`，已被 `.gitignore` 擋掉。
- `.gitignore` 也擋掉 `*.jpg` / `sample*.txt` 這類參考素材。
- `app/seed/` 裡的預設題組只有題目結構、選項與段落顏色，沒有任何人的答案。

## 專案結構

```
run.py                   啟動
app/
  main.py                FastAPI；也可以直接 python app/main.py
  models.py              題組 / 版型 / 日記的 schema
  storage.py             SQLite（含欄位遷移）
  seed_manager.py        第一次啟動把預設複製到 data/
  template_registry.py   讀 data/templates/
  richtext.py            HTML 白名單清理、色彩 run 解析
  services.py            答案清理、載入
  seed/                  出廠預設（題組 JSON、版型 j2）
  render/
    document.py          Entry + Template -> 兩個 renderer 共用的結構
    layout_registry.py   讀 data/layouts/
    artifact_html.py     -> 一頁 HTML
    card_svg.py          -> 筆記本卡片 SVG
    textlayout.py        中英混排斷行（含避頭尾）
    themes.py            五組紙張顏色
  ai/                    選配：版型設計、標題、繪圖 prompt
  routers/               FastAPI 路由
web/                     前端（原生 JS，不需要 build）
```

## API

`GET /docs` 有完整的互動文件。

```
GET    /api/templates              題組清單
PUT    /api/templates/{id}         新增或修改題組
POST   /api/templates/{id}/restore 還原成內建版本
GET    /api/layouts                版型清單
GET    /api/layouts/{id}           取得版型原始碼
PUT    /api/layouts/{id}           儲存修改過的版型
POST   /api/layouts/design         用 AI 設計新版型（需要 key）
POST   /api/entries                新增日記
PATCH  /api/entries/{id}           更新
POST   /api/export/html            產生頁面
GET    /api/export/html/{id}       直接在瀏覽器看
POST   /api/export/card            產生卡片 SVG
GET    /api/export/card/{id}.svg   直接取 SVG
POST   /api/ai/image-prompt        繪圖 prompt（沒 key 有 fallback）
POST   /api/ai/title               標題建議（需要 key）
```
