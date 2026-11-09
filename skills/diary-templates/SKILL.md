---
name: diary-templates
description: 替作者把一天寫下的東西套進「每日日記」的題組（範本）、存進日記、再匯出成一頁 HTML 或一張卡片圖。作者說「用某某格式整理今天」「幫我挑一個範本」「把今天的日記做成圖」、或你要決定用哪一個題組之前，先讀這一份。內容：21 個題組各是什麼（結構、要不要反思、走哪些步驟）、什麼情況選哪一個、每一種題型怎麼填、填寫的原則、怎麼用命令列寫入、改幾題、以 AI 整理的版本寫入（標明、附原文）與匯出。
---

# 每日日記的題組：怎麼選、怎麼填、怎麼匯出

這個專案（FastDailyJourneyWriter）是一個寫日記的小工具。一篇日記＝**某一天**＋**一個題組**（一組問題）的答案。
題組是 `data/templates/*.json`（內建的原本在 `content/templates/`），每一個都有：

- `when`（什麼情況用它）、`minutes`（大概幾分鐘）、`moods`（適合的心情）、`tags`（標籤）——**挑題組看這幾個**
- `structure`（一段式／三段式／多段式）、`reflection`（只記錄／有反思／有信仰的反思／有禱告）、`flow`（走過哪些步驟，照順序）——**分類看這幾個**（下一節）
- 每一題的 `kind`（題型）、`options`（選項）、`pattern`（填空句）、`ai_hint`（**這一題怎麼填**）——**填寫看這幾個**

**最新、最準的是命令列給的**（作者可能改過、刪過、自己加過題組）：

```bash
python -m backend.cli templates --brief --json          # 全部題組：名稱、什麼時候用、幾分鐘、心情、標籤、分類
python -m backend.cli templates --id=capsule --json     # 一個題組的每一題（含 ai_hint、選項、填空有幾格）
python -m backend.cli templates suggest --text="作者寫的那段話" --json   # 替一段話排出最像的題組，附理由
python -m backend.cli templates categories --json       # 分類字彙表：每一種結構／層級／步驟各有哪些題組
```

## 分類：每個題組是哪一種寫法

作者說過：題組太多、每一個都要看過才知道選什麼。所以每個題組都標了三個 ASCII 欄位（Telegram 的按鈕也是照這幾個畫的）：

| 欄位 | 值 | 怎麼用 |
|---|---|---|
| `structure` | `one-part` 一段式／`three-part` 三段式／`n-part` 多段式 | 作者說「三段式的」就 `--structure=three-part` |
| `reflection` | `none` 只記錄 → `reflection` 有反思（不談信仰）→ `devotional` 有信仰的反思 → `prayer` 有禱告／代禱（階梯，後面的包含前面的） | 作者不談信仰 → `--reflection=none,reflection`；要靈修的 → `devotional,prayer` |
| `flow` | 步驟的順序：`events` 發生的事、`feelings` 感受、`scripture` 經文、`reflection` 反思、`prayer` 禱告、`gratitude` 感恩、`worries`、`work`、`decision`、`review`、`identity`、`checkin`、`confession`、`trust`、`people`、`quote`、`plan` | 「先記事、再經文、再反思」→ 看 `flow` 的順序；`--flow=scripture,prayer` 列出兩個步驟都有的 |

`templates suggest --text=…` 就是照這套做的：看字裡提到什麼（擔心、工作、感謝、經文…）、寫了多長，對上每個題組的 `flow`／`moods`／`tags`，回 `suggestions`（每一個附 `why`）、`signals`（看到的線索）、`categories`（字裡指向的層級與步驟）。
**不呼叫模型，規則在 `content/suggest.json`**。拿到結果：把前兩三個跟 `why` 用一句話講給作者、讓他選；信仰類的題組只在他提到信仰、或他自己選的時候用（設定 `suggest_faith`）。

下面這張表是內建的樣子，給你先有個概念。

## 內建的 21 個題組

**與神同行**

