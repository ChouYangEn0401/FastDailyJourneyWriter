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

## 自己改題組

側欄每個題組右邊有支鉛筆，可以直接改；「＋ 新增」從空白開一個新的。
一個題組是幾個**段落**，每個段落有標題、顏色、和幾個**題目**。題目型態有：

| 型態 | 編輯器長什麼樣 |
|---|---|
| 多行文字 | 大輸入框，可以換色 |
| 條列 | 可增可減的編號行 |
| 單行文字 | 一行 |
| 單選 | 一排藥丸，點一下選起來（例：有／沒有） |
| 多選 | 同上，可複選 |
| 程度 | 同上（例：滿意／還可以／缺乏） |
| 填空句 | 句子裡用 `{}` 當空格，UI 自動變成行內填空 |

內建的五個題組可以照改、也可以刪。刪掉之後想拿回來：`POST /api/templates/{id}/restore`。

## 存檔怎麼運作（不會弄丟東西）

- **自動存**：停下來一秒多就會存，右上角會顯示「已儲存 HH:MM」。
- **不會亂建檔**：只點選範本、版型、顏色而沒寫任何字，不會產生日記。
- **同一天只有一篇**：重開程式會接著今天已經寫的那篇繼續，不會另開一筆。
- **換題組不會刪東西**：新題組沒有的題目，內容仍然留在那篇日記裡，只是暫時不顯示。
  編輯區上方會提示還留著幾段，換回原本的題組就會出現。
- **刪掉題組也不會刪日記**：用該題組寫的日記會退成純文字的「保留下來的內容」，
  仍然讀得到、也還能輸出。真的要刪還在用的題組，系統會先擋一次並告訴你有幾篇在用。
- **清理**：側欄「最近的日記」每筆右邊有 ✕；完全空白的日記可以一次清掉。

## 全部都是 `data/` 裡的檔案

程式裡沒有寫死任何題目或版型。第一次啟動時，內建的預設會被複製到 `data/`：

```
data/
  templates/*.json        題組
  layouts/<id>.html.j2    版型（Jinja2 模板）
  layouts/<id>.json       版型的名字、說明、標籤
  preferences.json        你的顏色與慣用設定
  journal.sqlite3         你的日記
  backups/                資料庫備份
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
按「管理顏色」可以加自己常用的顏色、刪掉用不到的，存在 `data/preferences.json`。
段落預設顏色跟著題組的段落色，也可以逐欄覆寫。顏色會一路帶到 HTML 與卡片。

寫字的區域在深色模式下仍然是**淺色的紙**——因為你挑的墨水色是為淺色紙選的，
放在深色底上會看不見（「墨黑」跟深色輸入框幾乎同色）。介面其他部分照系統深淺色走。

寫進資料庫前會白名單清理（只留 `b/i/u/s/br` 和帶 `color` 的 `span`），
`<script>` 之類的標籤連同內容一起丟掉。

## 輸出：同一篇日記，兩種形狀

這是最容易混淆的地方，所以講清楚：**「頁面」和「卡片」是兩個不同的東西**，
不是同一個東西的兩種預覽。

|  | 頁面 · HTML | 卡片 · 圖片 |
|---|---|---|
| 是什麼 | 一個 `.html` 檔 | 一張 SVG／PNG |
| 形狀 | 由**版型**決定：單欄長條、雙欄扁平、稿紙…共 4 種 | 單欄，寬度可選 1080～2000 |
| 怎麼看 | 瀏覽器打開、可捲動、可列印成 PDF | 直接看圖、傳 LINE |
| 想更扁 | 換「對帳」或「明信片」版型 | 形狀選「寬版 1600」 |

兩個都可以在右欄直接預覽再決定要不要下載。勾「加上可翻開的封面」會讓頁面多一張
要點一下才翻開的封面——把日記送給別人的那個想法。

第三個是 **繪圖 prompt**：從今天的內容生出中英各一段 prompt，忠實反映當天的事情與心情。

按「記住目前的設定」會把題組、版型、顏色、卡片設定存起來，下次開啟直接沿用。

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
