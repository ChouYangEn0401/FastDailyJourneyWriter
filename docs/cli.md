# 命令列參考（`python -m backend.cli`）

不用開伺服器，就能列題組、寫一篇、讀一篇、匯出成 HTML／卡片。給腳本、排程、AI 助理用。
讀寫的是跟 app **同一份**日記資料夾，走同一套清理與歷史版本：從這裡寫的，跟在編輯器裡寫的一模一樣，
寫壞了一樣在編輯器標題旁的「歷史」救得回來。不呼叫任何模型、不連網路。

- 每個指令加 `-h` 看它自己的說明和例子（`python -m backend.cli entry put -h`）。
- AI 怎麼挑題組、怎麼填，寫在 [skills/diary-templates/SKILL.md](../skills/diary-templates/SKILL.md)；
  題組的檔案格式在 [templates.md](templates.md)。
- 這份文件跟程式由 `tests/test_cli.py` 對過：每個指令、每個參數、每個 `-h` 的例子都要寫在這裡，漏了測試就失敗。

## 怎麼跑

在專案資料夾裡（Windows 用它自己的 venv）：

```bash
.venv\Scripts\python.exe -m backend.cli templates --brief      # Windows
python -m backend.cli templates --brief                         # 其他
```

## 指令一覽

| 指令 | 做什麼 | 會寫入嗎 |
|---|---|---|
| `templates` | 列出題組；`--id` 看一個題組的每一題 | 不會 |
| `layouts` | 列出輸出版型 | 不會 |
| `entry put` | 新增或更新某一天、某個題組的那一篇（內容是 JSON） | **會**（日記資料庫） |
| `entry show` | 讀出一篇，或某一天的全部 | 不會 |
| `entry list` | 最近寫過的日記（日期、題組、字數、編號，不印內容） | 不會 |
| `export` | 把一篇輸出成 HTML 頁面和（或）卡片 SVG | 只寫輸出的檔案 |

> 每一次執行，開頭都會跟 app 啟動時一樣：補裝還沒裝的內建題組與版型、把**沒改過**的內建題組換成新版
> （換之前先備份，見最後一節）、資料庫不存在就建一個空的。所以「不會寫入」指的是不動任何一篇日記。

## 每個指令都收的兩個參數

- `--json`：給程式用。只印**最後一行**的 JSON 信封（見下一節），其他什麼都不印。
  可以放在指令前面或後面（`--json templates` 和 `templates --json` 一樣）。
- `--data-dir=<資料夾>`：日記資料夾。沒給就照 app 的規則：環境變數 `JOURNAL_DATA_DIR`，沒設就是專案裡的 `data/`。
  資料夾不存在會自己建（裡面是空的日記）。測試、試東西時指到暫存資料夾，就不會碰到真的日記。

值一律寫成 `--旗標=值` 一個 token（`--date=2026-11-02`）；`--date 2026-11-02` 也看得懂，但給程式呼叫時請用等號。

## 信封與結束碼

加了 `--json`：

```text
{"ok": true, "result": {…}}                       結束碼 0
{"ok": false, "error": "日期要寫成 YYYY-MM-DD（收到：11/2）"}   結束碼 1
```

- 信封**一定是 stdout 的最後一行**，成功、失敗都是；`error` 是一句人話（中文），可以直接轉給人看。
- 參數寫錯（少了必填的、選項打錯、數字不是數字、沒有這個指令）也是結束碼 1 ＋ 同樣的信封，不會印 argparse 的英文說明。
- 程式本身出錯（不該發生）也一樣收在信封裡：`"error": "出錯了：<種類>: <訊息>"`，結束碼 1。
- 沒加 `--json`：結果以人看的文字印在 stdout，錯誤以「✗ …」印在 stderr，**最後一行照樣是信封**。
- `-h` 只印說明、結束碼 0、沒有信封。

**輸出一律是 UTF-8**，不管主控台是什麼編碼（Windows 中文版常是 cp950，印不出 emoji）：程式一開始就把
stdout／stderr 換成 UTF-8。呼叫端請用 UTF-8 解讀輸出；在 cp950 的主控台直接看會看到亂碼，但不會當掉。

## 寫入的內容怎麼給（`entry put`）

一個 JSON 物件，UTF-8（有沒有 BOM 都可以）：

```json
{"answers": {"<題目 id>": "<答案>"}, "title": "", "closing": "", "theme": "", "layout": ""}
```