| id | 名稱 | 分鐘 | 什麼時候用 | 適合的心情 | 標籤 | 版型 |
|---|---|---|---|---|---|---|
| `quick-checkin` | 快速打卡 | 2 | 很忙、只有兩分鐘，但不想讓靈修紀錄斷掉的日子。 | 忙碌、疲累、平穩 | 靈修、勾選為主、感恩、代禱、快速 | ledger |
| `three-part` | 三段式（反省・靈修・代禱） | 10 | 想照手寫本常見的分法，把反省、靈修、代禱分開寫的日子。 | 平靜、想整理 | 靈修、經文、感恩、代禱、書寫為主 | manuscript |
| `walk-with-jesus` | 同行日記（完整版） | 10 | 時間比較充裕、想把一整天在主面前逐項自省的日子。 | 平靜、想自省 | 靈修、勾選為主、自省、感恩、代禱 | ledger |
| `scripture-fill` | 填空式靈修 | 5 | 讀了經文卻不知道從哪裡寫起：句子寫好了，只要把空格填起來。 | 卡住、疲累、平靜 | 靈修、經文、填空 | letter |
| `free-bullets` | 星號隨筆 | 3 | 不想被題目綁住，想到什麼就記什麼，最後補上感恩與代禱。 | 隨意、零碎 | 靈修、條列、自由書寫、感恩、代禱 | postcard |
| `examen` | 省察 · 一天的回看 | 10 | 睡前，想把一天在主面前重看一遍的時候。 | 平靜、心有點亂、想沉澱 | 靈修、省察、認罪、感恩、睡前 | letter |
| `lament` | 哀歌 · 把痛苦帶到主面前 | 15 | 很難、很痛的日子：照詩篇哀歌的走法，把痛苦帶到主面前。 | 痛苦、難過、憤怒、無力、麻木 | 靈修、哀歌、詩篇、難處、交託 | letter |

**心情與難處**

| id | 名稱 | 分鐘 | 什麼時候用 | 適合的心情 | 標籤 | 版型 |
|---|---|---|---|---|---|---|
| `hard-day` | 難熬的一天 | 10 | 今天很不好過：先分清楚事實和自己的解讀，再找一件做得到的小事。 | 難過、焦慮、生氣、委屈、疲累 | 情緒、難處、事實與解讀、不談信仰也可以 | letter |
| `feelings` | 情緒盤點 | 5 | 說不出現在是什麼心情，想先替情緒找到名字。 | 說不上來、煩躁、麻木、混亂 | 情緒、勾選為主、自我照顧、不談信仰也可以 | ledger |
| `worry-sort` | 擔心的事，分一分 | 10 | 腦子停不下來、擔心一件接一件的時候。 | 焦慮、害怕、停不下來 | 情緒、焦慮、分類、不談信仰也可以 | ledger |

**成為什麼樣的人**

| id | 名稱 | 分鐘 | 什麼時候用 | 適合的心情 | 標籤 | 版型 |
|---|---|---|---|---|---|---|
| `day-review` | 三段回看 · 事情・感受・學到 | 8 | 想把一天分三段看清楚：發生了什麼、我怎麼了、我帶走什麼。不談信仰也完全成立。 | 平靜、想整理、有點亂 | 反思、三段式、每天、不談信仰也可以 | letter |
| `become` | 我想成為什麼樣的人 | 10 | 想看看今天的自己，離想成為的那個人近了還是遠了。 | 平靜、想成長、想調整 | 品格、成長、反思 | letter |
| `peaks-valleys` | 高峰與低谷 · 得意時謙卑，難處中敬畏 | 20 | 一天裡有特別開心和特別難受的事：在高處學謙卑、在低處學敬畏。 | 起伏很大、得意、失落 | 品格、謙卑、信靠、信仰、深度反思 | ledger |
| `capsule` | 反思膠囊 · 今天的三件事 | 15 | 有一件事想想到底：發生什麼、學到什麼、經文和有智慧的人各怎麼說。 | 平靜、想沉澱、有收穫 | 反思、經文、智慧、信仰、深度反思 | letter |
| `month-review` | 月回顧 · 這個月我變成了誰 | 20 | 月底或月初，一個月寫一次：看自己有沒有往想成為的人靠近。 | 回顧、平靜 | 回顧、每月、品格、成長 | ledger |

**工作與創業**

