"""Command line for the journal: read the question sets, write and read an
entry, export it, change a setting — without starting the server.

    python -m backend.cli templates [--id=<id>] [--brief] [--structure=] [--reflection=] [--flow=] [--tag=]
    python -m backend.cli templates suggest --text="<what was written>" [--limit=5]
    python -m backend.cli templates categories
    python -m backend.cli templates restore --id=<id>
    python -m backend.cli layouts
    python -m backend.cli entry put --date=YYYY-MM-DD|today|yesterday --template=<id>
                                    [--merge=fields|append|fill] [--format=plain|html]
                                    [--overwrite=<field,...>|all] [--author=user|ai] [--source-text=<file>]
                                    [--input=payload.json]       (or the JSON on stdin)
    python -m backend.cli entry show (--id=N | --date=YYYY-MM-DD [--template=<id>])
    python -m backend.cli entry list [--limit=30]
    python -m backend.cli export (--id=N | --date=YYYY-MM-DD --template=<id>)
                                 [--format=both|html|card] [--layout=] [--theme=]
                                 [--width=1080] [--paper=] [--out-dir=]
    python -m backend.cli settings | settings get --key=<k> | settings set --key=<k> --value=<v>
    python -m backend.cli setup | setup init --preset=generic|devotional

The full reference, in plain Chinese, is docs/cli.md; ``-h`` after any
command shows its own help and an example.

Add ``--json`` for machine use: then the only thing printed is the envelope.
The envelope is always the last line, on success and on failure:

    {"ok": true, "result": {...}}            exit code 0
    {"ok": false, "error": "一句人話"}         exit code 1

It works on the same files as the app (``JOURNAL_DATA_DIR``, or
``--data-dir=``), installs the shipped defaults the way the app does on
start, and goes through the same sanitising and revision history — so an
entry written here is exactly an entry written in the editor, and a bad write
from here is undone the same way (歷史版本). Nothing here calls a model or the
network.

``entry put`` reads one JSON object from stdin (or from ``--input=<file>``,
because Windows PowerShell re-encodes what it pipes into a program)::

    {"answers": {"<field id>": <value>, ...}, "title": "", "closing": "",
     "theme": "", "layout": "", "source_text": "", "sources": {"<field id>": ""}}

Values follow the field kind (see docs/templates.md). To be forgiving with
assistants, a choice may be given by its label as well as its id, a list may
be one string with one item per line, and with ``--format=plain`` (the
default) text is plain text — escaped and given line breaks here — rather
than the editor's HTML.

``--merge`` decides what happens to a field that already has an answer:
``fields`` replaces it (fields not mentioned are always kept), ``append``
adds to it (list items after the existing ones, text after a blank line) and
``fill`` leaves it alone and reports it under ``kept``. ``--overwrite`` names
the fields that may be replaced anyway (or ``all``), and reports them under
``overwritten`` — the only way to change a question that already has an
answer without touching the rest of the entry.

``--author=ai`` is for an assistant writing a polished version of what the
author said: every field it fills is marked and rendered as 「AI 整理」 with the
author's original next to it (``--source-text=<file>`` or ``source_text`` /
``sources`` in the payload — required), a field the author already wrote is
never replaced unless named in ``--overwrite`` (reported under ``protected``),
and ``--merge=append`` is refused because it would mix the two voices.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

MERGES = ("fields", "append", "fill")
FORMATS = ("plain", "html")
EXPORTS = ("both", "html", "card")
PAPERS = ("ruled", "grid", "plain", "dotted")
AUTHORS = ("user", "ai")
PRESETS = ("generic", "devotional")
DAY_WORDS = {"today": 0, "今天": 0, "yesterday": 1, "昨天": 1}


class CliError(Exception):
    """Something the person running the command can fix; the message says how."""


#: argparse's own messages are English; the person reading them may not be.
_ARGPARSE_WORDS = (
    (r"the following arguments are required: (.+)", "少了必填的參數：{0}"),
    (r"unrecognized arguments: (.+)", "看不懂的參數：{0}"),
    (r"argument \{.*?\}: invalid choice: (.+?) \(choose from (.+)\)", "沒有這個指令：{0}（有：{1}）"),
    (r"argument (\S+): invalid int value: (.+)", "{0} 要是整數（收到：{1}）"),
    (r"argument (\S+): invalid choice: (.+?) \(choose from (.+)\)", "{0} 只能是 {2}（收到：{1}）"),
    (r"argument (\S+): expected one argument", "{0} 後面要接一個值（寫成 {0}=值）"),
    (r"argument (\S+): ignored explicit argument (.+)", "{0} 不接值（收到：{1}）"),
)


def _human(message: str) -> str:
    import re

    for pattern, words in _ARGPARSE_WORDS:
        m = re.fullmatch(pattern, message)
        if m:
            return words.format(*m.groups())
    return message


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:  # argparse would print usage and exit 2
        raise CliError(f"參數有誤：{_human(message)}（-h 看說明）")


#: One worked example per command, shown at the bottom of its ``-h``. The same
#: lines are in docs/cli.md; tests/test_cli.py keeps the two in step.
EXAMPLES = {
    "templates": "python -m backend.cli templates --brief --json\n"
                 "python -m backend.cli templates --brief --reflection=none,reflection --json\n"
                 "python -m backend.cli templates --id=three-lines --json",
    "templates suggest": "python -m backend.cli templates suggest --text=\"今天跟客戶開會被罵，很擔心案子\" --json",
    "templates categories": "python -m backend.cli templates categories --json",
    "templates restore": "python -m backend.cli templates restore --id=capsule --json",
    "layouts": "python -m backend.cli layouts --json",
    "entry put": "echo '{\"answers\": {\"fact\": \"今天下雨\"}}' | python -m backend.cli entry put "
                 "--date=2026-11-02 --template=three-lines --merge=fill --json\n"
                 "python -m backend.cli entry put --date=2026-11-02 --template=jot --input=answers.json --json\n"
                 "python -m backend.cli entry put --date=2026-11-02 --template=capsule --merge=fill --overwrite=verse1 "
                 "--input=answers.json --json\n"
                 "python -m backend.cli entry put --date=today --template=day-review --author=ai --source-text=original.txt "
                 "--input=answers.json --json",
    "entry show": "python -m backend.cli entry show --date=2026-11-02 --json\n"
                  "python -m backend.cli entry show --id=12 --json",
    "entry list": "python -m backend.cli entry list --limit=7 --json",
    "export": "python -m backend.cli export --date=2026-11-02 --template=three-lines --format=card --json",
    "settings": "python -m backend.cli settings --json",
    "settings get": "python -m backend.cli settings get --key=day_start_hour --json",
    "settings set": "python -m backend.cli settings set --key=day_start_hour --value=4 --json\n"
                    "python -m backend.cli settings set --key=template_id --value=three-lines --json\n"
                    "python -m backend.cli settings set --key=palette --value=default --json",
    "setup": "python -m backend.cli setup --json",
    "setup init": "python -m backend.cli setup init --preset=generic --json\n"
                  "python -m backend.cli setup init --preset=devotional --data-dir=D:\\journal --json",
}


def _sub(parent, name: str, key: str, summary: str, description: str, common) -> argparse.ArgumentParser:
    return parent.add_parser(
        name, parents=[common], help=summary, description=f"{summary}\n\n{description}",
        epilog="例：\n  " + EXAMPLES[key].replace("\n", "\n  "),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )


def _parser() -> argparse.ArgumentParser:
    # Accepted before or after the sub-command. SUPPRESS, because a sub-parser's
    # own default would otherwise overwrite a value given before it.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                        help="給程式用：只印一行 JSON 信封（成功 {\"ok\": true, \"result\": …}，失敗 {\"ok\": false, \"error\": …}）")
    common.add_argument("--data-dir", default=argparse.SUPPRESS,
                        help="日記資料夾（預設跟 app 一樣：JOURNAL_DATA_DIR，沒設就是專案裡的 data/）")

    p = _Parser(
        prog="python -m backend.cli", parents=[common],
        description="每日日記的命令列：不開伺服器，列題組、挑題組、寫入、讀出、匯出、改設定。\n"
                    "每個指令後面加 -h 看它自己的說明和例子；完整參考在 docs/cli.md。",
        epilog="例：\n  python -m backend.cli templates --brief\n  python -m backend.cli entry show --date=2026-11-02\n"
               "  python -m backend.cli templates suggest --text=\"今天很累但很感謝\"",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = p.add_subparsers(dest="command", parser_class=_Parser,
                           metavar="{templates,layouts,entry,export,settings,setup}")

    t = _sub(sub, "templates", "templates", "列出題組（範本）與每一題的結構；suggest 替一段文字挑題組",
             "題組＝一組問題。不帶參數列出全部；--id 看一個題組的每一題（題型、選項、填空格數、ai_hint＝這一題怎麼填）。\n"
             "每個題組都有分類：structure（一段式／三段式／多段式）、reflection（只記錄／有反思／有信仰的反思／有禱告）、\n"
             "flow（走過哪些步驟，照順序）。--structure、--reflection、--flow、--tag 可以篩選（逗號分開＝其中之一）。", common)
    t.add_argument("--id", help="只看這一個題組，例 --id=three-lines")
    t.add_argument("--brief", action="store_true", help="只列名稱、什麼時候用、幾分鐘、分類，不列題目")
    t.add_argument("--structure", default="", help="只列這種結構：one-part、three-part、n-part")
    t.add_argument("--reflection", default="", help="只列這種反思層級：none、reflection、devotional、prayer（逗號分開＝其中之一）")
    t.add_argument("--flow", default="", help="只列走過這些步驟的：events、scripture、reflection、prayer…（逗號分開＝都要有）")
    t.add_argument("--tag", default="", help="只列有這個標籤的（逗號分開＝其中之一）")
    tsub = t.add_subparsers(dest="action", parser_class=_Parser, metavar="{suggest,categories,restore}")
    sg = _sub(tsub, "suggest", "templates suggest", "替一段文字挑題組：照規則排序，說出為什麼",
              "不呼叫模型。看字裡提到什麼（擔心、工作、感謝、經文…）、寫了多長，對上每個題組的 flow、moods、tags，\n"
              "每一分都寫成一句 why。規則在 content/suggest.json（複製到 data/suggest.json 可以自己調）。\n"
              "字裡沒提到信仰時，信仰類題組照設定 suggest_faith 處理（auto＝放後面）。", common)
    sg.add_argument("--text", required=True, help="使用者寫的那段話（整段放在一個參數裡）")
    sg.add_argument("--limit", type=int, default=5, help="最多幾個建議（1–20，預設 5）")
    _sub(tsub, "categories", "templates categories", "分類的字彙表：每一種結構、反思層級、步驟、標籤各有哪些題組",
         "給挑題組的畫面用（Telegram 的按鈕就是從這裡來的）。每一項有 id（ASCII）、label（中文）、templates（題組 id）。", common)
    rs = _sub(tsub, "restore", "templates restore", "把一個內建題組放回（或還原成）內建的版本",
              "setup init --preset=generic 沒裝的題組、或改壞了的，用這個拿回來。只動 templates/ 裡那一個檔，不碰日記。", common)
    rs.add_argument("--id", required=True, help="內建題組 id")

    _sub(sub, "layouts", "layouts", "列出輸出版型", "export 的 --layout 可以用這裡列出的 id。", common)

    e = sub.add_parser("entry", parents=[common], help="寫入、讀出、列出日記（put／show／list）",
                       description="一篇日記＝某一天＋一個題組。put 寫入、show 讀出、list 列出最近的。")
    es = e.add_subparsers(dest="action", parser_class=_Parser, metavar="{put,show,list}")
    put = _sub(es, "put", "entry put", "新增或更新某一天、某個題組的那一篇",
               "內容是一個 JSON 物件，從 stdin 讀（或 --input=檔案）：\n"
               "  {\"answers\": {\"題目 id\": 答案}, \"title\": \"\", \"closing\": \"\", \"theme\": \"\", \"layout\": \"\",\n"
               "   \"source_text\": \"作者原文（--author=ai 時）\", \"sources\": {\"題目 id\": \"這一題的原文\"}}\n"
               "同一天同一個題組再寫一次＝更新那一篇。沒給的題目一律不動。\n"
               "已經有答案的題目：--merge 決定（換掉／接在後面／不動）；--overwrite 點名可以換掉的題目（或 all）。\n"
               "--author=ai：替作者整理的版本。填進去的每一題都標「AI 整理」、旁邊印作者原文（一定要給 --source-text 或 source_text）；\n"
               "作者自己寫過的題目不換（回在 protected），除非 --overwrite 點名。", common)
    put.add_argument("--date", required=True, help="哪一天，YYYY-MM-DD；也收 today／yesterday（照設定 day_start_hour 換日）")
    put.add_argument("--template", required=True, help="題組 id（templates 看全部）")
    put.add_argument("--merge", choices=MERGES, default="fields",
                     help="已經有答案的題目怎麼辦：fields＝換成新的（預設）；append＝接在後面；fill＝不動、只填空著的")
    put.add_argument("--format", choices=FORMATS, default="plain",
                     help="文字是純文字（plain，預設，會跳脫、保留換行）還是編輯器的 HTML（html）")
    put.add_argument("--overwrite", default="",
                     help="可以換掉的題目 id，逗號分開（例 --overwrite=verse1,learned）；all＝全部給了的題目。沒點名的照 --merge")
    put.add_argument("--author", choices=AUTHORS, default="user",
                     help="user（預設）＝作者自己的話；ai＝替作者整理的版本（標 AI 整理、附原文、不蓋作者寫的）")
    put.add_argument("--source-text", help="--author=ai 時：作者原文的 UTF-8 檔案（整篇一份；每一題各自的原文放 JSON 的 sources）")
    put.add_argument("--input", help="從這個 UTF-8 檔案讀內容，不從 stdin（Windows PowerShell 管線會把中文弄壞時用）")
    show = _sub(es, "show", "entry show", "讀出一篇，或某一天的全部",
                "給 --id，或給 --date（可再加 --template 只看那一個題組）。每一篇有 text（純文字）、answers（原始答案）、\n"
                "provenance（哪幾題是 AI 整理的、作者原文）。", common)
    show.add_argument("--id", type=int, help="日記編號（put、list 回的 id）")
    show.add_argument("--date", help="哪一天，YYYY-MM-DD（也收 today／yesterday）")
    show.add_argument("--template", help="只看這個題組的那一篇")
    lst = _sub(es, "list", "entry list", "最近寫過的日記",
               "只有日期、題組、字數、編號，不印內容。", common)
    lst.add_argument("--limit", type=int, default=30, help="最多幾篇（1–500，預設 30）")

    x = _sub(sub, "export", "export", "把一篇輸出成 HTML 頁面和（或）卡片 SVG",
             "給 --id，或 --date 加 --template。檔案寫到日記資料夾的 exports/（設定 export_dir 或 --out-dir 可以換），回傳完整路徑。\n"
             "--layout、--theme 只影響這一次輸出，不改那一篇的設定。每一次都照現在存的內容重新畫，改過就是新的。", common)
    x.add_argument("--id", type=int, help="日記編號")
    x.add_argument("--date", help="哪一天，YYYY-MM-DD（要搭 --template；也收 today／yesterday）")
    x.add_argument("--template", help="題組 id")
    x.add_argument("--format", choices=EXPORTS, default="both", help="both＝HTML＋卡片（預設）；html；card")
    x.add_argument("--layout", help="版型 id（layouts 看全部）")
    x.add_argument("--theme", help="紙張顏色：letterpress、notebook、linen、dawn、midnight")
    x.add_argument("--width", type=int, default=1080, help="卡片寬度，480–2400（預設 1080）")
    x.add_argument("--paper", choices=PAPERS, help="卡片的紙：ruled、grid、plain、dotted（預設跟版型）")
    x.add_argument("--out-dir", help="輸出到這個資料夾（預設是設定 export_dir，再不然是日記資料夾的 exports/）")

    st = _sub(sub, "settings", "settings", "看、改設定（跟網頁「管理顏色」與輸出選項存的是同一份 preferences.json）",
              "不帶參數列出每一個設定：現在的值、預設、是什麼、怎麼寫。get 看一個，set 改一個。", common)
    stsub = st.add_subparsers(dest="action", parser_class=_Parser, metavar="{get,set}")
    sg2 = _sub(stsub, "get", "settings get", "看一個設定", "回 {\"key\", \"value\", \"default\", \"what\", \"how\"}。", common)
    sg2.add_argument("--key", required=True, help="設定名（settings 看全部）")
    ss = _sub(stsub, "set", "settings set", "改一個設定",
              "值可以是字、數字、true／false，或 JSON（palette 這種清單）；default＝放回內建的值。不合的值會說為什麼、什麼都不改。", common)
    ss.add_argument("--key", required=True, help="設定名（settings 看全部）")
    ss.add_argument("--value", required=True, help="新的值（寫成 --value=…）")

    su = _sub(sub, "setup", "setup", "這份安裝的狀態；init 替新的資料夾挑起始題組",
              "不帶參數：資料夾在哪、用了哪個起始組合、幾個題組、幾篇日記。", common)
    susub = su.add_subparsers(dest="action", parser_class=_Parser, metavar="{init}")
    si = _sub(susub, "init", "setup init", "替一個（新的）日記資料夾挑起始題組",
              "generic＝一般：記事、感恩、三段回看、情緒、擔心、週回顧，不談信仰；devotional＝全部內建題組（這是沒跑過 init 時的樣子）。\n"
              "只加不刪：已經有的題組一個都不動；之後想要沒裝的題組，templates restore --id= 拿回來。", common)
    si.add_argument("--preset", choices=PRESETS, required=True, help="generic 或 devotional")
    return p


# --------------------------------------------------------------------------
# Value shaping
# --------------------------------------------------------------------------


def _day(raw: str | None) -> date:
    word = str(raw or "").strip().lower()
    if word in DAY_WORDS:
        from backend import preferences

        now = datetime.now()
        if now.hour < preferences.load().day_start_hour:
            now -= timedelta(days=1)
        return (now - timedelta(days=DAY_WORDS[word])).date()
    try:
        return date.fromisoformat(str(raw or ""))
    except ValueError as exc:
        raise CliError(f"日期要寫成 YYYY-MM-DD（收到：{raw}）") from exc


def _rich(text: str) -> str:
    """Plain text → the editor's HTML: escaped, newlines kept as line breaks."""
    return html.escape(text.strip(), quote=False).replace("\r\n", "\n").replace("\n", "<br>")


