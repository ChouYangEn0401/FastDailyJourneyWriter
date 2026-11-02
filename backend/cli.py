"""Command line for the journal: read the question sets, write and read an
entry, export it — without starting the server.

    python -m backend.cli templates [--id=<id>] [--brief]
    python -m backend.cli layouts
    python -m backend.cli entry put --date=YYYY-MM-DD --template=<id>
                                    [--merge=fields|append|fill] [--format=plain|html]  < payload.json
    python -m backend.cli entry show (--id=N | --date=YYYY-MM-DD [--template=<id>])
    python -m backend.cli entry list [--limit=30]
    python -m backend.cli export (--id=N | --date=YYYY-MM-DD --template=<id>)
                                 [--format=both|html|card] [--layout=] [--theme=]
                                 [--width=1080] [--paper=] [--out-dir=]

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

``entry put`` reads one JSON object from stdin::

    {"answers": {"<field id>": <value>, ...}, "title": "", "closing": "",
     "theme": "", "layout": ""}

Values follow the field kind (see docs/templates.md). To be forgiving with
assistants, a choice may be given by its label as well as its id, a list may
be one string with one item per line, and with ``--format=plain`` (the
default) text is plain text — escaped and given line breaks here — rather
than the editor's HTML.

``--merge`` decides what happens to a field that already has an answer:
``fields`` replaces it (fields not mentioned are always kept), ``append``
adds to it (list items after the existing ones, text after a blank line) and
``fill`` leaves it alone and reports it under ``kept``.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import sys
from datetime import date
from pathlib import Path
from typing import Any

MERGES = ("fields", "append", "fill")
FORMATS = ("plain", "html")
EXPORTS = ("both", "html", "card")
PAPERS = ("ruled", "grid", "plain", "dotted")


class CliError(Exception):
    """Something the person running the command can fix; the message says how."""


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:  # argparse would print usage and exit 2
        raise CliError(f"參數有誤：{message}")


def _parser() -> argparse.ArgumentParser:
    # Accepted before or after the sub-command. SUPPRESS, because a sub-parser's
    # own default would otherwise overwrite a value given before it.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help="只印最後那一行 JSON")
    common.add_argument("--data-dir", default=argparse.SUPPRESS,
                        help="日記資料夾（預設跟 app 一樣：JOURNAL_DATA_DIR 或 data/）")

    p = _Parser(prog="python -m backend.cli", description="每日日記的命令列。", parents=[common])
    sub = p.add_subparsers(dest="command", parser_class=_Parser)

    t = sub.add_parser("templates", parents=[common], help="列出題組與每一題的結構")
    t.add_argument("--id", help="只看這一個題組")
    t.add_argument("--brief", action="store_true", help="只列名稱、什麼時候用，不列題目")

    sub.add_parser("layouts", parents=[common], help="列出輸出版型")

    e = sub.add_parser("entry", parents=[common], help="寫入、讀出一篇日記")
    es = e.add_subparsers(dest="action", parser_class=_Parser)
    put = es.add_parser("put", parents=[common], help="新增或更新某一天、某個題組的那一篇（內容從 stdin 的 JSON）")
    put.add_argument("--date", required=True)
    put.add_argument("--template", required=True)
    put.add_argument("--merge", choices=MERGES, default="fields")
    put.add_argument("--format", choices=FORMATS, default="plain")
    show = es.add_parser("show", parents=[common], help="讀出一篇（或某一天的全部）")
    show.add_argument("--id", type=int)
    show.add_argument("--date")
    show.add_argument("--template")
    lst = es.add_parser("list", parents=[common], help="最近寫過的日記（只有日期、題組、字數）")
    lst.add_argument("--limit", type=int, default=30)

    x = sub.add_parser("export", parents=[common], help="把一篇輸出成 HTML 頁面和（或）卡片 SVG")
    x.add_argument("--id", type=int)
    x.add_argument("--date")
    x.add_argument("--template")
    x.add_argument("--format", choices=EXPORTS, default="both")
    x.add_argument("--layout")
    x.add_argument("--theme")
    x.add_argument("--width", type=int, default=1080)
    x.add_argument("--paper", choices=PAPERS)
    x.add_argument("--out-dir")
    return p


# --------------------------------------------------------------------------
# Value shaping
# --------------------------------------------------------------------------


def _day(raw: str | None) -> date:
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


# --------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------


def _template_json(t, brief: bool = False) -> dict:
    out = {
        "id": t.id, "name": t.name, "description": t.description, "group": t.group or "其他",
        "order": t.order, "when": t.when, "minutes": t.minutes, "moods": t.moods, "tags": t.tags,
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
    from backend.template_registry import all_templates, get_template

    if args.id:
        t = get_template(args.id)
        if t is None:
            raise CliError(f"找不到題組：{args.id}（python -m backend.cli templates 看全部）")
        data = _template_json(t, args.brief)
        return {"template": data}, f"{t.name}（{t.id}）：{data['fields']} 題"
    items = [_template_json(t, args.brief) for t in all_templates()]
    text = "\n".join(
        f"{t['group']}｜{t['name']}（{t['id']}）約 {t['minutes'] or '?'} 分鐘：{t['when'] or t['description']}"
        for t in items
    )
    return {"templates": items, "count": len(items)}, text


def cmd_layouts(args) -> tuple[dict, str]:
    from backend.render.layout_registry import all_layouts

    items = [
        {"id": x.id, "name": x.name, "description": x.description, "tags": x.tags,
         "default_theme": x.default_theme, "card_paper": x.card_paper}
        for x in all_layouts()
    ]
    return {"layouts": items}, "\n".join(f"{x['name']}（{x['id']}）：{x['description']}" for x in items)


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
        "updated_at": entry.updated_at.isoformat(timespec="seconds"),
    }


def _read_payload() -> dict:
    raw = sys.stdin.buffer.read().decode("utf-8-sig") if not sys.stdin.isatty() else ""
    if not raw.strip():
        raise CliError("stdin 是空的：要給一個 JSON 物件，例如 {\"answers\": {\"fact\": \"今天…\"}}")
    try:
        payload = json.loads(raw)
    except ValueError as exc:
        raise CliError(f"stdin 不是 JSON：{exc}") from exc
    if not isinstance(payload, dict):
        raise CliError("stdin 要是一個 JSON 物件（{...}）")
    answers = payload.get("answers", {})
    if not isinstance(answers, dict):
        raise CliError("answers 要是一個物件：{\"題目 id\": 答案}")
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
    payload = _read_payload()
    fields = template.field_map()

    existing = storage.get_entry_for(day, template.id)
    stored = dict(existing.answers) if existing else {}
    changed: dict[str, Any] = {}
    filled, kept, ignored = [], [], []
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
        if args.merge == "fill" and not _is_blank(stored.get(field.id)):
            kept.append(field.id)
            continue
        changed[field.id] = _merge(field, stored.get(field.id), shaped, args.merge)
        filled.append(field.id)

    closing_in = str(payload.get("closing") or "")
    closing = None
    if closing_in.strip():
        new = _rich(closing_in) if args.format == "plain" else closing_in
        old = existing.closing if existing else ""
        if args.merge == "fill" and not _is_blank(old):
            kept.append("closing")
        else:
            closing = sanitize(f"{old}<br><br>{new}" if args.merge == "append" and not _is_blank(old) else new)
            filled.append("closing")
    title = str(payload.get("title") or "").strip()[:120]
    theme = str(payload.get("theme") or "") or None
    layout = str(payload.get("layout") or "") or None

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
        )
        entry = storage.update_entry(existing.id, update) or existing
        created = False

    result = {"entry": _summary(entry, template), "created": created,
              "filled": filled, "kept": kept, "ignored": ignored}
    verb = "新增" if created else "更新"
    text = f"{verb}了 {entry.entry_date} 的「{template.name}」（#{entry.id}）：填了 {len(filled)} 題"
    if kept:
        text += f"，{len(kept)} 題原本就有寫、沒有動"
    if ignored:
        text += f"，{len(ignored)} 題略過"
    return result, text


def _entry_json(entry) -> dict:
    from backend.render.document import build_document
    from backend.services import recovery_template
    from backend.template_registry import get_template

    template = get_template(entry.template_id) or recovery_template(entry)
    return {**_summary(entry, template), "answers": entry.answers, "closing": entry.closing,
            "text": build_document(entry, template).to_plain_text()}


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

    from backend import storage
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
        if get_layout(args.layout) is None:
            raise CliError(f"沒有這個版型：{args.layout}（python -m backend.cli layouts 看全部）")
        updates["layout"] = args.layout
    if updates:
        entry = entry.model_copy(update=updates)
    doc = build_document(entry, template)

    out_dir = Path(args.out_dir) if args.out_dir else settings.exports_dir
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


COMMANDS = {
    ("templates", None): cmd_templates,
    ("layouts", None): cmd_layouts,
    ("entry", "put"): cmd_entry_put,
    ("entry", "show"): cmd_entry_show,
    ("entry", "list"): cmd_entry_list,
    ("export", None): cmd_export,
}


def _emit(envelope: dict) -> None:
    sys.stdout.write(json.dumps(envelope, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def main(argv: list[str] | None = None) -> int:
    # Windows consoles default to a legacy code page; everything here is UTF-8.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
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
            raise CliError("要做什麼？templates、layouts、entry put|show|list、export（-h 看說明）")

        from backend import storage
        from backend.seed_manager import install_seeds

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
