"""Classify question sets, and suggest one from what somebody wrote.

Every set carries three ASCII labels (``backend/models.py``): ``structure``
(one-part / three-part / n-part), ``reflection`` (none / reflection /
devotional / prayer — a ladder, each level includes the ones before) and
``flow`` (the steps it walks through, in order: ``events``, ``scripture``,
``reflection``, ``prayer``…). :func:`categories` hands those vocabularies to a
picker (the Telegram side draws its buttons from it); :func:`filter_templates`
narrows the list by them.

:func:`suggest` ranks the sets for a piece of writing **by rule, not by a
model**: a table of signals (``content/suggest.json``, overridable by
``data/suggest.json``) says which words point at which steps, moods and tags,
and every point a set earns is reported back as a sentence, so the person can
see *why* a set came first and the rule can be tuned by editing the table.
Faith-oriented sets are only put forward when the text mentions faith unless
the ``suggest_faith`` setting says otherwise — the tool must not push belief
on someone who did not bring it up.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from backend.config import PROJECT_ROOT, settings
from backend.models import FLOW_TOKENS, REFLECTIONS, STRUCTURES, FieldKind, JournalTemplate

log = logging.getLogger(__name__)

SHIPPED_RULES = PROJECT_ROOT / "content" / "suggest.json"
FAITH_LEVELS = ("devotional", "prayer")


def categories(templates: list[JournalTemplate]) -> dict[str, Any]:
    """The vocabularies, with labels, plus which sets fall under each value."""
    def bucket(key: str, vocab: dict[str, str], pick) -> list[dict]:
        return [
            {"id": tid, "label": label, "templates": [t.id for t in templates if pick(t, tid)]}
            for tid, label in vocab.items()
        ]

    tags: dict[str, list[str]] = {}
    groups: dict[str, list[str]] = {}
    for t in templates:
        for tag in t.tags:
            tags.setdefault(tag, []).append(t.id)
        groups.setdefault(t.group or "其他", []).append(t.id)
    return {
        "structure": bucket("structure", STRUCTURES, lambda t, v: t.structure == v),
        "reflection": bucket("reflection", REFLECTIONS, lambda t, v: t.reflection == v),
        "flow": bucket("flow", FLOW_TOKENS, lambda t, v: v in t.flow),
        "tags": [{"id": k, "label": k, "templates": v} for k, v in sorted(tags.items(), key=lambda kv: -len(kv[1]))],
        "groups": [{"id": k, "label": k, "templates": v} for k, v in groups.items()],
    }


def filter_templates(templates: list[JournalTemplate], *, structure: str = "", reflection: str = "",
                     flow: str = "", tag: str = "") -> list[JournalTemplate]:
    """Keep the sets matching every given filter (an empty filter matches all).

    ``reflection`` matches exactly; ``reflection=none,reflection`` (a comma
    list) matches any of them, which is how "不談信仰" is asked for.
    """
    def wanted(raw: str) -> set[str]:
        return {v.strip() for v in raw.split(",") if v.strip()}

    out = templates
    if structure:
        out = [t for t in out if t.structure in wanted(structure)]
    if reflection:
        out = [t for t in out if t.reflection in wanted(reflection)]
    if flow:
        out = [t for t in out if wanted(flow) <= set(t.flow)]
    if tag:
        out = [t for t in out if wanted(tag) & set(t.tags)]
    return out


def check_filter_values(*, structure: str = "", reflection: str = "", flow: str = "") -> str | None:
    """A sentence naming the first unknown filter value, or None."""
    for raw, vocab, name in ((structure, STRUCTURES, "structure"), (reflection, REFLECTIONS, "reflection"),
                             (flow, FLOW_TOKENS, "flow")):
        for v in (x.strip() for x in raw.split(",") if x.strip()):
            if v not in vocab:
                return f"沒有這種 {name}：{v}（有：{'、'.join(vocab)}）"
    return None


# --------------------------------------------------------------------------
# Suggestion
# --------------------------------------------------------------------------


def load_rules() -> dict[str, Any]:
    """``data/suggest.json`` if the person made one, else the shipped table."""
    for path in (settings.data_dir / "suggest.json", SHIPPED_RULES):
        try:
            raw = json.loads(Path(path).read_text(encoding="utf-8-sig"))
        except FileNotFoundError:
            continue
        except Exception as exc:  # noqa: BLE001 - a bad override must not kill the shipped rule
            log.warning("Ignoring %s: %s", path, exc)
            continue
        if isinstance(raw, dict) and isinstance(raw.get("signals"), dict):
            return raw
    return {"signals": {}, "length": {"short": 40, "long": 300}, "faith_penalty": 4}


def _writing_length(text: str) -> int:
    return len([c for c in text if not c.isspace()])


def _has_text_field(t: JournalTemplate) -> bool:
    return any(f.kind in (FieldKind.TEXT, FieldKind.LIST) for s in t.sections for f in s.fields)


def detect_signals(text: str, rules: dict[str, Any]) -> list[dict[str, Any]]:
    """Which signals fire on this text, with the words that fired them."""
    found = []
    for sid, rule in rules.get("signals", {}).items():
        if not isinstance(rule, dict):
            continue
        hits = [w for w in rule.get("words", []) if isinstance(w, str) and w and w in text]
        if hits:
            found.append({"id": sid, "label": rule.get("label", sid), "words": hits[:5], "rule": rule})
    return found


def suggest(text: str, templates: list[JournalTemplate], *, faith: str = "auto", default_id: str = "",
            limit: int = 5, rules: dict[str, Any] | None = None) -> dict[str, Any]:
    """Rank ``templates`` for ``text``. Pure function of the text, the sets and the table.

    Returns ``{"suggestions": [{"id", "name", "score", "why": [...]}, ...],
    "signals": [{"id", "label", "words"}], "length": N, "categories": {...}}``.
    ``categories`` is what a picker would pre-select: the reflection level
    and flow steps the text points at.
    """
    rules = rules or load_rules()
    text = text or ""
    length = _writing_length(text)
    bounds = rules.get("length", {}) if isinstance(rules.get("length"), dict) else {}
    short_max, long_min = int(bounds.get("short", 40)), int(bounds.get("long", 300))
    penalty = int(rules.get("faith_penalty", 4))
    signals = detect_signals(text, rules)
    faith_seen = any(s["id"] == "faith" for s in signals)

    scored: list[tuple[float, int, JournalTemplate, list[str]]] = []
    for t in templates:
        score, why = 0.0, []
        if t.reflection in FAITH_LEVELS and not faith_seen:
            if faith == "never":
                continue
            if faith == "auto":
                score -= penalty
                why.append("沒提到信仰，先放後面")
        for s in signals:
            rule, word = s["rule"], "「" + s["words"][0] + "」"
            weight = float(rule.get("weight", 1))
            matched = []
            if set(rule.get("flow", [])) & set(t.flow):
                matched.append("、".join(FLOW_TOKENS.get(f, f) for f in rule.get("flow", []) if f in t.flow))
            if set(rule.get("moods", [])) & set(t.moods):
                matched.append("心情：" + "、".join(m for m in rule.get("moods", []) if m in t.moods))
            if set(rule.get("tags", [])) & set(t.tags):
                matched.append("標籤：" + "、".join(g for g in rule.get("tags", []) if g in t.tags))
            if t.id in rule.get("templates", []):
                score += weight * 1.5
                matched.append("這個題組就是為這種時候做的")
            if matched:
                # weight per matching word (capped), plus one for every extra
                # facet (step, mood, tag) the same signal lines up with
                score += weight * min(len(s["words"]), 3) + (len(matched) - 1)
                why.append(f"提到{word}→ {'；'.join(matched)}")
        if length and length <= short_max:
            if t.minutes and t.minutes <= 3:
                score += 2
                why.append(f"寫得很短（{length} 字）→ 快速的題組")
            elif t.minutes >= 15:
                score -= 2
        elif length >= long_min:
            if _has_text_field(t) and t.minutes >= 10:
                score += 2
                why.append(f"寫得很長（{length} 字）→ 有空間書寫的題組")
        if score > 0:
            scored.append((score, t.order, t, why))

    scored.sort(key=lambda row: (-row[0], row[1], row[2].id))
    out = [{"id": t.id, "name": t.name, "group": t.group or "其他", "minutes": t.minutes, "structure": t.structure,
            "reflection": t.reflection, "flow": t.flow, "score": round(score, 1), "why": why}
           for score, _, t, why in scored[:max(1, limit)]]
    if not out:
        by_id = {t.id: t for t in templates}
        for tid in dict.fromkeys([default_id, "jot", "three-lines"]):
            t = by_id.get(tid)
            if t is not None:
                out.append({"id": t.id, "name": t.name, "group": t.group or "其他", "minutes": t.minutes,
                            "structure": t.structure, "reflection": t.reflection, "flow": t.flow, "score": 0,
                            "why": ["沒有特別的線索：照原文記下來最穩"]})
    flows = list(dict.fromkeys(f for s in signals for f in s["rule"].get("flow", []) if f in FLOW_TOKENS))
    level = "prayer" if faith_seen and any("prayer" in s["rule"].get("flow", []) for s in signals) else \
        "devotional" if faith_seen else "reflection" if any(s["id"] in ("learn", "identity") for s in signals) else ""
    return {
        "suggestions": out,
        "signals": [{"id": s["id"], "label": s["label"], "words": s["words"]} for s in signals],
        "length": length,
        "categories": {"reflection": level, "flow": flows},
    }
