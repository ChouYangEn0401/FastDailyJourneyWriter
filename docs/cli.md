# 命令列參考（`python -m backend.cli`）

不用開伺服器，就能列題組、替一段話挑題組、寫一篇、改幾題、讀一篇、匯出成 HTML／卡片、改設定。給腳本、排程、AI 助理用。
讀寫的是跟 app **同一份**日記資料夾，走同一套清理與歷史版本：從這裡寫的，跟在編輯器裡寫的一模一樣，
寫壞了一樣在編輯器標題旁的「歷史」救得回來。不呼叫任何模型、不連網路。

- 每個指令加 `-h` 看它自己的說明和例子（`python -m backend.cli entry put -h`）。
- AI 怎麼挑題組、怎麼填，寫在 [skills/diary-templates/SKILL.md](../skills/diary-templates/SKILL.md)；
  題組的檔案格式在 [templates.md](templates.md)；接進 SYNOX 的宣告在 [../synox-pack/README.md](../synox-pack/README.md)。
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
| `templates` | 列出題組（可依分類篩選）；`--id` 看一個題組的每一題 | 不會 |
| `templates suggest` | 替一段文字排出最像的幾個題組，每一個附理由（照規則，不呼叫模型） | 不會 |
| `templates categories` | 分類的字彙表：每一種結構、反思層級、步驟、標籤各有哪些題組 | 不會 |
| `templates restore` | 把一個內建題組放回（或還原成）內建版本 | 只寫 `templates/` 裡那一個檔 |
| `layouts` | 列出輸出版型 | 不會 |
| `entry put` | 新增或更新某一天、某個題組的那一篇（內容是 JSON，或直接一段字＝寫進第一題）；可點名換掉幾題；可標成 AI 整理 | **會**（日記資料庫） |
| `entry show` | 讀出一篇，或某一天的全部 | 不會 |
| `entry list` | 最近寫過的日記（日期、題組、字數、編號，不印內容） | 不會 |
| `export` | 把一篇輸出成 HTML 頁面和（或）卡片 SVG | 只寫輸出的檔案 |
| `settings` | 列出每一個設定；`settings get`／`settings set` 看、改一個 | `set` 寫 `preferences.json` |
| `setup` | 這份安裝的狀態；`setup init --preset=` 替新資料夾挑起始題組 | `init` 只加題組、寫設定，不刪 |

> 每一次執行，開頭都會跟 app 啟動時一樣：補裝還沒裝的內建題組與版型（照 `setup init` 選的組合）、把**沒改過**的內建題組換成新版
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
- 成功時 `result.message` 是給人看的那段文字（跟不加 `--json` 時印的一樣：寫入是一句話、`entry show` 是整篇、`templates` 是一行一個題組）。
  SYNOX 之類的宿主直接顯示它；程式要的資料照舊在 `result` 的其他欄位。
- 參數寫錯（少了必填的、選項打錯、數字不是數字、沒有這個指令）也是結束碼 1 ＋ 同樣的信封，不會印 argparse 的英文說明。
- 程式本身出錯（不該發生）也一樣收在信封裡：`"error": "出錯了：<種類>: <訊息>"`，結束碼 1。
- 沒加 `--json`：結果以人看的文字印在 stdout，錯誤以「✗ …」印在 stderr，**最後一行照樣是信封**。
- `-h` 只印說明、結束碼 0、沒有信封。

**輸出一律是 UTF-8**，不管主控台是什麼編碼（Windows 中文版常是 cp950，印不出 emoji）：程式一開始就把
stdout／stderr 換成 UTF-8。呼叫端請用 UTF-8 解讀輸出；在 cp950 的主控台直接看會看到亂碼，但不會當掉。

## 日期

`--date` 收 `YYYY-MM-DD`，也收 **`today`／`yesterday`**（`今天`／`昨天` 也行）。換日照設定 `day_start_hour`：
設成 4 的話，凌晨 01:30 的 `today` 還是前一天（熬夜寫日記的人用）。日期一律是這台電腦的本地時間。

## 寫入的內容怎麼給（`entry put`）

一個 JSON 物件，UTF-8（有沒有 BOM 都可以）：

```json
{"answers": {"<題目 id>": "<答案>"}, "title": "", "closing": "", "theme": "", "layout": "",
 "source_text": "作者原文（--author=ai 時）", "sources": {"<題目 id>": "這一題對應的原文"}}
```

