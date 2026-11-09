# 改了什麼

新的在上面。日期是做完的那天；「分支」是還沒合進 `master-init` 時的所在。

## 2026-11-09 · 直接打字就能記、SYNOX pack 可以實際用（分支 `feat/synox-pack-plain-text`）

來自工作單 `_inbox/20261110-150500-synox-put-plain-text.md`（Telegram 上 `/diary_put … answers=今天很好` 回「stdin 不是 JSON」）。

- **`entry put` 收純文字**：內容不是 `{` 開頭就當作者自己的話，整段寫進題組的**第一個文字題**（`jot`＝新的一則，接在後面、不管 `--merge`）；
  不拆成好幾題；`--author=ai` 不收純文字。回傳多 `plain_text_field`。JSON 信封的用法完全不變。
- **信封多 `result.message`**：跟不加 `--json` 時印的那段文字一樣（寫入一句話、`entry show` 整篇…），SYNOX 直接顯示它，不再把結果攤平成 25 行截斷的 key=value。
  `templates --id=` 的文字改成一題一行（題目、id、題型、選項）。
- **SYNOX pack 0.2.0**：新指令 `jot`（預設）——`/diary 今天很好` 記成今天隨手記的一則；`put` 的 `answers` 可以直接打字；README 改寫成「怎麼用」＋用 `packs.dirs` 安裝；SKILL.md 加 `diary__jot`。

## 2026-11-09 · 題組分類、改幾題、AI 代寫標明、每個設定都有命令列、起始組合、SYNOX pack（分支 `feat/synox-pack-and-inbox`）

來自三張工作單（`_inbox/`：template-taxonomy、allow-overwrite-answer、ai-diary-write）與擁有者的要求「把每一個欄位的設定的 CLI 都設計好」、讓別人也能用、包成 SYNOX skill。

- **題組分類**：每個題組多了 `structure`（一段式／三段式／多段式）、`reflection`（只記錄／有反思／有信仰的反思／有禱告）、`flow`（走過哪些步驟、照順序）三個 ASCII 欄位，model 驗字彙表。
  `templates --brief` 回這三個欄位；`--structure=`、`--reflection=`、`--flow=`、`--tag=` 篩選；`templates categories` 給字彙表（Telegram 畫按鈕用）；
  `templates suggest --text=…` 照規則（`content/suggest.json`，不呼叫模型）替一段話排出最像的題組，每一分都有一句理由。新題組 `day-review`（不談信仰的三段回看）。內建 21 個。
- **改幾題**：`entry put --overwrite=<題目 id,…>|all` 只換點名的題目，其他一字不動（回在 `overwritten`）；`export` 本來就照現在存的內容重畫。
- **AI 代寫、標明**：`entry put --author=ai` 一定要附作者原文（`--source-text=` 或 JSON 的 `source_text`／`sources`），寫進去的題目記在新的 `provenance` 欄（資料庫多一欄，舊檔自動補），
  輸出時標「（AI 整理）」、印「作者原文」；作者寫過的題目不換（`protected`），`--merge=append` 不接受；作者再寫就把標記拿掉。
- **每個設定都有命令列**：`settings`／`settings get`／`settings set`，跟網頁同一份 `preferences.json`；新設定 `day_start_hour`（幾點換日；`--date=today|yesterday`）、`export_dir`、`preset`、`suggest_faith`。
- **給別人用**：`setup init --preset=generic|devotional`（組合是 `content/presets.json`；只加不刪）、`templates restore --id=` 把沒裝的拿回來、`setup` 看狀態。沒跑過 init 的安裝一切照舊。
- **SYNOX pack**：`synox-pack/`（`kind: cli`，每個 command 的 argv 樣板、effect、fields；`{python}`／`{user_data_dir}` 由 loader 代入；`entry put` 的內容走 stdin）。`tests/test_synox_pack.py` 對 SYNOX 的 `manifest.validate`。
- 修正：`export --layout=<不存在的>` 以前會默默退回預設版型，現在回錯。

## 2026-11-02 · 命令列、每個題組同一個結構（合併 `feat/clawbot-cli-templates`）

`python -m backend.cli`：`templates`、`layouts`、`entry put|show|list`、`export`，`--json` 信封；每個題組都有 `when`／`minutes`／`moods`／`tags`、每一題有 `ai_hint`；`docs/cli.md`、`skills/diary-templates/SKILL.md`。