| id | 名稱 | 分鐘 | 什麼時候用 | 適合的心情 | 標籤 | 版型 |
|---|---|---|---|---|---|---|
| `founder-daily` | 創業日記 · 每天 | 10 | 在做自己的事業或專案的日子：今天推進了什麼、在驗證什麼、卡在哪裡。 | 忙碌、焦慮、有衝勁 | 工作、創業、專案、不談信仰也可以 | ledger |
| `decision-log` | 決策紀錄 | 15 | 要做重要決定的那天：記下當時知道什麼、預期什麼，過一陣子回來對照。 | 猶豫、有壓力、冷靜 | 工作、決策、回頭對照、不談信仰也可以 | ledger |
| `week-review` | 週回顧 | 15 | 週末花十五分鐘回顧這一週，排好下週只做的三件事。 | 回顧、平靜、疲累 | 工作、回顧、每週、計畫 | ledger |

**簡單記一下**

| id | 名稱 | 分鐘 | 什麼時候用 | 適合的心情 | 標籤 | 版型 |
|---|---|---|---|---|---|---|
| `jot` | 隨手記 · 一則一則 | 2 | 不想選題目，想到什麼就一則一則記下來的時候（Telegram 上的 /diary 就是存在這一組）。 | 任何心情、零碎、忙碌 | 自由書寫、條列、經文可選、Telegram | letter |
| `three-lines` | 三行日記 | 1 | 只有一分鐘：一件事、一個感覺、一件謝謝。最不容易斷掉的那一種。 | 任何心情、很忙、很累 | 簡短、每天、感恩、不談信仰也可以 | postcard |
| `gratitude` | 感恩清單 | 3 | 想把注意力放回好的事情上：三件小事，加上一個人。 | 平靜、低落時也適合 | 感恩、簡短、不談信仰也可以 | letter |

## 挑哪一個

1. **作者指定了就用指定的**（名稱、id、或「三行那個」這種說法都算；對不上就列兩三個最像的給作者選，不要猜）。
2. 沒指定：先看那天寫了什麼，**照內容的形狀挑**，不是照你覺得作者該寫什麼：

| 那天寫的是 | 先考慮 |
|---|---|
| 很短、零碎、只有幾句 | `three-lines`（一件事一個感覺一件謝謝）、`free-bullets`（一則一則＋感恩代禱） |
| 一直在擔心、停不下來 | `worry-sort` |
| 很難過、很受傷、事情很糟 | `hard-day`（不談信仰也可以）；作者在向神哭訴、有詩篇那種語氣 → `lament` |
| 說不出是什麼心情 | `feelings` |
| 有一件事想想到底、有學到東西 | `capsule`（一件事一塊，最多三件；有經文那兩題）；不談信仰、想分三段看 → `day-review` |
| 同一天有很開心和很難受的事 | `peaks-valleys` |
| 讀經、禱告、靈修的內容 | 有經文和應用 → `three-part`；很忙只想打卡 → `quick-checkin`；睡前回看 → `examen`；想填空 → `scripture-fill` |
| 在想自己要成為怎樣的人 | `become` |
| 工作、專案、創業 | `founder-daily`；在做一個重要決定 → `decision-log` |
| 一整週或一整個月的回顧 | `week-review`、`month-review` |
| 都不太像 | 保持 `jot`（原文照存，不套範本），或問作者 |

3. 寫的東西跟題組的題目對不太上（例如只寫了一件事卻選 `capsule`）是可以的——**空的題目輸出時不會出現**，
   不要為了填滿而編內容。

## 每一種題型怎麼填（`entry put` 的 answers）

| `kind` | 給什麼 | 例 |
|---|---|---|
| `text` | 一段字（純文字，換行會保留） | `"今天跟同事吵了一架…"` |
| `short_text` | 一句話 | `"準時下班"` |
| `list` | 字串陣列，一項一個（也可以給一段字，一行一項） | `["家人平安", "雨停了"]` |
| `choice`／`scale` | **一個選項**的 id 或文字（要完全對得上 `options`） | `"yes"` 或 `"有"` |
| `multi_choice` | 選項 id 或文字的陣列 | `["焦慮", "疲累"]` |
| `fill` | 字串陣列，**格數＝`pattern` 裡 `{}` 的個數**（`templates --id=` 會給 `blanks`），照順序 | `["腓立比書 4:6", "應當一無掛慮"]` |