- 從 **stdin** 讀；或給 `--input=<檔案>` 從檔案讀。
- **Windows PowerShell 5.1 的管線（`… | python …`）會把中文換成別的編碼**——那時改用 `--input=檔案`
  （或從程式呼叫、自己把 UTF-8 寫進 stdin，ClawBot 就是這樣）。不是 UTF-8 會回「stdin 要是 UTF-8…」，什麼都不寫。
- 每一種題型給什麼（文字、清單、選項、填空）見 SKILL.md 的「每一種題型怎麼填」。選項可以給 id 也可以給文字；
  清單可以給陣列，也可以給一段字（一行一項）。
- `source_text`／`sources` 只在 `--author=ai` 時有意義（下面）。

**也可以直接給一段字（純文字）**：內容不是 `{` 開頭，就當成作者自己的話，**整段寫進那個題組的第一個文字題**
（題型 `list`／`text`／`short_text` 的第一題；`jot` 就是「一則一則記下來」）。給人在 Telegram 打字用：
`/diary_put today jot 今天很好`。

- 第一題是清單（`jot`）：每一行是新的一則，**接在原本的後面**（不管 `--merge`；原本的幾則不動）。
- 第一題是文字：照 `--merge`（`fill` 下那一題已經有寫 → 不寫，`message` 會說「沒有寫進去」、`kept` 有那一題）。
- **不會拆成好幾題**：猜哪一句回答哪一題會寫錯地方。要填好幾題就給 JSON。
- `--author=ai` 不收純文字（AI 整理的版本一定要附原文，要用 JSON）。回傳多一個 `plain_text_field`（寫進哪一題）。
- 想記一句 `{` 開頭的話，包成 JSON：`{"answers": {"notes": "{…}"}}`。

## 題組的分類（資料契約）

每個題組（`content/templates/*.json`，裝到 `data/templates/`）除了原本的 `when`／`minutes`／`moods`／`tags`，還有三個 **ASCII** 欄位，
`templates --brief --json`、`templates --id=` 都會回，Telegram 端照這幾個畫按鈕、篩題組：

| 欄位 | 值 | 意思 |
|---|---|---|
| `structure` | `one-part`／`three-part`／`n-part` | 一段式／三段式／多段式（多段＝不是 1 也不是 3 段）。沒寫就照段落數算；`jot` 第二段是程式填的，所以明寫 `one-part` |
| `reflection` | `none`／`reflection`／`devotional`／`prayer` | 要不要回頭看、看多深。**是一道階梯**：`none` 只記錄；`reflection` 有反思（不談信仰）；`devotional` 在神面前反思／有經文；`prayer` 再加禱告、代禱、哀歌。「不談信仰」＝ `none,reflection` |
| `flow` | 字串陣列，照順序、每個步驟只出現一次 | 這個題組走過哪些步驟：`checkin` 與主同行的打卡、`events` 發生的事、`feelings` 感受、`worries` 擔心的事、`work` 工作與專案、`decision` 一個決定、`identity` 想成為的人、`review` 一段時間的回顧、`scripture` 經文、`reflection` 反思／學到什麼、`confession` 認罪、`gratitude` 感恩、`prayer` 禱告／代禱、`trust` 信靠、`people` 人、`quote` 別人說過的話、`plan` 下一步／明天。例：`three-part` 是 `["events", "reflection", "scripture", "prayer", "gratitude"]`＝先記事、再反思、再經文、再代禱感恩 |

中文標籤不要自己對照：`templates categories --json` 回每個值的 `id`、`label`、`templates`（有哪些題組）。
一個題組的 JSON 寫錯這三個欄位（不在字彙表裡）會整個被跳過（跟其他欄位寫錯一樣），啟動時的 log 會說。

## 指令

### `templates`

列出題組（範本）。題組＝一組問題；一篇日記＝某一天＋一個題組。

| 參數 | 說明 |
|---|---|
| `--id=<題組>` | 只看這一個，含每一題：`id`、`label`、`kind`（題型）、`options`、`pattern`／`blanks`（填空句與格數）、`hint`、`ai_hint`（這一題怎麼填） |
| `--brief` | 只列名稱、`when`（什麼時候用）、`minutes`、`moods`、`tags`、`structure`、`reflection`、`flow`，不列題目 |
| `--structure=<值>` | 只列這種結構（逗號分開＝其中之一） |
| `--reflection=<值>` | 只列這種反思層級（逗號分開＝其中之一；`none,reflection`＝不談信仰的） |
| `--flow=<步驟>` | 只列走過這些步驟的（逗號分開＝**都要有**） |
| `--tag=<標籤>` | 只列有這個標籤的（逗號分開＝其中之一） |