- 從 **stdin** 讀；或給 `--input=<檔案>` 從檔案讀。
- **Windows PowerShell 5.1 的管線（`… | python …`）會把中文換成別的編碼**——那時改用 `--input=檔案`
  （或從程式呼叫、自己把 UTF-8 寫進 stdin，ClawBot 就是這樣）。不是 UTF-8 會回「stdin 要是 UTF-8…」，什麼都不寫。
- 每一種題型給什麼（文字、清單、選項、填空）見 SKILL.md 的「每一種題型怎麼填」。選項可以給 id 也可以給文字；
  清單可以給陣列，也可以給一段字（一行一項）。

## 指令

### `templates`

列出題組（範本）。題組＝一組問題；一篇日記＝某一天＋一個題組。

| 參數 | 說明 |
|---|---|
| `--id=<題組>` | 只看這一個，含每一題：`id`、`label`、`kind`（題型）、`options`、`pattern`／`blanks`（填空句與格數）、`hint`、`ai_hint`（這一題怎麼填） |
| `--brief` | 只列名稱、`when`（什麼時候用）、`minutes`、`moods`、`tags`，不列題目 |

回傳：沒有 `--id` → `{"templates": [...], "count": N}`；有 `--id` → `{"template": {...}}`。找不到 → `找不到題組：<id>`。

```bash
python -m backend.cli templates --brief --json
python -m backend.cli templates --id=three-lines --json
```

### `layouts`

列出輸出版型（`export --layout=` 用的 id）。內建 `letter`、`ledger`、`manuscript`、`postcard`；使用者可以自己加。

回傳 `{"layouts": [{"id", "name", "description", "tags", "default_theme", "card_paper"}, ...]}`。

```bash
python -m backend.cli layouts --json
```

### `entry put`

新增或更新**某一天、某個題組**的那一篇。同一天同一個題組再寫一次＝更新那一篇（不會多一篇）；沒給的題目一律不動。

| 參數 | 說明 |
|---|---|
| `--date=YYYY-MM-DD` | 必填，哪一天 |
| `--template=<題組>` | 必填，題組 id |
| `--merge=fields\|append\|fill` | 已經有答案的題目怎麼辦。`fields`（預設）＝換成新的；`append`＝接在後面（清單接在最後、文字空一行接上）；`fill`＝**不動**，只填空著的，沒動的回在 `kept` |
| `--format=plain\|html` | `plain`（預設）＝純文字，會跳脫 `<`、`>`，換行保留；`html`＝編輯器的 HTML（只留 `<b> <i> <u> <s> <br> <span style="color">`） |
| `--input=<檔案>` | 從這個 UTF-8 檔案讀內容，不從 stdin |

回傳：

```text
{"entry": {"id", "date", "template", "template_name", "title", "layout", "theme", "chars", "updated_at"},
 "created": true|false, "filled": ["題目 id", ...], "kept": [...], "ignored": [{"field", "why"}, ...]}
```

- `ignored`：不是這個題組的題目、對不上選項的答案，各寫一句為什麼。空的答案直接略過、不列。
- 寫入前，距離上一份自動備份超過六小時就先備份一次資料庫（跟 app 啟動時同一套）。

```bash
echo '{"answers": {"fact": "今天下雨"}}' | python -m backend.cli entry put --date=2026-11-02 --template=three-lines --merge=fill --json
python -m backend.cli entry put --date=2026-11-02 --template=jot --input=answers.json --json
```

（第一行是 bash／Git Bash 的寫法。Windows 的 cmd、PowerShell 管線送出去的不是 UTF-8，用第二行的 `--input=檔案`。）

### `entry show`

讀出一篇，或某一天的全部。

| 參數 | 說明 |
|---|---|
| `--id=<編號>` | 這一篇（`put`、`list` 回的 `id`）；有給就不看 `--date` |
| `--date=YYYY-MM-DD` | 那一天的全部 |
| `--template=<題組>` | 搭 `--date`：只看那個題組的那一篇 |

回傳 `{"date", "count", "entries": [{…entry 的摘要…, "answers": {...}, "closing": "", "text": "整篇的純文字"}]}`。
那天沒寫 → `count` 是 0（不是錯誤）；`--id` 找不到 → `找不到日記 #N`。

```bash
python -m backend.cli entry show --date=2026-11-02 --json
python -m backend.cli entry show --id=12 --json
```