def _lines(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v) for v in value if v is not None and str(v).strip()]
    if value is None:
        return []
    return [ln for ln in str(value).replace("\r\n", "\n").split("\n") if ln.strip()]


def _option(field, value: Any) -> str | None:
    """An option id, given the id or the label (assistants send either)."""
    text = str(value or "").strip()
    for o in field.options:
        if text in (o.id, o.label):
            return o.id
    return None


def _shape(field, value: Any, fmt: str) -> tuple[Any, str | None]:
    """(stored value, None) or (None, why it was ignored)."""
    from backend.models import FieldKind

    kind = field.kind
    if kind in (FieldKind.CHOICE, FieldKind.SCALE):
        picked = _option(field, value)
        if picked is None:
            if str(value or "").strip():
                return None, "不是這一題的選項"
            return None, "空的"
        return picked, None
    if kind is FieldKind.MULTI_CHOICE:
        raw = value if isinstance(value, list) else str(value or "").replace("，", "、").replace(",", "、").split("、")
        picked = [p for p in (_option(field, v) for v in raw) if p]
        unknown = [str(v) for v in raw if str(v).strip() and _option(field, v) is None]
        if not picked:
            return None, "不是這一題的選項" if unknown else "空的"
        return list(dict.fromkeys(picked)), ("有幾個不是選項，略過：" + "、".join(unknown)) if unknown else None
    if kind is FieldKind.SHORT_TEXT:
        text = "、".join(_lines(value)) if isinstance(value, list) else str(value or "").strip()
        return (text, None) if text else (None, "空的")
    if kind is FieldKind.FILL:
        blanks = max((field.pattern or "").count("{}"), 1)
        items = [str(v).strip() for v in value] if isinstance(value, list) else [str(value or "").strip()]
        items = (items + [""] * blanks)[:blanks]
        return (items, None) if any(items) else (None, "空的")
    if kind is FieldKind.LIST:
        items = _lines(value)
        if fmt == "plain":
            items = [_rich(i) for i in items]
        return (items, None) if items else (None, "空的")
    # TEXT
    text = "\n".join(_lines(value)) if isinstance(value, list) else str(value or "")
    if not text.strip():
        return None, "空的"
    return (_rich(text) if fmt == "plain" else text), None