回傳：沒有 `--id` → `{"templates": [...], "count": N, "filters": {...}}`（有篩選才有 `filters`）；有 `--id` → `{"template": {...}}`。
找不到 → `找不到題組：<id>`；篩選值不在字彙表 → `沒有這種 reflection：<值>（有：…）`。沒有符合的題組不是錯誤，`count` 是 0。

```bash
python -m backend.cli templates --brief --json
python -m backend.cli templates --brief --reflection=none,reflection --json
python -m backend.cli templates --id=three-lines --json
```

### `templates suggest`

替一段文字（使用者寫的那段話）排出最像的幾個題組。**照規則，不呼叫模型**，每一分都說得出來：

| 參數 | 說明 |
|---|---|
| `--text=<字>` | 必填，使用者寫的那段話（整段放在一個參數裡；空的回錯） |
| `--limit=<N>` | 最多幾個建議，1–20，預設 5 |

規則（`content/suggest.json`；複製到 `data/suggest.json` 可以自己調，那一份優先）：

1. **線索**：表裡每個 signal 有一組 `words`；字裡出現就算命中。例：「擔心」「睡不著」→ `worry`；「客戶」「開會」→ `work`；「主」「詩篇」「禱告」→ `faith`。
2. **對上題組**：命中的 signal 指向幾個步驟（`flow`）、心情（`moods`）、標籤（`tags`）或直接點名題組（`templates`）；題組有對上就得 `weight` ×命中字數（最多 3）分，同一個 signal 多對上一個面向再加 1。
3. **長短**：少於 40 字 → 3 分鐘以內的題組 +2、15 分鐘以上 −2；多於 300 字 → 有書寫欄且 10 分鐘以上的 +2。
4. **信仰**：字裡沒出現 `faith` 的字時，`reflection` 是 `devotional`／`prayer` 的題組照設定 `suggest_faith`：`auto`（預設）扣 4 分、`prefer` 不扣、`never` 不列。
5. 什麼都沒對上 → 回預設題組（設定 `template_id`）、`jot`、`three-lines`，理由寫「沒有特別的線索」。

回傳：

```text
{"suggestions": [{"id", "name", "group", "minutes", "structure", "reflection", "flow", "score", "why": ["提到「擔心」→ 擔心的事；心情：焦慮", ...]}, ...],
 "signals": [{"id": "worry", "label": "在擔心", "words": ["擔心", "睡不著"]}, ...],
 "length": 23,
 "categories": {"reflection": "" | "reflection" | "devotional" | "prayer", "flow": ["worries", "work"]}}
```

`categories` 是給挑題組的畫面預選用的：字裡指向哪一個反思層級、哪幾個步驟。`why` 是給人看的一句話，可以直接轉述。

```bash
python -m backend.cli templates suggest --text="今天跟客戶開會被罵，很擔心案子" --json
```

### `templates categories`

分類的字彙表，給挑題組的畫面（Telegram 的按鈕）用。

回傳 `{"structure": [{"id", "label", "templates": [題組 id…]}, …], "reflection": [...], "flow": [...], "groups": [...], "tags": [...]}`；
`structure`／`reflection`／`flow` 照固定順序（`reflection` 就是那道階梯的順序），`tags` 照用的題組數多到少，`groups` 照側欄的順序。

```bash
python -m backend.cli templates categories --json
```

### `templates restore`

把一個內建題組放回（`setup init --preset=generic` 沒裝的）或還原成內建版本（改壞了的）。只動 `templates/` 裡那一個檔，不碰日記。

| 參數 | 說明 |
|---|---|
| `--id=<題組>` | 必填，內建題組 id |

回傳 `{"template": {…brief…}}`；不是內建題組 → `<id> 不是內建題組，沒有可以放回的版本`。