### `entry list`

最近寫過的日記，新的在前。**只有日期、題組、字數、編號，不印內容。**

| 參數 | 說明 |
|---|---|
| `--limit=<N>` | 最多幾篇，1–500，預設 30 |

回傳 `{"entries": [{"id", "date", "template", "template_name", "title", "layout", "theme", "chars", "updated_at"}, ...]}`。

```bash
python -m backend.cli entry list --limit=7 --json
```

### `export`

把一篇輸出成一頁 **HTML**（瀏覽器打開、可以列印成 PDF）和（或）一張 **卡片 SVG**。

| 參數 | 說明 |
|---|---|
| `--id=<編號>` | 這一篇 |
| `--date=YYYY-MM-DD` | 搭 `--template` 指定那一篇 |
| `--template=<題組>` | 題組 id |
| `--format=both\|html\|card` | 預設 `both` |
| `--layout=<版型>` | 這一次用哪個版型（`layouts` 看全部）；不改那一篇自己的設定 |
| `--theme=<紙張顏色>` | `letterpress`、`notebook`、`linen`、`dawn`、`midnight`；同樣只影響這一次 |
| `--width=<px>` | 卡片寬度，480–2400，預設 1080 |
| `--paper=ruled\|grid\|plain\|dotted` | 卡片的紙，預設跟版型 |
| `--out-dir=<資料夾>` | 輸出到這裡；預設是日記資料夾的 `exports/` |

回傳 `{"entry": {...}, "layout", "theme", "html": "<完整路徑>", "svg": "<完整路徑>", "width", "height", "paper"}`
（只要 HTML 就沒有 svg 那幾個）。檔名是 `<日期>-<題組>-<編號>.html／.svg`，同一篇再匯出會蓋掉上一次的。
要 PNG：用瀏覽器開那個 SVG、視窗 `width`×`height` 截圖（SKILL.md 有指令）。

```bash
python -m backend.cli export --date=2026-11-02 --template=three-lines --format=card --json
```

## 隱私：輸出就是日記

- `entry show` 的輸出、`export` 產生的檔案，**就是日記本身**。呼叫端不要把 stdout 留在 log、追蹤檔、工作紀錄裡；
  要記就只記指令名、日期、題組、字數、編號、結束碼。
- `entry list` 刻意不印內容，可以放心列。
- 錯誤訊息不含日記內容（最多帶回你給的日期、題組 id、檔名）。
- `exports/` 底下的檔案在日記資料夾裡，跟資料庫一樣是私人的；用完不要搬去別的地方或上傳。

## ClawBot 怎麼叫它

ClawBot（個人 agent host）的日記功能（Telegram 的 `/diary` 系列）就是這支命令列的呼叫端，它不碰這邊的資料庫、不開這邊的伺服器：

```text
<日記專案>\.venv\Scripts\python.exe -m backend.cli <指令> … --json [--data-dir=<diary_data_dir>]
```

- 經它自己的外部程式管理（argv 陣列、不開視窗、60 秒逾時），值一律 `--旗標=值` 一個 token；工作目錄是這個專案的資料夾。
- `entry put` 的內容用 UTF-8 寫進 stdin（不放在命令列參數裡），環境變數 `PYTHONIOENCODING=utf-8`。
- 只讀**最後一行**信封；每一次的輸出都寫在一個暫存檔、讀完就刪，不留在它自己的工作紀錄。
- 用到的：`templates --brief`、`templates --id=`、`entry put --merge=append|fill --format=html|plain`、`entry show`、`export`。
- 找不到這個專案、沒有 `.venv`、或這個版本還沒有 `backend/cli.py`，它會先擋下來、回一句話，不會叫。

## 內建題組升級時的備份

新版改了內建題組時，`content/superseded.json` 記著每一個舊版的指紋。每一次啟動（app 或命令列）：

- 資料夾裡那一份**還是某個舊版、一字沒改** → 換成新版；
- 改過的 → 不動；刪掉的 → 不會回來；
- **日記本身（資料庫裡的每一篇與歷史版本）完全不碰**——題組是資料庫旁邊的檔案；
- 真的要換之前，先備份資料庫（`backups/journal-<時間>-before-template-upgrade.sqlite3`），
  被換掉的舊檔留在 `backups/defaults-<時間>-before-upgrade/`。**備份做不出來就不換**（舊的題組照樣能用）。