def _is_blank(value: Any) -> bool:
    from backend.richtext import to_plain

    if value is None:
        return True
    if isinstance(value, list):
        return not any(to_plain(str(v)).strip() for v in value)
    return not to_plain(str(value)).strip()


def _merge(field, old: Any, new: Any, mode: str) -> Any:
    from backend.models import FieldKind

    if mode != "append" or _is_blank(old):
        return new
    if field.kind in (FieldKind.LIST, FieldKind.MULTI_CHOICE):
        merged = list(old) + [v for v in new if field.kind is FieldKind.LIST or v not in old]
        return merged
    if field.kind is FieldKind.TEXT:
        return f"{old}<br><br>{new}"
    if field.kind is FieldKind.SHORT_TEXT:
        return f"{old}；{new}"
    return new  # a choice, a fill: the new answer is the answer


class _Overwrite:
    """Which fields ``--overwrite`` lets a write replace."""

    def __init__(self, raw: str, known: set[str]):
        self.all = raw.strip().lower() == "all"
        self.ids = set() if self.all else {v.strip() for v in raw.split(",") if v.strip()}
        unknown = sorted(self.ids - known - {"closing"})
        if unknown:
            raise CliError(f"--overwrite 點名的題目這個題組沒有：{'、'.join(unknown)}（templates --id= 看每一題的 id）")

    def __contains__(self, field_id: str) -> bool:
        return self.all or field_id in self.ids