```bash
python -m backend.cli templates restore --id=capsule --json
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
| `--date=YYYY-MM-DD` | 必填，哪一天（也收 `today`／`yesterday`） |
| `--template=<題組>` | 必填，題組 id |
| `--merge=fields\|append\|fill` | 已經有答案的題目怎麼辦。`fields`（預設）＝換成新的；`append`＝接在後面（清單接在最後、文字空一行接上）；`fill`＝**不動**，只填空著的，沒動的回在 `kept` |
| `--overwrite=<題目 id,…>\|all` | **點名可以換掉的題目**（逗號分開），不管 `--merge` 是什麼、不管是誰寫的；`all`＝這次給了的每一題。換掉的回在 `overwritten`。點名的題目這個題組沒有 → 回錯、什麼都不寫。`closing` 也可以點名 |
| `--author=user\|ai` | `user`（預設）＝作者自己的話。`ai`＝替作者整理的版本，見下面 |
| `--source-text=<檔案>` | `--author=ai` 時：作者原文的 UTF-8 檔案（整篇一份）。也可以放在 JSON 的 `source_text` |
| `--format=plain\|html` | `plain`（預設）＝純文字，會跳脫 `<`、`>`，換行保留；`html`＝編輯器的 HTML（只留 `<b> <i> <u> <s> <br> <span style="color">`） |
| `--input=<檔案>` | 從這個 UTF-8 檔案讀內容，不從 stdin |

**`--author=ai`（AI 整理的版本）**——給 AI 助理替作者潤飾、整理用，規矩寫死在程式裡：

- **一定要附作者原文**：`--source-text=檔案` 或 JSON 的 `source_text`（整篇），每一題各自對應的原文放 `sources`；都沒有 → 回錯、什麼都不寫。
- 填進去的每一題記在 `provenance.fields.<id>`（`author: "ai"`、時間、`source`）；原文存在 `provenance.source_text`（再整理一次會接在後面）。
- **輸出時**（HTML、卡片、`entry show` 的 `text`）那一題的標題後面多「（AI 整理）」，底下多一欄「作者原文」；整篇的原文在最後一段「作者原文」。四種版型都一樣，不用改版型。
- **作者已經寫過的題目不換**（回在 `protected`），除非 `--overwrite` 點名；`--merge=append` 不接受（會把兩個人的字混成一段）。
- 作者之後自己再寫那一題（命令列 `--author=user`，或在編輯器裡改）就把標記拿掉；原文留著。
- 跟 `--merge=fill` 搭：只填空著的、作者沒寫過的題目——這是 AI 幫忙時最安全的組合。

回傳：

```text
{"entry": {"id", "date", "template", "template_name", "title", "layout", "theme", "chars", "ai_fields": [...], "updated_at"},
 "created": true|false, "author": "user"|"ai",
 "filled": ["題目 id", ...], "kept": [...], "protected": [...], "overwritten": [...], "ignored": [{"field", "why"}, ...],
 "plain_text_field": "題目 id（給純文字時才有）", "message": "新增了 2026-11-02 的「三行日記」（#3）：填了 1 題"}
