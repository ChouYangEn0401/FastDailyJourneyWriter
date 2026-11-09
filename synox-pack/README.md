# synox-pack/ — 把每日日記接進 SYNOX

這個資料夾是一個 SYNOX **skill pack**（`kind: cli`，格式見 SYNOX 的 `docs/pack-format.md`）。
它不含任何邏輯：只是一份宣告，說「`python -m backend.cli` 有哪些子指令、每一個收什麼、會不會寫入」，
加上給 AI 看的 `SKILL.md`。SYNOX 把每個 command 變成指令樹的一個葉子（Telegram 指令＋AI 的工具 `diary__<name>`），
經它自己的 JobRunner 叫這支命令列（argv 陣列、逾時、不開視窗），只讀最後一行 JSON 信封。

## 在 Telegram 上怎麼用

| 打 | 做什麼 |
|---|---|
| `/diary 今天很好` | 記成今天「隨手記」的新的一則（接在之前的後面，不蓋掉） |
| `/diary_put yesterday jot 昨天忘了記的事` | 別天的隨手記；第二格換成別的題組 id＝寫進那個題組的第一題 |
| `/diary_show today` | 今天寫了什麼 |
| `/diary_list` | 最近寫過哪幾天 |
| `/diary_templates`、`/diary_template three-lines` | 有哪些題組、一個題組有哪些題 |
| `/diary_export today jot` | 做成一頁 HTML ＋ 一張卡片 |
| `/diary_settings`、`/diary_settings_set day_start_hour 4` | 看、改設定 |

照位置填：前面幾格是必填欄位，**最後一格吃掉剩下的字**；也可以寫 `key=value`。
限制（SYNOX 的規矩）：內容不能以 `-` 開頭（`- 買牛奶` 會被拒，寫成 `買牛奶`）；照位置填時換行會變成空格（多行要給 AI，或寫 JSON）。
想一次填好幾題、或要 AI 幫你整理，直接跟 AI 說（它走 `diary__put`／`diary__put_ai` 的 JSON）。

## 安裝

1. 這個 repo 要先照 README 建好 `.venv`、`pip install -r requirements.txt`（命令列要 pydantic、jinja2）。
2. **指過來（推薦）**：SYNOX 的 `config.json` 加
   ```json
   "packs": { "dirs": ["C:/Users/<你>/Documents/FastDailyJourneyWriter/synox-pack"] }
   ```
   （`packs.dirs` 收「一個 pack 資料夾」或「放很多 pack 的資料夾」）。pack 必須仍然放在這個 repo 裡（`cwd` 是 `..`、
   `cli.python: "venv"` 找的是 `../.venv`）；不要只把 `synox-pack/` 複製出去。
3. 重開 bot；`python -m synox doctor --offline` 會列出載入結果。

## 佈位符：SYNOX 的 loader 要代入的值

| 佈位符 | 意思 |
|---|---|
| `{python}` | **這個 repo 的 venv** 的 Python（`cli.python: "venv"`＝`<repo>/.venv/Scripts/python.exe`，macOS／Linux 是 `.venv/bin/python`）。不是 SYNOX 自己的 Python：日記的相依套件裝在這裡。 |
| `{user_data_dir}` | 這個使用者的資料夾；日記放在它底下的 `diary/`（`--data-dir={user_data_dir}/diary`，等於 `JOURNAL_DATA_DIR`）。伺服器版每個人一個資料夾，個人版就是擁有者的。**永遠不要讓它指到這個 repo 的 `data/`。** |
| `{date}`、`{template}`、`{text}`、`{fields}`、`{author}`、`{key}`、`{value}` | command 的 `fields`，由使用者或 AI 填；值以 `-` 開頭一律拒絕（SYNOX 的規矩），其他都寫成 `--旗標={值}` 一個 token。 |
| `{answers}`、`jot` 的 `{text}` | **走 stdin**，不走 argv（command 的 `"stdin"` 鍵，SYNOX 2026-11-10 起支援）：由 loader 以 UTF-8 寫進子程序的 stdin。內容可以是 JSON 物件（AI 用），也可以是一段純文字（人打字用：整段寫進題組的第一題，`jot`＝新的一則；見 `docs/cli.md`「寫入的內容怎麼給」）。 |

`cwd: ".."` 是 repo 根目錄（pack 資料夾的上一層）；`env.PYTHONIOENCODING=utf-8`；輸出一律 UTF-8。

## 指令與 effect

| command | 命令列 | effect |
|---|---|---|
| `jot`（預設） | `entry put --date=today --template=jot --merge=fill`（內容走 stdin） | WRITE |
| `templates`、`template`、`suggest`、`categories`、`show`、`list`、`settings` | `templates …`、`entry show`、`entry list`、`settings` | READ |
| `put`、`put_ai`、`export`、`settings_set` | `entry put --merge=fill [--author=ai]`、`export`、`settings set` | WRITE |
| `overwrite` | `entry put --merge=fill --overwrite=<ids> --author=<user\|ai>` | **DANGER**（會換掉已經寫過的答案；AI 一律送確認卡） |

`put_ai` 把 AI 整理的版本寫進去：每一題標「AI 整理」、附作者原文（JSON 的 `source_text` 必填，不收純文字），作者寫過的題目不動。
寫入的結果有 `message`（一句人話），SYNOX 直接顯示它。
細節與每個參數在這個 repo 的 `docs/cli.md`；AI 怎麼挑、怎麼填在 `SKILL.md`。

## 隱私

`show` 的輸出與 `export` 產生的檔案**就是日記本身**：SYNOX 這邊不要把子程序的輸出留在工作紀錄裡（ClawBot 的做法：每一次給一個暫存 log、讀完就刪）。
`list` 刻意不印內容。錯誤訊息不含日記內容。內容走 stdin，不會出現在程序清單的 argv。

## 測試

`python -m unittest tests.test_synox_pack`：pack.json 的每個 command 對得上真的子指令與旗標、每個 effect 都有寫、`SKILL.md` 提到每個工具；
旁邊有 SYNOX 的 checkout（`../SYNOX/src`，或環境變數 `SYNOX_SRC`）時，再用 SYNOX 自己的 `manifest.validate` 驗一次。
