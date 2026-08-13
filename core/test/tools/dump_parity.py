"""Regenerate ``core/test/fixtures/parity.json`` from the Python renderer.

The JavaScript core in ``core/`` is a port, and a port is only worth anything
while it still agrees with the thing it was ported from. So the expected values
in the parity fixture are not written by hand — they are *recorded* from
``backend/``:

    python core/test/tools/dump_parity.py

Then ``npm test`` (or ``node --test core/test/``) replays the same inputs
through the JavaScript and fails on any difference.

Run this after changing anything under ``backend/richtext.py`` or
``backend/render/``. A diff in the fixture is the signal that ``core/`` has to
be changed to match — or that the change was a bug.

This is the one Python file outside ``backend/``. It is test tooling, not part
of the core: nothing under ``core/`` imports it, and the fixture it writes is
committed so the JavaScript tests run without a Python interpreter.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from backend.models import Entry, JournalTemplate  # noqa: E402
from backend.render.artifact_html import runs_to_html  # noqa: E402
from backend.render.document import RenderedDoc, build_document  # noqa: E402
from backend.render.themes import THEMES  # noqa: E402
from backend.richtext import Run, normalize_color, sanitize, to_plain, to_runs  # noqa: E402

OUT = _ROOT / "core" / "test" / "fixtures" / "parity.json"

# --------------------------------------------------------------------------
# Inputs. Every case is here to pin down one decision the port could get wrong.
# --------------------------------------------------------------------------

RICH_TEXT_CASES: list[str] = [
    "",
    "今天很平安。",
    "<b>粗體</b>字",
    "<strong>a</strong><em>b</em><strike>c</strike><u>d</u>",
    '<span style="color: #C00">紅字</span>',
    '<span style="color:#abc">短碼</span>',
    '<span style="color: rgb(200, 50, 44)">rgb</span>',
    '<span style="color: rgba(200,50,44,0.5)">rgba</span>',
    '<span style="color:notacolour">壞值</span>',
    '<span style="font-weight:bold">沒有顏色</span>',
    '<span style="background:#fff;color:#0a0;">在後面的 color</span>',
    "<script>alert(1)</script>後面的字",
    "<style>body{color:red}</style>樣式後面",
    '<img src=x onerror="alert(1)">圖片',
    "<div>第一行</div><div>第二行</div>",
    "<p>段落一</p><p>段落二</p>",
    "第一行<br>第二行",
    "<br><br>前後空行<br><br>",
    "a &amp; b &lt; c &gt; d",
    "已經跳脫的 &amp;lt; 不該再跳脫",
    "&nbsp;&hellip;&mdash;&#20013;&#x6587;",
    "未知實體 &zzz; 原樣留著",
    "<b>沒關的粗體",
    "</b>沒開就關",
    "<b>a<i>b</b>c</i>",
    '<span style="color:#c00">外<span>內</span>回外</span>',
    '<b><span style="color:#ff0000">紅粗</span></b>',
    "<div><b>a</b></div><div>b</div>",
    "文字<svg><circle r='1'/></svg>更多文字",
    "註解<!-- 這段不見 -->後面",
    "<UL><LI>大寫標籤</LI></UL>",
    "<table><tr><td>表格</td></tr></table>",
    "兩個  空格",
    "emoji 🙏 與中文",
    "<b>混排 mixed 中英文 123</b>",
    "<span style=\"color:'#c00'\">怪引號</span>",
    "<3 不是標籤",
    "a<b",
    "<textarea>藏起來</textarea>看得見",
    "<div>a<br></div><div><br></div><div>b</div>",
]

COLOR_CASES: list[str | None] = [
    None,
    "",
    "#fff",
    "#FFF",
    "#a1b2c3",
    "#A1B2C3",
    "  #c00  ",
    "rgb(1,2,3)",
    "rgb(300, 0, 0)",
    "rgba(10, 20, 30, .5)",
    "red",
    "#gggggg",
    "#12345",
]

DEFAULT_COLOR = "#123456"

TEMPLATE = {
    "id": "parity",
    "name": "對照題組",
    "description": "只給測試用",
    "closing_label": "給主的話",
    "sections": [
        {
            "id": "morning",
            "title": "早晨",
            "color": "#b5623c",
            "icon": "☀",
            "fields": [
                {"id": "mood", "label": "今天的心情", "kind": "scale",
                 "options": [{"id": "good", "label": "很好"},
                             {"id": "ok", "label": "還可以"},
                             {"id": "low", "label": "低落"}]},
                {"id": "met", "label": "見了誰", "kind": "multi_choice",
                 "options": [{"id": "family", "label": "家人"},
                             {"id": "friend", "label": "朋友"},
                             {"id": "none", "label": "沒有人"}]},
                {"id": "verse", "label": "今天的經文", "kind": "short_text"},
                {"id": "fill", "label": "一句話", "kind": "fill",
                 "pattern": "今天讀了 {} ，最觸動我的是 {} 。"},
            ],
        },
        {
            "id": "evening",
            "title": "夜裡",
            "color": "#5d7a5a",
            "fields": [
                {"id": "thanks", "label": "感恩", "kind": "list", "color": "#1f7a4d"},
                {"id": "long", "label": "想寫的", "kind": "text"},
                {"id": "never", "label": "永遠沒填的", "kind": "text"},
            ],
        },
        {
            "id": "empty_section",
            "title": "整段沒寫",
            "color": "#8a5fbf",
            "fields": [{"id": "unused", "label": "沒用到", "kind": "text"}],
        },
    ],
}

ENTRIES: list[dict] = [
    {
        "label": "full",
        "entry": {
            "id": 7,
            "entry_date": "2026-08-11",
            "title": "  平常的一天  ",
            "template_id": "parity",
            "theme": "linen",
            "layout": "letter",
            "answers": {
                "mood": "ok",
                "met": ["family", "friend"],
                "verse": "詩篇 23",
                "fill": ["約翰福音 15", "住在我裡面"],
                "thanks": ["<b>早餐</b>", "  ", '<span style="color:#c00">下午的雨</span>'],
                "long": "第一段<br>第二段<div>第三段</div>",
            },
            "closing": "<b>親愛的主</b>，<br>今天謝謝祢。",
            "field_colors": {"long": "#2456b8"},
            "created_at": "2026-08-11T08:00:00",
            "updated_at": "2026-08-11T21:30:00",
        },
    },
    {
        "label": "sparse",
        "entry": {
            "id": 8,
            "entry_date": "2026-01-01",
            "title": "",
            "template_id": "parity",
            "theme": "midnight",
            "layout": "postcard",
            "answers": {"mood": "good"},
            "closing": "",
            "field_colors": {},
            "created_at": "2026-01-01T00:00:00",
            "updated_at": "2026-01-01T00:00:00",
        },
    },
    {
        "label": "blank",
        "entry": {
            "id": 9,
            "entry_date": "2027-02-28",
            "title": "",
            "template_id": "parity",
            "theme": "letterpress",
            "layout": "letter",
            "answers": {},
            "closing": "   ",
            "field_colors": {},
            "created_at": "2027-02-28T00:00:00",
            "updated_at": "2027-02-28T00:00:00",
        },
    },
]

#: One per weekday, so the Monday-is-0 mapping is pinned down rather than
#: assumed. 2026-08-10 is a Monday.
WEEKDAY_DATES = [f"2026-08-{day:02d}" for day in range(10, 17)]


# --------------------------------------------------------------------------
# Serialisation. The JavaScript side mirrors these shapes exactly.
# --------------------------------------------------------------------------


def run_json(run: Run) -> dict:
    return {
        "text": run.text,
        "color": run.color,
        "bold": run.bold,
        "italic": run.italic,
    }


def lines_json(lines: list[list[Run]]) -> list[list[dict]]:
    return [[run_json(r) for r in line] for line in lines]


def doc_json(doc: RenderedDoc) -> dict:
    return {
        "entry_id": doc.entry_id,
        "title": doc.title,
        "entry_date": doc.entry_date.isoformat(),
        "date_display": doc.date_display,
        "weekday": doc.weekday,
        "template_name": doc.template_name,
        "theme": doc.theme,
        "layout": doc.layout,
        "word_count": doc.word_count,
        "palette": doc.palette,
        "closing_label": doc.closing_label,
        "has_closing": doc.has_closing,
        "closing_lines": lines_json(doc.closing_lines),
        "plain_text": doc.to_plain_text(),
        "sections": [
            {
                "id": s.id,
                "title": s.title,
                "color": s.color,
                "icon": s.icon,
                "is_empty": s.is_empty,
                "fields": [
                    {
                        "id": f.id,
                        "label": f.label,
                        "kind": f.kind.value,
                        "color": f.color,
                        "numbered": f.numbered,
                        "plain": f.plain,
                        "is_empty": f.is_empty,
                        "chips": [
                            {"label": c.label, "selected": c.selected} for c in f.chips
                        ],
                        "lines": lines_json(f.lines),
                    }
                    for f in s.fields
                ],
            }
            for s in doc.sections
        ],
    }


def main() -> None:
    template = JournalTemplate.model_validate(TEMPLATE)

    payload = {
        "_note": (
            "Generated by core/test/tools/dump_parity.py — do not hand-edit. "
            "These are the Python renderer's answers; core/ must reproduce them."
        ),
        "default_color": DEFAULT_COLOR,
        "sanitize": [{"raw": raw, "out": sanitize(raw)} for raw in RICH_TEXT_CASES],
        "to_runs": [
            {"raw": raw, "runs": [run_json(r) for r in to_runs(raw, DEFAULT_COLOR)]}
            for raw in RICH_TEXT_CASES
        ],
        "to_runs_no_default": [
            {"raw": raw, "runs": [run_json(r) for r in to_runs(raw)]}
            for raw in RICH_TEXT_CASES
        ],
        "to_plain": [{"raw": raw, "out": to_plain(raw)} for raw in RICH_TEXT_CASES],
        "runs_to_html": [
            {"raw": raw, "out": str(runs_to_html(to_runs(raw, DEFAULT_COLOR)))}
            for raw in RICH_TEXT_CASES
        ],
        "normalize_color": [
            {"raw": raw, "out": normalize_color(raw)} for raw in COLOR_CASES
        ],
        "themes": {
            tid: {
                k: v
                for k, v in vars(theme).items()
                if not k.startswith("_")
            }
            for tid, theme in THEMES.items()
        },
        "template": TEMPLATE,
        "documents": [
            {
                "label": case["label"],
                "entry": case["entry"],
                "doc": doc_json(
                    build_document(Entry.model_validate(case["entry"]), template)
                ),
                "doc_keep_empty": doc_json(
                    build_document(
                        Entry.model_validate(case["entry"]), template, drop_empty=False
                    )
                ),
            }
            for case in ENTRIES
        ],
        "weekdays": [
            {
                "date": d,
                "weekday": build_document(
                    Entry.model_validate({**ENTRIES[0]["entry"], "entry_date": d}),
                    template,
                ).weekday,
            }
            for d in WEEKDAY_DATES
        ],
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    counts = {k: len(v) for k, v in payload.items() if isinstance(v, list)}
    print(f"wrote {OUT.relative_to(_ROOT)}")
    for name, n in counts.items():
        print(f"  {name}: {n} cases")


if __name__ == "__main__":
    main()