```

- `message`＝給人看的一句話（跟不加 `--json` 時印的那一行一樣）；SYNOX 之類的宿主直接把它顯示給使用者。

- `filled`＝這次寫進去的；`kept`＝`--merge=fill` 下原本就有寫、沒動的；`protected`＝`--author=ai` 下作者寫過、沒動的；`overwritten`＝原本有答案、這次換掉的（`--overwrite` 點名的，或 `--merge=fields` 下本來就會換的）。
- `ignored`：不是這個題組的題目、對不上選項的答案，各寫一句為什麼。空的答案直接略過、不列。
- 寫入前，距離上一份自動備份超過六小時就先備份一次資料庫（跟 app 啟動時同一套）。

```bash
echo '{"answers": {"fact": "今天下雨"}}' | python -m backend.cli entry put --date=2026-11-02 --template=three-lines --merge=fill --json
python -m backend.cli entry put --date=2026-11-02 --template=jot --input=answers.json --json
python -m backend.cli entry put --date=2026-11-02 --template=capsule --merge=fill --overwrite=verse1 --input=answers.json --json
python -m backend.cli entry put --date=today --template=day-review --author=ai --source-text=original.txt --input=answers.json --json
echo 今天很好 | python -m backend.cli entry put --date=today --template=jot --merge=fill --json
```

（第一、五行是 bash／Git Bash 的寫法。最後一行是純文字：記成 `jot` 的新的一則。Windows 的 cmd、PowerShell 管線送出去的不是 UTF-8，用 `--input=檔案`。第三行是工作單的情境：
`capsule` 的「有哪一段經文用得上」只填了出處，要補上原文——只換那一題，其他題一字不動，然後 `export` 重新畫。）

### `entry show`

讀出一篇，或某一天的全部。

| 參數 | 說明 |
|---|---|
| `--id=<編號>` | 這一篇（`put`、`list` 回的 `id`）；有給就不看 `--date` |
| `--date=YYYY-MM-DD` | 那一天的全部（也收 `today`／`yesterday`） |
| `--template=<題組>` | 搭 `--date`：只看那個題組的那一篇 |

回傳 `{"date", "count", "entries": [{…entry 的摘要…, "answers": {...}, "closing": "", "provenance": {...}, "text": "整篇的純文字"}]}`。
`provenance` 是 `{"fields": {"<題目 id>": {"author": "ai", "at", "source"}}, "source_text"}`，作者自己寫的全部是 `{}`。
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

回傳 `{"entries": [{"id", "date", "template", "template_name", "title", "layout", "theme", "chars", "ai_fields", "updated_at"}, ...]}`。

```bash
python -m backend.cli entry list --limit=7 --json
```

### `export`

把一篇輸出成一頁 **HTML**（瀏覽器打開、可以列印成 PDF）和（或）一張 **卡片 SVG**。**每一次都照現在存的內容重新畫**：
用 `--overwrite` 改過幾題之後再叫一次就是新的，沒有「已經寫過」這種擋法。

| 參數 | 說明 |
|---|---|
| `--id=<編號>` | 這一篇 |
| `--date=YYYY-MM-DD` | 搭 `--template` 指定那一篇（也收 `today`／`yesterday`） |
| `--template=<題組>` | 題組 id |
| `--format=both\|html\|card` | 預設 `both` |
| `--layout=<版型>` | 這一次用哪個版型（`layouts` 看全部）；不改那一篇自己的設定。不存在的版型回錯 |
| `--theme=<紙張顏色>` | `letterpress`、`notebook`、`linen`、`dawn`、`midnight`；同樣只影響這一次 |
| `--width=<px>` | 卡片寬度，480–2400，預設 1080 |
| `--paper=ruled\|grid\|plain\|dotted` | 卡片的紙，預設跟版型 |
| `--out-dir=<資料夾>` | 輸出到這裡；預設是設定 `export_dir`，沒設就是日記資料夾的 `exports/` |

回傳 `{"entry": {...}, "layout", "theme", "html": "<完整路徑>", "svg": "<完整路徑>", "width", "height", "paper"}`
（只要 HTML 就沒有 svg 那幾個）。檔名是 `<日期>-<題組>-<編號>.html／.svg`，同一篇再匯出會蓋掉上一次的。
要 PNG：用瀏覽器開那個 SVG、視窗 `width`×`height` 截圖（SKILL.md 有指令）。

```bash
python -m backend.cli export --date=2026-11-02 --template=three-lines --format=card --json
```

### `settings`

看、改設定。跟網頁的「管理顏色」與輸出選項存的是**同一份** `preferences.json`，網頁上能調的每一項這裡都能調，反過來也一樣。
不帶子指令＝列出全部：每一項的 `key`、`value`（現在）、`default`、`what`（是什麼）、`how`（怎麼寫）。

回傳 `{"settings": [{"key", "value", "default", "what", "how"}, ...], "file": "<preferences.json 的路徑>"}`。

| key | 是什麼 | 怎麼寫 |
|---|---|---|
| `palette` | 編輯器上方那一排墨水色 | JSON 清單 `[{"hex": "#22252a", "name": "墨黑"}, …]`；`default`＝內建六色；不能是空的 |
| `template_id` | 預設題組：開編輯器、新的一天先用哪一個；`templates suggest` 沒線索時也回它 | 題組 id，要存在；空字串＝不指定 |
| `layout` | 預設輸出版型 | 版型 id，要存在；空字串＝不指定 |
| `theme` | 預設紙張顏色 | `letterpress`、`notebook`、`linen`、`dawn`、`midnight`；空字串＝不指定 |
| `card_paper` | 卡片的紙 | `ruled`、`grid`、`plain`、`dotted`；空字串＝跟版型 |
| `card_width` | 卡片寬度（px） | 480–2400 |
| `image_style` | 繪圖 prompt 的風格 | 一個英文字，例 `watercolor` |
| `use_as_default` | 新日記要不要套用上面的預設 | `true`／`false` |
| `day_start_hour` | 幾點以前「今天」還算昨天 | 0–23；0＝午夜換日 |
| `export_dir` | `export` 寫到哪個資料夾 | 路徑；空字串＝日記資料夾的 `exports/` |
| `preset` | 這份安裝用的起始題組（`setup init` 寫的） | `generic`、`devotional`；空字串＝沒跑過 |
| `suggest_faith` | `templates suggest` 怎麼對待信仰類題組 | `auto`、`prefer`、`never` |

```bash
python -m backend.cli settings --json
```

### `settings get`

| 參數 | 說明 |
|---|---|
| `--key=<設定名>` | 必填 |

回傳那一項 `{"key", "value", "default", "what", "how"}`；沒有這個設定 → `沒有這個設定：<key>（有：…）`。

```bash
python -m backend.cli settings get --key=day_start_hour --json
```

### `settings set`

| 參數 | 說明 |
|---|---|
| `--key=<設定名>` | 必填 |
| `--value=<值>` | 必填。字、數字、`true`／`false`，或 JSON（`palette` 這種清單）；`default`＝放回內建的值 |

值不合（範圍外、不存在的題組／版型、不是那幾個字之一）→ 一句話說為什麼，**什麼都不改**。
回傳那一項加 `"saved": true` 與整份 `"settings"`。

```bash
python -m backend.cli settings set --key=day_start_hour --value=4 --json
python -m backend.cli settings set --key=template_id --value=three-lines --json
python -m backend.cli settings set --key=palette --value=default --json
```

### `setup`

這份安裝的狀態：資料夾在哪、用了哪個起始組合、幾個題組、幾篇日記、整份設定。

回傳 `{"data_dir", "preset", "presets": {名: 說明}, "templates": N, "template_ids": [...], "entries": N, "preferences": {...}}`。

```bash
python -m backend.cli setup --json
```

### `setup init`

替一個（通常是新的）日記資料夾挑**起始題組**。沒跑過 `init` 的安裝＝全部內建題組，跟以前一模一樣。

| 參數 | 說明 |
|---|---|
| `--preset=generic\|devotional` | 必填。組合是資料（`content/presets.json`）：`generic`＝一般、不談信仰：`jot`、`three-lines`、`gratitude`、`day-review`（三段回看）、`feelings`、`hard-day`、`worry-sort`、`week-review`，設定 `suggest_faith=never`、`template_id=three-lines`；`devotional`＝全部內建題組，設定 `suggest_faith=prefer` |

- **只加不刪**：已經有的題組一個都不動；沒選的內建題組記成「處理過了」，下次啟動不會自己跑出來；之後想要 → `templates restore --id=`。
- 組合裡的設定只寫還在預設值的欄位（你改過的不動）；`preset` 記下來。
- 在已經裝好全部題組的資料夾上跑 `devotional`，只會寫設定。

回傳 `{"preset", "label", "templates_added": [...], "templates_now": [...], "already_had": [...], "settings": {...}}`。

```bash
python -m backend.cli setup init --preset=generic --json
python -m backend.cli setup init --preset=devotional --data-dir=D:\journal --json
```

## 隱私：輸出就是日記

- `entry show` 的輸出、`export` 產生的檔案，**就是日記本身**。呼叫端不要把 stdout 留在 log、追蹤檔、工作紀錄裡；
  要記就只記指令名、日期、題組、字數、編號、結束碼。
- `entry list` 刻意不印內容，可以放心列。
- 錯誤訊息不含日記內容（最多帶回你給的日期、題組 id、檔名、設定名）。
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
  **這一版新增、等那邊接的**：`templates suggest`、`templates categories`、`templates --reflection=`（Telegram 上照分類挑）、
  `entry put --overwrite=`（改幾題再重畫）、`entry put --author=ai`（AI 代寫，標明、附原文）、`settings`。
- 找不到這個專案、沒有 `.venv`、或這個版本還沒有 `backend/cli.py`，它會先擋下來、回一句話，不會叫。

SYNOX 的接法是同一支命令列、不同的宣告：[../synox-pack/README.md](../synox-pack/README.md)。

## 內建題組升級時的備份

新版改了內建題組時，`content/superseded.json` 記著每一個舊版的指紋。每一次啟動（app 或命令列）：

- 資料夾裡那一份**還是某個舊版、一字沒改** → 換成新版；
- 改過的 → 不動；刪掉的 → 不會回來；
- **日記本身（資料庫裡的每一篇與歷史版本）完全不碰**——題組是資料庫旁邊的檔案；
- 真的要換之前，先備份資料庫（`backups/journal-<時間>-before-template-upgrade.sqlite3`），
  被換掉的舊檔留在 `backups/defaults-<時間>-before-upgrade/`。**備份做不出來就不換**（舊的題組照樣能用）。