對不上選項的、不是這個題組的題目會被略過，回傳的 `ignored` 會寫出哪一題、為什麼。

## 填寫的原則（每一題的 `ai_hint` 是這幾條的細節）

- **用作者自己的話。** 可以整理、拿掉贅字，不要改寫成你的句子，不要加作者沒寫的情節。
- **不替作者下結論、不替作者認罪、不替作者打分數。** 「學到什麼」「主在哪裡」「我領受赦免了嗎」這種題目，作者沒說就**留空**。
- **沒提到的就留空。** 空的題目輸出時本來就不會出現，不是失敗。勾選題沒把握就不勾。
- **經文只照抄作者寫過的**（或那天日記裡已經記下、程式從和合本查出來的那幾處）。**不要自己補經文，更不要憑記憶寫經文原文。**
- 誠實的選項（「我還在痛」「在裝有把握」「其實不想做」「我不確定，但我還在這裡」）只照作者承認的選。
- 「事後回來寫」的題目（`decision-log` 的 `later` 那一段）當天一律留空。
- `jot` 的「從經文來的回應（AI 整理）」不是作者寫的話，**不要搬到別的題組裡當成作者的答案**。
- 不確定作者要哪一種寫法，先問；寫錯地方作者之後找不到，比多問一句貴。

## 替作者潤飾、代寫：一律 `--author=ai`

作者要你「幫我整理成日記」「潤飾一下再寫進去」的時候，可以寫——但**你整理的版本永遠跟作者的原文一起存、分開標**：

- 用 `entry put --author=ai`，JSON 裡放 `source_text`（作者的原話，一字不改；或 `--source-text=檔案`），每一題各自對應的原文放 `sources`。
  沒附原文程式會拒絕。
- 寫進去的每一題會標「（AI 整理）」、底下印「作者原文」，整篇的原文在最後一段——HTML、卡片、`entry show` 的 `text` 都看得到。**不要用 `--author=user` 假裝是作者寫的。**
- 作者自己寫過的題目不會被換（回在 `protected`）；他要你改，才 `--overwrite=` 點名那一兩題。`--merge=append` 不能跟 `--author=ai` 搭。
- 潤飾＝整理、斷句、拿掉贅字；**不是**加情節、加感受、加結論。看到 `protected` 就告訴作者哪幾題他已經寫了、沒動。

## 改幾題：`--overwrite=`

作者說「經文那題補上原文」「第二件事寫錯了」：`entry show` 找出題目 id → `entry put --merge=fill --overwrite=<id,id>`（只換點名的，其他一字不動）→ `export` 重新畫。
`--overwrite=all` 是「這次給的每一題都換」，只在作者明說整篇重寫時用。

## 命令列

完整參考（每個參數、回傳的欄位、錯誤）在 **[docs/cli.md](../../docs/cli.md)**；每個指令加 `-h` 也有說明和例子。
在這個專案的資料夾裡跑（Windows：`.venv\Scripts\python.exe -m backend.cli …`）。加 `--json` 只印最後一行信封：
`{"ok": true, "result": {…}}`，失敗 `{"ok": false, "error": "一句人話"}`、結束碼 1。輸出一律是 UTF-8。