# --------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------


def _template_json(t, brief: bool = False) -> dict:
    out = {
        "id": t.id, "name": t.name, "description": t.description, "group": t.group or "其他",
        "order": t.order, "when": t.when, "minutes": t.minutes, "moods": t.moods, "tags": t.tags,
        "structure": t.structure, "reflection": t.reflection, "flow": t.flow,
        "default_layout": t.default_layout, "default_theme": t.default_theme,
        "closing_label": t.closing_label,
        "fields": sum(len(s.fields) for s in t.sections),
    }
    if brief:
        return out
    out["sections"] = [
        {
            "id": s.id, "title": s.title,
            "fields": [
                {
                    "id": f.id, "label": f.label, "kind": f.kind.value,
                    **({"options": [{"id": o.id, "label": o.label} for o in f.options]} if f.options else {}),
                    **({"pattern": f.pattern, "blanks": (f.pattern or "").count("{}")} if f.pattern else {}),
                    **({"hint": f.hint} if f.hint else {}),
                    **({"ai_hint": f.ai_hint} if f.ai_hint else {}),
                }
                for f in s.fields
            ],
        }
        for s in t.sections
    ]
    return out


def cmd_templates(args) -> tuple[dict, str]:
    from backend.models import FLOW_TOKENS, REFLECTIONS, STRUCTURES
    from backend.taxonomy import check_filter_values, filter_templates
    from backend.template_registry import all_templates, get_template

    if args.id:
        t = get_template(args.id)
        if t is None:
            raise CliError(f"找不到題組：{args.id}（python -m backend.cli templates 看全部）")
        data = _template_json(t, args.brief)
        return {"template": data}, f"{t.name}（{t.id}）：{data['fields']} 題"
    problem = check_filter_values(structure=args.structure, reflection=args.reflection, flow=args.flow)
    if problem:
        raise CliError(problem)
    chosen = filter_templates(all_templates(), structure=args.structure, reflection=args.reflection,
                              flow=args.flow, tag=args.tag)
    items = [_template_json(t, args.brief) for t in chosen]
    text = "\n".join(
        f"{t['group']}｜{t['name']}（{t['id']}）約 {t['minutes'] or '?'} 分鐘｜{STRUCTURES[t['structure']]}・"
        f"{REFLECTIONS[t['reflection']]}・{'→'.join(FLOW_TOKENS[f] for f in t['flow'])}：{t['when'] or t['description']}"
        for t in items
    )
    filters = {k: v for k, v in (("structure", args.structure), ("reflection", args.reflection),
                                 ("flow", args.flow), ("tag", args.tag)) if v}
    return {"templates": items, "count": len(items), **({"filters": filters} if filters else {})}, text or "沒有符合的題組。"


