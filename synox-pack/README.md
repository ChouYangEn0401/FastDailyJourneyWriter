# synox-pack/ — 把每日日記接進 SYNOX

這個資料夾是一個 SYNOX **skill pack**（`kind: cli`，格式見 SYNOX 的 `docs/pack-format.md`）。
它不含任何邏輯：只是一份宣告，說「`python -m backend.cli` 有哪些子指令、每一個收什麼、會不會寫入」，
加上給 AI 看的 `SKILL.md`。SYNOX 把每個 command 變成指令樹的一個葉子（Telegram 指令＋AI 的工具 `diary__<name>`），
經它自己的 JobRunner 叫這支命令列（argv 陣列、逾時、不開視窗），只讀最後一行 JSON 信封。

## 安裝

1. 這個 repo 要先照 README 建好 `.venv`、`pip install -r requirements.txt`（命令列要 pydantic、jinja2）。
2. 把這個資料夾放進（或連結到）SYNOX 的 `packs/diary/`——pack 必須仍然放在這個 repo 裡（`cwd` 是 `..`）；
   要複製出去的話，複製整個 repo，不要只複製 `synox-pack/`。
3. `python -m synox doctor` 會列出載入結果。

## 佈位符：SYNOX 的 loader 要代入的值

| 佈位符 | 意思 |
|---|---|
| `{python}` | **這個 repo 的 venv** 的 Python（`cli.python: "venv"`＝`<repo>/.venv/Scripts/python.exe`，macOS／Linux 是 `.venv/bin/python`）。不是 SYNOX 自己的 Python：日記的相依套件裝在這裡。 |
| `{user_data_dir}` | 這個使用者的資料夾；日記放在它底下的 `diary/`（`--data-dir={user_data_dir}/diary`，等於 `JOURNAL_DATA_DIR`）。伺服器版每個人一個資料夾，個人版就是擁有者的。**永遠不要讓它指到這個 repo 的 `data/`。** |
| `{date}`、`{template}`、`{text}`、`{fields}`、`{author}`、`{key}`、`{value}` | command 的 `fields`，由使用者或 AI 填；值以 `-` 開頭一律拒絕（SYNOX 的規矩），其他都寫成 `--旗標={值}` 一個 token。 |
| `{answers}` | **走 stdin**，不走 argv：`entry put` 的內容是一個 JSON 物件（可能很長、含換行），由 loader 以 UTF-8 寫進子程序的 stdin（command 的 `"stdin"` 鍵）。SYNOX 的 pack 格式 v0 沒有 `stdin` 這個鍵——這是這個 pack 需要的擴充，loader 沒實作時 `put`／`put_ai`／`overwrite` 不能用，其他指令不受影響。 |

`cwd: ".."` 是 repo 根目錄（pack 資料夾的上一層）；`env.PYTHONIOENCODING=utf-8`；輸出一律 UTF-8。

## 指令與 effect

| command | 命令列 | effect |
|---|---|---|
| `templates`（預設）、`template`、`suggest`、`categories`、`show`、`list`、`settings` | `templates …`、`entry show`、`entry list`、`settings` | READ |
| `put`、`put_ai`、`export`、`settings_set` | `entry put --merge=fill [--author=ai]`、`export`、`settings set` | WRITE |
| `overwrite` | `entry put --merge=fill --overwrite=<ids> --author=<user\|ai>` | **DANGER**（會換掉已經寫過的答案；AI 一律送確認卡） |

`put_ai` 把 AI 整理的版本寫進去：每一題標「AI 整理」、附作者原文（JSON 的 `source_text` 必填），作者寫過的題目不動。
細節與每個參數在這個 repo 的 `docs/cli.md`；AI 怎麼挑、怎麼填在 `SKILL.md`。

## 隱私

`show` 的輸出與 `export` 產生的檔案**就是日記本身**：SYNOX 這邊不要把子程序的輸出留在工作紀錄裡（ClawBot 的做法：每一次給一個暫存 log、讀完就刪）。
`list` 刻意不印內容。錯誤訊息不含日記內容。

## 測試

`python -m unittest tests.test_synox_pack`：pack.json 的每個 command 對得上真的子指令與旗標、每個 effect 都有寫、`SKILL.md` 提到每個工具；
旁邊有 SYNOX 的 checkout（`../SYNOX/src`，或環境變數 `SYNOX_SRC`）時，再用 SYNOX 自己的 `manifest.validate` 驗一次。