```bash
# 題組：全部（--brief 不列題目；--structure= --reflection= --flow= --tag= 篩選）、一個題組的每一題
python -m backend.cli templates --brief --json
python -m backend.cli templates --brief --reflection=none,reflection --json
python -m backend.cli templates --id=three-lines --json
python -m backend.cli templates suggest --text="今天跟客戶開會被罵，很擔心案子" --json   # 替一段話挑題組，附理由
python -m backend.cli templates categories --json                                         # 分類字彙表
python -m backend.cli templates restore --id=capsule --json                               # 把一個內建題組放回來

# 寫入：一天、一個題組＝一篇。同一天同一個題組再寫一次是「更新那一篇」。--date 也收 today／yesterday
echo '{"answers": {"fact": "今天…", "feel": "有點累", "overall": "普通"}}' \
  | python -m backend.cli entry put --date=2026-11-02 --template=three-lines --merge=fill --json
python -m backend.cli entry put --date=2026-11-02 --template=three-lines --merge=fill --input=answers.json --json
# 只換點名的那一兩題（其他一字不動），然後 export 重新畫
python -m backend.cli entry put --date=2026-11-02 --template=capsule --merge=fill --overwrite=a_verse --input=answers.json --json
# AI 整理的版本：標「AI 整理」、附作者原文（source_text 必填）、不蓋作者寫的
python -m backend.cli entry put --date=today --template=day-review --author=ai --source-text=original.txt --input=answers.json --json

# 讀出：那一天的全部（每一篇有 text＝純文字、answers＝原始答案）；或一篇
python -m backend.cli entry show --date=2026-11-02 --json
python -m backend.cli entry show --id=12 --json

# 最近寫過的（只有日期、題組、字數、編號，不印內容）
python -m backend.cli entry list --limit=7 --json

# 匯出：一頁 HTML ＋ 一張卡片 SVG，寫到 data/exports/（--out-dir= 可以換）
python -m backend.cli export --date=2026-11-02 --template=three-lines --json
#   --format=html|card|both   --layout=letter|ledger|manuscript|postcard   --theme=letterpress|notebook|linen|dawn|midnight
python -m backend.cli layouts --json      # 版型清單

# 設定（跟網頁同一份 preferences.json）：全部、看一個、改一個；setup 看這份安裝的狀態、init 替新資料夾挑起始題組
python -m backend.cli settings --json
python -m backend.cli settings get --key=day_start_hour --json
python -m backend.cli settings set --key=day_start_hour --value=4 --json      # 四點以前「今天」算昨天
python -m backend.cli setup --json
python -m backend.cli setup init --preset=generic --json                       # generic＝不談信仰的八個；devotional＝全部
```

`entry put` 的內容（stdin，或 `--input=` 一個 UTF-8 檔案）：`{"answers": {題目 id: 答案}, "title": "", "closing": "", "theme": "", "layout": "", "source_text": "", "sources": {}}`。
Windows 的 cmd／PowerShell 管線送出去的不是 UTF-8（中文會壞）：在那裡用 `--input=檔案`。

- `--merge=fields`（預設）：給了的題目換成新的，沒給的不動。
- `--merge=append`：清單接在後面、文字接在空一行之後（同一天又記了幾則）。
- `--merge=fill`：**只填空著的題目**，已經有寫的不動、回在 `kept`——替作者整理時用這個，不會蓋掉作者自己寫的。
- `--overwrite=<題目 id,…>`：點名可以換掉的題目（回在 `overwritten`）；`all`＝這次給的每一題。
- `--author=ai`：AI 整理的版本（上面那一節）；`--source-text=檔案`＝作者原文。
- `--format=plain`（預設）：文字是純文字；`--format=html`：文字是編輯器的 HTML（只收 `<b> <i> <u> <s> <br> <span style="color">`）。

寫入跟在編輯器裡寫一樣：會清理 HTML、留歷史版本（編輯器標題旁的「歷史」救得回來），每六小時留一份資料庫備份。

## 匯出成圖片

`export` 給的是 **HTML 頁面**（瀏覽器打開、可列印成 PDF）和 **卡片 SVG**（`width`×`height` 在回傳裡）。
要 PNG 就用本機瀏覽器開那個 SVG 截圖，視窗大小＝`width`×`height`，例如：

```bash
msedge --headless=new --disable-gpu --hide-scrollbars --user-data-dir=<暫存資料夾> \
       --window-size=1080,<height> --screenshot=<輸出.png> file:///<那個 .svg 的完整路徑>
```

（`data/exports/` 底下的檔案都是作者自己的日記，用完不要搬到別的地方、不要上傳。）

## 隱私

日記是最私人的東西：

- 內容不要寫進任何 log、追蹤檔、commit、issue；要記就只記日期、題組、字數、編號。
- 這個 repo 永遠不放任何人的日記（`data/` 整個被 gitignore；測試一律用編出來的內容）。
- 整理的時候只用作者給你的那一天，不要順手去讀別的日子。