def cmd_templates_suggest(args) -> tuple[dict, str]:
    from backend import preferences
    from backend.taxonomy import suggest
    from backend.template_registry import all_templates

    text = str(args.text or "")
    if not text.strip():
        raise CliError("--text 是空的：把使用者寫的那段話放進來")
    prefs = preferences.load()
    result = suggest(text, all_templates(), faith=prefs.suggest_faith, default_id=prefs.template_id or "",
                     limit=max(1, min(20, int(args.limit or 5))))
    lines = [f"{i + 1}. {s['name']}（{s['id']}）{s['score']} 分：" + "；".join(s["why"])
             for i, s in enumerate(result["suggestions"])]
    if result["signals"]:
        lines.append("看到的線索：" + "、".join(f"{s['label']}（{'、'.join(s['words'])}）" for s in result["signals"]))
    return result, "\n".join(lines)


def cmd_templates_categories(args) -> tuple[dict, str]:
    from backend.taxonomy import categories
    from backend.template_registry import all_templates

    cats = categories(all_templates())
    text = "\n".join(
        f"{name}：" + "、".join(f"{c['label']}（{len(c['templates'])}）" for c in cats[name] if c["templates"])
        for name in ("structure", "reflection", "flow", "groups", "tags")
    )
    return cats, text


def cmd_templates_restore(args) -> tuple[dict, str]:
    from backend.seed_manager import restore_default
    from backend.template_registry import get_template

    tid = str(args.id or "").strip()
    if not tid.replace("-", "").replace("_", "").isalnum():
        raise CliError("題組 id 只能是英數字、- 和 _")
    if not restore_default(f"templates/{tid}.json"):
        raise CliError(f"{tid} 不是內建題組，沒有可以放回的版本")
    t = get_template(tid)
    return {"template": _template_json(t, True) if t else {"id": tid}}, f"放回了內建的「{t.name if t else tid}」（{tid}）"


def cmd_layouts(args) -> tuple[dict, str]:
    from backend.render.layout_registry import all_layouts

    items = [
        {"id": x.id, "name": x.name, "description": x.description, "tags": x.tags,
         "default_theme": x.default_theme, "card_paper": x.card_paper}
        for x in all_layouts()
    ]
    return {"layouts": items}, "\n".join(f"{x['name']}（{x['id']}）：{x['description']}" for x in items)


def _ai_fields(entry) -> list[str]:
    marks = entry.provenance.get("fields", {}) if isinstance(entry.provenance, dict) else {}
    if not isinstance(marks, dict):
        return []
    return sorted(k for k, v in marks.items() if isinstance(v, dict) and v.get("author") == "ai")


def _summary(entry, template=None) -> dict:
    from backend.richtext import to_plain

    def count(value: Any) -> int:
        if isinstance(value, list):
            return sum(len(to_plain(str(v)).strip()) for v in value)
        return len(to_plain(str(value or "")).strip())

    kinds = {f.id: f.kind.value for f in template.field_map().values()} if template else {}
    chars = count(entry.closing) + sum(
        count(v) for k, v in entry.answers.items() if kinds.get(k) not in ("choice", "scale", "multi_choice")
    )
    return {
        "id": entry.id, "date": entry.entry_date.isoformat(), "template": entry.template_id,
        "template_name": template.name if template else entry.template_id, "title": entry.title,
        "layout": entry.layout, "theme": entry.theme, "chars": chars,
        "ai_fields": _ai_fields(entry),
        "updated_at": entry.updated_at.isoformat(timespec="seconds"),
    }


def _read_text_file(path: str, what: str) -> str:
    try:
        data = Path(path).read_bytes()
    except OSError as exc:
        raise CliError(f"讀不到{what}的檔案：{path}（{type(exc).__name__}）") from exc
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise CliError(f"{what}的檔案要是 UTF-8：{path}") from exc


