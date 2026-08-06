# 想幫忙的話

歡迎。這個專案最需要的貢獻不是程式碼，是**題組**——好的問題比好的程式難寫。

---

## 最歡迎的三種貢獻

### 1. 新的題組（最歡迎）

一個題組就是一個 JSON 檔，不用寫 Python。

1. 在程式裡按「＋ 新增」做一個，調到你自己會想用為止
2. 從 `data/templates/` 把那個 JSON 複製出來
3. 放進 `content/templates/`，開 PR

格式、七種題目型態、每個鍵的意思都在 **[docs/templates.md](docs/templates.md)**。

PR 裡請順便說一句：**這個題組是給誰、在什麼情況下用的。**
題組的價值在於問對問題，所以這句話比 JSON 本身更重要。

### 2. 新的版型

一個 Jinja2 模板 + 一個 JSON。最快的做法是複製 `content/layouts/letter.html.j2` 改。
唯一一條硬規定：**文字一律用 `{{ line | runs }}` 輸出**，那是保留使用者選的顏色的地方。

### 3. 修 bug

尤其是**任何會弄丟使用者文字的狀況**。那是這個專案的第一優先，
收到這類回報會排在所有功能前面。

---

## 開發環境

需要 Python 3.11 以上，其他什麼都不用裝。

```bash
git clone https://github.com/ChouYangEn0401/FastDailyJourneyWriter.git
cd FastDailyJourneyWriter
python3.11 -m venv .venv          # Windows: py -3.11 -m venv .venv
source .venv/bin/activate         # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

開發時建議把資料指到別的地方，不要動到自己真正的日記：

```bash
JOURNAL_DATA_DIR=/tmp/journal-dev python run.py
```

---

## 兩條規矩

### 一、絕對不要提交任何真實的日記內容

這是唯一沒有商量餘地的一條。

- `.gitignore` 已經擋掉所有 `*.png` / `*.jpg` / `*.heic`，**唯一的例外是 `docs/images/`**
- 要往 `docs/images/` 加圖之前，請先確認裡面**沒有任何真實內容**
  （現有的圖全部是為了說明編出來的）
- `data/` 整個資料夾都被擋掉了，包含 SQLite、匯出檔、備份

送 PR 前跑一次 `git status`，確認沒有夾帶東西進來。

### 二、貢獻的授權

送 PR 就表示你同意：

1. 你的貢獻以 **AGPL-3.0** 釋出，跟專案其他部分一樣；
2. 你另外授權維護者，**得以其他授權條款（含商業／閉源授權）散布你的貢獻**。

第 2 點的原因：這個專案未來可能會在 App Store / Google Play 上架，
而那些平台的條款跟 AGPL 有已知的衝突。有了這個授權，
維護者才能同時**維持 repo 永久開源**，又能合法上架。
你的貢獻不會因此變成閉源——AGPL 那份永遠在這裡。

如果你不同意第 2 點，還是可以貢獻**題組 JSON 與文件**，
那些不影響上架；直接在 PR 裡說一聲就好。

---

## 風格

沒有 linter 強制，但請跟著現有的程式碼走：

- 註解寫**為什麼**，不寫在做什麼
- 使用者看得到的文字用繁體中文；程式碼、註解、commit 訊息用英文
- 前端沒有 build 步驟，也請不要引入——`web/` 就是三個檔案，能直接開來看
- 不加相依套件，除非真的沒有別的辦法
