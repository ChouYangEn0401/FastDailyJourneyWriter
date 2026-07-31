"""Small optional writing helpers. Exports never depend on these."""

from __future__ import annotations

from app.ai.client import complete
from app.render.document import RenderedDoc

TITLE_SYSTEM = """\
You name a day. Given a devotional journal entry in Traditional Chinese, reply \
with a single short title in Traditional Chinese — 4 to 12 characters, no \
punctuation, no quotes, no explanation, just the title.

Take the title from what the writer actually said. Prefer a concrete image or \
phrase they used over an abstract summary. Do not add language they did not \
use, do not evaluate them, and do not make the day sound tidier or more \
resolved than they wrote it.
"""


def suggest_title(doc: RenderedDoc) -> str:
    raw = complete(
        system=TITLE_SYSTEM,
        user=doc.to_plain_text(),
        max_tokens=2000,
        effort="low",
    )
    return raw.strip().strip("「」\"'。 ")[:24]