def _read_payload(path: str | None = None) -> dict:
    if path:
        try:
            data = Path(path).read_bytes()
        except OSError as exc:
            raise CliError(f"讀不到 --input 的檔案：{path}（{type(exc).__name__}）") from exc
        source = "--input 的檔案"
    else:
        stdin = sys.stdin
        data = stdin.buffer.read() if stdin is not None and not stdin.isatty() else b""
        source = "stdin"
    try:
        raw = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise CliError(f"{source}要是 UTF-8（Windows PowerShell 的管線會換成別的編碼：改用 --input=檔案）") from exc
    if not raw.strip():
        raise CliError(f"{source}是空的：要給一個 JSON 物件，例如 {{\"answers\": {{\"fact\": \"今天…\"}}}}")
    try:
        payload = json.loads(raw)
    except ValueError as exc:
        raise CliError(f"stdin 不是 JSON：{exc}") from exc
    if not isinstance(payload, dict):
        raise CliError("stdin 要是一個 JSON 物件（{...}）")
    answers = payload.get("answers", {})
    if not isinstance(answers, dict):
        raise CliError("answers 要是一個物件：{\"題目 id\": 答案}")
    sources = payload.get("sources", {})
    if sources and not isinstance(sources, dict):
        raise CliError("sources 要是一個物件：{\"題目 id\": \"這一題的原文\"}")
    return payload


def cmd_entry_put(args) -> tuple[dict, str]:
    from backend import backup, storage
    from backend.models import EntryCreate, EntryUpdate
    from backend.render.themes import THEMES
    from backend.richtext import sanitize
    from backend.services import sanitize_answers
    from backend.template_registry import get_template

    day = _day(args.date)
    template = get_template(args.template)
    if template is None:
        raise CliError(f"找不到題組：{args.template}（python -m backend.cli templates 看全部）")
    ai = args.author == "ai"
    if ai and args.merge == "append":
        raise CliError("--author=ai 不能搭 --merge=append：會把 AI 整理的字接在作者的字後面、混成一段。用 fill（只填空的）或 --overwrite 點名")
    payload = _read_payload(args.input)
    fields = template.field_map()
    overwrite = _Overwrite(args.overwrite or "", set(fields))
    source_text = _read_text_file(args.source_text, "--source-text").strip() if args.source_text else \
        str(payload.get("source_text") or "").strip()
    sources = {str(k): str(v).strip() for k, v in (payload.get("sources") or {}).items() if str(v).strip()}
    if ai and not (source_text or sources):
        raise CliError("--author=ai 一定要附作者原文：--source-text=檔案，或 JSON 裡的 source_text（整篇）／sources（每一題）。"
                       "AI 整理的版本永遠跟原文一起存。")

    existing = storage.get_entry_for(day, template.id)
    stored = dict(existing.answers) if existing else {}
    provenance = dict(existing.provenance) if existing and isinstance(existing.provenance, dict) else {}
    marks = dict(provenance.get("fields") or {})
    now = datetime.now().isoformat(timespec="seconds")
    changed: dict[str, Any] = {}
    filled, kept, protected, overwritten, ignored = [], [], [], [], []

    def decide(field_id: str, old: Any) -> str:
        """replace | append | keep | protect — what happens to a field that already has an answer."""
        if _is_blank(old) or field_id in overwrite:
            return "replace"
        if args.merge == "fill":
            return "keep"
        if ai:
            return "protect"          # the author's words stay unless named in --overwrite
        return "append" if args.merge == "append" else "replace"

    def mark(field_id: str) -> None:
        if ai:
            marks[field_id] = {"author": "ai", "at": now, **({"source": sources[field_id]} if field_id in sources else {})}
        else:
            marks.pop(field_id, None)

    for field_id, value in payload.get("answers", {}).items():
        field = fields.get(str(field_id))
        if field is None:
            ignored.append({"field": str(field_id), "why": "這個題組沒有這一題"})
            continue
        shaped, why = _shape(field, value, args.format)
        if shaped is None:
            if why != "空的":
                ignored.append({"field": field.id, "why": why})
            continue
        if why:
            ignored.append({"field": field.id, "why": why})
        verdict = decide(field.id, stored.get(field.id))
        if verdict == "keep":
            kept.append(field.id)
            continue
        if verdict == "protect":
            protected.append(field.id)
            continue
        if verdict == "replace" and not _is_blank(stored.get(field.id)):
            overwritten.append(field.id)
        changed[field.id] = _merge(field, stored.get(field.id), shaped, verdict)
        filled.append(field.id)
        mark(field.id)

    closing_in = str(payload.get("closing") or "")
    closing = None
    if closing_in.strip():
        new = _rich(closing_in) if args.format == "plain" else closing_in
        old = existing.closing if existing else ""
        verdict = decide("closing", old)
        if verdict == "keep":
            kept.append("closing")
        elif verdict == "protect":
            protected.append("closing")
        else:
            if verdict == "replace" and not _is_blank(old):
                overwritten.append("closing")
            closing = sanitize(f"{old}<br><br>{new}" if verdict == "append" else new)
            filled.append("closing")
            mark("closing")
    title = str(payload.get("title") or "").strip()[:120]
    theme = str(payload.get("theme") or "") or None
    layout = str(payload.get("layout") or "") or None

    new_provenance = None
    if ai and filled:
        kept_text = str(provenance.get("source_text") or "").strip()
        if source_text and source_text not in kept_text:
            kept_text = f"{kept_text}\n\n{source_text}".strip()
        new_provenance = {**provenance, "fields": marks, **({"source_text": kept_text} if kept_text else {})}
    elif marks != (provenance.get("fields") or {}):
        new_provenance = {**provenance, "fields": marks}

    # The app keeps a rolling copy of the database; a write from here counts as
    # a reason to take one too, the same way the app does on start.
    backup.snapshot_if_stale("cli")
    if existing is None:
        entry = storage.create_entry(
            EntryCreate(
                entry_date=day, template_id=template.id, title=title,
                theme=theme if theme in THEMES else template.default_theme,
                layout=layout or template.default_layout,
                answers=sanitize_answers(template, changed), closing=closing or "",
                provenance=new_provenance or {},
            )
        )
        created = True
    else:
        update = EntryUpdate(
            answers=sanitize_answers(template, {**stored, **changed}) if changed else None,
            closing=closing,
            title=title if title and (args.merge != "fill" or not existing.title) else None,
            theme=theme if theme in THEMES else None,
            layout=layout,
            provenance=new_provenance,
        )
        entry = storage.update_entry(existing.id, update) or existing
        created = False

    result = {"entry": _summary(entry, template), "created": created, "author": args.author,
              "filled": filled, "kept": kept, "protected": protected, "overwritten": overwritten, "ignored": ignored}
    verb = "新增" if created else "更新"
    text = f"{verb}了 {entry.entry_date} 的「{template.name}」（#{entry.id}）：填了 {len(filled)} 題"
    if ai and filled:
        text += "（標為 AI 整理、附作者原文）"
    if overwritten:
        text += f"，其中 {len(overwritten)} 題換掉了原本的答案"
    if kept:
        text += f"，{len(kept)} 題原本就有寫、沒有動"
    if protected:
        text += f"，{len(protected)} 題是作者自己寫的、沒有動（要換要 --overwrite 點名）"
    if ignored:
        text += f"，{len(ignored)} 題略過"
    return result, text


def _entry_json(entry) -> dict:
    from backend.render.document import build_document
    from backend.services import recovery_template
    from backend.template_registry import get_template

    template = get_template(entry.template_id) or recovery_template(entry)
    return {**_summary(entry, template), "answers": entry.answers, "closing": entry.closing,
            "provenance": entry.provenance, "text": build_document(entry, template).to_plain_text()}


def cmd_entry_show(args) -> tuple[dict, str]:
    from backend import storage

    if args.id is not None:
        entry = storage.get_entry(args.id)
        if entry is None:
            raise CliError(f"找不到日記 #{args.id}")
        entries = [entry]
        day = entry.entry_date.isoformat()
    else:
        if not args.date:
            raise CliError("要給 --id=<編號> 或 --date=YYYY-MM-DD")
        d = _day(args.date)
        day = d.isoformat()
        if args.template:
            one = storage.get_entry_for(d, args.template)
            entries = [one] if one else []
        else:
            entries = storage.list_entries_on(d)
    items = [_entry_json(e) for e in entries]
    text = "\n\n".join(i["text"] for i in items) or f"{day} 還沒有日記。"
    return {"date": day, "entries": items, "count": len(items)}, text


def cmd_entry_list(args) -> tuple[dict, str]:
    from backend import storage
    from backend.template_registry import get_template

    limit = max(1, min(int(args.limit or 30), 500))
    items = [_summary(e, get_template(e.template_id)) for e in storage.list_entries(limit=limit)]
    text = "\n".join(f"{i['date']}　{i['template_name']}　{i['chars']} 字（#{i['id']}）" for i in items)
    return {"entries": items}, text or "還沒有任何日記。"


def cmd_export(args) -> tuple[dict, str]:
    import re

    from backend import preferences, storage
    from backend.config import settings
    from backend.render.artifact_html import render_document
    from backend.render.card_svg import render_document_svg
    from backend.render.document import build_document
    from backend.render.layout_registry import get_layout
    from backend.render.themes import THEMES
    from backend.services import recovery_template
    from backend.template_registry import get_template

    if args.id is not None:
        entry = storage.get_entry(args.id)
        if entry is None:
            raise CliError(f"找不到日記 #{args.id}")
    else:
        if not (args.date and args.template):
            raise CliError("要給 --id=<編號>，或 --date=YYYY-MM-DD 加 --template=<題組>")
        entry = storage.get_entry_for(_day(args.date), args.template)
        if entry is None:
            raise CliError(f"{args.date} 還沒有用「{args.template}」寫的日記")
    template = get_template(entry.template_id) or recovery_template(entry)

    updates: dict[str, str] = {}
    if args.theme:
        if args.theme not in THEMES:
            raise CliError(f"沒有這種紙張顏色：{args.theme}（{'／'.join(THEMES)}）")
        updates["theme"] = args.theme
    if args.layout:
        if not _layout_exists(args.layout):      # get_layout() falls back to the default; that is not "exists"
            raise CliError(f"沒有這個版型：{args.layout}（python -m backend.cli layouts 看全部）")
        updates["layout"] = args.layout
    if updates:
        entry = entry.model_copy(update=updates)
    doc = build_document(entry, template)

    configured = preferences.load().export_dir
    out_dir = Path(args.out_dir) if args.out_dir else Path(configured) if configured else settings.exports_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = re.sub(r"[^0-9A-Za-z._-]+", "-", f"{entry.entry_date.isoformat()}-{entry.template_id}-{entry.id}")
    result: dict[str, Any] = {"entry": _summary(entry, template), "layout": doc.layout, "theme": doc.theme}
    if args.format in ("both", "html"):
        page = out_dir / f"{stem}.html"
        page.write_text(render_document(doc), encoding="utf-8")
        result["html"] = str(page.resolve())
    if args.format in ("both", "card"):
        chosen = get_layout(doc.layout)
        paper = args.paper or (chosen.card_paper if chosen else "ruled")
        width = max(480, min(2400, int(args.width or 1080)))
        svg = render_document_svg(doc, width=width, paper=paper)
        m = re.search(r'height="(\d+)', svg)
        card = out_dir / f"{stem}.svg"
        card.write_text(svg, encoding="utf-8")
        result.update(svg=str(card.resolve()), width=width, height=int(m.group(1)) if m else 0, paper=paper)
    names = "、".join(Path(result[k]).name for k in ("html", "svg") if k in result)
    return result, f"輸出了 {entry.entry_date} 的「{template.name}」：{names}（在 {out_dir}）"


def _layout_exists(layout_id: str) -> bool:
    from backend.render.layout_registry import all_layouts

    return any(x.id == layout_id for x in all_layouts())


def _setting_row(row: dict) -> str:
    return f"{row['key']} = {json.dumps(row['value'], ensure_ascii=False)}　（{row['what']}；{row['how']}）"


def cmd_settings(args) -> tuple[dict, str]:
    from backend import preferences
    from backend.config import settings

    rows = preferences.describe()
    return {"settings": rows, "file": str(settings.data_dir / "preferences.json")}, "\n".join(_setting_row(r) for r in rows)


def cmd_settings_get(args) -> tuple[dict, str]:
    from backend import preferences

    rows = {r["key"]: r for r in preferences.describe()}
    row = rows.get(str(args.key or ""))
    if row is None:
        raise CliError(f"沒有這個設定：{args.key}（有：{'、'.join(rows)}）")
    return row, _setting_row(row)


def cmd_settings_set(args) -> tuple[dict, str]:
    from backend import preferences
    from backend.render.themes import THEMES
    from backend.template_registry import get_template

    key, value = str(args.key or ""), str(args.value if args.value is not None else "")
    checks = {
        "template_id": (lambda v: get_template(v) is not None, "沒有這個題組（templates 看全部）"),
        "layout": (_layout_exists, "沒有這個版型（layouts 看全部）"),
        "theme": (lambda v: v in THEMES, f"紙張顏色只有 {'、'.join(THEMES)}"),
        "card_paper": (lambda v: v in PAPERS, f"紙只有 {'、'.join(PAPERS)}"),
    }
    if key in checks and value not in ("", "default", "null", "none"):
        ok, why = checks[key]
        if not ok(value):
            raise CliError(f"{key} 的值不對：{why}（收到：{value}）")
    try:
        prefs = preferences.set_value(key, value)
    except ValueError as exc:
        raise CliError(str(exc)) from exc
    row = next(r for r in preferences.describe() if r["key"] == key)
    return {**row, "saved": True, "settings": prefs.model_dump(mode="json")}, "改好了：" + _setting_row(row)


def cmd_setup(args) -> tuple[dict, str]:
    from backend import preferences, storage
    from backend.config import settings
    from backend.seed_manager import presets
    from backend.template_registry import all_templates

    prefs = preferences.load()
    counts = storage.stats()
    tids = [t.id for t in all_templates()]
    result = {
        "data_dir": str(settings.data_dir), "preset": prefs.preset or "",
        "presets": {k: v.get("label", k) for k, v in presets().items()},
        "templates": len(tids), "template_ids": tids, "entries": counts["entries"],
        "preferences": prefs.model_dump(mode="json"),
    }
    text = (f"日記資料夾：{settings.data_dir}\n起始組合：{prefs.preset or '（沒跑過 setup init＝全部內建題組）'}\n"
            f"題組：{len(tids)} 個；日記：{counts['entries']} 篇")
    return result, text


def cmd_setup_init(args) -> tuple[dict, str]:
    from backend.seed_manager import init_preset

    try:
        result = init_preset(args.preset)
    except ValueError as exc:
        raise CliError(str(exc)) from exc
    text = (f"用「{result['label']}」設好了：裝了 {len(result['templates_added'])} 個題組"
            f"（原本就有 {len(result['already_had'])} 個，一個都沒動），現在共 {len(result['templates_now'])} 個；"
            f"設定：{json.dumps(result['settings'], ensure_ascii=False)}")
    return result, text


COMMANDS = {
    ("templates", None): cmd_templates,
    ("templates", "suggest"): cmd_templates_suggest,
    ("templates", "categories"): cmd_templates_categories,
    ("templates", "restore"): cmd_templates_restore,
    ("layouts", None): cmd_layouts,
    ("entry", "put"): cmd_entry_put,
    ("entry", "show"): cmd_entry_show,
    ("entry", "list"): cmd_entry_list,
    ("export", None): cmd_export,
    ("settings", None): cmd_settings,
    ("settings", "get"): cmd_settings_get,
    ("settings", "set"): cmd_settings_set,
    ("setup", None): cmd_setup,
    ("setup", "init"): cmd_setup_init,
}


def _emit(envelope: dict) -> None:
    sys.stdout.write(json.dumps(envelope, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def main(argv: list[str] | None = None) -> int:
    # Windows consoles default to a legacy code page (cp950 here), which cannot
    # encode most of what a journal holds — emoji included. Everything this
    # prints is UTF-8, whatever PYTHONIOENCODING says; ``replace`` so that even
    # a lone surrogate from a bad payload cannot crash the last line.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    as_json = "--json" in (argv if argv is not None else sys.argv[1:])
    try:
        args = _parser().parse_args(argv)
        if getattr(args, "data_dir", None):
            # backend.config reads this when first imported, which is below.
            os.environ["JOURNAL_DATA_DIR"] = str(Path(args.data_dir).resolve())
        key = (args.command, getattr(args, "action", None))
        handler = COMMANDS.get(key)
        if handler is None:
            raise CliError("要做什麼？templates、layouts、entry put|show|list、export、settings、setup（-h 看說明）")

        from backend import storage
        from backend.seed_manager import install_seeds

        # ``setup init`` chooses which defaults to install; everything else
        # installs them the way the app does on start.
        if key != ("setup", "init"):
            install_seeds()
        storage.init_db()
        result, text = handler(args)
    except CliError as exc:
        if not as_json:
            print(f"✗ {exc}", file=sys.stderr)
        _emit({"ok": False, "error": str(exc)})
        return 1
    except Exception as exc:  # noqa: BLE001 - always end with the envelope
        if not as_json:
            print(f"✗ 出錯了：{exc!r}", file=sys.stderr)
        _emit({"ok": False, "error": f"出錯了：{type(exc).__name__}: {exc}"})
        return 1
    if not as_json and text:
        print(text)
    _emit({"ok": True, "result": result})
    return 0


if __name__ == "__main__":
    sys.exit(main())
